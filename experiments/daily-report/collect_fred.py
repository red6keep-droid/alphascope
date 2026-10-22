"""FRED 경제 지표 수집

실업률(UNRATE), CPI(CPIAUCSL), VIX(VIXCLS)와 금리 4종(DGS10, DGS2, T10Y2Y, DFF)
시계열의 최근 관측치를 가져온다. API 키는 FRED_API_KEY 환경 변수(.env)에서 읽는다.

금리 일간 시리즈는 전 영업일 값으로 내려오는 날이 많다. 당일 10년물은
analyze.py가 Yahoo ^TNX에서 따로 읽고, 여기 값은 2Y·스프레드·기준금리에 쓴다.
"""

import datetime
import json
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

# FRED 가 막힌 날(2026-10-22 점검 페이지가 JSON 대신 내려와 게시가 멈췄다)을 위한 예비.
# 받은 값은 키마다 여기에 남기고(report-state 브랜치로 보존), 못 받은 키는 여기서 채운다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, "output", "state")
LAST_PATH = os.path.join(STATE_DIR, "macro_last.json")
# 첫 실행엔 macro_last.json 이 아직 없다 — 전날 글의 입력에서 꺼낸다
PREV_INPUT_PATH = os.path.join(STATE_DIR, "last", "report_input.json")


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


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _vix_from_yahoo(history, indices):
    """^VIX 일봉 마지막 두 종가 → FRED VIXCLS 와 같은 모양. 시계열이 없으면 당일 시세로."""
    s = ((history or {}).get("series") or {}).get("^VIX") or {}
    dates, close = s.get("dates") or [], s.get("close") or []
    if dates and close:
        rec = {"value": round(close[-1], 2), "date": dates[-1], "source": "Yahoo"}
        if len(close) >= 2:
            rec["prev"], rec["prev_date"] = round(close[-2], 2), dates[-2]
        return rec
    q = (indices or {}).get("vix") or {}
    if q.get("price") is None:
        return None
    rec = {"value": round(q["price"], 2), "date": (history or {}).get("as_of") or "", "source": "Yahoo"}
    if q.get("change_pct") is not None:
        rec["prev"] = round(q["price"] / (1 + q["change_pct"] / 100), 2)
    return rec


def apply_fallbacks(macro, history=None, indices=None):
    """FRED 에서 못 받은 키를 채운다. 채운 값엔 source 를 달아 둔다 (validate_report 가 경고로 알린다).

    - VIX: Yahoo ^VIX
    - 그 밖(실업률 · CPI · 금리): 마지막으로 받은 값 그대로 — 기준일(date)이 함께 있어 글에 그 날짜로 나간다.
    받은 값은 macro_last.json 에 갱신한다.
    """
    last = _load_json(LAST_PATH) or (_load_json(PREV_INPUT_PATH).get("macro") or {})
    for name in SERIES:
        if macro.get(name):
            continue
        rec = _vix_from_yahoo(history, indices) if name == "vix" else None
        if rec is None and (last.get(name) or {}).get("value") is not None:
            rec = {**{k: v for k, v in last[name].items() if k != "source"}, "source": "저장값"}
        if rec:
            macro[name] = rec
            print(f"::warning::FRED {SERIES[name]} 대신 {rec['source']} 값 사용 (기준일 {rec.get('date')})")

    fresh = {k: v for k, v in macro.items() if v and not v.get("source")}
    if fresh:
        merged = {**{k: v for k, v in last.items() if v and not v.get("source")}, **fresh}
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LAST_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    return macro


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(collect_fred())