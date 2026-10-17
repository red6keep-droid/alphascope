"""분할 매수 검증 — doc/지표-우리검증-계획.md 4절 (결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/split_buy_check.py              # 검증 ("검증해" 때만)
    FC_SMOKE=1 .venv/bin/python experiments/issue_store/split_buy_check.py --out 스크래치   # 점검 (섞은 수익률)

시기 안 매달 한 번 같은 금액: A 그 달 첫 거래일 · B 그 달 처음 종가 ≤ 20일 평균 − 2σ 인 날(없으면 마지막 거래일) · C 그 달 아무 날(플라시보).
r = mean(1 / 산 가격) ÷ A 의 mean(1 / 산 가격) − 1 (같은 끝 가격이므로 1달러당 최종 가치 차이). B 의 r 이 "대기 일수를 달끼리 섞은" 플라시보(대기 시간 맞춤, 계획 4절 수정)의 상위 5% 밖이면 특히 좋음.
묶음은 같은 달 순열을 모든 종목에 공통으로 적용해 같은 날 몰림을 보존.
결과: results/split_buy.csv · split_buy_pooled.csv
"""
import argparse
import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from failure_cost import N_DRAW, bar_frame, verdict_of
from normal_range import PERIODS

JUDGE_P = {"P3": ("2010-01-01", "2019-12-31"), "P4": ("2020-01-01", "2099-12-31")}


def stock_months(sym):
    b = bar_frame(sym)
    c = b.close
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    low = (c <= ma - 2 * sd).values
    out = {}
    for per, (a, z) in JUDGE_P.items():
        m = (c.index >= a) & (c.index <= z)
        idx = np.flatnonzero(m)
        if len(idx) < 300:
            continue
        key = c.index[idx].year * 12 + c.index[idx].month
        months = []
        for k in np.unique(key):
            pos = idx[key == k]
            months.append((int(k), pos))
        out[per] = (c.values.astype(float), low, months)
    return out


def positions(months, low):
    A = np.array([p[0] for _, p in months])
    B, touched, wait = [], 0, []
    for _, p in months:
        hit = np.flatnonzero(low[p])
        if len(hit):
            B.append(p[hit[0]]); touched += 1; wait.append(int(hit[0]))
        else:
            B.append(p[-1]); wait.append(len(p) - 1)
    return A, np.array(B), touched / len(months), float(np.mean(wait))


def run(out):
    rng = np.random.default_rng(41)
    M = {s: stock_months(s) for s in STOCKS}
    rows, pooled = [], []
    for per in JUDGE_P:
        stocks = [s for s in STOCKS if per in M[s]]
        keys = sorted({k for s in stocks for k, _ in M[s][per][2]})
        assert all(len(M[s][per][2]) == len(keys) for s in stocks), "달 수가 다른 종목"
        PI = np.argsort(rng.random((N_DRAW, len(keys))), axis=1)   # 묶음 · 종목 공통 달 순열 (같은 날 몰림 보존)
        rB, rP_pool, sides = [], np.zeros(N_DRAW), []
        for s in stocks:
            c, low, months = M[s][per][0], M[s][per][1], M[s][per][2]
            A, B, touch, wait = positions(months, low)
            starts = np.array([p[0] for _, p in months])
            lens = np.array([len(p) for _, p in months])
            off = B - starts                                        # B 가 기다린 거래일 수 (달 안 위치)
            invA = np.mean(1 / c[A])
            r_b = np.mean(1 / c[B]) / invA - 1
            # 종목 판정: 달 순열 종목 따로
            pi_s = np.argsort(rng.random((N_DRAW, len(months))), axis=1)
            posS = starts[None, :] + np.minimum(off[pi_s], lens[None, :] - 1)
            rS = (1 / c[posS]).mean(axis=1) / invA - 1
            q, vd = verdict_of(r_b, rS)
            # 묶음 판정: 공통 순열
            posP = starts[None, :] + np.minimum(off[PI], lens[None, :] - 1)
            rP = (1 / c[posP]).mean(axis=1) / invA - 1
            rP_pool += rP / len(stocks)
            # 참고: 그 달 아무 날(대기 시간 안 맞춤)
            u = rng.random((N_DRAW, len(months)))
            posC = starts[None, :] + np.minimum((u * lens[None, :]).astype(int), lens[None, :] - 1)
            rC = (1 / c[posC]).mean(axis=1) / invA - 1
            mon_mean = np.array([c[p].mean() for _, p in months])
            rows.append({"symbol": s, "period": per, "months": len(months), "r_B": r_b, "matched_median": float(np.median(rS)), "q": q,
                         "verdict": vd, "random_day_median": float(np.median(rC)), "touch_pct": touch * 100, "wait_days": wait,
                         "B_vs_month_mean_pct": float(np.mean(c[B] / mon_mean - 1) * 100)})
            rB.append(r_b)
            sides.append(np.sign(r_b - np.median(rP)))
        rb = float(np.mean(rB))
        q, vd = verdict_of(rb, rP_pool)
        want = 1 if vd == "특히 좋음" else -1 if vd == "특히 나쁨" else 0
        agree = float(np.mean([x == want for x in sides]) * 100) if want else np.nan
        sub = [r for r in rows if r["period"] == per]
        pooled.append({"period": per, "stocks": len(stocks), "r_B": rb, "matched_median": float(np.median(rP_pool)),
                       "matched_p5": float(np.quantile(rP_pool, .05)), "matched_p95": float(np.quantile(rP_pool, .95)), "q": q, "verdict": vd,
                       "agree_pct": agree, "random_day_median": float(np.mean([r["random_day_median"] for r in sub])),
                       "touch_pct": float(np.mean([r["touch_pct"] for r in sub])), "wait_days": float(np.mean([r["wait_days"] for r in sub])),
                       "B_vs_month_mean_pct": float(np.mean([r["B_vs_month_mean_pct"] for r in sub]))})
    S, P = pd.DataFrame(rows), pd.DataFrame(pooled)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, "split_buy.csv"), index=False)
    P.to_csv(os.path.join(out, "split_buy_pooled.csv"), index=False)
    return S, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P = run(a.out)
    print(f"저장: {a.out}/split_buy*.csv")
    print(P.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
