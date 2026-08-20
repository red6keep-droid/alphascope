"""시장 뉴스 수집 (CNBC RSS)

루트의 fetch_news.py 로직을 재사용하되, Gemini가 3~5개를 선정할 수 있도록
더 많은 후보(20건)를 수집한다.
"""

import datetime
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
MAX_ITEMS = 20
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
    try:
        dt = datetime.datetime.strptime(rfc822.strip(), "%a, %d %b %Y %H:%M:%S %Z")
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

    results = items[:MAX_ITEMS]
    print(f"뉴스 수집 완료: {len(results)}건")
    return results


if __name__ == "__main__":
    collect_news()