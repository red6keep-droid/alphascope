"""파동 주기는 이어지는가 — 1단계 (doc/검증/볼린저-이슈별-검증-계획.md 4-13, 결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/cycle_persistence.py                    # 검증 ("검증해" 때만)
    FC_SMOKE=1 .venv/bin/python experiments/issue_store/cycle_persistence.py --out 스크래치   # 점검 (진짜도 섞은 자료)

바닥 = 종가가 앞뒤 k 거래일 안에서 가장 낮은 날 (k = 3 · 5 · 10). 주기 = 이어진 바닥 사이 거래일 수.
① 이웃 주기 스피어만 상관 ② 그 전 60거래일 안에 끝난 주기(2개 이상) 중앙값으로 다음 주기 예측, |실제 − 예측| ÷ 실제 중앙값.
비교 = 같은 종목 · 시기 로그 수익률을 섞은 가짜 주가 200개. 진짜가 95% 보다 나으면 "이어짐". 15종목 평균도 가짜 200 세트.
결과: results/cycle_persistence.csv · _pooled.csv
"""
import argparse
import os

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from bollinger_by_stock import STOCKS
from failure_cost import bar_frame
from normal_range import PERIODS

KS = [3, 5, 10]
LOOK = 60
N_SUR = 200


def lows(lc, k):
    w = sliding_window_view(lc, 2 * k + 1).min(axis=1)
    i = np.arange(k, len(lc) - k)
    return i[lc[k:len(lc) - k] <= w + 1e-12]


def rank(x):
    return pd.Series(x).rank().values


def metrics(lc, k):
    L = lows(lc, k)
    cyc = np.diff(L)
    if len(cyc) < 10:
        return np.nan, np.nan, len(cyc)
    rho = np.corrcoef(rank(cyc[:-1]), rank(cyc[1:]))[0, 1]
    errs = []
    for j in range(1, len(L) - 1):
        # 바닥 L[j] 에서: 그 전 60거래일 안에 끝난 주기 = 끝 바닥 L[m] (m ≤ j) 가 L[j] − 60 이후
        ends = np.flatnonzero((L[1:j + 1] >= L[j] - LOOK))
        past = cyc[ends]
        if len(past) >= 2:
            p = np.median(past)
            a = L[j + 1] - L[j]
            errs.append(abs(a - p) / a)
    return rho, (np.median(errs) if errs else np.nan), len(cyc)


def run(out):
    rng = np.random.default_rng(23)
    rows, pool = [], {}
    for s in STOCKS:
        b = bar_frame(s)
        c = b.close.values.astype(float)
        for name, a, z in PERIODS:
            m = (b.index >= a) & (b.index <= z)
            if m.sum() < 500:
                continue
            r = np.diff(np.log(c[m]))
            lc = np.concatenate([[0], np.cumsum(r)])
            for k in KS:
                rho, err, n = metrics(lc, k)
                sur = np.array([metrics(np.concatenate([[0], np.cumsum(rng.permutation(r))]), k)[:2] for _ in range(N_SUR)])
                q_rho = float(np.nanmean(sur[:, 0] < rho)) if np.isfinite(rho) else np.nan
                q_err = float(np.nanmean(sur[:, 1] > err)) if np.isfinite(err) else np.nan
                rows.append({"symbol": s, "period": name, "k": k, "cycles": n, "rho": rho, "sur_rho_med": float(np.nanmedian(sur[:, 0])),
                             "q_rho": q_rho, "err": err, "sur_err_med": float(np.nanmedian(sur[:, 1])), "q_err": q_err,
                             "rho_pass": q_rho >= 0.95, "err_pass": q_err >= 0.95,
                             "cycle_med": float(np.median(np.diff(lows(lc, k))))})
                pool.setdefault((name, k), []).append((rho, err, sur))
    S = pd.DataFrame(rows)
    P = []
    for (name, k), lst in pool.items():
        rho_m = np.nanmean([x[0] for x in lst])
        err_m = np.nanmean([x[1] for x in lst])
        sur_rho = np.nanmean(np.vstack([x[2][:, 0] for x in lst]), axis=0)
        sur_err = np.nanmean(np.vstack([x[2][:, 1] for x in lst]), axis=0)
        P.append({"period": name, "k": k, "stocks": len(lst), "rho": rho_m, "sur_rho_med": float(np.median(sur_rho)),
                  "q_rho": float(np.mean(sur_rho < rho_m)), "err": err_m, "sur_err_med": float(np.median(sur_err)),
                  "q_err": float(np.mean(sur_err > err_m))})
    P = pd.DataFrame(P)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, "cycle_persistence.csv"), index=False)
    P.to_csv(os.path.join(out, "cycle_persistence_pooled.csv"), index=False)
    return S, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P = run(a.out)
    print(P.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
