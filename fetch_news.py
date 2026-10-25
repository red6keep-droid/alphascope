import datetime
import hashlib
import html as html_mod
import json
import re
import xml.etree.ElementTree as ET

import os

import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments"))

# 두 피드를 합친다 (2026-10-25 사용자): Top News 가 먼저 — Investing 피드만으로는 며칠에 몇 개라 홈에 최대 2주 전 기사가 걸려 있었다
# (10-22 ~ 10-24 2시간 실행 33번 모두 새 기사 0). 합친 뒤 발행 시각 최신 순 12개
RSS_URLS = ["https://www.cnbc.com/id/100003114/device/rss/rss.html",   # Top News
            "https://www.cnbc.com/id/15839069/device/rss/rss.html"]    # Investing
RSS_URL = RSS_URLS[0]   # 옛 이름 — 다른 곳이 읽을 수 있어 남긴다
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
MAX_ITEMS = 12

SECTION_TITLES = {
    "investing", "market insider", "top news", "us top news and analysis",
    "europe markets", "asia markets", "real estate", "commodities",
    "currencies", "bonds", "autos", "retail", "tech",
}


def clean(text):
    if text is None:
        return ""
    text = text.strip()
    if text.startswith("<![CDATA[") and text.endswith("]]>"):
        text = text[9:-3]
    return html_mod.unescape(text).strip()


def strip_tags(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_published(rfc822):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M %Z"):   # CNBC 는 초가 빠진 시각도 섞어 낸다 (2026-10-25 확인)
        try:
            return datetime.datetime.strptime(rfc822.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return rfc822.strip()


STORE_FILE = "news_store_home.json"   # 공용 뉴스 처리 결과 (gh-pages 에 같이 배포 — 다음 실행 · 다른 리포트가 다시 읽는다)
STORE_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/" + STORE_FILE
STORE_DAYS = 8


def _iid(link):
    return hashlib.sha1(link.encode()).hexdigest()[:12]


def process(items):
    """CNBC 기사 → 공용 뉴스 처리(experiments/news_store.py, 2026-10-25 공용 처리 2단계). 처음 본 기사만 AI 로 —
    원제 번역(헤드라인) · 요약 줄(RSS 요약을 재료로) · 종목별 관련도 · 이슈 코드. 홈은 헤드라인 · 요약만 쓴다. 사슬은 Groq 먼저(news).
    옛 자체 번역(translate 사슬: 제목 번역 · 선정 이유 · 소개)은 없앴다 — 선정 이유는 10-24 부터 홈에 보이지 않았다."""
    import news_store
    try:
        store = requests.get(STORE_URL, timeout=20).json()
    except Exception:  # noqa: BLE001 — 첫 실행 · 네트워크: 빈 저장소에서
        store = {}
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STORE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = {k: v for k, v in store.items() if v.get("published_at", "") >= cut}
    for it in items:
        k = _iid(it["link"])
        if k not in store:
            store[k] = {"item_id": k, "title": it["title"], "url": it["link"], "source": it.get("source") or "CNBC",
                        "published_at": it["published"].replace(" ", "T") + "Z", "queries": ["home"]}
        store[k]["snippet"] = it.get("summary", "")   # 요약 줄 재료 — 저장 · 공개하지 않는다 (운영지침 4-2)
    store = news_store.recheck(store)
    store = news_store.classify(store, lambda _: None, None, label="home-news")
    for v in store.values():
        v.pop("snippet", None)
    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)
    for it in items:
        x = store.get(_iid(it["link"])) or {}
        if news_store.headline(x):
            it["title_ko"] = news_store.headline(x)   # 원제 번역 (없으면 사실 문장)
        it["summary_ko"] = news_store.summary(x)
    n = sum(1 for it in items if it.get("title_ko"))
    print(f"[공용 처리] 헤드라인 {n}/{len(items)} · 요약 {sum(1 for it in items if it['summary_ko'])}")


MEDIA_MAX = 3   # 홈 주요 뉴스에 섞는 방송 줄 — 방송 여러 곳이 같이 다룬 시장 · 업종 이슈 (2026-10-25 사용자)


def media_items():
    """미디어 데일리 재료의 시장 · 업종 이슈 → news.json 항목 (kind=media). 홈 스크립트가 `방송` 라벨 · 채널로 그린다.
    제목 = 방송 주제, summary_ko = 방송 주장(뉴스 문체). 키(YTB_FIRESTORE_KEY) · 패키지가 없으면 [] — 기사만 나간다."""
    try:
        import design_kit as dk
        import media_feed
    except Exception as e:  # noqa: BLE001
        print(f"[방송] 모듈 없음 — 건너뜀: {e}")
        return []
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    out = []
    iss = media_feed.issues(media_feed.rows(media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=2)), since)   # 같은 이슈는 한 줄로 정리한 뒤
    for r in media_feed.market_top(iss, MEDIA_MAX):
        try:
            pub = datetime.datetime.fromisoformat(str(r["published_at"]).replace("Z", "+00:00")).astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        out.append({"title": r["topic"], "title_ko": r["topic"], "summary_ko": dk.headline(r["note"]) if r["note"] else "", "source": r["channel"],
                    "link": r["url"], "published": pub, "kind": "media", "tag": r["theme"], "direction": r["direction"], "n_channels": r["n_channels"]})
    print(f"[방송] 시장 이슈 {len(out)}줄")
    return out


def main():
    print(f"[{datetime.datetime.now()}] 뉴스 수집 시작...")
    roots = []
    for url in RSS_URLS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            roots.append(ET.fromstring(resp.content))
        except Exception as e:  # noqa: BLE001 — 한 피드가 실패해도 나머지로
            print(f"[피드] {url} 실패: {str(e)[:80]}")
    if not roots:
        raise RuntimeError("CNBC 피드 전부 실패")

    items = []
    seen = set()
    for item in (it for root in roots for it in root.iter("item")):
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        published = clean(item.findtext("pubDate"))
        summary = strip_tags(clean(item.findtext("description")))

        if not title or not link or "cnbc.com" not in link:
            continue
        if title.lower() in SECTION_TITLES or len(title) < 15:
            continue
        if link in seen:
            continue

        seen.add(link)
        items.append({
            "title": title,
            "source": "CNBC",
            "link": link,
            "published": parse_published(published),
            "summary": summary[:300],
        })

    items.sort(key=lambda it: it["published"], reverse=True)   # 두 피드를 섞어 최신 순
    media = media_items()
    results = items[:MAX_ITEMS - len(media)]
    process(results)
    results = sorted(results + media, key=lambda it: it["published"], reverse=True)   # 방송 줄도 시각 순으로 섞는다
    # 영문 RSS 요약은 번역 입력으로만 쓰고 공개 파일(gh-pages, PUBLIC 저장소 = 배포)에는 남기지 않는다 (2026-10-21, 운영지침 4-2 · D4-2).
    # 홈은 summary_ko(우리 소개 한 줄)만 쓴다
    for it in results:
        it.pop("summary", None)
    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "items": results,
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"news.json 생성 완료! 수집 {len(items)}개 / 저장 {len(results)}개")


if __name__ == "__main__":
    main()
