"""뉴팩트 개성 있는 아이 찾기 게임 — 3단계 개성 카드 (2026-11-24 사용자 "순서대로 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-7(3단계) · 7-16.
후보 한 명씩: 그래프 눈 확인 + 몇 번 · 언제 + 여섯 칸 값과 무리 안 자리. 평범 판정은 하지 않는다 — 눈에 띈 것을 적는다.

    python experiments/stock-character/look_card.py                  # 꼴이 다른 여섯 명
    python experiments/stock-character/look_card.py NVDA AMD

먼저 돌려 둘 것: look_stones.py(stones_us.csv) · look_earn.py(earn_react_us.csv) · look_fragile.py(fragile_us.csv).
그림 = output/graphs/card_<티커>.png — 위 가격(빨강 = 예고 없는 돌 · 회색 = 정해진 돌 · 파랑 = 파도 돌 · 노란 띠 = 민감 구간), 가운데 거래량 배수, 아래 60일 조각별 예고 없는 돌 수.
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

DEFAULT = ["COIN", "GLW", "TSLA", "SCHW", "KO", "MSI"]
NAMES = {"COIN": "코인베이스", "GLW": "코닝", "TSLA": "테슬라", "SCHW": "찰스 슈왑", "KO": "코카콜라", "MSI": "모토로라 솔루션스", "MSFT": "마이크로소프트"}
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def top_pct(series, s):
    """무리에서 위에서 몇 % 자리인가."""
    v = series.dropna()
    return (v > v[s]).mean() * 100 if s in v.index else np.nan


def where(p):
    if np.isnan(p):
        return "자료 없음"
    if p < 1:
        return "무리 맨 위"
    if p > 99:
        return "무리 맨 아래"
    return f"무리 위에서 {p:.0f}%" if p <= 50 else f"무리 아래에서 {100 - p:.0f}%"


def shape(pc):
    a, b = sum(pc[:8]), sum(pc[8:])
    if sum(x >= 2 for x in pc) >= 11:
        return "늘 켜져 있음"
    if sum(pc) <= 3:
        return "거의 없음"
    if b / 4 >= 3 * max(a / 8, 0.5):
        return "최근 1년에 켜짐"
    if a / 8 >= 3 * max(b / 4, 0.5):
        return "최근 1년에 꺼짐"
    return "켜졌다 꺼졌다"


def main():
    syms = sys.argv[1:] or DEFAULT
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    S = pd.read_csv(os.path.join(STORE, "stones_us.csv")).set_index("sym")
    R = pd.read_csv(os.path.join(STORE, "earn_react_us.csv")).set_index("sym")
    F = pd.read_csv(os.path.join(STORE, "fragile_us.csv"), parse_dates=["start", "end"])
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-LS.DAYS:]
    waves = set(share[share >= LS.WAVE_SHARE].index)
    dirn = (np.log(C / C.shift(60)).abs() * 100).iloc[-LS.DAYS:]
    os.makedirs(OUT, exist_ok=True)
    for s in syms:
        pr = LS.profile(s, bars[s], eg[s], waves)
        d, pc = pr["_d"], pr["pieces"]
        f = F[F.sym == s]
        fin = f[~f.ongoing]
        sudden = int((fin.fall_days <= 5).sum())
        lines = [f"■ {NAMES.get(s, s)} ({s}) — 최근 3년 ({d.index[0].date()} ~ {d.index[-1].date()})"]
        lines.append(f"① 호수(평소 하루 폭) {pr['lake']:.1f}% — {where(top_pct(S.lake, s))}")
        lines.append(f"② 예고 없는 돌(실적 · 파도 날이 아닌 ±5%) {pr['un']}개 — {where(top_pct(S.un, s))} · {shape(pc)} · 60일 조각 12개 중 {pr['on_pieces']}개에서 2개 넘게"
                     f" · 조각별 {pc}")
        lines.append(f"   정해진 돌(실적 · 공시 날) {pr['sched']}개 · 파도 돌 {pr['wave']}개")
        if pr["un"]:
            lines.append(f"③ 예고 없는 돌에 거래량이 실린 비율 {pr['un_vol'] * 100:.0f}% (2배 넘음) · ④ 20일 안에 돌 전 자리로 돌아온 비율 {pr['un_back'] * 100:.0f}%")
        else:
            lines.append("③ ④ 예고 없는 돌이 없어 잴 것이 없음")
        dv = dirn[s].dropna()
        lines.append(f"⑤ 방향 크기(60일 등락) 지금 {dv.iloc[-1]:.0f}% · 3년 가운데 {dv.median():.0f}% · 가장 컸을 때 {dv.max():.0f}% ({dv.idxmax().date()})")
        if s in R.index:
            r = R.loc[s]
            lines.append(f"⑥ 정해진 돌(실적)에 대한 반응 — 반응 날 등락 {r.react:.1f}%({where(top_pct(R.react, s))}) · 평소의 {r.times:.1f}배({where(top_pct(R.times, s))}) · "
                         f"{int(r.n)}번 중 ±5% 넘은 것 {int(r.big)}번 · 20일 뒤에도 머문 비율 {r.stay * 100:.0f}%")
        lines.append(f"민감 구간(1년 고점 10% 안에 20일 넘게) {len(f)}번 · 끝난 {len(fin)}번 중 갑자기(5일 안) 끝남 {sudden}번 · 예고 없는 돌로 끝남 {int((fin.kind == '예고 없는').sum())}번"
                     + (f" · 지금 {int(f[f.ongoing].len.iloc[0])}일째 머무는 중" if f.ongoing.any() else " · 지금은 아님"))
        print("\n".join(lines) + "\n")

        fig, (a, b, c) = plt.subplots(3, 1, figsize=(15, 9.5), gridspec_kw={"height_ratios": [3.2, 1, 1]})
        a.plot(d.index, d["close"], color="#1c2330", lw=1.0)
        a.set_yscale("log")
        for _, e in f.iterrows():
            a.axvspan(max(e.start, d.index[0]), e.end if pd.notna(e.end) else d.index[-1], color="#f6d9a8", alpha=0.35, lw=0)
        for key, col in (("_sc", "#9aa3b2"), ("_wv", "#2f6fdb"), ("_un", "#d0342c")):
            a.scatter(pr[key], d["close"].reindex(pr[key]), s=16, color=col, zorder=4)
        a.set_title("  |  ".join(x for x in lines[:1]) + "   빨강 = 예고 없는 돌 · 회색 = 정해진 돌 · 파랑 = 파도 돌 · 노란 띠 = 민감 구간", fontsize=10, loc="left")
        vx = d["volume"] / d["volume"].rolling(250, min_periods=60).median()
        b.bar(d.index, vx.clip(upper=6), width=1.5, color=["#e08a00" if v >= 2 else "#c3c9d4" for v in vx.fillna(0)])
        b.set_ylim(0, 6); b.set_ylabel("거래량\n(평소의 몇 배)", fontsize=8)
        mids = [d.index[min(k * LS.PIECE + LS.PIECE // 2, len(d) - 1)] for k in range(len(pc))]
        c.bar(mids, pc, width=70, color="#e9a8a3")
        c.set_ylabel("60일 조각별\n예고 없는 돌", fontsize=8)
        for ax in (a, b, c):
            ax.set_xlim(d.index[0], d.index[-1]); ax.grid(axis="x", color="#eef0f4", lw=0.6)
        fig.text(0.012, 0.005, "\n".join(lines[1:]), fontsize=8.5, va="bottom", linespacing=1.5)
        fig.tight_layout(rect=(0, 0.17, 1, 1))
        fig.savefig(os.path.join(OUT, f"card_{s}.png"), dpi=95)
        plt.close(fig)
    print("그림 →", OUT)


if __name__ == "__main__":
    main()
