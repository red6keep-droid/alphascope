"""Yahoo Finance 시장 데이터 수집

- 주요 지수: S&P 500(^GSPC), Nasdaq(^IXIC), Dow(^DJI), Russell 2000(^RUT), VIX(^VIX)
- 급등주 TOP5 / 관심 종목(거래량 상위) TOP5

급등주·관심종목은 Yahoo screener API를 우선 시도하고,
실패하면 정적 유니버스 리스트로 대체 수집한다.
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


def collect_yahoo():
    indices = collect_indices()
    gainers = collect_gainers()
    most_active = collect_most_active()
    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        ),
        "indices": indices,
        "gainers": gainers,
        "most_active": most_active,
    }


if __name__ == "__main__":
    import json

    data = collect_yahoo()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    with open("output_test_yahoo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)