"""r04 — 관심 종목(거래대금 급증 상위 10)의 매수·매도 타이밍. output/r04_attention.md

관심 종목 = 매일 거래대금 ÷ 직전 20일 평균(RVOL) 이 S&P 500 안에서 상위 10 (보조 20). 미디어 언급의 소급 대용치.
전제 조건 1(SPY 200일선)은 이 회차에서 제외 조건이 아니라 분할 축. 나머지 전제 조건 2~7 유지.

  A-1 진입 시점   T+1 시가 · T+2 · T+3 · 첫 눌림(T 뒤 첫 하락 마감 다음 날) · 재돌파(T 종가를 다시 넘은 다음 날)
  A-2 보유        1 · 2 · 3 · 5 · 10 · 20 · 40 + 첫 하락 마감 매도 · 5일선 이탈 매도 · 손절 −7 / 목표 +10
  A-3 방향        급증일 상승(+2%↑) / 하락(−2%↓) / 보합 × 실적 ±1일
  A-4 강도        RVOL 2~3 / 3~5 / 5↑ · 순위 1~3 / 4~10 / 11~20
  A-5 포트폴리오  10거래일마다 그날 상승 급증 상위 10 매수 → 10일 보유. 무작위 10종목 1,000개 · SPY 대비
  A-6 거시        (a) 보유 중 변수 변화와 수익의 동시 상관(섹터별) (b) 진입일 변수 20일 방향별 성적
                  (c) 급증 원인 — 시장·섹터가 함께 움직인 날 vs 종목 고유 (d) 200일선 × VIX 국면
규칙은 결과 전 고정 (2026-09-24).
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

TOP, TOP2 = 10, 20
HOLDS = [1, 2, 3, 5, 10, 20, 40]
UP, DN = 0.02, -0.02
REBAL = 10
NRAND = 1000


def add_h40(D):
    entry = D.O.shift(-1)
    D.fwd[40] = D.C.shift(-40) / entry - 1
    lo = D.L.shift(-1)
    for k in range(2, 41):
        lo = np.minimum(lo, D.L.shift(-k))
    D.mae[40] = lo / entry - 1
    so, sc = D.spy["Open"].reindex(D.days), D.spy["Close"].reindex(D.days)
    D.spy_fwd[40] = sc.shift(-40) / so.shift(-1) - 1


def first_event_mask(base, cond, max_d=10):
    """base 신호일 T 뒤 d=1..max_d 중 cond 가 처음 참인 날에 신호를 옮긴다 (그 다음 날 시가 진입)."""
    out = np.zeros(base.shape, dtype=bool)
    fired = np.zeros(base.shape, dtype=bool)          # 각 T 별로 이미 발동했는지 — T 기준 배열
    b = base.values
    c = cond.values
    for d in range(1, max_d + 1):
        cd = np.zeros_like(c); cd[:-d] = c[d:]          # cond at T+d, T 기준
        hit = b & cd & ~fired
        fired |= hit
        shifted = np.zeros_like(out); shifted[d:] = hit[:-d]   # 신호를 T+d 로 옮김
        out |= shifted
    return pd.DataFrame(out, index=base.index, columns=base.columns)


def macro_series(D):
    m = D.macro
    def close(k):
        return m[k]["Close"].reindex(D.days).ffill()
    return {
        "10년 금리": ("diff", close("^TNX")),
        "장단기 차": ("diff", close("^TNX") - close("^IRX")),
        "유가 WTI": ("pct", close("CL=F")),
        "금": ("pct", close("GC=F")),
        "구리": ("pct", close("HG=F")),
        "달러": ("pct", close("DX-Y.NYB")),
        "HYG/LQD": ("pct", close("HYG") / close("LQD")),
        "VIX": ("diff", D.vix.ffill()),
        "SPY": ("pct", D.spy["Close"].reindex(D.days)),
    }


def change(kind, s, a, b):
    """a→b (위치) 변화. diff 는 차, pct 는 비율."""
    return (s.shift(-b) - s.shift(-a)) if kind == "diff" else (s.shift(-b) / s.shift(-a) - 1)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    add_h40(D)
    C, O, V = D.C, D.O, D.V
    ok = D.valid & D.study.values[:, None]              # 전제 조건 1 완화
    D.signal_ok = ok
    dv = C * V
    rvol = dv / dv.shift(1).rolling(20).mean()
    rank = rvol.where(ok).rank(axis=1, ascending=False)
    top10 = (rank <= TOP) & ok
    top20 = (rank <= TOP2) & ok
    ret1 = C / C.shift(1) - 1
    up, dn = ret1 >= UP, ret1 <= DN
    flat = ~up & ~dn
    common.register_rule_exit(D, "rule_dn", C < C.shift(1))
    common.register_rule_exit(D, "rule_ma5", C < C.rolling(5).mean())
    common.register_stop_target(D, "br", config.STOP, config.TARGET)
    ma_axis = pd.Series(np.where(D.spy_ok, "SPY 200일선 위", "SPY 200일선 아래"), index=D.days)
    sec_axis = pd.DataFrame(np.tile(np.array([D.sector[s] for s in D.syms]), (len(D.days), 1)), index=D.days, columns=D.syms)
    EXIT_LAB = {"rule_dn": "첫 하락 마감 매도", "rule_ma5": "5일선 이탈 매도", "br": "손절 −7 / 목표 +10"}

    def block(title, mask, keys, seed, note=None):
        md = [f"**{title}**", ""] + ([note, ""] if note else []) + [common.HEADER]
        for k in keys:
            h = k if isinstance(k, int) else 20
            m = common.cluster(mask, h)
            s = common.evaluate(D, m, k, placebo=True, seed=seed + (k if isinstance(k, int) else 77))
            lab = f"{k}일" if isinstance(k, int) else EXIT_LAB[k]
            md.append(common.fmt_row(lab, s))
        return md + [""]

    n_days = int(ok.any(axis=1).sum())
    md = ["# r04 — 관심 종목(거래대금 급증 상위 10)의 매수·매도 타이밍", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {D.days.max().date()} ({n_days}거래일). 관심 종목 = 거래대금 RVOL 상위 {TOP} (보조 {TOP2}). "
          "**200일선 제외 없음** (분할 축). 편입일 이후 · 다음 날 시가 진입 · 비용 0.2% · 기준선 = 같은 종목 무작위 날.", "", common.LEGEND, ""]

    # 관심 종목의 모습
    t10 = top10.values
    md += ["## 관심 종목은 어떤 날인가", "",
           f"- 하루 {TOP}종목 × {n_days}일 = {int(t10.sum()):,}건. 종목당 연 {t10.sum() / len(D.syms) / 10.7:.1f}회",
           f"- 급증일 방향: 상승(+2%↑) {(top10 & up).values.sum() / t10.sum():.0%} · 하락(−2%↓) {(top10 & dn).values.sum() / t10.sum():.0%} · 보합 {(top10 & flat).values.sum() / t10.sum():.0%}",
           f"- 실적 ±1일: {(top10 & D.earn_adj).values.sum() / t10.sum():.0%} — 나머지가 실적 외 뉴스·이벤트",
           f"- RVOL 중앙값 {rvol.where(top10).stack().dropna().median():.1f}배 · 당일 변동 절대값 중앙값 {ret1.abs().where(top10).stack().dropna().median():.1%}",
           f"- 같은 종목이 이틀 연속 상위 10: {(top10 & top10.shift(1).fillna(False).astype(bool)).values.sum() / t10.sum():.0%}", ""]

    # A-3 먼저 (방향) — T+1 진입
    md += ["## A-3 급증일 방향별 — T+1 시가 진입", ""]
    for lab, m in (("상승 급증 (+2%↑)", top10 & up), ("하락 급증 (−2%↓)", top10 & dn), ("보합", top10 & flat), ("전체 상위 10", top10)):
        md += block(lab, m, HOLDS + ["rule_dn", "rule_ma5", "br"], seed=100)
    md += ["**상승 급증 × 실적 인접 (5일 · 20일)**", ""]
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & up, h), h, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), f"{h}일 보유"))
    md += ["**하락 급증 × 실적 인접 (5일 · 20일)**", ""]
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & dn, h), h, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), f"{h}일 보유"))

    # A-1 진입 시점 — 상승 급증 · 하락 급증 각각
    md += ["## A-1 진입 시점 — 같은 급증 사건에서 언제 사나", "",
           "신호일을 옮겨서 진입일을 바꾼다. 첫 눌림 = T 뒤 첫 하락 마감(≤10일) 다음 날 시가, 재돌파 = T 종가를 다시 넘은 첫 날(≤10일) 다음 날 시가. 기준선은 옮겨진 신호일 기준.", ""]
    pull = C < C.shift(1)
    for lab, base in (("상승 급증", top10 & up), ("하락 급증", top10 & dn)):
        # 재돌파: C[d] > C[T] 이고 C[d-1] <= C[T]. T 기준 비교라 루프
        rb = np.zeros(base.shape, dtype=bool); fired = np.zeros(base.shape, dtype=bool)
        cT = C.values; b = base.values
        for d in range(2, 11):
            cd = np.full_like(cT, np.nan); cd[:-d] = cT[d:]
            cp = np.full_like(cT, np.nan); cp[:-(d - 1)] = cT[d - 1:]
            hit = b & (cd > cT) & (cp <= cT) & ~fired
            fired |= hit
            sh = np.zeros_like(rb); sh[d:] = hit[:-d]; rb |= sh
        variants = {
            "T+1 시가": base,
            "T+2 시가": base.shift(1).fillna(False).astype(bool),
            "T+3 시가": base.shift(2).fillna(False).astype(bool),
            "첫 눌림 다음 날": first_event_mask(base, pull),
            "재돌파 다음 날": pd.DataFrame(rb, index=D.days, columns=D.syms),
        }
        for h in (5, 20):
            md += [f"**{lab} · {h}일 보유**", "", common.HEADER]
            for vlab, vm in variants.items():
                s = common.evaluate(D, common.cluster(vm & ok, h), h, placebo=True, seed=200 + h)
                md.append(common.fmt_row(vlab, s))
            md.append("")

    # A-4 강도
    md += ["## A-4 관심 강도 — 상승 급증, T+1 진입", ""]
    rv_axis = pd.DataFrame(np.select([rvol.values >= 5, rvol.values >= 3, rvol.values >= 2], ["RVOL 5↑", "RVOL 3~5", "RVOL 2~3"], "RVOL <2"), index=D.days, columns=D.syms)
    rk_axis = pd.DataFrame(np.select([rank.values <= 3, rank.values <= 10, rank.values <= 20], ["순위 1~3", "순위 4~10", "순위 11~20"], "그 외"), index=D.days, columns=D.syms)
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & up, h), h, rv_axis, f"RVOL 구간 · {h}일"))
        md.append(common.split_table(D, common.cluster(top20 & up, h), h, rk_axis, f"순위 구간 (상위 20 안) · {h}일"))

    # 분할 — 상승 급증 T+1, 5일·20일: 구간 · 연도 · 200일선 · VIX · 섹터
    md += ["## 분할 — 상승 급증 T+1 진입", ""]
    for h in (5, 20):
        m = common.cluster(top10 & up, h)
        md += [f"### {h}일 보유", ""]
        md.append(common.split_table(D, m, h, D.period, "구간"))
        md.append(common.year_table(D, m, h) + "\n")
        md.append(common.split_table(D, m, h, ma_axis, "SPY 200일선"))
        md.append(common.split_table(D, m, h, D.vix_bucket, "VIX"))
        md.append(common.split_table(D, m, h, sec_axis, "섹터"))

    # A-5 포트폴리오
    md += ["## A-5 포트폴리오 — 10거래일마다 상승 급증 상위 10 매수, 10일 보유", "",
           "교체일: 그날 RVOL 상위 20 중 상승 마감(+2%↑) 종목을 RVOL 순으로 10개 (5개 미만이면 그 회차 건너뜀). 다음 날 시가 매수 → 10거래일 뒤 종가 매도. 동일 비중, 왕복 0.2%. "
           f"대조: 같은 날 유효 종목에서 무작위 10개 × {NRAND:,} · SPY.", ""]
    fwd10 = D.fwd[10]
    rng = np.random.default_rng(config.SEED)
    start = D.days.searchsorted(pd.Timestamp(config.STUDY_START))
    rows = []
    for i in range(start, len(D.days) - 11, REBAL):
        row_ok = ok.iloc[i]
        cands = rvol.iloc[i][(top20.iloc[i] & up.iloc[i]).values].sort_values(ascending=False).index[:TOP]
        cands = [c for c in cands if pd.notna(fwd10.iloc[i][c])]
        pool = fwd10.iloc[i][row_ok.values].dropna()
        if len(cands) < 5 or len(pool) < 100:
            continue
        port = fwd10.iloc[i][cands].mean() - common.COST
        samp = pool.values[rng.integers(0, len(pool), size=(NRAND, TOP))].mean(axis=1) - common.COST
        # 하락 급증 대조 포트폴리오
        cd = rvol.iloc[i][(top20.iloc[i] & dn.iloc[i]).values].sort_values(ascending=False).index[:TOP]
        cd = [c for c in cd if pd.notna(fwd10.iloc[i][c])]
        port_dn = fwd10.iloc[i][cd].mean() - common.COST if len(cd) >= 5 else np.nan
        rows.append({"day": D.days[i], "n": len(cands), "port": port, "port_dn": port_dn, "rand_med": np.median(samp),
                     "pctile": (samp < port).mean(), "spy": D.spy_fwd[10].iloc[i], "spy_ok": bool(D.spy_ok.iloc[i]),
                     "period": D.period.iloc[i], "year": D.days[i].year})
    R = pd.DataFrame(rows)
    def port_stats(sub, col="port"):
        r = sub[col].dropna()
        if len(r) < 5:
            return None
        cum = (1 + r).prod() - 1
        yrs = len(r) * REBAL / 252
        eq = (1 + r).cumprod(); mdd = (eq / eq.cummax() - 1).min()
        return {"n": len(r), "win": (r > 0).mean(), "beat_rand": (sub.loc[r.index, "pctile"] > 0.5).mean() if col == "port" else np.nan,
                "pct_med": sub.loc[r.index, "pctile"].median() if col == "port" else np.nan,
                "beat_spy": (r > sub.loc[r.index, "spy"]).mean(), "mean": r.mean(), "cum": cum, "ann": (1 + cum) ** (1 / yrs) - 1 if yrs > 0 else np.nan,
                "mdd": mdd, "spy_cum": (1 + sub.loc[r.index, "spy"]).prod() - 1, "rand_cum": (1 + sub.loc[r.index, "rand_med"]).prod() - 1}
    md += ["| 구간 | 회차 | 회차 승률 | 무작위 중앙값 이긴 회차 | 무작위 백분위 중앙 | SPY 이긴 회차 | 회차 평균 | 누적 | 연환산 | 최대 낙폭 | SPY 누적 | 무작위 중앙 누적 |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for lab, sub in (("전체", R), ("탐색 ~2022", R[R.period == "탐색 ~2022"]), ("검증 2023~", R[R.period == "검증 2023~"]),
                     ("SPY 200일선 위", R[R.spy_ok]), ("SPY 200일선 아래", R[~R.spy_ok])):
        s = port_stats(sub)
        if s:
            md.append(f"| {lab} | {s['n']} | {s['win']:.0%} | **{s['beat_rand']:.0%}** | {s['pct_med']:.2f} | {s['beat_spy']:.0%} | {s['mean'] * 100:+.2f}% | {s['cum'] * 100:+.0f}% | {s['ann'] * 100:+.1f}% | {s['mdd'] * 100:.0f}% | {s['spy_cum'] * 100:+.0f}% | {s['rand_cum'] * 100:+.0f}% |")
    md += ["", "하락 급증 상위 10 (역발상 대조):", "", "| 구간 | 회차 | 회차 승률 | SPY 이긴 회차 | 회차 평균 | 누적 | 최대 낙폭 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for lab, sub in (("전체", R), ("탐색 ~2022", R[R.period == "탐색 ~2022"]), ("검증 2023~", R[R.period == "검증 2023~"])):
        s = port_stats(sub, "port_dn")
        if s:
            md.append(f"| {lab} | {s['n']} | {s['win']:.0%} | {s['beat_spy']:.0%} | {s['mean'] * 100:+.2f}% | {s['cum'] * 100:+.0f}% | {s['mdd'] * 100:.0f}% |")
    yr = R.groupby("year").apply(lambda g: pd.Series({"cum": (1 + g.port).prod() - 1, "spy": (1 + g.spy).prod() - 1, "beat": (g.pctile > 0.5).mean()}), include_groups=False)
    md += ["", "연도별 (포트폴리오 누적 / SPY 누적 / 무작위 이긴 회차): " + " · ".join(f"{y}: {r.cum * 100:+.0f}% / {r.spy * 100:+.0f}% / {r.beat:.0%}" for y, r in yr.iterrows()), ""]

    # A-6 거시
    MS = macro_series(D)
    md += ["## A-6 보유 중 수익과 다른 지표", ""]
    # (a) 동시 상관 — 상승 급증 T+1 진입, 20일 보유. 변수 변화 = 진입일(T+1) → 청산일(T+20)
    md += ["### A-6a 동시 상관 — 보유 20일 동안 변수 변화 ↔ 종목 수익 (상승 급증 관심 종목, 섹터별)", "",
           "값 = 상관계수. 금리·장단기·VIX 는 차, 나머지는 비율 변화. |r| ≥ 0.15 굵게. 이것은 **설명**이고 진입 판단이 아니다 (변수 변화는 보유 중에 일어난다).", ""]
    m20 = common.cluster(top10 & up, 20)
    r20 = D.fwd[20].where(m20)
    sectors = sorted(set(D.sector.values()))
    SH = {"Information Technology": "기술", "Financials": "금융", "Health Care": "헬스", "Consumer Discretionary": "경기소비", "Consumer Staples": "필수소비",
          "Energy": "에너지", "Industrials": "산업", "Materials": "소재", "Utilities": "유틸", "Real Estate": "부동산", "Communication Services": "통신"}
    md.append("| 변수 | 전체 | " + " | ".join(SH[s] for s in sectors) + " |")
    md.append("| --- | ---: | " + " | ".join("---:" for _ in sectors) + " |")
    stacked = r20.stack().dropna()
    for name, (kind, s) in MS.items():
        ch = change(kind, s, 1, 20)          # 진입일 T+1 → T+20
        chv = ch.reindex(stacked.index.get_level_values(0)).values
        df = pd.DataFrame({"r": stacked.values, "x": chv, "sec": [D.sector[k] for k in stacked.index.get_level_values(1)]}).dropna()
        cells = []
        c_all = df["r"].corr(df["x"])
        cells.append(f"**{c_all:+.2f}**" if abs(c_all) >= 0.15 else f"{c_all:+.2f}")
        for sec in sectors:
            g = df[df.sec == sec]
            c = g["r"].corr(g["x"]) if len(g) > 50 else np.nan
            cells.append("—" if np.isnan(c) else (f"**{c:+.2f}**" if abs(c) >= 0.15 else f"{c:+.2f}"))
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    md.append("")
    # (b) 사전 분할 — 진입일 시점 변수의 20일 방향
    md += ["### A-6b 사전 분할 — 급증일 시점 변수의 20일 방향별 성적 (상승 급증 T+1, 5일·20일)", "",
           "진입 판단에 쓸 수 있는 것. 변수가 직전 20일 동안 올랐나 내렸나로 나눈다.", ""]
    for h in (5, 20):
        m = common.cluster(top10 & up, h)
        lines = [f"**{h}일 보유**", "", "| 변수 | 방향 | n | 승률 | 기준선 | 차이 %p | 평균 | 이긴 날 / t |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for name, (kind, s) in MS.items():
            d20 = (s - s.shift(20)) if kind == "diff" else (s / s.shift(20) - 1)
            axis = pd.Series(np.where(d20 > 0, "상승", "하락"), index=D.days)
            for lab in ("상승", "하락"):
                st = common.evaluate(D, m & (axis == lab).values[:, None], h)
                if st:
                    dh = "—" if np.isnan(st["day_hit"]) else f"{st['day_hit']:.0%}"; dt = "—" if np.isnan(st["day_t"]) else f"{st['day_t']:.1f}"
                    lines.append(f"| {name} | {lab} | {st['n']:,}{common.flag(st['n'])} | {st['win']:.1%} | {st['base_win']:.1%} | **{st['diff'] * 100:+.1f}** | {st['mean'] * 100:+.2f}% | {dh} / {dt} |")
        md += lines + [""]
    # (c) 급증 원인 — 시장·섹터가 같이 움직인 날 vs 종목 고유
    spy_r = D.spy["Close"].reindex(D.days).pct_change()
    etf_r = pd.DataFrame({s: D.etf[D.sector[s]]["Close"].reindex(D.days).pct_change() if D.sector[s] in D.etf else np.nan for s in D.syms}, index=D.days)
    market_day = (spy_r.abs() >= 0.01).values[:, None] | (etf_r.abs() >= 0.015).values
    idio = ~market_day & (ret1.abs() >= 0.03)
    cause_axis = pd.DataFrame(np.where(idio.values if isinstance(idio, pd.DataFrame) else idio, "종목 고유 (시장·섹터 조용, 종목 ±3%↑)",
                                       np.where(market_day, "시장·섹터 동반 (SPY ±1% 또는 섹터 ETF ±1.5%)", "그 외")), index=D.days, columns=D.syms)
    md += ["### A-6c 급증 원인 — 시장·섹터가 함께 움직인 날 vs 종목 고유 급증", "",
           "종목 고유 급증이 \"뉴스 언급 종목\" 에 더 가깝다. 상승 급증 T+1 진입.", ""]
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & up, h), h, cause_axis, f"{h}일 보유"))
    md += ["하락 급증도 같은 분류 (역발상 — 종목 고유 악재 뒤 반등이 있나):", ""]
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & dn, h), h, cause_axis, f"{h}일 보유"))
    # (d) 국면 조합
    combo = pd.Series([f"{a} · {b}" for a, b in zip(ma_axis, D.vix_bucket)], index=D.days)
    md += ["### A-6d 국면 조합 — SPY 200일선 × VIX (상승 급증 T+1, 5일 · 20일). 칸이 얇으니 방향만.", ""]
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(top10 & up, h), h, combo, f"{h}일 보유"))

    os.makedirs(common.OUT, exist_ok=True)
    path = os.path.join(common.OUT, "r04_attention.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    R.to_csv(os.path.join(common.OUT, "r04_portfolio.csv"), index=False)
    print(f"→ {path}")


if __name__ == "__main__":
    main()
