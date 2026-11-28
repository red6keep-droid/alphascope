"""상승 중 좁아짐 검증 V11 — 지수는 상승 자리인데 오르는 종목이 좁아지는 중이면 뒤 석 달 · 여섯 달이 나빴나.
기준은 비공개 doc/기획/거시-흐름-지도.md 5-1-5 절(돌리기 전 고정).

    .venv/bin/python experiments/issue_store/fetch_bars.py RSP SPY
    .venv/bin/python experiments/issue_store/uptrend_breadth_check.py

B1 = 그날 구성 종목 중 200일 평균 위 비율(일봉 있는 비율 80% 넘는 날만), 좁아짐 = 60거래일 −15%p 이하.
B2 = RSP ÷ SPY, 좁아짐 = 60거래일 변화가 2003 ~ 분포 아래 10%.
결과: experiments/issue_store/results/uptrend_breadth.md (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402
from cycle_position_check import positions, forward, episodes, GAP  # noqa: E402

ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
COMP = os.path.join(ROOT, "data", "store", "calendar", "sp500_components.csv")
OUT = os.path.join(_HERE, "results")
NBOOT = 2000
rng = np.random.default_rng(20261128)


def spaced_random(k, valid):
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def breadth(idx):
    comp = pd.read_csv(COMP, parse_dates=["date"]).set_index("date")["tickers"].str.split(",")
    comp = comp.reindex(comp.index.union(idx)).ffill().reindex(idx)
    names = sorted(set(t for ts in comp.dropna() for t in ts))
    above, have = {}, {}
    for t in names:
        c = None
        for cand in (t, t.replace(".", "-")):
            c = load_close(cand)
            if c is not None:
                break
        if c is None or len(c) < 200:
            continue
        c = c.reindex(idx)
        ma = c.rolling(200, min_periods=200).mean()
        above[t] = (c > ma).where(ma.notna())
    A = pd.DataFrame(above)
    frac, cov = np.full(len(idx), np.nan), np.full(len(idx), np.nan)
    for i, ts in enumerate(comp.values):
        if not isinstance(ts, list):
            continue
        cols = [t for t in ts if t in A.columns]
        row = A.iloc[i][cols].dropna() if cols else pd.Series(dtype=float)
        cov[i] = len(row) / len(ts)
        if len(row):
            frac[i] = row.mean()
    return pd.Series(frac, idx), pd.Series(cov, idx)


def run(name, sig, live, spx, up, fw):
    out, det = [], []
    for h in (63, 126):
        r, mdd = fw[h]
        ok = ~np.isnan(r)
        valid_all = np.where(live & ok)[0]
        valid_up = np.where(live & ok & up)[0]
        ev = episodes(sig & live & ok)
        k = len(ev)
        if k == 0:
            out.append(f"| {name} | {h} | | 0 |" + " |" * 12)
            continue
        med, cr = np.median(r[ev]), (mdd[ev] < -0.10).mean()
        bm = np.array([np.median(r[spaced_random(k, valid_up)]) for _ in range(NBOOT)])
        bc = np.array([(mdd[spaced_random(k, valid_up)] < -0.10).mean() for _ in range(NBOOT)])
        p_m = min(1, 2 * min((bm >= med).mean(), (bm <= med).mean()))
        p_c = min(1, 2 * min((bc >= cr).mean(), (bc <= cr).mean()))
        half = valid_all[len(valid_all) // 2]
        sides = [np.sign(np.median(r[a]) - np.median(r[b])) if len(a) else 0
                 for a, b in ((ev[ev < half], valid_up[valid_up < half]), (ev[ev >= half], valid_up[valid_up >= half]))]
        same = sides[0] == sides[1] and sides[0] != 0
        verdict = ("다름" if p_m < .05 and same else "차이 없음") if k >= 30 else "n번 중 m번"
        out.append(f"| {name} | {h} | {spx.index[valid_all[0]].year} ~ {spx.index[valid_all[-1]].year} | {k} | {int((r[ev] > 0).sum())}/{k} | "
                   f"{(r[valid_up] > 0).mean() * 100:.0f}% | {med * 100:+.1f}% | {np.median(r[valid_up]) * 100:+.1f}% | {np.median(r[valid_all]) * 100:+.1f}% | "
                   f"{p_m:.3f} | {'같음' if same else '갈림'} | {int((mdd[ev] < -0.10).sum())}/{k} | {(mdd[valid_up] < -0.10).mean() * 100:.0f}% | {p_c:.3f} | {verdict} |")
        if h == 126:
            det += [f"| {name[:2]} | {spx.index[i].date()} | {spx.iloc[i] / spx.cummax().iloc[i] * 100 - 100:.1f}% | {fw[63][0][i] * 100:+.1f}% | {r[i] * 100:+.1f}% | {mdd[i] * 100:.1f}% |" for i in ev]
    return out, det


def main():
    spx = load_close("^GSPC")
    idx = spx.index
    up = (positions(spx, load_close("^VIX")) == "상승").values
    fw = forward(spx)
    frac, cov = breadth(idx)
    b1_chg = frac - frac.shift(60)
    live1 = (cov > 0.8).values & (cov.shift(60) > 0.8).values & b1_chg.notna().values
    sig1 = up & (b1_chg <= -0.15).values
    ratio = (load_close("RSP") / load_close("SPY")).reindex(idx)
    r2 = ratio / ratio.shift(60) - 1
    cut2 = r2.dropna().quantile(0.10)
    live2 = r2.notna().values
    sig2 = up & (r2 < cut2).values
    L = ["# 상승 중 좁아짐 V11", "", f"자료 끝 {idx[-1].date()} · B2 아래 10% 선 = 60일 {cut2 * 100:.2f}%", "",
         "| 자 | 창 | 기간 | 사건 | 오른 사건 | 상승 자리 | 중앙 사건 | 상승 자리 | 아무 날 | p | 앞뒤 | −10% 사건 | 상승 자리 | p(−10%) | 판정 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    D = []
    for name, sig, live in (("B1 구성 종목 폭 60일 −15%p", sig1, live1), ("B2 동일 가중 ÷ 시총 가중 아래 10%", sig2, live2)):
        o, d = run(name, sig, live, spx, up, fw)
        L += o
        D += d
    L += ["", "## 사건마다 (126일 창)", "", "| 자 | 날 | 최고점 대비 | 63일 뒤 | 126일 뒤 | 126일 안 최대 낙폭 |", "|---|---|---|---|---|---|"] + D
    L += ["", "## 일봉 있는 비율 (해마다 첫날)", "", " · ".join(f"{y} {cov[cov.index.year == y].iloc[0] * 100:.0f}%" for y in range(1997, 2027, 3) if (cov.index.year == y).any())]
    L += ["", "## 지금", "",
          f"- {idx[-1].date()} · 자리 {'상승' if up[-1] else '상승 아님'} · 200일선 위 비율 {frac.iloc[-1] * 100:.0f}%(60일 전 {frac.iloc[-61] * 100:.0f}%, 변화 {b1_chg.iloc[-1] * 100:+.0f}%p) · "
          f"동일 가중 ÷ 시총 가중 60일 {r2.iloc[-1] * 100:+.2f}%(선 {cut2 * 100:.2f}%) · B1 {'켜짐' if sig1[-1] else '꺼짐'} · B2 {'켜짐' if sig2[-1] else '꺼짐'}",
          "", "```", pd.DataFrame({"폭%": frac * 100, "폭60일%p": b1_chg * 100, "RSP/SPY60일%": r2 * 100})["2026-06-01":].iloc[::10].round(1).to_string(), "```"]
    with open(os.path.join(OUT, "uptrend_breadth.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
