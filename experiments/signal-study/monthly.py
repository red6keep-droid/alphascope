"""r05 — 월 단위 종목 선택, 기대값·낙폭으로 판정. output/r05_monthly.md

매월 첫 거래일 시가 매수 → 다음 달 첫 거래일 시가 매도. 신호는 전월 마지막 종가까지의 데이터.
S&P 500 편입일 이후 · 하락장 제외 없음 · 동일 비중 · 왕복 0.2% / 포지션 / 월 (전량 교체 가정, 실제 회전율은 따로 표시).

점수 (결과 전 고정, 2026-09-25):
  S1 12−1개월 모멘텀            높을수록
  S2 성장 = EPS 전년비 + 4분기 서프라이즈 평균 (순위 평균)   높을수록
  S3 저변동성 = 3개월 일간 변동성   낮을수록
  S4 = S1 · S2 · S3 순위 평균
  S5 = S4, 단 교체일에 SPY < 200일선이면 그 달은 현금
  S6 = S4 + 월중 −10% 손절 (터치 시 −10% 체결, 갭이면 시가, 남은 기간 현금)
대조: SPY · 500 동일가중 · 무작위 N 종목 1,000개
채택: 탐색(~2022)·검증(2023~) 양쪽에서 연환산 > SPY 이고 샤프 > SPY 이고 무작위 N 중앙값 초과.
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config
from winners import growth_features, price_features

NS = [10, 20, 50]
NRAND = 1000
STOP = -0.10


def month_starts(days):
    s = pd.Series(days)
    firsts = s.groupby([days.year, days.month]).first()
    return [d for d in firsts if d >= pd.Timestamp(config.STUDY_START)]


def stats(r, spy, name, rand_cagr=None):
    r = pd.Series(r).dropna()
    if len(r) < 6:
        return None
    n = len(r); yrs = n / 12
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(12)
    eq = (1 + r).cumprod(); mdd = (eq / eq.cummax() - 1).min()
    sp = pd.Series(spy).reindex(r.index)
    return {"name": name, "n": n, "cagr": cagr, "vol": vol, "sharpe": cagr / vol if vol > 0 else np.nan, "mdd": mdd, "worst": r.min(),
            "win": (r > 0).mean(), "beat_spy": (r > sp).mean(), "mean": r.mean(), "final": (1 + r).prod(),
            "rand_pct": (np.mean(rand_cagr < cagr) if rand_cagr is not None else np.nan)}


def row(s):
    if s is None:
        return ""
    rp = "—" if np.isnan(s["rand_pct"]) else f"{s['rand_pct']:.0%}"
    return (f"| {s['name']} | {s['n']} | **{s['cagr'] * 100:+.1f}%** | {s['vol'] * 100:.1f}% | {s['sharpe']:.2f} | **{s['mdd'] * 100:.0f}%** | {s['worst'] * 100:+.1f}% | "
            f"{s['win']:.0%} | {s['beat_spy']:.0%} | {s['mean'] * 100:+.2f}% | {rp} | ${s['final'] * 10000:,.0f} |")


HEAD = ("| 전략 | 개월 | 연환산 | 연변동성 | 샤프 | 최대 낙폭 | 최악의 달 | 월 승률 | SPY 이긴 달 | 월 기대값 | 무작위 N 이긴 비율 | $10,000 → |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    e = pd.read_csv(os.path.join(config.DATA_DIR, "earnings.csv"), parse_dates=["day"])
    earn = {s: g.sort_values("day") for s, g in e.groupby("symbol")}
    ms = month_starts(D.days)
    C, O, L = D.C, D.O, D.L
    spy_o = D.spy["Open"].reindex(D.days)
    rng = np.random.default_rng(config.SEED)
    # 월별: 점수 → 선택 → 월 수익
    rec = []                                   # (month, dict of strategy → return, spy, ew, rand[N] arrays)
    prev_hold = {}
    turnover = {}
    for k in range(len(ms) - 1):
        t, t_next = ms[k], ms[k + 1]
        i, j = D.days.get_loc(t), D.days.get_loc(t_next)
        if i - 1 < 260:
            continue
        sig_day = D.days[i - 1]
        valid = D.valid.iloc[i - 1] & C.iloc[i - 1].notna() & C.iloc[i - 260].notna() & O.iloc[i].notna() & O.iloc[j].notna()
        syms = valid[valid].index
        pf = price_features(D, sig_day, i - 1).loc[syms]
        gf = growth_features(D, earn, sig_day).reindex(syms)
        ret = (O.iloc[j][syms] / O.iloc[i][syms] - 1)            # 시가 → 다음 달 시가
        # 월중 −10% 손절 수익
        lo = L.iloc[i: j].min()[syms]
        op = O.iloc[i][syms]
        stop_px = op * (1 + STOP)
        # 갭 근사: 손절 터치면 손절가 체결 (갭 하락은 첫 저가가 손절가 아래 → 더 나쁨; 보수적으로 min(손절가, 그날 시가) 대신 손절가 사용은 낙관적. 첫 터치일 시가로 보정)
        ret_stop = ret.copy()
        hit = lo <= stop_px
        if hit.any():
            for s_ in hit[hit].index:
                seg = L.iloc[i: j][s_]
                d = seg[seg <= stop_px[s_]].index[0]
                o_d = O.loc[d, s_]
                px = min(stop_px[s_], o_d) if d != t else stop_px[s_]
                ret_stop[s_] = px / op[s_] - 1
        rk = lambda x, asc=False: x.rank(pct=True, ascending=asc)
        scores = {
            "S1 12−1 모멘텀": rk(pf["mom_12_1"]),
            "S2 성장 (EPS)": (rk(gf["eps_yoy"]) .fillna(0.5) + rk(gf["surp_avg4"]).fillna(0.5)) / 2,
            "S3 저변동성": rk(pf["vol_3m"], asc=False),   # ascending=False → 변동성이 작을수록 백분위가 높다 (상위 = 저변동성)
        }
        scores["S4 조합"] = (scores["S1 12−1 모멘텀"] + scores["S2 성장 (EPS)"] + scores["S3 저변동성"]) / 3
        spy_ok = bool(D.spy_ok.iloc[i - 1])
        m = {"month": t, "spy": spy_o.iloc[j] / spy_o.iloc[i] - 1, "ew": ret.mean() - common.COST, "spy_ok": spy_ok,
             "period": "탐색 ~2022" if t < pd.Timestamp(config.SPLIT_DAY) else "검증 2023~"}
        for N in NS:
            pool = ret.dropna().values
            m[f"rand|{N}"] = pool[rng.integers(0, len(pool), size=(NRAND, N))].mean(axis=1) - common.COST
            for name, sc in scores.items():
                pick = sc.dropna().sort_values(ascending=False).index[:N]
                key = f"{name}|{N}"
                m[key] = ret[pick].mean() - common.COST
                if name == "S4 조합":
                    m[f"S5 조합+국면 스위치|{N}"] = m[key] if spy_ok else 0.0
                    m[f"S6 조합+월중 −10% 손절|{N}"] = ret_stop[pick].mean() - common.COST
                    prev = prev_hold.get(N, set()); cur = set(pick)
                    turnover.setdefault(N, []).append(1 - len(prev & cur) / N if prev else np.nan)
                    prev_hold[N] = cur
        rec.append(m)
    R = pd.DataFrame(rec).set_index("month")
    strategies = ["S1 12−1 모멘텀", "S2 성장 (EPS)", "S3 저변동성", "S4 조합", "S5 조합+국면 스위치", "S6 조합+월중 −10% 손절"]

    md = ["# r05 — 월 단위 종목 선택 · 기대값과 낙폭", "",
          f"교체 {len(R)}회 ({R.index[0].date()} ~ {R.index[-1].date()}) · 매월 첫 거래일 시가 → 다음 달 첫 거래일 시가 · 왕복 0.2%/포지션/월 · 하락장 제외 없음. 규칙은 `monthly.py` 머리말.",
          "**무작위 N 이긴 비율** = 같은 달들에 무작위 N종목을 1,000번 굴린 연환산 분포에서 전략이 이긴 비율 (50% = 무작위와 같음).", ""]

    def section(title, sub, note=None):
        out = [f"## {title}", ""] + ([note, ""] if note else [])
        for N in NS:
            rand_c = (1 + np.vstack(sub[f"rand|{N}"].values)).prod(axis=0) ** (12 / len(sub)) - 1
            out += [f"**{N}종목**", "", HEAD]
            for name in strategies:
                out.append(row(stats(sub[f"{name}|{N}"], sub["spy"], name, rand_c)))
            rs = stats(pd.Series(np.median(np.vstack(sub[f"rand|{N}"].values), axis=1), index=sub.index), sub["spy"], f"무작위 {N} (중앙값 경로)")
            out.append(row(rs))
            if N == NS[0]:
                out.append(row(stats(sub["spy"], sub["spy"], "SPY")))
                out.append(row(stats(sub["ew"], sub["spy"], "500 동일가중")))
            out.append("")
        return out

    md += section("전체 기간", R)
    md += section("탐색 ~2022", R[R.period == "탐색 ~2022"])
    md += section("검증 2023~", R[R.period == "검증 2023~"])

    # 채택 판정
    md += ["## 채택 판정 — 탐색·검증 양쪽에서 연환산 > SPY 이고 샤프 > SPY 이고 무작위 N 중앙값 초과", "",
           "| 전략 | N | 탐색: 연환산 vs SPY / 샤프 vs SPY / 무작위 | 검증: 같은 셋 | 판정 |", "| --- | ---: | --- | --- | --- |"]
    adopted = []
    for name in strategies:
        for N in NS:
            cells, okk = [], True
            for per in ("탐색 ~2022", "검증 2023~"):
                sub = R[R.period == per]
                rand_c = (1 + np.vstack(sub[f"rand|{N}"].values)).prod(axis=0) ** (12 / len(sub)) - 1
                s = stats(sub[f"{name}|{N}"], sub["spy"], name, rand_c); sp = stats(sub["spy"], sub["spy"], "spy")
                a, b, c = s["cagr"] > sp["cagr"], s["sharpe"] > sp["sharpe"], s["rand_pct"] > 0.5
                okk &= a and b and c
                cells.append(f"{s['cagr'] * 100:+.1f} vs {sp['cagr'] * 100:+.1f} {'○' if a else '×'} / {s['sharpe']:.2f} vs {sp['sharpe']:.2f} {'○' if b else '×'} / {s['rand_pct']:.0%} {'○' if c else '×'}")
            if okk:
                adopted.append((name, N))
            md.append(f"| {name} | {N} | {cells[0]} | {cells[1]} | {'**채택**' if okk else '—'} |")
    md.append("")

    # 연도별 — S4 10·20, SPY
    md += ["## 연도별 수익 — S4 조합 (10 · 20 · 50) vs SPY vs 동일가중", "", "| 연도 | S4 10 | S4 20 | S4 50 | S5 10 | SPY | 동일가중 |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for y, g in R.groupby(R.index.year):
        f = lambda col: f"{((1 + g[col]).prod() - 1) * 100:+.0f}%"
        md.append(f"| {y} | {f('S4 조합|10')} | {f('S4 조합|20')} | {f('S4 조합|50')} | {f('S5 조합+국면 스위치|10')} | {f('spy')} | {f('ew')} |")
    md.append("")
    # 회전율 · 국면
    md += ["## 회전율 · 국면", "",
           "월 회전율(교체된 종목 비율): " + " · ".join(f"{N}종목 {np.nanmean(turnover[N]):.0%}" for N in NS),
           f"\n국면 스위치(S5)가 현금이었던 달: {(~R.spy_ok).sum()} / {len(R)}",
           "\n비용은 전량 교체 가정(0.2% × N/N)이라 실제 회전율만큼만 내면 연 " + " · ".join(f"{N}: +{(1 - np.nanmean(turnover[N])) * 0.2 * 12:.1f}%p" for N in NS) + " 정도 유리해진다.", ""]
    # 낙폭 — S4 10 의 낙폭 구간
    r = R["S4 조합|10"]; eq = (1 + r).cumprod(); dd = eq / eq.cummax() - 1
    worst = dd.idxmin()
    peak = eq[:worst].idxmax()
    rec_ = eq[worst:][eq[worst:] >= eq[peak]]
    md += ["## 낙폭 — S4 조합 10종목", "",
           f"최대 낙폭 {dd.min() * 100:.0f}%: 고점 {peak.date()} → 저점 {worst.date()} → 회복 {rec_.index[0].date() if len(rec_) else '미회복'}. "
           f"SPY 같은 구간: {((1 + R.loc[peak:worst, 'spy']).prod() - 1) * 100:+.0f}%.",
           "월 수익 분포 (10종목): 하위 5% " + f"{r.quantile(0.05) * 100:+.1f}% · 중앙값 {r.median() * 100:+.1f}% · 상위 5% {r.quantile(0.95) * 100:+.1f}%. SPY: {R.spy.quantile(0.05) * 100:+.1f}% / {R.spy.median() * 100:+.1f}% / {R.spy.quantile(0.95) * 100:+.1f}%", ""]

    os.makedirs(common.OUT, exist_ok=True)
    path = os.path.join(common.OUT, "r05_monthly.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    R.drop(columns=[c for c in R.columns if c.startswith("rand|")]).to_csv(os.path.join(common.OUT, "r05_monthly.csv"))
    print(f"→ {path}  채택: {adopted if adopted else '없음'}")


if __name__ == "__main__":
    main()
