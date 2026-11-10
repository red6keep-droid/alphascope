"""헤지펀드 선물 포지션 + VIX 상승 → 급락 검증 (2026-11-09 사용자 "다음 단계 해").

    python experiments/issue_store/position_check.py

결과 보기 전 고정한 설계 = 비공개 doc/검증/헤지펀드-포지션-급락-검증.md. 요약:
- 포지션 = CFTC TFF 레버리지 펀드 순포지션(S&P 500 E-mini 13874A → ^GSPC, 나스닥 100 E-mini 209742 → ^NDX), 2006-06 ~.
- 3년 범위 자리 = 156주 최저~최고 안 % (리포트 카드와 같은 계산). 화요일 포지션은 금요일 발표 → 다음 거래일 종가부터 신호.
- 상태: P1 ≥90% · P2 ≤10% · P3 주간 변화 하위 10% · V VIX ≥ 20일 평균×1.1 · K1 P1&V · K2 P2&V · K3 P3&V · K4 P1&V&50일선 아래 · X1 V · X2 VIX>25.
- 결과 = MDD20 ≤ −5% 비율 (보조 MDD5 ≤ −3%). 에피소드 = 20거래일 넘게 끊겼다 켜진 첫 날.
- 플라시보 ① 아무 날 · ② (K 만) V 켜진 날 — 각 2,000번. 앞 절반 ~2017-12 / 뒤 절반 2018-01~.
- 통과 = 에피소드 ≥30, p① <0.05, 두 절반 같은 방향, 1.25배↑ (K 는 더해서 p② <0.05 · V 날의 1.25배↑).
"""
import datetime
import os

import numpy as np
import pandas as pd
import requests
import yfinance as yf

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "results")
URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
PAIRS = [("13874A", "S&P 500", "^GSPC"), ("209742", "나스닥 100", "^NDX")]
WEEKS = 156
GAP = 20
NBOOT = 2000
SPLIT = pd.Timestamp("2018-01-01")
rng = np.random.default_rng(20261109)


def cftc(code):
    r = requests.get(URL, params={
        "$select": "report_date_as_yyyy_mm_dd,lev_money_positions_long,lev_money_positions_short",
        "$where": f"cftc_contract_market_code='{code}'", "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": 5000,
    }, headers={"User-Agent": "alpha-scope/position-check"}, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    df["d"] = pd.to_datetime(df.report_date_as_yyyy_mm_dd.str[:10])
    df["net"] = df.lev_money_positions_long.astype(int) - df.lev_money_positions_short.astype(int)
    w = df.groupby("d").net.sum().sort_index()   # 같은 날 두 줄(이름 바뀐 주)이 있으면 합 — 실제로는 없음
    lo, hi = w.rolling(WEEKS).min(), w.rolling(WEEKS).max()
    pos = (w - lo) / (hi - lo) * 100
    dn = w.diff()
    thr = dn.shift(1).rolling(WEEKS).quantile(0.10)
    return pd.DataFrame({"net": w, "pos": pos, "p3": dn <= thr})


def close(sym):
    c = yf.download(sym, start="2005-01-01", progress=False, auto_adjust=False)["Close"].squeeze().dropna()
    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
    return c[~c.index.duplicated()]


def to_daily(wk, idx):
    """화요일 기준 → 토요일(+4일) 이후 첫 거래일부터 쓴다."""
    avail = wk.copy()
    avail.index = [idx[idx.searchsorted(d + pd.Timedelta(days=4))] if idx.searchsorted(d + pd.Timedelta(days=4)) < len(idx) else pd.NaT
                   for d in wk.index]
    avail = avail[avail.index.notna()]
    avail = avail[~avail.index.duplicated(keep="last")]
    return avail.reindex(idx).ffill()


def mdd_forward(c, h):
    v = c.values
    out = np.full(len(v), np.nan)
    for i in range(len(v) - h):
        out[i] = v[i + 1:i + h + 1].min() / v[i] - 1
    return out


def episodes(sig):
    idx = np.where(sig)[0]
    out, last = [], -10 ** 9
    for i in idx:
        if i - last > GAP:
            out.append(i)
        last = i
    return np.array(out, dtype=int)


def spaced_random(k, pool):
    picks, tries = [], 0
    while len(picks) < k and tries < 50:
        cand = np.sort(rng.choice(pool, size=min(len(pool), k * 3), replace=False))
        last = -10 ** 9
        picks = []
        for i in cand:
            if i - last > GAP:
                picks.append(i)
                last = i
            if len(picks) >= k:
                break
        tries += 1
    return np.array(picks[:k])


def rate(m, ix, cut):
    return float((m[ix] <= cut).mean()) if len(ix) else np.nan


def boot_p(m, ix, pool, cut):
    s = rate(m, ix, cut)
    b = np.array([rate(m, spaced_random(len(ix), pool), cut) for _ in range(NBOOT)])
    return min(1.0, float(2 * min((b >= s).mean(), (b <= s).mean())))


def run(code, name, sym, vix):
    c = close(sym)
    wk = cftc(code)
    d = to_daily(wk, c.index)
    start = d.pos.first_valid_index()
    c, d = c[c.index >= start], d[d.index >= start]
    v = vix.reindex(c.index).ffill()
    V = (v >= v.rolling(20).mean() * 1.1).values
    ma50 = (c < c.rolling(50).mean()).values
    P1, P2, P3 = (d.pos >= 90).values, (d.pos <= 10).values, d.p3.fillna(False).astype(bool).values
    states = {
        "P1 포지션 위 끝 (≥90%)": P1, "P2 포지션 아래 끝 (≤10%)": P2, "P3 큰 매도 쪽 이동 (주간 하위 10%)": P3,
        "K1 위 끝 & VIX 상승": P1 & V, "K2 아래 끝 & VIX 상승": P2 & V, "K3 큰 매도 쪽 이동 & VIX 상승": P3 & V,
        "K4 위 끝 & VIX 상승 & 50일선 아래": P1 & V & ma50,
        "X1 대조 VIX 상승만": V, "X2 대조 VIX>25": (v > 25).values,
    }
    rows, notes = [], []
    for h, cut, lab in ((20, -0.05, "MDD20≤−5%"), (5, -0.03, "MDD5≤−3%")):
        m = mdd_forward(c, h)
        valid = np.where(~np.isnan(m))[0]
        first, second = valid[c.index[valid] < SPLIT], valid[c.index[valid] >= SPLIT]
        vpool = valid[V[valid]]
        base, b1, b2 = rate(m, valid, cut), rate(m, first, cut), rate(m, second, cut)
        vrate = rate(m, vpool, cut)
        notes.append(f"{name} ({sym}) {lab}: {c.index[0].date()} ~ · 날 {len(valid)} · 아무 날 {base:.1%} · VIX 상승 날 {vrate:.1%}")
        for st, sig in states.items():
            ep = episodes(sig)
            ep = ep[~np.isnan(m[ep])]
            if not len(ep):
                rows.append({"자": name, "결과": lab, "상태": st, "에피소드": 0, "판정": "신호 없음"})
                continue
            s = rate(m, ep, cut)
            p1 = boot_p(m, ep, valid, cut)
            isk = st.startswith("K")
            p2 = boot_p(m, ep, vpool, cut) if isk else np.nan
            e1, e2 = ep[c.index[ep] < SPLIT], ep[c.index[ep] >= SPLIT]
            f = rate(m, e1, cut) - b1 if len(e1) else np.nan
            g = rate(m, e2, cut) - b2 if len(e2) else np.nan
            same = not np.isnan(f) and not np.isnan(g) and np.sign(f) == np.sign(g) and f != 0
            ratio = s / base if base else np.nan
            vr = s / vrate if vrate else np.nan
            if len(ep) < 30:
                verdict = "표본 부족"
            elif isk:
                verdict = "두껍다 (통과)" if (p1 < 0.05 and p2 < 0.05 and same and ratio >= 1.25 and vr >= 1.25) else "VIX 상승 위에 더하는 것 없음"
            elif p1 < 0.05 and same and (ratio >= 1.25 or ratio <= 0.8):
                verdict = "두껍다 (통과)" if ratio >= 1.25 else "얇다 (반대로 통과)"
            else:
                verdict = "차이 없음"
            rows.append({"자": name, "결과": lab, "상태": st, "에피소드": len(ep), "신호 날": float(sig[valid].mean()), "비율": s,
                         "아무 날": base, "배": ratio, "p①": p1, "VIX 상승 날": vrate if isk else np.nan, "V 배": vr if isk else np.nan,
                         "p②": p2, "앞 절반 차": f, "뒤 절반 차": g, "판정": verdict})
    # 전조 — MDD20 ≤ −10% 급락 창 첫 날 직전 10일 안 켜짐
    m20 = mdd_forward(c, 20)
    valid = np.where(~np.isnan(m20))[0]
    crash = episodes(np.nan_to_num(m20, nan=0) <= -0.10)
    pre = []
    for st, sig in states.items():
        had = [sig[max(0, i - 10):i + 1].any() for i in crash]
        anyday = pd.Series(sig.astype(float)).rolling(11, min_periods=1).max().values[valid].mean()
        pre.append({"자": name, "상태": st, "급락 창": len(crash), "급락 전 켜짐": float(np.mean(had)) if len(crash) else np.nan, "아무 날 켜짐": float(anyday)})
    crash_days = [str(c.index[i].date()) for i in crash]
    return rows, pre, notes, crash_days, wk


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    vix = close("^VIX")
    R, P, N, C = [], [], [], []
    for code, name, sym in PAIRS:
        rows, pre, notes, crash, _wk = run(code, name, sym, vix)
        R += rows
        P += pre
        N += notes
        C.append(f"{name}: " + " · ".join(crash))
    df, pf = pd.DataFrame(R), pd.DataFrame(P)
    df.to_csv(os.path.join(OUT, "position_check.csv"), index=False)
    pct = lambda x: "—" if pd.isna(x) else f"{x:.1%}"   # noqa: E731
    pp = lambda x: "—" if pd.isna(x) else f"{x:+.1%}"   # noqa: E731
    f2 = lambda x, d=2: "—" if pd.isna(x) else f"{x:.{d}f}"   # noqa: E731
    L = [f"# 헤지펀드 선물 포지션 + VIX 상승 → 급락 검증 — 결과 (자동 생성, position_check.py, {datetime.date.today()})", "",
         "설계: 비공개 doc/검증/헤지펀드-포지션-급락-검증.md (결과 보기 전 고정)", "", *[f"- {x}" for x in N], "",
         "| 자 | 결과 | 상태 | 에피소드 | 신호 날 | 비율 | 아무 날 | 배 | p① | VIX 상승 날 | V 배 | p② | 앞 절반 차 | 뒤 절반 차 | 판정 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r['자']} | {r['결과']} | {r['상태']} | {r['에피소드']} | {pct(r.get('신호 날'))} | {pct(r.get('비율'))} | {pct(r.get('아무 날'))} | "
                 f"{f2(r.get('배'))} | {f2(r.get('p①'), 3)} | {pct(r.get('VIX 상승 날'))} | {f2(r.get('V 배'))} | {f2(r.get('p②'), 3)} | "
                 f"{pp(r.get('앞 절반 차'))} | {pp(r.get('뒤 절반 차'))} | {r['판정']} |")
    L += ["", "## 전조 확인 — 급락(MDD20 ≤ −10%) 창 첫 날 직전 10거래일 안에 켜져 있던 비율", "",
          "| 자 | 상태 | 급락 창 | 급락 전 켜짐 | 아무 날 켜짐 |", "|---|---|---|---|---|"]
    for _, r in pf.iterrows():
        L.append(f"| {r['자']} | {r['상태']} | {r['급락 창']} | {pct(r['급락 전 켜짐'])} | {pct(r['아무 날 켜짐'])} |")
    L += ["", "## 급락 창 첫 날", "", *[f"- {x}" for x in C]]
    open(os.path.join(OUT, "position_check.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
