"""실행 — 유니버스 → 일봉·실적일 → 조건값·결과 → 통계 → output/results.md

    python experiments/signal-study/main.py                    # 캐시 있으면 재사용
    python experiments/signal-study/main.py --refresh-prices   # 일봉 다시 받기
    python experiments/signal-study/main.py --skip-earnings    # 실적일 없이 (실적 인접 표는 전부 '아님')
"""

import argparse
import os
import sys
import time

import config
import outcomes
import prices
import render
import study
import universe


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--refresh-prices", action="store_true")
    ap.add_argument("--refresh-earnings", action="store_true")
    ap.add_argument("--skip-earnings", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    uni = universe.load(refresh=args.refresh_universe)
    symbols = sorted(set(uni["symbol"]) | set(config.SECTOR_ETF.values()) | {config.BENCHMARK, config.VIX})
    bars = prices.load_bars(symbols, refresh=args.refresh_prices)
    uni = uni[uni["symbol"].isin(bars)]
    earnings = None if args.skip_earnings else prices.load_earnings(sorted(uni["symbol"]), refresh=args.refresh_earnings)

    long = outcomes.build(uni, bars)
    print(f"[build] {len(long):,}행 (종목 {long['symbol'].nunique()} × 거래일 {long['day'].nunique()}) · {time.time() - t0:.0f}s")

    res = study.run(long, earnings)
    md = os.path.join(config.OUTPUT_DIR, "results.md")
    csv = os.path.join(config.OUTPUT_DIR, "events.csv")
    render.render(res, md, csv)
    ev = res["events"]
    print(f"[study] 신호 {len(ev):,}건 (탐색 {int((ev.period == 'train').sum()):,} · 검증 {int((ev.period == 'test').sum()):,}) "
          f"· {time.time() - t0:.0f}s\n→ {md}\n→ {csv}")


if __name__ == "__main__":
    main()
