"""흔들림 회복 일수 — doc/평소-범위-검증-계획.md 8절 (결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/normal_range_recovery.py

기준 = 충격 시작일 직전까지 252일 표준편차(실적일 제외). 회복 = 시작 뒤 EWMA σ ≤ 기준 × 1.25 첫 거래일까지 일수
(500 넘으면 '500 넘음'), 첫 20거래일 안에 1.25 배를 안 넘으면 '부풀지 않음'. 정점 배수 = 60거래일 EWMA 최대 ÷ 기준.
결과: results/normal_range_recovery.md · .csv
"""

import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from normal_range import OUT, START, earnings_days, load_close, market_shock, prepare

K, CAP, SWELL, PEAK = 1.25, 500, 20, 60


def episodes(P):
    idx, m = P["r"].index, P["mshock"].values
    out = [(i, "시장") for i in range(1, len(idx)) if m[i] and not m[i - 1] and idx[i] >= START]
    out += [(i, "종목") for i in np.flatnonzero(P["trig"].values)
            if idx[i] >= START and not (i > 0 and P["sshock"].values[i - 1])]
    return sorted(out)


def run_stock(sym):
    c = load_close(sym)
    idx = c.index
    r = np.log(c).diff()
    edays, _ = earnings_days(sym, idx)
    P = prepare(r, pd.Series(idx.isin(list(edays)), index=idx), market_shock(idx))
    e, base_s = P["sd"]["ewma"].values, P["s252"].values
    rows = []
    for i, kind in episodes(P):
        base = base_s[i]
        if not np.isfinite(base) or base <= 0:
            continue
        seg = e[i + 1:i + 1 + CAP + 1]
        peak = float(np.nanmax(e[i + 1:i + 1 + PEAK]) / base) if i + 1 < len(e) else np.nan
        swelled = bool(np.nanmax(e[i + 1:i + 1 + SWELL]) > K * base) if i + 1 < len(e) else False
        if not swelled:
            rec = "부풀지 않음"
        else:
            j = np.flatnonzero(seg <= K * base)
            # 부푼 뒤에 돌아온 첫날
            first_up = int(np.flatnonzero(seg > K * base)[0])
            j = j[j > first_up]
            rec = int(j[0]) + 1 if len(j) else ("진행 중" if i + 1 + CAP >= len(e) else "500 넘음")
        rows.append({"symbol": sym, "start": idx[i].date(), "kind": kind, "base_daily_sd": round(float(base), 4),
                     "peak_x": round(peak, 2), "recovery_days": rec})
    return rows


def main():
    D = pd.DataFrame([row for s in STOCKS for row in run_stock(s)])
    D.to_csv(os.path.join(OUT, "normal_range_recovery.csv"), index=False)
    D["rec"] = pd.to_numeric(D.recovery_days, errors="coerce")
    L = ["# 흔들림 회복 일수 (충격 뒤 EWMA 가 직전 1년 수준 × 1.25 안으로 돌아오기까지)", "",
         "계획: doc/평소-범위-검증-계획.md 8절. 흔들림 회복이지 주가 회복이 아님.", "",
         "| 종목 | 종류 | 충격 수 | 부풀지 않음 | 회복 중앙값(일) | 사분위 25 ~ 75 | 500 넘음 · 진행 중 | 정점 배수 중앙값 |",
         "|---|---|---|---|---|---|---|---|"]
    for (sym, kind), g in D.groupby(["symbol", "kind"], sort=False):
        r = g.rec.dropna()
        L.append(f"| {sym} | {kind} | {len(g)} | {(g.recovery_days == '부풀지 않음').sum()} | "
                 f"{r.median():.0f} | {r.quantile(.25):.0f} ~ {r.quantile(.75):.0f} | "
                 f"{g.recovery_days.isin(['500 넘음', '진행 중']).sum()} | {g.peak_x.median():.2f} |" if len(r) else
                 f"| {sym} | {kind} | {len(g)} | {(g.recovery_days == '부풀지 않음').sum()} | - | - | - | {g.peak_x.median():.2f} |")
    L += ["", "## 시장 충격별 (15종목 회복 일수 중앙값 · 정점 배수 중앙값)", "", "| 시작 | 회복 중앙값 | 정점 배수 | 부풀지 않음 |", "|---|---|---|---|"]
    M = D[D.kind == "시장"]
    for st, g in M.groupby("start"):
        L.append(f"| {st} | {g.rec.median():.0f} | {g.peak_x.median():.2f} | {(g.recovery_days == '부풀지 않음').sum()}/{len(g)} |")
    with open(os.path.join(OUT, "normal_range_recovery.md"), "w") as f:
        f.write("\n".join(L))
    print(open(os.path.join(OUT, "normal_range_recovery.md")).read())


if __name__ == "__main__":
    main()
