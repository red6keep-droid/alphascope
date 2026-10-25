"""종목 페이지 기사 수집 (doc/기획/종목-레이더-기획.md 10-4 · 10-8 2단계) — 상세 페이지 `오늘` 탭의 중요 이슈 · 뉴스.

- 수집 : 후보마다 Google News RSS(최근 7일, 영어) 최근 PER_STOCK 건. 같은 제목은 한 건으로 친다(여러 종목에 겹치는 기사).
  엔비디아(REPORT_TYPE)는 모으지 않는다 — 엔비디아 리포트가 따로 수집 · 분류한다 (2026-10-25 사용자).
- 분류 · 검사 : 공용 뉴스 처리 experiments/news_store.py (2026-10-25 여기서 옮김 — 홈 · 데일리도 같은 처리를 쓰게).
결과는 data/news.json (item_id → 기사). 8일이 지난 기사는 지운다.
"""

import datetime
import email.utils
import hashlib
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))

import universe as U  # noqa: E402
import news_store  # noqa: E402  — 공용 뉴스 처리 (분류 · 헤드라인 · 요약 줄 · 검사)
from news_store import EN, fact_problem, detail_style_bad  # noqa: E402,F401  — 옛 이름 (시험 스크립트가 읽는다)

NEWS = os.path.join(BASE, "data", "news.json")
LEAD_CACHE = os.path.join(BASE, "data", "article_cache.json")   # 깃 · 상태 브랜치에 넣지 않는다 (기사 원문 조각)
PER_STOCK = 15
KEEP_DAYS = 8
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _strip(t):
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def _key(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch(sym):
    q = urllib.parse.quote(f'"{EN[sym]}" stock when:7d')
    r = requests.get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title = _strip(it.findtext("title"))
        src = _strip(it.findtext("source"))
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            continue
        out.append({"title": title, "url": it.findtext("link"), "source": src, "published_at": pub, "query": sym})
    out.sort(key=lambda x: x["published_at"], reverse=True)
    return out[:PER_STOCK]


def collect(store):
    now = datetime.datetime.now(datetime.timezone.utc)
    cut = (now - datetime.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = {k: v for k, v in store.items() if v["published_at"] >= cut}
    seen = {_key(v["title"]): k for k, v in store.items()}
    new = 0
    for sym, *_ in U.CANDIDATES:
        if sym in U.REPORT_TYPE:
            continue   # 엔비디아는 엔비디아 리포트가 자기 수집 · 분류로 더 깊게 다룬다 — 여기서 또 모아 분류하지 않는다 (2026-10-25 사용자)
        time.sleep(1)   # 종목당 1회, 사이 1초 — 기획(알파-종목-리포트 341)대로. 49회 연속 요청을 피한다 (2026-10-21)
        try:
            items = fetch(sym)
        except Exception as e:   # noqa: BLE001
            print(f"[news] {sym} 받기 실패 : {e}")
            continue
        for x in items:
            k = _key(x["title"])
            if k in seen:
                store[seen[k]].setdefault("queries", [])
                if sym not in store[seen[k]]["queries"]:
                    store[seen[k]]["queries"].append(sym)
                continue
            iid = hashlib.sha1(k.encode()).hexdigest()[:12]
            store[iid] = dict(x, item_id=iid, queries=[sym])
            seen[k] = iid
            new += 1
    print(f"[news] 새 기사 {new}건 · 보관 {len(store)}건")
    return store


def load():
    try:
        with open(NEWS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(store):
    os.makedirs(os.path.dirname(NEWS), exist_ok=True)
    with open(NEWS, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)


def run():
    store = news_store.recheck(collect(load()))
    save(store)
    store = news_store.classify(store, save, LEAD_CACHE)
    save(store)
    return store


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()
