"""일봉 캐시와 "그날 반응" (기획 9-3, 2026-10-25). LLM 없음.

- data/prices.json: {symbol: {"YYYY-MM-DD": close}} — yfinance 로 최근 PERIOD 를 받아 덮어쓴다 (하루 한 번이면 충분, 12시간 안이면 다시 받지 않는다).
- effective_day(발언 UTC): 미국 동부 16:00 전 + 거래일이면 그날, 아니면 다음 거래일 (reaction_refs · 트럼프 반응 통계와 같은 규칙). 거래일은 SPY 기준.
- reaction(symbol, D): close(D)/close(D-1) − 1 (금리 ^TNX 는 bp 차이), 평소 대비 = |등락| ÷ 직전 60거래일 |등락| 중앙값. D 종가가 없으면 pending.
yfinance 가 막히면 캐시로 간다 — 캐시도 없으면 그 자산 줄은 빠진다 (가격 약관 · 예비 소스는 price_source 메모 참고).
"""

import datetime
import json
import os
import statistics
import zoneinfo

import config

PRICES_PATH = os.path.join(config.DATA_DIR, "prices.json")
PERIOD = "6mo"
FRESH_HOURS = 12
REL_LOOKBACK = 60
ET = zoneinfo.ZoneInfo("America/New_York")
BASE_SYMBOLS = ["SPY"]   # 거래일 달력용 — 항상 받는다

_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            with open(PRICES_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {"_fetched_at": None, "bars": {}}
    return _cache


def _save():
    os.makedirs(os.path.dirname(PRICES_PATH), exist_ok=True)
    with open(PRICES_PATH, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)


def ensure(symbols, force=False):
    """필요한 심볼을 캐시에 갖춘다. 12시간 안에 받은 것이 있고 심볼이 다 있으면 건너뛴다."""
    c = _load()
    want = [s for s in dict.fromkeys(list(symbols) + BASE_SYMBOLS)]
    fetched = c.get("_fetched_at")
    fresh = False
    if fetched and not force:
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.strptime(fetched, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        fresh = age < datetime.timedelta(hours=FRESH_HOURS)
    missing = [s for s in want if s not in c["bars"]]
    if fresh and not missing:
        return c["bars"]
    try:
        import yfinance as yf
    except ImportError:
        print("[prices] yfinance 없음 — 캐시만")
        return c["bars"]
    todo = want if not fresh else missing
    ok = 0
    for sym in todo:
        try:
            h = yf.Ticker(sym).history(period=PERIOD, interval="1d", auto_adjust=True)
            if h is None or h.empty:
                continue
            c["bars"][sym] = {d.strftime("%Y-%m-%d"): round(float(v), 4) for d, v in h["Close"].dropna().items()}
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"[prices] {sym} 실패: {str(e)[:80]}")
    if ok:
        c["_fetched_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _save()
    print(f"[prices] {ok}/{len(todo)} 심볼 갱신 · 캐시 {len(c['bars'])}개")
    return c["bars"]


def trading_days():
    return sorted((_load()["bars"].get("SPY") or {}).keys())


def effective_day(utc_iso):
    """발언 UTC 시각 → 반응을 재는 거래일 D (문자열). 거래일 달력이 비면 None."""
    days = trading_days()
    if not days:
        return None
    dt = datetime.datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(ET)
    d = dt.date() if dt.hour < 16 else dt.date() + datetime.timedelta(days=1)
    d = d.isoformat()
    nxt = [x for x in days if x >= d]
    if nxt:
        return nxt[0]
    # 달력 끝(오늘 · 앞으로) — 다음 평일을 D 로 두고 pending
    dd = datetime.date.fromisoformat(d)
    while dd.weekday() >= 5:
        dd += datetime.timedelta(days=1)
    return dd.isoformat()


def reaction(symbol, day):
    """{"day", "ret"(%), "bp"(^TNX 만), "rel"(평소 대비 배수), "pending"} — 자료가 없으면 None."""
    bars = _load()["bars"].get(symbol)
    if not bars or not day:
        return None
    days = sorted(bars)
    if day not in bars:
        return {"day": day, "pending": True}
    i = days.index(day)
    if i == 0:
        return None
    prev, cur = bars[days[i - 1]], bars[day]
    if not prev:
        return None
    out = {"day": day, "pending": False}
    if symbol == "^TNX":
        out["bp"] = round((cur - prev) * 100, 1)   # ^TNX 는 % 단위 수익률 → bp
        rets = [abs(bars[days[k]] - bars[days[k - 1]]) * 100 for k in range(max(1, i - REL_LOOKBACK), i)]
        move = abs(out["bp"])
    else:
        out["ret"] = round((cur / prev - 1) * 100, 2)
        rets = [abs(bars[days[k]] / bars[days[k - 1]] - 1) * 100 for k in range(max(1, i - REL_LOOKBACK), i) if bars[days[k - 1]]]
        move = abs(out["ret"])
    med = statistics.median(rets) if len(rets) >= 20 else None
    out["rel"] = round(move / med, 1) if med else None
    return out
