"""r03 — 승자의 사전 특징. output/r03_winners.md

질문: 분기 시작일에 알 수 있던 값으로, 그 분기(60거래일) 수익률 상위 20% 종목을 미리 가려낼 수 있나.
  W-1 지속성        분기 상위 20% → 다음 분기 상위 20% 확률 (전이 행렬), 연간도
  W-2 특징별 적중률  특징 상위/하위 20% 를 뽑았을 때 실제 상위 20% 에 든 비율 (기준 20%) · 순위 상관(IC) · 탐색/검증
  W-3 조합          탐색 구간에서 통과한 특징의 순위 평균 → 상위 100 → 검증 구간 적중률 · 수익 · 분기별 일관성
  W-4 승자의 모습    실제 상위 20% 가 시작일에 어땠나 — 특징 중앙값 승자 vs 나머지
  W-5 연결          W-3 상위 100 안에서 P3(3일 하락 뒤 첫 상승) 진입 · 하루 ≤ 10 개 → r02 와 비교

특징은 전부 시작일 t 까지의 데이터로만. 실적은 발표일 < t 인 것만. 결과를 보기 전에 고정 (2026-09-24).
제외 종목 95 개도 유니버스에 넣는다(가격 특징만 있음, 성장 특징은 NaN → 순위 0.5).
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

H_MAIN, H_AUX = 60, 250
TOP = 0.20
N_PICK = 100
MIN_HIST = 260
ADOPT_HIT = 0.05          # 적중률 +5%p
ADOPT_T = 2.0             # 분기별 IC 의 t


def quarter_starts(days):
    q = pd.Series(days).groupby([days.year, days.quarter]).first()
    return pd.DatetimeIndex([d for d in q if d >= pd.Timestamp(config.STUDY_START)])


def price_features(D, t, i):
    """t = 시작일, i = 그 위치. 모든 종목의 특징 dict(Series)."""
    C, V = D.C, D.V
    spy = D.spy["Close"].reindex(D.days)
    c = C.iloc[: i + 1]
    r = c.pct_change()
    f = {}
    f["mom_1m"] = c.iloc[-1] / c.iloc[-22] - 1
    f["mom_3m"] = c.iloc[-1] / c.iloc[-64] - 1
    f["mom_6m"] = c.iloc[-1] / c.iloc[-127] - 1
    f["mom_12_1"] = c.iloc[-22] / c.iloc[-253] - 1
    f["rs_6m"] = f["mom_6m"] - (spy.iloc[i] / spy.iloc[i - 126] - 1)
    f["vol_3m"] = r.iloc[-63:].std()
    roll_max = c.iloc[-127:].cummax()
    f["mdd_6m"] = (c.iloc[-127:] / roll_max - 1).min()
    sr = spy.pct_change().iloc[i - 249: i + 1]
    rr = r.iloc[-250:]
    f["beta_1y"] = rr.apply(lambda s: s.cov(sr) / sr.var() if s.notna().sum() > 200 else np.nan)
    f["dist_52w"] = c.iloc[-1] / c.iloc[-252:].max() - 1
    ma200 = C.rolling(200).mean().iloc[i - 62: i + 1]
    f["above200_3m"] = (c.iloc[-63:] > ma200).mean()
    dv = (C * V).iloc[: i + 1]
    f["dvol_trend"] = dv.iloc[-21:].mean() / dv.iloc[-126:].mean() - 1
    sign = np.sign(r.iloc[-63:])
    f["flow_3m"] = (dv.iloc[-63:] * sign).sum() / dv.iloc[-63:].sum()
    return pd.DataFrame(f)


def growth_features(D, earn, t):
    """발표일 < t 인 실적만. EPS 전년비 · 4분기 서프라이즈 평균 · 연속 상회 · 직전 발표 반응."""
    out = {}
    C = D.C
    pos_t = D.days.searchsorted(t)
    for sym, g in earn.items():
        g = g[g["day"] < t]
        if len(g) < 2:
            continue
        last = g.iloc[-1]
        row = {"surp_avg4": g["surprise_pct"].iloc[-4:].mean(), "beat_streak": 0, "eps_yoy": np.nan, "last_react": np.nan}
        for v in g["surprise_pct"].iloc[::-1]:
            if pd.notna(v) and v > 0:
                row["beat_streak"] += 1
            else:
                break
        if len(g) >= 5 and pd.notna(last["eps_actual"]) and pd.notna(g["eps_actual"].iloc[-5]) and g["eps_actual"].iloc[-5] != 0:
            prev = g["eps_actual"].iloc[-5]
            row["eps_yoy"] = (last["eps_actual"] - prev) / abs(prev)
        p = D.days.searchsorted(last["day"])
        if 1 <= p < pos_t - 1 and sym in C:
            a, b = C[sym].iloc[p - 1], C[sym].iloc[p + 1]
            row["last_react"] = b / a - 1 if pd.notna(a) and pd.notna(b) and a > 0 else np.nan
        out[sym] = row
    return pd.DataFrame(out).T


FEATURES = {
    "mom_1m": "직전 1개월 수익률", "mom_3m": "직전 3개월 수익률", "mom_6m": "직전 6개월 수익률", "mom_12_1": "직전 12개월 (최근 1개월 제외)",
    "rs_6m": "6개월 SPY 대비", "vol_3m": "3개월 일간 변동성", "mdd_6m": "6개월 최대 낙폭", "beta_1y": "1년 베타",
    "dist_52w": "52주 고점 대비 거리", "above200_3m": "3개월 중 200일선 위 비율", "dvol_trend": "거래대금 1개월/6개월", "flow_3m": "3개월 상승−하락 거래대금 비율",
    "eps_yoy": "EPS 전년비 성장", "surp_avg4": "최근 4분기 서프라이즈 평균", "beat_streak": "연속 상회 분기 수", "last_react": "직전 실적 반응(2일)",
}
GROUP = {"mom": "모멘텀", "rs": "모멘텀", "vol": "변동성", "mdd": "변동성", "beta": "변동성", "dist": "추세 위치", "above": "추세 위치",
         "above200": "추세 위치", "dvol": "거래량", "flow": "거래량", "eps": "성장", "surp": "성장", "beat": "성장", "last": "성장"}


def build_panel(D, earn):
    qs = quarter_starts(D.days)
    rows = []
    C = D.C
    spy = D.spy["Close"].reindex(D.days)
    for t in qs:
        i = D.days.get_loc(t)
        if i < MIN_HIST:
            continue
        end = i + H_MAIN
        if end >= len(D.days):
            break
        valid = D.valid.iloc[i] & C.iloc[i].notna() & C.iloc[i - MIN_HIST + 1].notna()
        syms = valid[valid].index
        pf = price_features(D, t, i).loc[syms]
        gf = growth_features(D, earn, t).reindex(syms)
        fwd = C.iloc[end][syms] / C.iloc[i][syms] - 1
        fwd_aux = (C.iloc[i + H_AUX][syms] / C.iloc[i][syms] - 1) if i + H_AUX < len(D.days) else pd.Series(np.nan, index=syms)
        panel = pd.concat([pf, gf], axis=1)
        panel["fwd"] = fwd; panel["fwd_aux"] = fwd_aux
        panel["fwd_spy"] = spy.iloc[end] / spy.iloc[i] - 1
        panel["winner"] = (fwd.rank(pct=True) > 1 - TOP).astype(float)
        panel["winner_aux"] = (fwd_aux.rank(pct=True) > 1 - TOP).astype(float) if fwd_aux.notna().any() else np.nan
        panel["quintile"] = pd.qcut(fwd.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        panel["t"] = t
        panel["symbol"] = syms
        panel["sector"] = [D.sector.get(s, "Removed") for s in syms]
        panel["period"] = "탐색 ~2022" if t < pd.Timestamp(config.SPLIT_DAY) else "검증 2023~"
        panel["spy_ok"] = bool(D.spy_ok.iloc[i])
        rows.append(panel.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True)


def hit_table(P, feat, label="winner"):
    """특징 상위 20% / 하위 20% 를 뽑았을 때 적중률 · 평균 수익 · 분기별 IC."""
    res = {}
    for per in ["탐색 ~2022", "검증 2023~", "전체"]:
        sub = P if per == "전체" else P[P.period == per]
        hits_hi, hits_lo, ics, ret_hi = [], [], [], []
        for t, g in sub.groupby("t"):
            x = g[feat]
            if x.notna().sum() < 100:
                continue
            rk = x.rank(pct=True)
            hi, lo = g[rk > 0.8], g[rk <= 0.2]
            hits_hi.append(hi[label].mean()); hits_lo.append(lo[label].mean()); ret_hi.append(hi["fwd"].mean() - g["fwd"].mean())
            ics.append(x.rank().corr(g["fwd"].rank()))   # 스피어만 = 순위의 피어슨 (scipy 불필요)
        if not ics:
            res[per] = None; continue
        ics = np.array(ics)
        res[per] = {"q": len(ics), "hit_hi": np.mean(hits_hi), "hit_lo": np.mean(hits_lo), "ret_hi": np.mean(ret_hi),
                    "ic": ics.mean(), "ic_t": ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics))) if len(ics) > 2 else np.nan,
                    "q_beat": np.mean(np.array(hits_hi) > TOP)}
    return res


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load(include_removed=True)
    e = pd.read_csv(os.path.join(config.DATA_DIR, "earnings.csv"), parse_dates=["day"])
    earn = {s: g.sort_values("day") for s, g in e.groupby("symbol")}
    P = build_panel(D, earn)
    qs = sorted(P.t.unique())
    n_rem = (P.sector == "Removed").sum()
    md = ["# r03 — 승자의 사전 특징", "",
          f"분기 시작일 {len(qs)}개 ({pd.Timestamp(qs[0]).date()} ~ {pd.Timestamp(qs[-1]).date()}) × 종목 → {len(P):,}건 (제외 종목 {n_rem:,}건 포함). "
          f"라벨 = 시작일 종가 → {H_MAIN}거래일 뒤 종가 수익률 **상위 {TOP:.0%}** (보조 {H_AUX}일). 특징은 시작일까지의 값만, 실적은 발표일 < 시작일.",
          f"적중률 기준 = {TOP:.0%} (무작위). 채택 = 상위 20% 적중률 **+{ADOPT_HIT * 100:.0f}%p 이상**(즉 ≥ 25%) 이고 분기별 IC 의 t ≥ {ADOPT_T}, **탐색·검증 양쪽**.", ""]

    # W-1 지속성
    md += ["## W-1 지속성 — 이번 분기 상위 20%가 다음 분기에도 상위 20%인가", ""]
    piv = P.pivot(index="t", columns="symbol", values="quintile")
    cur, nxt = piv.iloc[:-1].stack().dropna(), piv.shift(-1).iloc[:-1].stack().dropna()
    both = pd.concat([cur.rename("now"), nxt.rename("next")], axis=1).dropna()
    tm = pd.crosstab(both["now"], both["next"], normalize="index")
    md += ["분기 → 다음 분기 전이 (행 = 이번 분기 5분위, 5 = 상위 20%; 열 = 다음 분기; 무작위 = 20%)", "",
           "| 이번 \\ 다음 | 1 (하위) | 2 | 3 | 4 | 5 (상위) |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for q in [1, 2, 3, 4, 5]:
        md.append(f"| {q} | " + " | ".join(f"{tm.loc[q, c]:.1%}" for c in [1, 2, 3, 4, 5]) + " |")
    p55 = tm.loc[5, 5]; p15 = tm.loc[1, 5]
    # 연간
    yrs = P[P.t.dt.quarter == 1].pivot(index="t", columns="symbol", values="fwd_aux")
    yq = yrs.rank(axis=1, pct=True) > 0.8
    yc, yn = yq.iloc[:-1].stack().dropna(), yq.shift(-1).iloc[:-1].stack().dropna()
    yb = pd.concat([yc.rename("now"), yn.rename("next")], axis=1).dropna()
    p_year = yb[yb["now"] == True]["next"].mean()
    md += ["", f"상위 20% → 다음 분기도 상위 20%: **{p55:.1%}** (무작위 20%). 하위 20% → 다음 분기 상위 20%: {p15:.1%}. "
           f"연간(1분기 시작 250일 라벨): 올해 상위 20% → 내년도 상위 20% **{p_year:.1%}**.", ""]

    # W-2 특징별
    md += ["## W-2 특징별 — 그 특징 상위 20%를 뽑으면 승자가 얼마나 들어 있나", "",
           "**적중↑** = 특징 상위 20% 중 승자 비율, **적중↓** = 특징 하위 20% 중 승자 비율 (둘 중 하나가 25% 넘으면 방향이 있는 것). **IC** = 분기별 순위 상관 평균, t = 그 t 통계량. **초과** = 특징 상위 20% 의 60일 수익 − 유니버스 평균. **이긴 분기** = 적중↑ > 20% 인 분기 비율.", ""]
    results = {}
    for feat in FEATURES:
        results[feat] = hit_table(P, feat)
    for per in ["탐색 ~2022", "검증 2023~"]:
        md += [f"**{per}**", "", "| 묶음 | 특징 | 분기 | 적중↑ | 적중↓ | 초과 (상위 20%) | IC | t | 이긴 분기 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for feat, name in FEATURES.items():
            r = results[feat][per]
            if r is None:
                continue
            grp = GROUP[feat.split("_")[0]]
            hi = f"**{r['hit_hi']:.1%}**" if r["hit_hi"] >= TOP + ADOPT_HIT else f"{r['hit_hi']:.1%}"
            lo = f"**{r['hit_lo']:.1%}**" if r["hit_lo"] >= TOP + ADOPT_HIT else f"{r['hit_lo']:.1%}"
            md.append(f"| {grp} | {name} | {r['q']} | {hi} | {lo} | {r['ret_hi'] * 100:+.2f}% | {r['ic']:+.3f} | {r['ic_t']:+.1f} | {r['q_beat']:.0%} |")
        md.append("")
    # 보조 라벨 250일 — 전체
    md += ["**보조 — 250일(1년) 라벨, 전체 기간** (윈도 겹침 있음, 방향 참고용)", "", "| 특징 | 적중↑ | 적중↓ | IC | t |", "| --- | ---: | ---: | ---: | ---: |"]
    Paux = P.dropna(subset=["winner_aux"]).assign(fwd=lambda d: d["fwd_aux"])
    for feat, name in FEATURES.items():
        r = hit_table(Paux, feat, label="winner_aux")["전체"]
        if r:
            md.append(f"| {name} | {r['hit_hi']:.1%} | {r['hit_lo']:.1%} | {r['ic']:+.3f} | {r['ic_t']:+.1f} |")
    md.append("")

    # 채택 — 탐색 구간 기준으로 방향과 통과 결정, 검증에서 확인
    passed = []
    for feat in FEATURES:
        tr, te = results[feat]["탐색 ~2022"], results[feat]["검증 2023~"]
        if tr is None or te is None:
            continue
        sign = 1 if tr["ic"] > 0 else -1
        tr_hit = tr["hit_hi"] if sign > 0 else tr["hit_lo"]
        te_hit = te["hit_hi"] if sign > 0 else te["hit_lo"]
        ok_tr = tr_hit >= TOP + ADOPT_HIT and abs(tr["ic_t"]) >= ADOPT_T
        ok_te = te_hit >= TOP + ADOPT_HIT and np.sign(te["ic"]) == sign
        passed.append((feat, sign, tr_hit, te_hit, ok_tr, ok_te))
    md += ["## 채택 판정 (탐색에서 방향·통과 → 검증에서 확인)", "", "| 특징 | 방향 | 탐색 적중 | 탐색 통과 | 검증 적중 | 검증 통과 | 판정 |", "| --- | --- | ---: | :-: | ---: | :-: | --- |"]
    adopted = []
    for feat, sign, trh, teh, oktr, okte in passed:
        verdict = "**채택**" if oktr and okte else ("탐색만" if oktr else ("검증만" if okte else "—"))
        if oktr and okte:
            adopted.append((feat, sign))
        md.append(f"| {FEATURES[feat]} | {'높을수록' if sign > 0 else '낮을수록'} | {trh:.1%} | {'○' if oktr else '×'} | {teh:.1%} | {'○' if okte else '×'} | {verdict} |")
    md.append("")

    # W-3 조합 — 탐색 통과 특징(검증 무관)의 순위 평균으로 만들고 검증에서 잰다 (검증을 보고 고르면 안 되므로 탐색 통과 기준)
    train_pass = [(f, s) for f, s, trh, teh, oktr, okte in passed if oktr]
    md += ["## W-3 조합 — 탐색 통과 특징의 순위 평균 → 상위 100종목", ""]
    if not train_pass:
        md += ["탐색 구간에서 통과한 특징이 없어 조합을 만들지 않는다.", ""]
    else:
        md.append("조합에 쓴 특징(탐색 통과): " + " · ".join(f"{FEATURES[f]}({'+' if s > 0 else '−'})" for f, s in train_pass) + "\n")
        score = pd.Series(0.0, index=P.index); cnt = pd.Series(0.0, index=P.index)
        for f, s in train_pass:
            rk = P.groupby("t")[f].rank(pct=True)
            rk = rk if s > 0 else 1 - rk
            score += rk.fillna(0.5); cnt += 1
        P["score"] = score / cnt
        P["score_rank"] = P.groupby("t")["score"].rank(ascending=False, method="first")
        top = P[P.score_rank <= N_PICK]
        md += ["| 구간 | 분기 | 상위 100 적중률 | 평균 60일 수익 | 유니버스 평균 | SPY | 이긴 분기(적중>20%) | 이긴 분기(수익>유니버스) |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for per in ["탐색 ~2022", "검증 2023~", "전체"]:
            sub = top if per == "전체" else top[top.period == per]
            uni = P if per == "전체" else P[P.period == per]
            byq = sub.groupby("t").agg(hit=("winner", "mean"), ret=("fwd", "mean"))
            uq = uni.groupby("t")["fwd"].mean()
            md.append(f"| {per} | {len(byq)} | **{sub.winner.mean():.1%}** | {sub.fwd.mean() * 100:+.2f}% | {uni.fwd.mean() * 100:+.2f}% | {uni.groupby('t').fwd_spy.first().mean() * 100:+.2f}% | {(byq.hit > TOP).mean():.0%} | {(byq.ret > uq.reindex(byq.index)).mean():.0%} |")
        md.append("")
        yq = top.assign(y=top.t.dt.year).groupby("y").agg(hit=("winner", "mean"), n=("winner", "size"))
        md.append("연도별 상위 100 적중률: " + " · ".join(f"{y}: {r.hit:.0%}" for y, r in yq.iterrows()) + "\n")
        # 상위 20·50 도
        md += ["| 상위 N | 탐색 적중 | 검증 적중 | 검증 평균 수익 |", "| ---: | ---: | ---: | ---: |"]
        for n in (10, 20, 50, 100):
            sub = P[P.score_rank <= n]
            md.append(f"| {n} | {sub[sub.period == '탐색 ~2022'].winner.mean():.1%} | {sub[sub.period == '검증 2023~'].winner.mean():.1%} | {sub[sub.period == '검증 2023~'].fwd.mean() * 100:+.2f}% |")
        md.append("")

    # W-4 승자의 모습
    md += ["## W-4 승자의 모습 — 시작일 시점 특징 중앙값, 승자 vs 나머지 (전체 기간)", "", "| 특징 | 승자 | 나머지 | 차이 |", "| --- | ---: | ---: | ---: |"]
    for feat, name in FEATURES.items():
        w, o = P[P.winner == 1][feat].median(), P[P.winner == 0][feat].median()
        fmt = (lambda v: f"{v * 100:+.1f}%") if feat not in ("beta_1y", "beat_streak", "surp_avg4") else (lambda v: f"{v:.2f}")
        md.append(f"| {name} | {fmt(w)} | {fmt(o)} | {fmt(w - o) if feat not in ('beta_1y', 'beat_streak', 'surp_avg4') else f'{w - o:+.2f}'} |")
    md.append("")
    # 섹터별 승자 비율
    sec = P.groupby("sector")["winner"].mean().sort_values(ascending=False)
    md += ["섹터별 승자 비율 (무작위 20%): " + " · ".join(f"{k} {v:.0%}" for k, v in sec.items()), ""]

    # W-5 연결 — 상위 100 유니버스 안에서 P3
    if train_pass:
        md += ["## W-5 연결 — 조합 상위 100 종목 안에서 P3(3일 하락 뒤 첫 상승) 진입", "", common.LEGEND, ""]
        D1 = common.load()
        in_top = pd.DataFrame(False, index=D1.days, columns=D1.syms)
        for t, g in top.groupby("t"):
            i = D1.days.get_loc(t)
            cols = [s for s in g.symbol if s in in_top.columns]
            in_top.iloc[i + 1: i + 1 + H_MAIN, [in_top.columns.get_loc(c) for c in cols]] = True
        C = D1.C
        dn = C < C.shift(1)
        v = dn.astype(int).values; Ld = np.zeros_like(v)
        for k in range(1, len(v)):
            Ld[k] = np.where(v[k] == 1, Ld[k - 1] + 1, 0)
        Ld = pd.DataFrame(Ld, index=C.index, columns=C.columns)
        p3 = (Ld.shift(1) == 3) & (C > C.shift(1))
        base_ok = D1.signal_ok.copy()
        for label, uni_mask in (("전체 500 (r02 와 같음)", base_ok), ("조합 상위 100 안", base_ok & in_top)):
            D1.signal_ok = uni_mask
            md += [f"**{label}** — 기준선은 같은 유니버스 안의 같은 종목 무작위 날", "", common.HEADER]
            for h in (3, 5, 10, 20):
                m = common.cluster(p3 & uni_mask, h)
                md.append(common.fmt_row(f"{h}일", common.evaluate(D1, m, h, placebo=True, seed=300 + h)))
            # 유니버스 자체 (무작위 날)
            s = common.evaluate(D1, common.cluster(uni_mask & (np.random.default_rng(config.SEED).random(uni_mask.shape) < 0.02), 20), 20)
            md.append(common.fmt_row("유니버스 무작위 2% 표본 · 20일", s))
            md.append("")
        D1.signal_ok = base_ok
        # 하루 10개 — 상위 100 안 P3 신호를 상대강도(6개월) 순으로 10개
        md += ["**상위 100 안 P3 신호가 하루 10개를 넘으면 6개월 상대강도 순 10개만 (5일 · 20일)**", "", common.HEADER]
        rs6 = C / C.shift(126) - 1
        sig = p3 & base_ok & in_top
        keep = pd.DataFrame(False, index=D1.days, columns=D1.syms)
        for i in np.flatnonzero(sig.values.any(axis=1)):
            row = sig.iloc[i]; cols = row[row].index
            if len(cols) > 10:
                cols = rs6.iloc[i][cols].sort_values(ascending=False).index[:10]
            keep.iloc[i, [keep.columns.get_loc(c) for c in cols]] = True
        D1.signal_ok = base_ok & in_top
        for h in (5, 20):
            md.append(common.fmt_row(f"{h}일", common.evaluate(D1, common.cluster(keep, h), h, placebo=True, seed=400 + h)))
        md.append("")

    os.makedirs(common.OUT, exist_ok=True)
    path = os.path.join(common.OUT, "r03_winners.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    P.to_pickle(os.path.join(common.OUT, "r03_panel.pkl"))
    print(f"→ {path}")


if __name__ == "__main__":
    main()
