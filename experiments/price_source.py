"""가격 데이터 예비 소스 — yfinance 가 막힌 날을 위한 공식 API 사슬 (2026-10-21, doc/운영/블로그-운영-지침.md D6-1 · D4-7-1).

순서 (키가 있는 것만, 없으면 건너뜀):
    FRED(공식 · 지수 · VIX · 금리 · 환율, 키 FRED_API_KEY) → Polygon/Massive → Twelve Data → Finnhub(호가만) → Alpha Vantage(하루 25회, 맨 뒤)

약관: 네 곳 무료 등급은 모두 "개인 · 비상업 · 내부(비표시)" 라이선스라 공개 블로그 표시는 약관 밖이다 — yfinance(Yahoo 약관)와
같은 조건이다. 2026-10-21 사용자: "yfinance 와 동일하면 수집 순위로 올려줘, 예비로". 그래서 1순위가 아니라 **yfinance 가 실패한
심볼에만** 쓴다. Stooq CSV 는 2026-10 현재 JS 브라우저 확인 뒤라 못 쓴다.

무료 한도 (2026-10-21 요금표): Polygon 5회/분 · 종가(EOD) · 2년 — Twelve Data 8크레딧/분 · 800/일 · 실시간 — Finnhub 60회/분, 일봉 캔들은 유료
(호가 · 프로필 · 실적일만) — Alpha Vantage 5회/분 · **25회/일**. 호출 사이 간격은 _GAP 으로 지킨다(한 실행이 순차라 자연히 분산).

환경 변수 (GitHub 시크릿 이름과 같게): POLYGON_API_KEY · TWELVEDATA_API_KEY · FINNHUB_API_KEY · ALPHAVANTAGE_API_KEY
(사용자가 적은 이름 POLYGON_API · TWELVE_DATA_API · FINNHUB_API · ALPHAVANTAGE_API 도 받는다.) 값은 절대 출력하지 않는다.

쓰는 법:
    import price_source
    price_source.quote(symbol)                  # {"price", "prev", "change_pct", "volume", "date", "source", ["day_high","day_low"]} 또는 None
    price_source.daily_bars(symbol, start)      # [{"day","open","high","low","close","volume"}, ...] 오래된 날이 앞. 없으면 []
    price_source.daily_closes(symbol, start)    # [(day, close), ...]  (호환)
    price_source.intraday_bars(symbol, "15min") # 오늘 분봉 [{"t","o","h","l","c","v"}] — Twelve Data 만 (Polygon 무료는 EOD)
"""

import datetime
import os
import time

import requests

# yfinance 심볼 → FRED 시리즈. 여기 없는 심볼은 FRED 단계 건너뜀.
FRED_MAP = {
    "^GSPC": "SP500",
    "^IXIC": "NASDAQCOM",
    "^DJI": "DJIA",
    "^VIX": "VIXCLS",
    "^TNX": "DGS10",      # 10년물 수익률(%) — yfinance ^TNX 도 % 단위
    "^FVX": "DGS5",
    "^IRX": "DTB3",
    "KRW=X": "DEXKOUS",
}
# FRED 에 없는 것: ^RUT · ^SOX · 개별 종목 · ETF (RU2000PR 은 400, 2026-10-21 확인)

_UA = {"User-Agent": "alpha-scope/price-fallback"}
_TIMEOUT = 30
_GAP = {"polygon": 12.5, "twelvedata": 8, "finnhub": 1.1, "alphavantage": 13}   # 분당 한도 → 호출 간격(초)
_last = {}


def _key(*names):
    """환경 변수의 첫 키만. 값에 쉼표로 키가 여럿 있어도 첫 것만 쓴다 — 같은 공급자의 키를 돌려 한도를 늘리는 것은
    약관상 우회라 하지 않는다 (운영지침 3-1, llm_chain.gemini_keys 와 같은 규칙. 2026-10-21 .env 에 공급자마다 2~4개가 있었다)."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v.split(",")[0].strip()
    return ""


KEYS = {
    "fred": lambda: _key("FRED_API_KEY"),
    "polygon": lambda: _key("POLYGON_API_KEY", "POLYGON_API"),
    "twelvedata": lambda: _key("TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY", "TWELVE_DATA_API"),
    "finnhub": lambda: _key("FINNHUB_API_KEY", "FINNHUB_API"),
    "alphavantage": lambda: _key("ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API"),
}


def _throttle(provider):
    gap = _GAP.get(provider, 0)
    t = _last.get(provider)
    if t and gap:
        wait = gap - (time.monotonic() - t)
        if wait > 0:
            time.sleep(wait)
    _last[provider] = time.monotonic()


def _get(provider, url, params):
    """키가 URL 쿼리에 들어가는 공급자가 많다 — 오류 메시지에 URL 을 섞지 않는다 (운영지침 9절). 상태 코드만."""
    _throttle(provider)
    r = requests.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"{provider} HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(f"{provider} JSON 아님")


def _dot(symbol):
    """BRK-B → BRK.B (Polygon · Twelve Data · Finnhub 표기). 지수(^…) · 환율(=X)은 이 공급자들에서 안 받는다."""
    return symbol.replace("-", ".")


def _plain(symbol):
    return not (symbol.startswith("^") or symbol.endswith("=X"))


def _log(symbol, provider, what):
    print(f"[price_source] {symbol} ← {provider} {what} (yfinance 대체)")


# ── FRED ───────────────────────────────────────────────────────────────────

def _fred_observations(series_id, start=None, limit=None):
    key = KEYS["fred"]()
    if not key:
        return []
    params = {"series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc"}
    if start:
        params["observation_start"] = start
    if limit:
        params["limit"] = limit
    j = _get("fred", "https://api.stlouisfed.org/fred/series/observations", params)
    out = []
    for o in j.get("observations", []):
        if o.get("value") in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(o["value"])))
        except (TypeError, ValueError):
            continue
    return out   # 최신이 앞


def _fred_quote(symbol):
    sid = FRED_MAP.get(symbol)
    if not sid:
        return None
    obs = _fred_observations(sid, limit=5)
    if len(obs) < 2 or not obs[1][1]:
        return None
    (d1, v1), (_, v0) = obs[0], obs[1]
    _log(symbol, "FRED", f"{sid} {d1}")
    return {"price": round(v1, 2), "prev": round(v0, 2), "change_pct": round((v1 - v0) / v0 * 100, 2), "volume": 0, "date": d1, "source": "FRED"}


def _fred_bars(symbol, start):
    sid = FRED_MAP.get(symbol)
    if not sid:
        return []
    obs = sorted(_fred_observations(sid, start=start))
    if obs:
        _log(symbol, "FRED", f"{sid} {len(obs)}일")
    return [{"day": d, "open": c, "high": c, "low": c, "close": c, "volume": None} for d, c in obs]


# ── Polygon / Massive (무료: 5회/분, EOD, 2년) ──────────────────────────────

def _polygon_quote(symbol):
    key = KEYS["polygon"]()
    if not key or not _plain(symbol):
        return None
    j = _get("polygon", f"https://api.polygon.io/v2/aggs/ticker/{_dot(symbol)}/prev", {"adjusted": "true", "apiKey": key})
    res = (j.get("results") or [])
    if not res:
        return None
    r = res[0]
    # prev 는 "직전 거래일 하루" — 전일 종가는 없다. 그 전날을 한 번 더 받아 등락률을 만든다
    day = datetime.datetime.utcfromtimestamp(r["t"] / 1000).date()
    bars = _polygon_bars(symbol, (day - datetime.timedelta(days=10)).isoformat(), end=day.isoformat())
    prev = bars[-2]["close"] if len(bars) >= 2 else None
    out = {"price": round(r["c"], 2), "prev": prev, "change_pct": round((r["c"] - prev) / prev * 100, 2) if prev else None,
           "volume": int(r.get("v") or 0), "date": day.isoformat(), "source": "Polygon", "day_high": r.get("h"), "day_low": r.get("l")}
    _log(symbol, "Polygon", f"prev {day}")
    return out


def _polygon_bars(symbol, start, end=None):
    key = KEYS["polygon"]()
    if not key or not _plain(symbol):
        return []
    end = end or datetime.date.today().isoformat()
    j = _get("polygon", f"https://api.polygon.io/v2/aggs/ticker/{_dot(symbol)}/range/1/day/{start}/{end}",
             {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key})
    out = []
    for r in j.get("results") or []:
        day = datetime.datetime.utcfromtimestamp(r["t"] / 1000).date().isoformat()
        out.append({"day": day, "open": r.get("o"), "high": r.get("h"), "low": r.get("l"), "close": r["c"], "volume": r.get("v")})
    if out:
        _log(symbol, "Polygon", f"{len(out)}일")
    return out


# ── Twelve Data (무료: 8/분 · 800/일 · 실시간 미국 주식) ─────────────────────

def _twelve_quote(symbol):
    key = KEYS["twelvedata"]()
    if not key or not _plain(symbol):
        return None
    j = _get("twelvedata", "https://api.twelvedata.com/quote", {"symbol": _dot(symbol), "apikey": key})
    if j.get("status") == "error" or "close" not in j:
        return None
    price, prev = float(j["close"]), float(j.get("previous_close") or 0) or None
    _log(symbol, "TwelveData", "quote")
    return {"price": round(price, 2), "prev": prev, "change_pct": round((price - prev) / prev * 100, 2) if prev else None,
            "volume": int(float(j.get("volume") or 0)), "date": (j.get("datetime") or "")[:10], "source": "TwelveData",
            "day_high": float(j["high"]) if j.get("high") else None, "day_low": float(j["low"]) if j.get("low") else None}


def _twelve_bars(symbol, start):
    key = KEYS["twelvedata"]()
    if not key or not _plain(symbol):
        return []
    j = _get("twelvedata", "https://api.twelvedata.com/time_series",
             {"symbol": _dot(symbol), "interval": "1day", "start_date": start, "outputsize": 5000, "order": "ASC", "apikey": key})
    vals = j.get("values") or []
    out = [{"day": v["datetime"][:10], "open": float(v["open"]), "high": float(v["high"]), "low": float(v["low"]), "close": float(v["close"]),
            "volume": float(v["volume"]) if v.get("volume") else None} for v in vals]
    if out:
        _log(symbol, "TwelveData", f"{len(out)}일")
    return out


def intraday_bars(symbol, interval="15min"):
    """오늘(뉴욕) 분봉 — 홈 시총 TOP 10 차트용. Twelve Data 만(Polygon 무료는 EOD). [{"t","o","h","l","c","v"}]"""
    key = KEYS["twelvedata"]()
    if not key or not _plain(symbol):
        return []
    try:
        j = _get("twelvedata", "https://api.twelvedata.com/time_series",
                 {"symbol": _dot(symbol), "interval": interval, "outputsize": 40, "order": "ASC", "timezone": "America/New_York", "apikey": key})
    except Exception as e:  # noqa: BLE001
        print(f"[price_source] {symbol} TwelveData 분봉 실패: {e}")
        return []
    vals = j.get("values") or []
    if not vals:
        return []
    last_day = vals[-1]["datetime"][:10]
    out = []
    ny = datetime.timezone(datetime.timedelta(hours=-4))   # 표시용 근사 — 홈 차트는 순서만 쓴다
    for v in vals:
        if v["datetime"][:10] != last_day:
            continue
        t = datetime.datetime.fromisoformat(v["datetime"]).replace(tzinfo=ny)
        out.append({"t": int(t.timestamp()), "o": round(float(v["open"]), 2), "h": round(float(v["high"]), 2),
                    "l": round(float(v["low"]), 2), "c": round(float(v["close"]), 2), "v": int(float(v.get("volume") or 0))})
    if out:
        _log(symbol, "TwelveData", f"{interval} {len(out)}봉")
    return out


# ── Finnhub (무료: 호가만 — 캔들은 유료 403) ──────────────────────────────

def _finnhub_quote(symbol):
    key = KEYS["finnhub"]()
    if not key or not _plain(symbol):
        return None
    j = _get("finnhub", "https://finnhub.io/api/v1/quote", {"symbol": _dot(symbol), "token": key})
    c, pc = j.get("c"), j.get("pc")
    if not c or not pc:
        return None
    _log(symbol, "Finnhub", "quote")
    return {"price": round(float(c), 2), "prev": round(float(pc), 2), "change_pct": round((c - pc) / pc * 100, 2), "volume": 0,
            "date": datetime.datetime.utcfromtimestamp(j.get("t") or 0).date().isoformat() if j.get("t") else "", "source": "Finnhub",
            "day_high": j.get("h"), "day_low": j.get("l")}


# ── Alpha Vantage (무료: 25회/일 — 맨 뒤) ───────────────────────────────────

def _alpha_quote(symbol):
    key = KEYS["alphavantage"]()
    if not key or not _plain(symbol):
        return None
    j = _get("alphavantage", "https://www.alphavantage.co/query", {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": key})
    q = j.get("Global Quote") or {}
    if not q.get("05. price"):
        return None
    price, prev = float(q["05. price"]), float(q.get("08. previous close") or 0) or None
    _log(symbol, "AlphaVantage", "quote")
    return {"price": round(price, 2), "prev": prev, "change_pct": round((price - prev) / prev * 100, 2) if prev else None,
            "volume": int(float(q.get("06. volume") or 0)), "date": q.get("07. latest trading day", ""), "source": "AlphaVantage",
            "day_high": float(q["03. high"]) if q.get("03. high") else None, "day_low": float(q["04. low"]) if q.get("04. low") else None}


def _alpha_bars(symbol, start):
    key = KEYS["alphavantage"]()
    if not key or not _plain(symbol):
        return []
    j = _get("alphavantage", "https://www.alphavantage.co/query",
             {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "full", "apikey": key})
    ts = j.get("Time Series (Daily)") or {}
    out = []
    for day in sorted(ts):
        if day < start:
            continue
        v = ts[day]
        out.append({"day": day, "open": float(v["1. open"]), "high": float(v["2. high"]), "low": float(v["3. low"]), "close": float(v["4. close"]),
                    "volume": float(v.get("5. volume") or 0)})
    if out:
        _log(symbol, "AlphaVantage", f"{len(out)}일")
    return out


# ── 사슬 ───────────────────────────────────────────────────────────────────

_QUOTE_CHAIN = (("FRED", _fred_quote), ("Polygon", _polygon_quote), ("TwelveData", _twelve_quote), ("Finnhub", _finnhub_quote), ("AlphaVantage", _alpha_quote))
_BARS_CHAIN = (("FRED", _fred_bars), ("Polygon", _polygon_bars), ("TwelveData", _twelve_bars), ("AlphaVantage", _alpha_bars))


def quote(symbol):
    """가격 · 전일 · 등락률. 사슬을 차례로, 실패 · 대체 불가면 None."""
    for name, fn in _QUOTE_CHAIN:
        try:
            q = fn(symbol)
        except Exception as e:  # noqa: BLE001
            print(f"[price_source] {symbol} {name} 실패: {e}")
            continue
        if q:
            return q
    return None


def daily_bars(symbol, start=None):
    """일봉 [{"day","open","high","low","close","volume"}] 오래된 날이 앞. FRED 는 종가만(OHL = 종가)."""
    if start is None:
        start = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
    for name, fn in _BARS_CHAIN:
        try:
            rows = fn(symbol, start)
        except Exception as e:  # noqa: BLE001
            print(f"[price_source] {symbol} {name} 실패: {e}")
            continue
        if rows:
            return rows
    return []


def daily_closes(symbol, start=None):
    """[(day, close), ...] — 호환용."""
    return [(r["day"], r["close"]) for r in daily_bars(symbol, start)]


def available():
    """키가 있는 공급자 이름 — 로그 · 진단용 (값은 안 보인다)."""
    return [k for k, f in KEYS.items() if f()]
