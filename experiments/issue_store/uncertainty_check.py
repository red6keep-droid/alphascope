"""지정학 · 정책 불확실성 검증 V7 — 기준은 비공개 doc/기획/거시-흐름-지도.md 5-1-2 절(돌리기 전 고정).

    .venv/bin/python experiments/issue_store/fetch_gpr_epu.py   # 자료 먼저
    .venv/bin/python experiments/issue_store/uncertainty_check.py

- 높음 = 30일 평균이 지난 5년(1,260거래일, 모자라면 252일 이상 있는 만큼) 30일 평균 분포의 위 20%(V7a) · 위 10%(V7b).
  GPR 은 7일, EPU 는 1일 늦게 쓴다(그날 알 수 있던 값).
- V7a = 하락 목록(S&P 500, 가르는 날 1986 ~)을 가르는 날의 높음으로 갈라 깊음 · 김 · 20 · 60 · 120일 (drawdown_kind_check 와 같은 비교).
- V7b = 위 10% 로 막 들어간 날 뒤 63 · 126거래일 vs 아무 날.
결과: experiments/issue_store/results/uncertainty.md (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402
from cycle_position_check import forward, episodes, GAP  # noqa: E402
from drawdown_kind_check import outcomes, summarize  # noqa: E402

ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
CAL = os.path.join(ROOT, "data", "store", "calendar")
DD = os.path.join(ROOT, "data", "store", "drawdowns")
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


def load_index(name, col, lag, idx):
    d = pd.read_csv(os.path.join(CAL, f"{name}.csv"))
    s = pd.Series(d[col].astype(float).values, pd.to_datetime(d["day"])).sort_index()
    s = s[~s.index.duplicated()]
    ma = s.rolling(30, min_periods=20).mean()
    ma.index = ma.index + pd.Timedelta(days=lag)        # 그날 알 수 있던 값
    ma = ma.reindex(ma.index.union(idx)).ffill(limit=10).reindex(idx)
    return ma


def trailing_pct(ma):
    """그날 값이 지난 1,260거래일(최소 252) 분포에서 몇 분위인가 — 그날까지만."""
    v = ma.values
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        w = v[max(0, i - 1260):i]
        w = w[~np.isnan(w)]
        if len(w) >= 252:
            out[i] = (w < v[i]).mean()
    return pd.Series(out, ma.index)


def main():
    spx = load_close("^GSPC")
    idx = spx.index
    g = trailing_pct(load_index("gpr_daily", "gpr", 7, idx))
    e = trailing_pct(load_index("epu_daily", "epu", 1, idx))

    # V7a
    dd = outcomes(pd.read_csv(os.path.join(DD, "_GSPC.csv")), spx)
    for i, r in dd.iterrows():
        x = int(r["x"])
        dd.loc[i, "G"] = None if np.isnan(g.iloc[x]) else bool(g.iloc[x] >= 0.8)
        dd.loc[i, "E"] = None if np.isnan(e.iloc[x]) else bool(e.iloc[x] >= 0.8)
    summ = pd.DataFrame([summarize("G 지정학 위험 높음(위 20%)", "S&P 500", dd, "G"),
                         summarize("E 정책 불확실성 높음(위 20%)", "S&P 500", dd, "E")])
    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.1f}%"
    pf = lambda v: "" if pd.isna(v) else f"{v:.3f}"
    L = ["# 지정학 · 정책 불확실성 V7", "", f"자료 끝 {idx[-1].date()}", "", "## V7a 하락이 시작된 날 높음이었나", "",
         "| 조건 | 기간 | 하락 | 켜짐 | 깊음 켜짐 | 깊음 꺼짐 | p | 김 켜짐 | 김 꺼짐 | p | 20일 켜짐 | 꺼짐 | p | 60일 켜짐 | 꺼짐 | p | 120일 켜짐 | 꺼짐 | p |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, s in summ.iterrows():
        L.append(f"| {s['조건']} | {s['기간']} | {s['하락 수']} | {s['켜짐']} | {s['deep 켜짐']} | {s['deep 꺼짐']} | {pf(s['deep p'])} | "
                 f"{s['long 켜짐']} | {s['long 꺼짐']} | {pf(s['long p'])} | "
                 + " | ".join(f"{pct(s[f'r{h} 켜짐'])} | {pct(s[f'r{h} 꺼짐'])} | {pf(s[f'r{h} p'])}" for h in (20, 60, 120)) + " |")
    L += ["", "| 가르는 날 | 깊이 | 더 빠짐 | 바닥까지 | GPR 분위 | EPU 분위 |", "|---|---|---|---|---|---|"]
    for _, r in dd[dd["G"].notna()].iterrows():
        x = int(r["x"])
        L.append(f"| {r['cross']} | {r['depth'] * 100:.1f}% | {r['more'] * 100:.1f}% | {r['days']} | {g.iloc[x] * 100:.0f} | {e.iloc[x] * 100:.0f} |")

    # V7b
    fw = forward(spx)
    L += ["", "## V7b 위 10% 로 막 들어간 날 뒤", "",
          "| 조건 | 창 | 사건 | 오른 사건 | 아무 날 | 중앙 사건 | 아무 날 | p | 앞뒤 | −10% 사건 | 아무 날 | p(−10%) | 판정 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    dates = []
    for name, pc in (("GPR 위 10%", g), ("EPU 위 10%", e)):
        live = pc.notna().values & (idx >= "1986-01-01")
        sig = (pc >= 0.9).values & live
        for h in (63, 126):
            r, mdd = fw[h]
            ok = ~np.isnan(r)
            valid = np.where(live & ok)[0]
            ev = episodes(sig & ok)
            k = len(ev)
            med, cr = np.median(r[ev]), (mdd[ev] < -0.10).mean()
            bm = np.array([np.median(r[spaced_random(k, valid)]) for _ in range(NBOOT)])
            bc = np.array([(mdd[spaced_random(k, valid)] < -0.10).mean() for _ in range(NBOOT)])
            p = min(1, 2 * min((bm >= med).mean(), (bm <= med).mean()))
            pc_ = min(1, 2 * min((bc >= cr).mean(), (bc <= cr).mean()))
            half = valid[len(valid) // 2]
            sides = [np.sign(np.median(r[a]) - np.median(r[b])) if len(a) else 0
                     for a, b in ((ev[ev < half], valid[valid < half]), (ev[ev >= half], valid[valid >= half]))]
            same = sides[0] == sides[1] and sides[0] != 0
            verdict = ("다름" if p < .05 and same else "차이 없음") if k >= 30 else "n번 중 m번"
            L.append(f"| {name} | {h} | {k} | {int((r[ev] > 0).sum())}/{k} | {(r[valid] > 0).mean() * 100:.0f}% | {med * 100:+.1f}% | {np.median(r[valid]) * 100:+.1f}% | "
                     f"{p:.3f} | {'같음' if same else '갈림'} | {int((mdd[ev] < -0.10).sum())}/{k} | {(mdd[valid] < -0.10).mean() * 100:.0f}% | {pc_:.3f} | {verdict} |")
            if h == 126:
                dates.append(f"- {name}: " + " · ".join(f"{idx[i].date()}({r[i] * 100:+.0f}%)" for i in ev))
    L += ["", "## V7b 사건 날짜 (괄호 = 126일 뒤)", ""] + dates
    L += ["", "## 지금", "", f"- {idx[-1].date()} · GPR 30일 평균 분위(지난 5년) {g.iloc[-1] * 100:.0f} · EPU {e.iloc[-1] * 100:.0f}",
          "", "```", pd.DataFrame({"GPR분위": g, "EPU분위": e})["2026-06-01":].iloc[::10].mul(100).round(0).to_string(), "```"]
    with open(os.path.join(OUT, "uncertainty.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
