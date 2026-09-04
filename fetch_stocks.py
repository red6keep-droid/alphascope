import json
import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "JPM"
]

# 홈 화면 상단 "주요 지수" 카드 4개. (yfinance 심볼, 표시 이름)
INDICES = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "나스닥 종합"),
    ("^DJI", "다우존스"),
    ("^RUT", "러셀 2000"),
]

INTERVAL = "15m"
PERIOD = "1d"

NY = ZoneInfo("America/New_York")


def market_status():
    """미국 정규장 기준 장중/장마감 판정 (ET 평일 09:30~16:00)."""
    now = datetime.datetime.now(NY)
    if now.weekday() >= 5:
        return "장마감"
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return "장중" if open_t <= now < close_t else "장마감"


def num(v, digits=2):
    """fast_info 값을 JSON 에 넣을 수 있는 float 로 정리한다 (없으면 None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return round(f, digits)


def fetch_indices():
    """지수 카드용 시세 + 52주 고저 + 당일 고저를 수집한다."""
    print(f"{len(INDICES)}개 지수 수집 시작...")
    index_list = []
    status = market_status()

    for symbol, name in INDICES:
        try:
            info = yf.Ticker(symbol).fast_info
            price = num(info.last_price)
            prev = num(info.previous_close)
            if price is None or prev is None:
                print(f"{symbol} 시세 없음 — 건너뜀")
                continue

            change = price - prev
            index_list.append({
                "s": symbol,
                "name": name,
                "p": price,
                "c": round(change, 2),
                "cp": round(change / prev * 100, 2),
                "prev": prev,
                "dh": num(info.day_high),
                "dl": num(info.day_low),
                "yh": num(info.year_high),
                "yl": num(info.year_low),
                "st": status,
            })
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")

    return index_list


def fetch_data():
    print(f"[{datetime.datetime.now()}] {len(TICKERS)}개 종목 15분봉 수집 시작...")
    tickers_str = " ".join(TICKERS)
    data = yf.Tickers(tickers_str)

    stock_list = []
    failed = []

    for symbol in TICKERS:
        try:
            ticker = data.tickers[symbol]
            if ticker is None:
                failed.append(symbol)
                continue

            info = ticker.fast_info
            last_price = info.last_price
            prev_close = info.previous_close

            if not (last_price and prev_close):
                failed.append(symbol)
                continue

            change = last_price - prev_close
            change_pct = (change / prev_close) * 100

            df = ticker.history(period=PERIOD, interval=INTERVAL)
            candles = []
            if df is not None and not df.empty:
                for idx, row in df.iterrows():
                    vol = row["Volume"]
                    try:
                        candles.append({
                            "t": int(idx.timestamp()),
                            "o": round(float(row["Open"]), 2),
                            "h": round(float(row["High"]), 2),
                            "l": round(float(row["Low"]), 2),
                            "c": round(float(row["Close"]), 2),
                            "v": int(vol) if (vol == vol and vol is not None) else 0
                        })
                    except (ValueError, TypeError):
                        continue

            stock_list.append({
                "s": symbol,
                "p": round(float(last_price), 2),
                "c": round(float(change), 2),
                "cp": round(float(change_pct), 2),
                "v": int(info.last_volume or 0),
                "n": len(candles),
                "candles": candles
            })
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")
            failed.append(symbol)

    index_list = fetch_indices()

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "interval": INTERVAL,
        "indices": index_list,
        "stocks": stock_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"data.json 생성 완료! 종목 {len(stock_list)}/{len(TICKERS)}, "
          f"지수 {len(index_list)}/{len(INDICES)}")
    for i in index_list:
        print(f"  {i['name']}: {i['p']} ({i['cp']:+.2f}%) {i['st']}")
    for s in stock_list:
        print(f"  {s['s']}: {s['n']}봉 (현재가 {s['p']})")
    if failed:
        print(f"실패 종목: {', '.join(failed)}")


if __name__ == "__main__":
    fetch_data()