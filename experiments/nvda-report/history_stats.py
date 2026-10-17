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
             "generated_at": datetime.date.today().isoformat(),
             "note": "각 조건 '진입일'(연속 구간 첫날)의 20·60거래일 뒤 수익률. base = 아무 날. 과거 빈도이지 예측이 아니다."}
    with open(config.HISTORY_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
