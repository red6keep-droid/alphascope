"""과거 참고치 — 인물 × 주제의 "그런 날 하루" 시장 움직임 (기획 8절, 2026-10-25 축소안).

예측이 아니라 참고치다: "과거에 이런 발언이 있던 날 S&P 500 은 보통 얼마나 움직였나"를 아무 날과 나란히 둔다.
플라시보 검정 · 두 기간 지속 확인은 "검증해" 단계 — 여기는 중앙값 · 오른 날 비율만 (단순 비교라고 화면에 밝힌다).

둘만 만든다 (기획 8절: CEO 발언 × 가격은 접음, 5 · 20일 창도 접음):
  trump × Trade : 1기(2017-01-20 ~ 2021-01-08) 트윗 중 'tariff' 가 든 날 — 공개 아카이브 사본(GitHub MarkHershey/CompleteTrumpTweetsArchive, X 계정 · API 없음)
                  시각은 트윗 ID(스노플레이크)에서 UTC 를 다시 계산 → 미국 동부 16:00 전이면 그날, 뒤면 다음 거래일
  fed × Fed     : FOMC 정기 결정일 (data/store/calendar/fomc.csv, fetch_fomc.py) — 1994~
가격: data/store/bars/SPY.parquet (30년 일봉, 로컬). 없으면 만들지 않는다 (CI 는 ref/reaction_refs.json 을 그대로 쓴다).

    .venv/bin/python experiments/people-radar/reaction_refs.py   → ref/reaction_refs.json
"""

import csv
import datetime
import json
import os
import sys
import urllib.request
import zoneinfo

import config

ROOT = os.path.abspath(os.path.join(config.BASE_DIR, "..", ".."))
BARS = os.path.join(ROOT, "data", "store", "bars", "SPY.parquet")
FOMC = os.path.join(ROOT, "data", "store", "calendar", "fomc.csv")
TWEETS_URL = "https://raw.githubusercontent.com/MarkHershey/CompleteTrumpTweetsArchive/master/data/realDonaldTrump_in_office.csv"
TWEETS_PATH = os.path.join(config.DATA_DIR, "trump_tweets_in_office.csv")
OUT = os.path.join(config.BASE_DIR, "ref", "reaction_refs.json")
ET = zoneinfo.ZoneInfo("America/New_York")
SNOWFLAKE_EPOCH_MS = 1288834974657


def _bars():
    import pandas as pd
    df = pd.read_parquet(BARS)
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")   # 날짜 문자열 인덱스 — 캘린더 · 트윗 날짜와 그대로 비교
    df["ret"] = df["close"] / df["close"].shift(1) - 1
    return df.dropna(subset=["ret"])


def _stats(df, days):
    sub = df.loc[df.index.isin(list(days))]
    base = df
    return {"n": int(len(sub)), "med_abs": round(float(sub["ret"].abs().median()) * 100, 2),
            "base_abs": round(float(base["ret"].abs().median()) * 100, 2),
            "up_pct": round(float((sub["ret"] > 0).mean()) * 100), "base_up": round(float((base["ret"] > 0).mean()) * 100)}


def _tweet_days(df):
    if not os.path.exists(TWEETS_PATH):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        req = urllib.request.Request(TWEETS_URL, headers={"User-Agent": config.BROWSER_USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as r, open(TWEETS_PATH, "wb") as f:
            f.write(r.read())
    csv.field_size_limit(10 ** 7)
    trading = df.index
    days = set()
    with open(TWEETS_PATH, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].strip() == "ID" or "tariff" not in row[3].lower():
                continue
            tid = int(row[2].strip().rsplit("/", 1)[1])
            utc = datetime.datetime.fromtimestamp(((tid >> 22) + SNOWFLAKE_EPOCH_MS) / 1000, datetime.timezone.utc)
            et = utc.astimezone(ET)
            d = et.date() if et.hour < 16 else et.date() + datetime.timedelta(days=1)
            nxt = trading[trading >= str(d)]
            if len(nxt):
                days.add(nxt[0])
    return days


def _fomc_days(df):
    days = set()
    with open(FOMC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["scheduled"] == "True" and r["decision"] and r["day"] in df.index:
                days.add(r["day"])
    return days


def build():
    if not (os.path.exists(BARS) and os.path.exists(FOMC)):
        print("[refs] 30년 일봉 · FOMC 표 없음 — 만들지 않는다")
        return None
    df = _bars()
    first_term = df.loc["2017-01-20":"2021-01-08"]
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": "S&P 500",
        "trump": {"Trade": dict(_stats(first_term, _tweet_days(first_term)),
                                label="관세 발언이 있던 날", period="2017~2020년 트윗", base_label="그 기간 아무 날")},
        "fed": {"Fed": dict(_stats(df.loc["1994-01-01":], _fomc_days(df)),
                            label="FOMC 금리 결정일", period="1994년부터", base_label="아무 날")},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for sp, d in out.items():
        if isinstance(d, dict):
            for t, v in d.items():
                print(f"[refs] {sp} × {t}: {v['n']}일 · 보통 ±{v['med_abs']}% (아무 날 ±{v['base_abs']}%) · 오른 날 {v['up_pct']}% (아무 날 {v['base_up']}%)")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
