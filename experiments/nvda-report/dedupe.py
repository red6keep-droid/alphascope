"""중복 표시 · 키워드 1차 필터 (기획서 5절 ①). 분류 전에 돈다. 멱등.

① 외부 기사(kind=news)는 제목+요약에 NVDA 키워드가 있어야 한다 → 없으면 prefilter_reason='no_nvda_keyword'.
② 같은 날 ±1일 안의 문서끼리 제목 정규화(소문자·구두점 제거·회사명 통일) 후 토큰 자카드 ≥ 0.6이면
   뒤의 것에 'duplicate_of:{앞 item_id}'. 뉴스룸·블로그·공시가 있으면 그것이 대표가 되고 외부 기사는 전부 중복이다.
"""

import datetime
import re
import sys

import config
import db

OFFICIAL_KINDS = ("newsroom", "blog", "8k", "form4", "10q", "10k", "fedreg", "court")
STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with", "as", "at", "by", "is", "are", "its",
             "it", "this", "that", "from", "after", "over", "amid", "says", "say", "said", "new", "vs", "how", "why", "what"}
COMPANY_ALIASES = {"nvidia corp": "nvidia", "nvidia corporation": "nvidia", "nvda": "nvidia", "nvidia's": "nvidia"}


def normalize(title):
    t = (title or "").lower()
    for k, v in COMPANY_ALIASES.items():
        t = t.replace(k, v)
    t = re.sub(r"[^a-z0-9가-힣 ]+", " ", t)
    toks = [w for w in t.split() if w not in STOPWORDS and len(w) > 1]
    return set(toks)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def has_keyword(text):
    t = (text or "").lower()
    return any(k in t for k in config.NVDA_KEYWORDS)


def run(conn, since_days=config.CLASSIFY_SINCE_DAYS):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=since_days + 2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [dict(r) for r in conn.execute(
        """SELECT item_id, kind, published_at, title, summary, prefilter_reason FROM items
           WHERE kind IN ('news','newsroom','blog','fedreg','court') AND published_at >= ? ORDER BY published_at""", (since,))]
    n_kw = n_dup = 0
    # ① 키워드
    for r in rows:
        if r["kind"] == "news" and r["prefilter_reason"] is None and not has_keyword(f"{r['title']} {r['summary'] or ''}"):
            conn.execute("UPDATE items SET prefilter_reason = 'no_nvda_keyword' WHERE item_id = ?", (r["item_id"],))
            r["prefilter_reason"] = "no_nvda_keyword"
            n_kw += 1
    # ② 중복 — 대표 후보: 공식 소스 우선, 그다음 먼저 나온 것
    cands = [r for r in rows if r["prefilter_reason"] is None or r["prefilter_reason"].startswith("duplicate_of:")]
    for r in cands:
        r["_tok"] = normalize(r["title"])
        r["_day"] = datetime.date.fromisoformat(r["published_at"][:10])
        r["_rank"] = (0 if r["kind"] in OFFICIAL_KINDS else 1, r["published_at"])
    cands.sort(key=lambda r: r["_rank"])
    reps = []   # 확정된 대표들
    for r in cands:
        dup_of = None
        for p in reps:
            if abs((r["_day"] - p["_day"]).days) > config.DEDUPE_WINDOW_DAYS:
                continue
            if jaccard(r["_tok"], p["_tok"]) >= config.DEDUPE_JACCARD:
                dup_of = p["item_id"]
                break
        reason = f"duplicate_of:{dup_of}" if dup_of else None
        if reason != r["prefilter_reason"]:
            # 분류가 이미 끝난 행의 사유만 바꾼다 (분류 결과는 유지) — 대표가 바뀌는 드문 경우
            conn.execute("UPDATE items SET prefilter_reason = ? WHERE item_id = ?", (reason, r["item_id"]))
            if reason:
                n_dup += 1
        if not dup_of:
            reps.append(r)
    conn.commit()
    pending = conn.execute(
        "SELECT COUNT(*) FROM items WHERE kind IN ('news','newsroom','blog','fedreg','court') AND prefilter_reason IS NULL AND analyzed_at IS NULL"
    ).fetchone()[0]
    print(f"[dedupe] {len(rows)}건 검사 · 키워드 탈락 {n_kw} · 중복 {n_dup} · 분류 대기 {pending}")
    return pending


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run(db.connect())
