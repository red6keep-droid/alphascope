"""발언 → 8칸 라벨 (기획 2절 · 6절 4단계). 인물군(policy · investor · commentator · ceo)마다 프롬프트 · 주제 목록이 다르고
출력 칸은 trump-trend 와 같다 — 묶기 · 반응 통계를 그대로 쓰려고.

대상: 1차 항목 전부(노이즈 제외) + 2차 묶음 대표 중 발언(is_statement=1)이고 1차와 겹치지 않는 것.
트럼프 Truth Social 은 trump-trend 가 매일 Gemini 로 분류한 라벨을 게시물 id 로 가져온다(trump-state). 없으면 정책군 프롬프트로.

    python classify.py
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

import config
import db

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
from llm_chain import LLMPool, usage_line  # noqa: E402
import issue_codes  # noqa: E402  — 이슈 코드 어휘 (공용, doc/기획/이슈-분류-코드표.md)

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,6}$")
LABEL_COLS = ["ai_topic", "ai_subtopic", "ai_target_country", "ai_target_sector", "ai_mentioned_companies",
              "ai_direction", "ai_intensity", "ai_market_relevance", "ai_issue"]


def _since(hours):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _noise(row):
    text = (row["body"] or row["title"] or "").strip()
    if row["collector"] == "cnn_archive":
        if not text or re.fullmatch(r"(https?://\S+\s*)+", text) or text.startswith("RT "):
            return "repost_or_empty"   # trump-trend prefilter 와 같은 기준 (링크만 · 리포스트 · 빈 글)
    return None


# ── 트럼프 라벨 가져오기 ────────────────────────────────────────────────

def load_trump_labels():
    # 파일(CI 가 꺼내 둔 것) + 상태 브랜치(로컬) 둘 다 읽어 합친다 — 로컬 파일은 오래됐을 수 있다 (10-19: 10-11 파일이 먼저 읽혀 0건)
    texts = []
    if os.path.exists(config.TRUMP_LABELS_PATH):
        with open(config.TRUMP_LABELS_PATH, encoding="utf-8") as f:
            texts.append(f.read())
    try:
        texts.append(subprocess.run(["git", "show", config.TRUMP_LABELS_GIT], capture_output=True, text=True,
                                    check=True, cwd=config.BASE_DIR).stdout)
    except Exception as e:  # noqa: BLE001
        print(f"[classify] 상태 브랜치 라벨 못 읽음: {str(e)[:80]}")
    out = {}
    for text in texts:
        for line in text.splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("ai_topic"):
                    out[str(r["id"])] = r
    if not out:
        print("[classify] 트럼프 라벨 없음 — 정책군 프롬프트로 분류")
    return out


def apply_trump_labels(conn, since):
    labels = load_trump_labels()
    rows = conn.execute("""SELECT id, ext_id FROM statements WHERE collector='cnn_archive' AND analyzed_at IS NULL
                           AND noise_reason IS NULL AND published_at >= ?""", (since,)).fetchall()
    n = 0
    for r in rows:
        lab = labels.get(r["ext_id"] or "")
        if not lab:
            continue
        conn.execute(f"""UPDATE statements SET {", ".join(c + "=?" for c in LABEL_COLS)}, analyzed_at=?, ai_model=? WHERE id=?""",
                     [lab.get(c) for c in LABEL_COLS] + [lab.get("analyzed_at") or db.now_iso(),
                                                         "trump-trend:" + str(lab.get("ai_model")), r["id"]])
        n += 1
    conn.commit()
    print(f"[classify] 트럼프 게시물 {len(rows)}건 중 {n}건은 trump-trend 라벨 사용")


# ── 검증 ────────────────────────────────────────────────────────────────

def _str_list(v, allowed=None, pattern=None):
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        x = str(x).strip()
        if not x or (allowed and x not in allowed) or (pattern and not pattern.match(x)):
            continue
        out.append(x)
    return list(dict.fromkeys(out))


def validate_item(item, ids, group):
    if not isinstance(item, dict) or str(item.get("post_id", "")) not in ids:
        return None
    market, nonmarket = config.TOPICS_BY_GROUP[group]
    if item.get("topic") not in market + nonmarket or item.get("direction") not in config.DIRECTIONS:
        return None
    try:
        inten, rel = int(item.get("intensity")), int(item.get("market_relevance"))
    except (TypeError, ValueError):
        return None
    if not (1 <= inten <= 10 and 0 <= rel <= 3):
        return None
    return {
        "id": str(item["post_id"]), "ai_topic": item["topic"], "ai_subtopic": str(item.get("subtopic") or "")[:60],
        "ai_target_country": db.dumps(_str_list(item.get("target_country"))[:5]),
        "ai_target_sector": db.dumps(_str_list(item.get("target_sector"), allowed=config.SECTORS)[:4]),
        "ai_mentioned_companies": db.dumps(_str_list(item.get("mentioned_companies"), pattern=TICKER_RE)[:8]),
        "ai_direction": item["direction"], "ai_intensity": inten, "ai_market_relevance": rel,
        "ai_issue": item.get("issue") if item.get("issue") in issue_codes.ISSUES else issue_codes.FROM_PEOPLE_TOPIC.get(item["topic"], "OTHER"),   # 이슈 코드 (공용 어휘, 2026-10-21) — 모델이 빼먹으면 주제 대응표
    }


# ── 분류 ────────────────────────────────────────────────────────────────

def pending(conn, since):
    return conn.execute("""SELECT * FROM statements WHERE analyzed_at IS NULL AND noise_reason IS NULL AND published_at >= ?
                             AND (source_kind='primary'
                                  OR (group_id = id AND is_statement = 1 AND dup_of_primary IS NULL))
                           ORDER BY speaker, published_at""", (since,)).fetchall()


def _text(r):
    if r["source_kind"] == "secondary":
        return f'{r["quote"]} (headline: {r["title"]})'
    body = r["body"] or ""
    t = r["title"] if not body.startswith(r["title"][:60]) else ""
    return (t + "\n" + body).strip()[:config.CLASSIFY_TEXT_MAX]


def classify(conn, since, max_batches=None):
    for r in conn.execute("SELECT * FROM statements WHERE analyzed_at IS NULL AND noise_reason IS NULL AND published_at >= ?",
                          (since,)).fetchall():
        reason = _noise(r)
        if reason:
            conn.execute("UPDATE statements SET noise_reason=? WHERE id=?", (reason, r["id"]))
    conn.commit()
    apply_trump_labels(conn, since)
    rows = pending(conn, since)
    by_group = {}
    for r in rows:
        by_group.setdefault(config.PEOPLE[r["speaker"]]["group"], []).append(r)
    print(f"[classify] 분류 대기 {len(rows)}건 · " + " · ".join(f"{g} {len(v)}" for g, v in by_group.items()))
    pool = LLMPool(config.CLASSIFY_CHAIN, label="people-classify", skip_when_day_out=config.SKIP_WHEN_DAY_OUT)
    batches = [(g, v[i:i + config.CLASSIFY_BATCH]) for g, v in by_group.items() for i in range(0, len(v), config.CLASSIFY_BATCH)]
    if max_batches:
        batches = batches[:max_batches]
    done = 0
    for bi, (group, batch) in enumerate(batches, 1):
        with open(os.path.join(config.BASE_DIR, "prompts", config.PROMPT_BY_GROUP[group]), encoding="utf-8") as f:
            head = f.read()
        payload = [{"post_id": r["id"], "speaker": f'{config.PEOPLE[r["speaker"]]["aliases"][0].title()} ({config.PEOPLE[r["speaker"]]["title_ko"]})',
                    "attribution": r["attribution"], "published_at": r["published_at"], "text": _text(r)} for r in batch]
        ids = {p["post_id"] for p in payload}

        def check(v, ids=ids, group=group):
            if isinstance(v, dict):
                v = v.get("items") or v.get("posts") or [v]
            got = [x for x in (validate_item(i, ids, group) for i in (v if isinstance(v, list) else [])) if x]
            if len(got) < max(1, int(len(ids) * 0.8)):
                raise ValueError(f"유효 {len(got)}/{len(ids)}")
            return got
        try:
            got = pool.generate_json(head + json.dumps(payload, ensure_ascii=False, indent=1), temperature=0.0, validate=check)
        except RuntimeError as e:
            print(f"[classify] 배치 {bi}/{len(batches)} 실패 — 다음 실행이 이어받는다: {str(e)[:120]}")
            continue
        now = db.now_iso()
        conn.executemany(f"""UPDATE statements SET {", ".join(c + "=:" + c for c in LABEL_COLS)},
                                analyzed_at=:analyzed_at, ai_model=:ai_model WHERE id=:id AND analyzed_at IS NULL""",
                         [dict(v, analyzed_at=now, ai_model=pool.last_model) for v in got])
        conn.commit()
        done += len(got)
        print(f"[classify] 배치 {bi}/{len(batches)} ({group}): {len(got)}/{len(batch)}건 · {pool.last_model}")
    print(f"[classify] 완료 — {done}건 · {usage_line()}")
    return done


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-batches", type=int)
    a = ap.parse_args()
    classify(db.connect(), _since(config.COLLECT_SINCE_HOURS), max_batches=a.max_batches)
