"""뉴팩트 개성 있는 아이 찾기 게임 (A 갈래) — 정해진 돌(실적 발표)에 호수마다 어떻게 반응하나, S&P 500 줄 세우기 (2026-11-24 사용자 "그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-7 · 7-9.
사용자: "실적일은 정해진 돌로 봐야지. 종목마다 돌을 던질 때 유난히 거칠게 반응하는 호수가 있고 잔잔하게 반응하는 호수가 있는 거겠지. 이것도 개성으로 봐야 될지가 문제."
→ 실적일인지 아닌지는 개성이 아니다(다 있는 돌). 반응 크기가 종목마다 갈리는지 · 반복되는지를 본다.

    python experiments/stock-character/look_earn.py

자료 = data/store/character/bars_us.pkl (check_stage1.py) · earn_days_us.csv (collect_earn_days.py --market us). 최근 3년.
반응 날 = 발표가 장 마감 뒤면 다음 거래일, 아니면 그날.
재는 것(종목마다, 실적 돌 약 12개):
  반응 크기      반응 날 등락 크기(%)의 중앙값 — 모든 종목 같은 잣대
  평소의 몇 배    반응 날 등락 크기 ÷ 그 앞 60거래일(실적 날 빼고) 등락 크기 중앙값, 의 중앙값
  큰 반응 횟수    반응 날 ±5% 넘은 횟수 (반복)
  머문 비율      20거래일 뒤에도 가격이 돌 전 자리로 안 돌아온 실적 돌의 비율 (계단)
그림 = output/graphs/earn_sorted.png (깃에 안 올림).
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "graphs")
DAYS = 756
MARK = ["MSFT", "TSLA", "JPM", "KO", "NVDA", "AMD"]
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    rows, each = [], []
    for s, d in bars.items():
        if s.startswith("^") or len(d) < 400:
            continue
        d = d[(d["open"] > 0) & (d["volume"] > 0)]
        c = d["close"]
        ret = c.pct_change() * 100
        idx = c.index
        start = idx[-DAYS] if len(idx) > DAYS else idx[0]
        pos_e = []
        for _, e in earn[earn.sym == s].iterrows():
            p = idx.searchsorted(e["day"])
            if p < len(idx) and idx[p] == e["day"] and e["after_close"] == 1:
                p += 1
            if p < len(idx):
                pos_e.append(p)
        eset = set(pos_e)
        got = []
        for p in pos_e:
            if idx[p] < start or p < 61:
                continue
            r = ret.iloc[p]
            base = ret.iloc[[k for k in range(p - 60, p) if k not in eset]].abs().median()
            pre = c.iloc[p - 1]
            stay = None
            if p + 20 < len(idx):
                after = c.iloc[p + 1:p + 21]
                stay = not ((after >= pre).any() if r < 0 else (after <= pre).any())
            got.append((abs(r), abs(r) / base if base else np.nan, stay, r))
            each.append({"sym": s, "day": idx[p].date(), "ret": r})
        if len(got) < 8:
            continue
        a = np.array([g[0] for g in got])
        stays = [g[2] for g in got if g[2] is not None]
        rows.append({"sym": s, "n": len(got), "react": np.median(a), "times": np.nanmedian([g[1] for g in got]),
                     "big": int((a >= 5).sum()), "big_share": (a >= 5).mean(), "stay": np.mean(stays) if stays else np.nan,
                     "lake": ret.iloc[-DAYS:].abs().median()})
    R = pd.DataFrame(rows).set_index("sym")
    print(f"종목 {len(R)}개 · 실적 돌 종목당 중앙 {int(R.n.median())}개 · 최근 3년")
    print(f"무리 한가운데: 반응 크기 {R.react.median():.1f}% · 평소의 {R.times.median():.1f}배 · 12번 중 ±5% 넘은 횟수 {R.big.median():.0f} · 머문 비율 {R.stay.median() * 100:.0f}%")

    cols = [("react", "반응 크기 (반응 날 등락 %, 중앙값)", 1), ("times", "평소의 몇 배", 1), ("big", "±5% 넘은 횟수 (약 12번 중)", 1), ("stay", "20일 뒤에도 머문 비율 (%)", 100)]
    fig, axs = plt.subplots(1, 4, figsize=(19, 4.8))
    for ax, (col, label, mul) in zip(axs, cols):
        v = (R[col].dropna() * mul).sort_values()
        med = v.median()
        mad = max((v - med).abs().median() * 1.4826, 1.0 if col == "big" else 1e-9)
        z = (v - med) / mad
        print(f"\n[{label}] 중앙값 {med:.1f} · 무리 폭 {mad:.1f} | 3폭 넘게 위 {int((z > 3).sum())}종목 · 5폭 넘게 위 {int((z > 5).sum())} · 2폭 넘게 아래 {int((z < -2).sum())}")
        print("  맨 위: " + ", ".join(f"{s} {x:.1f}" for s, x in v.iloc[-12:][::-1].items()))
        print("  맨 아래: " + ", ".join(f"{s} {x:.1f}" for s, x in v.iloc[:10].items()))
        print("  표시 종목: " + ", ".join(f"{s} {v[s]:.1f}(위에서 {100 - (v < v[s]).mean() * 100:.0f}%)" for s in MARK if s in v.index))
        ax.plot(range(len(v)), v.values, color="#1c2330", lw=1.2)
        ax.axhline(med, color="#8a93a3", lw=0.6, ls=":")
        ax.axhline(med + 3 * mad, color="#d0342c", lw=0.6, ls=":")
        for s in MARK:
            if s in v.index:
                p = list(v.index).index(s)
                ax.scatter([p], [v[s]], s=26, zorder=3)
                ax.annotate(s, (p, v[s]), fontsize=8, xytext=(-26, 6), textcoords="offset points")
        ax.set_title(label, fontsize=10, loc="left")
    fig.suptitle("정해진 돌(실적 발표)에 대한 반응 — S&P 500 을 값 순서대로 줄 세움 · 최근 3년 · 빨간 점선 = 무리에서 3폭 위", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "earn_sorted.png"), dpi=100)

    # 반응 크기는 호수 크기가 그대로 비친 것인가
    rk = R[["react", "lake", "times", "stay", "big"]].rank()
    print(f"\n호수 크기(평소 등락)와 순위가 얼마나 같이 가나 — 반응 크기 {rk.react.corr(rk.lake):.2f} · 평소의 몇 배 {rk.times.corr(rk.lake):.2f} · 머문 비율 {rk.stay.corr(rk.lake):.2f}")
    calm_big = R[(R.lake.rank(pct=True) <= 0.35)].sort_values("times", ascending=False).head(10)
    print("평소엔 잔잔한데(호수 아래쪽 35%) 실적 때 크게 반응: " + ", ".join(f"{s} 평소의 {r.times:.1f}배 · ±5% {r.big}번" for s, r in calm_big.iterrows()))
    rough_small = R[(R.lake.rank(pct=True) >= 0.8)].sort_values("times").head(8)
    print("평소엔 거친데(호수 위쪽 20%) 실적 때는 평소와 비슷: " + ", ".join(f"{s} {r.times:.1f}배" for s, r in rough_small.iterrows()))
    R.round(3).to_csv(os.path.join(STORE, "earn_react_us.csv"))
    E = pd.DataFrame(each)
    for s in ("MSFT", "TSLA", "JPM", "KO"):
        x = E[E.sym == s].sort_values("day")
        print(f"{s} 실적 돌: " + " ".join(f"{r:+.1f}" for r in x.ret))


if __name__ == "__main__":
    main()
