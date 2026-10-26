"""2차 소스(기사 제목) → 인물의 직접 발언만 (기획 2절 · 6절 3단계).

① 규칙 거르기 (LLM 없음): 제목에 그 인물 이름(config aliases)이 없으면 no_name, 말한 형태(SPEECH_RE)가 없으면 no_speech.
② 같은 발언 묶기: 같은 인물 · 48시간 안 제목 토큰 자카드 ≥ GROUP_JACCARD → 한 묶음, 대표 = 가장 이른 기사.
   이미 추출된 묶음에 붙는 새 기사는 LLM 없이 그 결과를 따른다 (매체 수만 는다).
③ 인용 추출 (LLM, 묶음 대표만): 그 인물이 직접 한 새 발언 · 행동인가 · 한 문장 인용 · 같은 1차 항목.
   사슬은 config.EXTRACT_CHAIN — 예비 공급자 먼저, Gemini 맨 뒤.

    python extract.py              # 거르기 + 묶기 + 추출
    python extract.py --no-llm     # ① ② 만
"""

import argparse
import datetime
import json
import os
import re
import sys

import config
import db

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
from llm_chain import LLMPool, usage_line  # noqa: E402

STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with", "as", "at", "by", "is", "are", "its",
             "it", "this", "that", "from", "after", "over", "amid", "says", "say", "said", "new", "vs", "how", "why",
             "what", "he", "his", "will", "be", "was", "has", "have", "not", "no", "us", "u", "s"}
MAX_PRIMARY_IN_PROMPT = 20
MAX_HEADLINES_PER_GROUP = 4
PRIMARY_LOOKBACK_HOURS = 96   # 기사는 발언 · 공시보다 늦다 — ARK 10-15 공시를 10-18 기사가 다룸 (2026-10-19 시험)


def _since(hours):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def tokens(title, speaker):
    t = (title or "").lower().replace("’", "'")
    for a in config.PEOPLE[speaker]["aliases"]:   # 인물 이름은 모든 제목에 있으니 비교에서 뺀다
        t = t.replace(a.replace("’", "'"), " ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return {w for w in t.split() if w not in STOPWORDS and len(w) > 1}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ── ① 규칙 거르기 ────────────────────────────────────────────────────────

def prefilter(conn, since):
    rows = conn.execute("""SELECT id, speaker, title FROM statements
                           WHERE source_kind='secondary' AND extracted_at IS NULL AND prefilter_reason IS NULL
                             AND group_id IS NULL AND published_at >= ?""", (since,)).fetchall()
    speech = re.compile(config.SPEECH_RE, re.I)
    drops = {"no_name": 0, "no_speech": 0}
    for r in rows:
        t = r["title"].lower().replace("’", "'")
        reason = None
        if not any(a.replace("’", "'") in t for a in config.PEOPLE[r["speaker"]]["aliases"]):
            reason = "no_name"
        elif not speech.search(r["title"]):
            reason = "no_speech"
        if reason:
            drops[reason] += 1
            conn.execute("UPDATE statements SET prefilter_reason=?, extracted_at=? WHERE id=?", (reason, db.now_iso(), r["id"]))
    conn.commit()
    print(f"[extract] 거르기: {len(rows)}건 중 이름 없음 {drops['no_name']} · 말한 형태 없음 {drops['no_speech']} · 통과 {len(rows) - sum(drops.values())}")


# ── ② 묶기 ───────────────────────────────────────────────────────────────

def group(conn, since):
    rows = conn.execute("""SELECT id, speaker, title, publisher, published_at, group_id, extracted_at FROM statements
                           WHERE source_kind='secondary' AND prefilter_reason IS NULL AND published_at >= ?
                           ORDER BY speaker, published_at""", (since,)).fetchall()
    groups = {}   # (speaker) → [ [rep_id, tokens] ]
    new_members = 0
    for r in rows:
        toks = tokens(r["title"], r["speaker"])
        cands = groups.setdefault(r["speaker"], [])
        if r["group_id"]:
            if r["group_id"] == r["id"]:
                cands.append([r["id"], toks])
            continue
        best = max(cands, key=lambda c: jaccard(c[1], toks), default=None)
        if best and jaccard(best[1], toks) >= config.GROUP_JACCARD:
            conn.execute("UPDATE statements SET group_id=? WHERE id=?", (best[0], r["id"]))
            best[1] |= toks   # 묶음이 다른 표현도 받도록 토큰을 넓힌다
            new_members += 1
        else:
            conn.execute("UPDATE statements SET group_id=? WHERE id=?", (r["id"], r["id"]))
            cands.append([r["id"], toks])
    # 묶음 크기(매체 수) · 이미 추출된 묶음에 붙은 새 기사는 대표 결과를 따른다
    conn.execute("""UPDATE statements SET group_size = (
                        SELECT COUNT(DISTINCT COALESCE(m.publisher, m.id)) FROM statements m WHERE m.group_id = statements.id)
                    WHERE group_id = id AND published_at >= ?""", (since,))
    conn.execute("""UPDATE statements SET extracted_at = (SELECT g.extracted_at FROM statements g WHERE g.id = statements.group_id)
                    WHERE group_id != id AND extracted_at IS NULL
                      AND (SELECT g.extracted_at FROM statements g WHERE g.id = statements.group_id) IS NOT NULL""")
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM statements WHERE group_id = id AND published_at >= ?", (since,)).fetchone()[0]
    print(f"[extract] 묶기: 통과 {len(rows)}건 → 묶음 {n}개 (이번에 묶음에 붙은 기사 {new_members})")


# ── ③ 인용 추출 ─────────────────────────────────────────────────────────

def _payload(conn, rep):
    heads = conn.execute("""SELECT title, publisher FROM statements WHERE group_id=? ORDER BY published_at LIMIT ?""",
                         (rep["id"], MAX_HEADLINES_PER_GROUP)).fetchall()
    lo = (datetime.datetime.fromisoformat(rep["published_at"].replace("Z", "+00:00"))
          - datetime.timedelta(hours=PRIMARY_LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prim = conn.execute("""SELECT id, title FROM statements WHERE speaker=? AND source_kind='primary'
                           AND published_at BETWEEN ? AND ? ORDER BY published_at DESC LIMIT ?""",
                        (rep["speaker"], lo, rep["published_at"], MAX_PRIMARY_IN_PROMPT)).fetchall()
    p = config.PEOPLE[rep["speaker"]]
    return {
        "group_id": rep["id"],
        "speaker": f'{p["aliases"][0].title()} ({p["title_ko"]})',
        "headlines": [f'{h["title"]} — {h["publisher"]}' for h in heads],
        "primary": [{"id": x["id"], "title": x["title"][:200]} for x in prim],
    }


def _batch_input(payload):
    """1차 목록은 인물마다 한 번만 — 묶음마다 붙이면 같은 목록이 30번 반복돼 Groq 분당 8,000토큰을 넘는다
    (10-26: 배치 하나 12~17K 토큰, 1차 항목 304개 중 고유 23개 → Groq 413 으로 매번 flash-lite 가 받음)."""
    primary = {}
    for p in payload:
        seen = primary.setdefault(p["speaker"], {})
        for x in p["primary"]:
            seen.setdefault(x["id"], x["title"])
    return {"primary": {s: [{"id": i, "title": t} for i, t in items.items()] for s, items in primary.items() if items},
            "groups": [{k: p[k] for k in ("group_id", "speaker", "headlines")} for p in payload]}


def _validate(result, batch_ids, primary_ids):
    if isinstance(result, dict):
        result = result.get("items") or result.get("groups") or [result]
    if not isinstance(result, list):
        return None
    out = {}
    for it in result:
        if not isinstance(it, dict) or it.get("group_id") not in batch_ids:
            continue
        st = it.get("is_statement")
        if not isinstance(st, bool):
            continue
        quote = str(it.get("quote") or "").strip()[:300]
        if st and not quote:
            continue
        same = str(it.get("same_as_primary") or "").strip()
        out[it["group_id"]] = {"is_statement": int(st), "quote": quote if st else None,
                               "dup_of_primary": same if same in primary_ids.get(it["group_id"], set()) else None}
    return out if len(out) >= max(1, int(len(batch_ids) * 0.8)) else None   # 8할 넘게 빠지면 형식 오류로 보고 다음 모델


def extract(conn, since, max_batches=None):
    reps = conn.execute("""SELECT id, speaker, published_at FROM statements
                           WHERE group_id = id AND extracted_at IS NULL AND prefilter_reason IS NULL AND published_at >= ?
                           ORDER BY speaker, published_at""", (since,)).fetchall()   # 같은 인물끼리 한 배치 — 1차 목록이 덜 늘어난다
    if not reps:
        print("[extract] 추출할 묶음 0개")
        return 0
    with open(os.path.join(config.BASE_DIR, "prompts", "extract_quotes.txt"), encoding="utf-8") as f:
        head = f.read()
    pool = LLMPool(config.EXTRACT_CHAIN, label="people-extract")
    batches = [reps[i:i + config.EXTRACT_BATCH] for i in range(0, len(reps), config.EXTRACT_BATCH)]
    if max_batches:
        batches = batches[:max_batches]
    done = 0
    for bi, batch in enumerate(batches, 1):
        payload = [_payload(conn, r) for r in batch]
        ids = {p["group_id"] for p in payload}
        prim_ids = {p["group_id"]: {x["id"] for x in p["primary"]} for p in payload}
        prompt = head + "\n\nINPUT:\n" + json.dumps(_batch_input(payload), ensure_ascii=False, separators=(",", ":"))

        def check(v):
            got = _validate(v, ids, prim_ids)
            if got is None:
                raise ValueError("형식 오류 또는 8할 미만")
            return got
        try:
            got = pool.generate_json(prompt, temperature=0.0, validate=check)
        except RuntimeError as e:
            print(f"[extract] 배치 {bi}/{len(batches)} 실패 — 다음 실행이 이어받는다: {str(e)[:120]}")
            continue
        now = db.now_iso()
        for gid, v in got.items():
            conn.execute("""UPDATE statements SET is_statement=?, quote=?, dup_of_primary=?, extract_model=?, extracted_at=?
                            WHERE id=?""", (v["is_statement"], v["quote"], v["dup_of_primary"], pool.last_model, now, gid))
            conn.execute("UPDATE statements SET extracted_at=? WHERE group_id=? AND id != ?", (now, gid, gid))
        conn.commit()
        yes = sum(v["is_statement"] for v in got.values())
        done += len(got)
        print(f"[extract] 배치 {bi}/{len(batches)}: {len(got)}/{len(batch)}묶음 · 발언 {yes} · {pool.last_model}")
    print(f"[extract] 완료 — 묶음 {done}개 · {usage_line()}")
    return done


QUOTE_JACCARD = 0.4   # 인용문끼리 — LLM 이 고른 표현이라 제목보다 낮은 기준으로도 같은 발언이 묶인다 (10-19: 머스크 SpaceX 주식 발언 8묶음)


def merge_quotes(conn, since):
    """④ 추출 뒤 같은 인물 · 48시간 안 발언 묶음끼리 인용문이 비슷하면 이른 묶음으로 합친다."""
    reps = conn.execute("""SELECT id, speaker, quote FROM statements WHERE group_id = id AND is_statement = 1
                           AND published_at >= ? ORDER BY speaker, published_at""", (since,)).fetchall()
    kept, merged = {}, 0
    for r in reps:
        toks = tokens(r["quote"], r["speaker"])
        cands = kept.setdefault(r["speaker"], [])
        best = max(cands, key=lambda c: jaccard(c[1], toks), default=None)
        if best and jaccard(best[1], toks) >= QUOTE_JACCARD:
            conn.execute("UPDATE statements SET group_id=? WHERE group_id=?", (best[0], r["id"]))
            merged += 1
        else:
            cands.append([r["id"], toks])
    if merged:
        conn.execute("""UPDATE statements SET group_size = (
                            SELECT COUNT(DISTINCT COALESCE(m.publisher, m.id)) FROM statements m WHERE m.group_id = statements.id)
                        WHERE group_id = id AND published_at >= ?""", (since,))
        conn.commit()
    print(f"[extract] 인용문 묶기: 발언 묶음 {len(reps)}개 중 {merged}개를 같은 발언에 합침")


def run(conn, use_llm=True, max_batches=None):
    since = _since(config.EXTRACT_SINCE_HOURS)
    prefilter(conn, since)
    group(conn, since)
    if use_llm:
        extract(conn, since, max_batches=max_batches)
    merge_quotes(conn, since)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--max-batches", type=int)
    a = ap.parse_args()
    run(db.connect(), use_llm=not a.no_llm, max_batches=a.max_batches)
