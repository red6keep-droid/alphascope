"""거시 이벤트 캘린더 → macro_calendar (confounded 판정용, 기획서 8절).

- FOMC 결정일: config의 정적 목록 (연준 공개 일정)
- CPI · NFP · GDP · PCE: FRED release/dates API (FRED_API_KEY 있을 때만)
- 관찰 종목 실적 발표일: yfinance earnings_dates (있으면 넣고, 실패해도 계속)

키가 없으면 FOMC만 들어간다. 이 경우 confounded_daily는 과소 판정된다 — README에 명시.
"""

import datetime
import os
import sys

import requests

import config
import db

FRED_URL = "https://api.stlouisfed.org/fred/release/dates"


def _insert(conn, rows):
    conn.executemany(
        "INSERT OR IGNORE INTO macro_calendar(day, kind, label, source) VALUES (?, ?, ?, ?)", rows)


def load_fomc(conn):
    rows = [(d, "FOMC", "FOMC decision", "static") for d in config.FOMC_DECISION_DATES]
    _insert(conn, rows)
    return len(rows)


def load_fred(conn, api_key, start="2024-01-01"):
    count = 0
    for release_id, label in config.FRED_RELEASES.items():
        params = {
            "release_id": release_id, "api_key": api_key, "file_type": "json",
            "realtime_start": start, "include_release_dates_with_no_data": "true",
            "limit": 1000, "sort_order": "desc",
        }
        try:
            resp = requests.get(FRED_URL, params=params, timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            dates = [d["date"] for d in resp.json().get("release_dates", []) if d.get("date", "") >= start]
        except Exception as e:  # noqa: BLE001
            print(f"[calendar] FRED release {release_id} 실패: {e}")
            continue
        kind = label.split(" ")[0].upper() if release_id != 50 else "NFP"
        if release_id == 54:
            kind = "PCE"
        _insert(conn, [(d, kind, label, "fred") for d in dates])
        count += len(dates)
    return count


def load_earnings(conn, symbols):
    import yfinance as yf  # 지연 import — 캘린더만 갱신할 때 yfinance가 없어도 되게

    count = 0
    for sym in symbols:
        try:
            ed = yf.Ticker(sym).earnings_dates
        except Exception as e:  # noqa: BLE001
            print(f"[calendar] {sym} earnings_dates 실패: {e}")
            continue
        if ed is None or ed.empty:
            continue
        rows = [(idx.strftime("%Y-%m-%d"), "EARNINGS", sym, "yfinance") for idx in ed.index]
        _insert(conn, rows)
        count += len(rows)
    return count


def refresh(conn):
    n_fomc = load_fomc(conn)
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    n_fred = load_fred(conn, api_key) if api_key else 0
    if not api_key:
        print("[calendar] FRED_API_KEY 없음 — CPI/NFP/GDP/PCE 미반영 (confounded_daily 과소 판정)")
    n_earn = load_earnings(conn, config.UNIVERSE["named"])
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM macro_calendar").fetchone()[0]
    print(f"[calendar] FOMC {n_fomc} · FRED {n_fred} · 실적 {n_earn} → 누적 {total}건")
    db.set_meta(conn, "calendar_last_refreshed_at",
                datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    conn.commit()


def labels_on(conn, day):
    """해당 거래일의 거시 이벤트 라벨 목록."""
    return [f"{r['kind']}:{r['label']}" for r in conn.execute(
        "SELECT kind, label FROM macro_calendar WHERE day = ?", (day,))]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    refresh(db.connect())
