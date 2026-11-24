"""뉴팩트 개성 있는 아이 찾기 게임 (A 갈래) — 반복 횟수 표 · 켜진 띠, 최근 3년 (2026-11-24 사용자 "계속 진행하자").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0절. 개성 = 반복(한 번은 우연), 주기 20 · 60 · 120 · 200일을 같이.

    python experiments/stock-character/look_repeat.py                 # JPM TSLA MSFT CRCL
    python experiments/stock-character/look_repeat.py NVDA KO

재는 것 — 모든 종목 같은 잣대(돌 = 하루 ±5%, 거래량 = 지난 250일 중앙값의 2배), 날마다 "최근 W일":
  호수        하루 폭 (고가 − 저가) ÷ 종가 의 중앙값
  돌          ±5% 넘은 날 수
  거래량 실린 돌   ±5% 이면서 거래량 2배 넘은 날 수
  거래량만 튐     거래량 2배 넘었는데 등락 2% 미만인 날 수
  방향 크기     W일 등락의 크기
켜짐 = 그날 그 값이 무리(S&P 500, 같은 날 같은 주기)에서 위쪽 5% 안(자기보다 작은 종목이 95% 이상).
한 번 = 켜진 날이 이어진 덩어리(5일 이상). 덩어리 사이가 W일 넘게 꺼져 있어야 따로 센다. 지속 = 켜져 있던 날 비율.
돌 뒤(둘 다) = 돌 하나하나에 대해 ① 물결 평온까지 ② 가격이 돌 전 자리까지 — look_numbers 의 함수 그대로.

무리 일봉 = data/store/character/bars_us.pkl (없으면 check_stage1.py 가 받는다 — 그 스크립트의 검증 결과는 쓰지 않는다).
그림 = output/graphs/repeat_<티커>.png (깃에 안 올림).
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
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PKL = os.path.join(ROOT, "data", "store", "character", "bars_us.pkl")
OUT = os.path.join(HERE, "output", "graphs")
sys.path.insert(0, HERE)
import look_numbers as LN  # noqa: E402 — calm_back · price_back · earn_days

WINS = [20, 60, 120, 200]
YEARS_DAYS = 756
TOP = 0.95
BOXES = [("lake", "호수"), ("stone", "돌"), ("vstone", "거래량 실린 돌"), ("vonly", "거래량만 튐"), ("dir", "방향 크기")]
NAMES = {"JPM": "JP모건", "TSLA": "테슬라", "MSFT": "마이크로소프트", "CRCL": "서클"}
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def wide(bars, col):
    return pd.DataFrame({s: d[col] for s, d in bars.items() if not s.startswith("^")})


def measures(H, L, C, V):
    """날짜 × 종목 표들 → {(칸, W): 날짜 × 종목}."""
    rng = (H - L) / C
    ret = C.pct_change() * 100
    volx = V / V.rolling(250, min_periods=60).median()
    stone = (ret.abs() >= LN.STONE).astype(float).where(ret.notna())
    vstone = ((ret.abs() >= LN.STONE) & (volx >= LN.VOL2)).astype(float).where(ret.notna() & volx.notna())
    vonly = ((volx >= LN.VOL2) & (ret.abs() < 2)).astype(float).where(ret.notna() & volx.notna())
    out = {}
    for w in WINS:
        mp = int(w * 0.9)
        out[("lake", w)] = rng.rolling(w, min_periods=mp).median()
        out[("stone", w)] = stone.rolling(w, min_periods=mp).sum()
        out[("vstone", w)] = vstone.rolling(w, min_periods=mp).sum()
        out[("vonly", w)] = vonly.rolling(w, min_periods=mp).sum()
        out[("dir", w)] = np.log(C / C.shift(w)).abs()
    return out


def episodes(on, w):
    """켜진 날 True/False → [(시작 위치, 끝 위치)] — 5일 이상, 사이가 w일 넘게 꺼져야 따로."""
    idx = np.flatnonzero(on.values)
    if not len(idx):
        return []
    runs, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > w:
            runs.append((s, p)); s = i
        p = i
    runs.append((s, p))
    return [(a, b) for a, b in runs if int(on.values[a:b + 1].sum()) >= 5]


def main():
    syms = sys.argv[1:] or ["JPM", "TSLA", "MSFT", "CRCL"]
    if not os.path.exists(PKL):
        sys.exit("무리 일봉이 없다 — 먼저 python experiments/stock-character/check_stage1.py (약 5분)")
    bars = pd.read_pickle(PKL)
    H, L, C, V = (wide(bars, c) for c in ("high", "low", "close", "volume"))
    last = C.index.max()
    extra = {}
    for s in syms:   # 무리에 없는 종목(서클 등)은 야후에서
        if s not in C.columns:
            d = yf.download(s, start="2015-01-01", interval="1d", auto_adjust=True, progress=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            d = d.rename(columns=str.lower).dropna(subset=["close"])
            d.index = pd.to_datetime(d.index).tz_localize(None)
            extra[s] = d[d.index <= last]
    crowd = measures(H, L, C, V)
    days = C.index[-YEARS_DAYS:]
    print(f"무리 {C.shape[1]}종목 · 기간 {days[0].date()} ~ {days[-1].date()} · 켜짐 = 무리 위쪽 {round((1 - TOP) * 100)}% 안")
    os.makedirs(OUT, exist_ok=True)

    for s in syms:
        if s in extra:
            e = extra[s]
            own = measures(*(e[[c]].rename(columns={c: s}) for c in ("high", "low", "close", "volume")))
            px = e["close"]
            one = e
        else:
            own = {k: v[[s]] for k, v in crowd.items()}
            px = C[s]
            one = pd.DataFrame({"open": bars[s]["open"], "high": H[s], "low": L[s], "close": C[s], "volume": V[s]})
        px = px.reindex(days).dropna()
        on_all = {}
        print(f"\n=== {NAMES.get(s, s)} ({s}) · 자료 {px.index[0].date()} ~ {px.index[-1].date()} ({len(px)}일)")
        print(f"{'칸':12} " + " ".join(f"{str(w) + '일':>16}" for w in WINS) + "    (켜진 횟수 · 켜져 있던 날 비율)")
        for box, label in BOXES:
            cells = []
            for w in WINS:
                v = own[(box, w)][s].reindex(px.index)
                cw = crowd[(box, w)].reindex(px.index)
                below = cw.lt(v, axis=0).sum(axis=1) / cw.notna().sum(axis=1)
                on = (below >= TOP) & v.notna()
                ep = episodes(on, w)
                on_all[(box, w)] = (on, ep)
                share = on.sum() / max(1, v.notna().sum()) * 100
                cells.append(f"{len(ep):>3}번 · {share:3.0f}%")
            print(f"{label:12} " + " ".join(f"{c:>16}" for c in cells))

        # 돌 하나하나 — 돌 뒤 둘 다
        d = one[(one["open"] > 0) & (one["volume"] > 0)].copy()
        d = d[d.index >= px.index[0] - pd.Timedelta(days=40)]
        d = d[d.index <= px.index[-1]]
        d["ret"] = d["close"].pct_change() * 100
        d["rng"] = (d["high"] - d["low"]) / d["close"] * 100
        d["volx"] = d["volume"] / d["volume"].rolling(250, min_periods=60).median().reindex(d.index).fillna(d["volume"].median())
        ed = LN.earn_days(s)
        st = [i for i in range(21, len(d)) if abs(d["ret"].iloc[i]) >= LN.STONE]
        n_e = sum(any(abs((d.index[i].normalize() - x).days) <= 1 for x in ed) for i in st)
        pb = [LN.price_back(d, i) for i in st]
        cb = [LN.calm_back(d, i) for i in st]
        back20 = sum(isinstance(x, int) and x <= 20 for x, _ in pb)
        stay = sum(x == "안 돌아옴" or (isinstance(x, int) and x > 60) for x, _ in pb)
        calm = [x for x in cb if isinstance(x, int)]
        vs = sum(d["volx"].iloc[i] >= LN.VOL2 for i in st)
        print(f"돌 {len(st)}개(3년) — 실적일 근처 {n_e} · 거래량 실림 {vs} · 가격이 20일 안에 돌 전 자리로 {back20} · 60일 넘게 안 돌아옴(계단) {stay} · "
              f"물결 평온까지 중앙값 {np.median(calm) if calm else '—'}일")

        # 그림 — 가격 + 켜진 띠
        fig, (a, b) = plt.subplots(2, 1, figsize=(15, 8), gridspec_kw={"height_ratios": [2.2, 3]}, sharex=True)
        a.plot(px.index, px.values, color="#1c2330", lw=1.1)
        a.set_yscale("log")
        a.set_title(f"{NAMES.get(s, s)} ({s}) — 가격(위) · 개성이 켜진 때(아래, 무리 위쪽 5% 안) · 숫자 = 켜진 횟수", loc="left", fontsize=11)
        colors = {"lake": "#2f6fdb", "stone": "#d0342c", "vstone": "#e08a00", "vonly": "#8a5fd0", "dir": "#1f9d6b"}
        rows = [(box, w) for box, _ in BOXES for w in WINS]
        for r, (box, w) in enumerate(rows):
            on, ep = on_all[(box, w)]
            y = len(rows) - 1 - r
            xs = px.index[on.values]
            b.scatter(xs, [y] * len(xs), marker="|", s=90, color=colors[box], linewidths=1.2)
            b.text(px.index[-1] + pd.Timedelta(days=8), y, f"{len(ep)}번", va="center", fontsize=8, color=colors[box])
        b.set_yticks(range(len(rows)))
        b.set_yticklabels([f"{dict(BOXES)[box]} {w}일" for box, w in rows][::-1], fontsize=8)
        for k in range(1, len(BOXES)):
            b.axhline(k * len(WINS) - 0.5, color="#d5d9e0", lw=0.8)
        b.set_ylim(-0.7, len(rows) - 0.3)
        b.set_xlim(days[0], days[-1] + pd.Timedelta(days=40))
        b.grid(axis="x", color="#eef0f4", lw=0.6)
        a.grid(axis="x", color="#eef0f4", lw=0.6)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"repeat_{s}.png"), dpi=100)
        plt.close(fig)
    print("\n그림 →", OUT)


if __name__ == "__main__":
    main()
