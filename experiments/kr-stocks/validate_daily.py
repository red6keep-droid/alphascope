"""일별 · 사건 신호 검증 — K17 · K18 · K21 · K22 · K24 · K25 · K26 · K29 · K30 (기획 11-8, 2026-10-25 사용자 "검증해").

    python experiments/kr-stocks/validate_daily.py     # → doc/검증/한국-일별-사건-검증.md · data/validate_daily.json

판정 기준은 결과를 보기 전에 정했다 (RULES). 계산은 전부 코드.
- 일별 자료: yfinance(한국 종목 · KOSPI · KOSDAQ · EWY · ADR · SOX · VIX · 달러지수 · 미국 짝, 배당 반영 종가) · ECOS 802Y001 외국인 순매수 · 817Y002 금리 · 731Y001 환율 · FRED(미국 10년물 · WTI · 천연가스).
- 밤사이 신호: 미국 거래일 t 의 수익은 한국 시간 t+1 새벽에 확정 → 신호는 한국 t 종가 시점에 두고, '다음날' = 한국 t 종가 → t+1 종가 수익. 1차 실행(10-25 낮)은 하루 늦게 셌다(us_to_kr_signal_day 머리말) — 고친 뒤 재실행.
- 신호 → 이후 수익: 신호가 알려진 날의 종가 이후 h 거래일 누적 수익(묶음은 KOSPI 대비 초과).
- 플라시보: 신호 시계열을 통째로 무작위 칸 밀기(circular shift) 500회 — 자기상관 유지. 상위 25% − 하위 25% 차이가 플라시보보다 큰 비율 = p (양쪽).
- 사건(실적 · 배당락 · 만기일): 사건일 반응 = 그날 수익의 절대값 vs 보통 날, 이후 수익 = 사건 뒤 h 일 누적 초과수익 vs 무작위 날 500회.
"""
import datetime
import json
import os
import random
import sys

import numpy as np
import pandas as pd
import requests
import yfinance as yf

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import collect_kr as C  # noqa: E402
import universe_kr as U  # noqa: E402

ROOT = os.path.join(BASE, "..", "..")
OUT_MD = os.path.join(ROOT, "doc", "검증", "한국-일별-사건-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_daily.json")
SEED = 20261025
N_PL = 500
MIN_N = 250
RULES = ("통과 = ① 상위 25% − 하위 25% 의 이후 수익 차이가 예상 방향 ② 플라시보(통째 밀기 500회) p < 0.05 ③ 앞뒤 절반 같은 방향 — "
         "일별은 1 · 5 · 20거래일 가운데 하나, 월 단위 신호는 20 · 60거래일 가운데 하나. 한 묶음(K번호) 안의 검정 수가 많으면 BH q 도 함께 적는다")

EXPORT = ["005930.KS", "000660.KS", "005380.KS", "000270.KS", "373220.KS", "006400.KS", "329180.KS", "042660.KS", "009540.KS", "012450.KS", "207940.KS", "068270.KS", "005490.KS", "010130.KS", "051910.KS"]
DOMESTIC = ["105560.KS", "055550.KS", "086790.KS", "032830.KS", "000810.KS", "035420.KS", "035720.KS", "017670.KS", "015760.KS", "028260.KS"]
SEMI = ["005930.KS", "000660.KS", "402340.KS", "042700.KS"]
ADR = {"PKX": "005490.KS", "KB": "105560.KS", "SHG": "055550.KS", "SKM": "017670.KS"}
US_PAIRS = sorted({t for v in U.PAIRS.values() for t in v[0]})


# ── 데이터 ──────────────────────────────────────────────────────────────

def prices():
    syms = [c[0] for c in U.CANDIDATES] + ["^KS11", "^KQ11", "EWY", "KORU", "^SOX", "^VIX", "DX-Y.NYB"] + list(ADR) + US_PAIRS
    df = yf.download(syms, start="2000-01-01", interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=3)
    px = {}
    for s in syms:
        try:
            c = df[s]["Close"].dropna()
        except KeyError:
            continue
        c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
        px[s] = c[~c.index.duplicated(keep="last")]
    return pd.DataFrame(px)


def fred(series):
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
        key = os.environ.get("FRED_API_KEY", "")
    out = {}
    for s in series:
        try:
            j = requests.get("https://api.stlouisfed.org/fred/series/observations", params={"series_id": s, "api_key": key, "file_type": "json", "observation_start": "2000-01-01"}, timeout=30).json()
            out[s] = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in j.get("observations", []) if o["value"] not in (".", "")}).sort_index()
        except Exception as e:   # noqa: BLE001
            print(f"[daily] FRED {s} 실패: {str(e)[:60]}")
    return out


def ecos_daily(stat, item, start="20030101"):
    rows = C._ecos(C._ecos_key(), stat, "D", start, datetime.date.today().strftime("%Y%m%d"), item, n=10000)
    return pd.Series({pd.Timestamp(x["TIME"]): float(x["DATA_VALUE"]) for x in rows if x.get("DATA_VALUE") not in (None, "")}).sort_index()


# ── 도구 ────────────────────────────────────────────────────────────────

def basket_excess(px, members, bench="^KS11"):
    r = px[[m for m in members if m in px.columns]].pct_change(fill_method=None)
    return (r.mean(axis=1, skipna=True) - px[bench].pct_change(fill_method=None)).dropna() * 100


def fwd_sum(ret, h):
    """t 종가 이후 h 거래일 누적 (단순 합, %)."""
    return ret[::-1].rolling(h).sum()[::-1].shift(-1)


def next_kr_day(us_dates, kr_index):
    """미국 날짜 → 그보다 큰 첫 한국 거래일 (사건일 정렬용)."""
    pos = kr_index.searchsorted(us_dates, side="right")
    pos = np.minimum(pos, len(kr_index) - 1)
    return kr_index[pos]


def us_to_kr_signal_day(us_dates, kr_index):
    """미국 거래일 t 의 종가 신호를 '어느 한국 거래일 종가 시점에 알려진 것' 으로 둘지 — 미국 장 t 는 한국 t 종가(15:30 KST = 새벽 ET) 뒤에 열리고
    한국 t+1 개장 전에 끝난다. 그래서 신호는 **t 보다 작거나 같은 마지막 한국 거래일** 에 두고, 이후 1거래일 수익 = 한국 t+1 (진짜 '다음날').
    (2026-10-25 1차 실행은 t 보다 큰 첫 거래일에 두어 하루 늦게 셌다 — 고침)"""
    pos = kr_index.searchsorted(us_dates, side="right") - 1
    pos = np.clip(pos, 0, len(kr_index) - 1)
    return kr_index[pos]


def quart_spread(sig, fwd):
    d = pd.concat([sig, fwd], axis=1, keys=["s", "f"]).dropna()
    if len(d) < MIN_N:
        return None, len(d)
    q1, q3 = d["s"].quantile(0.25), d["s"].quantile(0.75)
    return float(d.loc[d["s"] >= q3, "f"].mean() - d.loc[d["s"] <= q1, "f"].mean()), len(d)


def placebo(sig, fwd, actual, rng, n=N_PL):
    v = sig.dropna()
    hits = 0
    for _ in range(n):
        k = rng.randint(30, len(v) - 30)
        sp, _ = quart_spread(pd.Series(np.roll(v.values, k), index=v.index), fwd)
        if sp is not None and abs(sp) >= abs(actual):
            hits += 1
    return (hits + 1) / (n + 1)


def test(name, group, sig, target_ret, horizons, expect, rng, note=""):
    """sig: 신호(알려진 날 기준) · target_ret: 일별 수익(%) 시계열. 결과 dict."""
    sig = sig.dropna()
    out = {"name": name, "group": group, "expect": expect, "note": note, "from": str(sig.index.min().date()) if len(sig) else None, "to": str(sig.index.max().date()) if len(sig) else None, "h": {}}
    common = sig.index.intersection(target_ret.index)
    half = common[len(common) // 2] if len(common) else None
    passed = []
    for h in horizons:
        f = fwd_sum(target_ret, h)
        sp, n = quart_spread(sig, f)
        if sp is None:
            out["h"][h] = {"n": n}
            continue
        p = placebo(sig, f, sp, rng)
        a, _ = quart_spread(sig[sig.index <= half], f)
        b, _ = quart_spread(sig[sig.index > half], f)
        stable = a is not None and b is not None and np.sign(a) == np.sign(b) == np.sign(expect)
        ok = bool(np.sign(sp) == np.sign(expect) and p < 0.05 and stable)
        d = pd.concat([sig, f], axis=1).dropna()
        corr = float(d.corr().iloc[0, 1]) if len(d) > 2 else None
        out["h"][h] = {"spread": sp, "n": n, "p": p, "corr": corr, "first_half": a, "second_half": b, "stable": bool(stable), "pass": ok}
        if ok:
            passed.append(h)
    out["pass_h"] = passed
    out["pass"] = bool(passed)
    return out


def bh(pvals):
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, pvals[i] * n / rank)
        q[i] = prev
    return q


# ── 검정 묶음 ───────────────────────────────────────────────────────────

def run_overnight(px, rng, results):
    """K24 · K25 · K17① — 미국 거래일 수익 → 다음 한국 거래일."""
    kr = px["^KS11"].pct_change(fill_method=None).dropna() * 100
    def us_sig(sym):
        s = px[sym].pct_change(fill_method=None).dropna() * 100
        s.index = us_to_kr_signal_day(s.index, kr.index)
        return s[~s.index.duplicated(keep="last")]
    def level_sig(sym, chg=False):
        s = px[sym].dropna()
        s = (s.diff() if chg else s)
        s.index = us_to_kr_signal_day(s.index, kr.index)
        return s[~s.index.duplicated(keep="last")].dropna()
    for sym, label in (("EWY", "EWY(MSCI 한국 ETF) 밤사이 수익"), ("KORU", "KORU 밤사이 수익")):
        if sym in px:
            results.append(test(f"{label} → KOSPI 다음날", "K24", us_sig(sym), kr, (1, 5, 20), +1, rng, "미국 장에서 거래된 한국 가격"))
    for adr, ks in ADR.items():
        if adr in px and ks in px:
            tgt = px[ks].pct_change(fill_method=None).dropna() * 100
            results.append(test(f"{adr} ADR 밤사이 → {U.name(ks)} 다음날", "K24", us_sig(adr), tgt, (1, 5), +1, rng))
    semi = basket_excess(px, SEMI)
    if "^SOX" in px:
        results.append(test("SOX(필라델피아 반도체) 밤사이 → 반도체 묶음 다음날 (KOSPI 대비)", "K25", us_sig("^SOX"), semi, (1, 5, 20), +1, rng))
        results.append(test("SOX 밤사이 → KOSPI 다음날", "K25", us_sig("^SOX"), kr, (1, 5), +1, rng))
    if "^VIX" in px:
        results.append(test("VIX 밤사이 변화 → KOSPI 다음날", "K25", level_sig("^VIX", chg=True), kr, (1, 5, 20), -1, rng))
    if "DX-Y.NYB" in px:
        results.append(test("달러지수 밤사이 수익 → KOSPI 다음날", "K25", us_sig("DX-Y.NYB"), kr, (1, 5, 20), -1, rng))
    # K17① 미국 짝 → 종목 (짝이 있는 종목 전부, 짝 평균)
    for ks, (pairs, why) in U.PAIRS.items():
        ps = [p for p in pairs if p in px]
        if not ps or ks not in px:
            continue
        sig = (px[ps].pct_change(fill_method=None).mean(axis=1) * 100).dropna()
        sig.index = us_to_kr_signal_day(sig.index, kr.index)
        sig = sig[~sig.index.duplicated(keep="last")]
        tgt = (px[ks].pct_change(fill_method=None) * 100 - kr).dropna()
        results.append(test(f"미국 짝({'·'.join(ps)}) 밤사이 → {U.name(ks)} 다음날 (KOSPI 대비)", "K17①", sig, tgt, (1, 5), +1, rng))


def run_flows_fx_rates(px, rng, results):
    """K17② 외국인 · ③ 환율 · ④ 금리 스프레드 · ⑤ 거래대금."""
    kr = px["^KS11"].pct_change(fill_method=None).dropna() * 100
    exp_ex = basket_excess(px, EXPORT)
    dom_ex = basket_excess(px, DOMESTIC)
    try:
        f = ecos_daily("802Y001", "0030000")   # 외국인 순매수 유가증권 억원
        for w in (5, 20):
            cum = f.rolling(w).sum()
            z = (cum - cum.rolling(250).mean()) / cum.rolling(250).std()
            results.append(test(f"외국인 순매수 {w}일 누적(1년 표준화) → KOSPI 이후", "K17②", z.dropna(), kr, (1, 5, 20), +1, rng, "ECOS 802Y001"))
        tv = ecos_daily("802Y001", "0088000")   # 거래대금 억원
        ratio = tv / tv.rolling(20).mean()
        results.append(test("거래대금 ÷ 20일 평균 → KOSPI 이후", "K17⑤", ratio.dropna(), kr, (1, 5, 20), -1, rng, "과열 가설: 거래 급증 뒤 부진"))
    except Exception as e:   # noqa: BLE001
        print(f"[daily] ECOS 외국인/거래대금 실패: {str(e)[:80]}")
    try:
        usd = ecos_daily("731Y001", "0000001")
        chg20 = (usd / usd.shift(20) - 1) * 100
        results.append(test("원/달러 20일 변화(+ = 원화 약세) → 수출형 − 내수형 이후", "K17③", chg20.dropna(), (exp_ex - dom_ex).dropna(), (5, 20, 60), +1, rng))
        results.append(test("원/달러 20일 변화 → KOSPI 이후", "K17③", chg20.dropna(), kr, (5, 20, 60), -1, rng, "원화 약세 = 외국인 이탈 가설"))
        results.append(test("원/달러 하루 변화 → KOSPI 다음날", "K17③", ((usd / usd.shift(1) - 1) * 100).dropna(), kr, (1, 5), -1, rng))
    except Exception as e:   # noqa: BLE001
        print(f"[daily] ECOS 환율 실패: {str(e)[:80]}")
    try:
        k3, k10, bbb = ecos_daily("817Y002", "010200000", "19990101"), ecos_daily("817Y002", "010210000", "20001218"), ecos_daily("817Y002", "010320000", "20001001")
        bank = basket_excess(px, ["105560.KS", "055550.KS", "086790.KS"])
        results.append(test("국고채 10년 − 3년(장단기 차) → KOSPI 이후", "K17④", (k10 - k3).dropna(), kr, (20, 60), +1, rng))
        results.append(test("국고채 10년 − 3년 → 은행 묶음 이후 (KOSPI 대비)", "K17④", (k10 - k3).dropna(), bank, (20, 60), +1, rng))
        results.append(test("회사채 BBB− − 국고채 3년(신용 스프레드) → KOSPI 이후", "K17④", (bbb - k3).dropna(), kr, (20, 60), -1, rng))
        results.append(test("신용 스프레드 20일 변화 → KOSPI 이후", "K17④", (bbb - k3).diff(20).dropna(), kr, (5, 20, 60), -1, rng))
    except Exception as e:   # noqa: BLE001
        print(f"[daily] ECOS 금리 실패: {str(e)[:80]}")


def run_us_macro_commodity(px, rng, results):
    """K21 원자재 · K25 미국 10년물 (FRED 일별)."""
    kr = px["^KS11"].pct_change(fill_method=None).dropna() * 100
    fr = fred(["DGS10", "DCOILWTICO", "DHHNGSP"])
    def kr_align(s):
        s = s.dropna()
        s.index = us_to_kr_signal_day(s.index, kr.index)
        return s[~s.index.duplicated(keep="last")]
    if "DGS10" in fr:
        results.append(test("미국 10년물 하루 변화(bp) → KOSPI 다음날", "K25", kr_align(fr["DGS10"].diff() * 100), kr, (1, 5, 20), -1, rng))
        results.append(test("미국 10년물 20일 변화 → KOSPI 이후", "K25", kr_align(fr["DGS10"].diff(20) * 100), kr, (5, 20, 60), -1, rng))
    if "DCOILWTICO" in fr:
        wti = fr["DCOILWTICO"]
        kepco = (px["015760.KS"].pct_change(fill_method=None) * 100 - kr).dropna()
        chem = basket_excess(px, ["051910.KS", "005490.KS"])
        results.append(test("WTI 20일 변화 → 한국전력 이후 (KOSPI 대비)", "K21", kr_align((wti / wti.shift(20) - 1) * 100), kepco, (5, 20, 60), -1, rng, "원가 상승 = 나쁨"))
        results.append(test("WTI 하루 변화 → 한국전력 다음날", "K21", kr_align((wti / wti.shift(1) - 1) * 100), kepco, (1, 5), -1, rng))
        results.append(test("WTI 20일 변화 → 화학 · 철강(LG화학 · POSCO) 이후", "K21", kr_align((wti / wti.shift(20) - 1) * 100), chem, (5, 20, 60), +1, rng, "제품가 전가 가설"))
    if "DHHNGSP" in fr:
        ng = fr["DHHNGSP"]
        kepco = (px["015760.KS"].pct_change(fill_method=None) * 100 - kr).dropna()
        results.append(test("미국 천연가스 20일 변화 → 한국전력 이후", "K21", kr_align((ng / ng.shift(20) - 1) * 100), kepco, (5, 20, 60), -1, rng, "LNG 가격의 대리"))


def run_price_signals(px, rng, results):
    """K18 — 월말 재조정, 횡단면 신호 → 다음 달 초과수익. 신호를 시계열로 바꿔(상위 5 − 하위 5 묶음 수익) 같은 틀로 검정하지 않고,
    5분위 상위 − 하위 월별 수익과 그 플라시보(종목 라벨 섞기)를 쓴다."""
    kr_syms = [c[0] for c in U.CANDIDATES if c[0] in px.columns]
    P = px[kr_syms + ["^KS11"]].resample("ME").last()
    m_ret = P.pct_change(fill_method=None) * 100
    def quintile_ls(signal_df, name, expect=+1):
        rows = []
        for i in range(len(signal_df.index) - 1):
            s = signal_df.iloc[i].dropna()
            if len(s) < 10:
                continue
            nxt = m_ret.iloc[i + 1][s.index].dropna()
            s = s[nxt.index]
            if len(s) < 10:
                continue
            k = max(2, len(s) // 5)
            top, bot = s.nlargest(k).index, s.nsmallest(k).index
            rows.append((signal_df.index[i + 1], nxt[top].mean() - nxt[bot].mean()))
        ls = pd.Series(dict(rows))
        if len(ls) < 60:
            return {"name": name, "group": "K18", "n": len(ls), "note": "표본 부족"}
        mean = float(ls.mean())
        # 플라시보: 종목 라벨 섞기 500회
        pl = []
        for _ in range(N_PL):
            vals = []
            for i in range(len(signal_df.index) - 1):
                s = signal_df.iloc[i].dropna()
                nxt = m_ret.iloc[i + 1][s.index].dropna()
                s = s[nxt.index]
                if len(s) < 10:
                    continue
                perm = pd.Series(rng.sample(list(s.values), len(s)), index=s.index)
                k = max(2, len(s) // 5)
                vals.append(nxt[perm.nlargest(k).index].mean() - nxt[perm.nsmallest(k).index].mean())
            pl.append(np.mean(vals))
        p = (sum(1 for v in pl if abs(v) >= abs(mean)) + 1) / (N_PL + 1)
        half = len(ls) // 2
        a, b = float(ls.iloc[:half].mean()), float(ls.iloc[half:].mean())
        ok = bool(np.sign(mean) == expect and p < 0.05 and np.sign(a) == np.sign(b) == expect)
        return {"name": name, "group": "K18", "expect": expect, "from": str(ls.index.min().date()), "to": str(ls.index.max().date()),
                "h": {"월": {"spread": mean, "n": len(ls), "p": p, "first_half": a, "second_half": b, "stable": bool(np.sign(a) == np.sign(b) == expect), "pass": ok,
                           "hit_rate": float((ls > 0).mean())}}, "pass": ok, "pass_h": ["월"] if ok else [], "note": "월말 5분위 상위 − 하위, 다음 달 수익(%p). 플라시보 = 종목 라벨 섞기"}
    px_m = P[kr_syms]
    mom = (px_m.shift(1) / px_m.shift(12) - 1) * 100           # 12-1 모멘텀 (최근 1달 제외)
    results.append(quintile_ls(mom, "12-1 모멘텀 상위 − 하위 → 다음 달"))
    rev = px_m.pct_change(fill_method=None) * 100               # 1개월 수익 (단기 반전 가설)
    results.append(quintile_ls(rev, "지난 1개월 수익 상위 − 하위 → 다음 달 (반전이면 −)", expect=-1))
    high52 = px_m / px[kr_syms].rolling(252).max().resample("ME").last() * 100
    results.append(quintile_ls(high52, "52주 최고가 대비 위치 상위 − 하위 → 다음 달"))
    ma200 = (px_m / px[kr_syms].rolling(200).mean().resample("ME").last() - 1) * 100
    results.append(quintile_ls(ma200, "200일선 대비 거리 상위 − 하위 → 다음 달"))


def run_events(px, rng, results):
    """K26 실적 · K30 배당락 · K22 달력."""
    kr = px["^KS11"].pct_change(fill_method=None).dropna() * 100
    kr_days = kr.index
    kst = "Asia/Seoul"
    def reaction_day(ts):
        t = pd.Timestamp(ts).tz_convert(kst)
        d = pd.Timestamp(t.date())
        if t.hour * 60 + t.minute >= 15 * 60 + 30:
            d = d + pd.Timedelta(days=1)
        pos = kr_days.searchsorted(d)
        return kr_days[min(pos, len(kr_days) - 1)]
    # K26 — 실적 발표일 반응 · 서프라이즈 뒤 20 · 60일
    abs_ratio, surprise_rows = [], []
    for c in U.CANDIDATES:
        s = c[0]
        if s not in px:
            continue
        try:
            ed = yf.Ticker(s).get_earnings_dates(limit=60)
        except Exception:   # noqa: BLE001
            continue
        if ed is None or ed.empty:
            continue
        ex = (px[s].pct_change(fill_method=None) * 100 - kr).dropna()
        ret = (px[s].pct_change(fill_method=None) * 100).dropna()
        sd = ret.rolling(60).std()
        for ts, row in ed.iterrows():
            if pd.isna(row.get("Reported EPS")):
                continue
            d = reaction_day(ts)
            if d not in ret.index or pd.isna(sd.get(d)):
                continue
            abs_ratio.append(abs(ret[d]) / sd[d])
            sp = row.get("Surprise(%)")
            if pd.notna(sp):
                f20, f60 = fwd_sum(ex, 20).get(d), fwd_sum(ex, 60).get(d)
                surprise_rows.append({"sym": s, "day": d, "surprise": float(sp), "day_ex": float(ex.get(d, np.nan)), "f20": f20, "f60": f60})
    if abs_ratio:
        results.append({"name": "실적 발표 반응일 |수익| ÷ 60일 표준편차 (1 = 보통 날)", "group": "K26", "n": len(abs_ratio), "median_ratio": float(np.median(abs_ratio)), "mean_ratio": float(np.mean(abs_ratio)),
                        "share_over_2x": float(np.mean([x > 2 for x in abs_ratio])), "pass": None, "note": "참고 — 발표일에 평소보다 얼마나 크게 움직이나"})
    if surprise_rows:
        df = pd.DataFrame(surprise_rows).dropna(subset=["f20", "f60"])
        q1, q3 = df["surprise"].quantile(0.25), df["surprise"].quantile(0.75)
        out = {"name": "실적 서프라이즈 상위 25% − 하위 25% → 발표 뒤 초과수익 (PEAD)", "group": "K26", "n": len(df), "from": str(df["day"].min().date()), "to": str(df["day"].max().date()), "h": {}, "pass_h": []}
        for col, h in (("day_ex", 0), ("f20", 20), ("f60", 60)):
            d_ = df[col].dropna()
            sp = float(df.loc[df["surprise"] >= q3, col].mean() - df.loc[df["surprise"] <= q1, col].mean())
            pl = []
            vals = df[col].values
            sur = df["surprise"].values
            for _ in range(N_PL):
                perm = np.random.default_rng(rng.randint(0, 10**9)).permutation(sur)
                pl.append(vals[perm >= q3].mean() - vals[perm <= q1].mean())
            p = (sum(1 for v in pl if abs(v) >= abs(sp)) + 1) / (N_PL + 1)
            mid = df["day"].median()
            a = float(df[df["day"] <= mid].pipe(lambda x: x.loc[x["surprise"] >= q3, col].mean() - x.loc[x["surprise"] <= q1, col].mean()))
            b = float(df[df["day"] > mid].pipe(lambda x: x.loc[x["surprise"] >= q3, col].mean() - x.loc[x["surprise"] <= q1, col].mean()))
            ok = bool(sp > 0 and p < 0.05 and a > 0 and b > 0)
            out["h"][h] = {"spread": sp, "n": int(d_.shape[0]), "p": p, "first_half": a, "second_half": b, "stable": bool(a > 0 and b > 0), "pass": ok}
            if ok and h > 0:
                out["pass_h"].append(h)
        out["pass"] = bool(out["pass_h"])
        out["expect"] = +1
        out["note"] = "플라시보 = 서프라이즈 라벨 섞기. 0 = 반응일 당일"
        results.append(out)
    # K30 — 배당락일(배당 지급 기준일 전후) 종목 초과수익 −5 ~ +5
    windows = {k: [] for k in range(-5, 6)}
    n_ev = 0
    for c in U.CANDIDATES:
        s = c[0]
        if s not in px:
            continue
        try:
            dv = yf.Ticker(s).dividends
        except Exception:   # noqa: BLE001
            continue
        if dv is None or dv.empty:
            continue
        ex = (px[s].pct_change(fill_method=None) * 100 - kr).dropna()
        for ts in dv.index:
            d = pd.Timestamp(pd.Timestamp(ts).tz_convert(kst).date())
            pos = ex.index.searchsorted(d)
            if pos - 5 < 0 or pos + 5 >= len(ex):
                continue
            n_ev += 1
            for k in range(-5, 6):
                windows[k].append(ex.iloc[pos + k])
    if n_ev:
        results.append({"name": "배당락일 전후 일별 초과수익 평균 (−5 ~ +5)", "group": "K30", "n": n_ev, "window": {str(k): float(np.mean(v)) for k, v in windows.items()}, "pass": None,
                        "note": "참고 — 야후 배당일 기준(배당락일 표기). 전날(−1) 양수 · 당일(0) 음수면 배당락 효과"})
    # K22 — 월별 계절성 · 옵션 만기(둘째 목요일) · 삼성전자 실적 발표일 KOSPI 반응
    m = kr.groupby(kr.index.month).agg(["mean", "count"])
    daily_all = kr.values
    seas = {}
    for mo in range(1, 13):
        v = kr[kr.index.month == mo]
        boot = [np.mean(np.random.default_rng(rng.randint(0, 10**9)).choice(daily_all, len(v))) for _ in range(N_PL)]
        p = (sum(1 for b in boot if abs(b) >= abs(v.mean())) + 1) / (N_PL + 1)
        seas[mo] = {"mean_daily": float(v.mean()), "n": int(len(v)), "p": p}
    results.append({"name": "월별 계절성 — KOSPI 일 평균 수익(%), 무작위 날 부트스트랩 p", "group": "K22", "months": seas, "pass": None, "note": "참고"})
    thursdays = [d for d in kr.index if d.weekday() == 3 and 8 <= d.day <= 14]
    exp_ = kr.reindex(thursdays).dropna()
    nxt = kr.shift(-1).reindex(thursdays).dropna()
    boot = [np.mean(np.random.default_rng(rng.randint(0, 10**9)).choice(daily_all, len(exp_))) for _ in range(N_PL)]
    results.append({"name": "옵션 만기일(둘째 목요일) KOSPI 수익", "group": "K22", "n": int(len(exp_)), "mean_day": float(exp_.mean()), "mean_next": float(nxt.mean()), "abs_mean": float(exp_.abs().mean()), "abs_all": float(kr.abs().mean()),
                    "p_mean": (sum(1 for b in boot if abs(b) >= abs(exp_.mean())) + 1) / (N_PL + 1), "pass": None, "note": "참고"})
    try:
        ed = yf.Ticker("005930.KS").get_earnings_dates(limit=60)
        days = [reaction_day(ts) for ts, row in ed.iterrows() if pd.notna(row.get("Reported EPS"))]
        v = kr.reindex(days).dropna()
        results.append({"name": "삼성전자 실적 발표(반응)일 KOSPI 수익 · |수익|", "group": "K22", "n": int(len(v)), "mean": float(v.mean()), "abs_mean": float(v.abs().mean()), "abs_all": float(kr.abs().mean()), "pass": None, "note": "참고"})
    except Exception as e:   # noqa: BLE001
        print(f"[daily] 삼성 실적일 실패: {str(e)[:60]}")


def run_relative(px, rng, results):
    """K29 — 코스닥/코스피 상대강도 · 일드갭(월)."""
    kr = px["^KS11"].pct_change(fill_method=None).dropna() * 100
    rs = ((px["^KQ11"] / px["^KS11"]) / (px["^KQ11"] / px["^KS11"]).shift(20) - 1) * 100
    results.append(test("코스닥/코스피 20일 상대강도(+ = 코스닥 우위 · 위험 선호) → KOSPI 이후", "K29", rs.dropna(), kr, (5, 20, 60), +1, rng))
    try:
        dy = C._ecos(C._ecos_key(), "901Y014", "M", "200401", datetime.date.today().strftime("%Y%m"), "1100000")
        dy = pd.Series({pd.Period(x["TIME"][:4] + "-" + x["TIME"][4:], "M"): float(x["DATA_VALUE"]) for x in dy if x.get("DATA_VALUE") not in (None, "")}).sort_index()
        k3 = ecos_daily("817Y002", "010200000", "20040101")
        k3m = k3.groupby(k3.index.to_period("M")).mean()
        gap = (dy - k3m).dropna()
        # 월말 KOSPI 로 이후 수익 (20 · 60 거래일 ≈ 1 · 3개월): 신호를 다음 달 첫 거래일에 둔다(발표 지연 1개월)
        sig = pd.Series(gap.values, index=[next_kr_day(pd.Timestamp((p + 1).to_timestamp()), kr.index) for p in gap.index])
        results.append(test("KOSPI 배당수익률 − 국고채 3년(일드갭, 월) → KOSPI 이후", "K29", sig[~sig.index.duplicated()], kr, (20, 60), +1, rng, "ECOS 901Y014 · 817Y002"))
    except Exception as e:   # noqa: BLE001
        print(f"[daily] 일드갭 실패: {str(e)[:80]}")


# ── 문서 ────────────────────────────────────────────────────────────────

def write_md(results, period):
    tests = [r for r in results if "h" in r]
    refs = [(i, h) for i, r in enumerate(tests) for h in r["h"] if "p" in r["h"][h]]
    qs = bh([tests[i]["h"][h]["p"] for i, h in refs])
    for (i, h), q in zip(refs, qs):
        tests[i]["h"][h]["q"] = q
    L = ["# 한국 일별 · 사건 신호 검증 (K17 · K18 · K21 · K22 · K24 · K25 · K26 · K29 · K30)", "",
         f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/kr-stocks/validate_daily.py` · 후보 목록 [종목-레이더-기획 11-8](../기획/종목-레이더-기획.md)", "",
         "## 미리 정한 기준 (결과를 보기 전)", "", f"- {RULES}.",
         "- 밤사이 신호: 미국 거래일 t 수익(한국 t+1 새벽 확정) → 한국 t 종가에서 t+1 종가까지의 수익. 즉 다음날 시가 갭을 포함한다 — 시가에 사면 못 얻는 몫이 있다(아래 '시가 뒤 남는 몫' 절). 묶음은 KOSPI 대비 초과수익.",
         "- 플라시보: 신호 통째 밀기 500회(일별) · 종목 라벨 섞기(횡단면) · 서프라이즈 라벨 섞기(실적) · 무작위 날 부트스트랩(달력).",
         f"- 기간: 주가 {period}. ECOS 일별 2003~, FRED 2000~. 한계: 종가 대비 종가라 시가 갭은 안 본다(밤사이 신호는 다음날 시가에 상당 부분 반영될 수 있어 **과소평가**), 생존 편향, 거래 비용 없음.",
         f"- 검정 {len(refs)}개 전체에 BH q 를 붙였다(q < 0.10 이면 다중 검정 뒤에도 남는 것).", "",
         "## 결과 요약 (통과 → 뚜렷 → 나머지)", "", "| 묶음 | 신호 → 대상 | 기간 | 상위25% − 하위25% | p · q | 앞/뒤 절반 | 판정 |", "|---|---|---|---|---|---|---|"]
    def key(r):
        best = min((r["h"][h].get("p", 1) for h in r["h"]), default=1)
        return (not r.get("pass"), best)
    for r in sorted(tests, key=key):
        for h, x in r["h"].items():
            if "spread" not in x:
                L.append(f"| {r['group']} | {r['name']} | {h} | 표본 부족 (n {x.get('n', 0)}) | | | |")
                continue
            unit = "%p" if r["group"] != "K18" else "%p/월"
            fh = "—" if x.get("first_half") is None else f"{x['first_half']:+.2f}"
            sh = "—" if x.get("second_half") is None else f"{x['second_half']:+.2f}"
            L.append(f"| {r['group']} | {r['name']} | {h}{'일' if isinstance(h, int) else ''} | {x['spread']:+.2f}{unit} (n {x['n']}) | {x['p']:.3f} · {x.get('q', float('nan')):.2f} | {fh} / {sh} | "
                     f"{'✅ 통과' if x.get('pass') else ('방향 맞음' if np.sign(x['spread']) == r.get('expect', 1) else '방향 반대')} |")
    L += ["", "## 참고 결과 (판정 없음)", ""]
    for r in results:
        if "h" in r:
            continue
        L.append(f"- **{r['name']}** ({r['group']}): " + json.dumps({k: v for k, v in r.items() if k not in ('name', 'group', 'pass', 'note')}, ensure_ascii=False, default=lambda o: round(o, 3) if isinstance(o, float) else str(o))[:900] + (f" — {r['note']}" if r.get("note") else ""))
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    tail = ""   # 손으로 쓴 '## 결론' 아래는 다시 만들 때 보존
    if os.path.exists(OUT_MD):
        old = open(OUT_MD, encoding="utf-8").read()
        if "\n## 결론" in old:
            tail = old[old.index("\n## 결론"):]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n" + tail)


def main():
    rng = random.Random(SEED)
    print("[daily] 주가 받기…")
    px = prices()
    period = f"{px.index.min().date()} ~ {px.index.max().date()}"
    results = []
    only = [a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--only=")]
    only = only[0] if only else None
    fns = (run_overnight, run_flows_fx_rates, run_us_macro_commodity, run_price_signals, run_events, run_relative)
    if only:   # 일부만 다시 돌리고 나머지는 지난 결과(JSON)에서 가져온다
        fns = tuple(f for f in fns if f.__name__.replace("run_", "") in only)
        groups_rerun = {"overnight": ("K24", "K25", "K17①"), "us_macro_commodity": ("K21", "K25")}
        drop = set(g for f in fns for g in groups_rerun.get(f.__name__.replace("run_", ""), ()))
        try:
            old = json.load(open(OUT_JSON, encoding="utf-8"))["results"]
            for r in old:
                if "h" in r:
                    r["h"] = {(int(k) if str(k).isdigit() else k): v for k, v in r["h"].items()}
            results = [r for r in old if r["group"] not in drop or (r["group"] == "K25" and "10년물" in r["name"] and "us_macro_commodity" not in [f.__name__.replace("run_", "") for f in fns])]
            print(f"[daily] 지난 결과 {len(results)}개 유지, {sorted(drop)} 다시 계산")
        except Exception as e:   # noqa: BLE001
            print(f"[daily] 지난 결과 없음: {e}")
    for fn in fns:
        print(f"[daily] {fn.__name__}…")
        try:
            fn(px, rng, results)
        except Exception as e:   # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"[daily] {fn.__name__} 실패: {str(e)[:120]}")
    for r in results:
        if "h" in r:
            best = min(((h, x) for h, x in r["h"].items() if "p" in x), key=lambda t: t[1]["p"], default=None)
            if best:
                h, x = best
                print(f"[daily] {r['group']:5s} {'✅' if r.get('pass') else '  '} {r['name'][:60]:60s} {h}: {x['spread']:+.2f} p{x['p']:.3f}")
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"built": datetime.date.today().isoformat(), "period": period, "rules": RULES, "results": results}, f, ensure_ascii=False, default=str)
    write_md(results, period)
    print(f"[daily] 통과 {sum(1 for r in results if r.get('pass'))} / 검정 {sum(1 for r in results if 'h' in r)} → {OUT_MD}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
