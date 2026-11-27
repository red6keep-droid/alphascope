"""한국 종가 확정 기다리기 — 한국 종목 실행(kr-stocks.yml) 맨 앞.

야후 한국 시세는 거래소 규정상 약 20분 늦게 나온다(collect_kr_live.DELAY_MIN). 그래서 실행을 15:50 에 걸고,
여기서 대표 종목 · 지수의 마지막 거래 시각이 오늘 마감 시각(15:30, 수능일 16:30) 이상인지 본다.
  - 됐으면 바로 끝 → 수집 시작 (옛 16:10 시작보다 약 20분 빠름)
  - 아직이면 2분마다 다시, 마감 + 40분(16:10 · 수능일 17:10)까지. 그래도 안 되면 경고만 남기고 넘어간다(옛 16:10 과 같은 시각에 시작)
  - 마지막 거래 날짜가 오늘이 아니면(휴장일) 기다리지 않는다 — 장 열린 날 15:50 이면 지연 시세도 이미 오늘 15:2x~15:30 이다.
    휴장일 게시는 뒤 단계(fresh.txt)가 막는다.
새 수집 아님: 야후 chart 요청 3개 × 최대 11번 = 하루 33회 이하. AI · 쓰기 0.

    python experiments/kr-stocks/wait_close.py            # 정시 실행만 (수동 실행은 워크플로가 건너뛴다)
    python experiments/kr-stocks/wait_close.py --once     # 한 번만 보고 끝 (시험)
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universe_kr import EXAM_DAYS, MARKET_CLOSE  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SYMS = ("005930.KS", "000660.KS", "^KS11")   # 삼성전자 · SK하이닉스 · 코스피
STEP_S = 120
GRACE_MIN = 40   # 마감 + 40분 = 옛 시작 시각(16:10)


def last_trade(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=1d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        meta = json.loads(r.read().decode("utf-8"))["chart"]["result"][0]["meta"]
    return dt.datetime.fromtimestamp(meta["regularMarketTime"], KST)


def close_time(day):
    hh, mm = (16, 30) if day.isoformat() in EXAM_DAYS else map(int, MARKET_CLOSE.split(":"))   # 수능일은 한 시간 늦게 닫는다
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=KST)


def check(close):
    seen = {}
    for s in SYMS:
        try:
            seen[s] = last_trade(s)
        except Exception as e:  # noqa: BLE001 — 받기 실패는 '아직'으로 보고 다시
            seen[s] = None
            print(f"[종가 확인] {s} 못 받음: {str(e)[:80]}", flush=True)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    close = close_time(now.date())
    deadline = close + dt.timedelta(minutes=GRACE_MIN)
    while True:
        seen = check(close)
        line = " · ".join(f"{s} {t:%m-%d %H:%M:%S}" if t else f"{s} 없음" for s, t in seen.items())
        got = [t for t in seen.values() if t]
        if got and all(t >= close for t in got) and len(got) == len(SYMS):
            print(f"[종가 확인] 확정 — {line} (마감 {close:%H:%M}) → 수집 시작 {dt.datetime.now(KST):%H:%M:%S}", flush=True)
            return 0
        if got and all(t.date() < now.date() for t in got):
            print(f"[종가 확인] 오늘 거래 없음(휴장일로 보임) — {line} → 기다리지 않음", flush=True)
            return 0
        if a.once or dt.datetime.now(KST) + dt.timedelta(seconds=STEP_S) > deadline:
            print(f"::warning::[종가 확인] {deadline:%H:%M} 까지 확정 안 됨 — {line} · 그대로 수집 (옛 시작 시각과 같음)", flush=True)
            return 0
        print(f"[종가 확인] 아직 — {line} · {STEP_S // 60}분 뒤 다시", flush=True)
        time.sleep(STEP_S)


if __name__ == "__main__":
    sys.exit(main())
