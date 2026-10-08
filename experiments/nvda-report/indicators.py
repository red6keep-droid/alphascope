"""숫자는 전부 여기서 파이썬이 만든다 — 기술 지표(7절)와 옵션 수식(Black-Scholes 감마).

scipy 없이 math만 쓴다. 입력은 일봉 리스트(dict: day·open·high·low·close·volume, 날짜 오름차순).
"""

import math

import config


# ── 기술 지표 ──────────────────────────────────────────────────────────────

def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes, period=config.RSI_PERIOD):
    """Wilder 방식. 최소 period+1개 종가."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def technical_rows(bars_by_symbol):
    """심볼별 일봉 → NVDA 거래일마다 가격·거래량·기술 칸 dict. 전 기간을 돌려주므로 백필에도 쓴다."""
    nv = bars_by_symbol.get(config.SYMBOL, [])
    others = {s: {b["day"]: b for b in bars_by_symbol.get(s, [])} for s in config.SYMBOLS if s != config.SYMBOL}
    out = []
    closes, highs, vols = [], [], []
    prev = None
    prev_ma50 = prev_ma200 = None
    for b in nv:
        closes.append(b["close"]); highs.append(b["high"]); vols.append(b["volume"] or 0.0)
        row = {"day": b["day"], "close": b["close"], "volume": b["volume"]}
        if prev:
            row["ret_1d"] = (b["close"] / prev["close"] - 1) * 100
            row["gap"] = (b["open"] / prev["close"] - 1) * 100 if b["open"] else None
            for s in ("SPY", "SMH", "AMD", "QQQ"):
                o, op = others[s].get(b["day"]), others[s].get(prev["day"])
                row[f"ret_vs_{s.lower()}"] = (row["ret_1d"] - (o["close"] / op["close"] - 1) * 100) if o and op else None
        row["range_pct"] = (b["high"] - b["low"]) / b["close"] * 100 if b["close"] else None
        look = config.VOL_LOOKBACK_DAYS
        if len(vols) > look and vols[-1]:
            base = sum(vols[-look - 1:-1]) / look
            row["vol_ratio_20d"] = vols[-1] / base if base else None
        ma50, ma200 = sma(closes, config.MA_SHORT), sma(closes, config.MA_LONG)
        row["ma50"], row["ma200"] = ma50, ma200
        if len(highs) >= 2:
            hi = max(highs[-config.HIGH_52W_DAYS:])
            row["pct_from_52w_high"] = (b["close"] / hi - 1) * 100 if hi else None
        row["rsi14"] = rsi(closes[-(config.RSI_PERIOD * 10):])
        cross = None
        if ma50 and ma200 and prev_ma50 and prev_ma200:
            if prev_ma50 <= prev_ma200 and ma50 > ma200:
                cross = "golden"
            elif prev_ma50 >= prev_ma200 and ma50 < ma200:
                cross = "death"
        row["ma_cross"] = cross
        prev_ma50, prev_ma200 = ma50, ma200
        prev = b
        out.append(row)
    return out


# ── 옵션 수식 ──────────────────────────────────────────────────────────────

def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_gamma(spot, strike, t_years, iv, r=config.RISK_FREE_RATE):
    """Black-Scholes 감마 (콜·풋 동일). 입력이 깨지면 None."""
    if not (spot and strike and t_years and iv) or t_years <= 0 or iv <= 0 or iv > 3:
        return None
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    return _norm_pdf(d1) / (spot * iv * math.sqrt(t_years))


def gex_approx(rows, spot, as_of_day):
    """Σ(call_oi·γ) − Σ(put_oi·γ) × 100 × spot² × 0.01 — 1% 움직임당 딜러 헤지 금액 근사 (달러).

    딜러가 콜 매도·풋 매도라는 가정이 조잡하므로 크기는 쓰지 않고 부호와 0 근처 행사가만 본다 (기획서 7절).
    rows: option_snapshots 행(dict). 반환 (gex_total, flip_strike).
    """
    import datetime
    d0 = datetime.date.fromisoformat(as_of_day)
    per_strike = {}
    for r in rows:
        try:
            dte = (datetime.date.fromisoformat(r["expiry"]) - d0).days
        except ValueError:
            continue
        t = max(dte, 0.5) / 365.0
        g_c = bs_gamma(spot, r["strike"], t, r.get("call_iv"))
        g_p = bs_gamma(spot, r["strike"], t, r.get("put_iv"))
        v = 0.0
        if g_c and r.get("call_oi"):
            v += r["call_oi"] * g_c
        if g_p and r.get("put_oi"):
            v -= r["put_oi"] * g_p
        per_strike[r["strike"]] = per_strike.get(r["strike"], 0.0) + v
    if not per_strike:
        return None, None
    scale = 100 * spot * spot * 0.01
    total = sum(per_strike.values()) * scale
    # 누적 감마가 부호를 바꾸는 행사가 중 현재가에 가장 가까운 것
    strikes = sorted(per_strike)
    cum, flip = 0.0, None
    prev_sign = None
    for k in strikes:
        cum += per_strike[k]
        sign = 1 if cum > 0 else (-1 if cum < 0 else 0)
        if prev_sign is not None and sign and prev_sign and sign != prev_sign:
            if flip is None or abs(k - spot) < abs(flip - spot):
                flip = k
        if sign:
            prev_sign = sign
    return total, flip


def atm_iv_interpolated(expiry_iv, as_of_day, target_days=config.OPTION_IV_TARGET_DAYS):
    """{expiry: atm_iv} → target_days 기준 IV. 분산(iv²·T)을 선형 보간한다.

    목표 일수를 감싸는 만기 둘이 있으면 보간, 한쪽만 있으면 가장 가까운 만기 값을 그대로 쓴다.
    """
    import datetime
    d0 = datetime.date.fromisoformat(as_of_day)
    pts = []
    for e, iv in expiry_iv.items():
        if iv is None or iv <= 0:
            continue
        dte = (datetime.date.fromisoformat(e) - d0).days
        if dte >= 1:
            pts.append((dte, iv))
    if not pts:
        return None
    pts.sort()
    below = [p for p in pts if p[0] <= target_days]
    above = [p for p in pts if p[0] >= target_days]
    if below and above:
        (t1, v1), (t2, v2) = below[-1], above[0]
        if t1 == t2:
            return v1
        var1, var2 = v1 * v1 * t1, v2 * v2 * t2
        var = var1 + (var2 - var1) * (target_days - t1) / (t2 - t1)
        return math.sqrt(var / target_days)
    nearest = min(pts, key=lambda p: abs(p[0] - target_days))
    return nearest[1]
