"""C9 — 매일 바뀌는 범위(EWMA)가 고정 범위보다 나은가 (doc/리포트-재설계/평소-범위-검증-계획.md 7절, 결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/normal_range_skill.py

B1 = 지난 252일 표준편차, B3 = P3 평소 날(실적 · 충격 제외) 고정 표준편차를 P4 에 그대로.
점수 QLIKE L = ln V + R²/V (V = h·σ²). Diebold-Mariano (Newey-West 지연 h=1 → 10, h≥5 → 2).
결과: results/normal_range_skill.md · .csv
"""

import math
import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from normal_range import (HZ, OUT, START, earnings_days, load_close, market_shock, period_of, prepare)

SETS = {"평소만": ("normal",), "충격 포함": ("normal", "shock")}


def nw_p(d, lag):
    d = np.asarray(d, float)
    n = len(d)
    if n < 30:
        return float("nan"), float("nan")
    m = d.mean()
    e = d - m
    v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    se = math.sqrt(max(v, 1e-18) / n)
    t = m / se
    return m, math.erfc(abs(t) / math.sqrt(2))


def run_stock(sym):
    c = load_close(sym)
    idx = c.index
    r = np.log(c).diff()
    edays, _ = earnings_days(sym, idx)
    earn = pd.Series(idx.isin(list(edays)), index=idx)
    P = prepare(r, earn, market_shock(idx))
    r_in = r.where(~earn)
    p3 = (idx >= pd.Timestamp("2010-01-01")) & (idx <= pd.Timestamp("2019-12-31"))
    b3 = float(r_in[p3 & ~P["shock"].values].std())
    sd = {"ewma": P["sd"]["ewma"], "b1": P["s252"], "b3": pd.Series(b3, index=idx)}
    rows = []
    for h in HZ:
        ok = (idx >= START) & sd["ewma"].notna().values & sd["b1"].notna().values
        first = np.flatnonzero(ok)[0]
        for t in range(first - 1, len(idx) - h, h):
            a, b = t + 1, t + 1 + h
            if P["earn"].values[a:b].any():
                continue
            per = period_of(idx[a])
            if per not in ("P3", "P4"):
                continue
            R = float(np.nansum(r.values[a:b]))
            row = {"symbol": sym, "h": h, "period": per, "bucket": "shock" if P["shock"].values[a:b].any() else "normal"}
            for k, s in sd.items():
                V = h * float(s.values[a]) ** 2
                row[f"L_{k}"] = math.log(V) + R * R / V
                row[f"z_{k}"] = R / math.sqrt(V)
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    W = pd.concat([run_stock(s) for s in STOCKS])
    res = []
    for (sym, h), g0 in W.groupby(["symbol", "h"]):
        lag = 10 if h == 1 else 2
        for setname, bks in SETS.items():
            g = g0[g0.bucket.isin(bks)]
            row = {"symbol": sym, "h": h, "set": setname}
            for base in ("b1", "b3"):
                for per in ("P3", "P4"):
                    if base == "b3" and per == "P3":
                        continue
                    s = g[g.period == per]
                    m, p = nw_p(s["L_ewma"] - s[f"L_{base}"], lag)
                    row[f"{base}_{per}_d"], row[f"{base}_{per}_p"], row[f"{base}_{per}_n"] = m, p, len(s)
            def verdict(keys):
                ds = [row[f"{k}_d"] for k in keys]
                ps = [row[f"{k}_p"] for k in keys]
                if any(not np.isfinite(x) for x in ds + ps):
                    return "표본 부족"
                if all(d < 0 for d in ds) and all(p < 0.05 for p in ps):
                    return "매일 범위가 낫다"
                if all(d > 0 for d in ds) and all(p < 0.05 for p in ps):
                    return "고정이 낫다"
                return "차이 없음"
            row["vs_b1"] = verdict(["b1_P3", "b1_P4"])
            row["vs_b3"] = verdict(["b3_P4"])
            p4 = g[g.period == "P4"]
            for k in ("ewma", "b1", "b3"):
                row[f"in1_{k}"] = round(float((p4[f"z_{k}"].abs() < 1).mean()), 3)
                row[f"out2_{k}"] = round(float((p4[f"z_{k}"].abs() > 2).mean()), 3)
            res.append(row)
    R = pd.DataFrame(res)
    R.to_csv(os.path.join(OUT, "normal_range_skill.csv"), index=False)
    L = ["# C9 — 매일 바뀌는 범위(EWMA) vs 고정 범위", "",
         "계획: doc/리포트-재설계/평소-범위-검증-계획.md 7절. B1 = 지난 1년, B3 = 2010년대 고정을 2020년대에. QLIKE · Diebold-Mariano.", ""]
    for setname in SETS:
        for base, lab in (("vs_b1", "B1 지난 1년 대비 (P3 · P4 둘 다)"), ("vs_b3", "B3 2010년대 고정 대비 (P4)")):
            L += [f"## {setname} · {lab}", "", "| 종목 | " + " | ".join(f"{h}일" for h in HZ) + " |", "|---|" + "---|" * len(HZ)]
            for sym in STOCKS:
                cells = []
                for h in HZ:
                    v = R[(R.symbol == sym) & (R.h == h) & (R.set == setname)]
                    cells.append(v[base].iloc[0] if len(v) else "-")
                L.append(f"| {sym} | " + " | ".join(cells) + " |")
            L.append("")
            L.append("합계: " + ", ".join(f"{h}일 " + " · ".join(f"{k} {n}" for k, n in
                     R[(R.set == setname) & (R.h == h)][base].value_counts().items()) for h in HZ))
            L.append("")
    L += ["## P4 보정 참고 (평소만, 1일 · 10일): ±1σ 안 / ±2σ 밖", "", "| 종목 | h | EWMA | B1 | B3 |", "|---|---|---|---|---|"]
    for r in R[(R.set == "평소만") & (R.h.isin([1, 10]))].itertuples():
        L.append(f"| {r.symbol} | {r.h} | {r.in1_ewma:.0%} / {r.out2_ewma:.1%} | {r.in1_b1:.0%} / {r.out2_b1:.1%} | {r.in1_b3:.0%} / {r.out2_b3:.1%} |")
    with open(os.path.join(OUT, "normal_range_skill.md"), "w") as f:
        f.write("\n".join(L))
    print("저장:", os.path.join(OUT, "normal_range_skill.md"))


if __name__ == "__main__":
    main()
