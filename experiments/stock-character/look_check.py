"""뉴팩트 개성 있는 아이 찾기 게임 — 이름만 나온 아이들을 그림으로 확인 (2026-11-24 사용자 "그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-3 "다. 숫자만 있고 그림으로는 안 본 것" → 7-17.
새로 재지 않는다 — 이미 뽑은 이름을 한 장에 모아 눈으로 본다. 모든 칸 세로 눈금 폭 같음(로그, 가운데 맞춤).

    python experiments/stock-character/look_check.py

  check_calm.png    늘 잔잔한 8명(7-8) + 견줄 아이 둘(마이크로소프트 · 테슬라)
  check_repeat.png  민감 구간이 예고 없는 돌로 갑자기 끝난 일이 되풀이된 9명(7-13) — 노란 띠 = 민감 구간, 빨간 세로선 = 그렇게 끝난 날
빨강 점 = 예고 없는 돌 · 회색 = 정해진 돌 · 파랑 = 파도 돌 · 아래 = 거래량 배수.
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

CALM = ["BRK-B", "KO", "RSG", "PG", "L", "LIN", "WM", "JNJ", "MSFT", "TSLA"]
REPEAT = ["LRCX", "ANET", "APP", "COHR", "AMAT", "KLAC", "HPE", "HOOD", "VRT"]
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def sheet(syms, fname, title, bars, eg, waves, F, cols, span):
    rows = int(np.ceil(len(syms) / cols))
    fig, axs = plt.subplots(rows * 2, cols, figsize=(6.2 * cols, 4.4 * rows), gridspec_kw={"height_ratios": [3, 1] * rows})
    for k in range(rows * cols):
        a, b = axs[(k // cols) * 2, k % cols], axs[(k // cols) * 2 + 1, k % cols]
        if k >= len(syms):
            a.axis("off"); b.axis("off"); continue
        s = syms[k]
        pr = LS.profile(s, bars[s], eg[s], waves)
        d = pr["_d"]
        lc = np.log(d["close"])
        mid = (lc.max() + lc.min()) / 2
        a.plot(d.index, lc, color="#1c2330", lw=0.9)
        a.set_ylim(mid - span / 2, mid + span / 2)
        f = F[F.sym == s]
        for _, e in f.iterrows():
            a.axvspan(max(e.start, d.index[0]), e.end if pd.notna(e.end) else d.index[-1], color="#f6d9a8", alpha=0.4, lw=0)
        hitn = 0
        for _, e in f[(~f.ongoing) & (f.fall_days <= 5) & (f.kind == "예고 없는")].iterrows():
            a.axvline(e.end, color="#d0342c", lw=1.0, ls="--"); hitn += 1
        for key, col in (("_sc", "#9aa3b2"), ("_wv", "#2f6fdb"), ("_un", "#d0342c")):
            a.scatter(pr[key], lc.reindex(pr[key]), s=10, color=col, zorder=4)
        a.set_yticks([]); a.set_xticks([])
        a.set_title(f"{s} · 호수 {pr['lake']:.1f}% · 돌: 예고 없는 {pr['un']} · 정해진 {pr['sched']} · 파도 {pr['wave']} · 민감 구간 {len(f)}번"
                    + (f" · 그중 예고 없는 돌로 갑자기 끝남 {hitn}번" if hitn else ""), fontsize=8.5, loc="left")
        vx = d["volume"] / d["volume"].rolling(250, min_periods=60).median()
        b.bar(d.index, vx.clip(upper=6), width=1.5, color=["#e08a00" if v >= 2 else "#c3c9d4" for v in vx.fillna(0)])
        b.set_ylim(0, 6); b.tick_params(labelsize=7)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(os.path.join(OUT, fname), dpi=88)
    plt.close(fig)


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    F = pd.read_csv(os.path.join(STORE, "fragile_us.csv"), parse_dates=["start", "end"])
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-LS.DAYS:]
    waves = set(share[share >= LS.WAVE_SHARE].index)
    os.makedirs(OUT, exist_ok=True)
    sheet(CALM, "check_calm.png", "늘 잔잔한 8명 + 견줄 아이 둘(마이크로소프트 · 테슬라) — 3년, 모든 칸 세로 눈금 폭 같음(위아래 = 약 4.5배)", bars, eg, waves, F, 5, np.log(4.5))
    sheet(REPEAT, "check_repeat.png", "민감 구간이 예고 없는 돌로 갑자기 끝난 일이 되풀이된 9명 — 노란 띠 = 민감 구간 · 빨간 세로선 = 그렇게 끝난 날 (세로 눈금 폭 = 약 20배)", bars, eg, waves, F, 3, np.log(20))
    print("그림 →", OUT)


if __name__ == "__main__":
    main()
