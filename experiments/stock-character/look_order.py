"""뉴팩트 개성 있는 아이 찾기 게임 — 가설 1 의 순서: 돈이 먼저냐 돌이 먼저냐 (2026-11-24 사용자 "순서대로 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-12 · 7-14.
사용자 가설: 돈 · 관심이 몰린 아이가 개성을 갖는다. 닭과 달걀(급등락이 거래를 부른다)을 가르려면 순서를 봐야 한다.

    python experiments/stock-character/look_order.py            # "최근 1년에 켜짐" 15명
    python experiments/stock-character/look_order.py GLW STX

아이마다 최근 3년을 20거래일 조각 37개로:
  거래량 배수   조각 평균 거래 주식 수 ÷ 첫 1년(12조각) 가운데 값 — 주가가 올라 거래대금이 저절로 커지는 것을 빼려고 **주식 수**로 잰다
  주가         조각 끝 종가 ÷ 첫 1년 가운데 값
  예고 없는 돌   조각 안 개수 (실적 · 파도 날 뺌)
처음 켜진 조각(두 조각 이어서 넘을 때 첫 조각): 거래량 1.5배 · 주가 +30% · 돌 3개. 셋의 순서와 간격(조각 = 약 한 달).
그림 = output/graphs/order_faces.png (검정 = 주가 · 주황 = 거래량 배수 · 빨간 막대 = 예고 없는 돌 수, 세로 점선 = 처음 켜진 때).
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
sys.path.insert(0, HERE)
import look_stones as LS  # noqa: E402
import look_money as LM  # noqa: E402

B = 20
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def first_on(v, th):
    for k in range(len(v) - 1):
        if v[k] >= th and v[k + 1] >= th:
            return k
    return None


def main():
    syms = sys.argv[1:] or LM.GROUPS["최근 1년에 켜짐"]
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-LS.DAYS:]
    waves = set(share[share >= LS.WAVE_SHARE].index)
    nb = LS.DAYS // B
    fig, axs = plt.subplots(4, 4, figsize=(22, 14))
    axs = axs.ravel()
    print(f"조각 = {B}거래일(약 한 달) · {nb}조각 · 처음 켜진 조각 번호(0 = 3년 전) — 거래량 1.5배 / 주가 +30% / 예고 없는 돌 3개")
    tally = {"거래량 먼저": [], "돌 먼저": [], "같은 조각": [], "가를 수 없음": []}
    for n, s in enumerate(syms[:16]):
        pr = LS.profile(s, bars[s], eg[s], waves)
        d = pr["_d"]
        un = pd.Series(1, index=pd.DatetimeIndex(pr["_un"]))
        vol = np.array([d["volume"].iloc[k * B:(k + 1) * B].mean() for k in range(nb)])
        px = np.array([d["close"].iloc[(k + 1) * B - 1] for k in range(nb)])
        st = np.array([int(un[(un.index >= d.index[k * B]) & (un.index <= d.index[(k + 1) * B - 1])].sum()) for k in range(nb)])
        vx, pxx = vol / np.median(vol[:12]), px / np.median(px[:12])
        kv, kp, ks = first_on(vx, 1.5), first_on(pxx, 1.3), first_on(st, 3)
        day = lambda k: "—" if k is None else f"{k}({d.index[k * B].strftime('%y.%m')})"   # noqa: E731
        if kv is None or ks is None:
            key = "가를 수 없음"
        elif kv < ks:
            key = "거래량 먼저"
        elif kv > ks:
            key = "돌 먼저"
        else:
            key = "같은 조각"
        gap = "" if kv is None or ks is None else f" · 간격 {abs(ks - kv)}조각"
        tally[key].append(s)
        print(f"  {s:5} 거래량 {day(kv):>10} · 주가 {day(kp):>10} · 돌 {day(ks):>10} → {key}{gap} | 돌 조각별 {st.tolist()}")
        ax = axs[n]
        x = np.arange(nb)
        ax.bar(x, st, color="#e9a8a3", width=0.8)
        ax.set_ylim(0, max(12, st.max() * 1.1))
        a2 = ax.twinx()
        a2.plot(x, vx, color="#e08a00", lw=1.4)
        a2.plot(x, pxx, color="#1c2330", lw=1.4)
        a2.axhline(1.5, color="#e08a00", lw=0.5, ls=":")
        a2.set_yscale("log")
        for k, col in ((kv, "#e08a00"), (ks, "#d0342c"), (kp, "#1c2330")):
            if k is not None:
                ax.axvline(k, color=col, lw=0.9, ls="--")
        ax.set_xticks(x[::6]); ax.set_xticklabels([d.index[k * B].strftime("%y.%m") for k in x[::6]], fontsize=7)
        ax.set_title(f"{s} — {key}{gap}", fontsize=9, loc="left")
    for k in range(len(syms[:16]), 16):
        axs[k].axis("off")
    print("\n순서: " + " | ".join(f"{k} {len(v)}명 ({', '.join(v)})" for k, v in tally.items()))
    fig.suptitle("돈이 먼저냐 돌이 먼저냐 — 검정 = 주가(첫 1년 = 1) · 주황 = 거래 주식 수 배수 · 분홍 막대 = 예고 없는 돌 수 · 점선 = 처음 켜진 조각(주황 거래량 · 빨강 돌 · 검정 주가)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "order_faces.png"), dpi=85)


if __name__ == "__main__":
    main()
