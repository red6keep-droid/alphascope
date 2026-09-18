"""GitHub Actions용 상태 내보내기·불러오기.

런너는 매번 빈 환경이다. 다시 만들 수 없는 것은 Gemini 분류 결과뿐이므로
(게시물은 archive에서, 가격·캘린더는 API에서, 이벤트·반응은 재계산) 그것만 JSONL로 남긴다.

    classifications.jsonl   한 줄 = 분류된 게시물 하나 (id + ai_* + analyzed_at + ai_model)
    daily_bars.csv          일봉 OHLCV 전체 (symbol, day, open, high, low, close, volume)

불러오기는 collect_posts 뒤에 돈다 — 행이 있어야 UPDATE 할 수 있다.
archive에서 사라진 게시물(삭제)의 분류는 DB에 못 붙지만, 내보낼 때 다시 이어 붙여 잃지 않는다.

일봉은 다시 받을 수 있지만 보존한다 (2026-09-18): yfinance가 깨지는 날에도 전날까지의 일봉으로
반응 통계와 플라시보 풀이 나오게 하고, 매 실행 2년치 대신 최근 한 달만 받게 하기 위해서다.
불러오기는 collect_prices 앞에 돈다 — 행이 200개를 넘으면 수집기가 백필 대신 1개월 갱신을 택한다.
"""

import csv
import json
import os

AI_FIELDS = [
    "ai_topic", "ai_subtopic", "ai_target_country", "ai_target_sector",
    "ai_mentioned_companies", "ai_direction", "ai_intensity", "ai_market_relevance",
    "analyzed_at", "ai_model",
]

_carry = []   # import 때 DB에 없던 행 — export 때 그대로 다시 쓴다


def import_state(conn, path):
    global _carry
    _carry = []
    if not path or not os.path.exists(path):
        print(f"[state] 불러올 파일 없음: {path} (첫 실행이면 정상)")
        return 0
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    existing = {r["id"] for r in conn.execute("SELECT id FROM trump_posts")}
    applied = []
    for r in rows:
        if r.get("id") in existing:
            applied.append(r)
        else:
            _carry.append(r)
    conn.executemany(
        """UPDATE trump_posts SET
             ai_topic=:ai_topic, ai_subtopic=:ai_subtopic,
             ai_target_country=:ai_target_country, ai_target_sector=:ai_target_sector,
             ai_mentioned_companies=:ai_mentioned_companies, ai_direction=:ai_direction,
             ai_intensity=:ai_intensity, ai_market_relevance=:ai_market_relevance,
             analyzed_at=:analyzed_at, ai_model=:ai_model
           WHERE id=:id AND analyzed_at IS NULL""",
        applied,
    )
    conn.commit()
    print(f"[state] 분류 결과 {len(rows):,}행 중 {len(applied):,}행 적용 · DB에 없는 게시물 {len(_carry):,}행은 보존")
    return len(applied)


def export_state(conn, path):
    rows = [dict(r) for r in conn.execute(
        f"SELECT id, {', '.join(AI_FIELDS)} FROM trump_posts WHERE analyzed_at IS NOT NULL ORDER BY id")]
    ids = {r["id"] for r in rows}
    rows += [r for r in _carry if r.get("id") not in ids]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[state] 분류 결과 {len(rows):,}행 → {path}")
    return len(rows)


# ── 일봉 ──────────────────────────────────────────────────────────────────

BAR_FIELDS = ["symbol", "day", "open", "high", "low", "close", "volume"]


def import_bars(conn, path):
    if not path or not os.path.exists(path):
        print(f"[state] 불러올 일봉 없음: {path} (첫 실행이면 정상 — 2년치를 새로 받는다)")
        return 0
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not r.get("close"):
                continue
            rows.append((
                r["symbol"], r["day"],
                *[float(r[k]) if r.get(k) not in (None, "") else None for k in ("open", "high", "low", "close", "volume")],
            ))
    # 새로 받은 값이 우선이어야 하므로 이미 있는 (symbol, day)는 건드리지 않는다.
    conn.executemany(
        "INSERT OR IGNORE INTO daily_bars(symbol, day, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    last = conn.execute("SELECT MAX(day) FROM daily_bars").fetchone()[0]
    print(f"[state] 일봉 {len(rows):,}행 불러옴 · 마지막 거래일 {last}")
    return len(rows)


def export_bars(conn, path):
    rows = conn.execute(
        f"SELECT {', '.join(BAR_FIELDS)} FROM daily_bars WHERE close IS NOT NULL ORDER BY symbol, day").fetchall()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(BAR_FIELDS)
        for r in rows:
            # yfinance float32 잔재(216.5399932861328)를 소수 4자리로 — 파일이 절반으로 줄고 수익률에는 영향 없다
            w.writerow([r["symbol"], r["day"],
                        *[("" if r[k] is None else f"{r[k]:.4f}") for k in ("open", "high", "low", "close")],
                        int(r["volume"]) if r["volume"] is not None else ""])
    print(f"[state] 일봉 {len(rows):,}행 → {path}")
    return len(rows)
