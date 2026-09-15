"""Gemini 배치 분류 → trump_posts의 ai_* 컬럼 (기획서 4-A · 12절).

- 대상: noise_reason IS NULL AND analyzed_at IS NULL AND published_at >= since
- 최신 글부터 분류한다 — 오늘 리포트에 필요한 데이터가 먼저 채워지도록
- 배치 하나(15개)를 한 호출로. 항목별로 검증해 통과한 것만 쓴다
- 한 번에 최대 N 배치. 남은 건 다음 실행이 analyzed_at IS NULL 로 이어받는다
"""

import datetime
import json
import os
import re
import sys

import config
import db
import labels
import prefilter
from gemini_client import GeminiPool

PROMPT_FILE = os.path.join(config.PROMPTS_DIR, "classify.txt")
TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")
MAX_TEXT_CHARS = 1500


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pending_posts(conn, since_days, limit):
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT id, published_at, content FROM trump_posts
           WHERE noise_reason IS NULL AND analyzed_at IS NULL AND published_at >= ?
           ORDER BY published_at DESC LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _str_list(value, allowed=None, pattern=None):
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if not isinstance(v, str):
            continue
        v = v.strip()
        if not v:
            continue
        if allowed is not None and v not in allowed:
            continue
        if pattern is not None and not pattern.match(v):
            continue
        out.append(v)
    return list(dict.fromkeys(out))


def validate_item(item, batch_ids):
    """항목 하나를 검증해 정규화된 dict 또는 None."""
    if not isinstance(item, dict):
        return None
    pid = str(item.get("post_id", "")).strip()
    if pid not in batch_ids:
        return None
    topic = item.get("topic")
    direction = item.get("direction")
    try:
        intensity = int(item.get("intensity"))
        relevance = int(item.get("market_relevance"))
    except (TypeError, ValueError):
        return None
    lo, hi = config.INTENSITY_RANGE
    rlo, rhi = config.RELEVANCE_RANGE
    if topic not in config.TOPICS or direction not in config.DIRECTIONS:
        return None
    if not (lo <= intensity <= hi) or not (rlo <= relevance <= rhi):
        return None
    subtopic = labels.normalize_subtopic(item.get("subtopic"))[:60]
    return {
        "id": pid,
        "ai_topic": topic,
        "ai_subtopic": subtopic,
        "ai_target_country": db.dumps(_str_list(item.get("target_country"))[:5]),
        "ai_target_sector": db.dumps(_str_list(item.get("target_sector"), allowed=config.SECTORS)[:4]),
        "ai_mentioned_companies": db.dumps(_str_list(item.get("mentioned_companies"), pattern=TICKER_RE)[:8]),
        "ai_direction": direction,
        "ai_intensity": intensity,
        "ai_market_relevance": relevance,
    }


def classify_batch(pool, prompt_head, batch):
    payload = [{
        "post_id": p["id"],
        "published_at": p["published_at"],
        "text": prefilter.clean_text(p["content"])[:MAX_TEXT_CHARS],
    } for p in batch]
    prompt = prompt_head + json.dumps(payload, ensure_ascii=False, indent=1)
    result = pool.generate_json(prompt)
    if isinstance(result, dict):
        result = result.get("items") or result.get("posts") or [result]
    if not isinstance(result, list):
        return []
    batch_ids = {p["id"] for p in batch}
    valid = []
    for item in result:
        v = validate_item(item, batch_ids)
        if v:
            valid.append(v)
    return valid


def write_results(conn, valid, model):
    now = _utc_now()
    conn.executemany(
        """UPDATE trump_posts SET
             ai_topic=:ai_topic, ai_subtopic=:ai_subtopic,
             ai_target_country=:ai_target_country, ai_target_sector=:ai_target_sector,
             ai_mentioned_companies=:ai_mentioned_companies, ai_direction=:ai_direction,
             ai_intensity=:ai_intensity, ai_market_relevance=:ai_market_relevance,
             analyzed_at=:analyzed_at, ai_model=:ai_model
           WHERE id=:id AND analyzed_at IS NULL""",
        [dict(v, analyzed_at=now, ai_model=model) for v in valid],
    )
    conn.commit()


def classify(conn, since_days=config.CLASSIFY_SINCE_DAYS,
             max_batches=config.CLASSIFY_MAX_BATCHES_PER_RUN,
             batch_size=config.CLASSIFY_BATCH_SIZE):
    posts = pending_posts(conn, since_days, limit=max_batches * batch_size)
    remaining_total = conn.execute(
        "SELECT COUNT(*) FROM trump_posts WHERE noise_reason IS NULL AND analyzed_at IS NULL"
    ).fetchone()[0]
    if not posts:
        print(f"[classify] 대기 0건 (최근 {since_days}일) · 전체 미분류 {remaining_total:,}")
        return 0

    pool = GeminiPool()
    prompt_head = _load_prompt()
    batches = [posts[i:i + batch_size] for i in range(0, len(posts), batch_size)]
    print(f"[classify] 대기 {len(posts):,}건 → {len(batches)}배치 (최근 {since_days}일 · 전체 미분류 {remaining_total:,})")

    written = 0
    failed = 0
    for n, batch in enumerate(batches, 1):
        try:
            valid = classify_batch(pool, prompt_head, batch)
        except Exception as e:  # noqa: BLE001
            print(f"[classify] 배치 {n}/{len(batches)} 실패: {str(e)[:200]}")
            failed += 1
            if failed >= 3:
                print("[classify] 연속 실패 — 이번 실행 중단. 다음 실행이 이어받는다.")
                break
            continue
        write_results(conn, valid, pool.model)
        written += len(valid)
        dropped = len(batch) - len(valid)
        print(f"[classify] 배치 {n}/{len(batches)}: {len(valid)}건 저장" + (f" · {dropped}건 검증 탈락" if dropped else ""))

    print(f"[classify] 완료 — 저장 {written:,}건 · Gemini 호출 {pool.calls}회")
    db.set_meta(conn, "classify_last_run_at", _utc_now())
    conn.commit()
    return written


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    load_dotenv(os.path.join(config.BASE_DIR, ".env"))
    mb = int(sys.argv[sys.argv.index("--max-batches") + 1]) if "--max-batches" in sys.argv else config.CLASSIFY_MAX_BATCHES_PER_RUN
    classify(db.connect(), max_batches=mb)
