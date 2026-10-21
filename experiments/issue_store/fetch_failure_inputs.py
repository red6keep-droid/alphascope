"""실패 비용 검증 재료 — doc/리포트-재설계/실패-비용-검증-계획.md F1 · F3 · F6.

- S&P 500 역대 구성 (GitHub fja05680/sp500, 날짜별 구성 목록) → data/store/calendar/sp500_components.csv
- 미 국채 3개월 FRED DTB3 (일별, 연 %) → data/store/bars/DTB3.parquet
- 한국 3개월 금리 FRED IR3TIB01KRM156N (월별, 연 %) → data/store/bars/KR3M.parquet

실행: .venv/bin/python experiments/issue_store/fetch_failure_inputs.py
"""
import io
import os

import pandas as pd
import requests
from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BARS = os.path.join(ROOT, "data", "store", "bars")
CAL = os.path.join(ROOT, "data", "store", "calendar")
SP500 = "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"


def fred(series, key):
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": series, "api_key": key, "file_type": "json"}, timeout=60)
    r.raise_for_status()
    obs = pd.DataFrame(r.json()["observations"])
    obs = obs[obs["value"] != "."]
    return pd.Series(obs["value"].astype(float).values, index=pd.to_datetime(obs["date"]), name="close")


def main():
    r = requests.get(SP500, timeout=120)
    r.raise_for_status()
    comp = pd.read_csv(io.StringIO(r.text))
    assert list(comp.columns[:2]) == ["date", "tickers"], comp.columns
    comp.to_csv(os.path.join(CAL, "sp500_components.csv"), index=False)
    print(f"구성: {len(comp)}개 날짜, {comp.date.min()} ~ {comp.date.max()}")

    key = dotenv_values(os.path.join(ROOT, ".env")).get("FRED_API_KEY") or os.environ.get("FRED_API_KEY")
    for series, name in [("DTB3", "DTB3"), ("IR3TIB01KRM156N", "KR3M")]:
        s = fred(series, key)
        s.to_frame().to_parquet(os.path.join(BARS, name + ".parquet"))
        print(f"{name}: {len(s)}개, {s.index[0].date()} ~ {s.index[-1].date()}")


if __name__ == "__main__":
    main()
