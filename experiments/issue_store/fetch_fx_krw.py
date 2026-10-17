"""원/달러 일별 환율 — FRED DEXKOUS (뉴욕 정오 매입 기준, 1981 ~).

평소 범위 검증 계획 C7 (doc/평소-범위-검증-계획.md): 원화 수익률 = 달러 수익률 + 환율 변화율.
주가 종가(16:00 ET)와 몇 시간 차이 — 일별로는 작아 받아들이고 보고서에 밝힌다.

출력: data/store/bars/DEXKOUS.parquet (index = 날짜, close = 원/달러, 빈 날 제외)
실행: .venv/bin/python experiments/issue_store/fetch_fx_krw.py
"""
import os

import pandas as pd
import requests
from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "store", "bars", "DEXKOUS.parquet")


def main():
    key = dotenv_values(os.path.join(ROOT, ".env")).get("FRED_API_KEY") or os.environ.get("FRED_API_KEY")
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": "DEXKOUS", "api_key": key, "file_type": "json"}, timeout=60)
    r.raise_for_status()
    obs = pd.DataFrame(r.json()["observations"])
    obs = obs[obs["value"] != "."]
    s = pd.Series(obs["value"].astype(float).values, index=pd.to_datetime(obs["date"]), name="close")
    s.to_frame().to_parquet(OUT)
    print(f"저장: {OUT} ({len(s)}일, {s.index[0].date()} ~ {s.index[-1].date()})")


if __name__ == "__main__":
    main()
