"""이벤트 스터디 — 일봉 OHLCV만으로 (기획서 8절 · 2026-09-18 개정: 분봉은 쓰지 않는다).

구간(horizon)은 (기준일 b, 측정일 d) 한 쌍으로 정의되고, 이벤트와 플라시보(비이벤트 날) 양쪽이 같은 함수를 쓴다.

  baseline    = close(b)                       게시 직전 마지막 종가
  gap         = open(d)  / baseline − 1        장외 게시물의 즉각 반응 (다음 개장 갭)
  intraday    = close(d) / open(d)  − 1        정규장 게시물의 즉각 반응 (시가 → 종가)
  close       = close(d)   / baseline − 1
  next_close  = close(d+1) / baseline − 1
  d3 / d5     = close(d+3) / baseline − 1 · close(d+5) / baseline − 1     (거래일 기준)
  rel_range   = ((high−low)/close)(d) ÷ 직전 REL_LOOKBACK_DAYS 거래일 중앙값      배수, 방향 무관
  rel_volume  = volume(d) ÷ 직전 REL_LOOKBACK_DAYS 거래일 평균                    배수, 방향 무관

abn_* = 수익률 구간 − SPY의 같은 구간 (SPY 행은 NULL). rel_* 는 SPY를 빼지 않는다.
"""

import statistics
import sys

import config
import db

RET_HORIZONS = ["gap", "intraday", "close", "next_close", "d3", "d5"]
REL_HORIZONS = ["rel_range", "rel_volume"]
_CAR = {f"d{n}": n for n in config.CAR_DAYS}


class Bars:
    """심볼별 일봉 배열. 거래일 인덱스로 구간 값을 계산한다."""

    def __init__(self, conn):
        self.days, self.idx = {}, {}
        self.o, self.h, self.l, self.c, self.v = {}, {}, {}, {}, {}
        for r in conn.execute("SELECT symbol, day, open, high, low, close, volume FROM daily_bars "
                              "WHERE close IS NOT NULL ORDER BY symbol, day"):
            s = r["symbol"]
            self.days.setdefault(s, []).append(r["day"])
            self.o.setdefault(s, []).append(r["open"])
            self.h.setdefault(s, []).append(r["high"])
            self.l.setdefault(s, []).append(r["low"])
            self.c.setdefault(s, []).append(r["close"])
            self.v.setdefault(s, []).append(r["volume"])
        for s, ds in self.days.items():
            self.idx[s] = {d: i for i, d in enumerate(ds)}

    def has(self, sym, day):
        return day in self.idx.get(sym, {})

    def measures(self, sym, b, d):
        """(기준일, 측정일) → {horizon: 값}. 없는 값은 None. 심볼에 두 날이 없으면 None."""
        ix = self.idx.get(sym)
        if not ix or b not in ix or d not in ix:
            return None
        ib, id_ = ix[b], ix[d]
        c, o, h, l, v = self.c[sym], self.o[sym], self.h[sym], self.l[sym], self.v[sym]
        base = c[ib]
        if not base:
            return None
        m = {"baseline": base}
        m["gap"] = (o[id_] / base - 1) if o[id_] else None
        m["intraday"] = (c[id_] / o[id_] - 1) if o[id_] else None
        m["close"] = c[id_] / base - 1
        m["next_close"] = (c[id_ + 1] / base - 1) if id_ + 1 < len(c) else None
        for key, n in _CAR.items():
            m[key] = (c[id_ + n] / base - 1) if id_ + n < len(c) else None

        lo = max(0, ib - config.REL_LOOKBACK_DAYS + 1)
        rng_hist = [(h[i] - l[i]) / c[i] for i in range(lo, ib + 1)
                    if h[i] is not None and l[i] is not None and c[i]]
        vol_hist = [v[i] for i in range(lo, ib + 1) if v[i]]
        rr = ((h[id_] - l[id_]) / c[id_]) if (h[id_] is not None and l[id_] is not None and c[id_]) else None
        m["rel_range"] = None
        if rr is not None and len(rng_hist) >= config.REL_MIN_LOOKBACK:
            med = statistics.median(rng_hist)
            m["rel_range"] = rr / med if med > 0 else None
        m["rel_volume"] = None
        if v[id_] and len(vol_hist) >= config.REL_MIN_LOOKBACK:
            avg = statistics.fmean(vol_hist)
            m["rel_volume"] = v[id_] / avg if avg > 0 else None
        return m


def _abnormal(m, bench):
    """수익률 구간에서 SPY 같은 구간을 뺀다. bench가 None이면 전부 None."""
    out = {}
    for hz in RET_HORIZONS:
        a, s = m.get(hz), bench.get(hz) if bench else None
        out[hz] = None if (a is None or s is None) else a - s
    return out


def build(conn):
    bars = Bars(conn)
    events = conn.execute(
        "SELECT event_id, baseline_day, effective_day FROM trump_events "
        "WHERE baseline_day IS NOT NULL AND effective_day IS NOT NULL").fetchall()

    rows = []
    for ev in events:
        b, d = ev["baseline_day"], ev["effective_day"]
        bench = bars.measures(config.BENCHMARK, b, d)
        for sym in config.ALL_SYMBOLS:
            m = bars.measures(sym, b, d)
            if m is None:
                continue
            is_bench = sym == config.BENCHMARK
            abn = {hz: None for hz in RET_HORIZONS} if is_bench else _abnormal(m, bench)
            rows.append((
                ev["event_id"], sym, m["baseline"],
                *[m[hz] for hz in RET_HORIZONS],
                *[abn[hz] for hz in RET_HORIZONS],
                m["rel_range"], m["rel_volume"],
            ))

    conn.execute("DELETE FROM event_reactions")
    conn.executemany(
        """INSERT INTO event_reactions(event_id, symbol, baseline_price,
               ret_gap, ret_intraday, ret_close, ret_next_close, ret_d3, ret_d5,
               abn_gap, abn_intraday, abn_close, abn_next_close, abn_d3, abn_d5,
               rel_range, rel_volume)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    pending = sum(1 for r in rows if r[5] is None)      # ret_close
    print(f"[study] 이벤트 {len(events):,}개 × 자산 → 반응 {len(rows):,}행 (종가 대기 {pending})")
    return len(rows)


def placebo_pools(conn, exclude_days):
    """심볼 → 구간 → 비이벤트 거래일의 값 목록. 이벤트와 같은 계산(SPY 차감 포함).

    (직전 거래일, 당일) 쌍마다 measures를 구한다. exclude_days(이벤트 측정일·거시 발표일)는 빼서
    '보통 날' 분포를 만든다. 집계의 플라시보 검정이 여기서 N개씩 뽑아 평균 분포를 만든다.
    """
    bars = Bars(conn)
    pools = {}
    for sym in config.ALL_SYMBOLS:
        days = bars.days.get(sym, [])
        pool = {hz: [] for hz in RET_HORIZONS + REL_HORIZONS}
        is_bench = sym == config.BENCHMARK
        for i in range(1, len(days)):
            b, d = days[i - 1], days[i]
            if d in exclude_days:
                continue
            m = bars.measures(sym, b, d)
            if m is None:
                continue
            if is_bench:
                vals = {hz: m[hz] for hz in RET_HORIZONS}
            else:
                if not (bars.has(config.BENCHMARK, b) and bars.has(config.BENCHMARK, d)):
                    continue
                vals = _abnormal(m, bars.measures(config.BENCHMARK, b, d))
            for hz in RET_HORIZONS:
                if vals[hz] is not None:
                    pool[hz].append(vals[hz])
            for hz in REL_HORIZONS:
                if m[hz] is not None:
                    pool[hz].append(m[hz])
        pools[sym] = pool
    return pools


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(db.connect())
