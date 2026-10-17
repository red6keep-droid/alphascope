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
        early = float(np.nanmax(e[i + 1:i + 6]) / base) if i + 1 < len(e) else np.nan  # 시작일 포함 5거래일 마감까지
        rows.append({"symbol": sym, "start": idx[i].date(), "kind": kind, "base_daily_sd": round(float(base), 4),
                     "early_x": round(early, 3), "peak_x": round(peak, 2), "recovery_days": rec})
    return rows


def spearman(x, y):
    if len(x) < 5:
        return float("nan")
    return float(pd.Series(x).rank().corr(pd.Series(y).rank()))


def early():
    """C10 (계획 9절)."""
    D = pd.DataFrame([row for s in STOCKS for row in run_stock(s)])
    D = D[D.recovery_days != "진행 중"].copy()
    D["cluster"] = np.where(D.kind == "시장", "M" + D.start.astype(str), "S" + D.symbol + D.start.astype(str))
    sw = D[D.recovery_days != "부풀지 않음"].copy()
    sw["rec"] = sw.recovery_days.replace({"500 넘음": CAP + 1}).astype(float)
    rho = spearman(sw.early_x.values, sw.rec.values)
    rng = np.random.default_rng(0)
    cl = sw.cluster.unique()
    groups = {c: g for c, g in sw.groupby("cluster")}
    boots = []
    for _ in range(2000):
        pick = rng.choice(cl, size=len(cl), replace=True)
        b = pd.concat([groups[c] for c in pick])
        boots.append(spearman(b.early_x.values, b.rec.values))
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    yr = pd.to_datetime(sw.start).dt.year
    r_a = spearman(sw[yr < 2013].early_x.values, sw[yr < 2013].rec.values)
    r_b = spearman(sw[yr >= 2013].early_x.values, sw[yr >= 2013].rec.values)
    split = rho > 0 and lo > 0 and r_a > 0 and r_b > 0
    q1, q2 = sw.early_x.quantile([1 / 3, 2 / 3])
    lab = lambda x: "작음" if x < q1 else ("중간" if x < q2 else "큼")
    D["group"] = D.early_x.map(lab)
    sw["group"] = sw.early_x.map(lab)
    L = ["# C10 — 충격 초기 크기로 흔들림 회복 기간이 갈리나", "", "계획: doc/평소-범위-검증-계획.md 9절. 초기 크기 = 시작일 포함 5거래일 마감까지 EWMA 최대 ÷ 직전 1년.", "",
         f"## ① 갈리나: {'**초기 크기로 갈린다**' if split else '**판정 기준 미달**'}", "",
         f"- 스피어만 {rho:.2f} (묶음 붓스트랩 95% {lo:.2f} ~ {hi:.2f}, 묶음 {len(cl)}개 · 충격 {len(sw)}건)",
         f"- 앞 시기(< 2013) {r_a:.2f} (n {int((yr < 2013).sum())}) · 뒤 시기(≥ 2013) {r_b:.2f} (n {int((yr >= 2013).sum())})", "",
         f"## 그룹 (경계 {q1:.2f} 배 · {q2:.2f} 배)", "", "| 그룹 | 충격 수 | 부풀지 않음(같은 경계) | 회복 중앙값 | 사분위 25 ~ 75 | 10 ~ 90% | 500 넘음 |", "|---|---|---|---|---|---|---|"]
    even_rows = []
    for gname in ("작음", "중간", "큼"):
        g = sw[sw.group == gname]
        ns = int(((D.group == gname) & (D.recovery_days == "부풀지 않음")).sum())
        q25, q75 = g.rec.quantile([.25, .75])
        L.append(f"| {gname} | {len(g)} | {ns} | {g.rec.median():.0f} | {q25:.0f} ~ {q75:.0f} | "
                 f"{g.rec.quantile(.1):.0f} ~ {g.rec.quantile(.9):.0f} | {(g.rec > CAP).sum()} |")
        st = g.groupby("symbol").rec.agg(["size", "median"])
        st = st[st["size"] >= 3]
        inside = ((st["median"] >= q25) & (st["median"] <= q75))
        even_rows.append((gname, len(st), int(inside.sum()), st))
    L += ["", "## ② 고른가 (그룹 안 종목별 회복 중앙값이 그룹 사분위 안, 충격 3번 이상 종목)", "", "| 그룹 | 종목 수 | 안 | 비율 | 판정 | 밖 종목 (중앙값) |", "|---|---|---|---|---|---|"]
    for gname, n, k, st in even_rows:
        g = sw[sw.group == gname]
        q25, q75 = g.rec.quantile([.25, .75])
        outs = ", ".join(f"{sym} {m:.0f}" for sym, m in st["median"].items() if not (q25 <= m <= q75))
        L.append(f"| {gname} | {n} | {k} | {k / n:.0%} | {'고르다' if n and k / n >= 0.8 else '고르지 않음'} | {outs or '-'} |" if n else f"| {gname} | 0 | - | - | 표본 부족 | - |")
    L += ["", "## ③ 종목별 실제 기록은 normal_range_recovery_early.csv (종목 · 시작일 · 종류 · 초기 크기 · 회복 일수 · 정점 배수)", ""]
    D.drop(columns=["cluster"]).to_csv(os.path.join(OUT, "normal_range_recovery_early.csv"), index=False)
    with open(os.path.join(OUT, "normal_range_recovery_early.md"), "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))


def main():
    import sys
    if "--early" in sys.argv:
        early()
        return
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
