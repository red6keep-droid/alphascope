"""볼린저 하단이 바닥인가 — 출구를 뺀 확인 (doc/볼린저-이슈별-검증-계획.md 4-11, 결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/bollinger_excursion.py            # 검증 ("검증해" 때만)
    FC_SMOKE=1 ... bollinger_excursion.py --out 스크래치                         # 점검 (섞은 수익률)

신호 = 종가 ≤ 20일 평균 − 2σ 첫 진입. 진입 = 신호 날 종가(주) · 다음 날 시가(참고).
MAE = ln(N일 안 최저 종가 ÷ 진입가), MFE = ln(N일 안 최고 종가 ÷ 진입가), N = 5 · 10 · 20 · 60.
주 지표 = 위쪽 비율 MFE ÷ (MFE − MAE) (바닥이면 1 에 가까움, 흔들림 크기와 무관). 참고 = 지난 252일 σ × √N 으로 나눈 MAE · MFE.
(처음 등록한 "그날 EWMA 로 나눈 값" 은 섞은 자료에서 한쪽으로 쏠려 결과 보기 전에 바꿈 — 계획 4-11)
비교 = 같은 종목 × 시기 아무 날. 플라시보 = 원형 이동 2,000번 (종목 · 15종목 묶음 모두, 사건 간격 보존). P3 · P4 같은 쪽만.
결과: results/bollinger_excursion.md · .csv
"""
import argparse
import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from failure_cost import MIN_N, N_DRAW, bar_frame, verdict_of
from normal_range import START, period_of

NS = [5, 10, 20, 60]
JUDGE_P = ["P3", "P4"]


def stock_table(sym):
    b = bar_frame(sym)
    c, o = b.close.values.astype(float), b.open.values.astype(float)
    idx = b.index
    cs = pd.Series(c, index=idx)
    ma, sd = cs.rolling(20).mean(), cs.rolling(20).std()
    lo = (cs <= ma - 2 * sd).values
    sig = lo & ~np.concatenate([[False], lo[:-1]])
    r = np.log(cs).diff()
    # 나누는 값 = 지난 252일 표준편차 (신호 날 제외) — 그날 EWMA 는 신호 날 하락이 부풀려 MAE · MFE 를 작게 만듦 (섞은 자료 점검에서 고침)
    ew = r.rolling(252, min_periods=200).std().shift(1).values
    n = len(c)
    rows = []
    for t in range(n):
        if idx[t] < START or not np.isfinite(ew[t]) or ew[t] <= 0 or not np.isfinite(ma.values[t]):
            continue
        for ex in ("close", "open"):
            e = t if ex == "close" else t + 1
            if e >= n:
                continue
            p = c[e] if ex == "close" else o[e]
            if not (p > 0):
                continue
            for N in NS:
                E = t + N
                if E >= n:
                    continue
                seg = c[e + 1 if ex == "close" else e:E + 1]
                if len(seg) == 0:
                    continue
                mae, mfe = np.log(seg.min() / p), np.log(seg.max() / p)
                s = ew[t] * np.sqrt(N)
                up = mfe / (mfe - mae) if mfe - mae > 0 else 0.5   # 위쪽 비율: N일 범위 중 진입가 위 몫 (흔들림 크기와 무관)
                rows.append((idx[t], period_of(idx[t]), bool(sig[t]), ex, N, mae, mfe, mae / s, mfe / s, up))
    return pd.DataFrame(rows, columns=["t", "period", "sig", "exec", "N", "mae", "mfe", "mae_z", "mfe_z", "up"])


def run(out):
    rng = np.random.default_rng(11)
    T = {s: stock_table(s) for s in STOCKS}
    rows, pooled_src = [], {}
    for s, d in T.items():
        d = d.copy()
        for (per, ex, N), g in d.groupby(["period", "exec", "N"]):
            ev, pool = g[g.sig], g.sort_values("t")
            for m in ["up", "mae_z", "mfe_z", "mae", "mfe"]:
                v, pv = ev[m].values, pool[m].values
                row = {"symbol": s, "period": per, "exec": ex, "N": N, "metric": m, "n": len(v),
                       "median": float(np.median(v)) if len(v) else np.nan,
                       "mean": float(np.mean(v)) if len(v) else np.nan,
                       "anyday_median": float(np.median(pv)), "anyday_mean": float(np.mean(pv))}
                if per in JUDGE_P and m in ("up", "mae_z", "mfe_z") and len(v):
                    if len(v) < MIN_N:
                        row["verdict"] = "표본 부족"
                    else:
                        # 원형 이동 (사건 간격 · 겹침 보존) — 21일 블록은 붙어 오는 진입의 겹침을 못 담아 섞은 자료에서 양쪽 8 ~ 11% (고침)
                        pos = np.flatnonzero(pool.sig.values)
                        sh = rng.integers(1, len(pv), size=N_DRAW)
                        dd = pv[(pos[None, :] + sh[:, None]) % len(pv)]
                        row["q"], row["verdict"] = verdict_of(np.median(v), np.median(dd, axis=1))
                    pooled_src.setdefault((per, ex, N, m), []).append((pool.t.values, pv, set(ev.t.values), row["median"], row["anyday_median"]))
                rows.append(row)
    S = pd.DataFrame(rows)
    # 15종목 묶음 — 원형 이동 (같은 날 몰림 보존)
    P = []
    for (per, ex, N, m), lst in pooled_src.items():
        days = pd.DatetimeIndex(sorted(set().union(*[set(t) for t, _, _, _, _ in lst])))
        L = len(days)
        V = np.vstack([pd.Series(pv, index=pd.DatetimeIndex(t)).reindex(days).values for t, pv, _, _, _ in lst])
        si, di = [], []
        for i, (t, pv, evs, _, _) in enumerate(lst):
            pos = days.get_indexer(pd.DatetimeIndex(sorted(evs)))
            si += [i] * len(pos)
            di += list(pos)
        si, di = np.array(si), np.array(di)
        ev = V[si, di]
        stat = np.nanmedian
        shifts = rng.integers(1, L, size=N_DRAW)
        meds = stat(V[si[None, :], (di[None, :] + shifts[:, None]) % L], axis=1)
        q, vd = verdict_of(stat(ev), meds)
        want = 1 if vd == "특히 좋음" else -1 if vd == "특히 나쁨" else 0
        sides = [np.sign(a - b) for _, _, _, a, b in lst]
        agree = float(np.mean([x == want for x in sides]) * 100) if want else np.nan
        P.append({"period": per, "exec": ex, "N": N, "metric": m, "n": len(ev), "stat": float(stat(ev)),
                  "anyday": float(np.nanmedian(meds)), "q": q, "verdict": vd, "agree_pct": agree})
    P = pd.DataFrame(P)
    os.makedirs(out, exist_ok=True)
    S.to_csv(os.path.join(out, "bollinger_excursion.csv"), index=False)
    P.to_csv(os.path.join(out, "bollinger_excursion_pooled.csv"), index=False)
    return S, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    S, P = run(a.out)
    print(P[(P["exec"] == "close") & P.period.isin(JUDGE_P)].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
