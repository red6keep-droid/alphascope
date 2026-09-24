"""신호 추출 · 통계 · 플라시보 검정.

승률 하나로는 답이 안 된다 — 상승장에서는 아무 날 사도 오를 확률이 55% 안팎이다.
그래서 모든 칸에 '같은 종목의 비신호 날을 같은 수만큼 샀을 때'의 승률과, 관측 승률이 그 분포에서
얼마나 극단적인지(p)를 함께 낸다. p 가 작아야 조건이 실제로 확률을 올린 것이다.
"""

import math

import numpy as np
import pandas as pd

import config

R = config.RULE

OUTCOMES = [(f"h{h}", f"ret_h{h}", f"spy_h{h}") for h in config.HORIZONS] + [("br", "ret_br", "spy_br")]
OUTCOME_LABEL = {**{f"h{h}": f"{h}일 보유" for h in config.HORIZONS},
                 "br": f"손절 {config.STOP:+.0%} / 목표 {config.TARGET:+.0%}"}


# ---------------------------------------------------------------- 신호
def conditions(df):
    return {
        "ret1": (df["ret1"] >= R["ret1_min"]) & (df["ret1"] <= R["ret1_max"]),
        "rvol": df["rvol"] >= R["rvol_min"],
        "close_pos": df["close_pos"] >= R["close_pos_min"],
        "sector": df["sector_ok"] == 1.0,
        "overheat": df["ret5"] < R["ret5_max"],
    }


def signal_mask(df, drop=None):
    conds = conditions(df)
    mask = pd.Series(True, index=df.index)
    for k, m in conds.items():
        if k == drop:
            continue
        mask &= m.fillna(False)
    return mask


def cluster(events):
    """같은 종목에서 CLUSTER_GAP 거래일 안에 이어지는 신호는 첫 날만 남긴다."""
    keep = []
    for _, g in events.sort_values(["symbol", "pos"]).groupby("symbol", sort=False):
        last = -10 ** 9
        for idx, p in zip(g.index, g["pos"]):
            if p - last > config.CLUSTER_GAP:
                keep.append(idx)
                last = p
    return events.loc[sorted(keep)]


def flag_earnings(events, earnings):
    """실적 발표일 ±EARNINGS_WINDOW 거래일(주말 포함 3일) 안이면 True."""
    if earnings is None or earnings.empty:
        return pd.Series(False, index=events.index)
    e = earnings.copy()
    e["day"] = pd.to_datetime(e["day"])
    near = pd.Series(False, index=events.index)
    by_sym = {s: g["day"].values.astype("datetime64[D]") for s, g in e.groupby("symbol")}
    tol = np.timedelta64(config.EARNINGS_WINDOW * 3, "D")
    for idx, sym, day in zip(events.index, events["symbol"], events["day"].values.astype("datetime64[D]")):
        arr = by_sym.get(sym)
        if arr is None or len(arr) == 0:
            continue
        near[idx] = bool((np.abs(arr - day) <= tol).any())
    return near


# ---------------------------------------------------------------- 통계
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (center - half, center + half)


def stats(ev, ret_col, spy_col):
    r = ev[ret_col].dropna()
    if r.empty:
        return None
    net = r - config.COST_ROUND_TRIP
    spy = ev.loc[r.index, spy_col]
    wins = int((net > 0).sum())
    lo, hi = wilson(wins, len(net))
    return {
        "n": int(len(net)),
        "win": wins / len(net),
        "win_lo": lo, "win_hi": hi,
        "mean": float(net.mean()),
        "median": float(net.median()),
        "excess": float((r - spy).mean()),
        "excess_win": float(((r - spy) > 0).mean()),
        "thin": len(net) < config.MIN_N,
    }


def placebo(ev, pool, ret_col, seed):
    """이벤트와 같은 종목·같은 수의 비신호 날을 복원 추출해 승률·평균 순수익 분포를 만든다.

    반환: 무작위 승률 · 무작위 평균 · 관측이 그 이상일 확률 p(단측: 신호가 더 낫다는 쪽).
    풀에 종목이 없거나 너무 적은 이벤트는 검정에서 뺀다.
    """
    r = ev[ret_col].dropna()
    if r.empty:
        return None
    rng = np.random.default_rng(abs(hash(seed)) % (2 ** 32))
    B = config.PLACEBO_RESAMPLES
    pool_r = pool[ret_col]
    groups = {s: (pool_r[g.index].dropna().values - config.COST_ROUND_TRIP)
              for s, g in pool.groupby("symbol") if s in set(ev.loc[r.index, "symbol"])}
    win_tot = np.zeros(B)
    ret_tot = np.zeros(B)
    used = 0
    obs_w, obs_m = [], []
    for sym, g in ev.loc[r.index].groupby("symbol"):
        arr = groups.get(sym)
        if arr is None or len(arr) < 50:
            continue
        k = len(g)
        samp = arr[rng.integers(0, len(arr), size=(B, k))]
        win_tot += (samp > 0).sum(axis=1)
        ret_tot += samp.sum(axis=1)
        used += k
        net = g[ret_col].values - config.COST_ROUND_TRIP
        obs_w.append((net > 0).sum())
        obs_m.append(net.sum())
    if used == 0:
        return None
    pw, pm = win_tot / used, ret_tot / used
    ow, om = sum(obs_w) / used, sum(obs_m) / used
    return {
        "n_used": used,
        "base_win": float(pw.mean()),
        "base_mean": float(pm.mean()),
        "p_win": float(((pw >= ow).sum() + 1) / (B + 1)),
        "p_mean": float(((pm >= om).sum() + 1) / (B + 1)),
    }


def cell(ev, pool, key, seed):
    _, ret_col, spy_col = next(o for o in OUTCOMES if o[0] == key)
    s = stats(ev, ret_col, spy_col)
    if s is None:
        return None
    s["outcome"] = key
    pb = placebo(ev, pool, ret_col, f"{seed}|{key}") if pool is not None else None
    s.update(pb or {"n_used": 0, "base_win": float("nan"), "base_mean": float("nan"),
                    "p_win": float("nan"), "p_mean": float("nan")})
    return s


def run(long, earnings):
    """모든 표를 계산해 dict 로 돌려준다. events 도 함께."""
    base_mask = signal_mask(long)
    events = cluster(long[base_mask])
    events = events.assign(near_earnings=flag_earnings(events, earnings))
    events = events.assign(period=np.where(events["day"] < config.SPLIT_DAY, "train", "test"))
    pool_all = long[~base_mask]
    pool_all = pool_all.assign(period=np.where(pool_all["day"] < config.SPLIT_DAY, "train", "test"))

    def table(ev, pool, seed):
        return [c for c in (cell(ev, pool, k, seed) for k, _, _ in OUTCOMES) if c]

    out = {"events": events, "n_days": int(long["day"].nunique()), "n_symbols": int(long["symbol"].nunique()),
           "day_min": long["day"].min(), "day_max": long["day"].max()}

    # 1. 기간별
    out["by_period"] = {
        "전체": table(events, pool_all, "all"),
        "탐색 (~2022)": table(events[events.period == "train"], pool_all[pool_all.period == "train"], "train"),
        "검증 (2023~)": table(events[events.period == "test"], pool_all[pool_all.period == "test"], "test"),
    }
    # 2. 국면
    out["by_regime"] = {
        "RISK ON": table(events[events.risk_on], pool_all[pool_all.risk_on], "on"),
        "RISK OFF": table(events[~events.risk_on], pool_all[~pool_all.risk_on], "off"),
    }
    # 3. 실적 인접
    out["by_earnings"] = {
        "실적 인접 아님": table(events[~events.near_earnings], pool_all, "noearn"),
        "실적 인접": table(events[events.near_earnings], pool_all, "earn"),
    }
    # 4. 절제 — 조건 하나씩 빼기 (전체 기간, 플라시보 풀은 각 변형의 비신호 날)
    abl = {}
    for name, drop in config.ABLATIONS.items():
        m = signal_mask(long, drop)
        ev = cluster(long[m])
        abl[name] = {"n": len(ev), "cells": table(ev, long[~m], f"abl|{drop}")}
    out["ablation"] = abl
    # 5. 손절·목표 청산 사유
    br = events.dropna(subset=["ret_br"])
    out["exit_reasons"] = (br.groupby("exit_reason")
                             .agg(n=("ret_br", "size"), mean=("ret_br", "mean"), days=("exit_d", "mean"))
                             .reset_index().to_dict("records"))
    # 6. 연도별 (5일 보유)
    yr = events.dropna(subset=["ret_h5"]).assign(year=lambda d: d["day"].dt.year)
    yr["net"] = yr["ret_h5"] - config.COST_ROUND_TRIP
    out["by_year"] = (yr.groupby("year")
                        .agg(n=("net", "size"), win=("net", lambda s: (s > 0).mean()), mean=("net", "mean"))
                        .reset_index().to_dict("records"))
    # 7. 섹터별 (5일 보유)
    sec = events.dropna(subset=["ret_h5"]).copy()
    sec["net"] = sec["ret_h5"] - config.COST_ROUND_TRIP
    out["by_sector"] = (sec.groupby("sector")
                          .agg(n=("net", "size"), win=("net", lambda s: (s > 0).mean()), mean=("net", "mean"))
                          .sort_values("n", ascending=False).reset_index().to_dict("records"))
    return out
