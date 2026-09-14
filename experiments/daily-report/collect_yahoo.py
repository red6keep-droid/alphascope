"""Yahoo Finance 시장 데이터 수집

- 주요 지수: S&P 500(^GSPC), Nasdaq(^IXIC), Dow(^DJI), Russell 2000(^RUT), VIX(^VIX)
- 급등주 TOP5 / 관심 종목(거래량 상위) TOP5
- 분석용 시계열: 지수 + 광의 시장 ETF + 섹터 ETF + 금리·안전자산, 6개월 일봉 종가

급등주·관심종목은 Yahoo screener API를 우선 시도하고,
실패하면 정적 유니버스 리스트로 대체 수집한다.

시계열은 analyze.py 전용이다. 지수의 당일 가격·등락률은 여전히 fast_info에서
받는다 — 게시되는 표의 숫자 소스를 바꾸지 않기 위해서다.
"""

import datetime
import os

import requests
import yfinance as yf

INDICES = {
    "sp500": {"symbol": "^GSPC", "name": "S&P 500"},
    "nasdaq": {"symbol": "^IXIC", "name": "Nasdaq"},
    "dow": {"symbol": "^DJI", "name": "Dow Jones"},
    "russell": {"symbol": "^RUT", "name": "Russell 2000"},
    "vix": {"symbol": "^VIX", "name": "VIX"},
}

# analyze.py가 1D/5D/20D · 이동평균 · 연속성 · 상대강도를 계산하는 유니버스.
# 그룹은 analyze.py의 규칙이 참조하므로 심볼을 옮기면 그쪽도 같이 본다.
HISTORY_UNIVERSE = {
    "indices": ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
    "broad": ["SPY", "QQQ", "IWM", "RSP"],
    "sectors": ["XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLU", "XLI", "XLB", "XLRE", "XLC"],
    "theme": ["SMH"],
    "safe": ["TLT", "HYG", "GLD"],
    "rates": ["^TNX", "^FVX", "^IRX"],
}
# 50일선과 그 기울기까지 보려면 3개월(약 63거래일)은 빠듯하다.
HISTORY_PERIOD = "6mo"
# 심볼마다 마지막 행 날짜가 다를 수 있다(^VIX는 다음 날 부분 바가 먼저 붙는다).
# 이 심볼의 마지막 종가 날짜를 기준일로 삼아 모든 시계열을 거기까지로 자른다.
HISTORY_ANCHOR = "^GSPC"

SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
TARGET_COUNT = 10
TOP_N = 5

MIN_PRICE = 1.0
MIN_VOLUME = 1_000_000

FALLBACK_UNIVERSE = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "NFLX",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "WMT", "COST", "TGT", "XOM", "CVX",
    "V", "MA", "UNH", "JNJ", "PFE", "MRK", "ABBV", "LLY", "CRM", "ORCL",
    "AMD", "MU", "INTC", "QCOM", "TXN", "CSCO", "ADBE", "ACN", "PEP", "PG",
    "KO", "MCD", "DIS", "HD", "NKE", "SBUX", "BA", "GE", "CAT", "DE",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def _ticker_info(symbol):
    t = yf.Ticker(symbol)
    info = t.fast_info
    last = info.last_price
    prev = info.previous_close
    if not (last and prev):
        return None
    change_pct = (last - prev) / prev * 100
    return {
        "symbol": symbol,
        "price": round(float(last), 2),
        "change_pct": round(float(change_pct), 2),
        "volume": int(info.last_volume or 0),
    }


def collect_indices():
    symbols_str = " ".join(v["symbol"] for v in INDICES.values())
    tickers = yf.Tickers(symbols_str)

    result = {}
    for key, meta in INDICES.items():
        try:
            rec = _ticker_info(meta["symbol"])
        except Exception as e:
            print(f"{meta['symbol']} 지수 수집 실패: {e}")
            rec = None
        result[key] = {"name": meta["name"], "symbol": meta["symbol"], **(
            rec or {
                "price": None,
                "change_pct": None,
                "volume": 0,
            }
        )}
    print(f"지수 수집 완료: {len([v for v in result.values() if v['price']])}/{len(result)}")
    return result


def _screener_quotes(scr_ids):
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://fc.yahoo.com", timeout=10)
    except requests.RequestException:
        pass

    params = {"scrIds": scr_ids, "count": TARGET_COUNT}
    resp = session.get(SCREENER_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
    if not quotes:
        raise RuntimeError(f"screener '{scr_ids}' 결과 없음")
    return quotes


def _normalize_quotes(quotes, symbol_key, price_key, change_key, volume_key):
    out = []
    for q in quotes:
        price = q.get(price_key)
        volume = q.get(volume_key)
        if price is None or volume is None:
            continue
        symbol = q.get(symbol_key)
        if not symbol:
            continue
        if float(price) < MIN_PRICE or int(volume) < MIN_VOLUME:
            continue
        change = q.get(change_key, 0.0) or 0.0
        out.append({
            "symbol": symbol,
            "price": round(float(price), 2),
            "change_pct": round(float(change), 2),
            "volume": int(volume),
        })
    return out


def _fallback_quotes():
    df = yf.download(FALLBACK_UNIVERSE, period="2d", interval="1d",
                     group_by="ticker", auto_adjust=True, threads=True,
                     progress=False)
    if df is None or df.empty:
        return []

    out = []
    for symbol in FALLBACK_UNIVERSE:
        try:
            close = df[symbol]["Close"].dropna()
            vol = df[symbol]["Volume"].dropna()
            if len(close) < 2 or len(vol) == 0:
                continue
            prev_close = float(close.iloc[-2])
            last_price = float(close.iloc[-1])
            volume = int(vol.iloc[-1])
            if prev_close <= 0 or last_price < MIN_PRICE or volume < MIN_VOLUME:
                continue
            change_pct = (last_price - prev_close) / prev_close * 100
            out.append({
                "symbol": symbol,
                "price": round(last_price, 2),
                "change_pct": round(change_pct, 2),
                "volume": volume,
            })
        except Exception:
            continue
    return out


def _quotes_from_screener(scr_ids):
    raw = _screener_quotes(scr_ids)
    return _normalize_quotes(
        raw,
        symbol_key="symbol",
        price_key="regularMarketPrice",
        change_key="regularMarketChangePercent",
        volume_key="regularMarketVolume",
    )


def collect_gainers(session_candidates=True):
    quotes = []
    if session_candidates:
        try:
            quotes = _quotes_from_screener("day_gainers")
        except Exception as e:
            print(f"Yahoo screener(day_gainers) 실패 → fallback: {e}")
            quotes = []

    if not quotes:
        quotes = _fallback_quotes()

    quotes.sort(key=lambda r: r["change_pct"], reverse=True)
    result = quotes[:TOP_N]
    print(f"급등주 수집 완료: {len(result)}개")
    return result


def collect_most_active(session_candidates=True):
    quotes = []
    if session_candidates:
        try:
            quotes = _quotes_from_screener("most_actives")
        except Exception as e:
            print(f"Yahoo screener(most_actives) 실패 → fallback: {e}")
            quotes = []

    if not quotes:
        quotes = _fallback_quotes()

    quotes.sort(key=lambda r: r["volume"], reverse=True)
    result = quotes[:TOP_N]
    print(f"관심 종목(거래량 상위) 수집 완료: {len(result)}개")
    return result


def collect_history():
    """유니버스 전체의 일봉 종가를 받아 기준일까지로 정렬해 돌려준다.

    반환: {"as_of", "period", "groups", "series": {symbol: {"dates": [...], "close": [...]}}}
    기준일(anchor)의 종가가 없으면 None — 호출자가 분석을 건너뛴다.
    """
    symbols = [s for group in HISTORY_UNIVERSE.values() for s in group]
    df = yf.download(symbols, period=HISTORY_PERIOD, interval="1d",
                     group_by="ticker", auto_adjust=True, threads=True,
                     progress=False)
    if df is None or df.empty:
        print("시계열 수집 실패: 빈 응답")
        return None

    def closes(symbol):
        try:
            s = df[symbol]["Close"].dropna()
        except Exception:
            return None
        return s if len(s) else None

    anchor = closes(HISTORY_ANCHOR)
    if anchor is None:
        print(f"시계열 수집 실패: 기준 심볼 {HISTORY_ANCHOR} 없음")
        return None
    as_of = anchor.index[-1]

    series = {}
    missing = []
    for symbol in symbols:
        s = closes(symbol)
        if s is None:
            missing.append(symbol)
            continue
        s = s[s.index <= as_of]
        series[symbol] = {
            "dates": [d.strftime("%Y-%m-%d") for d in s.index],
            "close": [round(float(v), 4) for v in s.values],
        }
    if missing:
        print(f"시계열 결측 심볼: {missing}")
    print(f"시계열 수집 완료: {len(series)}/{len(symbols)} 심볼, 기준일 {as_of.date()}")
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "period": HISTORY_PERIOD,
        "groups": HISTORY_UNIVERSE,
        "series": series,
    }


def collect_yahoo():
    indices = collect_indices()
    gainers = collect_gainers()
    most_active = collect_most_active()
    # 시계열은 그림자 모드 분석용이라 실패해도 리포트를 막지 않는다.
    try:
        history = collect_history()
    except Exception as e:
        print(f"시계열 수집 실패 (분석 건너뜀): {e}")
        history = None
    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        ),
        "indices": indices,
        "gainers": gainers,
        "most_active": most_active,
        "history": history,
    }


if __name__ == "__main__":
    import json

    data = collect_yahoo()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    with open("output_test_yahoo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)