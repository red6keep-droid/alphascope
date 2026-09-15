"""이벤트 스터디 — MVP는 일 단위 (기획서 8절).

baseline = 기준 거래일 종가 (게시 직전 마지막 종가)
ret_close      = close(D)   / baseline − 1
ret_next_close = close(D+1) / baseline − 1
abn_*          = ret_* − SPY의 같은 구간 수익률   (SPY 행은 NULL)

분 단위 컬럼(ret_5m …)은 분봉 경로가 생기면 채운다. 여기서는 건드리지 않는다.
"""

import sys

import config
import db


def _closes(conn):
    closes = {}
    for r in conn.execute("SELECT symbol, day, close FROM daily_bars ORDER BY symbol, day"):
        closes.setdefault(r["symbol"], {})[r["day"]] = r["close"]
    return closes


def _next_day(days, day):
    for d in days:
        if d > day:
            return d
    return None


def _ret(closes_sym, base_day, day):
    if not day or base_day not in closes_sym or day not in closes_sym:
        return None
    base = closes_sym[base_day]
    return closes_sym[day] / base - 1 if base else None


def build(conn):
    closes = _closes(conn)
    bench = closes.get(config.BENCHMARK, {})
    days = sorted(bench)
    events = conn.execute(
        "SELECT event_id, baseline_day, effective_day FROM trump_events "
        "WHERE baseline_day IS NOT NULL AND effective_day IS NOT NULL").fetchall()

    rows = []
    for ev in events:
        b, d = ev["baseline_day"], ev["effective_day"]
        d1 = _next_day(days, d)
        spy_close = _ret(bench, b, d)
        spy_next = _ret(bench, b, d1)
        for sym in config.ALL_SYMBOLS:
            cs = closes.get(sym)
            if not cs or b not in cs:
                continue
            rc = _ret(cs, b, d)
            rn = _ret(cs, b, d1)
            is_bench = sym == config.BENCHMARK
            rows.append((
                ev["event_id"], sym, cs[b], rc, rn,
                None if (is_bench or rc is None or spy_close is None) else rc - spy_close,
                None if (is_bench or rn is None or spy_next is None) else rn - spy_next,
            ))

    conn.execute("DELETE FROM event_reactions")
    conn.executemany(
        """INSERT INTO event_reactions(event_id, symbol, baseline_price, ret_close, ret_next_close,
                                       abn_close, abn_next_close)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    pending = sum(1 for r in rows if r[3] is None)
    print(f"[study] 이벤트 {len(events):,}개 × 자산 → 반응 {len(rows):,}행 (종가 대기 {pending})")
    return len(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(db.connect())
