"""CFTC 선물 포지션 — 헤지펀드(레버리지 펀드) S&P 500 · 나스닥 100 선물 순포지션 (2026-11-09 사용자).

- 출처: CFTC Traders in Financial Futures (선물만), 공개 API publicreporting.cftc.gov 데이터셋 gpe5-46if. 키 없음.
- 기준일 = 화요일 장 마감 포지션, 발표 = 그 주 금요일 15:30 ET. 그래서 날마다 같은 값이 며칠 이어진다.
- 순포지션 = lev_money_positions_long − lev_money_positions_short (계약 수).
- 3년 범위 = 최근 156주 순포지션의 최저 · 최고, 오늘 자리 = 그 안 몇 % 지점.
- 사실만 낸다 — 위험 점수 · 판정 없음. 극단 포지션이 급락을 앞서는지는 검증 전 (비공개 doc/검증 예정).

실패하면 마지막으로 받은 값(output/state/cftc_last.json)을 기준일과 함께 쓰고, 그것도 없으면 None — 카드만 빠진다.
"""

import datetime
import json
import os

import requests

URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
CONTRACTS = {"sp500": ("13874A", "S&P 500"), "nasdaq": ("209742", "나스닥 100")}   # E-mini S&P 500 · E-mini 나스닥 100 (CME)
WEEKS = 156
HIST = 12   # 카드 막대 주 수
TIMEOUT = 30

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_PATH = os.path.join(BASE_DIR, "output", "state", "cftc_last.json")


def _fetch(code, since):
    r = requests.get(URL, params={
        "$select": "report_date_as_yyyy_mm_dd,lev_money_positions_long,lev_money_positions_short,open_interest_all,"
                   "asset_mgr_positions_long,asset_mgr_positions_short",
        "$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd >= '{since}'",
        "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": 1000,
    }, headers={"User-Agent": "alpha-scope/daily-report"}, timeout=TIMEOUT)
    r.raise_for_status()
    rows = []
    for x in r.json():
        try:
            rows.append((x["report_date_as_yyyy_mm_dd"][:10], int(x["lev_money_positions_long"]), int(x["lev_money_positions_short"]),
                         int(x["open_interest_all"]), int(x["asset_mgr_positions_long"]) - int(x["asset_mgr_positions_short"])))
        except (KeyError, ValueError, TypeError):
            continue
    return rows[-WEEKS:]


def _summary(rows, name):
    if len(rows) < 52:   # 1년도 안 되면 범위가 뜻이 없다
        return None
    nets = [lg - sh for _d, lg, sh, _oi, _am in rows]
    lo, hi, net = min(nets), max(nets), nets[-1]
    d, lg, sh, oi, _am = rows[-1]
    am = [r[4] for r in rows]   # 자산운용사 · 연기금 순포지션 — 급락한 주에 거의 늘 판 쪽 (2026-11-09 사용자, 46번 중 45번)
    alo, ahi = min(am), max(am)
    return {"name": name, "date": d, "net": net, "prev": nets[-2], "prev_date": rows[-2][0], "long": lg, "short": sh, "oi": oi,
            "prev_long": rows[-2][1], "prev_short": rows[-2][2],
            "hist": [[r[0], r[1] - r[2], r[4]] for r in rows[-HIST - 1:]],   # 최근 13주 [기준일, 헤지펀드 순, 자산운용사 순] → 카드의 12주 주간 순매수 · 순매도 막대 (2026-11-11 사용자 "기간에 따라 늘고 있는지")   # 산 물량 · 판 물량 각각 지난주 대비 (2026-11-11 사용자 "매수가 늘어난 건지 매도가 늘어난 건지")
            "lo": lo, "hi": hi, "pos_pct": round((net - lo) / (hi - lo) * 100) if hi > lo else 50, "weeks": len(rows),
            "from": rows[0][0],
            "am": {"net": am[-1], "prev": am[-2], "lo": alo, "hi": ahi, "pos_pct": round((am[-1] - alo) / (ahi - alo) * 100) if ahi > alo else 50}}


def collect_cftc(today=None):
    today = today or datetime.date.today()
    since = (today - datetime.timedelta(weeks=WEEKS + 2)).isoformat()
    out = {}
    for key, (code, name) in CONTRACTS.items():
        try:
            s = _summary(_fetch(code, since), name)
            if s:
                out[key] = s
        except Exception as e:  # noqa: BLE001
            print(f"::warning::CFTC {name} 수집 실패: {e!r}")
    if out:
        os.makedirs(os.path.dirname(LAST_PATH), exist_ok=True)
        with open(LAST_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"[CFTC] 기준일 {next(iter(out.values()))['date']} · {', '.join(out)}")
        return out
    try:
        with open(LAST_PATH, encoding="utf-8") as f:
            last = json.load(f) or None
        if last:
            print("::warning::CFTC 대신 저장값 사용")
            return {k: {**v, "source": "저장값"} for k, v in last.items()}
    except (OSError, ValueError):
        pass
    return None


if __name__ == "__main__":
    print(json.dumps(collect_cftc(), ensure_ascii=False, indent=1))
