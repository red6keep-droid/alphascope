"""FRED 경제 지표 수집

실업률(UNRATE), CPI(CPIAUCSL), VIX(VIXCLS) 시계열의 최근 관측치를 가져온다.
API 키는 FRED_API_KEY 환경 변수(.env)에서 읽는다.
"""

import datetime
import os

import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "unemployment_rate": "UNRATE",
    "cpi": "CPIAUCSL",
    "vix": "VIXCLS",
}

TIMEOUT = 30


def _last_value(session, api_key, series_id):
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 8,
    }
    resp = session.get(FRED_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])

    for o in obs:
        value = str(o.get("value") or "").strip()
        date = str(o.get("date") or "").strip()
        if value and value != "." and date:
            try:
                return {"value": round(float(value), 2), "date": date}
            except (ValueError, TypeError):
                continue
    return None


def collect_fred(api_key=None):
    api_key = api_key or os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY 환경 변수(또는 .env)가 필요합니다.")

    session = requests.Session()
    session.headers.update({"User-Agent": "alpha-scope/daily-report (test)"})

    result = {}
    for name, series_id in SERIES.items():
        try:
            result[name] = _last_value(session, api_key, series_id)
        except requests.RequestException as e:
            print(f"FRED {series_id} 수집 실패: {e}")
            result[name] = None

    print(f"FRED 수집 완료: {result}")
    return result


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(collect_fred())