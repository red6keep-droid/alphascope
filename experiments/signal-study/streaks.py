"""① 연속 상승 (계획 3절) — output/r01_timing_study.md

상승일 = 종가 > 전일 종가 (확정 2026-09-24). L_t = t 에서 끝나는 연속 상승일 수.
  ①-1 스트릭 분포          — 완성된 스트릭의 길이 분포 (시작일이 유효한 것만)
  ①-2 지속 확률            — P(다음 날 상승 | L_t = k) vs 무조건 P(상승)
  ①-3 첫날 크기별           — 첫날 상승률 구간별로 3일 · 5일까지 이어지는 비율
  ①-4 진입 위치별 성적      — L_t = k 확인 후 다음 날 시가 매수 × 보유 6개, 전 지표 · 분할 · 생존 편향
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

KS = [1, 2, 3, 4, 5]
MAG = [(0, 0.01, "+0~1%"), (0.01, 0.03, "+1~3%"), (0.03, 0.06, "+3~6%"), (0.06, 9, "+6%↑")]


def streak_len(C):
    up = (C > C.shift(1)).astype(int).values
    L = np.zeros_like(up)
    for i in range(1, len(up)):
        L[i] = np.where(up[i] == 1, L[i - 1] + 1, 0)
    return pd.DataFrame(L, index=C.index, columns=C.columns), pd.DataFrame(up.astype(bool), index=C.index, columns=C.columns)


def main(include_removed=False):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    reg_path = os.path.join(common.OUT, "r01_regime.pkl")
    D.regime = pd.read_pickle(reg_path) if os.path.exists(reg_path) else None
    L, up = streak_len(D.C)
    ok = D.signal_ok
    ret1 = D.C / D.C.shift(1) - 1
    md = ["# r01 ① 연속 상승", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {D.days.max().date()} · 전제 조건 1~7 적용 (계획 2절). 상승일 = 종가 > 전일 종가.", ""]

    # ①-1 스트릭 분포 — 스트릭 마지막 날 (다음 날 하락 또는 끝) 에서 길이를 센다. 시작일이 유효(SPY>200일선·편입 후)인 것만
    end = (L > 0) & ~up.shift(-1).fillna(False).astype(bool)
    start_ok = pd.DataFrame(False, index=D.days, columns=D.syms)
    # 시작일 = 끝 - (L-1). 벡터화: 시작일 유효 여부를 L 만큼 앞의 ok 로 본다 (최대 L 30 까지)
    okv = ok.values
    Lv = L.values
    ev = end.values
    n_syms = len(D.syms)
    lens = []
    for i, j in zip(*np.nonzero(ev)):
        s = i - Lv[i, j] + 1
        if s >= 0 and okv[s, j]:
            lens.append(Lv[i, j])
    lens = np.array(lens)
    md += ["## ①-1 스트릭 분포 — 연속 상승이 며칠 가나", "", f"유효 시작일 스트릭 {len(lens):,}개 (종목당 연 {len(lens) / n_syms / 10.7:.0f}개)", "",
           "| 길이 | 건수 | 비율 | 이상 누적 | 종목당 연간 |", "| ---: | ---: | ---: | ---: | ---: |"]
    for k in range(1, 11):
        n = int((lens == k).sum()); ge = int((lens >= k).sum())
        md.append(f"| {k}{'+' if k == 10 else ''} | {n if k < 10 else ge:,} | {(n if k < 10 else ge) / len(lens):.1%} | {ge / len(lens):.1%} | {ge / n_syms / 10.7:.1f} |")
    md.append("")

    # ①-2 지속 확률
    nxt = up.shift(-1)
    base_up = nxt.where(ok).stack().dropna().mean()
    md += ["## ①-2 지속 확률 — k일 연속 상승 뒤 다음 날도 오를 확률", "",
           f"무조건 P(다음 날 상승) = **{base_up:.1%}** (유효일 전체). 이 값보다 높으면 모멘텀, 낮으면 반전.", "",
           "| k | n | P(다음 날 상승) | 차이 %p | 탐색 ~2022 | 검증 2023~ | 다음 날 평균 수익 |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for k in range(1, 8):
        m = (L == k) & ok
        v = nxt.where(m).stack().dropna()
        r = ret1.shift(-1).where(m).stack().dropna()
        tr = nxt.where(m & (D.period == "탐색 ~2022").values[:, None]).stack().dropna().mean()
        te = nxt.where(m & (D.period == "검증 2023~").values[:, None]).stack().dropna().mean()
        md.append(f"| {k} | {len(v):,} | {v.mean():.1%} | **{(v.mean() - base_up) * 100:+.1f}** | {tr:.1%} | {te:.1%} | {r.mean() * 100:+.3f}% |")
    md.append("")
    # 하락 스트릭도 대칭으로
    dn = (D.C < D.C.shift(1))
    Ld, _ = streak_len(-D.C)
    md += ["대칭 확인 — k일 연속 **하락** 뒤 다음 날 상승 확률:", "", "| k | n | P(다음 날 상승) | 차이 %p |", "| ---: | ---: | ---: | ---: |"]
    for k in range(1, 6):
        m = (Ld == k) & ok
        v = nxt.where(m).stack().dropna()
        md.append(f"| {k} | {len(v):,} | {v.mean():.1%} | **{(v.mean() - base_up) * 100:+.1f}** |")
    md.append("")

    # ①-3 첫날 크기별
    md += ["## ①-3 첫날 상승 크기별 — 스트릭이 3일 · 5일까지 가는 비율", "",
           "첫날(L=1) 상승률 구간별. \"5일 연속 상승은 조용히 시작한다\"(인수인계)의 재확인.", "",
           "| 첫날 상승률 | n | 2일 이상 | 3일 이상 | 5일 이상 | 첫날 RVOL≥2 비율 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    first = (L == 1) & ok
    rvol = D.V / D.V.shift(1).rolling(20).mean()
    for lo, hi, lab in MAG:
        m = first & (ret1 >= lo) & (ret1 < hi)
        n = int(m.values.sum())
        if n == 0:
            continue
        r2 = ((L.shift(-1) >= 2) & m).values.sum() / n
        r3 = ((L.shift(-2) >= 3) & m).values.sum() / n
        r5 = ((L.shift(-4) >= 5) & m).values.sum() / n
        rv = (rvol.where(m) >= 2).values.sum() / n
        md.append(f"| {lab} | {n:,} | {r2:.1%} | {r3:.1%} | {r5:.1%} | {rv:.0%} |")
    md.append("")

    # ①-4 진입 위치별 성적
    md += ["## ①-4 진입 위치별 성적 — k일 연속 상승 확인 후 다음 날 시가 매수", "", common.LEGEND, ""]
    masks = {k: (L == k) & ok for k in KS}
    for k in KS:
        md += [f"**k = {k} (연속 {k}일째 마감 확인 후 진입)**", "", common.HEADER]
        for h in common.HORIZONS:
            m = common.cluster(masks[k], h)
            s = common.evaluate(D, m, h, placebo=True, seed=k * 100 + h)
            md.append(common.fmt_row(f"{h}일", s))
        md.append("")
    # 분할 — k=3, 5일·20일 보유 (전체 표본에서 가장 의미 있는 것을 고르지 않고 사전에 k=3 으로 고정)
    kk = 3
    for h in (5, 20):
        m = common.cluster(masks[kk], h)
        md += [f"### k = {kk} · {h}일 보유 — 분할", ""]
        md.append(common.split_table(D, m, h, D.period, "구간"))
        md.append(common.year_table(D, m, h) + "\n")
        md.append(common.split_table(D, m, h, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), "실적 인접"))
        md.append(common.split_table(D, m, h, D.vix_bucket, "공포 (VIX)"))
        md.append(common.split_table(D, m, h, D.rate_dir, "금리 방향 (10년 금리 20일 변화)"))
        if D.regime is not None:
            md.append(common.split_table(D, m, h, D.regime, "섹터 국면 (동일가중 RRG)"))
        sec_axis = pd.DataFrame(np.tile(np.array([D.sector[s] for s in D.syms]), (len(D.days), 1)), index=D.days, columns=D.syms)
        md.append(common.split_table(D, m, h, sec_axis, "섹터"))
    # k=1 실적 분할도 (급등 첫날이 실적인지)
    m = common.cluster(masks[1], 5)
    md += ["### k = 1 · 5일 보유 — 실적 인접 분할", ""]
    md.append(common.split_table(D, m, 5, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), "실적 인접"))

    # 생존 편향 — 제외 종목 포함
    md += ["## 생존 편향 측정 — 지수에서 빠진 종목 95개를 포함하면", "",
           "같은 규칙(k=1~5, 5일 보유)을 현재 500종목 / 제외 종목 포함으로 두 번. 차이가 편향의 크기다 (제외 종목은 편입~제외일 사이만).", "",
           "| k | 현재 500 승률 | 차이 %p | 포함 승률 | 차이 %p | 포함 n | 승률 변화 |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    D2 = common.load(include_removed=True)
    L2, _ = streak_len(D2.C)
    for k in KS:
        s1 = common.evaluate(D, common.cluster(masks[k], 5), 5)
        s2 = common.evaluate(D2, common.cluster((L2 == k) & D2.signal_ok, 5), 5)
        md.append(f"| {k} | {s1['win']:.1%} | {s1['diff'] * 100:+.1f} | {s2['win']:.1%} | {s2['diff'] * 100:+.1f} | {s2['n']:,} | {(s2['win'] - s1['win']) * 100:+.2f} |")
    md += ["", "제외 종목 중 인수·합병으로 사라진 114개는 데이터가 없어 여기에도 빠져 있다. 이 표의 변화는 편향의 **하한**이다.", ""]

    path = os.path.join(common.OUT, "r01_timing_study.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"→ {path}")


if __name__ == "__main__":
    main()
