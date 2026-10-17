"""조건부 통계 (상장 이후 전체 — 엔비디아는 1999년~, 2026-10-17 10년 → 30년) → static/history_stats.json (1년에 한 번 손으로 갱신: python history_stats.py).

자료: 이 저장소의 30년 저장소 data/store/bars/<종목>.parquet 가 있으면 그것(수정주가), 없으면 yfinance 전체 기간. 두 곳 모두 yfinance auto_adjust 라 같다.

볼린저(20, 2σ) 하단 이하·상단 이상 '진입일'(연속 구간 첫날)의 20·60거래일 뒤 수익률과, 비교용 '아무 날' 값.
과거 빈도이지 예측이 아니다 — 리포트는 n·아무 날 비율과 함께만 보여 준다 (2026-10-11 사용자: 이익 실현 구간을 찾을 수 있나 → 처음엔 10년 통계로 답했고, 2026-10-17 30년 저장소가 생겨 전체 기간으로 바꿈: 같은 정의로 10년 73% vs 66% 이던 하단 뒤 20일 상승 비율이 30년으로는 60% vs 59%).
"""

import datetime
import json
import os

import pandas as pd
import yfinance as yf

import config


PEERS = ["NVDA", "AMD", "QCOM", "AVGO", "AMAT", "LRCX", "KLAC", "MU", "INTC", "TXN", "AAPL", "MSFT", "AMZN", "GOOGL", "CSCO"]   # 15종목 (검증과 같은 목록)
DD_LEVELS = (10, 20, 30)


def drawdown_cycles(c):
    """종가가 직전 최고 종가에서 몇 % 내려갔다가 그 고점을 다시 넘을 때까지 — 사이클마다 (깊이 %, 고점 날짜부터 센 거래일, 회복 여부)."""
    v = c.values
    peak, peak_i, trough = v[0], 0, 0.0
    out = []
    for i in range(1, len(v)):
        if v[i] >= peak:
            if trough < 0:
                out.append((trough * 100, i - peak_i, True))
            peak, peak_i, trough = v[i], i, 0.0
        else:
            trough = min(trough, v[i] / peak - 1)
    if trough < 0:
        out.append((trough * 100, len(v) - 1 - peak_i, False))   # 아직 회복 못 한 지금 사이클
    return out


def dd_summary(cycles):
    """수준별 요약: 깊이가 그 수준을 넘은 사이클 수 · 회복한 것의 중앙값 · 1년(250거래일) 넘게 걸린 수 · 가장 오래 걸린 값."""
    res = {}
    for lv in DD_LEVELS:
        hit = [(d, n, ok) for d, n, ok in cycles if d <= -lv]
        rec = sorted(n for d, n, ok in hit if ok)
        res[str(lv)] = {"n": len(hit), "recovered": len(rec), "median_days": int(rec[len(rec) // 2]) if rec else None,
                        "over_year": sum(1 for n in rec if n > 250), "longest_days": max(rec) if rec else None}
    return res


def drawdown_stats():
    store = os.path.abspath(os.path.join(config.BASE_DIR, "..", "..", "data", "store", "bars"))
    per, pooled = {}, []
    for sym in PEERS:
        f = os.path.join(store, f"{sym}.parquet")
        if not os.path.exists(f):
            continue
        c = pd.read_parquet(f)["close"]
        c.index = pd.to_datetime(c.index)
        c = c[c > 0].dropna()
        cy = drawdown_cycles(c)
        per[sym] = dd_summary(cy)
        pooled += cy
    if "NVDA" not in per:
        return None
    return {"nvda": per["NVDA"], "peers": dd_summary(pooled), "peers_n": len(per),
            "peers_span": "1999~" , "note": "고점 날짜부터 그 고점을 다시 넘을 때까지 거래일. 사이클마다 깊이가 수준(10 · 20 · 30%)을 넘은 것만 센다."}


def main():
    store = os.path.abspath(os.path.join(config.BASE_DIR, "..", "..", "data", "store", "bars", f"{config.SYMBOL}.parquet"))
    if os.path.exists(store):
        c = pd.read_parquet(store)["close"]
        c.index = pd.to_datetime(c.index)
    else:
        df = yf.download(config.SYMBOL, period="max", interval="1d", auto_adjust=True, progress=False)
        c = df["Close"].squeeze()
    c = c[c > 0].dropna()
    ma = c.rolling(config.BOLL_WINDOW).mean()
    sd = c.rolling(config.BOLL_WINDOW).std()
    lower, upper = ma - config.BOLL_SIGMA * sd, ma + config.BOLL_SIGMA * sd
    pctb = (c - lower) / (upper - lower)
    fwd = {n: c.shift(-n) / c - 1 for n in (20, 60)}
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    dist200 = c / c.rolling(200).mean() - 1
    ret20 = c / c.shift(20) - 1

    def stat(mask):
        m = mask.fillna(False)
        m = m & ~m.shift(1, fill_value=False)
        out = {"n": int(m.sum())}
        for n in (20, 60):
            f = fwd[n][m].dropna()
            out[f"up{n}"] = round(float((f > 0).mean() * 100))
            out[f"med{n}"] = round(float(f.median() * 100), 1)
        return out

    base = {f"up{n}": round(float((fwd[n].dropna() > 0).mean() * 100)) for n in (20, 60)}
    base.update({f"med{n}": round(float(fwd[n].dropna().median() * 100), 1) for n in (20, 60)})
    stats = {"symbol": config.SYMBOL, "window": "all", "from": str(c.index[0].date()), "to": str(c.index[-1].date()), "days": int(len(c)),
             "base": base, "boll_lower": stat(pctb <= 0), "boll_upper": stat(pctb >= 1),
             "rsi80": stat(rsi >= config.OVERHEAT_RSI), "ma200_40": stat(dist200 >= config.OVERHEAT_MA200_PCT / 100),
             "ret20_25": stat(ret20 >= config.OVERHEAT_RET20_PCT / 100), "rsi30": stat(rsi <= 30),
             "drawdown": drawdown_stats(),
             "generated_at": datetime.date.today().isoformat(),
             "note": "각 조건 '진입일'(연속 구간 첫날)의 20·60거래일 뒤 수익률. base = 아무 날. 과거 빈도이지 예측이 아니다."}
    with open(config.HISTORY_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
