"""섹터 · 한국 지수가 크게 움직인 날 찾기 — 사건표(scope 섹터 · 종목 13건)를 채울 후보 (데이터-기록-계획 A3-3-2 의 7, 2026-11-06 사용자 "받아와").

    .venv/bin/python experiments/issue_store/detect_sector_shocks.py

기준 = detect_shocks.py 와 같다(평소의 3배 + 절대 크기), 다만 **시장 대비 초과 움직임**으로 센다: 업종 ETF 하루 수익 − 시장 하루 수익.
시장이 같이 움직인 날(시장 사건)은 사건표 시장 135건이 맡으므로 뺀다. 연속된 날은 한 묶음.
결과 = results/sector_shocks_candidates.csv (날짜 · 계열 · 초과 수익 · 배수 · 묶음 · 사건표에 이미 있는지). 원인(기사)은 사람이 채운다 — 어휘는 event_vocab.py 21개.
"""
import os

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "store", "bars")
OUT = os.path.join(_HERE, "results", "sector_shocks_candidates.csv")
Z_MIN, LOOKBACK = 3.0, 60
# 계열: (이름, 시장 기준, 절대 기준 %p)
SERIES = {"_SOX": ("반도체 지수", "_GSPC", 3.0), "SMH": ("반도체 ETF", "_GSPC", 3.0), "XLE": ("에너지", "_GSPC", 2.5), "XLF": ("금융", "_GSPC", 2.5),
          "XLK": ("기술", "_GSPC", 2.0), "XLV": ("헬스케어", "_GSPC", 2.0), "XLU": ("유틸리티", "_GSPC", 2.0),
          "_KS11": ("코스피 (시장 자체)", None, 3.0), "_KQ11": ("코스닥 (vs 코스피)", "_KS11", 3.0),
          "091160.KS": ("KODEX 반도체 (vs 코스피)", "_KS11", 3.0), "091170.KS": ("KODEX 은행 (vs 코스피)", "_KS11", 2.5),
          "091180.KS": ("KODEX 자동차 (vs 코스피)", "_KS11", 2.5), "117460.KS": ("KODEX 에너지화학 (vs 코스피)", "_KS11", 2.5)}


def close(sym):
    c = pd.read_parquet(os.path.join(STORE, sym + ".parquet"))["close"].dropna()
    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
    return c[~c.index.duplicated()]


def main():
    ev = pd.read_csv(os.path.join(_HERE, "events_curated.csv"))
    ev["start"] = pd.to_datetime(ev["start"])
    rows = []
    for sym, (name, mkt, absmin) in SERIES.items():
        c = close(sym)
        r = c.pct_change() * 100
        if mkt:
            m = close(mkt).pct_change().reindex(r.index) * 100
            r = (r - m).dropna()
        sd = r.rolling(LOOKBACK).std().shift(1)
        z = r / sd
        hit = r.index[(z.abs() >= Z_MIN) & (r.abs() >= absmin)]
        ep, last = 0, None
        for d in hit:
            if last is None or (d - last).days > 3:
                ep += 1
            last = d
            near = ev[(ev["start"] <= d) & (d <= ev["start"] + pd.to_timedelta(ev["window_days"].fillna(1), unit="D"))]
            rows.append({"day": d.date(), "series": name, "sym": sym, "excess_pct": round(float(r[d]), 2), "z": round(float(z[d]), 1),
                         "episode": f"{sym}-{ep}", "in_event_table": "; ".join(near["title"].astype(str).str[:30]) if len(near) else ""})
    df = pd.DataFrame(rows).sort_values(["sym", "day"])
    df.to_csv(OUT, index=False)
    print(f"후보 {len(df)}일 · 묶음 {df['episode'].nunique()} · 사건표에 이미 있는 날 {(df['in_event_table'] != '').sum()}")
    print(df.groupby("series").agg(days=("day", "count"), episodes=("episode", "nunique"), known=("in_event_table", lambda x: (x != "").sum())).to_string())
    print("\n최근 2년 후보:")
    print(df[df["day"] >= pd.Timestamp("2024-11-01").date()].to_string(index=False))


if __name__ == "__main__":
    main()
