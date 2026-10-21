import json
import datetime
import os
import sys
from zoneinfo import ZoneInfo

import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments"))
import notify  # noqa: E402  — 운영 알림 (experiments/notify.py)
import price_source  # noqa: E402  — yfinance 예비 사슬 (experiments/price_source.py, 2026-10-21)

# 홈 "시총 TOP 10" — 미국 시가총액 상위 10개 (doc/종목-레이더-기획.md 10-10, 2026-10-18 장 마감 기준 순서).
# experiments/stock-radar/universe.py CANDIDATES 앞 10개와 같아야 한다. 교체(11위 밖 5거래일)가 생기면 두 곳을 같이 고친다.
# 2026-10-18: JPM(13위) 빠지고 LLY(10위) 들어옴
TICKERS = [
    "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY"
]

# 홈 화면 상단 "주요 지수" 카드 4개. (yfinance 심볼, 표시 이름)
INDICES = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "나스닥 종합"),
    ("^DJI", "다우존스"),
    ("^RUT", "러셀 2000"),
]

# 홈 "주요 핵심 섹터 현황" — S&P 500 11개 업종 섹터 ETF 의 일일 등락률 (2026-10-12 사용자: 가짜 데이터 삭제 → 실제 값으로)
SECTORS = [
    ("XLK", "기술"), ("XLF", "금융"), ("XLV", "헬스케어"), ("XLY", "경기소비재"), ("XLP", "필수소비재"), ("XLE", "에너지"),
    ("XLI", "산업재"), ("XLB", "소재"), ("XLU", "유틸리티"), ("XLRE", "부동산"), ("XLC", "커뮤니케이션"),
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
        rec = None
        try:
            info = yf.Ticker(symbol).fast_info
            price = num(info.last_price)
            prev = num(info.previous_close)
            if price is not None and prev:
                rec = {"p": price, "prev": prev, "dh": num(info.day_high), "dl": num(info.day_low), "yh": num(info.year_high), "yl": num(info.year_low)}
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")
        if rec is None:
            # yfinance 가 비면 예비 사슬(FRED → Polygon → Twelve Data → Finnhub → Alpha Vantage) — 2026-10-21 price_source
            q = price_source.quote(symbol)
            if q and q.get("prev"):
                rec = {"p": q["price"], "prev": q["prev"], "dh": num(q.get("day_high")), "dl": num(q.get("day_low")), "yh": None, "yl": None}
        if rec is None:
            print(f"{symbol} 시세 없음 — 건너뜀")
            continue
        change = rec["p"] - rec["prev"]
        index_list.append({
            "s": symbol,
            "name": name,
            "p": rec["p"],
            "c": round(change, 2),
            "cp": round(change / rec["prev"] * 100, 2),
            "prev": rec["prev"],
            "dh": rec["dh"],
            "dl": rec["dl"],
            "yh": rec["yh"],
            "yl": rec["yl"],
            "st": status,
        })

    return index_list


def fetch_sectors():
    """섹터 ETF 11개의 현재가 · 전일 대비 등락률. 값이 없는 ETF 는 뺀다."""
    out = []
    for symbol, name in SECTORS:
        price = prev = None
        try:
            info = yf.Ticker(symbol).fast_info
            price, prev = num(info.last_price), num(info.previous_close)
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")
        if price is None or not prev:
            q = price_source.quote(symbol)   # 예비 사슬 (2026-10-21)
            if q and q.get("prev"):
                price, prev = q["price"], q["prev"]
        if price is None or not prev:
            print(f"{symbol} 시세 없음 — 건너뜀")
            continue
        out.append({"s": symbol, "name": name, "p": price, "cp": round((price - prev) / prev * 100, 2)})
    return out


def _market_cap(info):
    try:
        v = info.market_cap
        return int(v) if v else None
    except Exception:  # noqa: BLE001 — 시총을 못 받아도 가격 줄은 낸다
        return None


def fetch_data():
    print(f"[{datetime.datetime.now()}] {len(TICKERS)}개 종목 15분봉 수집 시작...")
    tickers_str = " ".join(TICKERS)
    data = yf.Tickers(tickers_str)

    stock_list = []
    failed = []

    for symbol in TICKERS:
        last_price = prev_close = volume = mcap = None
        candles = []
        try:
            ticker = data.tickers[symbol]
            if ticker is not None:
                info = ticker.fast_info
                last_price, prev_close = info.last_price, info.previous_close
                volume, mcap = int(info.last_volume or 0), _market_cap(info)
                df = ticker.history(period=PERIOD, interval=INTERVAL)
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
        except Exception as e:
            print(f"{symbol} 수집 실패: {e}")

        if not (last_price and prev_close):
            # yfinance 가 비면 예비 사슬(FRED → Polygon → Twelve Data → Finnhub → Alpha Vantage, 키 있는 것만) — 2026-10-21 price_source.
            # 분봉은 Twelve Data 만 준다(Polygon 무료는 종가). 시총은 예비에 없어 None — 홈 정렬은 지난 값 없이 가격 줄만
            q = price_source.quote(symbol)
            if q and q.get("prev"):
                last_price, prev_close, volume = q["price"], q["prev"], q.get("volume") or 0
                candles = price_source.intraday_bars(symbol, INTERVAL) or []
        if not (last_price and prev_close):
            failed.append(symbol)
            continue

        change = last_price - prev_close
        change_pct = (change / prev_close) * 100
        stock_list.append({
            "s": symbol,
            "p": round(float(last_price), 2),
            "c": round(float(change), 2),
            "cp": round(float(change_pct), 2),
            "v": int(volume or 0),
            "mc": mcap,   # 시가총액(달러) — 홈 시총 TOP 10 기본 정렬 (2026-10-18)
            "n": len(candles),
            "candles": candles
        })

    index_list = fetch_indices()
    sector_list = fetch_sectors()

    # yfinance 가 통째로 막힌 날 빈 배열을 배포해 홈의 이전 데이터를 덮어쓰던 구멍 (2026-10-21, 운영지침 D6-2).
    # 한 종류라도 0건이거나 종목이 절반 아래면 data.json 을 쓰지 않고 실패로 끝낸다 — 워크플로가 배포를 건너뛰고 예전 파일이 남는다.
    short = []
    if len(stock_list) < len(TICKERS) / 2:
        short.append(f"종목 {len(stock_list)}/{len(TICKERS)}")
    if not index_list:
        short.append(f"지수 0/{len(INDICES)}")
    if not sector_list:
        short.append(f"섹터 0/{len(SECTORS)}")
    if short:
        notify.now("홈 시세 수집 부족 — data.json 을 쓰지 않음 (yfinance 차단?): " + " · ".join(short))
        sys.exit(1)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "interval": INTERVAL,
        "indices": index_list,
        "stocks": stock_list,
        "sectors": sector_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"data.json 생성 완료! 종목 {len(stock_list)}/{len(TICKERS)}, "
          f"지수 {len(index_list)}/{len(INDICES)}, 섹터 {len(sector_list)}/{len(SECTORS)}")
    for i in index_list:
        print(f"  {i['name']}: {i['p']} ({i['cp']:+.2f}%) {i['st']}")
    for s in stock_list:
        print(f"  {s['s']}: {s['n']}봉 (현재가 {s['p']})")
    if failed:
        print(f"실패 종목: {', '.join(failed)}")


if __name__ == "__main__":
    fetch_data()