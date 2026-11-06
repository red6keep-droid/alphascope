"""취약 상태 경고 검증 — "취약 상태 뒤 하락 꼬리가 아무 날보다 두꺼운가" (2026-11-06 사용자 "검증해").

    .venv/bin/python experiments/issue_store/fragility_check.py

결과 보기 전 고정한 설계 (비공개 doc/검증/취약-상태-경고-검증.md):
- 자 = S&P 500 종가(^GSPC), 기간 = VIX 가 있는 1990-01 ~ 2026-10. 보조 = 나스닥(^IXIC) · 반도체(^SOX, 1994~).
- 취약 상태 후보(그날 종가 기준, 각각 따로): C1 연속 상승 7일↑ · C2 VIX < 15 가 30거래일↑ 지속 · C3 20거래일 수익 +8%↑ ·
  C4 200일선 위 10%↑ · C5 20일 볼린저(2σ) 상단 위 · C6 52주 신고가 · C7 복합 = C2 그리고 (C1 5일↑ 또는 C4).
- 결과 = 그날 종가에서 뒤 20거래일 안 최대 낙폭(MDD20). 지표 = MDD20 ≤ −5% 비율 · ≤ −10% 비율 · 중앙값 · 창 안 하루 |수익률| 최대(흔들림).
- 에피소드 = 신호가 20거래일 넘게 끊겼다 다시 켜진 첫 날(겹치는 창 제거). 통계는 에피소드 첫 날로만.
- 플라시보 = 같은 수의 아무 날(서로 20일 넘게 떨어진)을 2,000번 뽑아 ≤ −5% 비율 분포 → 양쪽 p.
- 통과 = p < 0.05 그리고 앞 절반(1990~2008-06) · 뒤 절반 같은 방향 그리고 비율이 아무 날의 1.25배 이상. 에피소드 < 30 = 표본 부족.
- 전조 확인(거꾸로): MDD20 ≤ −10% 인 급락 창(첫 날)마다 직전 10일 안에 각 상태가 켜져 있던 비율 vs 상태의 평소 비율.
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402

OUT = os.path.join(_HERE, "results")
H = int(os.environ.get("FRAG_H", "20"))
GAP = 20
NBOOT = 2000
SPLIT = pd.Timestamp("2008-07-01")
rng = np.random.default_rng(20261106)


def mdd_forward(c, h=H):
    v = c.values
    n = len(v)
    out = np.full(n, np.nan)
    big = np.full(n, np.nan)
    for i in range(n - h):
        w = v[i + 1:i + h + 1]
        out[i] = w.min() / v[i] - 1
        r = np.abs(np.diff(np.concatenate([[v[i]], w])) / np.concatenate([[v[i]], w[:-1]]))
        big[i] = r.max()
    return pd.Series(out, c.index), pd.Series(big, c.index)


def conditions(c, vix):
    r = c.pct_change()
    up = (r > 0).astype(int)
    streak = up.groupby((up == 0).cumsum()).cumsum()
    low = (vix.reindex(c.index) < 15).astype(int)
    lowrun = low.groupby((low == 0).cumsum()).cumsum()
    ret20 = c / c.shift(20) - 1
    ma200 = c.rolling(200).mean()
    m20, s20 = c.rolling(20).mean(), c.rolling(20).std()
    hi252 = c.rolling(252).max()
    cond = {
        "C1 연속 상승 7일↑": streak >= 7,
        "C1' 연속 상승 5일↑": streak >= 5,
        "C2 VIX<15 30일↑ 지속": lowrun >= 30,
        "C2' VIX<15 60일↑ 지속": lowrun >= 60,
        "C3 20일 수익 +8%↑": ret20 >= 0.08,
        "C4 200일선 위 10%↑": c / ma200 - 1 >= 0.10,
        "C5 볼린저 상단 위": c > m20 + 2 * s20,
        "C6 52주 신고가": c >= hi252,
        "C7 복합 VIX낮음 & (상승5일 or 200일선+10%)": (lowrun >= 30) & ((streak >= 5) | (c / ma200 - 1 >= 0.10)),
        "X1 대조 VIX>25 (이미 흔들림)": vix.reindex(c.index) > 25,
        "X2 대조 VIX>30": vix.reindex(c.index) > 30,
        "X3 대조 20일 수익 −8%↓ (이미 빠짐)": ret20 <= -0.08,
        "X4 대조 200일선 아래": c < ma200,
    }
    return {k: v.fillna(False) for k, v in cond.items()}


def episodes(sig):
    """신호 첫 날들 — 직전 신호에서 GAP 거래일 넘게 떨어진 날만."""
    idx = np.where(sig.values)[0]
    out, last = [], -10 ** 9
    for i in idx:
        if i - last > GAP:
            out.append(i)
        last = i
    return np.array(out, dtype=int)


def spaced_random(n_days, k, valid):
    """서로 GAP 넘게 떨어진 아무 날 k개 (valid = 결과가 있는 날)."""
    picks = []
    tries = 0
    while len(picks) < k and tries < 50:
        cand = rng.choice(valid, size=k * 3, replace=False)
        cand.sort()
        last = -10 ** 9
        for i in cand:
            if i - last > GAP:
                picks.append(i)
                last = i
            if len(picks) >= k:
                break
        tries += 1
    return np.array(picks[:k])


def stats(m, big, ix):
    x = m[ix]
    return {"n": len(ix), "p5": float((x <= -0.05).mean()), "p10": float((x <= -0.10).mean()),
            "med": float(np.median(x)), "big": float(np.median(big[ix]))}


def run(sym, vix):
    c = load_close(sym)
    c = c[c.index >= "1990-01-01"]
    m, big = mdd_forward(c)
    mv, bv = m.values, big.values
    valid = np.where(~np.isnan(mv))[0]
    base = stats(mv, bv, valid)
    base_first = stats(mv, bv, valid[c.index[valid] < SPLIT])
    base_second = stats(mv, bv, valid[c.index[valid] >= SPLIT])
    rows = []
    conds = conditions(c, vix)
    for name, sig in conds.items():
        ep = episodes(sig)
        ep = ep[~np.isnan(mv[ep])]
        if len(ep) == 0:
            continue
        s = stats(mv, bv, ep)
        boot = np.array([stats(mv, bv, spaced_random(len(c), len(ep), valid))["p5"] for _ in range(NBOOT)])
        p = float(2 * min((boot >= s["p5"]).mean(), (boot <= s["p5"]).mean()))
        p = min(p, 1.0)
        d1 = ep[c.index[ep] < SPLIT]
        d2 = ep[c.index[ep] >= SPLIT]
        f = stats(mv, bv, d1)["p5"] - base_first["p5"] if len(d1) else np.nan
        g = stats(mv, bv, d2)["p5"] - base_second["p5"] if len(d2) else np.nan
        same = (not np.isnan(f)) and (not np.isnan(g)) and (np.sign(f) == np.sign(g)) and f != 0
        ratio = s["p5"] / base["p5"] if base["p5"] else np.nan
        if len(ep) < 30:
            verdict = "표본 부족"
        elif p < 0.05 and same and (ratio >= 1.25 or ratio <= 0.8):
            verdict = "두껍다 (통과)" if ratio >= 1.25 else "얇다 (반대로 통과)"
        else:
            verdict = "차이 없음"
        rows.append({"자": sym, "상태": name, "에피소드": len(ep), "신호 날 비율": float(sig.values[valid].mean()),
                     "MDD20≤−5%": s["p5"], "아무 날": base["p5"], "배": ratio, "p": p,
                     "앞 절반 차": f, "뒤 절반 차": g, "MDD20≤−10%": s["p10"], "아무 날 −10%": base["p10"],
                     "MDD 중앙값": s["med"], "아무 날 중앙값": base["med"], "흔들림 중앙값": s["big"], "아무 날 흔들림": base["big"],
                     "판정": verdict})
    # 전조 확인 — 급락 창 첫 날 직전 10일 안에 상태가 켜져 있던 비율
    crash = episodes(pd.Series(mv <= -0.10, c.index).fillna(False))
    pre = []
    for name, sig in conds.items():
        sv = sig.values
        had = [sv[max(0, i - 10):i + 1].any() for i in crash]
        # 평소: 아무 날 직전 10일 안 켜짐 비율
        anyday = pd.Series(sv).rolling(11, min_periods=1).max().values[valid].mean()
        pre.append({"자": sym, "상태": name, "급락 창 수": len(crash), "급락 전 10일 안 켜짐": float(np.mean(had)) if len(crash) else np.nan,
                    "아무 날 10일 안 켜짐": float(anyday)})
    return rows, pre, base, len(valid)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    vix = load_close("^VIX")
    all_rows, all_pre, notes = [], [], []
    syms = os.environ.get("FRAG_SYMS", "^GSPC,^IXIC,^SOX").split(",")   # 한국 = ^KS11,^KQ11 (VIX 는 세계 변동성 국면의 대리 — 한국 VKOSPI 는 야후에 없음)
    tag = os.environ.get("FRAG_TAG", "")
    for sym in syms:
        rows, pre, base, n = run(sym, vix)
        all_rows += rows
        all_pre += pre
        notes.append(f"{sym}: 날 {n} · 아무 날 MDD20≤−5% {base['p5']:.1%} · ≤−10% {base['p10']:.1%} · 중앙값 {base['med']:+.1%} · 흔들림 중앙값 {base['big']:.1%}")
    df = pd.DataFrame(all_rows)
    pf = pd.DataFrame(all_pre)
    df.to_csv(os.path.join(OUT, f"fragility_check{tag}_h{H}.csv"), index=False)
    pf.to_csv(os.path.join(OUT, f"fragility_precursor{tag}_h{H}.csv"), index=False)
    pct = lambda v: "—" if pd.isna(v) else f"{v:.1%}"   # noqa: E731
    pp = lambda v: "—" if pd.isna(v) else f"{v:+.1%}"   # noqa: E731
    lines = [f"# 취약 상태 경고 검증 — 결과, 창 {H}거래일 (자동 생성, fragility_check.py)", "", *notes, "",
             "| 자 | 상태 | 에피소드 | 신호 날 | MDD20≤−5% | 아무 날 | 배 | p | 앞 절반 차 | 뒤 절반 차 | ≤−10% | 아무 날 | 흔들림 | 아무 날 | 판정 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        lines.append(f"| {r['자']} | {r['상태']} | {r['에피소드']} | {pct(r['신호 날 비율'])} | {pct(r['MDD20≤−5%'])} | {pct(r['아무 날'])} | "
                     f"{r['배']:.2f} | {r['p']:.3f} | {pp(r['앞 절반 차'])} | {pp(r['뒤 절반 차'])} | {pct(r['MDD20≤−10%'])} | {pct(r['아무 날 −10%'])} | "
                     f"{pct(r['흔들림 중앙값'])} | {pct(r['아무 날 흔들림'])} | {r['판정']} |")
    lines += ["", "## 전조 확인 — 급락(MDD20 ≤ −10%) 창 첫 날 직전 10일 안에 상태가 켜져 있던 비율", "",
              "| 자 | 상태 | 급락 창 | 급락 전 켜짐 | 아무 날 켜짐 |", "|---|---|---|---|---|"]
    for _, r in pf.iterrows():
        lines.append(f"| {r['자']} | {r['상태']} | {r['급락 창 수']} | {pct(r['급락 전 10일 안 켜짐'])} | {pct(r['아무 날 10일 안 켜짐'])} |")
    open(os.path.join(OUT, f"fragility_check{tag}_h{H}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
