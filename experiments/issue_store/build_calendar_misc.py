"""실적 · 시장 구조 날짜표 (이슈 저장소 3절 3 · 7).

    python experiments/issue_store/build_calendar_misc.py

- earnings.csv: 9월 백테스트 backtest/data/earnings.csv (yfinance, 2002~, 예상 · 실제 EPS) 중 추적 종목. 엔비디아는 장 마감 뒤 발표 → 반응은 다음 날
  attrs: surprise_pct, 서프라이즈 구간(예상 상회 +5% 이상 · 상회 · 부합 ±1% · 하회)
- market_structure.csv: 월간 옵션 만기(셋째 금요일, 휴장이면 전날) · 네 마녀의 날(3 · 6 · 9 · 12월) · 분기 말 · 연말 — 규칙으로 생성
"""

import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "calendar")
TRACK = ["NVDA"]   # 종목을 늘리면 여기에


def earnings():
    e = pd.read_csv(os.path.join(ROOT, "backtest", "data", "earnings.csv"))
    e = e[e.symbol.isin(TRACK)].copy()

    def band(p):
        if pd.isna(p):
            return None
        return "크게 상회" if p >= 5 else "상회" if p >= 1 else "부합" if p > -1 else "하회"
    e["surprise_band"] = e["surprise_pct"].map(band)
    e["kind"], e["subkind"], e["time_et"] = "실적", "자기 실적", "16:20"
    e.to_csv(os.path.join(OUT, "earnings.csv"), index=False)
    print(f"실적 {len(e)}건 ({e.day.min()} ~ {e.day.max()})")
    print(e["surprise_band"].value_counts(dropna=False).to_string())


def market_structure(trading_days):
    td = pd.DatetimeIndex(sorted(trading_days))
    rows = []
    for per in pd.period_range(td.min(), td.max(), freq="M"):
        fridays = pd.date_range(per.start_time, per.end_time, freq="W-FRI")
        if len(fridays) < 3:
            continue
        d = fridays[2]
        while d not in td and d > per.start_time:   # 휴장이면 전 거래일 (2008 성금요일 등)
            d -= pd.Timedelta(days=1)
        quad = per.month in (3, 6, 9, 12)
        rows.append({"day": d.date(), "kind": "시장 구조", "subkind": "네 마녀의 날" if quad else "월간 옵션 만기", "time_et": "16:00"})
        last = td[(td >= per.start_time) & (td <= per.end_time)]
        if len(last) and per.month in (3, 6, 9, 12):
            rows.append({"day": last[-1].date(), "kind": "시장 구조", "subkind": "연말" if per.month == 12 else "분기 말", "time_et": "16:00"})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "market_structure.csv"), index=False)
    print(f"시장 구조 {len(df)}건 · " + " · ".join(f"{k} {v}" for k, v in df["subkind"].value_counts().items()))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    earnings()
    spy = pd.read_parquet(os.path.join(ROOT, "data", "store", "bars", "SPY.parquet"))
    market_structure(spy.index)
