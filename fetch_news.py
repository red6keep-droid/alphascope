import datetime
import html as html_mod
import json
import re
import xml.etree.ElementTree as ET

import os

import requests

RSS_URL = "https://www.cnbc.com/id/15839069/device/rss/rss.html"
# 이전 결과(gh-pages) — 이미 번역한 제목은 다시 번역하지 않는다
PREV_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news.json"
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
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
    try:
        dt = datetime.datetime.strptime(rfc822.strip(), "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return rfc822.strip()


def gemini_keys():
    raw = os.environ.get("GEMINI_API_KEY", "")
    return [k.strip().strip('"') for k in re.split(r"[;,]", raw) if k.strip()]


def translate_titles(titles):
    """영문 제목 목록 → 한국어 제목 목록 (같은 길이). 키를 돌아가며 시도, 전부 실패하면 None.

    홈 화면 제목용 (2026-10-10 사용자: 최신 뉴스 제목은 한글로). 본문·요약은 번역하지 않는다.
    """
    if not titles:
        return []
    prompt = (
        "다음은 미국 경제 뉴스(CNBC)의 영문 제목 목록이다. 각 제목을 한국 경제지 헤드라인처럼 자연스러운 한국어로 옮겨라. "
        "의미를 더하거나 빼지 말고, 고유명사(기업·인명·지수)는 통용 표기를 쓰며, 숫자·티커는 그대로 둔다. "
        "결과는 입력과 같은 순서·같은 개수의 JSON 문자열 배열로만 답하라.\n\n" + json.dumps(titles, ensure_ascii=False)
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    for key in gemini_keys():
        try:
            r = requests.post(GEMINI_URL.format(model=GEMINI_MODEL, key=key), json=body, timeout=60)
            if r.status_code in (429, 503, 500):
                print(f"  [번역] {r.status_code} — 다음 키")
                continue
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(text)
            if isinstance(out, list) and len(out) == len(titles) and all(isinstance(x, str) and x.strip() for x in out):
                return [x.strip() for x in out]
            print("  [번역] 응답 형식 불일치 — 다음 키")
        except Exception as e:  # noqa: BLE001
            print(f"  [번역] 실패: {str(e)[:100]} — 다음 키")
    return None


def previous_translations():
    try:
        j = requests.get(PREV_URL, timeout=20).json()
        return {it["link"]: it["title_ko"] for it in j.get("items", []) if it.get("title_ko") and it.get("link")}
    except Exception:  # noqa: BLE001
        return {}


def add_korean_titles(items):
    prev = previous_translations()
    for it in items:
        if prev.get(it["link"]):
            it["title_ko"] = prev[it["link"]]
    todo = [it for it in items if not it.get("title_ko")]
    if not todo:
        print(f"[번역] 새 제목 없음 (이전 번역 {len(items)}건 재사용)")
        return
    if not gemini_keys():
        print("[번역] GEMINI_API_KEY 없음 — 영문 제목 유지")
        return
    ko = translate_titles([it["title"] for it in todo])
    if ko is None:
        print(f"[번역] 실패 — {len(todo)}건 영문 제목 유지 (다음 실행에서 재시도)")
        return
    for it, t in zip(todo, ko):
        it["title_ko"] = t
    print(f"[번역] 새 제목 {len(todo)}건 번역 · 재사용 {len(items) - len(todo)}건")


def main():
    print(f"[{datetime.datetime.now()}] 뉴스 수집 시작...")
    resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
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
    add_korean_titles(results)
    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "items": results,
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"news.json 생성 완료! 수집 {len(items)}개 / 저장 {len(results)}개")


if __name__ == "__main__":
    main()
