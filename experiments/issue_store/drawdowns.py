"""과거 하락 목록 — 고점 대비 −10% 넘게 빠진 하락 전부 (거시 흐름 검증 V1 ~ V6 가 같이 쓰는 한 벌).

    .venv/bin/python experiments/issue_store/drawdowns.py            # ^GSPC(1950 ~) · ^KS11(1997 ~)
    .venv/bin/python experiments/issue_store/drawdowns.py ^IXIC 1985-01-01

저장: data/store/drawdowns/{심볼}.csv (깃 밖, 이 스크립트로 몇 초 만에 다시 만든다).

정의 (비공개 doc/기획/거시-흐름-지도.md 0-3 · 5절):
- 고점 = 마지막으로 하락을 끊은 날 뒤의 최고 종가. 종가가 고점 × 0.9 아래면 하락.
  하락은 고점을 다시 넘거나(회복) 바닥에서 +20% 넘게 오르면(반등) 끝나고, 그날부터 고점을 새로 센다.
- **가르는 날(cross)** = 종가가 처음 고점 × 0.9 아래로 내려간 날 — 그날 아는 것은 "−10% 넘게 빠졌다"뿐이다.
  검증의 조건(경기 · 신용 · 금리 …)은 이 날까지 알 수 있던 값으로 가른다.
- 칸: peak · cross · trough · recover(고점을 다시 넘은 날, 없으면 빈칸) · end(회복 · 반등 +20% · 진행 중) · depth(바닥 / 고점 − 1) ·
  cross_to_trough(가르는 날부터 더 빠진 폭) · d_peak_trough · d_cross_trough · d_trough_recover (거래일) · open(회복 전이면 1).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402

ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "drawdowns")
CUT = -0.10
REBOUND = 0.20


def drawdowns(c):
    """고점 = 마지막으로 끊은 날 뒤의 최고 종가. 고점 × 0.9 아래로 내려가면 하락 시작(cross).
    하락은 ① 고점을 종가로 다시 넘거나 ② 바닥에서 +20% 넘게 오르면 끝 — 그날부터 고점을 새로 센다.
    ② 가 없으면 2007 고점(2013 회복) 안의 2010 · 2011 하락이 한 덩어리에 묻힌다."""
    v, idx = c.values, c.index
    n = len(v)
    rows = []
    peak_i, i = 0, 0
    while i < n:
        if v[i] > v[peak_i]:
            peak_i = i
        if v[i] > v[peak_i] * (1 + CUT):
            i += 1
            continue
        x = t = i
        j = i + 1
        end = None
        while j < n:
            if v[j] < v[t]:
                t = j
            if v[j] >= v[peak_i]:
                end = "회복"
                break
            if v[j] >= v[t] * (1 + REBOUND):
                end = "반등 +20%"
                break
            j += 1
        rec = next((k for k in range(t + 1, n) if v[k] >= v[peak_i]), None)
        rows.append({
            "peak": idx[peak_i].date(), "cross": idx[x].date(), "trough": idx[t].date(),
            "recover": idx[rec].date() if rec is not None else None, "end": end or "진행 중",
            "depth": round(v[t] / v[peak_i] - 1, 4), "cross_to_trough": round(v[t] / v[x] - 1, 4),
            "d_peak_trough": t - peak_i, "d_cross_trough": t - x,
            "d_trough_recover": (rec - t) if rec is not None else None, "open": int(end is None),
        })
        if end is None:
            break
        peak_i = i = j
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [(sys.argv[1], sys.argv[2])] if len(sys.argv) > 2 else [("^GSPC", "1950-01-01"), ("^KS11", "1997-01-01")]
    for sym, start in jobs:
        c = load_close(sym)
        c = c[c.index >= start]
        df = drawdowns(c)
        p = os.path.join(OUT, sym.replace("^", "_") + ".csv")
        df.to_csv(p, index=False)
        print(f"{sym} {start} ~ {c.index[-1].date()}: −10% 넘은 하락 {len(df)}개 (회복 전 {int(df['open'].sum())}) → {p}")


if __name__ == "__main__":
    main()
