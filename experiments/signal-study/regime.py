"""r06 — 관심 종목 5개 + 낙폭 사다리. output/r06_regime.md

사용자 확정 (2026-09-25):
  종목      거래대금 RVOL(당일 거래대금 ÷ 직전 20일 평균) 상위 5, 방향 무관, 동일 비중. 대조로 상위 10.
  교체 주기 5 · 10 · 20 · 40 · 60 거래일을 탐색(~2022)에서 돌려 1등(연환산) 하나만 검증(2023~)에 쓴다.
  참조 지수 = 관심 종목 5개를 항상 100% 보유했을 때의 자산. 낙폭은 이 지수의 고점 대비로 잰다.
  사다리    −20% → 비중 50% · −30% → 100% 재매수 · −40% → 20% · 마지막 변경 뒤 20거래일 다음 단계 없음 → 100% · 새 고점 → 초기화.
            각 단계는 고점을 새로 쓰기 전까지 한 번만 걸린다. 판정은 전날 종가까지, 비중 변경은 다음 날.
  비용      교체 왕복 0.2%. 비중 변경도 거래로 세어 바뀐 비중 × 편도 0.1%.
  대조      참조 지수(비중 조절 없음) · SPY · SPY에 같은 사다리 · 무작위 5종목 1,000개(교체 수익만).
  채택      탐색·검증 양쪽에서 사다리가 참조 지수보다 연환산 높고 최대 낙폭 작으면 통과.
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

HS = [5, 10, 20, 40, 60]
NS = [5, 10]
NRAND = 1000
LADDER = [(-0.20, 0.5, "−20% → 50%"), (-0.30, 1.0, "−30% → 100% 재매수"), (-0.40, 0.2, "−40% → 20%")]
WAIT = 20
ONE_WAY = common.COST / 2
OUT = config.OUTPUT_DIR


# ---------------------------------------------------------------- 참조 지수 (교체 주기 H, 상위 N)
def reference_index(D, rvol, ok, H, N, rng=None):
    """일간 수익률 시리즈와 교체 기록. 교체일 T의 상위 N → T+1 시가 매수 → T+H 종가 매도 → T+H 가 다음 교체일."""
    C, O = D.C.values, D.O.values
    days = D.days
    start = days.searchsorted(pd.Timestamp(config.STUDY_START))
    rv = rvol.values
    okv = ok.values
    rets, dates, recs, rand_rets = [], [], [], []
    i = start
    while i + 1 < len(days):
        row = rv[i].copy()
        row[~okv[i]] = np.nan
        row[np.isnan(O[i + 1])] = np.nan
        order = np.argsort(-row)
        order = order[~np.isnan(row[order])]
        if len(order) < N:
            i += H
            continue
        picks = order[:N]
        end = min(i + H, len(days) - 1)
        path = C[i + 1:end + 1, picks] / O[i + 1, picks]          # (k, N) 가치 경로, 진입 = T+1 시가
        v = np.nanmean(path, axis=1)
        v = np.concatenate([[1.0], v])
        r = v[1:] / v[:-1] - 1
        r[0] -= common.COST                                       # 왕복 비용은 진입일에
        rets.append(r)
        dates.append(days[i + 1:end + 1])
        per = v[-1] - 1 - common.COST
        rec = {"signal": days[i], "entry": days[i + 1], "exit": days[end], "n": len(picks), "ret": per,
               "syms": " ".join(D.syms[p] for p in picks), "period": D.period.iloc[i]}
        if rng is not None:
            pool = np.flatnonzero(okv[i] & ~np.isnan(O[i + 1]) & ~np.isnan(C[end]))
            samp = pool[rng.integers(0, len(pool), size=(NRAND, N))]
            rr = (C[end][samp] / O[i + 1][samp]).mean(axis=1) - 1 - common.COST
            rand_rets.append(rr)
        recs.append(rec)
        i = end
    r = pd.Series(np.concatenate(rets), index=pd.DatetimeIndex(np.concatenate([d.values for d in dates])))
    R = pd.DataFrame(recs)
    if rand_rets:
        R["rand"] = list(np.array(rand_rets))
    return r, R


# ---------------------------------------------------------------- 사다리
def ladder(ref_r):
    """참조 지수 일간 수익률 → (비중, 전략 일간 수익률, 이벤트). 판정은 t−1 종가까지의 낙폭, 비중은 t 부터."""
    eq = (1 + ref_r).cumprod()
    dd = eq / eq.cummax() - 1
    n = len(ref_r)
    expo = np.ones(n)
    strat = np.zeros(n)
    events = []
    e = 1.0
    hit = [False] * len(LADDER)
    last = 0
    for t in range(n):
        if t > 0:
            d = dd.iloc[t - 1]
            new_e, label = None, None
            if d >= 0:
                if hit != [False] * len(LADDER):
                    hit = [False] * len(LADDER)
                    if e != 1.0:
                        new_e, label = 1.0, "새 고점 → 초기화"
            else:
                for k, (th, ex, lab) in enumerate(LADDER):
                    if d <= th and not hit[k]:
                        hit[k] = True
                        new_e, label = ex, lab
                        break
                if new_e is None and e != 1.0 and t - 1 - last >= WAIT:
                    new_e, label = 1.0, f"{WAIT}일 무변화 → 100%"
            if new_e is not None:
                cost = abs(new_e - e) * ONE_WAY
                events.append({"day": ref_r.index[t], "dd": d, "from": e, "to": new_e, "what": label})
                e = new_e
                last = t
                strat[t] = e * ref_r.iloc[t] - cost
                expo[t] = e
                continue
        expo[t] = e
        strat[t] = e * ref_r.iloc[t]
    return pd.Series(expo, index=ref_r.index), pd.Series(strat, index=ref_r.index), pd.DataFrame(events)


# ---------------------------------------------------------------- 통계
def stats(r):
    r = r.dropna()
    n = len(r)
    if n < 60:
        return None
    eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    w20 = (eq / eq.shift(20) - 1).min()
    return {"n": n, "cagr": cagr, "vol": vol, "sharpe": cagr / vol if vol > 0 else np.nan, "mdd": mdd, "w20": w20, "final": eq.iloc[-1]}


def srow(name, s, extra=""):
    if s is None:
        return f"| {name} | — |"
    return (f"| {name} | {s['n']} | **{s['cagr'] * 100:+.1f}%** | {s['vol'] * 100:.1f}% | {s['sharpe']:.2f} | **{s['mdd'] * 100:.0f}%** | "
            f"{s['w20'] * 100:+.1f}% | ${s['final'] * 10000:,.0f} |{extra}")


HEAD = ("| 전략 | 거래일 | 연환산 | 연변동성 | 샤프 | 최대 낙폭 | 최악 20일 | $10,000 → |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")


def by_period(D, r):
    p = D.period.reindex(r.index)
    return {"전체": r, "탐색 ~2022": r[p == "탐색 ~2022"], "검증 2023~": r[p == "검증 2023~"]}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    C, V = D.C, D.V
    ok = D.valid & D.study.values[:, None]
    dv = C * V
    rvol = dv / dv.shift(1).rolling(20).mean()
    spy_c = D.spy["Close"].reindex(D.days)
    spy_r = spy_c / spy_c.shift(1) - 1
    rng = np.random.default_rng(config.SEED)

    md = ["# r06 — 관심 종목 5개 + 낙폭 사다리", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {D.days.max().date()}. 종목 = 거래대금 RVOL 상위 N (방향 무관), 동일 비중, T+1 시가 매수 → T+H 종가 매도 → 같은 날 다시 선정. "
          "낙폭은 100% 투자 참조 지수의 고점 대비. 사다리: −20% → 50% · −30% → 100% 재매수 · −40% → 20% · 마지막 변경 뒤 20거래일 다음 단계 없음 → 100% · 새 고점 → 초기화. "
          "각 단계는 새 고점 전까지 한 번. 판정은 전날 종가, 비중은 다음 날부터. 비용 교체 왕복 0.2% + 비중 변경 편도 0.1%. 현금 수익 0.", "",
          "채택 = 탐색·검증 양쪽에서 사다리가 참조 지수보다 연환산 높고 최대 낙폭 작음. 교체 주기는 탐색 구간의 사다리(N=5) 연환산 1등 하나만 검증에 쓴다.", ""]

    results = {}
    for N in NS:
        for H in HS:
            ref_r, R = reference_index(D, rvol, ok, H, N, rng)
            expo, st_r, ev = ladder(ref_r)
            results[(N, H)] = {"ref": ref_r, "strat": st_r, "expo": expo, "ev": ev, "R": R}

    # 1. 교체 주기 × 구간
    md += ["## 1. 교체 주기 — 참조 지수와 사다리, 탐색·검증", "",
           "| N | H | 구간 | 참조 연환산 | 참조 낙폭 | 사다리 연환산 | 사다리 낙폭 | 차이(연환산) | 차이(낙폭) | 무작위 N 이긴 비율(참조) | SPY 연환산 | SPY 낙폭 | 사다리 이벤트 수 |",
           "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    pick = {}
    for N in NS:
        best = None
        for H in HS:
            x = results[(N, H)]
            R = x["R"]
            for lab, rr in by_period(D, x["ref"]).items():
                sr = stats(rr)
                ss = stats(x["strat"].reindex(rr.index))
                sp = stats(spy_r.reindex(rr.index))
                if sr is None:
                    continue
                sub = R if lab == "전체" else R[R.period == lab]
                if "rand" in R and len(sub):
                    rand_final = np.prod(1 + np.array(list(sub["rand"])), axis=0)
                    ref_final = np.prod(1 + sub["ret"].values)
                    rp = f"{(rand_final < ref_final).mean():.0%}"
                else:
                    rp = "—"
                nev = int(((x["ev"].day >= rr.index.min()) & (x["ev"].day <= rr.index.max())).sum()) if len(x["ev"]) else 0
                md.append(f"| {N} | {H} | {lab} | {sr['cagr'] * 100:+.1f}% | {sr['mdd'] * 100:.0f}% | **{ss['cagr'] * 100:+.1f}%** | **{ss['mdd'] * 100:.0f}%** | "
                          f"{(ss['cagr'] - sr['cagr']) * 100:+.1f}%p | {(ss['mdd'] - sr['mdd']) * 100:+.0f}%p | {rp} | {sp['cagr'] * 100:+.1f}% | {sp['mdd'] * 100:.0f}% | {nev} |")
                if lab == "탐색 ~2022" and (best is None or ss["cagr"] > best[1]):
                    best = (H, ss["cagr"])
        pick[N] = best[0]
        md.append(f"| {N} | | **탐색 1등 H = {best[0]}** (사다리 연환산 {best[1] * 100:+.1f}%) | | | | | | | | | | |")
    md.append("")

    # 2. 선택된 H 의 판정
    md += ["## 2. 판정 — 탐색에서 고른 교체 주기로 검증", ""]
    verdicts = []
    for N in NS:
        H = pick[N]
        x = results[(N, H)]
        md += [f"### N = {N}, H = {H}", "", HEAD]
        ok_both = True
        for lab, rr in by_period(D, x["ref"]).items():
            sr, ss = stats(rr), stats(x["strat"].reindex(rr.index))
            sp = stats(spy_r.reindex(rr.index))
            spy_e, spy_s, _ = ladder(spy_r.reindex(rr.index).fillna(0))
            sps = stats(spy_s)
            md.append(srow(f"{lab} · 참조 지수 (조절 없음)", sr))
            md.append(srow(f"{lab} · **사다리**", ss))
            md.append(srow(f"{lab} · SPY", sp))
            md.append(srow(f"{lab} · SPY + 같은 사다리", sps))
            if lab != "전체":
                ok_both &= (ss["cagr"] > sr["cagr"]) and (ss["mdd"] > sr["mdd"])
        verdicts.append((N, H, ok_both))
        md += ["", f"**판정 N={N}:** {'통과' if ok_both else '미통과'} — 탐색·검증 양쪽에서 참조 지수보다 연환산 높고 낙폭 작아야 통과.", ""]

    # 3. 이벤트 표 (N=5, 선택 H)
    N, H = 5, pick[5]
    x = results[(N, H)]
    ev = x["ev"].copy()
    ref_eq = (1 + x["ref"]).cumprod()
    md += [f"## 3. 사다리가 실제로 움직인 날 — N=5, H={H}", "",
           "뒤 20일·60일 = 그 날부터 참조 지수(100% 보유)가 움직인 폭. 비중을 줄였을 때 참조가 더 내렸으면 축소가 맞았고, 올랐으면 놓친 것.", "",
           "| 날짜 | 판정 낙폭 | 비중 | 무엇 | 참조 뒤 20일 | 참조 뒤 60일 | SPY 고점 대비 그날 |", "| --- | ---: | ---: | --- | ---: | ---: | ---: |"]
    spy_dd = spy_c / spy_c.cummax() - 1
    for _, e in ev.iterrows():
        t = ref_eq.index.get_loc(e.day)
        f20 = ref_eq.iloc[min(t + 20, len(ref_eq) - 1)] / ref_eq.iloc[t] - 1
        f60 = ref_eq.iloc[min(t + 60, len(ref_eq) - 1)] / ref_eq.iloc[t] - 1
        md.append(f"| {e.day.date()} | {e.dd * 100:.0f}% | {e['from']:.0%} → {e.to:.0%} | {e.what} | {f20 * 100:+.1f}% | {f60 * 100:+.1f}% | {spy_dd.loc[e.day] * 100:.0f}% |")
    counts = ev.what.value_counts() if len(ev) else pd.Series(dtype=int)
    md += ["", "이벤트 수: " + (" · ".join(f"{k} {v}회" for k, v in counts.items()) if len(counts) else "없음"),
           f"현금 비중이 있던 날 비율: {(x['expo'] < 1).mean():.0%} (탐색 {(x['expo'][D.period.reindex(x['expo'].index) == '탐색 ~2022'] < 1).mean():.0%} · 검증 {(x['expo'][D.period.reindex(x['expo'].index) == '검증 2023~'] < 1).mean():.0%})", ""]

    # 4. 참조 지수 낙폭 분포 — 왜 단계가 이만큼 걸리나
    md += ["## 4. 참조 지수의 낙폭 — 단계별 도달 횟수 (N=5 · N=10, H별)", "",
           "| N | H | 고점 대비 −10% | −20% | −30% | −40% | 최대 낙폭 | 연환산 |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for N in NS:
        for H in HS:
            rr = results[(N, H)]["ref"]
            eq = (1 + rr).cumprod(); dd = eq / eq.cummax() - 1
            cnt = []
            for th in (-0.10, -0.20, -0.30, -0.40):
                n_ep, inep = 0, False
                for v in dd.values:
                    if not inep and v <= th:
                        inep, n_ep = True, n_ep + 1
                    elif inep and v >= 0:
                        inep = False
                cnt.append(n_ep)
            s = stats(rr)
            md.append(f"| {N} | {H} | {cnt[0]} | {cnt[1]} | {cnt[2]} | {cnt[3]} | {dd.min() * 100:.0f}% | {s['cagr'] * 100:+.1f}% |")
    md.append("")

    # 5. 연도별 (N=5, 선택 H)
    x = results[(5, pick[5])]
    yr = pd.DataFrame({"ref": x["ref"], "strat": x["strat"], "spy": spy_r.reindex(x["ref"].index)}).groupby(x["ref"].index.year).apply(lambda g: (1 + g).prod() - 1)
    md += [f"## 5. 연도별 — N=5, H={pick[5]} (참조 / 사다리 / SPY)", "",
           " · ".join(f"{y}: {r.ref * 100:+.0f}% / {r.strat * 100:+.0f}% / {r.spy * 100:+.0f}%" for y, r in yr.iterrows()), ""]

    # 결론 자리
    md += ["## 결론", "", "(계획 문서 8절에 요약)", ""]

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "r06_regime.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    x = results[(5, pick[5])]
    pd.DataFrame({"ref_r": x["ref"], "exposure": x["expo"], "strat_r": x["strat"], "spy_r": spy_r.reindex(x["ref"].index)}).to_csv(os.path.join(OUT, "r06_daily.csv"), index_label="day")
    x["ev"].to_csv(os.path.join(OUT, "r06_events.csv"), index=False)
    x["R"].drop(columns=["rand"], errors="ignore").to_csv(os.path.join(OUT, "r06_rebalances.csv"), index=False)
    print("\n".join(md))
    print("\nverdicts:", verdicts, "pick:", pick)


if __name__ == "__main__":
    main()
