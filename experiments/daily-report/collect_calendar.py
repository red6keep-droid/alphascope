"""다가오는 일정 (D5, doc/데일리-리포트-기획.md 6절 일정 탭) — 앞으로 LOOKAHEAD 일.

- FOMC 결정일: static/daily_stats.json 의 fomc_upcoming (data/store/calendar/fomc.csv 에서 build_daily_stats.py 가 옮김)
- CPI · 고용 보고서 · GDP · PCE: FRED release/dates API (FRED_API_KEY, 엔비디아 collect_calendar 와 같은 release id)
- 월간 옵션 만기: 셋째 금요일 계산
- 대형주 10개 실적 발표일: yfinance get_earnings_dates (추정일 포함 — 확정 여부는 모른다)
실패한 묶음은 빼고 나머지만 낸다. 리포트를 막지 않는다.
"""

import datetime
import json
import os

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(BASE, "static", "daily_stats.json")
LOOKAHEAD = 14
FRED_URL = "https://api.stlouisfed.org/fred/release/dates"
FRED_RELEASES = {10: "CPI", 50: "NFP", 53: "GDP", 54: "PCE"}
MEGA = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "JPM"]


def _third_fridays(start, end):
    out, d = [], datetime.date(start.year, start.month, 1)
    while d <= end:
        first_fri = d + datetime.timedelta(days=(4 - d.weekday()) % 7)
        f = first_fri + datetime.timedelta(days=14)
        if start <= f <= end:
            out.append(f)
        d = datetime.date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return out


def _fred(api_key, start, end):
    rows = []
    for rid, kind in FRED_RELEASES.items():
        try:
            r = requests.get(FRED_URL, params={"release_id": rid, "api_key": api_key, "file_type": "json",
                                               "realtime_start": start.isoformat(), "include_release_dates_with_no_data": "true",
                                               "limit": 50, "sort_order": "asc"}, timeout=30)
            r.raise_for_status()
            for x in r.json().get("release_dates", []):
                d = x.get("date", "")
                if start.isoformat() <= d <= end.isoformat():
                    rows.append({"day": d, "kind": kind})
        except Exception as e:  # noqa: BLE001
            print(f"[일정] FRED {kind} 실패: {e}")
    return rows


def _earnings(start, end):
    import yfinance as yf

    rows = []
    for sym in MEGA:
        try:
            ed = yf.Ticker(sym).get_earnings_dates(limit=4)
        except Exception as e:  # noqa: BLE001
            print(f"[일정] {sym} 실적일 실패: {e}")
            continue
        if ed is None or ed.empty:
            continue
        for ts in ed.index:
            d = ts.date()
            if start <= d <= end:
                rows.append({"day": d.isoformat(), "kind": "EARNINGS", "symbol": sym,
                             "after_close": ts.hour >= 16 or ts.hour == 0})
                break
    return rows


def collect_calendar(today=None):
    today = today or datetime.date.today()
    end = today + datetime.timedelta(days=LOOKAHEAD)
    rows = []
    try:
        with open(STATS, encoding="utf-8") as f:
            fomc = json.load(f).get("fomc_upcoming") or []
        rows += [{"day": d, "kind": "FOMC"} for d in fomc if today.isoformat() <= d <= end.isoformat()]
    except (OSError, ValueError) as e:
        print(f"[일정] FOMC 목록 없음: {e}")
    key = os.environ.get("FRED_API_KEY")
    if key:
        rows += _fred(key, today, end)
    rows += [{"day": d.isoformat(), "kind": "OPEX"} for d in _third_fridays(today, end)]
    rows += _earnings(today, end)
    rows.sort(key=lambda r: (r["day"], r["kind"]))
    print(f"[일정] {LOOKAHEAD}일 안 {len(rows)}건")
    return {"from": today.isoformat(), "to": end.isoformat(), "days": LOOKAHEAD, "items": rows}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(json.dumps(collect_calendar(), ensure_ascii=False, indent=1))
