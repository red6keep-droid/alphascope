"""일봉 · 실적일 수집 (yfinance). data/ 에 pickle · csv 로 캐시.

auto_adjust=True — 분할·배당 반영 가격. 수익률은 이 값으로 계산해야 분할일에 가짜 급등이 생기지 않는다.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

import config

BARS_CACHE = os.path.join(config.DATA_DIR, "bars.pkl")
EARN_CACHE = os.path.join(config.DATA_DIR, "earnings.csv")


def _download(symbols):
    df = yf.download(symbols, start=config.PRICE_START, interval="1d", auto_adjust=True,
                     group_by="ticker", progress=False, threads=True)
    out = {}
    for sym in symbols:
        try:
            sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            continue
        sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        if len(sub) < 250:
            print(f"[prices] {sym}: 일봉 {len(sub)}개 — 제외")
            continue
        sub.index = pd.to_datetime(sub.index).tz_localize(None)
        out[sym] = sub
    return out


def load_bars(symbols, refresh=False):
    """{symbol: DataFrame[Open High Low Close Volume]} — 종목 + 섹터 ETF + SPY + VIX."""
    if not refresh and os.path.exists(BARS_CACHE):
        bars = pd.read_pickle(BARS_CACHE)
        missing = [s for s in symbols if s not in bars]
        if not missing:
            return bars
        print(f"[prices] 캐시에 없는 {len(missing)}개 추가 수집")
        bars.update(_download(missing))
    else:
        bars = {}
        for i in range(0, len(symbols), 100):
            chunk = symbols[i:i + 100]
            bars.update(_download(chunk))
            print(f"[prices] {min(i + 100, len(symbols))}/{len(symbols)} 수집")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    pd.to_pickle(bars, BARS_CACHE)
    last = bars[config.BENCHMARK].index.max().date()
    print(f"[prices] {len(bars)}개 심볼 · {config.BENCHMARK} 마지막 거래일 {last} → {BARS_CACHE}")
    return bars


def _earnings_one(sym):
    try:
        ed = yf.Ticker(sym).get_earnings_dates(limit=100)
    except Exception as e:  # noqa: BLE001
        return sym, None, str(e)
    if ed is None or ed.empty:
        return sym, [], None
    days = sorted({pd.Timestamp(d).tz_localize(None).normalize() for d in ed.index})
    return sym, days, None


def load_earnings(symbols, refresh=False):
    """DataFrame[symbol, day] — 실적 발표일. 실패한 종목은 빠진다(그 종목의 신호는 '실적 인접' 판정을 못 받는다)."""
    if not refresh and os.path.exists(EARN_CACHE):
        df = pd.read_csv(EARN_CACHE, parse_dates=["day"])
        return df
    rows, failed = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, days, err in ex.map(_earnings_one, symbols):
            if err:
                failed.append(sym)
                continue
            rows += [(sym, d) for d in days]
    df = pd.DataFrame(rows, columns=["symbol", "day"])
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df.to_csv(EARN_CACHE, index=False)
    print(f"[earnings] {df['symbol'].nunique()}종목 {len(df):,}건 · 실패 {len(failed)} → {EARN_CACHE}")
    return df
