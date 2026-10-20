"""로컬 30년 종목 데이터 저장소 — 일봉 받기 (doc/볼린저-이슈별-검증-계획.md 6절 · doc/데이터-기록-계획.md 2부).

    python experiments/issue_store/fetch_bars.py            # 기본 심볼 전부, 있으면 마지막 날짜 뒤만 이어 받기
    python experiments/issue_store/fetch_bars.py NVDA AMD   # 지정 심볼만

저장: data/store/bars/{심볼}.parquet (깃 밖). 칸: open high low close volume (수정주가 auto_adjust) + adj 없음.
manifest: data/store/manifest.json — 심볼별 첫날 · 마지막 날 · 행 수 · 받은 날.
"""

import datetime
import json
import os
import sys
import time

import pandas as pd
import yfinance as yf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
BARS = os.path.join(STORE, "bars")
MANIFEST = os.path.join(STORE, "manifest.json")

# 반응을 시장 · 섹터 · 종목 몫으로 나누는 데 필요한 것 (이슈 저장소 6절)
DEFAULT = [
    "NVDA",
    # 종목 확대 15 (2026-10-17 확정, 볼린저 계획 4-1) — 설계 · 장비 · 메모리/제조/아날로그 · 플랫폼 · 거품 뒤 횡보
    "AMD", "QCOM", "AVGO", "AMAT", "LRCX", "KLAC", "MU", "INTC", "TXN",
    "MSFT", "AAPL", "AMZN", "GOOGL", "CSCO",
    "^GSPC", "SPY", "QQQ", "^IXIC",                 # 시장 (^GSPC 1927~, SPY 1993~)
    "SMH", "SOXX", "^SOX",                          # 반도체 섹터 (^SOX 1994~)
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",   # 섹터 ETF (1998~, XLRE 2015 · XLC 2018)
    "^VIX", "^TNX", "^IRX", "JPY=X", "DX-Y.NYB", "CL=F", "GC=F",   # 변동성 · 10년 · 3개월 금리 · 엔화 · 달러 · 원유 · 금
]


def safe(sym):
    return sym.replace("^", "_").replace("=", "_").replace("/", "_")


def load_manifest():
    try:
        return json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:
        return {}


def fetch(sym, manifest):
    path = os.path.join(BARS, safe(sym) + ".parquet")
    old = pd.read_parquet(path) if os.path.exists(path) else None
    start = None
    if old is not None and len(old):
        start = (old.index.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = (yf.download(sym, start=start, interval="1d", auto_adjust=True, progress=False) if start
          else yf.download(sym, period="max", interval="1d", auto_adjust=True, progress=False))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[[c for c in ("open", "high", "low", "close", "volume") if c in df.rename(columns=str.lower).columns]]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "day"
    if old is not None:
        df = pd.concat([old, df[~df.index.isin(old.index)]]).sort_index()
    df = df.dropna(subset=["close"])
    df.to_parquet(path)
    manifest[sym] = {"file": os.path.relpath(path, STORE), "first": str(df.index.min().date()), "last": str(df.index.max().date()),
                     "rows": int(len(df)), "fetched": datetime.date.today().isoformat(), "source": "yfinance auto_adjust"}
    return manifest[sym]


def main(symbols):
    os.makedirs(BARS, exist_ok=True)
    manifest = load_manifest()
    for sym in symbols:
        try:
            m = fetch(sym, manifest)
            print(f"{sym:>10}  {m['first']} ~ {m['last']}  {m['rows']:>6}행")
        except Exception as e:  # noqa: BLE001
            print(f"{sym:>10}  실패: {str(e)[:120]}")
        time.sleep(0.5)   # yfinance 차단 피하기
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
