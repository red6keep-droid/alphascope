"""FINRA Reg SHO 일별 공매도 거래량 (장외 보고분) — 스마트 머니 흔적 ② (2026-10-11 사용자: "시작해").

파일: https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt (Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market)
- 장외(FINRA TRF·ADF 보고) 거래만 집계한다 — 거래소 체결은 빠진다. 그래서 TotalVolume은 일봉 거래량보다 작고, 비율은 '장외 공매도 비율'이라고 적는다.
- 그날 파일은 미국 저녁에 올라오므로 22:45 UTC 실행에는 기준 거래일 파일이 아직 없을 수 있다 → 그 칸은 "—", 다음 실행에서 채운다.
- daily_state.finra_short_vol · finra_total_vol · finra_short_ratio(%). 기준일 포함 최근 FINRA_BACKFILL_DAYS 거래일 중 빈 날만 받는다.
"""

import requests

import config
import db


def _fetch_day(day):
    url = config.FINRA_SHORT_URL.format(ymd=day.replace("-", ""))
    r = requests.get(url, headers={"User-Agent": config.BROWSER_USER_AGENT}, timeout=config.HTTP_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    for line in r.text.splitlines():
        p = line.split("|")
        if len(p) >= 5 and p[1] == config.SYMBOL:
            short, total = float(p[2]), float(p[4])
            return {"short": short, "total": total, "ratio": (short / total * 100) if total else None}
    return {"short": None, "total": None, "ratio": None}   # 파일은 있는데 심볼 행이 없다


def collect(conn, day):
    days = [r["day"] for r in conn.execute(
        "SELECT day FROM daily_bars WHERE symbol = ? AND day <= ? ORDER BY day DESC LIMIT ?",
        (config.SYMBOL, day, config.FINRA_BACKFILL_DAYS))]
    have = {r["day"] for r in conn.execute(
        "SELECT day FROM daily_state WHERE finra_short_ratio IS NOT NULL AND day <= ?", (day,))}
    got, missing = 0, []
    for d in days:
        if d in have:
            continue
        try:
            v = _fetch_day(d)
        except Exception as e:  # noqa: BLE001
            print(f"[finra] {d} 실패: {e}")
            continue
        if not v or v["ratio"] is None:
            missing.append(d)
            continue
        conn.execute("INSERT OR IGNORE INTO daily_state(day) VALUES (?)", (d,))
        conn.execute("UPDATE daily_state SET finra_short_vol = ?, finra_total_vol = ?, finra_short_ratio = ? WHERE day = ?",
                     (v["short"], v["total"], v["ratio"], d))
        got += 1
    conn.commit()
    cur = conn.execute("SELECT finra_short_ratio FROM daily_state WHERE day = ?", (day,)).fetchone()
    cur = cur["finra_short_ratio"] if cur else None
    print(f"[finra] 장외 공매도 비율 {got}일 수신 · 기준일 {day}: {f'{cur:.1f}%' if cur is not None else '파일 아직 없음'}"
          + (f" · 없는 날 {missing[:3]}" if missing else ""))
    return got
