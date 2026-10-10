"""Gemini 라벨 위에 얹는 결정적 보정 규칙 (trump-trend labels.adjust와 같은 패턴). 멱등 — 매 실행 reapply.

2026-10-08 첫 분류 91건에서 반복된 오류를 규칙으로 막는다:
- 해설·전망·투자 조언 매체(Motley Fool, TIKR, Inc. …)와 "Why … / Prediction: / Should you …" 제목은
  1차 자료가 아니라 남의 사실에 대한 논평이다 → relevance 상한 1, novelty 'repeat'.
- 주가 신고가·시가총액·CEO 자산 기사는 상태판이 이미 숫자로 보여 주는 것 → relevance 상한 1, 'repeat'.
규칙은 Gemini 결과를 깎기만 한다 (올리지 않는다). is_event는 보정 뒤 다시 계산한다.
"""

import re
import sys

import config
import db

# Yahoo Finance는 로이터·FT 전재가 많아 넣지 않는다 (제목 규칙으로만 거른다)
OPINION_PUBLISHERS = (
    "motley fool", "tikr", "inc.com", "seeking alpha", "benzinga", "simply wall st", "zacks", "24/7 wall st",
    "investorplace", "barchart", "marketbeat", "the street", "thestreet", "gurufocus", "fool.com", "tipranks",
)
FACT_DUP_BIGRAM_JACCARD = 0.30    # 사실 문장의 글자 2-gram 자카드가 이 이상이면 같은 사건
FACT_DUP_WINDOW_DAYS = 2
OPINION_TITLE_RE = re.compile(
    r"^(why|what|how|should you|is it|is nvidia|here'?s|prediction:|could|will nvidia|can nvidia|forget|better buy|"
    r"\d+ (reasons|things|stocks|catalysts)|the \d+|opinion:|analysis:)\b"
    r"|\b(lesson|explained|what it means|what to know|what investors|best stock|stocks to buy|stock to buy|a buy\b|bull case|bear case|"
    r"could be worth|by 20\d\d\b|jim cramer|cramer)",
    re.I,
)
PRICE_MOVE_RE = re.compile(
    r"\b(record high|all-time high|new high|hits? record|market cap|market value|trillion milestone|"
    r"net worth|fortune|richest|billionaire|soars?|slips?|slides?|tumbles?|jumps?|rallies|rally|surges?|plunges?|dips?|"
    r"stock (is )?(up|down|falls|fell|rises|rose|gains|drops)|shares (fall|fell|rise|rose|jump|drop|gain))\b",
    re.I,
)
ACTION_RE = re.compile(
    r"\b(lawsuit|sues?|sued|court|ruling|settle|ban|license|export|tariff|probe|investigat|antitrust|order|contract|deal|"
    r"acqui|invest|buyback|repurchase|guidance|earnings|revenue|launch|ship|delay|recall|layoff|appoint|resign|files?|filed)\b",
    re.I,
)
MAX_OPINION_RELEVANCE = 1


def adjust(row):
    """row: item_id·source·title·ai_relevance·ai_novelty·ai_area. 바뀐 dict와 사유 목록을 돌려준다."""
    reasons = []
    rel, nov = row.get("ai_relevance"), row.get("ai_novelty")
    if rel is None:
        return row, reasons
    src = (row.get("source") or "").lower()
    title = row.get("title") or ""
    opinion = any(p in src for p in OPINION_PUBLISHERS) or bool(OPINION_TITLE_RE.search(title))
    price_move = bool(PRICE_MOVE_RE.search(title)) and not ACTION_RE.search(title)
    secondary = config.is_secondary_source(src)
    if opinion or price_move or secondary:
        tag = "opinion" if opinion else ("price_move" if price_move else "secondary_source")
        if rel > MAX_OPINION_RELEVANCE:
            row["ai_relevance"] = MAX_OPINION_RELEVANCE
            reasons.append(tag + "_cap")
        if nov in ("new", "update"):
            row["ai_novelty"] = "repeat"
            reasons.append(tag + "_repeat")
    row["is_event"] = 1 if (row["ai_relevance"] >= config.event_min(row.get("ai_area")) and row["ai_novelty"] in ("new", "update")) else 0
    return row, reasons


def _bigrams(text):
    s = re.sub(r"[\s\W_]+", "", (text or "").lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def dedupe_facts(conn, verbose=False):
    """같은 영역·±2일 안의 이벤트끼리 ai_fact 글자 2-gram 자카드 ≥ 임계면 뒤의 것을 'repeat'로.

    같은 배치에 들어온 형제 기사는 Gemini가 서로를 모른다(recent_facts는 저장된 것만) — 그 구멍을 여기서 막는다.
    먼저 나온 것이 대표. 멱등: 대표는 항상 가장 이른 이벤트라 재실행해도 같은 결과.
    """
    import datetime
    kinds = ",".join(f"'{k}'" for k in config.CLASSIFY_KINDS)
    rows = [dict(r) for r in conn.execute(
        f"""SELECT item_id, published_at, ai_area, ai_fact FROM items
            WHERE kind IN ({kinds}) AND analyzed_at IS NOT NULL AND is_event = 1 ORDER BY published_at""")]
    reps, changed = [], 0
    for r in rows:
        bg = _bigrams(r["ai_fact"])
        day = datetime.date.fromisoformat(r["published_at"][:10])
        dup_of, best = None, 0.0
        for p in reps:
            if p["ai_area"] != r["ai_area"] or abs((day - p["_day"]).days) > FACT_DUP_WINDOW_DAYS:
                continue
            j = len(bg & p["_bg"]) / len(bg | p["_bg"]) if (bg or p["_bg"]) else 0.0
            if j >= FACT_DUP_BIGRAM_JACCARD and j > best:
                dup_of, best = p, j
        if dup_of:
            conn.execute("UPDATE items SET ai_novelty = 'repeat', is_event = 0 WHERE item_id = ?", (r["item_id"],))
            changed += 1
            if verbose:
                print(f"  [same story {best:.2f}] {r['ai_fact'][:60]}  ⇐  {dup_of['ai_fact'][:60]}")
        else:
            reps.append(dict(r, _bg=bg, _day=day))
    conn.commit()
    return changed


def reapply(conn, verbose=False):
    kinds = ",".join(f"'{k}'" for k in config.CLASSIFY_KINDS)
    rows = [dict(r) for r in conn.execute(
        f"SELECT item_id, source, title, ai_area, ai_relevance, ai_novelty, is_event FROM items WHERE kind IN ({kinds}) AND analyzed_at IS NOT NULL")]
    changed = 0
    counts = {}
    for r in rows:
        before = (r["ai_relevance"], r["ai_novelty"], r["is_event"])
        r, reasons = adjust(r)
        if (r["ai_relevance"], r["ai_novelty"], r["is_event"]) != before:
            conn.execute("UPDATE items SET ai_relevance = ?, ai_novelty = ?, is_event = ? WHERE item_id = ?",
                         (r["ai_relevance"], r["ai_novelty"], r["is_event"], r["item_id"]))
            changed += 1
            for x in reasons:
                counts[x] = counts.get(x, 0) + 1
    conn.commit()
    same = dedupe_facts(conn, verbose=verbose)
    if changed or same:
        print(f"[labels] 보정 {changed}건 {counts} · 같은 사건 병합 {same}건")
    return changed + same


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    reapply(db.connect(), verbose="--verbose" in sys.argv)
    raise SystemExit


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    reapply(db.connect())
