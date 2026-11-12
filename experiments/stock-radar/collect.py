"""yfinance 수집 — 일봉(2년) · 시가총액 · 실적 발표일. AI 없음, 무료 (doc/기획/종목-레이더-기획.md 10-8 1단계).

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

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import price_source  # noqa: E402  — yfinance 예비 사슬 (2026-10-21)
import etf_universe  # noqa: E402  — 회원 `내 종목` ETF, 가격만 (2026-11-12)

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
        except (KeyError, TypeError):
            sub = None
        if sub is None or sub.empty:
            # yfinance 가 비면 예비 사슬(FRED → Polygon → Twelve Data → Alpha Vantage, 키 있는 것만) — 2026-10-21 price_source
            fb = price_source.daily_bars(s, (datetime.date.today() - datetime.timedelta(days=731)).isoformat())
            if not fb:
                print(f"[collect] {s}: 일봉 없음")
                continue
            out[s] = [{"day": b["day"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "adj": b["close"], "volume": float(b["volume"] or 0)} for b in fb]
            continue
        out[s] = [{"day": i.strftime("%Y-%m-%d"), "open": float(r["Open"]) if r["Open"] == r["Open"] else None, "high": float(r["High"]), "low": float(r["Low"]), "close": float(r["Close"]),
                   "adj": float(r["Adj Close"]), "volume": float(r["Volume"] or 0)} for i, r in sub.iterrows()]
    # 늦은 봉도 예비로 (2026-11-12 사용자 "예비는 왜 안 도나") — 야후는 막을 때 빈 표만이 아니라 마지막 날이 빠진 표도 준다.
    # 다수결 마지막 날보다 늦은 종목은 예비 사슬에서 빠진 날만 받아 붙인다 (조정 종가 adj 는 예비에 없어 종가로)
    from collections import Counter
    days = Counter(v[-1]["day"] for v in out.values() if v)
    if days:
        top = days.most_common(1)[0][0]
        late = [s for s, v in out.items() if v and v[-1]["day"] < top and "." not in s and not s.startswith("^")][:15]   # 미국 종목 · ETF 만, 많아야 15개(Polygon 무료 분당 5회 — 실행이 3분 넘게 늘지 않게)
        for s in late:
            v = out[s]
            fb = [b for b in price_source.daily_bars(s, v[-1]["day"]) if b["day"] > v[-1]["day"]]
            if fb:
                v += [{"day": b["day"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "adj": b["close"], "volume": float(b["volume"] or 0)} for b in fb]
                print(f"[collect] {s}: 늦은 봉 {len(fb)}일 예비로 채움")
    return out


def _cap(s):
    try:
        v = float(yf.Ticker(s).fast_info.market_cap or 0) or None
    except Exception as e:   # noqa: BLE001
        print(f"[collect] {s} 시총 실패: {e}")
        v = None
    return s, v or price_source.market_cap(s)   # 비면 Finnhub (2026-11-12)


def _earnings(s):
    """실적 발표 시각(뉴욕) 목록. 정오 전 = 장 시작 전(그날 반응), 그 뒤 = 장 마감 뒤(다음 거래일 반응)."""
    try:
        ed = yf.Ticker(s).get_earnings_dates(limit=16)
    except Exception as e:   # noqa: BLE001
        print(f"[collect] {s} 실적일 실패: {e}")
        ed = None
    if ed is None or ed.empty:
        return s, price_source.earnings_dates(s)   # 비면 Finnhub 실적 달력 (2026-11-12)
    out = []
    for ts in ed.index:
        t = pd.Timestamp(ts)
        t = t.tz_convert(NY) if t.tzinfo else t.tz_localize(NY)
        out.append({"day": t.strftime("%Y-%m-%d"), "when": "bmo" if t.hour < 12 else "amc"})
    # 회사 캘린더(Ticker.calendar) 날짜를 먼저 믿는다 — earnings_dates 의 미래 추정일은 하루씩 어긋난다(엔비디아 11-17 vs 11-18).
    # 엔비디아 리포트 collect_calendar 와 같은 규칙, 모든 종목으로 (2026-11-01 사용자)
    try:
        ds = (yf.Ticker(s).calendar or {}).get("Earnings Date") or []
        cal = min(str(d)[:10] for d in ds) if ds else None
    except Exception as e:   # noqa: BLE001
        print(f"[collect] {s} 회사 캘린더 실패: {e}")
        cal = None
    today = datetime.datetime.now(NY).strftime("%Y-%m-%d")
    if cal and cal >= today:
        near = [x for x in out if x["day"] >= today and abs((datetime.date.fromisoformat(x["day"]) - datetime.date.fromisoformat(cal)).days) <= 3]
        out = [x for x in out if x not in near] + [{"day": cal, "when": near[0]["when"] if near else None}]
    return s, sorted({x["day"]: x for x in out}.values(), key=lambda x: x["day"])


def run():
    syms = [c[0] for c in U.CANDIDATES]
    extra = sorted({U.BENCH, "^VIX", "SMH", *SECTOR_ETFS})
    peers = sorted({p for v in U.PEERS.values() for p in v} - set(syms))   # 함께 보는 회사 중 64종목 밖 — `함께 움직이는 종목은?` 오늘 등락 (2026-11-01 사용자 P263). 페이지는 만들지 않는다
    etfs = sorted(set(etf_universe.US_SYMS) - set(syms) - set(extra) - set(peers))   # 맨 뒤 — 늦은 봉 예비(15개) 자리를 종목이 먼저 쓰게
    bars = _bars(syms + extra + peers + etfs)
    # 시총 · 실적일은 바뀌는 주기에 맞춰서만 (detail_cache, 2026-11-12 사용자) — 시총 = 새 거래일마다, 실적일 = 주 1회 · 발표 14일 안이면 매일 · 발표 지난 뒤 처음.
    # 하루 네 번 실행이 같은 날 값을 다시 받던 것 (64종목 × 2 × 4)
    import detail_cache as DC
    cache = DC.shared(os.path.join(BASE, "data"))
    bar_day = max((bars[s][-1]["day"] for s in syms if bars.get(s)), default=None)
    need_cap = [s for s in syms if cache.due(s, "caps", bar=bar_day)]
    need_earn = []
    for s in syms:
        past, nxt = DC.earn_info(cache, s)
        if cache.due(s, "earnings", earn_days=past, next_earn=nxt):
            need_earn.append(s)
    # 스레드 8 → 3: 49종목 × 2 호출을 한꺼번에 쏘면 러너 IP 가 Yahoo 에 막힐 때 전부 같이 죽는다 (운영지침 D6-1, 2026-10-21)
    with ThreadPoolExecutor(3) as ex:
        for s, v in ex.map(_cap, need_cap):
            cache.put(s, "caps", v, bar=bar_day)
        for s, v in ex.map(_earnings, need_earn):
            cache.put(s, "earnings", v)
    cache.reused += (len(syms) - len(need_cap)) + (len(syms) - len(need_earn))
    caps = {s: cache.get(s, "caps") for s in syms}
    earn = {s: cache.get(s, "earnings") or [] for s in syms}
    print(f"[collect] 시총 새로 {len(need_cap)} · 실적일 새로 {len(need_earn)} (나머지 저장값)")
    cache.save("미국 종목 시총 · 실적일")
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
