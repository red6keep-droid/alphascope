"""FRED 경제 지표 수집

실업률(UNRATE), CPI(CPIAUCSL), VIX(VIXCLS)와 금리 4종(DGS10, DGS2, T10Y2Y, DFF)
시계열의 최근 관측치를 가져온다. API 키는 FRED_API_KEY 환경 변수(.env)에서 읽는다.

금리 일간 시리즈는 전 영업일 값으로 내려오는 날이 많다. 당일 10년물은
analyze.py가 Yahoo ^TNX에서 따로 읽고, 여기 값은 2Y·스프레드·기준금리에 쓴다.
"""

import datetime
import os

import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "unemployment_rate": "UNRATE",
    "cpi": "CPIAUCSL",
    "vix": "VIXCLS",
    # 금리 — validate_report의 REQUIRED_MACRO에는 넣지 않는다. 결측이어도 리포트는 나간다.
    "us10y": "DGS10",
    "us2y": "DGS2",
    "spread_10_2": "T10Y2Y",
    "fed_funds": "DFF",
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

    found = []   # 최근 관측 둘 — 값 옆 직전 대비 증감에 쓴다 (2026-10-12 사용자: "증감 표시는 안 되는 거야?")
    for o in obs:
        value = str(o.get("value") or "").strip()
        date = str(o.get("date") or "").strip()
        if value and value != "." and date:
            try:
                found.append((round(float(value), 2), date))
            except (ValueError, TypeError):
                continue
        if len(found) == 2:
            break
    if not found:
        return None
    rec = {"value": found[0][0], "date": found[0][1]}
    if len(found) == 2:
        rec["prev"], rec["prev_date"] = found[1]
    return rec


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