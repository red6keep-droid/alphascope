"""지표 우리 검증 — doc/지표-우리검증-계획.md (결과 보기 전 고정). 4단계 W8.

    .venv/bin/python experiments/issue_store/indicator_check.py overheat              # 검증 ("검증해" 때만)
    FC_SMOKE=1 .venv/bin/python experiments/issue_store/indicator_check.py overheat --out 스크래치   # 점검 (섞은 수익률)

공통: 15종목 30년, 신호 = 조건에 처음 들어간 날(같은 조건 다음 진입은 20거래일 뒤부터), 진입 = 신호 날 종가(주) · 다음 날 시가(참고).
잴 것 N = 20 · 60: 그 뒤 로그 수익률 · MAE ÷ (지난 252일 σ × √N). 비교 = 같은 종목 × 시기 아무 날.
플라시보 = 원형 이동 2,000번 (종목 · 15종목 묶음), P3 · P4 둘 다 같은 쪽만, 사건 < 20 표본 부족.
결과: results/indicator_<이름>.csv · _pooled.csv
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from failure_cost import MIN_N, N_DRAW, bar_frame, verdict_of
from normal_range import START, period_of

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nvda-report"))
import config as nvda_config  # noqa: E402  — 리포트와 같은 경계값

NS = [20, 60]
JUDGE_P = ["P3", "P4"]
REARM = 20


def rsi_wilder(c, n=14):
    d = np.diff(c, prepend=np.nan)
    g, l = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    ag, al = g[1:n + 1].mean(), l[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + l[i]) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def conditions_overheat(c):
    cs = pd.Series(c)
    ma200 = cs.rolling(200).mean().values
    ret20 = (cs / cs.shift(20) - 1).values * 100
    return {"rsi80": rsi_wilder(c) >= nvda_config.OVERHEAT_RSI,
            "ma200_40": (c / ma200 - 1) * 100 >= nvda_config.OVERHEAT_MA200_PCT,
            "ret20_25": ret20 >= nvda_config.OVERHEAT_RET20_PCT}


def conditions_rsi(c):
    r = rsi_wilder(c, nvda_config.RSI_PERIOD)
    return {"rsi70": r >= 70, "rsi30": r <= 30}


def conditions_cross(c):
    cs = pd.Series(c)
    s, l = cs.rolling(nvda_config.MA_SHORT).mean().values, cs.rolling(nvda_config.MA_LONG).mean().values
    above = s > l
    ok = np.isfinite(s) & np.isfinite(l)
    prev = np.concatenate([[False], above[:-1]])
    prev_ok = np.concatenate([[False], ok[:-1]])
    return {"golden": ok & prev_ok & above & ~prev, "dead": ok & prev_ok & ~above & prev}


INDICATORS = {"overheat": conditions_overheat, "rsi": conditions_rsi, "cross": conditions_cross}


def first_entries(cond):
    cond = np.nan_to_num(cond.astype(float), nan=0).astype(bool)
    sig, last = np.zeros(len(cond), bool), -10 ** 9
    for t in np.flatnonzero(cond & ~np.concatenate([[False], cond[:-1]])):
        if t - last > REARM:
            sig[t], last = True, t
    return sig


def stock_table(sym, name):
    b = bar_frame(sym)
    c, o, idx = b.close.values.astype(float), b.open.values.astype(float), b.index
    conds = INDICATORS[name](c)
    if name == "overheat":
        conds["any"] = np.logical_or.reduce([np.nan_to_num(v.astype(float), nan=0).astype(bool) for v in conds.values()])
    sigs = {k: first_entries(v) for k, v in conds.items()}
    r = np.log(pd.Series(c)).diff()
    s252 = r.rolling(252, min_periods=200).std().shift(1).values
    rows = []
    for t in range(len(c)):
        if idx[t] < START or not np.isfinite(s252[t]):
            continue
        for ex in ("close", "open"):
            e = t if ex == "close" else t + 1
            if e >= len(c) or not (c[e] if ex == "close" else o[e]) > 0:
                continue
            p = c[e] if ex == "close" else o[e]
            for N in NS:
                E = t + N
                if E >= len(c):
                    continue
                seg = c[(e + 1 if ex == "close" else e):E + 1]
                rows.append([idx[t], period_of(idx[t]), ex, N, np.log(c[E] / p), np.log(seg.min() / p) / (s252[t] * np.sqrt(N))]
                            + [bool(sigs[k][t]) for k in sigs])
    return pd.DataFrame(rows, columns=["t", "period", "exec", "N", "ret", "mae_z"] + [f"sig_{k}" for k in sigs])


def run(name, out):
    rng = np.random.default_rng(17)
    T = {s: stock_table(s, name) for s in STOCKS}
    sig_cols = [c for c in next(iter(T.values())).columns if c.startswith("sig_")]
    rows, src = [], {}
    for s, d in T.items():
        for (per, ex, N), g in d.groupby(["period", "exec", "N"]):
            g = g.sort_values("t")
            for sc in sig_cols:
                pos = np.flatnonzero(g[sc].values)
                for m in ("ret", "mae_z"):
                    pv = g[m].values
                    v = pv[pos]
                    row = {"symbol": s, "cond": sc[4:], "period": per, "exec": ex, "N": N, "metric": m, "n": len(v),
                           "median": float(np.median(v)) if len(v) else np.nan, "anyday_median": float(np.median(pv))}
                    if per in JUDGE_P and len(v):
                        if len(v) < MIN_N:
                            row["verdict"] = "표본 부족"
                        else:
                            sh = rng.integers(1, len(pv), size=N_DRAW)
                            row["q"], row["verdict"] = verdict_of(np.median(v), np.median(pv[(pos[None, :] + sh[:, None]) % len(pv)], axis=1))
                        src.setdefault((sc[4:], per, ex, N, m), []).append((g.t.values, pv, g.t.values[pos], row["median"], row["anyday_median"]))
                    rows.append(row)
    S = pd.DataFrame(rows)
    P = []
    for (cond, per, ex, N, m), lst in src.items():
        days = pd.DatetimeIndex(sorted(set().union(*[set(t) for t, *_ in lst])))
        L = len(days)
        V = np.vstack([pd.Series(pv, index=pd.DatetimeIndex(t)).reindex(days).values for t, pv, *_ in lst])
        si = np.concatenate([np.full(len(ev), i) for i, (_, _, ev, _, _) in enumerate(lst)])
        di = np.concatenate([days.get_indexer(pd.DatetimeIndex(ev)) for _, _, ev, _, _ in lst])
        n = len(di)
        if n < MIN_N:
            P.append({"cond": cond, "period": per, "exec": ex, "N": N, "metric": m, "n": n, "stocks": len(lst), "verdict": "표본 부족"})
            continue
        ev = V[si, di]
        sh = rng.integers(1, L, size=N_DRAW)
        meds = np.nanmedian(V[si[None, :], (di[None, :] + sh[:, None]) % L], axis=1)
        q, vd = verdict_of(np.nanmedian(ev), meds)
        want = 1 if vd == "특히 좋음" else -1 if vd == "특히 나쁨" else 0
        sides = [np.sign(a - b) for _, _, e, a, b in lst if len(e)]
        agree = float(np.mean([x == want for x in sides]) * 100) if want else np.nan
        P.append({"cond": cond, "period": per, "exec": ex, "N": N, "metric": m, "n": n, "stocks": len(lst),
                  "median": float(np.nanmedian(ev)), "anyday": float(np.nanmedian(meds)), "q": q, "verdict": vd, "agree_pct": agree,
                  "even": vd in ("특히 나쁨", "특히 좋음") and agree > 50})
    P = pd.DataFrame(P)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, f"indicator_{name}.csv"), index=False)
    P.to_csv(os.path.join(out, f"indicator_{name}_pooled.csv"), index=False)
    return S, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=list(INDICATORS))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P = run(a.name, a.out)
    print(f"저장: {a.out}/indicator_{a.name}*.csv · 종목 칸 {len(S)} · 묶음 칸 {len(P)}")


if __name__ == "__main__":
    main()
