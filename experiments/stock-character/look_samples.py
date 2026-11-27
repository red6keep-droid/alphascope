"""샘플 종목 그래프 눈으로 보기 — 가격 + 하루 등락 + 거래량, 네 종목 같은 눈금.

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md (4절 1번 "그래프를 먼저 본다").


    python experiments/stock-character/look_samples.py                # 기본 네 종목
    python experiments/stock-character/look_samples.py JPM TSLA MSFT CRCL

그림 = experiments/stock-character/output/graphs/ (깃에 안 올림). 통계 검증 없음 — 보는 용도.
  look_3m.png · look_6m.png · look_1y.png   기간별, 종목 = 세로 칸, 위에서부터 가격(시작 = 0%, 로그 눈금) · 하루 등락(%) · 거래량(1년 평소의 몇 배)
  look_2m_pieces.png                        최근 1년을 2개월 조각 6개로 — 조각마다 시작 = 0% 로 다시 맞춰 꼴만 견줌
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output", "graphs")
NAMES = {"JPM": "JP모건(금융)", "TSLA": "테슬라", "MSFT": "마이크로소프트", "CRCL": "서클"}
UP, DOWN, INK, MUTE = "#d0342c", "#2f6fdb", "#1c2330", "#8a93a3"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def load(syms):
    out = {}
    for s in syms:
        d = yf.download(s, period="2y", interval="1d", auto_adjust=True, progress=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.rename(columns=str.lower).dropna(subset=["close"])
        d = d[(d["open"] > 0) & (d["volume"] > 0)]
        d["ret"] = d["close"].pct_change() * 100
        d["volx"] = d["volume"] / d["volume"].iloc[-252:].median()   # 최근 1년 평소(중앙값)의 몇 배
        out[s] = d
    return out


def pct_ticks(ax, lo, hi):
    """로그 눈금 위에 % 로 읽히는 눈금."""
    cand = [-80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 50, 75, 100, 150, 200, 300, 400]
    ticks = [c for c in cand if lo <= np.log(1 + c / 100) <= hi]
    if len(ticks) > 9:
        ticks = ticks[::2] if 0 in ticks[::2] else ticks[1::2]
    ax.set_yticks([np.log(1 + c / 100) for c in ticks])
    ax.set_yticklabels([f"{c:+d}%" if c else "0%" for c in ticks])


def draw_price(ax, d, lo, hi):
    base = d["close"].iloc[0]
    x = np.arange(len(d))
    ax.vlines(x, np.log(d["low"] / base), np.log(d["high"] / base), color=MUTE, lw=1.0)
    ax.plot(x, np.log(d["close"] / base), color=INK, lw=1.2)
    ax.axhline(0, color=MUTE, lw=0.6, ls=":")
    ax.set_ylim(lo, hi)
    pct_ticks(ax, lo, hi)


def draw_ret(ax, d, lim):
    x = np.arange(len(d))
    r = d["ret"].fillna(0).values
    ax.bar(x, np.clip(r, -lim, lim), color=[UP if v > 0 else DOWN for v in r], width=0.8)
    ax.axhline(0, color=MUTE, lw=0.6)
    for y in (-5, 5):
        ax.axhline(y, color=MUTE, lw=0.5, ls=":")
    ax.set_ylim(-lim, lim)


def draw_vol(ax, d, lim):
    x = np.arange(len(d))
    v = d["volx"].values
    ax.bar(x, np.clip(v, 0, lim), color=["#e08a00" if a >= 2 else "#b9c0cc" for a in v], width=0.8)
    ax.axhline(1, color=MUTE, lw=0.6, ls=":")
    ax.axhline(2, color="#e08a00", lw=0.5, ls=":")
    ax.set_ylim(0, lim)


def month_marks(axes, d):
    """달이 바뀌는 자리에 옅은 세로선 + 맨 아래 칸에 달 이름."""
    idx = d.index
    pos = [i for i in range(1, len(idx)) if idx[i].month != idx[i - 1].month]
    for ax in axes:
        for p in pos:
            ax.axvline(p - 0.5, color="#e3e6ec", lw=0.6, zorder=0)
        ax.set_xlim(-1, len(idx))
    step = max(1, len(pos) // 6)
    axes[-1].set_xticks([p for p in pos[::step]])
    axes[-1].set_xticklabels([f"{idx[p].year % 100}.{idx[p].month}" for p in pos[::step]], fontsize=8)
    for ax in axes[:-1]:
        ax.set_xticks([])


def facts(d):
    """그림 아래 붙이는 쉬운 숫자 — 눈으로 본 것을 적어 두는 용도."""
    hl = ((d["high"] - d["low"]) / d["close"] * 100).median()
    big = int((d["ret"].abs() >= 5).sum())
    v2 = int((d["volx"] >= 2).sum())
    tot = (d["close"].iloc[-1] / d["close"].iloc[0] - 1) * 100
    return f"기간 {tot:+.0f}% · 하루 폭 {hl:.1f}% · ±5% 넘은 날 {big} · 거래량 2배 넘은 날 {v2}"


def window_fig(data, syms, n, label, fname):
    cut = {s: data[s].iloc[-n:] for s in syms}
    span = max(max(abs(np.log(c["high"] / c["close"].iloc[0])).max(), abs(np.log(c["low"] / c["close"].iloc[0])).max()) for c in cut.values()) * 1.05
    rlim = 20
    vlim = 6
    fig, axs = plt.subplots(3, len(syms), figsize=(4.6 * len(syms), 8.2), gridspec_kw={"height_ratios": [3, 1.6, 1.3]}, sharey="row")
    for j, s in enumerate(syms):
        c = cut[s]
        draw_price(axs[0, j], c, -span, span)
        draw_ret(axs[1, j], c, rlim)
        draw_vol(axs[2, j], c, vlim)
        month_marks([axs[0, j], axs[1, j], axs[2, j]], c)
        axs[0, j].set_title(f"{NAMES.get(s, s)} ({s})\n{facts(c)}", fontsize=10, loc="left")
    axs[0, 0].set_ylabel("가격 (시작 = 0%)")
    axs[1, 0].set_ylabel("하루 등락 %\n(점선 = ±5%)")
    axs[2, 0].set_ylabel("거래량\n(1년 평소의 몇 배)")
    fig.suptitle(f"최근 {label} · 일봉 · 네 종목 같은 눈금 ({cut[syms[0]].index[0].date()} ~ {cut[syms[0]].index[-1].date()})", fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(os.path.join(OUT, fname), dpi=110)
    plt.close(fig)


def pieces_fig(data, syms, fname, piece=42, k=6):
    """최근 1년을 2개월(42거래일) 조각 6개로 — 조각마다 시작 = 0% 로 다시 맞춰 꼴만 견준다. 왼쪽 = 옛날, 오른쪽 = 최근."""
    cuts = {s: [data[s].iloc[len(data[s]) - piece * (k - i): len(data[s]) - piece * (k - i - 1)] for i in range(k)] for s in syms}
    span = max(max(abs(np.log(c["high"] / c["close"].iloc[0])).max(), abs(np.log(c["low"] / c["close"].iloc[0])).max())
               for cs in cuts.values() for c in cs if len(c)) * 1.05
    fig, axs = plt.subplots(len(syms) * 2, k, figsize=(3.1 * k, 3.6 * len(syms)), gridspec_kw={"height_ratios": [3, 1.2] * len(syms)})
    for i, s in enumerate(syms):
        for j, c in enumerate(cuts[s]):
            a, b = axs[2 * i, j], axs[2 * i + 1, j]
            if len(c) < 5:
                a.axis("off"); b.axis("off"); continue
            draw_price(a, c, -span, span)
            draw_vol(b, c, 6)
            a.set_xticks([]); b.set_xticks([])
            a.set_xlim(-1, piece); b.set_xlim(-1, piece)
            hl = ((c["high"] - c["low"]) / c["close"] * 100).median()
            a.set_title(f"{c.index[0].year % 100}.{c.index[0].month}~{c.index[-1].month}월 · 폭 {hl:.1f}% · ±5% {int((c['ret'].abs() >= 5).sum())}일 · 거래량2배 {int((c['volx'] >= 2).sum())}일", fontsize=8, loc="left")
            if j:
                a.set_yticklabels([]); b.set_yticklabels([])
            else:
                a.set_ylabel(NAMES.get(s, s), fontsize=10)
                b.set_ylabel("거래량", fontsize=8)
    fig.suptitle("최근 1년을 2개월 조각으로 — 조각마다 시작 = 0%, 모든 칸 같은 눈금 (왼쪽 옛날 → 오른쪽 최근)", fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(OUT, fname), dpi=100)
    plt.close(fig)


def main():
    syms = sys.argv[1:] or ["JPM", "TSLA", "MSFT", "CRCL"]
    os.makedirs(OUT, exist_ok=True)
    data = load(syms)
    for s in syms:
        print(f"{s}: {data[s].index[0].date()} ~ {data[s].index[-1].date()} · {len(data[s])}일")
    window_fig(data, syms, 63, "3개월", "look_3m.png")
    window_fig(data, syms, 126, "6개월", "look_6m.png")
    window_fig(data, syms, 252, "1년", "look_1y.png")
    pieces_fig(data, syms, "look_2m_pieces.png")
    print("그림 →", OUT)


if __name__ == "__main__":
    main()
