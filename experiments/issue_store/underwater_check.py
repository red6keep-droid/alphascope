"""물림 검증 — doc/지표-우리검증-계획.md 3절 (결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/underwater_check.py              # 검증 ("검증해" 때만)
    FC_SMOKE=1 .venv/bin/python experiments/issue_store/underwater_check.py --out 스크래치   # 점검 (섞은 수익률)

산 날(종가) 다섯 종류: any · high52(종가 ≥ 252일 최고의 97%) · daily_low(종가 ≤ 20일 평균 − 2σ) · weekly_low(20주 밴드 하단, 주 마지막 거래일) · deep(종가 ≤ 252일 최고의 75%).
처음 들어간 날, 재무장 20거래일(주봉 4주). 잴 것: s120 · s250(N일 뒤 종가 ≥ 산 날 종가), above250(250일 중 종가 ≥ 산 날 종가인 날 비율), ret250(로그 수익률).
높을수록 덜 물림. 비교 = 같은 종목 × 시기 아무 날, 플라시보 = 원형 이동 2,000번(종목 · 15종목 묶음), P3 · P4 같은 쪽만.
결과: results/underwater.csv · underwater_pooled.csv
"""
import argparse
import os

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from bollinger_by_stock import STOCKS
from failure_cost import MIN_N, N_DRAW, bar_frame, verdict_of
from indicator_check import REARM, first_entries
from normal_range import START, period_of

H = 250
JUDGE_P = ["P3", "P4"]
METRICS = ["s120", "s250", "above250", "ret250"]
GROUPS = ["any", "high52", "daily_low", "weekly_low", "deep"]


def stock_table(sym):
    b = bar_frame(sym)
    c = b.close.values.astype(float)
    idx = b.index
    cs = pd.Series(c, index=idx)
    n = len(c)
    # 산 뒤 경로 값
    s120 = np.full(n, np.nan)
    s250 = np.full(n, np.nan)
    ab = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    if n > H + 1:
        s120[:n - 120] = (c[120:] >= c[:n - 120]).astype(float)
        s250[:n - H] = (c[H:] >= c[:n - H]).astype(float)
        win = sliding_window_view(c[1:], H)[:n - H]          # t+1 .. t+H
        ab[:n - H] = (win >= c[:n - H, None]).mean(axis=1)
        ret[:n - H] = np.log(c[H:] / c[:n - H])
    hi = cs.rolling(252, min_periods=252).max().values
    ma, sd = cs.rolling(20).mean(), cs.rolling(20).std()
    sigs = {
        "high52": first_entries(c >= 0.97 * hi),
        "daily_low": first_entries((cs <= ma - 2 * sd).values),
        "deep": first_entries(c <= 0.75 * hi),
    }
    # 주봉 하단 — 주 마지막 거래일 종가로 20주 밴드
    last = pd.Series(idx, index=idx).resample("W-FRI").last().dropna()
    wk = cs.loc[last.values]
    wma, wsd = wk.rolling(20).mean(), wk.rolling(20).std()
    low = (wk <= wma - 2 * wsd).values
    sw = np.zeros(len(wk), bool)
    lastk = -10 ** 9
    for k in np.flatnonzero(low & ~np.concatenate([[False], low[:-1]])):
        if k - lastk > 4:
            sw[k], lastk = True, k
    wsig = np.zeros(n, bool)
    wsig[idx.get_indexer(pd.DatetimeIndex(last.values)[sw])] = True
    sigs["weekly_low"] = wsig
    ok = (idx >= START) & np.isfinite(hi) & np.isfinite(s250)
    per = np.array([period_of(d) for d in idx], dtype=object)
    df = pd.DataFrame({"t": idx, "period": per, "ok": ok, "s120": s120, "s250": s250, "above250": ab, "ret250": ret})
    df["any"] = True
    for g, v in sigs.items():
        df[g] = v
    return df[df.ok & df.period.isin(JUDGE_P)].reset_index(drop=True)


def stat(v, m):
    return np.nanmedian(v) if m == "ret250" else np.nanmean(v)


def run(out):
    rng = np.random.default_rng(31)
    T = {s: stock_table(s) for s in STOCKS}
    rows, src = [], {}
    for s, d in T.items():
        for per, g in d.groupby("period"):
            g = g.sort_values("t")
            for grp in GROUPS:
                pos = np.flatnonzero(g[grp].values)
                for m in METRICS:
                    pv = g[m].values
                    v = pv[pos]
                    row = {"symbol": s, "group": grp, "period": per, "metric": m, "n": len(v),
                           "value": float(stat(v, m)) if len(v) else np.nan, "anyday": float(stat(pv, m))}
                    if grp != "any" and len(v):
                        if len(v) < MIN_N:
                            row["verdict"] = "표본 부족"
                        else:
                            sh = rng.integers(1, len(pv), size=N_DRAW)
                            dd = pv[(pos[None, :] + sh[:, None]) % len(pv)]
                            f = np.nanmedian if m == "ret250" else np.nanmean
                            row["q"], row["verdict"] = verdict_of(row["value"], f(dd, axis=1))
                        src.setdefault((grp, per, m), []).append((g.t.values, pv, g.t.values[pos], row["value"], row["anyday"]))
                    rows.append(row)
    S = pd.DataFrame(rows)
    P = []
    for (grp, per, m), lst in src.items():
        days = pd.DatetimeIndex(sorted(set().union(*[set(t) for t, *_ in lst])))
        L = len(days)
        V = np.vstack([pd.Series(pv, index=pd.DatetimeIndex(t)).reindex(days).values for t, pv, *_ in lst])
        si = np.concatenate([np.full(len(ev), i) for i, (_, _, ev, _, _) in enumerate(lst)])
        di = np.concatenate([days.get_indexer(pd.DatetimeIndex(ev)) for _, _, ev, _, _ in lst])
        n = len(di)
        base = float(stat(V[~np.isnan(V)], m))
        if n < MIN_N:
            P.append({"group": grp, "period": per, "metric": m, "n": n, "stocks": len(lst), "verdict": "표본 부족"})
            continue
        ev = V[si, di]
        sh = rng.integers(1, L, size=N_DRAW)
        f = np.nanmedian if m == "ret250" else np.nanmean
        meds = f(V[si[None, :], (di[None, :] + sh[:, None]) % L], axis=1)
        val = float(stat(ev, m))
        q, vd = verdict_of(val, meds)
        want = 1 if vd == "특히 좋음" else -1 if vd == "특히 나쁨" else 0
        sides = [np.sign(a - b) for _, _, e, a, b in lst if len(e)]
        agree = float(np.mean([x == want for x in sides]) * 100) if want else np.nan
        P.append({"group": grp, "period": per, "metric": m, "n": n, "stocks": len(lst), "value": val, "anyday": base,
                  "q": q, "verdict": vd, "agree_pct": agree, "even": vd in ("특히 나쁨", "특히 좋음") and agree > 50})
    P = pd.DataFrame(P)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, "underwater.csv"), index=False)
    P.to_csv(os.path.join(out, "underwater_pooled.csv"), index=False)
    return S, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P = run(a.out)
    print(f"저장: {a.out}/underwater*.csv · 종목 칸 {len(S)} · 묶음 칸 {len(P)}")


if __name__ == "__main__":
    main()
