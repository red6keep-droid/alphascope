"""실적 서프라이즈 뒤 — 좋은 실적은 그 뒤에도 이어지나 (doc/지표-우리검증-계획.md 5절, 결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/earnings_drift_check.py              # 검증 ("검증해" 때만)
    FC_SMOKE=1 .venv/bin/python experiments/issue_store/earnings_drift_check.py --out 스크래치   # 점검 (섞은 수익률)

사건 = data/store/calendar/earnings.csv 15종목, 발표 16:20(ET) → 반응일 = 다음 거래일, 진입 = 반응일 종가.
그룹: big_beat(크게 상회) · beat(상회) · inline(부합) · miss(하회) · streak4(이번 + 직전 3번 모두 상회 · 크게 상회).
잴 것: ret20 · ret60 · ret250(로그 수익률), s250(250일 뒤 종가 ≥ 진입 종가). 높을수록 좋음.
비교 = 같은 종목 · 시기 아무 날, 플라시보 = 사건 날짜 통째 원형 이동 2,000번 (종목 · 묶음).
결과: results/earnings_drift.csv · earnings_drift_pooled.csv
"""
import argparse
import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from failure_cost import MIN_N, N_DRAW, bar_frame, verdict_of
from normal_range import CAL, START, period_of

JUDGE_P = ["P3", "P4"]
METRICS = ["ret20", "ret60", "ret250", "s250"]
GROUPS = ["big_beat", "beat", "inline", "miss", "streak4"]
BEATS = {"크게 상회", "상회"}


def stock_table(sym, ev):
    b = bar_frame(sym)
    c = b.close.values.astype(float)
    idx = b.index
    n = len(c)
    f = {}
    for k in (20, 60, 250):
        r = np.full(n, np.nan)
        if n > k:
            r[:n - k] = np.log(c[k:] / c[:n - k])
        f[f"ret{k}"] = r
    s = np.full(n, np.nan)
    s[:n - 250] = (c[250:] >= c[:n - 250]).astype(float)
    df = pd.DataFrame({"t": idx, "period": [period_of(d) for d in idx], "ret20": f["ret20"], "ret60": f["ret60"],
                       "ret250": f["ret250"], "s250": s, "react": np.nan})
    e = ev[ev.symbol == sym].sort_values("day").reset_index(drop=True)
    for g in GROUPS:
        df[g] = False
    react_ret = {}
    streak = []
    bands = e.surprise_band.tolist()
    for i, (d, band) in enumerate(zip(pd.to_datetime(e.day), bands)):
        j = idx.searchsorted(d, side="right")           # 발표일 다음 거래일 (16:20 발표)
        if j >= n or not isinstance(band, str):
            streak.append(False)
            continue
        ok4 = i >= 3 and all(isinstance(x, str) and x in BEATS for x in bands[i - 3:i + 1])
        streak.append(ok4)
        grp = {"크게 상회": "big_beat", "상회": "beat", "부합": "inline", "하회": "miss"}.get(band)
        if grp:
            df.loc[j, grp] = True
        if ok4:
            df.loc[j, "streak4"] = True
        if j >= 1:
            react_ret[(grp, band)] = react_ret.get((grp, band), []) + [c[j] / c[j - 1] - 1]
    df = df[(df.period.isin(JUDGE_P)) & (idx >= START) & np.isfinite(df.ret20.values)].reset_index(drop=True)
    return df, react_ret


def stat(v, m):
    return np.nanmean(v) if m == "s250" else np.nanmedian(v)


def run(out):
    rng = np.random.default_rng(53)
    ev = pd.read_csv(os.path.join(CAL, "earnings.csv"))
    ev = ev[ev.symbol.isin(STOCKS)]
    T, react = {}, {}
    for s in STOCKS:
        T[s], r = stock_table(s, ev)
        for k, v in r.items():
            react.setdefault(k, []).extend(v)
    rows, src = [], {}
    for s, d in T.items():
        for per, g in d.groupby("period"):
            g = g.sort_values("t")
            for grp in GROUPS:
                pos = np.flatnonzero(g[grp].values)
                for m in METRICS:
                    pv = g[m].values
                    v = pv[pos]
                    nv = int(np.isfinite(v).sum())
                    row = {"symbol": s, "group": grp, "period": per, "metric": m, "n": nv,
                           "value": float(stat(v, m)) if nv else np.nan, "anyday": float(stat(pv, m))}
                    if nv:
                        if nv < MIN_N:
                            row["verdict"] = "표본 부족"
                        else:
                            sh = rng.integers(1, len(pv), size=N_DRAW)
                            dd = pv[(pos[None, :] + sh[:, None]) % len(pv)]
                            fn = np.nanmean if m == "s250" else np.nanmedian
                            row["q"], row["verdict"] = verdict_of(row["value"], fn(dd, axis=1))
                        src.setdefault((grp, per, m), []).append((g.t.values, pv, g.t.values[pos], row["value"], row["anyday"]))
                    rows.append(row)
    S = pd.DataFrame(rows)
    P = []
    for (grp, per, m), lst in src.items():
        days = pd.DatetimeIndex(sorted(set().union(*[set(t) for t, *_ in lst])))
        L = len(days)
        V = np.vstack([pd.Series(pv, index=pd.DatetimeIndex(t)).reindex(days).values for t, pv, *_ in lst])
        si = np.concatenate([np.full(len(ev_), i) for i, (_, _, ev_, _, _) in enumerate(lst)])
        di = np.concatenate([days.get_indexer(pd.DatetimeIndex(ev_)) for _, _, ev_, _, _ in lst])
        ev_vals = V[si, di]
        nv = int(np.isfinite(ev_vals).sum())
        base = float(stat(V[np.isfinite(V)], m))
        if nv < MIN_N:
            P.append({"group": grp, "period": per, "metric": m, "n": nv, "stocks": len(lst), "verdict": "표본 부족"})
            continue
        sh = rng.integers(1, L, size=N_DRAW)
        fn = np.nanmean if m == "s250" else np.nanmedian
        meds = fn(V[si[None, :], (di[None, :] + sh[:, None]) % L], axis=1)
        val = float(stat(ev_vals, m))
        q, vd = verdict_of(val, meds)
        want = 1 if vd == "특히 좋음" else -1 if vd == "특히 나쁨" else 0
        sides = [np.sign(a - b) for _, _, e_, a, b in lst if len(e_) and np.isfinite(a)]
        agree = float(np.mean([x == want for x in sides]) * 100) if want else np.nan
        P.append({"group": grp, "period": per, "metric": m, "n": nv, "stocks": len(lst), "value": val, "anyday": base, "q": q,
                  "verdict": vd, "agree_pct": agree, "even": vd in ("특히 나쁨", "특히 좋음") and agree > 50})
    P = pd.DataFrame(P)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, "earnings_drift.csv"), index=False)
    P.to_csv(os.path.join(out, "earnings_drift_pooled.csv"), index=False)
    chk = pd.DataFrame([{"band": b, "n": len(v), "reaction_day_median_pct": float(np.median(v) * 100)} for (g, b), v in react.items()])
    chk.to_csv(os.path.join(out, "earnings_drift_reaction_check.csv"), index=False)
    return S, P, chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P, chk = run(a.out)
    print(f"저장: {a.out}/earnings_drift*.csv · 종목 칸 {len(S)} · 묶음 칸 {len(P)}")
    print(chk.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
