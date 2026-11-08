"""로컬 30년 종목 데이터 저장소 — 일봉 받기 (doc/검증/볼린저-이슈별-검증-계획.md 6절 · doc/기획/데이터-기록-계획.md 2부).

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
    # 한국 시장 · 업종 (2026-11-06 사용자, 데이터-기록-계획 A3-3-2 의 8) — 코스피 · 코스닥 · 한국 ETF(미국 상장, 2000~) · KODEX 업종 ETF(반도체 · 은행 · 자동차 · 에너지화학, 2006~)
    "^KS11", "^KQ11", "EWY", "091160.KS", "091170.KS", "091180.KS", "117460.KS",
]

# 신호 지표판 — 사건보다 먼저 움직이는 앞 고리 (기획 증시-전망-기획 8-19, 2026-11-08 사용자 "지표가 먼저 말할 때").
# 위 DEFAULT 에 이미 있는 유가 · 금 · 달러 · 엔 · 10년 · 3개월 · VIX · 섹터 ETF · 한국은 그대로 쓰고, 빠진 것만 더한다. FRED(신용 웃돈 · 2년 · 기대 물가)는 fetch_fred_daily.py
SIGNAL = [
    "KRW=X", "CNY=X", "EURUSD=X",                    # 원화 · 위안 · 유로 — 위험 회피 · 무역
    "HG=F", "NG=F", "SI=F", "ZW=F",                  # 구리(경기) · 천연가스(유럽 · 전쟁) · 은 · 밀(우크라이나 · 식량)
    "^OVX", "^GVZ", "^MOVE",                         # 유가 · 금 · 채권 변동성 — 가격보다 먼저 불안이 오른다
    "^FVX", "TLT", "HYG", "LQD",                     # 5년 금리 · 장기 국채 · 하이일드 · 투자등급 회사채 ETF
    "ITA", "JETS", "BDRY", "URA",                    # 방산 · 항공 · 해운 운임 · 우라늄
    "EEM", "FXI", "EWJ", "BTC-USD",                  # 신흥국 · 중국 · 일본 · 비트코인(위험 선호)
]
DEFAULT = DEFAULT + SIGNAL


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
