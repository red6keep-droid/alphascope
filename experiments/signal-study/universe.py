"""유니버스 — 현재 S&P 500 구성 종목 + GICS 섹터 (Wikipedia). data/universe.csv 에 캐시.

지금 목록으로 과거를 보므로 생존 편향이 있다: 그 사이 지수에서 빠진(상장폐지·인수) 종목이 없다.
승률이 실제보다 좋게 나오는 방향의 편향이고, 결과 문서에 이를 명시한다.
"""

import io
import os
import urllib.request

import pandas as pd

import config

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
CACHE = os.path.join(config.DATA_DIR, "universe.csv")


def fetch():
    req = urllib.request.Request(WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    for t in pd.read_html(io.StringIO(html)):
        cols = [str(c) for c in t.columns]
        if "Symbol" in cols and "GICS Sector" in cols:
            df = t[["Symbol", "Security", "GICS Sector"]].copy()
            df.columns = ["symbol", "name", "sector"]
            # BRK.B · BF.B → yfinance 표기
            df["symbol"] = df["symbol"].astype(str).str.replace(".", "-", regex=False)
            df["etf"] = df["sector"].map(config.SECTOR_ETF)
            return df
    raise RuntimeError("Wikipedia S&P 500 표를 찾지 못했다")


def load(refresh=False):
    if not refresh and os.path.exists(CACHE):
        return pd.read_csv(CACHE)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df = fetch()
    df.to_csv(CACHE, index=False)
    print(f"[universe] {len(df)}종목 · 섹터 {df['sector'].nunique()}개 → {CACHE}")
    missing = df[df["etf"].isna()]
    if len(missing):
        print(f"[universe] ETF 매핑 없는 섹터: {sorted(missing['sector'].unique())}")
    return df
