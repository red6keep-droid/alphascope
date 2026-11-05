"""한국 종목 장중 지연 시세 → output/home/live.json (홈 카드 `장중 가격` 토글 재료, 2026-11-05 사용자).

    python experiments/kr-stocks/collect_kr_live.py

- 한국 장중(09:00~15:30 KST, 수능일은 16:30) 10분마다 kr-live.yml 이 돌린다. 종목은 universe_kr.CANDIDATES 전부(35) — 홈 카드 어디서든 빠지는 종목이 없게.
- yfinance 일봉 한 번(종목을 묶어 요청 1회): 장중에는 오늘 봉의 종가 칸이 "지금 가격"(거래소 규정상 약 20분 지연), 전일 대비는 전날 봉 종가 기준.
  장 마감 뒤에는 그 값이 그날 종가와 같아진다 → 홈은 session 이 closed 면 "종가" 로 표시한다.
- 오늘(KST) 봉이 없으면(휴장일 · 자료 지연) 파일을 쓰지 않고 0 으로 끝난다 — 워크플로는 파일이 있을 때만 배포한다.
- stocks.json · kr.json 과 분리한 작은 파일 — 자주 바뀌는 값이 하루 1회 파일의 퍼지 타이밍 사고(11-05 빈 칸)와 섞이지 않게. 홈 카드 신호 · 의견은 전날 종가 기준 그대로, 가격 · 등락률 · 거래량만 이 파일로 바꾼다.
- 야후 약관 위험은 일일 수집과 같은 성격(운영지침 D4-7). 증권사 API 는 공개 사이트 용도로 쓰지 않는다. TradingView 숫자를 옮기지 않는다.
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe_kr as U  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "home", "live.json")
DELAY_MIN = 20   # 거래소 규정상 야후 한국 시세 지연 — 표시용


def session(now):
    """open · closed — 정규장 안인가. 수능일은 마감 16:30."""
    day = now.strftime("%Y-%m-%d")
    close = "16:30" if day in U.EXAM_DAYS else U.MARKET_CLOSE
    hhmm = now.strftime("%H:%M")
    return "open" if U.MARKET_OPEN <= hhmm < close else "closed"


def fetch(syms):
    df = yf.download(syms, period="5d", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=False)
    out = {}
    for sym in syms:
        try:
            t = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
            t = t.dropna(subset=["Close"])
        except KeyError:
            continue
        if len(t) < 2:
            continue
        last, prev = t.iloc[-1], t.iloc[-2]
        out[sym] = {"day": t.index[-1].strftime("%Y-%m-%d"), "p": float(last["Close"]), "prev": float(prev["Close"]),
                    "v": int(last["Volume"]) if pd.notna(last.get("Volume")) else None}
    return out


def build(now=None):
    now = now or dt.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    syms = [c[0] for c in U.CANDIDATES]
    bars = fetch(syms)
    rows = {}
    for sym, b in bars.items():
        if b["day"] != today:   # 오늘 봉이 아니면(휴장일 · 지연) 그 종목은 뺀다
            continue
        code = sym.split(".")[0]
        rows[code] = {"p": round(b["p"]), "cp": round((b["p"] / b["prev"] - 1) * 100, 2) if b["prev"] else None, "v": b["v"]}
    if not rows:
        return None
    return {"updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "day": today, "at": now.strftime("%H:%M"), "session": session(now), "delay_min": DELAY_MIN,
            "currency": "KRW", "source": "yfinance", "stocks": rows}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = build()
    if not data:
        print("[kr-live] 오늘 봉 없음(휴장일 또는 지연) — 파일을 쓰지 않는다")
        sys.exit(0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[kr-live] {data['day']} {data['at']} KST · {data['session']} · {len(data['stocks'])}/{len(U.CANDIDATES)}종목 → {OUT}")
