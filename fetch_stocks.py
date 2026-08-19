import json
import datetime

import yfinance as yf

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "JPM"
]

INTERVAL = "15m"
PERIOD = "1d"


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

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "interval": INTERVAL,
        "stocks": stock_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"data.json 생성 완료! 성공 {len(stock_list)} / 전체 {len(TICKERS)}")
    for s in stock_list:
        print(f"  {s['s']}: {s['n']}봉 (현재가 {s['p']})")
    if failed:
        print(f"실패 종목: {', '.join(failed)}")


if __name__ == "__main__":
    fetch_data()