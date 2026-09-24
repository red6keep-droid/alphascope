"""r01 공통 — 전제 조건 적용 · 앞으로 수익률 · 지표 · 기준선 · 분할 축.

전제 조건은 doc/알파-종목-매수-타이밍-검증-계획.md 2절 (2026-09-24 확정):
  1 SPY 종가 < 200일선인 날은 신호일에서 제외          → signal_ok
  2 S&P 500 현재 구성, 편입일 이후만                     → valid (removed 종목은 제외일까지)
  3 진입 = 신호일 다음 거래일 시가                        → fwd = close(t+h) / open(t+1) − 1
  4 보유 1 · 2 · 3 · 5 · 10 · 20                        → HORIZONS
  5 왕복 비용 0.2%                                       → COST
  6 승률 = 비용 후 > 0. 기준선 = 같은 종목 · 같은 필터 · 무작위 날
  7 손익비 · 기대값 · MAE · 진입 갭 · 하루 신호 수

모든 값은 (거래일 × 종목) 넓은 표로 든다. 신호는 같은 모양의 bool 표.
"""

import math
import os

import numpy as np
import pandas as pd

import config
import universe

HORIZONS = [1, 2, 3, 5, 10, 20]
COST = config.COST_ROUND_TRIP
SPY_MA = 200
MIN_N = 300           # 이 아래 칸은 † (해석 안 함)
THIN_N = 1000         # 이 아래 칸은 ‡ (방향만)
B = 500               # 플라시보 재추출 횟수
OUT = config.OUTPUT_DIR
VIX_BUCKETS = [(0, 15, "VIX<15"), (15, 20, "15~20"), (20, 30, "20~30"), (30, 999, "VIX>30")]


def _wide(bars, syms, col, index):
    return pd.DataFrame({s: bars[s][col] for s in syms if s in bars}).reindex(index)


class Data:
    pass


def load(include_removed=False):
    D = Data()
    bars = pd.read_pickle(os.path.join(config.DATA_DIR, "bars.pkl"))
    uni = universe.load()
    uni["added"] = pd.to_datetime(uni["added"])
    uni = uni[uni["symbol"].isin(bars)].reset_index(drop=True)
    spy = bars[config.BENCHMARK]
    days = spy.index
    syms = list(uni["symbol"])
    sector = dict(zip(uni["symbol"], uni["sector"]))
    added = dict(zip(uni["symbol"], uni["added"]))
    until = {}
    if include_removed:
        rem = pd.read_csv(os.path.join(config.DATA_DIR, "removed.csv"), parse_dates=["removed"])
        rbars = pd.read_pickle(os.path.join(config.DATA_DIR, "removed.pkl"))
        for s, d in zip(rem["symbol"], rem["removed"]):
            if s in rbars and s not in bars:
                bars[s] = rbars[s]
                syms.append(s)
                sector[s] = "Removed"
                added[s] = pd.Timestamp("1900-01-01")
                until[s] = d
    D.days, D.syms, D.sector = days, syms, sector
    D.C = _wide(bars, syms, "Close", days)
    D.O = _wide(bars, syms, "Open", days)
    D.H = _wide(bars, syms, "High", days)
    D.L = _wide(bars, syms, "Low", days)
    D.V = _wide(bars, syms, "Volume", days)
    D.spy = spy
    D.vix = bars[config.VIX]["Close"].reindex(days)
    D.etf = {k: bars[v] for k, v in config.SECTOR_ETF.items() if v in bars}

    # 전제 조건 2 — 편입일 이후 (제외 종목은 제외일까지)
    add_row = pd.Series({s: added[s] for s in syms})
    valid = D.C.notna() & (pd.DataFrame(np.tile(days.values[:, None], (1, len(syms))), index=days, columns=syms) >= add_row.values)
    if until:
        for s, d in until.items():
            valid.loc[valid.index > d, s] = False
    D.valid = valid
    # 전제 조건 1 — SPY 200일선
    macro = pd.read_pickle(os.path.join(config.DATA_DIR, "macro.pkl"))
    sc = macro["SPY_long"]["Close"] if "SPY_long" in macro else spy["Close"]   # 200일선은 2014년부터 있어야 2016년 초를 판정할 수 있다
    D.spy_ok = (sc > sc.rolling(SPY_MA).mean()).reindex(days).fillna(False)
    D.study = pd.Series(days >= pd.Timestamp(config.STUDY_START), index=days)
    D.signal_ok = valid & (D.spy_ok & D.study).values[:, None]

    # 전제 조건 3 · 4 · 5 — 앞으로 수익률 (비용 전), 진입 갭, MAE, SPY 동일 구간
    entry = D.O.shift(-1)
    D.fwd = {h: D.C.shift(-h) / entry - 1 for h in HORIZONS}
    D.gap = entry / D.C - 1
    D.mae = {}
    lo = D.L.shift(-1)
    for k in range(1, max(HORIZONS) + 1):
        if k > 1:
            lo = np.minimum(lo, D.L.shift(-k))
        if k in HORIZONS:
            D.mae[k] = lo / entry - 1
    so, sc2 = spy["Open"].reindex(days), spy["Close"].reindex(days)
    D.spy_fwd = {h: (sc2.shift(-h) / so.shift(-1) - 1) for h in HORIZONS}

    # 분할 축
    D.period = pd.Series(np.where(days < pd.Timestamp(config.SPLIT_DAY), "탐색 ~2022", "검증 2023~"), index=days)
    D.year = pd.Series(days.year, index=days)
    D.vix_bucket = pd.cut(D.vix, [b[0] for b in VIX_BUCKETS] + [999], labels=[b[2] for b in VIX_BUCKETS], right=False).astype(str)
    tnx = macro["^TNX"]["Close"].reindex(days).ffill()
    D.rate_dir = pd.Series(np.where(tnx - tnx.shift(20) > 0, "금리 상승", "금리 하락"), index=days)
    D.macro = macro
    D.earn_adj = _earnings_mask(D, syms)
    D.regime = None            # sectors.py 가 채운다: (거래일 × 종목) 국면 라벨
    return D


def _earnings_mask(D, syms):
    e = pd.read_csv(os.path.join(config.DATA_DIR, "earnings.csv"), parse_dates=["day"])
    m = np.zeros(D.C.shape, dtype=bool)
    col = {s: i for i, s in enumerate(syms)}
    days = D.days.values
    for s, g in e.groupby("symbol"):
        if s not in col:
            continue
        pos = np.searchsorted(days, g["day"].values.astype("datetime64[ns]"))
        for p in pos:
            for q in (p - 1, p, p + 1):
                if 0 <= q < len(days):
                    m[q, col[s]] = True
    return pd.DataFrame(m, index=D.days, columns=syms)


# ---------------------------------------------------------------- 신호 정리
def cluster(mask, h):
    """같은 종목에서 h 거래일 안에 다시 뜨는 신호는 첫 건만 남긴다 (보유 구간 겹침 방지)."""
    out = np.zeros(mask.shape, dtype=bool)
    m = mask.values
    for j in range(m.shape[1]):
        idx = np.flatnonzero(m[:, j])
        last = -10 ** 9
        for i in idx:
            if i - last > h:
                out[i, j] = True
                last = i
    return pd.DataFrame(out, index=mask.index, columns=mask.columns)


# ---------------------------------------------------------------- 통계
def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - half, c + half)


def evaluate(D, mask, h, placebo=False, seed=0):
    """한 칸. mask = 신호 (거래일 × 종목 bool, 이미 signal_ok 와 cluster 적용). 반환 dict 또는 None."""
    fwd = D.fwd[h]
    m = mask.values & fwd.notna().values
    if m.sum() == 0:
        return None
    r = fwd.values[m] - COST
    rows, cols = np.nonzero(m)
    n = len(r)
    wins = r > 0
    win = wins.mean()
    pos, neg = r[r > 0], r[r < 0]
    payoff = pos.mean() / abs(neg.mean()) if len(pos) and len(neg) else np.nan
    mae = D.mae[h].values[m]
    gap = D.gap.values[m]
    spy = D.spy_fwd[h].values[rows]
    # 기준선 — 같은 종목 · 같은 필터 · 신호 아닌 날. 종목별 풀 승률을 신호 수로 가중
    pool = D.signal_ok.values & ~mask.values & fwd.notna().values
    pr = fwd.values - COST
    pool_win = np.where(pool, pr > 0, False).sum(0) / np.maximum(pool.sum(0), 1)
    pool_mean = np.where(pool, pr, 0).sum(0) / np.maximum(pool.sum(0), 1)
    k = np.bincount(cols, minlength=m.shape[1])
    base_win = (k * pool_win).sum() / n
    base_mean = (k * pool_mean).sum() / n
    out = {
        "n": n, "days": len(np.unique(rows)), "per_day": n / max(len(np.unique(rows)), 1),
        "win": win, "win_lo": wilson(wins.sum(), n)[0], "win_hi": wilson(wins.sum(), n)[1],
        "base_win": base_win, "diff": win - base_win,
        "mean": r.mean(), "base_mean": base_mean, "median": np.median(r),
        "payoff": payoff, "mae_med": np.nanmedian(mae), "mae_p10": np.nanpercentile(mae, 10),
        "gap_med": np.nanmedian(gap), "excess_spy": np.nanmean(r + COST - spy),
        "p_win": np.nan, "day_hit": np.nan, "day_t": np.nan,
    }
    # 날짜 단위 — 신호일마다 신호 종목 평균 vs 그날 풀(신호 아닌 종목) 평균
    ev_sum = np.bincount(rows, weights=r, minlength=m.shape[0])
    ev_n = np.bincount(rows, minlength=m.shape[0])
    pool_sum = np.where(pool, pr, 0).sum(1)
    pool_n = pool.sum(1)
    ok = (ev_n > 0) & (pool_n >= 20)
    if ok.sum() >= 5:
        d = ev_sum[ok] / ev_n[ok] - pool_sum[ok] / pool_n[ok]
        out["day_hit"] = (d > 0).mean()
        out["day_t"] = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else np.nan
    if placebo:
        rng = np.random.default_rng(config.SEED + seed)
        tot = np.zeros(B)
        used = 0
        for j in np.flatnonzero(k):
            arr = pr[pool[:, j], j]
            if len(arr) < 50:
                continue
            samp = arr[rng.integers(0, len(arr), size=(B, k[j]))]
            tot += (samp > 0).sum(1)
            used += k[j]
        if used:
            obs = wins[np.isin(cols, np.flatnonzero(k))].sum()  # 전체 관측 승수 (풀 부족 종목 포함 — 근사)
            out["p_win"] = ((tot / used >= win).sum() + 1) / (B + 1)
    return out


def flag(n):
    return "†" if n < MIN_N else ("‡" if n < THIN_N else "")


def fmt_row(label, s):
    if s is None:
        return f"| {label} | 0 | | | | | | | | | | | |"
    f = flag(s["n"])
    p = "—" if np.isnan(s["p_win"]) else f"{s['p_win']:.3f}"
    dh = "—" if np.isnan(s["day_hit"]) else f"{s['day_hit']:.0%}"
    dt = "—" if np.isnan(s["day_t"]) else f"{s['day_t']:.1f}"
    return (f"| {label} | {s['n']:,}{f} | {s['win']:.1%} | {s['base_win']:.1%} | **{s['diff'] * 100:+.1f}** | {p} | "
            f"{s['mean'] * 100:+.2f}% | {s['base_mean'] * 100:+.2f}% | {s['payoff']:.2f} | {s['mae_med'] * 100:.1f}% / {s['mae_p10'] * 100:.1f}% | "
            f"{s['gap_med'] * 100:+.2f}% | {dh} / {dt} | {s['per_day']:.1f} |")


HEADER = ("| 구분 | n | 승률 | 기준선 | 차이 %p | p | 평균 | 기준선 평균 | 손익비 | MAE 중앙/10% | 진입 갭 | 이긴 날 / t | 하루 신호 |\n"
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

LEGEND = ("- **n** 신호 수(† 300 미만: 해석 안 함, ‡ 1,000 미만: 방향만) · **승률** 비용 0.2% 차감 후 > 0 · **기준선** 같은 종목·같은 필터·신호 아닌 날의 승률(신호 수 가중) · "
          "**차이** 승률 − 기준선 · **p** 플라시보(같은 종목 비신호 날 재추출 500회, 관측 이상 비율) · **손익비** 평균 이익 ÷ 평균 손실 · "
          "**MAE** 진입 후 최저가 손실(중앙값 / 하위 10%) · **진입 갭** 다음 날 시가 ÷ 신호일 종가 − 1 · **이긴 날 / t** 신호일 단위로 그날 비신호 종목 평균을 이긴 비율과 t 통계량")


def split_table(D, mask, h, axis, name, seed=0):
    """axis: 거래일 Series(라벨) 또는 (거래일 × 종목) DataFrame(라벨). 라벨별 evaluate."""
    lines = [f"**{name}**", "", HEADER]
    if isinstance(axis, pd.Series):
        labels = [l for l in pd.unique(axis) if isinstance(l, str) and l != "nan"]
        for l in labels:
            sub = mask & (axis == l).values[:, None]
            lines.append(fmt_row(l, evaluate(D, sub, h, seed=seed)))
    else:
        labels = [l for l in pd.unique(axis.values.ravel()) if isinstance(l, str) and l != "nan"]
        for l in sorted(labels):
            sub = mask & (axis == l).values
            lines.append(fmt_row(l, evaluate(D, sub, h, seed=seed)))
    return "\n".join(lines) + "\n"


def year_table(D, mask, h):
    """연도별 차이만 — 기준선을 이긴 해 수를 센다."""
    rows, beat, tot = [], 0, 0
    for y in sorted(D.year.unique()):
        s = evaluate(D, mask & (D.year == y).values[:, None], h)
        if s is None or s["n"] < 30:
            continue
        tot += 1
        beat += s["diff"] > 0
        rows.append(f"{y}: {s['diff'] * 100:+.1f}{flag(s['n'])}")
    return f"기준선을 이긴 해 **{beat}/{tot}** — " + " · ".join(rows)


def bool_axis(mask_true, label_true, label_false):
    return pd.DataFrame(np.where(mask_true.values, label_true, label_false), index=mask_true.index, columns=mask_true.columns)
