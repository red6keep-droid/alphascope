"""결과 → output/results.md (사람이 읽는 표) · output/events.csv (신호 목록)."""

import os

import pandas as pd

import config
import study

R = config.RULE


def pct(x, d=1):
    return "—" if x is None or x != x else f"{x * 100:+.{d}f}%" if x < 0 or d == 2 else f"{x * 100:.{d}f}%"


def spct(x):
    return "—" if x is None or x != x else f"{x * 100:+.2f}%"


def pval(p):
    if p is None or p != p:
        return "—"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def cells_table(cells, title=None):
    lines = []
    if title:
        lines.append(f"**{title}**\n")
    lines.append("| 보유 방식 | N | 승률 (95% 구간) | 무작위 날 승률 | p | 평균 순수익 | 중앙값 | SPY 대비 초과 | 초과 승률 |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|")
    for c in cells:
        n = f"{c['n']:,}" + (" ⚠" if c["thin"] else "")
        lines.append(
            f"| {study.OUTCOME_LABEL[c['outcome']]} | {n} | {pct(c['win'])} ({pct(c['win_lo'], 0)}~{pct(c['win_hi'], 0)}) "
            f"| {pct(c['base_win'])} | {pval(c['p_win'])} | {spct(c['mean'])} | {spct(c['median'])} "
            f"| {spct(c['excess'])} | {pct(c['excess_win'])} |")
    return "\n".join(lines) + "\n"


def render(res, path_md, path_csv):
    ev = res["events"]
    L = []
    L.append("# 신호 스터디 — 조건 충족 상승 뒤 매수했을 때의 수익 확률\n")
    L.append(f"기준: {res['day_min'].date()} ~ {res['day_max'].date()} · 종목 {res['n_symbols']}개 (현재 S&P 500) · "
             f"신호 {len(ev):,}건 · 진입 = 신호일 다음 거래일 시가 · 왕복 비용 {config.COST_ROUND_TRIP:.1%}\n")
    L.append("## 규칙 (MRH Signal Engine 6~10장 그대로)\n")
    L.append(f"- 당일 상승률 {R['ret1_min']:+.0%} ~ {R['ret1_max']:+.0%}\n"
             f"- RVOL(직전 {R['rvol_lookback']}거래일 평균 대비 거래량) ≥ {R['rvol_min']}\n"
             f"- 종가가 당일 고저 범위의 상위 {100 - R['close_pos_min'] * 100:.0f}%\n"
             f"- 소속 섹터 ETF 종가 > {R['sector_ma']}일선\n"
             f"- 최근 5거래일 누적 상승 < {R['ret5_max']:+.0%}\n"
             f"- 같은 종목 {config.CLUSTER_GAP}거래일 안 재발생은 한 건\n")
    L.append("## 읽는 법\n")
    L.append("- **승률**: 비용을 뺀 뒤 0보다 크면 승리. 괄호는 95% 신뢰구간.\n"
             "- **무작위 날 승률**: 같은 종목의 조건이 없던 날을 같은 수만큼 샀을 때의 승률(1,000회 재추출 평균). "
             "승률 자체가 아니라 **이 값과의 차이**가 조건의 효과다.\n"
             "- **p**: 무작위로 골라도 관측 승률 이상이 나올 확률(단측). 0.05 아래면 우연으로 보기 어렵다.\n"
             "- **SPY 대비 초과**: 같은 날 SPY를 샀다 팔았을 때보다 얼마나 더 벌었나(비용 전). 시장 전체가 오른 덕인지 가려 준다.\n"
             "- ⚠ = 표본 30건 미만. 숫자를 믿지 말 것.\n")

    L.append("## 1. 기간별\n")
    L.append(f"탐색/검증은 {config.SPLIT_DAY} 기준으로 나눴다. 규칙을 손볼 때는 탐색 구간만 보고, 검증 구간은 마지막에 한 번만 본다.\n")
    for title, cells in res["by_period"].items():
        L.append(cells_table(cells, title))

    L.append("## 2. 시장 국면별 (전체 기간)\n")
    L.append(f"RISK ON = 신호일에 VIX < {config.REGIME_VIX_MAX:.0f} 이고 SPY 종가 > {config.REGIME_SPY_MA}일선.\n")
    for title, cells in res["by_regime"].items():
        L.append(cells_table(cells, title))

    L.append("## 3. 실적 발표 인접 여부 (전체 기간)\n")
    L.append("실적 발표일 ±1거래일(주말 포함 3일) 안의 신호는 성격이 다르다 — 갭의 원인이 실적이다.\n")
    for title, cells in res["by_earnings"].items():
        L.append(cells_table(cells, title))

    L.append("## 4. 조건 하나씩 빼 보기 (전체 기간)\n")
    L.append("어떤 조건이 실제로 확률을 올리는지. 빼도 승률이 같으면 그 조건은 표본만 줄인다.\n")
    L.append("| 변형 | 신호 N | 5일 승률 | 무작위 | p | 5일 평균 | 손절/목표 승률 | 무작위 | p | 손절/목표 평균 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, a in res["ablation"].items():
        by = {c["outcome"]: c for c in a["cells"]}
        h5, br = by.get("h5"), by.get("br")
        f = lambda c, k, fn: fn(c[k]) if c else "—"  # noqa: E731
        L.append(f"| {name} | {a['n']:,} | {f(h5, 'win', pct)} | {f(h5, 'base_win', pct)} | {f(h5, 'p_win', pval)} | {f(h5, 'mean', spct)} "
                 f"| {f(br, 'win', pct)} | {f(br, 'base_win', pct)} | {f(br, 'p_win', pval)} | {f(br, 'mean', spct)} |")
    L.append("")

    L.append("## 5. 손절/목표 방식 — 어떻게 끝났나\n")
    L.append("| 청산 사유 | N | 비율 | 평균 수익(비용 전) | 평균 보유일 |")
    L.append("|---|---:|---:|---:|---:|")
    tot = sum(r["n"] for r in res["exit_reasons"]) or 1
    names = {"stop": "손절선 도달", "stop_gap": "손절선 아래로 갭", "target": "목표선 도달",
             "target_gap": "목표선 위로 갭", "timeout": f"{config.MAX_HOLD}일 만기 종가"}
    for r in sorted(res["exit_reasons"], key=lambda r: -r["n"]):
        L.append(f"| {names.get(r['exit_reason'], r['exit_reason'])} | {r['n']:,} | {r['n'] / tot * 100:.1f}% | {spct(r['mean'])} | {r['days']:.1f} |")
    L.append("")

    L.append("## 6. 연도별 (5일 보유)\n")
    L.append("| 연도 | N | 승률 | 평균 순수익 |")
    L.append("|---|---:|---:|---:|")
    for r in res["by_year"]:
        L.append(f"| {r['year']} | {r['n']:,} | {pct(r['win'])} | {spct(r['mean'])} |")
    L.append("")

    L.append("## 7. 섹터별 (5일 보유)\n")
    L.append("| 섹터 | N | 승률 | 평균 순수익 |")
    L.append("|---|---:|---:|---:|")
    for r in res["by_sector"]:
        L.append(f"| {r['sector']} | {r['n']:,} | {pct(r['win'])} | {spct(r['mean'])} |")
    L.append("")

    L.append("## 한계\n")
    L.append("- **생존 편향**: 유니버스가 *현재* S&P 500 이라 그 사이 상장폐지·인수·퇴출된 종목이 없다. 승률이 실제보다 좋게 나오는 방향이다.\n"
             "- **체결 가정**: 다음 날 시가 체결, 손절·목표는 그 가격에 정확히 체결. 실제는 더 나쁘다.\n"
             "- **섹터 ETF**: XLC(2018-06)·XLRE(2015-10) 상장 전에는 그 섹터 종목의 신호가 빠진다.\n"
             "- **실적일**: yfinance 값. 일부 종목은 누락될 수 있어 '실적 인접 아님'에 실적 신호가 조금 섞일 수 있다.\n"
             "- 이 문서는 과거 빈도다. 미래 확률이 아니다.\n")

    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    cols = ["day", "symbol", "sector", "period", "risk_on", "near_earnings",
            "ret1", "rvol", "close_pos", "ret5", "entry"] + \
           [f"ret_h{h}" for h in config.HORIZONS] + ["ret_br", "exit_d", "exit_reason"] + \
           [f"spy_h{h}" for h in config.HORIZONS] + ["spy_br"]
    ev[cols].sort_values("day").to_csv(path_csv, index=False, float_format="%.5f")
