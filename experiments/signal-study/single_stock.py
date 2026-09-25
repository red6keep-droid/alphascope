"""r07 — 거래대금 폭등 1위 종목 하나만 매수: 비중 · 손절 · 손절 뒤 재매수. output/r07_single.md

사용자 확정 (2026-09-25):
  종목    매일 거래대금 RVOL 1위 하나. 진입일부터 20거래일 보유(20번째 종가 매도), 매도일의 1위로 교체.
  진입    (a) 폭등일 다음 날 시가 · (b) 폭등 뒤 첫 하락 마감(10거래일 안) 다음 날 시가. 눌림이 안 오면 그 회차 건너뜀.
  손절    진입가 −10% · −15% · 추적 −10%(진입 후 종가 최고 대비). 장중 저가 터치 시 손절가, 시가가 아래면 시가. 없음 = 참조.
  비중    100 · 50 · 33 %. 나머지 현금(수익 0).
  재매수  저점 +5% 회복(손절 뒤 종가가 손절 후 최저 종가 × 1.05 이상이면 다음 날 시가) · 진입가 회복(종가 ≥ 원래 진입가) · 20일 경과 · 없음.
          보유 기간 안에서만. 재매수 뒤 같은 손절 재적용.
  비용    매수·매도 각 0.1%.
  채택    같은 진입의 참조(손절 없음 · 100%)보다 탐색·검증 양쪽에서 회차 기대값 높고 최대 낙폭 작음.
"""

import itertools
import os
import sys

import numpy as np
import pandas as pd

import common
import config

H = 20
DIP_MAX = 10
ONE_WAY = common.COST / 2
ENTRIES = ["a", "b"]
STOPS = [None, ("fixed", 0.10), ("fixed", 0.15), ("trail", 0.10)]
WEIGHTS = [1.0, 0.5, 0.33]
REENTRY = ["none", "low5", "entry", "wait20"]
OUT = config.OUTPUT_DIR
LAB_E = {"a": "(a) 폭등 다음 날", "b": "(b) 첫 눌림 다음 날"}
LAB_S = {None: "손절 없음", ("fixed", 0.10): "−10%", ("fixed", 0.15): "−15%", ("trail", 0.10): "추적 −10%"}
LAB_R = {"none": "없음", "low5": "저점 +5%", "entry": "진입가 회복", "wait20": "20일 경과"}


def simulate_round(O, Hh, L, C, e, stop, w, reentry):
    """진입일 e 시가 매수 → e+H−1 종가 매도. 일간 계좌 가치(시작 1)와 기록을 돌려준다."""
    last = e + H - 1
    cash = 1.0 - w
    units = w * (1 - ONE_WAY) / O[e]
    in_pos = True
    p0 = O[e]
    hi = C[e]                      # 추적 손절 기준 (전날까지의 종가 최고)
    sleeve = 0.0
    vals = []
    n_stop = n_re = 0
    stop_day = None
    low_after = None
    stopped_ret_rest = []          # 손절가 → 회차 마지막 종가, 손절이 피한(또는 놓친) 폭
    for d in range(e, last + 1):
        if in_pos:
            lvl = None
            if stop is not None:
                kind, x = stop
                ref = p0 if kind == "fixed" else hi
                lvl = ref * (1 - x)
            if lvl is not None and d > e and (O[d] <= lvl or L[d] <= lvl):
                px = O[d] if O[d] <= lvl else lvl
                sleeve = units * px * (1 - ONE_WAY)
                units = 0.0
                in_pos = False
                n_stop += 1
                stop_day = d
                low_after = C[d]
                stopped_ret_rest.append(C[last] / px - 1)
            elif lvl is not None and d == e and L[d] <= lvl:
                px = lvl
                sleeve = units * px * (1 - ONE_WAY)
                units = 0.0
                in_pos = False
                n_stop += 1
                stop_day = d
                low_after = C[d]
                stopped_ret_rest.append(C[last] / px - 1)
            if in_pos:
                hi = max(hi, C[d])
        else:
            if stop_day is not None and d > stop_day and reentry != "none" and d < last:
                low_after = min(low_after, C[d - 1])
                go = False
                if reentry == "low5" and C[d - 1] >= low_after * 1.05:
                    go = True
                elif reentry == "entry" and C[d - 1] >= p0:
                    go = True
                elif reentry == "wait20" and d - stop_day >= 20:
                    go = True
                if go and sleeve > 0:
                    units = sleeve * (1 - ONE_WAY) / O[d]
                    sleeve = 0.0
                    in_pos = True
                    n_re += 1
                    p0 = O[d]
                    hi = C[d]
                    stop_day = None
        v = cash + sleeve + units * C[d]
        vals.append(v)
    if in_pos:
        vals[-1] = cash + sleeve + units * C[last] * (1 - ONE_WAY)
    return np.array(vals), n_stop, n_re, stopped_ret_rest


def stats_daily(r):
    r = pd.Series(r).dropna()
    n = len(r)
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
    Cv, Ov, Hv, Lv = D.C.values, D.O.values, D.H.values, D.L.values
    col = {s: i for i, s in enumerate(D.syms)}
    days = D.days
    n_days = len(days)
    spy = D.spy["Close"].reindex(days)
    spy_r = (spy / spy.shift(1) - 1)

    # 회차 일정 (진입 방식별) — 신호일 T, 진입일 e, 마지막 날 e+H−1, 다음 신호일 = 마지막 날
    schedules = {}
    for ent in ENTRIES:
        sched = []
        i = days.searchsorted(pd.Timestamp(config.STUDY_START))
        while i + 1 < n_days:
            if not has.iloc[i]:
                i += 1
                continue
            s = top1.iloc[i]
            j = col[s]
            if ent == "a":
                e = i + 1
            else:
                e = None
                for k in range(i + 1, min(i + DIP_MAX, n_days - 1) + 1):
                    if Cv[k, j] < Cv[k - 1, j]:
                        e = k + 1
                        break
                if e is None:
                    i += H          # 눌림 없음 → 건너뛰고 H 뒤 다시
                    continue
            last = e + H - 1
            if last >= n_days or np.isnan(Cv[e:last + 1, j]).any() or np.isnan(Ov[e, j]):
                i += H
                continue
            sched.append((i, e, j, s))
            i = last
        schedules[ent] = sched

    results = {}
    for ent, stop, w, re in itertools.product(ENTRIES, STOPS, WEIGHTS, REENTRY):
        if stop is None and re != "none":
            continue
        rows, daily, rest = [], [], []
        for (i, e, j, s) in schedules[ent]:
            vals, ns, nr, srr = simulate_round(Ov[:, j], Hv[:, j], Lv[:, j], Cv[:, j], e, stop, w, re)
            r = np.diff(np.concatenate([[1.0], vals])) / np.concatenate([[1.0], vals[:-1]])
            daily.append(pd.Series(r, index=days[e:e + H]))
            rows.append({"signal": days[i], "entry": days[e], "sym": s, "ret": vals[-1] - 1, "stopped": ns > 0, "re": nr, "period": D.period.iloc[i]})
            rest += srr
        R = pd.DataFrame(rows)
        results[(ent, stop, w, re)] = {"R": R, "daily": pd.concat(daily), "rest": np.array(rest)}

    def summ(key):
        x = results[key]
        R, dr = x["R"], x["daily"]
        out = {}
        for lab, sub, dsub in (("전체", R, dr), ("탐색", R[R.period == "탐색 ~2022"], dr[dr.index < pd.Timestamp(config.SPLIT_DAY)]),
                               ("검증", R[R.period == "검증 2023~"], dr[dr.index >= pd.Timestamp(config.SPLIT_DAY)])):
            sd = stats_daily(dsub)
            out[lab] = {"n": len(sub), "mean": sub.ret.mean(), "med": sub.ret.median(), "win": (sub.ret > 0).mean(), "stop": sub.stopped.mean(),
                        "re": sub.re.sum(), "cagr": sd["cagr"] if sd else np.nan, "mdd": sd["mdd"] if sd else np.nan, "final": sd["final"] if sd else np.nan}
        return out

    S = {k: summ(k) for k in results}

    md = ["# r07 — 거래대금 폭등 1위 종목 하나만 매수: 비중 · 손절 · 재매수", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {days.max().date()}. 매일 RVOL 1위 하나를 진입일부터 {H}거래일 보유, 매도일의 1위로 교체. "
          "진입 (a) 폭등 다음 날 시가 · (b) 폭등 뒤 첫 하락 마감(10일 안) 다음 날 시가. 손절 진입가 −10 · −15% · 추적 −10%(종가 최고 대비), 장중 저가 터치 시 손절가, 시가가 아래면 시가. "
          "비중 100 · 50 · 33%, 나머지 현금 0. 재매수 저점 +5% · 진입가 회복 · 20일 경과 · 없음, 보유 기간 안에서만, 재매수 뒤 같은 손절. 매수·매도 각 0.1%.", "",
          "채택 = 같은 진입의 참조(손절 없음 · 100%)보다 탐색(~2022)·검증(2023~) 양쪽에서 회차 기대값 높고 최대 낙폭 작음.", ""]

    # 1. 참조
    md += ["## 1. 참조 — 손절 없음 · 100%, 그리고 SPY", "",
           "| 진입 | 구간 | 회차 | 회차 기대값 | 중앙값 | 승률 | 연환산 | 최대 낙폭 | $10,000 → |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for ent in ENTRIES:
        s = S[(ent, None, 1.0, "none")]
        for lab in ("전체", "탐색", "검증"):
            v = s[lab]
            md.append(f"| {LAB_E[ent]} | {lab} | {v['n']} | **{v['mean'] * 100:+.2f}%** | {v['med'] * 100:+.2f}% | {v['win']:.0%} | {v['cagr'] * 100:+.1f}% | **{v['mdd'] * 100:.0f}%** | ${v['final'] * 10000:,.0f} |")
    for lab, m in (("전체", spy_r), ("탐색", spy_r[spy_r.index < pd.Timestamp(config.SPLIT_DAY)]), ("검증", spy_r[spy_r.index >= pd.Timestamp(config.SPLIT_DAY)])):
        m = m[m.index >= pd.Timestamp(config.STUDY_START)]
        sd = stats_daily(m)
        md.append(f"| SPY | {lab} | | | | | {sd['cagr'] * 100:+.1f}% | {sd['mdd'] * 100:.0f}% | ${sd['final'] * 10000:,.0f} |")
    md.append("")

    # 2. 손절 × 재매수 (비중 100%)
    md += ["## 2. 손절 × 재매수 — 비중 100%", "",
           "차이 = 참조(같은 진입, 손절 없음) 대비. 통과 = 탐색·검증 양쪽에서 기대값 차이 > 0 이고 낙폭 차이 > 0(덜 빠짐).", "",
           "| 진입 | 손절 | 재매수 | 회차 | 손절 발동 | 재매수 | 전체 기대값 | 승률 | 연환산 | 낙폭 | 탐색 기대값 차 | 탐색 낙폭 차 | 검증 기대값 차 | 검증 낙폭 차 | 판정 |",
           "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    n_pass = 0
    passes = []
    for ent in ENTRIES:
        ref = S[(ent, None, 1.0, "none")]
        for stop in STOPS[1:]:
            for re in REENTRY:
                s = S[(ent, stop, 1.0, re)]
                de = {lab: s[lab]["mean"] - ref[lab]["mean"] for lab in ("탐색", "검증")}
                dm = {lab: s[lab]["mdd"] - ref[lab]["mdd"] for lab in ("탐색", "검증")}
                ok_ = all(de[l] > 0 and dm[l] > 0 for l in ("탐색", "검증"))
                n_pass += ok_
                if ok_:
                    passes.append((ent, stop, re))
                v = s["전체"]
                md.append(f"| {LAB_E[ent]} | {LAB_S[stop]} | {LAB_R[re]} | {v['n']} | {v['stop']:.0%} | {v['re']} | **{v['mean'] * 100:+.2f}%** | {v['win']:.0%} | {v['cagr'] * 100:+.1f}% | **{v['mdd'] * 100:.0f}%** | "
                          f"{de['탐색'] * 100:+.2f}%p | {dm['탐색'] * 100:+.0f}%p | {de['검증'] * 100:+.2f}%p | {dm['검증'] * 100:+.0f}%p | {'**통과**' if ok_ else '—'} |")
    md += ["", f"**통과 {n_pass} / 24**", ""]

    # 3. 비중
    md += ["## 3. 비중 — 재매수 없음, 손절별", "",
           "| 진입 | 손절 | 비중 | 회차 기대값 | 연환산 | 낙폭 | 탐색 연환산 / 낙폭 | 검증 연환산 / 낙폭 | $10,000 → |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for ent in ENTRIES:
        for stop in STOPS:
            for w in WEIGHTS:
                s = S[(ent, stop, w, "none")]
                v = s["전체"]
                md.append(f"| {LAB_E[ent]} | {LAB_S[stop]} | {w:.0%} | {v['mean'] * 100:+.2f}% | {v['cagr'] * 100:+.1f}% | **{v['mdd'] * 100:.0f}%** | "
                          f"{s['탐색']['cagr'] * 100:+.1f}% / {s['탐색']['mdd'] * 100:.0f}% | {s['검증']['cagr'] * 100:+.1f}% / {s['검증']['mdd'] * 100:.0f}% | ${v['final'] * 10000:,.0f} |")
    md.append("")

    # 4. 손절이 피한 것
    md += ["## 4. 손절 뒤 그 종목은 어디로 갔나 — 손절가 → 회차 마지막 종가 (비중 100%, 재매수 없음)", "",
           "음수면 손절이 그만큼 손실을 피한 것, 양수면 놓친 것.", "",
           "| 진입 | 손절 | 발동 수 | 중앙값 | 평균 | 더 내린 비율 | 10% / 90% 분위 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for ent in ENTRIES:
        for stop in STOPS[1:]:
            rest = results[(ent, stop, 1.0, "none")]["rest"]
            if len(rest):
                md.append(f"| {LAB_E[ent]} | {LAB_S[stop]} | {len(rest)} | {np.median(rest) * 100:+.1f}% | {rest.mean() * 100:+.1f}% | {(rest < 0).mean():.0%} | {np.quantile(rest, .1) * 100:+.0f}% / {np.quantile(rest, .9) * 100:+.0f}% |")
    md.append("")

    # 5. 연도별 참조
    md += ["## 5. 연도별 — 참조 (a) / (b) / SPY", ""]
    ya = results[("a", None, 1.0, "none")]["daily"]; yb = results[("b", None, 1.0, "none")]["daily"]
    parts = []
    for y in sorted(set(ya.index.year)):
        ra = (1 + ya[ya.index.year == y]).prod() - 1
        rb = (1 + yb[yb.index.year == y]).prod() - 1 if (yb.index.year == y).any() else np.nan
        rs = (1 + spy_r[(spy_r.index.year == y) & (spy_r.index >= pd.Timestamp(config.STUDY_START))]).prod() - 1
        parts.append(f"{y}: {ra * 100:+.0f}% / {rb * 100:+.0f}% / {rs * 100:+.0f}%")
    md += [" · ".join(parts), ""]

    md += ["## 결론", "", "(계획 문서 8절에 요약)", ""]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "r07_single.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    rows = []
    for k, s in S.items():
        for lab in ("전체", "탐색", "검증"):
            rows.append({"entry": k[0], "stop": LAB_S[k[1]], "weight": k[2], "reentry": k[3], "period": lab, **s[lab]})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "r07_grid.csv"), index=False)
    pd.concat([results[("a", None, 1.0, "none")]["R"].assign(entry="a"), results[("b", None, 1.0, "none")]["R"].assign(entry="b")]).to_csv(os.path.join(OUT, "r07_rounds.csv"), index=False)
    print("\n".join(md))
    print("passes:", passes)


if __name__ == "__main__":
    main()
