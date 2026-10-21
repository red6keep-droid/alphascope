import datetime
import html as html_mod
import json
import re
import xml.etree.ElementTree as ET

import os

import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments"))
from llm_chain import LLMPool, gemini_keys, STEPS, CHAINS  # noqa: E402  — 모든 리포트 공용 LLM 사슬 (2026-10-14)

RSS_URL = "https://www.cnbc.com/id/15839069/device/rss/rss.html"
# 이전 결과(gh-pages) — 이미 번역한 제목은 다시 번역하지 않는다
PREV_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news.json"
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


def _translate_prompt(items):
    """items: [{"title", "summary"}] — 제목 번역(t) + 선정 이유(why) 한 문장 (2026-10-14 사용자: 홈 뉴스에 선정 이유)
    + 소개 한 문장(s) (2026-10-19 사용자: 원문이 영어라 기사 내용을 한국어로 조금 — 같은 호출에서 받으므로 AI 호출 수는 그대로)."""
    src = [{"title": it["title"], "summary": it.get("summary", "")} for it in items]
    return (
        "다음은 미국 경제 뉴스(CNBC)의 영문 제목과 요약 목록이다. 항목마다 세 가지를 만들어라.\n"
        "1) t: 제목을 한국 경제지 헤드라인처럼 자연스러운 한국어로. 의미를 더하거나 빼지 말고, 고유명사(기업·인명·지수)는 통용 표기, 숫자·티커는 그대로.\n"
        "2) why: 투자자가 이 기사를 볼 만한 이유 한 문장(40자 안팎, '~다'로 끝냄). 요약에 있는 사실만 쓰고, 매수·매도 권유나 전망 단정은 하지 않는다.\n"
        "3) s: 영문 요약을 옮긴 기사 소개 한 줄(100자 안팎). 뉴스 헤드라인처럼 명사형으로 끝낸다 — '~ 선정' · '~ 전망' · '~ 유입' · '~ 기록'. "
        "'기사는'으로 시작하지 않고, '~다' · '전한다' · '본다' · '밝혔다'로 끝내지 않는다. 누구의 말·판단인지는 주어로 밝힌다(예: '애널리스트가 선정', '연준 위원, 추가 인하 서두를 필요 없다는 입장'). "
        "요약에 있는 내용만 쓰고 새 내용·의견을 더하지 않는다. 숫자·비교(무엇보다 높고 낮은지)·시간 순서는 원문 그대로 옮긴다. "
        "예: 'Analysts picked these 5 stocks to buy in October' → '10월에 살 만한 종목 5개, 애널리스트가 선정' · "
        "'The odds are higher than before X, but lower than after Y' → '확률이 X 전보다 높지만 Y 직후보다는 낮은 수준'. 요약이 비었거나 제목과 같은 내용뿐이면 빈 문자열.\n"
        '결과는 입력과 같은 순서·같은 개수의 JSON 배열 [{"t": "...", "why": "...", "s": "..."}] 로만 답하라.\n\n' + json.dumps(src, ensure_ascii=False)
    )


def _valid_translation(out, items):
    return (isinstance(out, list) and len(out) == len(items)
            and all(isinstance(x, dict) and isinstance(x.get("t"), str) and x["t"].strip() and isinstance(x.get("why"), str) and isinstance(x.get("s", ""), str) for x in out))


def _clean_out(out):
    return [{"t": x["t"].strip(), "why": x["why"].strip(), "s": _intro(x.get("s"))} for x in out]


SUMMARY_STYLE = 2   # 소개 문체 판 — 2: 명사형 "… 애널리스트가 선정" (2026-10-20 사용자: "전한다" 금지). 판이 다른 옛 소개는 다시 만든다


def _intro(s):
    """기사 소개 — 명사형으로 끝나는 한 줄만 싣는다 (2026-10-20 사용자). '기사는 …' 으로 시작하거나 '~다' 로 끝나면 빈 문자열."""
    s = str(s or "").strip().rstrip(".")
    return s if s and not s.startswith("기사는") and not s.endswith("다") and len(s) <= 200 else ""


def translate_titles(titles):
    """뉴스 항목 목록 → [{"t": 한국어 제목, "why": 선정 이유, "s": 소개}] (같은 길이, 2026-10-14 선정 이유 · 2026-10-19 소개 추가). 전부 실패하면 None.

    홈 화면 제목용 (2026-10-10 사용자: 최신 뉴스 제목은 한글로). 기사 본문은 가져오지도 옮기지도 않는다 — 소개(s)는 RSS 요약만 옮긴다.
    공용 사슬 "translate" (experiments/llm_chain.py): Groq gpt-oss-120b → NVIDIA gpt-oss-20b → Gemini(예비). 형식이 어긋나면 다음 단계.
    """
    if not titles:
        return []

    def check(out):
        if not _valid_translation(out, titles):
            raise ValueError("응답 형식 불일치")
        return _clean_out(out)

    try:
        pool = LLMPool("translate", label="번역")
        return pool.generate_json(_translate_prompt(titles), temperature=0.2, validate=check)
    except RuntimeError as e:
        print(f"  [번역] {str(e)[:200]}")
        return None


def previous_translations():
    try:
        j = requests.get(PREV_URL, timeout=20).json()
        return {it["link"]: it for it in j.get("items", []) if it.get("title_ko") and it.get("why_ko") and it.get("link")}
    except Exception:  # noqa: BLE001
        return {}


def add_korean_titles(items):
    prev = previous_translations()
    for it in items:
        if prev.get(it["link"]):
            it["title_ko"] = prev[it["link"]]["title_ko"]
            it["why_ko"] = prev[it["link"]]["why_ko"]
            if "summary_ko" in prev[it["link"]] and prev[it["link"]].get("summary_v") == SUMMARY_STYLE:   # 옛 문체("기사는 … 전한다")는 다시 만든다
                it["summary_ko"] = prev[it["link"]]["summary_ko"]
                it["summary_v"] = SUMMARY_STYLE
    # 선정 이유 · 소개가 없는 옛 번역도 다시 만든다. 소개는 빈 문자열("요약이 제목뿐")도 만든 것으로 친다 — 매번 다시 묻지 않게
    todo = [it for it in items if not (it.get("title_ko") and it.get("why_ko") and "summary_ko" in it)]
    if not todo:
        print(f"[번역] 새 제목 없음 (이전 번역 {len(items)}건 재사용)")
        return
    if not gemini_keys() and not any(os.environ.get(STEPS[st].get("env", ""), "").strip() for st in CHAINS["translate"]):
        print("[번역] 번역 키 없음 (GROQ/NVIDIA/GEMINI) — 영문 제목 유지")
        return
    ko = translate_titles(todo)
    if ko is None:
        print(f"[번역] 실패 — {len(todo)}건 영문 제목 유지 (다음 실행에서 재시도)")
        return
    for it, t in zip(todo, ko):
        it["title_ko"] = t["t"]
        if t["why"]:
            it["why_ko"] = t["why"]
        it["summary_ko"] = t["s"]
        it["summary_v"] = SUMMARY_STYLE
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
