"""데이터 점검 (계획 1절) — 검증 전 1회. output/r01_data_check.md

  - 하루 종가 변동 ±40% 초과
  - 거래량이 20일 평균의 20배 초과
  - 종목별 첫 거래일 · 편입일 · 결측
  - SPY 200일선 필터가 빼는 날 수, 편입일 필터가 빼는 (종목, 날) 수
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    C, V = D.C, D.V
    ret = C / C.shift(1) - 1
    big = ret.abs() > 0.40
    rv = V / V.shift(1).rolling(20).mean()
    vol20 = rv > 20
    study = D.study.values[:, None]

    md = ["# r01 데이터 점검", "", f"종목 {C.shape[1]} · 거래일 {len(D.days)} ({D.days.min().date()} ~ {D.days.max().date()}) · 집계 구간 {config.STUDY_START}~", ""]
    md += ["## 하루 ±40% 초과 변동 (집계 구간)", ""]
    idx = np.argwhere(big.values & study)
    md.append(f"{len(idx)}건")
    md += ["", "| 날짜 | 종목 | 변동 | 비고 |", "| --- | --- | ---: | --- |"]
    for i, j in idx[:60]:
        s = C.columns[j]
        md.append(f"| {D.days[i].date()} | {s} | {ret.iat[i, j]:+.0%} | {'실적 인접' if D.earn_adj.iat[i, j] else ''} |")
    md += ["", "## 거래량 20일 평균의 20배 초과 (집계 구간)", ""]
    idx2 = np.argwhere(vol20.values & study)
    md.append(f"{len(idx2)}건 — 분할 근처 거래량 미조정이면 RVOL 이 튄다")
    md += ["", "| 날짜 | 종목 | 배수 | 종가 변동 |", "| --- | --- | ---: | ---: |"]
    for i, j in idx2[:40]:
        md.append(f"| {D.days[i].date()} | {C.columns[j]} | {rv.iat[i, j]:.0f}× | {ret.iat[i, j]:+.1%} |")

    first = C.apply(lambda s: s.first_valid_index())
    uni = pd.read_csv(os.path.join(config.DATA_DIR, "universe.csv"), parse_dates=["added"]).set_index("symbol")
    late = first[first > pd.Timestamp(config.STUDY_START)].sort_values()
    md += ["", "## 2016년 이후 첫 거래일인 종목 (신규 상장·분사)", "", f"{len(late)}종목", "",
           "| 종목 | 첫 거래일 | 편입일 |", "| --- | --- | --- |"]
    for s, d in late.items():
        md.append(f"| {s} | {d.date()} | {uni.loc[s, 'added'].date() if s in uni.index else ''} |")

    gaps = []
    for s in C.columns:
        v = C[s].dropna()
        d = v.index.to_series().diff().dt.days
        if (d > 7).any():
            gaps.append((s, int((d > 7).sum()), int(d.max())))
    md += ["", "## 7일 넘는 결측 구간이 있는 종목", "", f"{len(gaps)}종목", ""]
    if gaps:
        md += ["| 종목 | 구간 수 | 최대 일수 |", "| --- | ---: | ---: |"] + [f"| {s} | {n} | {mx} |" for s, n, mx in gaps]

    n_study = int(D.study.sum())
    n_spy_off = int((D.study & ~D.spy_ok).sum())
    cell_all = int((D.C.notna().values & study).sum())
    cell_valid = int((D.valid.values & study).sum())
    cell_sig = int(D.signal_ok.values.sum())
    md += ["", "## 전제 조건이 빼는 양", "",
           f"- SPY 200일선 아래: {n_spy_off}일 / {n_study}일 ({n_spy_off / n_study:.0%})",
           f"- 편입일 전 (종목, 날): {cell_all - cell_valid:,} / {cell_all:,} ({(cell_all - cell_valid) / cell_all:.0%})",
           f"- 둘 다 적용 후 신호 가능한 (종목, 날): {cell_sig:,} ({cell_sig / cell_all:.0%})",
           f"- 실적 ±1일에 해당하는 (종목, 날): {int((D.earn_adj.values & D.signal_ok.values).sum()):,}"]
    os.makedirs(common.OUT, exist_ok=True)
    path = os.path.join(common.OUT, "r01_data_check.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"±40% {len(idx)}건 · 거래량 20× {len(idx2)}건 · 신규상장 {len(late)} · 결측 {len(gaps)} · SPY 제외 {n_spy_off}일 · 신호 가능 {cell_sig:,}\n→ {path}")


if __name__ == "__main__":
    main()
