"""yfinance 수집 — 일봉(2년) · 시가총액 · 실적 발표일. AI 없음, 무료 (doc/종목-레이더-기획.md 10-8 1단계).

결과는 data/snapshot.json 하나에 둔다. 분석 · 렌더는 이 파일만 읽는다(같은 날 여러 번 그려도 다시 받지 않게).
"""

import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

import universe as U

SECTOR_ETFS = ("XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLI", "XLB", "XLU", "XLRE", "XLC")   # NVDA 리포트 config.SECTOR_ETFS 와 같은 11개
HIST_MAX_AGE_DAYS = 7

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "data", "history.json")
SNAP = os.path.join(BASE, "data", "snapshot.json")
NY = ZoneInfo("America/New_York")


def _bars(symbols):
    df = yf.download(symbols, period="2y", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
    out = {}
    for s in symbols:
        try:
            sub = df[s].dropna(subset=["Close"])
        except KeyError:
            print(f"[collect] {s}: 일봉 없음")
            continue
        out[s] = [{"day": i.strftime("%Y-%m-%d"), "open": float(r["Open"]) if r["Open"] == r["Open"] else None, "high": float(r["High"]), "low": float(r["Low"]), "close": float(r["Close"]),
                   "adj": float(r["Adj Close"]), "volume": float(r["Volume"] or 0)} for i, r in sub.iterrows()]
    return out


def _cap(s):
    try:
        return s, float(yf.Ticker(s).fast_info.market_cap or 0) or None
    except Exception as e:   # noqa: BLE001
        print(f"[collect] {s} 시총 실패: {e}")
        return s, None


def _earnings(s):
    """실적 발표 시각(뉴욕) 목록. 정오 전 = 장 시작 전(그날 반응), 그 뒤 = 장 마감 뒤(다음 거래일 반응)."""
    try:
        ed = yf.Ticker(s).get_earnings_dates(limit=16)
    except Exception as e:   # noqa: BLE001
        print(f"[collect] {s} 실적일 실패: {e}")
        return s, []
    if ed is None or ed.empty:
        return s, []
    out = []
    for ts in ed.index:
        t = pd.Timestamp(ts)
        t = t.tz_convert(NY) if t.tzinfo else t.tz_localize(NY)
        out.append({"day": t.strftime("%Y-%m-%d"), "when": "bmo" if t.hour < 12 else "amc"})
    return s, sorted({x["day"]: x for x in out}.values(), key=lambda x: x["day"])


def run():
    syms = [c[0] for c in U.CANDIDATES]
    extra = sorted({U.BENCH, "^VIX", "SMH", *SECTOR_ETFS})
    bars = _bars(syms + extra)
    with ThreadPoolExecutor(8) as ex:
        caps = dict(ex.map(_cap, syms))
        earn = dict(ex.map(_earnings, syms))
    snap = {"fetched_at": datetime.datetime.now(NY).isoformat(timespec="minutes"), "bars": bars, "caps": caps, "earnings": earn, "history": history()}
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    with open(SNAP, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    print(f"[collect] 일봉 {len(bars)} · 시총 {sum(1 for v in caps.values() if v)} · 실적일 {sum(1 for v in earn.values() if v)} → {SNAP}")
    return snap


def history():
    """고점 하락 후 회복 통계 — 1999년부터(검증 데이터 기준과 같게) 종가 사이클. 일주일에 한 번만 다시 받는다.
    계산은 NVDA 리포트 history_stats 와 같은 함수(drawdown_cycles · dd_summary)."""
    try:
        with open(HIST, encoding="utf-8") as f:
            h = json.load(f)
        if (datetime.date.today() - datetime.date.fromisoformat(h["built"])).days < HIST_MAX_AGE_DAYS:
            return h
    except (OSError, ValueError, KeyError):
        pass
    import sys
    sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
    import history_stats as HS
    syms = [c[0] for c in U.CANDIDATES] + [U.BENCH]
    df = yf.download(syms, start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
    out = {"built": datetime.date.today().isoformat(), "stats": {}}
    spy = df[U.BENCH]["Close"].dropna()
    for s in syms:
        try:
            c = df[s]["Close"].dropna()
        except KeyError:
            continue
        c = c[c > 0]
        if len(c) < 500:
            continue
        out["stats"][s] = {"from": c.index[0].strftime("%Y-%m-%d"), "to": c.index[-1].strftime("%Y-%m-%d"), "dd": HS.dd_summary(HS.drawdown_cycles(c)),
                           "spy_dd": HS.dd_summary(HS.drawdown_cycles(spy[spy.index >= c.index[0]]))}   # S&P 500 도 이 종목과 같은 기간
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"[collect] 고점 회복 통계 {len(out['stats'])}종목 → {HIST}")
    return out


def load():
    with open(SNAP, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    run()
