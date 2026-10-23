"""연준 나우캐스트 스냅샷 — "발표 전 예상" 을 날마다 기록한다 (2026-10-22 사용자: "진행해").

왜: 경제 지표의 시장 컨센서스(예상치)는 무료 · 자동 수집이 허용되는 소스가 없다(운영지침 D4-14 — Investing.com · ForexFactory 는
재배포 금지, Trading Economics · Econoday 는 유료). 대신 연준이 공개하는 나우캐스트를 쓴다 — 공공 자료, 재배포 제한 없음.
  - 클리블랜드 연준 Inflation Nowcasting: 이달 · 다음 달 CPI · 근원 CPI · PCE · 근원 PCE 전월 대비(%) 추정, 매 영업일 10:00 ET 갱신.
    페이지의 차트 JSON(nowcast_month.json)을 그대로 읽는다 — 월별 차트 하나에 그날까지의 추정 추이와 발표 뒤 실제값(Actual …)이 같이 있다.
    인용: "Inflation Nowcasting." Federal Reserve Bank of Cleveland. https://doi.org/10.26509/frbc-inflationnowcast
  - 애틀랜타 연준 GDPNow: 이번 분기 GDP 성장률 추정(연율 %). FRED 시리즈 GDPNOW — 이미 쓰는 FRED 키 하나로 받는다.

어디에: report-state 의 records/snapshots/YYYY.jsonl (record_store, 하루 1줄 id="nowcast"). 두 기관 모두 지난 추정을 스스로 보관하므로
(클리블랜드 = 월별 차트 전체, GDPNow = FRED/ALFRED 빈티지) 이 기록은 "그날 우리가 알 수 있던 예상" 을 한 줄로 꺼내 쓰기 위한 것이다 —
목적 문서 6절 8번(발표 일정 + 예상 vs 실제)의 재료. 리포트 본문에는 아직 쓰지 않는다.

실패해도 예외를 내지 않는다 — 기록은 게시를 막지 않는다 (운영지침 D6-2). 하루 1회 · 소스별 1회 호출.
"""

import os
import re

import requests

CLEVELAND_MONTH_URL = "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en"
CLEVELAND_PAGE = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
FRED_URL = "https://api.stlouisfed.org/fred"
TIMEOUT = 60
# 월별 차트의 series 이름 → 우리 칸 이름. "Actual …" 은 발표 뒤 실제값.
SERIES = {
    "CPI Inflation": "cpi_mm",
    "Core CPI Inflation": "core_cpi_mm",
    "PCE Inflation": "pce_mm",
    "Core PCE Inflation": "core_pce_mm",
}
MONTHS_KEEP = 3   # 최근 3개 달 — 발표 전 달 · 발표된 달(실제값 포함) · 그 전 달


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": "alpha-scope/daily-report (nowcast snapshot)"})
    return s


def _num(v, digits=3):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, digits)


def _month_period(subcaption):
    """차트 subcaption '2026-10' → '2026-10' (한 자리 달도 두 자리로)."""
    m = re.match(r"^\s*(\d{4})-(\d{1,2})\s*$", str(subcaption or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}" if m else None


def _last_point(categories, points):
    """series 의 마지막 비어 있지 않은 점 → (값, 라벨 날짜 'MM/DD')."""
    for i in range(min(len(categories), len(points)) - 1, -1, -1):
        v = _num((points[i] or {}).get("value"))
        if v is not None:
            return v, str(categories[i] or "")
    return None, None


def _parse_cleveland(charts):
    """월별 차트 목록 → 최근 MONTHS_KEEP 달의 {period, as_of, 추정 4개, 실제값 4개}."""
    out = []
    for ch in charts[-MONTHS_KEEP:]:
        period = _month_period((ch.get("chart") or {}).get("subcaption"))
        if not period:
            continue
        cats = [c.get("label") for c in ((ch.get("categories") or [{}])[0].get("category") or [])]
        row = {"period": period, "as_of": None}
        for s in ch.get("dataset") or []:
            name = str(s.get("seriesname") or "")
            key = SERIES.get(name.replace("Actual ", "", 1))
            if not key:
                continue
            v, label = _last_point(cats, s.get("data") or [])
            if name.startswith("Actual "):
                if v is not None:
                    row["actual_" + key] = v
                    row["actual_" + key + "_date"] = label
            else:
                row[key] = v
                # 추정의 기준일 = 네 series 중 가장 늦은 점 (발표된 지표는 발표일에 멈춘다)
                if label and (row["as_of"] is None or label > row["as_of"]):
                    row["as_of"] = label
        out.append(row)
    return out


def collect_cleveland(session=None):
    session = session or _session()
    r = session.get(CLEVELAND_MONTH_URL, timeout=TIMEOUT)
    r.raise_for_status()
    charts = r.json()
    if not isinstance(charts, list) or not charts:
        raise ValueError("클리블랜드 나우캐스트 JSON 모양이 다름")
    stamp = str(((charts[-1].get("chart") or {}).get("_comment")) or "")   # '2026-10-21 00:00' = 자료 기준일
    return {"source": "Federal Reserve Bank of Cleveland", "url": CLEVELAND_PAGE, "updated": stamp[:10] or None,
            "months": _parse_cleveland(charts)}


def collect_gdpnow(session=None, api_key=None):
    api_key = api_key or os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY 없음")
    session = session or _session()
    r = session.get(f"{FRED_URL}/series/observations", timeout=TIMEOUT, params={
        "series_id": "GDPNOW", "api_key": api_key, "file_type": "json", "sort_order": "desc", "limit": 1})
    r.raise_for_status()
    obs = (r.json().get("observations") or [{}])[0]
    value, quarter_start = _num(obs.get("value"), 2), str(obs.get("date") or "")
    if value is None or not quarter_start:
        raise ValueError("GDPNOW 관측치 없음")
    r = session.get(f"{FRED_URL}/series", timeout=TIMEOUT, params={"series_id": "GDPNOW", "api_key": api_key, "file_type": "json"})
    r.raise_for_status()
    meta = (r.json().get("seriess") or [{}])[0]
    y, m = int(quarter_start[:4]), int(quarter_start[5:7])
    return {"source": "Federal Reserve Bank of Atlanta (FRED GDPNOW)", "url": "https://fred.stlouisfed.org/series/GDPNOW",
            "quarter": f"{y}:Q{(m - 1) // 3 + 1}", "value": value, "updated": str(meta.get("last_updated") or "")[:10] or None}


def collect(date, session=None):
    """record_store 행 하나. 소스별로 따로 실패를 삼킨다 — 하나가 죽어도 다른 쪽은 남긴다."""
    session = session or _session()
    row = {"date": date, "source": "daily", "id": "nowcast", "as_of": date}
    for key, fn in (("inflation", collect_cleveland), ("gdpnow", collect_gdpnow)):
        try:
            row[key] = fn(session)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::나우캐스트 {key} 수집 실패 (기록만 비움): {e!r}")
            row[key] = None
    stamps = [v.get("updated") for v in (row["inflation"], row["gdpnow"]) if v and v.get("updated")]
    if stamps:
        row["as_of"] = max(stamps)
    return row


if __name__ == "__main__":   # 로컬 확인: python experiments/daily-report/collect_nowcast.py
    import json
    import sys

    from dotenv import load_dotenv
    load_dotenv()
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import report_title
    print(json.dumps(collect(report_title.today_kst()), ensure_ascii=False, indent=2))
