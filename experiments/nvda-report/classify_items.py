"""Gemini 배치 분류 → items의 ai_* 컬럼 (기획서 4-A · 12절).

- 대상: kind ∈ CLASSIFY_KINDS · prefilter_reason IS NULL · analyzed_at IS NULL · published_at ≥ since. 오래된 것부터.
- 배치 하나(20건)를 한 호출로. 항목별 검증(enum·범위·필수)에 통과한 것만 쓴다.
- 신규성 판단용으로 최근 7일의 ai_fact 목록(최대 30)을 함께 준다.
- 검증 탈락은 classify_attempts를 올리고, CLASSIFY_MAX_ATTEMPTS를 넘으면 prefilter_reason='classify_failed'로 제외한다.
- is_event = relevance ≥ 2 and novelty ∈ {new, update}  (6절 문서형 조건)
"""

import datetime
import json
import os
import sys

import config
import db
import labels
from gemini_client import GeminiPool

PROMPT_FILE = os.path.join(config.PROMPTS_DIR, "classify.txt")


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def pending_items(conn, since_days, limit):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    kinds = ",".join(f"'{k}'" for k in config.CLASSIFY_KINDS)
    rows = conn.execute(
        f"""SELECT item_id, kind, source, published_at, title, summary, raw_json FROM items
            WHERE kind IN ({kinds}) AND prefilter_reason IS NULL AND analyzed_at IS NULL AND published_at >= ?
            ORDER BY published_at ASC LIMIT ?""", (since, limit)).fetchall()
    # 오래된 것부터 — 최신부터 하면 원보도가 나중 기사의 'repeat'로 밀린다 (2026-10-08 확인)
    return [dict(r) for r in rows]


def recent_facts(conn, days=config.NOVELTY_WINDOW_DAYS, limit=config.NOVELTY_CONTEXT_MAX):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT published_at, ai_area, ai_fact FROM items
           WHERE analyzed_at IS NOT NULL AND ai_fact IS NOT NULL AND ai_relevance >= 1 AND published_at >= ?
           ORDER BY published_at DESC LIMIT ?""", (since, limit)).fetchall()
    return [f"{r['published_at'][:10]} [{r['ai_area']}] {r['ai_fact']}" for r in rows]


def _text_for(item):
    raw = db.loads(item["raw_json"], {}) or {}
    body = raw.get("body") or ""
    text = item["summary"] or ""
    if body:
        text = (text + " " + body).strip()
    return text[:config.MAX_TEXT_CHARS]


def _str_list(value, limit=8):
    if not isinstance(value, list):
        return []
    out = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return list(dict.fromkeys(out))[:limit]


def validate_item(item, batch_ids):
    if not isinstance(item, dict):
        return None
    iid = str(item.get("item_id", "")).strip()
    if iid not in batch_ids:
        return None
    area, direction, novelty = item.get("area"), item.get("direction"), item.get("novelty")
    try:
        relevance = int(item.get("relevance"))
    except (TypeError, ValueError):
        return None
    lo, hi = config.RELEVANCE_RANGE
    if area not in config.AREAS or direction not in config.DIRECTIONS or novelty not in config.NOVELTIES:
        return None
    if not (lo <= relevance <= hi):
        return None
    fact = item.get("fact")
    if not isinstance(fact, str) or not fact.strip():
        return None
    if area == "Other":
        relevance, direction = 0, "neutral"
    ents = item.get("entities") if isinstance(item.get("entities"), dict) else {}
    return {
        "item_id": iid, "ai_area": area, "ai_direction": direction, "ai_novelty": novelty, "ai_relevance": relevance,
        "ai_fact": fact.strip()[:300],
        "ai_entities": db.dumps({"tickers": [t.upper() for t in _str_list(ents.get("tickers"))],
                                 "countries": _str_list(ents.get("countries")), "products": _str_list(ents.get("products"))}),
        "is_event": 1 if (relevance >= config.RELEVANCE_EVENT_MIN and novelty in ("new", "update")) else 0,
    }


def classify_batch(pool, prompt_head, batch, facts):
    payload = {
        "recent_facts": facts,
        "items": [{
            "item_id": it["item_id"], "kind": it["kind"], "source": it["source"], "published_at": it["published_at"],
            "title": it["title"], "text": _text_for(it),
        } for it in batch],
    }
    prompt = prompt_head + json.dumps(payload, ensure_ascii=False, indent=1)
    result = pool.generate_json(prompt)
    if isinstance(result, dict):
        result = result.get("items") or result.get("results") or [result]
    if not isinstance(result, list):
        return []
    batch_ids = {it["item_id"] for it in batch}
    meta = {it["item_id"]: it for it in batch}
    valid = []
    for item in result:
        v = validate_item(item, batch_ids)
        if v:
            v["source"], v["title"] = meta[v["item_id"]]["source"], meta[v["item_id"]]["title"]
            v, _ = labels.adjust(v)   # 해설 매체·주가 기사 상한 (결정적)
            valid.append(v)
    return valid


def write_results(conn, valid, model, batch):
    now = db.now_iso()
    conn.executemany(
        """UPDATE items SET ai_area=:ai_area, ai_direction=:ai_direction, ai_novelty=:ai_novelty, ai_relevance=:ai_relevance,
             ai_fact=:ai_fact, ai_entities=:ai_entities, is_event=:is_event, analyzed_at=:analyzed_at, ai_model=:ai_model
           WHERE item_id=:item_id AND analyzed_at IS NULL""",
        [dict(v, analyzed_at=now, ai_model=model) for v in valid])
    ok = {v["item_id"] for v in valid}
    failed = [it["item_id"] for it in batch if it["item_id"] not in ok]
    if failed:
        conn.executemany("UPDATE items SET classify_attempts = classify_attempts + 1 WHERE item_id = ?", [(i,) for i in failed])
        conn.execute("UPDATE items SET prefilter_reason = 'classify_failed' WHERE analyzed_at IS NULL AND prefilter_reason IS NULL "
                     "AND classify_attempts >= ?", (config.CLASSIFY_MAX_ATTEMPTS,))
    conn.commit()
    return len(failed)


def classify(conn, since_days=config.CLASSIFY_SINCE_DAYS, max_batches=config.CLASSIFY_MAX_BATCHES_PER_RUN,
             batch_size=config.CLASSIFY_BATCH_SIZE):
    items = pending_items(conn, since_days, limit=max_batches * batch_size)
    if not items:
        print(f"[classify] 대기 0건 (최근 {since_days}일)")
        return 0
    pool = GeminiPool()
    prompt_head = _load_prompt()
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    print(f"[classify] 대기 {len(items):,}건 → {len(batches)}배치")
    written = dropped_total = failed_batches = 0
    for n, batch in enumerate(batches, 1):
        facts = recent_facts(conn)
        try:
            valid = classify_batch(pool, prompt_head, batch, facts)
        except Exception as e:  # noqa: BLE001
            print(f"[classify] 배치 {n}/{len(batches)} 실패: {str(e)[:200]}")
            failed_batches += 1
            if failed_batches >= 3:
                print("[classify] 연속 실패 — 이번 실행 중단. 다음 실행이 이어받는다.")
                break
            continue
        dropped = write_results(conn, valid, pool.model, batch)
        written += len(valid)
        dropped_total += dropped
        ev = sum(v["is_event"] for v in valid)
        print(f"[classify] 배치 {n}/{len(batches)}: {len(valid)}건 저장 (이벤트 {ev})" + (f" · {dropped}건 검증 탈락" if dropped else ""))
    print(f"[classify] 완료 — 저장 {written:,}건 · 검증 탈락 {dropped_total} · Gemini 호출 {pool.calls}회")
    db.set_meta(conn, "classify_last_run_at", db.now_iso())
    conn.commit()
    return written


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    mb = int(sys.argv[sys.argv.index("--max-batches") + 1]) if "--max-batches" in sys.argv else config.CLASSIFY_MAX_BATCHES_PER_RUN
    classify(db.connect(), max_batches=mb)
