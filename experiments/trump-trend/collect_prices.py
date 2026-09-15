"""관찰 종목 일봉 수집 → daily_bars (기획서 9절, MVP는 일봉).

yfinance 무료·키 없음. 첫 실행은 2년치를 받고, 이후엔 최근 한 달만 받아 덧쓴다.
분봉은 경로가 정해지면 별도 모듈로 붙인다 — 이 파일은 일봉만 다룬다.
"""

import sys

import pandas as pd
import yfinance as yf

import config
import db


def _has_history(conn, symbol):
    row = conn.execute("SELECT COUNT(*) FROM daily_bars WHERE symbol = ?", (symbol,)).fetchone()
    return row[0] > 200


def fetch_daily(symbols, period):
    df = yf.download(symbols, period=period, interval="1d", auto_adjust=False,
                     group_by="ticker", progress=False, threads=True)
    rows = []
    for sym in symbols:
        try:
            sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            print(f"[prices] {sym}: 데이터 없음")
            continue
        sub = sub.dropna(subset=["Close"])
        for idx, r in sub.iterrows():
            rows.append((
                sym, idx.strftime("%Y-%m-%d"),
                float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                float(r["Volume"]) if pd.notna(r["Volume"]) else None,
            ))
    return rows


def collect(conn, symbols=None, force_backfill=False):
    symbols = symbols or config.ALL_SYMBOLS
    backfill = [s for s in symbols if force_backfill or not _has_history(conn, s)]
    update = [s for s in symbols if s not in backfill]

    total = 0
    for group, period in ((backfill, config.PRICE_BACKFILL_PERIOD), (update, config.PRICE_UPDATE_PERIOD)):
        if not group:
            continue
        print(f"[prices] {len(group)}개 심볼 · period={period}: {', '.join(group)}")
        rows = fetch_daily(group, period)
        conn.executemany(
            """INSERT INTO daily_bars(symbol, day, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol, day) DO UPDATE SET
                 open=excluded.open, high=excluded.high, low=excluded.low,
                 close=excluded.close, volume=excluded.volume""",
            rows,
        )
        total += len(rows)
    conn.commit()
    last = conn.execute("SELECT MAX(day) FROM daily_bars WHERE symbol = ?", (config.BENCHMARK,)).fetchone()[0]
    print(f"[prices] {total:,}행 갱신 · {config.BENCHMARK} 마지막 거래일 {last}")
    return total


def trading_days(conn):
    """SPY 일봉이 있는 날 = 거래일. 휴장 판정에 쓴다."""
    return [r[0] for r in conn.execute(
        "SELECT day FROM daily_bars WHERE symbol = ? ORDER BY day", (config.BENCHMARK,))]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    collect(db.connect(), force_backfill="--backfill" in sys.argv)
