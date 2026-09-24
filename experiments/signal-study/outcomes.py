"""모든 (종목, 거래일)에 대해 규칙 조건값과 매수 결과를 미리 계산한다.

신호가 뜬 날만이 아니라 모든 날을 계산하는 이유: 플라시보(같은 종목의 비신호 날) 비교가 같은 함수로 나와야 하고,
조건을 하나씩 빼 보는 절제 분석이 다시 계산 없이 마스크만 바꿔 가능하기 때문이다.

  진입   entry     = open(t+1)                          신호일 다음 거래일 시가
  고정   ret_h{h}  = close(t+h) / entry − 1             신호일 + h 거래일 종가 청산
  손절·목표 ret_br = exit / entry − 1                    t+1 부터 하루씩:
                        시가가 손절선 아래로 갭 → 시가 청산 (stop_gap)
                        시가가 목표선 위로 갭   → 시가 청산 (target_gap)
                        저가 ≤ 손절선           → 손절선 청산 (stop)
                        고가 ≥ 목표선           → 목표선 청산 (target)
                        같은 날 둘 다 닿으면 손절로 본다 (보수적)
                        MAX_HOLD 일까지 아무것도 없으면 종가 청산 (timeout)
  spy_*             같은 진입일 · 청산일에 SPY를 샀다면의 수익률
"""

import numpy as np
import pandas as pd

import config

R = config.RULE


def features(df, etf):
    """규칙 조건값. etf 가 None 이면 sector_ok 는 전부 NaN(평가 불가 → 조건 미충족)."""
    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"]
    f = pd.DataFrame(index=df.index)
    f["ret1"] = c / c.shift(1) - 1
    f["rvol"] = v / v.shift(1).rolling(R["rvol_lookback"]).mean()
    rng = h - l
    f["close_pos"] = np.where(rng > 0, (c - l) / rng, np.nan)
    f["ret5"] = c / c.shift(5) - 1
    if etf is not None:
        ec = etf["Close"]
        ok = ec > ec.rolling(R["sector_ma"]).mean()
        f["sector_ok"] = ok.reindex(f.index).astype("float")   # NaN 유지
    else:
        f["sector_ok"] = np.nan
    return f


def outcomes(df, spy):
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    entry = o.shift(-1)
    spy_o = spy["Open"].reindex(df.index)
    spy_c = spy["Close"].reindex(df.index)
    spy_entry = spy_o.shift(-1)

    out = pd.DataFrame(index=df.index)
    out["entry"] = entry
    for hz in config.HORIZONS:
        out[f"ret_h{hz}"] = c.shift(-hz) / entry - 1
        out[f"spy_h{hz}"] = spy_c.shift(-hz) / spy_entry - 1

    stop_px = entry * (1 + config.STOP)
    tgt_px = entry * (1 + config.TARGET)
    n = len(df)
    exit_px = np.full(n, np.nan)
    exit_d = np.full(n, np.nan)
    reason = np.full(n, None, dtype=object)
    resolved = np.zeros(n, dtype=bool)
    ent = entry.values

    for d in range(1, config.MAX_HOLD + 1):
        od, hd, ld, cd = (s.shift(-d).values for s in (o, h, l, c))
        valid = ~np.isnan(cd) & ~np.isnan(ent)
        new = valid & ~resolved
        if d == 1:
            gap_stop = np.zeros(n, dtype=bool)       # 진입일 시가 = 진입가
            gap_tgt = np.zeros(n, dtype=bool)
        else:
            gap_stop = od <= stop_px.values
            gap_tgt = od >= tgt_px.values
        hit_stop = ld <= stop_px.values
        hit_tgt = hd >= tgt_px.values

        for mask, px, why in (
            (new & gap_stop, od, "stop_gap"),
            (new & ~gap_stop & gap_tgt, od, "target_gap"),
            (new & ~gap_stop & ~gap_tgt & hit_stop, stop_px.values, "stop"),
            (new & ~gap_stop & ~gap_tgt & ~hit_stop & hit_tgt, tgt_px.values, "target"),
        ):
            exit_px[mask] = px[mask]
            exit_d[mask] = d
            reason[mask] = why
            resolved |= mask
        if d == config.MAX_HOLD:
            mask = new & ~resolved
            exit_px[mask] = cd[mask]
            exit_d[mask] = d
            reason[mask] = "timeout"
            resolved |= mask

    out["ret_br"] = exit_px / ent - 1
    out["exit_d"] = exit_d
    out["exit_reason"] = reason

    # SPY: 청산 날짜(offset)에 맞춘 종가
    spy_mat = np.column_stack([spy_c.shift(-d).values for d in range(1, config.MAX_HOLD + 1)])
    idx = np.where(np.isnan(exit_d), 0, exit_d - 1).astype(int)
    spy_exit = spy_mat[np.arange(n), idx]
    spy_br = spy_exit / spy_entry.values - 1
    spy_br[np.isnan(exit_d)] = np.nan
    out["spy_br"] = spy_br
    return out


def regime(spy, vix):
    """RISK ON = VIX 종가 < 20 이고 SPY 종가 > 20일선 (Tech Master Spec 3.1). 날짜 인덱스의 bool Series."""
    sc = spy["Close"]
    on = (sc > sc.rolling(config.REGIME_SPY_MA).mean()) & (vix["Close"].reindex(sc.index) < config.REGIME_VIX_MAX)
    return on.rename("risk_on")


def build(universe, bars):
    """긴 형식 DataFrame — 한 행 = (종목, 거래일). STUDY_START 이후만."""
    spy = bars[config.BENCHMARK]
    frames = []
    for row in universe.itertuples(index=False):
        df = bars.get(row.symbol)
        if df is None:
            continue
        etf = bars.get(row.etf) if isinstance(row.etf, str) else None
        f = features(df, etf)
        o = outcomes(df, spy)
        x = pd.concat([f, o], axis=1)
        x["symbol"] = row.symbol
        x["sector"] = row.sector
        x["pos"] = np.arange(len(x))                 # 종목 안 거래일 순번 — 군집 판정용
        x = x[x.index >= config.STUDY_START]
        frames.append(x)
    long = pd.concat(frames).rename_axis("day").reset_index()
    rg = regime(spy, bars[config.VIX])
    long = long.merge(rg.rename_axis("day").reset_index(), on="day", how="left")
    long["risk_on"] = long["risk_on"].fillna(False).astype(bool)
    return long
