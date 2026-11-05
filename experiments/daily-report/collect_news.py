"""시장 뉴스 수집 (CNBC RSS)

루트의 fetch_news.py 로직을 재사용한다. 후보는 **최근 NEWS_HOURS(48)시간** 기사만 (2026-11-05 사용자 batch 8 ②: CNBC 목록에는 며칠 ~ 2주 지난 기사가
섞여 들어와 요약 줄 · 한글 헤드라인이 비었다 — 공용 처리가 오래된 기사를 AI 에 보내지 않는다). 시차 때문에 24 가 아니라 48 (사용자). 최신이 위.
"""

import datetime
import email.utils
import html as html_mod
import re
import xml.etree.ElementTree as ET

import requests

RSS_URL = "https://www.cnbc.com/id/15839069/device/rss/rss.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
MAX_ITEMS = 40   # 20 → 40: 48시간 안 기사만 남기므로 넉넉히 (데일리 AI 프롬프트에는 처리된 기사만 간다)
NEWS_HOURS = 48
TIMEOUT = 30

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
    return re.sub(r"\s+", " ", text).strip()


def parse_published(rfc822):
    """RSS pubDate → UTC 'YYYY-MM-DD HH:MM:SS' (옛 형식 그대로). 못 읽으면 원문."""
    try:
        dt = email.utils.parsedate_to_datetime(rfc822.strip())
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return rfc822.strip()


def collect_news():
    print(f"[{datetime.datetime.now()}] 뉴스 수집 시작...")
    resp = requests.get(RSS_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    seen = set()
    for item in root.iter("item"):
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

    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=NEWS_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    fresh = [it for it in items if it["published"] >= cut]   # 48시간 밖 기사는 후보에서 뺀다 (batch 8 ②)
    fresh.sort(key=lambda it: it["published"], reverse=True)   # 최신이 위
    results = fresh[:MAX_ITEMS]
    print(f"뉴스 수집 완료: {len(results)}건 (목록 {len(items)}건 중 {NEWS_HOURS}시간 안)")
    return results


HOME_STORE_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news_store_home.json"   # 홈 뉴스(06:45 실행)가 처리해 둔 기사


def process(items):
    """공용 뉴스 처리 (experiments/news_store.py, 2026-10-25 공용 처리 3단계) — 기사마다 headline_ko(원제 번역) · detail_ko(요약 줄) · theme ·
    related(관련도 2 이상 종목) · issue · subtopic · scope · scheduled · surprise. 홈 뉴스가 이미 처리한 기사(같은 CNBC 주소)는 그 결과를 그대로,
    처음 본 기사만 AI 로 (RSS 요약이 요약 줄 재료). 데일리 AI(generate_report)는 어떤 기사를 실을지 고르기만 한다 (2026-10-25 사용자: 특별 케이스 없이).
    실패해도 리포트는 나간다 (영문 원제로)."""
    import hashlib
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    try:
        import news_store
        try:
            store = requests.get(HOME_STORE_URL, timeout=20).json()
        except Exception:  # noqa: BLE001
            store = {}
        mine = {}
        for it in items:
            k = hashlib.sha1(it["link"].encode()).hexdigest()[:12]   # fetch_news._iid 와 같은 열쇠
            mine[k] = dict(store.get(k) or {"item_id": k, "title": it["title"], "url": it["link"], "source": it.get("source") or "CNBC",
                                              "published_at": it["published"].replace(" ", "T") + "Z", "queries": ["daily"]},
                           snippet=it.get("summary", ""))
        mine = news_store.classify(news_store.recheck(mine), lambda _: None, None, label="daily-news", hours=NEWS_HOURS)   # 데일리는 48시간 (batch 8 ②)
        for it in items:
            x = mine.get(hashlib.sha1(it["link"].encode()).hexdigest()[:12]) or {}
            if not x.get("ai_model"):
                continue
            it.update(headline_ko=news_store.headline(x), detail_ko=news_store.summary(x), theme=news_store.theme(x), related=news_store.related(x),
                      issue=x.get("issue"), subtopic=x.get("subtopic"), scope=x.get("scope"), scheduled=x.get("scheduled"), surprise=x.get("surprise"),
                      market_dir=x.get("market_dir"))   # 뉴스 방향 막대 (P143)
        print(f"[공용 처리] 헤드라인 {sum(1 for it in items if it.get('headline_ko'))}/{len(items)} (홈이 처리해 둔 것 {sum(1 for k in mine if k in store)})")
        done = [it for it in items if it.get("headline_ko")]
        if len(done) >= 3:   # 처리 안 된 기사(영문 원제 · 요약 없음)는 후보에서 뺀다 — AI 가 거의 다 막힌 날만 그대로 (batch 8 ②)
            dropped = len(items) - len(done)
            if dropped:
                print(f"[공용 처리] 미처리 {dropped}건은 후보에서 뺌")
            items = done
    except Exception as e:  # noqa: BLE001
        print(f"::warning::공용 뉴스 처리 실패 — 데일리 AI 제목으로: {str(e)[:120]}")
    return items


if __name__ == "__main__":
    collect_news()