"""상승의 나이 검증 V9 — 상승 자리가 오래 이어질수록 뒤 여섯 달에 크게 빠지는 일이 잦았나.
기준은 비공개 doc/기획/거시-흐름-지도.md 5-1-4 절(돌리기 전 고정).

    .venv/bin/python experiments/issue_store/uptrend_age_check.py

결과: experiments/issue_store/results/uptrend_age.md (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402
from cycle_position_check import forward, GAP  # noqa: E402

OUT = os.path.join(_HERE, "results")
NBOOT = 2000
BINS = [("1년 미만", 0, 251), ("1 ~ 3년", 252, 756), ("3년 넘음", 757, 10 ** 9)]
rng = np.random.default_rng(20261128)


def ages(c):
    """상승 자리(역대 최고점 대비 −10% 안)인 날의 나이 = 마지막으로 −10% 아래였던 날로부터 거래일. 아래였던 적 없으면 NaN."""
    v = c.values
    peak = np.maximum.accumulate(v)
    below = v < peak * 0.9
    age = np.full(len(v), np.nan)
    last = None
    for i in range(len(v)):
        if below[i]:
            last = i
        elif last is not None:
            age[i] = i - last - 1
    return pd.Series(age, c.index), pd.Series(~below, c.index)


def spaced_random(k, valid):
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def study(label, c, start):
    age, up = ages(c)
    fw = forward(c)
    a = age.values
    live = (c.index >= pd.Timestamp(start))
    rows, dates = [], []
    for h in (63, 126):
        r, mdd = fw[h]
        ok = ~np.isnan(r)
        valid_up = np.where(live & ok & up.values & ~np.isnan(a))[0]
        for name, lo, hi in BINS:
            ev = np.where(live & ok & (a == lo))[0]          # 그 칸에 처음 들어간 날
            days = valid_up[(a[valid_up] >= lo) & (a[valid_up] <= hi)]
            k = len(ev)
            row = f"| {label} | {h} | {name} | {k} | "
            if k == 0:
                rows.append(row + " |" * 10)
                continue
            med, cr = np.median(r[ev]), (mdd[ev] < -0.10).mean()
            bm = np.array([np.median(r[spaced_random(k, valid_up)]) for _ in range(NBOOT)])
            bc = np.array([(mdd[spaced_random(k, valid_up)] < -0.10).mean() for _ in range(NBOOT)])
            p_m = min(1, 2 * min((bm >= med).mean(), (bm <= med).mean()))
            p_c = min(1, 2 * min((bc >= cr).mean(), (bc <= cr).mean()))
            verdict = ("다름" if p_m < .05 else "차이 없음") if k >= 30 else "n번 중 m번"
            rows.append(row + f"{int((r[ev] > 0).sum())}/{k} | {med * 100:+.1f}% | {np.median(r[valid_up]) * 100:+.1f}% | {p_m:.3f} | "
                        f"{int((mdd[ev] < -0.10).sum())}/{k} | {(mdd[valid_up] < -0.10).mean() * 100:.0f}% | {p_c:.3f} | "
                        f"{len(days)} | {np.median(r[days]) * 100:+.1f}% · {(mdd[days] < -0.10).mean() * 100:.0f}% | {verdict} |")
            if h == 126:
                dates.append(f"- {label} {name}: " + " · ".join(f"{c.index[i].date()}({r[i] * 100:+.0f}%{' ▼' if mdd[i] < -0.10 else ''})" for i in ev))
    # 상승 한 번 한 번: 시작 · 끝 · 나이
    runs = []
    i = 0
    n = len(a)
    while i < n:
        if not np.isnan(a[i]) and a[i] == 0 and c.index[i] >= pd.Timestamp(start):
            j = i
            while j + 1 < n and not np.isnan(a[j + 1]):
                j += 1
            runs.append(f"| {label} | {c.index[i].date()} | {c.index[j].date()} | {(j - i + 1) / 252:.1f}년 | {'진행 중' if j == n - 1 else '−10% 아래로'} |")
            i = j + 1
        else:
            i += 1
    now = f"- {label} {c.index[-1].date()}: " + (f"상승 자리 · 나이 {a[-1] / 252:.1f}년({int(a[-1])}거래일)" if not np.isnan(a[-1]) else "하락 자리(나이 없음)")
    return rows, dates, runs, now


def main():
    L = ["# 상승의 나이 V9", "",
         "| 시장 | 창 | 나이 칸 | 사건 | 오른 사건 | 중앙 사건 | 상승 자리 | p | −10% 사건 | 상승 자리 | p(−10%) | 날 단위 날 수 | 날 단위 중앙 · −10% | 판정 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    D, R, N = [], [], []
    for label, sym, start in (("S&P 500", "^GSPC", "1928-01-01"), ("코스피", "^KS11", "1997-01-01")):
        rows, dates, runs, now = study(label, load_close(sym), start)
        L += rows
        D += dates
        R += runs
        N.append(now)
    L += ["", "## 사건 날짜 (126일 창, 괄호 = 126일 뒤 · ▼ = 그 안에 −10% 넘게 빠짐)", ""] + D
    L += ["", "## 상승 한 번 한 번", "", "| 시장 | 시작 | 끝 | 길이 | 끝난 까닭 |", "|---|---|---|---|---|"] + R
    L += ["", "## 지금", ""] + N
    with open(os.path.join(OUT, "uptrend_age.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
