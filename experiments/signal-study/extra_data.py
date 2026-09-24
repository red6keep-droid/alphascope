"""추가 데이터 — 편입일 · 지수 제외 종목 · 실적 서프라이즈. backtest/data 에 저장.

    .venv/bin/python experiments/signal-study/extra_data.py            # 셋 다
    .venv/bin/python experiments/signal-study/extra_data.py --skip-earnings

1. universe.csv 에 added(편입일) 열 추가 — Wikipedia 본표 "Date added"
2. removed.csv · removed.pkl — 2016년 이후 지수에서 빠진 종목의 제외일과 (받을 수 있는 경우) 일봉. 출처 HIST_URL.
   인수·합병으로 사라진 종목은 yfinance 에 없다. 티커가 다른 회사에 재사용된 경우가 있어
   제외일 뒤로도 1년 넘게 거래가 이어지면 reused_suspect 로 표시한다.
3. earnings.csv 에 eps_est · eps_actual · surprise_pct 열 추가
"""

import argparse
import io
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

import config
import universe

HIST_URL = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"   # 변경 이력은 2025년 이후 별도 페이지
REMOVED_CSV = os.path.join(config.DATA_DIR, "removed.csv")
REMOVED_PKL = os.path.join(config.DATA_DIR, "removed.pkl")
EARN_CSV = os.path.join(config.DATA_DIR, "earnings.csv")


def wiki_tables(url=universe.WIKI_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    return pd.read_html(io.StringIO(html))


def _flat(cols):
    return [" ".join(str(c) for c in col if not str(c).startswith("Unnamed")).strip() if isinstance(col, tuple) else str(col)
            for col in cols]


def add_inclusion_dates(tables):
    main = next(t for t in tables if "Symbol" in [str(c) for c in t.columns] and "Date added" in [str(c) for c in t.columns])
    main = main[["Symbol", "Date added"]].copy()
    main["symbol"] = main["Symbol"].astype(str).str.replace(".", "-", regex=False)
    main["added"] = pd.to_datetime(main["Date added"], errors="coerce")
    uni = universe.load()
    uni = uni.drop(columns=[c for c in ("added",) if c in uni]).merge(main[["symbol", "added"]], on="symbol", how="left")
    uni.to_csv(universe.CACHE, index=False)
    since = (uni["added"] >= config.STUDY_START).sum()
    print(f"[universe] 편입일 {uni['added'].notna().sum()}/{len(uni)} · {config.STUDY_START} 이후 편입 {since}종목 · 결측 {uni['added'].isna().sum()}")
    return uni


def removed_constituents(tables, current):
    chg = next(t for t in tables if any("Removed" in str(c) for c in t.columns))
    chg.columns = _flat(chg.columns)
    date_col = next(c for c in chg.columns if "Date" in c)
    tick_col = next(c for c in chg.columns if c.startswith("Removed") and "Ticker" in c)
    name_col = next(c for c in chg.columns if c.startswith("Removed") and "Security" in c)
    reason_col = next((c for c in chg.columns if c.startswith("Reason")), None)
    df = pd.DataFrame({
        "symbol": chg[tick_col].astype(str).str.replace(".", "-", regex=False),
        "name": chg[name_col],
        "removed": pd.to_datetime(chg[date_col], errors="coerce"),
        "reason": chg[reason_col] if reason_col else "",
    }).dropna(subset=["removed"])
    df = df[df["symbol"].str.match(r"^[A-Z][A-Z0-9-]{0,6}$") & (df["removed"] >= config.STUDY_START) & ~df["symbol"].isin(current)]
    df = df.sort_values("removed").drop_duplicates("symbol", keep="last").reset_index(drop=True)
    print(f"[removed] {config.STUDY_START} 이후 제외 {len(df)}종목 (현재 구성 제외)")
    return df


def download_removed(df):
    syms = [str(x) for x in df["symbol"]]
    bars = {}
    for i in range(0, len(syms), 100):
        chunk = syms[i:i + 100]
        raw = yf.download(chunk, start=config.PRICE_START, interval="1d", auto_adjust=True,
                          group_by="ticker", progress=False, threads=True)
        for s in chunk:
            try:
                sub = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
            if len(sub) < 60:
                continue
            sub.index = pd.to_datetime(sub.index).tz_localize(None)
            bars[s] = sub
    df = df.copy()
    df["bars"] = df["symbol"].map(lambda s: len(bars[s]) if s in bars else 0)
    df["first_bar"] = df["symbol"].map(lambda s: bars[s].index.min().date() if s in bars else pd.NaT)
    df["last_bar"] = df["symbol"].map(lambda s: bars[s].index.max().date() if s in bars else pd.NaT)
    last = pd.to_datetime(df["last_bar"])
    df["reused_suspect"] = (last - df["removed"]).dt.days > 365
    df.to_csv(REMOVED_CSV, index=False)
    pd.to_pickle(bars, REMOVED_PKL)
    got = (df["bars"] > 0).sum()
    print(f"[removed] 일봉 확보 {got}/{len(df)} · 제외 후 1년 넘게 거래 지속(재사용 의심 또는 중형주 이동) {df['reused_suspect'].sum()} → {REMOVED_CSV}")
    return df


def _earn_one(sym):
    try:
        ed = yf.Ticker(sym).get_earnings_dates(limit=100)
    except Exception as e:  # noqa: BLE001
        return sym, None, str(e)
    if ed is None or ed.empty:
        return sym, [], None
    rows = []
    for idx, r in ed.iterrows():
        rows.append((sym, pd.Timestamp(idx).tz_localize(None).normalize(),
                     r.get("EPS Estimate"), r.get("Reported EPS"), r.get("Surprise(%)")))
    return sym, rows, None


def earnings_with_surprise(symbols):
    rows, failed = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, got, err in ex.map(_earn_one, symbols):
            if err:
                failed.append(sym)
                continue
            rows += got
    df = pd.DataFrame(rows, columns=["symbol", "day", "eps_est", "eps_actual", "surprise_pct"])
    df = df.drop_duplicates(["symbol", "day"]).sort_values(["symbol", "day"])
    df.to_csv(EARN_CSV, index=False)
    have = df["surprise_pct"].notna()
    print(f"[earnings] {df['symbol'].nunique()}종목 {len(df):,}건 · 서프라이즈 있음 {have.sum():,} ({have.mean():.0%}) · 실패 {len(failed)} → {EARN_CSV}")
    if failed:
        print("  실패:", " ".join(failed[:20]), "..." if len(failed) > 20 else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-earnings", action="store_true")
    args = ap.parse_args()
    tables = wiki_tables()
    uni = add_inclusion_dates(tables)
    rem = removed_constituents(wiki_tables(HIST_URL), set(uni["symbol"]))
    download_removed(rem)
    if not args.skip_earnings:
        earnings_with_surprise(sorted(uni["symbol"]))


if __name__ == "__main__":
    main()
