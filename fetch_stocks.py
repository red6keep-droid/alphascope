import json
import datetime

import yfinance as yf

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "JPM",
    "LLY", "V", "UNH", "MA", "PG", "HD", "JNJ", "COST", "MRK", "ABBV",
    "ORCL", "BAC", "CVX", "CRM", "AMD", "NFLX", "KO", "PEP", "TSM", "WMT",
    "ACN", "MCD", "CSCO", "ABT", "XOM", "DIS", "INTC", "QCOM", "TXN", "INTU",
    "VZ", "AMGN", "IBM", "PFE", "CMCSA", "NOW", "CAT", "GE", "UBER", "AMAT"
]


def fetch_data():
    print(f"[{datetime.datetime.now()}] {len(TICKERS)}개 종목 수집 시작...")
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

            if last_price and prev_close:
                change = last_price - prev_close
                change_pct = (change / prev_close) * 100
                stock_list.append({
                    "s": symbol,
                    "p": round(float(last_price), 2),
                    "c": round(float(change), 2),
                    "cp": round(float(change_pct), 2),
                    "v": int(info.last_volume or 0)
                })
            else:
                failed.append(symbol)
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")
            failed.append(symbol)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "stocks": stock_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"data.json 생성 완료! 성공 {len(stock_list)} / 전체 {len(TICKERS)}")
    if failed:
        print(f"실패 종목: {', '.join(failed)}")


if __name__ == "__main__":
    fetch_data()
