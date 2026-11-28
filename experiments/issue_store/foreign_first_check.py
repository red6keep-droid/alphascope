"""해외가 먼저 꺾임 검증 V12 — 우리 시장은 상승 자리인데 해외 지수 다수가 이미 52주 고점 대비 −10% 넘게 빠져 있으면,
뒤 석 달 · 여섯 달이 나빴나. 기준은 비공개 doc/기획/거시-흐름-지도.md 5-1-3 절(돌리기 전 고정).

    .venv/bin/python experiments/issue_store/foreign_first_check.py

결과: experiments/issue_store/results/foreign_first.md (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402
from cycle_position_check import positions, forward, episodes, GAP  # noqa: E402

OUT = os.path.join(_HERE, "results")
NBOOT = 2000
FOREIGN = {"^N225": "닛케이", "^HSI": "항셍", "^GDAXI": "독일", "000001.SS": "상하이", "^TWII": "대만", "^STOXX50E": "유로 50"}
rng = np.random.default_rng(20261128)


def spaced_random(k, valid):
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def foreign_down(idx, shift):
    """우리 날짜 idx 마다 해외 지수별 52주 고점 대비 −10% 아래 여부(그날 알 수 있던 종가)."""
    cols = {}
    for sym, name in FOREIGN.items():
        c = load_close(sym)
        dd = c / c.rolling(252, min_periods=252).max() - 1
        dd.index = dd.index + pd.Timedelta(days=shift)      # 한국은 해외 전날 종가
        s = dd.reindex(dd.index.union(idx)).ffill(limit=5).reindex(idx)
        cols[name] = s
    df = pd.DataFrame(cols)
    n_ok = df.notna().sum(axis=1)
    n_down = (df < -0.10).sum(axis=1)
    return df, n_ok, n_down


def study(label, c, pos, shift):
    idx = c.index
    df, n_ok, n_down = foreign_down(idx, shift)
    live = (n_ok >= 3).values
    many = (n_down > n_ok / 2).values & live
    up = (pos == "상승").values
    sig = many & up
    fw = forward(c)
    rows, detail = [], []
    for h in (63, 126):
        r, mdd = fw[h]
        ok = ~np.isnan(r)
        valid_all = np.where(live & ok)[0]
        valid_up = np.where(live & ok & up)[0]
        ev = episodes(sig & ok)
        k = len(ev)
        med, cr = np.median(r[ev]), (mdd[ev] < -0.10).mean()
        b_med = np.array([np.median(r[spaced_random(k, valid_up)]) for _ in range(NBOOT)])
        b_cr = np.array([(mdd[spaced_random(k, valid_up)] < -0.10).mean() for _ in range(NBOOT)])
        p_med = min(1, 2 * min((b_med >= med).mean(), (b_med <= med).mean()))
        p_cr = min(1, 2 * min((b_cr >= cr).mean(), (b_cr <= cr).mean()))
        half = valid_all[len(valid_all) // 2]
        sides = [np.sign(np.median(r[a]) - np.median(r[b])) if len(a) else 0
                 for a, b in ((ev[ev < half], valid_up[valid_up < half]), (ev[ev >= half], valid_up[valid_up >= half]))]
        same = sides[0] == sides[1] and sides[0] != 0
        verdict = ("다름" if p_med < .05 and same else "차이 없음") if k >= 30 else "n번 중 m번"
        rows.append(f"| {label} | {h} | {idx[valid_all[0]].year} ~ {idx[valid_all[-1]].year} | {k} | {int((r[ev] > 0).sum())}/{k} | "
                    f"{(r[valid_up] > 0).mean() * 100:.0f}% | {(r[valid_all] > 0).mean() * 100:.0f}% | {med * 100:+.1f}% | "
                    f"{np.median(r[valid_up]) * 100:+.1f}% | {np.median(r[valid_all]) * 100:+.1f}% | {p_med:.3f} | {'같음' if same else '갈림'} | "
                    f"{int((mdd[ev] < -0.10).sum())}/{k} | {(mdd[valid_up] < -0.10).mean() * 100:.0f}% | {(mdd[valid_all] < -0.10).mean() * 100:.0f}% | {p_cr:.3f} | {verdict} |")
        if h == 126:
            for i in ev:
                downs = [n for n in df.columns if df[n].iloc[i] < -0.10]
                detail.append(f"| {label} | {idx[i].date()} | {n_down.iloc[i]}/{n_ok.iloc[i]} ({' · '.join(downs)}) | "
                              f"{c.iloc[i] / c.cummax().iloc[i] * 100 - 100:.1f}% | {fw[63][0][i] * 100:+.1f}% | {r[i] * 100:+.1f}% | {mdd[i] * 100:.1f}% |")
    share_up_many = many[up & live].mean()
    now = f"- {label} {idx[-1].date()}: 우리 자리 **{pos.iloc[-1]}** · 해외 꺾임 {n_down.iloc[-1]}/{n_ok.iloc[-1]} (" + \
          " · ".join(f"{n} {df[n].iloc[-1] * 100:.1f}%" for n in df.columns if not np.isnan(df[n].iloc[-1])) + \
          f") · 조건 {'켜짐' if sig[-1] else '꺼짐'}"
    return rows, detail, share_up_many, now


def main():
    vix = load_close("^VIX")
    spx, ks = load_close("^GSPC"), load_close("^KS11")
    L = ["# 해외가 먼저 꺾임 V12", "",
         "| 우리 시장 | 창 | 기간 | 사건 | 오른 사건 | 상승 자리 아무 날 | 아무 날 | 중앙 사건 | 상승 자리 | 아무 날 | p(상승 자리) | 앞뒤 | −10% 사건 | 상승 자리 | 아무 날 | p(−10%) | 판정 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    D, notes, nows = [], [], []
    for label, c, shift in (("S&P 500", spx, 0), ("코스피", ks, 1)):
        rows, det, share, now = study(label, c, positions(c, vix), shift)
        L += rows
        D += det
        notes.append(f"- {label}: 상승 자리 날 중 해외 다수가 꺾여 있던 날 {share * 100:.0f}%")
        nows.append(now)
    L += ["", "## 얼마나 흔한가", ""] + notes
    L += ["", "## 사건마다 (126일 창)", "", "| 우리 시장 | 날 | 해외 꺾임 | 우리 최고점 대비 | 63일 뒤 | 126일 뒤 | 126일 안 최대 낙폭 |", "|---|---|---|---|---|---|---|"] + D
    L += ["", "## 지금", ""] + nows
    with open(os.path.join(OUT, "foreign_first.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
