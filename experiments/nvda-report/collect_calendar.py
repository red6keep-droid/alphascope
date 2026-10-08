"""다가오는 것 → calendar (기획서 2절 캘린더 묶음, ①단계 범위).

- FOMC 결정일: config 정적 목록
- CPI · NFP · GDP · PCE: FRED release/dates API (FRED_API_KEY 있을 때만)
- 실적 발표일 12종목: yfinance earnings_dates (+ NVDA는 Ticker.calendar의 날짜를 우선)
- OPEX(월간 옵션 만기)·INDEX(S&P 분기 리밸런싱 발효·나스닥100 연례 재구성): 셋째 금요일 계산
- GTC · Computex · CES: static/events.json (연 1회 수동 갱신)

TSMC 월매출·ETF 발행주식수는 ④단계에서 붙인다.
"""

import datetime
import json
import os
import sys

import requests

import config
import db

FRED_URL = "https://api.stlouisfed.org/fred/release/dates"
MACRO_KIND = {10: "CPI", 50: "NFP", 53: "GDP", 54: "PCE"}


def _insert(conn, rows):
    conn.executemany(
        "INSERT OR IGNORE INTO calendar(day, kind, label, symbol, source, confirmed) VALUES (?, ?, ?, ?, ?, ?)", rows)


def load_fomc(conn):
    rows = [(d, "FOMC", "FOMC 결정", None, "static", 1) for d in config.FOMC_DECISION_DATES]
    _insert(conn, rows)
    return len(rows)


def load_fred(conn, api_key, start="2025-01-01"):
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
        _insert(conn, [(d, MACRO_KIND[release_id], label, None, "fred", 1) for d in dates])
        count += len(dates)
    return count


def load_earnings(conn, symbols, today):
    """미래 실적일은 매 실행 지우고 다시 넣는다 — yfinance 추정일이 바뀌면 옛 날짜가 남지 않게."""
    import yfinance as yf

    limit = (today + datetime.timedelta(days=config.EARNINGS_FUTURE_LIMIT_DAYS)).isoformat()
    count = 0
    for sym in symbols:
        kind = "EARNINGS" if sym == config.SYMBOL else "EARNINGS_PEER"
        t = yf.Ticker(sym)
        days = set()
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                days |= {idx.strftime("%Y-%m-%d") for idx in ed.index}
        except Exception as e:  # noqa: BLE001
            print(f"[calendar] {sym} earnings_dates 실패: {e}")
        cal_day = None
        if sym == config.SYMBOL:
            try:
                cal = t.calendar or {}
                ds = cal.get("Earnings Date") or []
                cal_day = min(str(d)[:10] for d in ds) if ds else None
            except Exception as e:  # noqa: BLE001
                print(f"[calendar] {sym} calendar 실패: {e}")
        if not days and not cal_day:
            continue
        conn.execute("DELETE FROM calendar WHERE kind = ? AND symbol = ? AND day >= ?", (kind, sym, today.isoformat()))
        future = sorted(d for d in days if d >= today.isoformat() and d <= limit)
        past = sorted(d for d in days if d < today.isoformat())
        # NVDA는 회사 캘린더 날짜를 신뢰하고, earnings_dates의 미래 추정일은 그 주의 중복으로 본다
        if cal_day and cal_day >= today.isoformat():
            future = [cal_day] + [d for d in future if abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(cal_day)).days) > 3]
        rows = [(d, kind, f"{sym} 실적", sym, "yfinance", 1) for d in past]
        rows += [(d, kind, f"{sym} 실적", sym, "yfinance", 0) for d in future]
        _insert(conn, rows)
        count += len(rows)
    return count


def third_friday(year, month):
    d = datetime.date(year, month, 15)
    while d.weekday() != 4:
        d += datetime.timedelta(days=1)
    return d


def load_computed(conn, today):
    rows = []
    for y in range(today.year, today.year + config.CALENDAR_GENERATE_YEARS):
        for m in range(1, 13):
            f = third_friday(y, m).isoformat()
            rows.append((f, "OPEX", "월간 옵션 만기", None, "computed", 1))
            if m in config.INDEX_REBALANCE_MONTHS:
                rows.append((f, "INDEX", "S&P 500 분기 리밸런싱 발효", None, "computed", 1))
            if m == 12:
                rows.append((f, "INDEX", "나스닥100 연례 재구성 발효", None, "computed", 1))
    _insert(conn, rows)
    return len(rows)


def load_static(conn):
    path = os.path.join(config.STATIC_DIR, "events.json")
    if not os.path.exists(path):
        print(f"[calendar] 정적 캘린더 없음: {path}")
        return 0
    with open(path, "r", encoding="utf-8") as f:
        events = json.load(f)
    rows = [(e["day"], e.get("kind", "EVENT"), e["label"], e.get("symbol"), "static", 1 if e.get("confirmed", True) else 0)
            for e in events]
    _insert(conn, rows)
    return len(rows)


def refresh(conn, today=None):
    today = today or datetime.date.today()
    n_fomc = load_fomc(conn)
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    n_fred = load_fred(conn, api_key) if api_key else 0
    if not api_key:
        print("[calendar] FRED_API_KEY 없음 — CPI/NFP/GDP/PCE 미반영")
    n_earn = load_earnings(conn, config.EARNINGS_SYMBOLS, today)
    n_comp = load_computed(conn, today)
    n_static = load_static(conn)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM calendar").fetchone()[0]
    print(f"[calendar] FOMC {n_fomc} · FRED {n_fred} · 실적 {n_earn} · 계산 {n_comp} · 정적 {n_static} → 누적 {total}건")
    db.set_meta(conn, "calendar_last_refreshed_at", db.now_iso())
    conn.commit()


def upcoming(conn, day, lookahead=config.CALENDAR_LOOKAHEAD_DAYS):
    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=lookahead)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT day, kind, label, symbol, source, confirmed FROM calendar WHERE day >= ? AND day <= ? ORDER BY day, kind",
        (day, end))]


def on_day(conn, day):
    return [dict(r) for r in conn.execute(
        "SELECT day, kind, label, symbol, source, confirmed FROM calendar WHERE day = ? ORDER BY kind", (day,))]


def next_of(conn, kind, day, symbol=None):
    q = "SELECT day FROM calendar WHERE kind = ? AND day >= ?"
    args = [kind, day]
    if symbol:
        q += " AND symbol = ?"
        args.append(symbol)
    row = conn.execute(q + " ORDER BY day LIMIT 1", args).fetchone()
    return row["day"] if row else None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    refresh(db.connect())
