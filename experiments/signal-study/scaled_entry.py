"""r08 — 거래대금 폭등 1위 종목 하나, 분할 매수. output/r08_scaled.md

사용자 확정 (2026-09-25): 회차 창 T+1 ~ T+20 (T = 1위 신호일), T+20 종가 전량 매도, 매도일의 1위로 교체. 비중 100%, 손절 없음.
  전량 A     T+1 시가 100%
  전량 B     첫 하락 마감(T+1 ~ T+10) 다음 날 시가 100%. 눌림 없으면 그 회차 현금
  시간 분할  T+1 · T+3 · T+5 시가 1/3 씩
  눌림 분할  T+1 시가 1/2 + 첫 눌림 다음 날 시가 1/2. 없으면 1/2 만 보유
  물타기     T+1 시가 1/2 + 첫 진입가 −5% 터치(T+2 이후) 시 1/2 (시가가 아래면 시가). 없으면 1/2 만 보유
비용 매수·매도 각 0.1%. 채택 = 전량 A보다 탐색·검증 양쪽에서 회차 기대값 높고 최대 낙폭 작음.
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

H = 20
DIP_MAX = 10
ONE_WAY = common.COST / 2
OUT = config.OUTPUT_DIR
VARIANTS = ["A", "B", "time", "dip", "avgdown"]
LAB = {"A": "전량 A (T+1)", "B": "전량 B (첫 눌림)", "time": "시간 분할 1/3×3", "dip": "눌림 분할 1/2+1/2", "avgdown": "물타기 1/2 + −5% 1/2"}


def plan_buys(O, L, C, i, variant):
    """(day, fraction, price) 목록. i = 신호일. 창 = i+1 .. i+H."""
    e, last = i + 1, i + H
    dip = None
    for k in range(i + 1, min(i + DIP_MAX, last - 1) + 1):
        if C[k] < C[k - 1]:
            dip = k + 1
            break
    if variant == "A":
        return [(e, 1.0, O[e])]
    if variant == "B":
        return [(dip, 1.0, O[dip])] if dip is not None else []
    if variant == "time":
        return [(e, 1 / 3, O[e]), (e + 2, 1 / 3, O[e + 2]), (e + 4, 1 / 3, O[e + 4])]
    if variant == "dip":
        b = [(e, 0.5, O[e])]
        if dip is not None:
            b.append((dip, 0.5, O[dip]))
        return b
    if variant == "avgdown":
        b = [(e, 0.5, O[e])]
        lvl = O[e] * 0.95
        for d in range(e + 1, last + 1):
            if O[d] <= lvl:
                b.append((d, 0.5, O[d])); break
            if L[d] <= lvl:
                b.append((d, 0.5, lvl)); break
        return b
    raise ValueError(variant)


def simulate(O, L, C, i, buys):
    e, last = i + 1, i + H
    cash, units = 1.0, 0.0
    by_day = {}
    for d, f, px in buys:
        by_day.setdefault(d, []).append((f, px))
    vals = []
    for d in range(e, last + 1):
        for f, px in by_day.get(d, []):
            cash -= f
            units += f * (1 - ONE_WAY) / px
        vals.append(cash + units * C[d])
    vals[-1] = cash + units * C[last] * (1 - ONE_WAY)
    invested = sum(f for _, f, _ in buys)
    return np.array(vals), invested


def stats_daily(r):
    r = pd.Series(r).dropna(); n = len(r)
    if n < 60:
        return None
    eq = (1 + r).cumprod()
    return {"cagr": eq.iloc[-1] ** (252 / n) - 1, "mdd": (eq / eq.cummax() - 1).min(), "final": eq.iloc[-1], "vol": r.std() * np.sqrt(252)}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    ok = D.valid & D.study.values[:, None]
    dv = D.C * D.V
    rvol = (dv / dv.shift(1).rolling(20).mean()).where(ok)
    has = rvol.notna().any(axis=1)
    top1 = rvol.fillna(-1).idxmax(axis=1).where(has)
    Cv, Ov, Lv = D.C.values, D.O.values, D.L.values
    col = {s: k for k, s in enumerate(D.syms)}
    days = D.days; n_days = len(days)
    spy = D.spy["Close"].reindex(days); spy_r = spy / spy.shift(1) - 1

    sched = []
    i = days.searchsorted(pd.Timestamp(config.STUDY_START))
    while i + H < n_days:
        if not has.iloc[i]:
            i += 1; continue
        s = top1.iloc[i]; j = col[s]
        if np.isnan(Cv[i + 1:i + H + 1, j]).any() or np.isnan(Ov[i + 1:i + 6, j]).any():
            i += H; continue
        sched.append((i, j, s)); i += H

    results = {}
    for v in VARIANTS:
        rows, daily = [], []
        for (i, j, s) in sched:
            buys = plan_buys(Ov[:, j], Lv[:, j], Cv[:, j], i, v)
            vals, inv = simulate(Ov[:, j], Lv[:, j], Cv[:, j], i, buys)
            r = np.diff(np.concatenate([[1.0], vals])) / np.concatenate([[1.0], vals[:-1]])
            daily.append(pd.Series(r, index=days[i + 1:i + H + 1]))
            rows.append({"signal": days[i], "sym": s, "ret": vals[-1] - 1, "invested": inv, "n_buys": len(buys),
                         "avg_px_vs_A": (sum(f * px for _, f, px in buys) / inv / Ov[i + 1, j] - 1) if inv > 0 else np.nan,
                         "period": D.period.iloc[i]})
        results[v] = {"R": pd.DataFrame(rows), "daily": pd.concat(daily)}

    def summ(v):
        R, dr = results[v]["R"], results[v]["daily"]
        out = {}
        for lab, sub, dsub in (("전체", R, dr), ("탐색", R[R.period == "탐색 ~2022"], dr[dr.index < pd.Timestamp(config.SPLIT_DAY)]),
                               ("검증", R[R.period == "검증 2023~"], dr[dr.index >= pd.Timestamp(config.SPLIT_DAY)])):
            sd = stats_daily(dsub)
            out[lab] = {"n": len(sub), "mean": sub.ret.mean(), "med": sub.ret.median(), "win": (sub.ret > 0).mean(), "inv": sub.invested.mean(),
                        "full": (sub.invested >= 0.99).mean(), "avgpx": sub.avg_px_vs_A.mean(),
                        "cagr": sd["cagr"] if sd else np.nan, "mdd": sd["mdd"] if sd else np.nan, "final": sd["final"] if sd else np.nan, "vol": sd["vol"] if sd else np.nan}
        return out
    S = {v: summ(v) for v in VARIANTS}

    md = ["# r08 — 1위 종목 하나, 분할 매수", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {days.max().date()} · 회차 {len(sched)}. 매일 RVOL 1위, 창 T+1 ~ T+20, T+20 종가 전량 매도. 비중 100%, 손절 없음, 매수·매도 각 0.1%. "
          "전량 B와 눌림 분할의 눌림 = T+1~T+10 안 첫 하락 마감 다음 날 시가. 물타기 = 첫 진입가 −5% 터치(T+2 이후) 시 나머지 1/2. 남은 현금 수익 0.", "",
          "채택 = 전량 A보다 탐색·검증 양쪽에서 회차 기대값 높고 최대 낙폭 작음.", "",
          "## 1. 진입 방식별", "",
          "| 진입 | 구간 | 회차 | 평균 투입 비율 | 전량 투입된 회차 | 평균 매수가 (A 대비) | 회차 기대값 | 중앙값 | 승률 | 연환산 | 연변동성 | 최대 낙폭 | $10,000 → | A 대비 기대값 | A 대비 낙폭 | 판정 |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    verdict = {}
    for v in VARIANTS:
        ok_ = True
        for lab in ("전체", "탐색", "검증"):
            x, a = S[v][lab], S["A"][lab]
            de, dm = x["mean"] - a["mean"], x["mdd"] - a["mdd"]
            if lab != "전체":
                ok_ &= (de > 0) and (dm > 0)
            md.append(f"| {LAB[v]} | {lab} | {x['n']} | {x['inv']:.0%} | {x['full']:.0%} | {x['avgpx'] * 100:+.2f}% | **{x['mean'] * 100:+.2f}%** | {x['med'] * 100:+.2f}% | {x['win']:.0%} | "
                      f"{x['cagr'] * 100:+.1f}% | {x['vol'] * 100:.1f}% | **{x['mdd'] * 100:.0f}%** | ${x['final'] * 10000:,.0f} | {de * 100:+.2f}%p | {dm * 100:+.0f}%p | "
                      f"{'' if v == 'A' else ('**통과**' if ok_ and lab == '검증' else ('—' if lab == '검증' else ''))} |")
        verdict[v] = ok_
    for lab, m in (("전체", spy_r), ("탐색", spy_r[spy_r.index < pd.Timestamp(config.SPLIT_DAY)]), ("검증", spy_r[spy_r.index >= pd.Timestamp(config.SPLIT_DAY)])):
        m = m[m.index >= pd.Timestamp(config.STUDY_START)]; sd = stats_daily(m)
        md.append(f"| SPY | {lab} | | | | | | | | {sd['cagr'] * 100:+.1f}% | {sd['vol'] * 100:.1f}% | {sd['mdd'] * 100:.0f}% | ${sd['final'] * 10000:,.0f} | | | |")
    n_pass = sum(verdict[v] for v in VARIANTS if v != "A")
    md += ["", f"**통과 {n_pass} / 4**", ""]

    # 2. 같은 투입 비율로 맞춘 비교 — 분할의 효과 중 '덜 투자한 것'을 뺀다
    md += ["## 2. 투입 비율을 맞춘 비교 — 회차 수익 ÷ 평균 투입 비율 (투자한 돈 기준 기대값)", "",
           "분할·눌림·물타기는 창의 일부 기간에 현금이 남는다. 투자한 돈 기준으로 다시 보면 '덜 투자해서 낙폭이 준 것'과 '더 싸게 사서 나아진 것'이 갈린다.", "",
           "| 진입 | 전체 | 탐색 | 검증 |", "| --- | ---: | ---: | ---: |"]
    for v in VARIANTS:
        R = results[v]["R"]
        vals = []
        for lab, sub in (("전체", R), ("탐색", R[R.period == "탐색 ~2022"]), ("검증", R[R.period == "검증 2023~"])):
            sub = sub[sub.invested > 0]
            vals.append((sub.ret / sub.invested).mean())
        md.append(f"| {LAB[v]} | {vals[0] * 100:+.2f}% | {vals[1] * 100:+.2f}% | {vals[2] * 100:+.2f}% |")
    md.append("")

    # 3. 눌림·물타기 발생 통계
    Rd, Ra = results["dip"]["R"], results["avgdown"]["R"]
    md += ["## 3. 눌림 · −5% 터치가 실제로 왔나", "",
           f"- 10일 안 첫 하락 마감이 온 회차: {(Rd.n_buys == 2).mean():.0%} (탐색 {(Rd[Rd.period == '탐색 ~2022'].n_buys == 2).mean():.0%} · 검증 {(Rd[Rd.period == '검증 2023~'].n_buys == 2).mean():.0%})",
           f"- 창 안에 첫 진입가 −5% 터치가 온 회차: {(Ra.n_buys == 2).mean():.0%} (탐색 {(Ra[Ra.period == '탐색 ~2022'].n_buys == 2).mean():.0%} · 검증 {(Ra[Ra.period == '검증 2023~'].n_buys == 2).mean():.0%})",
           f"- 물타기가 발동한 회차의 수익 중앙값 {Ra[Ra.n_buys == 2].ret.median() * 100:+.1f}% vs 같은 회차 전량 A {results['A']['R'][Ra.n_buys == 2].ret.median() * 100:+.1f}% · 발동 안 한 회차 물타기(=1/2 보유) {Ra[Ra.n_buys == 1].ret.median() * 100:+.1f}% vs 전량 A {results['A']['R'][Ra.n_buys == 1].ret.median() * 100:+.1f}%", ""]

    # 4. 연도별
    md += ["## 4. 연도별 — A / B / 시간 / 눌림 / 물타기 / SPY", ""]
    parts = []
    yrs = sorted(set(results["A"]["daily"].index.year))
    for y in yrs:
        vs = []
        for v in VARIANTS:
            d = results[v]["daily"]; vs.append((1 + d[d.index.year == y]).prod() - 1)
        rs = (1 + spy_r[(spy_r.index.year == y) & (spy_r.index >= pd.Timestamp(config.STUDY_START))]).prod() - 1
        parts.append(f"{y}: " + " / ".join(f"{x * 100:+.0f}%" for x in vs) + f" / {rs * 100:+.0f}%")
    md += [" · ".join(parts), "", "## 결론", "", "(계획 문서 8절에 요약)", ""]

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "r08_scaled.md"), "w", encoding="utf-8").write("\n".join(md))
    pd.concat([results[v]["R"].assign(variant=v) for v in VARIANTS]).to_csv(os.path.join(OUT, "r08_rounds.csv"), index=False)
    print("\n".join(md)); print("verdict:", verdict)


if __name__ == "__main__":
    main()
