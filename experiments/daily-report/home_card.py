"""홈 카드 재료 JSON — 글 게시 직후 카드가 쓸 구획만 뽑아 gh-pages cards/<카드>.json 으로 (H31, 2026-11-05).

왜: 홈 리포트 카드 4개(데일리 · 한국 증시 · 트럼프 · 인물 발언)는 방문자 브라우저가 라벨 피드 + 글 페이지 HTML(각 600KB)을
받아 몇 줄만 뽑아 썼다. 이 모듈이 게시 시점에 같은 규칙으로 구획을 뽑아 2~20KB JSON 으로 두면 홈은 JSON 만 읽는다.
글 전문은 싣지 않는다(짧은 피드 H29 · 공개 브랜치 규칙 D4-2). 기획: alphascope-docs/doc/기획/홈-카드-JSON-전환-기획.md

규칙은 alphaflow-home.html 의 reportSections · fillChart 를 그대로 옮긴 것이다 — 홈 JS 쪽 linesOf · trumpRows · radarRows ·
fillPicks 는 JSON 의 구획 HTML 을 DOMParser 로 다시 요소로 만들어 전과 같은 코드로 그린다. 그래서 여기서는 "어느 구획을
어떤 이름으로" 만 맞추면 된다. 홈 JS 의 CARDS 가 바뀌면 아래 CARDS 의 sections 도 같이 고친다.

사용:
    python experiments/daily-report/home_card.py --card kr-report \
        --body experiments/kr-market-report/output/report_body.html \
        --meta experiments/kr-market-report/output/post_meta.json \
        --out deploy-home/cards/kr-report.json
    meta = {"title": "...", "url": "https://alpha-scope.blogspot.com/...", "day": "YYYY-MM-DD"(선택)}
    --page <글 페이지 HTML> 를 주면 .post-body 안쪽만 본문으로 쓴다 (로컬 검증용)
"""
import argparse
import copy
import datetime
import html
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Comment, Tag

KST = ZoneInfo("Asia/Seoul")

# 카드별로 홈 JS 가 읽는 구획 이름 (alphaflow-home.html CARDS 의 map 값 + picks(PICKS_HEADS) + fill 이 읽는 구획)
CARDS = {
    "report": {"id": "report-card", "label": "데일리 브리핑", "chart": True,
               "sections": ["(머리)", "오늘 한 줄", "급등주", "오늘의 급등주 TOP 5"]},
    "kr-report": {"id": "kr-report-card", "label": "한국 증시 리포트", "chart": True,
                  "sections": ["(요약)"]},
    "radar": {"id": "radar-card", "label": "인물 발언", "chart": False,
              "sections": ["(머리)", "발언"]},
}


def _ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _direct_text(tag):
    """요소 자식을 뺀 제목 글자만 — JS: clone 뒤 children 제거 후 textContent.trim()"""
    return "".join(s for s in tag.contents if isinstance(s, str) and not isinstance(s, Comment)).strip()


def section_key(title):
    """앞의 ①②… 번호와 뒤의 "(…)" 를 뗀 이름 — JS sectionKey"""
    return re.sub(r"\s*\([^)]*\)\s*$", "", re.sub(r"^[①-⑳\s]+", "", title or "")).strip()


def _following(tag):
    """다음 h2 전까지의 형제 요소 — JS nextElementSibling 반복"""
    out, n = [], tag.find_next_sibling()
    while n is not None and n.name != "h2":
        out.append(n)
        n = n.find_next_sibling()
    return out


def report_sections(soup):
    """JS reportSections(html) 와 같은 구획 사전 {이름: [요소…]}"""
    out = {}
    for h in soup.find_all("h2"):
        nodes = _following(h)
        title = _direct_text(h)
        out[title] = nodes
        key = section_key(title)
        if key and key not in out:
            out[key] = nodes
    lead = soup.select_one("[data-lead]") or soup.select_one("[data-cards]")
    q = lead
    while q is not None:   # 첫 h2 뒤에 오는 data-cards 는 머리가 아니다
        if q.name == "h2":
            lead = None
            break
        q = q.find_previous_sibling()
    if lead is not None:
        ln = [lead] + _following(lead)
        out["(가격)"] = ln
        out["(머리)"] = ln
    ins = soup.select_one("[data-insight]")
    if ins is not None:
        out["(종합)"] = [ins]
    seo = soup.select_one("[data-seo-lead]")
    if seo is not None:
        st = _ws(seo.get_text())
        se = st.find("다. ")
        p = BeautifulSoup("<p></p>", "html.parser").p
        p.string = st[: se + 2] if se > 0 else st
        out["(요약)"] = [p]
    return out


def prune_radar(nodes):
    """인물 발언 '발언' 구획은 9명 × 발언 전부(약 75KB)라 홈 JS radarRows 가 읽는 것만 남긴다(약 3KB) —
    인물 컨테이너(data-person-page) · 소제목(data-sub, 이름 (직함)) · 인물마다 첫 li 의 첫 칸(헤드라인 <a>, 숨은 이름 span 포함) + "강도 N".
    style · href 는 radarRows 가 안 쓴다 → 뗀다. 원본은 건드리지 않는다(복사본)."""
    out = []
    for n in nodes:
        if not isinstance(n, Tag):
            continue
        c = copy.copy(n)
        # 인물 컨테이너 안에는 소제목(data-sub)과 첫 목록(ul)만 — "더 보기" 접기(details, 같은 인물이라 radarRows 가 건너뜀) · 신뢰 기록 상자는 뗀다
        persons = ([c] if c.has_attr("data-person-page") else []) + c.find_all(attrs={"data-person-page": True})
        for person in persons:
            sub = person.find(attrs={"data-sub": True})
            ul = person.find(["ul", "ol"])
            for child in list(person.children):
                if isinstance(child, Tag):
                    if child is not sub and child is not ul:
                        child.decompose()
                else:
                    child.extract()
        for ul in c.find_all(["ul", "ol"]):
            lis = ul.find_all("li", recursive=False)
            for li in lis[1:]:
                li.decompose()
            if lis:
                li = lis[0]
                m = re.search(r"강도\s*(\d+)", li.get_text())
                first = next((x for x in li.contents if isinstance(x, Tag)), None)
                li.clear()
                if first is not None:
                    li.append(first)
                if m:
                    s = BeautifulSoup("<span></span>", "html.parser").span
                    s.string = "강도 " + m.group(1)
                    li.append(s)
        for t in [c] + c.find_all(True):
            for attr in ("style", "href", "target", "rel", "title"):
                t.attrs.pop(attr, None)
        out.append(c)
    return out


def chart_of(soup):
    """본문 맨 위 그래프 — JS fillChart: a[data-zoom] img, a[aria-label="그래프 확대 보기"] img"""
    im = soup.select_one("a[data-zoom] img") or soup.select_one('a[aria-label="그래프 확대 보기"] img')
    if im is None or not im.get("src"):
        return None
    return {"src": im["src"], "alt": im.get("alt") or "S&P 500 그래프"}


def date_of(title, body_text, day=None):
    """카드 날짜 2026.11.4 — JS 와 같은 순서: 제목의 "YYYY년 M월 D일" → 본문 첫 1200자의 "M월 D일 기준" → 게시일(KST)"""
    m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", title or "")
    if m:
        return f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))}"
    m = re.search(r"(\d{1,2})월\s*(\d{1,2})일\s*기준", body_text[:1200])
    if m:
        return f"{datetime.datetime.now(KST).year}.{int(m.group(1))}.{int(m.group(2))}"
    d = datetime.date.fromisoformat(day) if day else datetime.datetime.now(KST).date()
    return f"{d.year}.{d.month}.{d.day}"


def post_body_of_page(page_html):
    """글 페이지 HTML → .post-body 안쪽 (로컬 검증용 — 홈 JS postBody 와 같은 선택자)"""
    soup = BeautifulSoup(page_html, "html.parser")
    b = soup.select_one(".post-outer-container .post-body") or soup.select_one(".post-body")
    return b.decode_contents() if b is not None else ""


def build(card, body_html, title, url, day=None):
    spec = CARDS[card]
    soup = BeautifulSoup(body_html, "html.parser")
    sec = report_sections(soup)
    sections = {}
    for name in spec["sections"]:
        if name in sec:
            nodes = prune_radar(sec[name]) if (card == "radar" and name == "발언") else sec[name]
            sections[name] = "".join(str(n) for n in nodes if isinstance(n, Tag))
    body_text = _ws(soup.get_text(" "))
    return {
        "id": spec["id"],
        "label": spec["label"],
        "title": title,
        "url": url,
        "date": date_of(title, body_text, day),
        "generated": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "chart": chart_of(soup) if spec["chart"] else None,
        "sections": sections,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="홈 카드 재료 JSON")
    ap.add_argument("--card", required=True, choices=sorted(CARDS))
    ap.add_argument("--body", help="글 본문 HTML (게시한 그 파일)")
    ap.add_argument("--page", help="글 페이지 HTML — .post-body 안쪽을 본문으로 (검증용)")
    ap.add_argument("--meta", help='{"title","url","day"} JSON')
    ap.add_argument("--title")
    ap.add_argument("--url")
    ap.add_argument("--day")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not a.body and not a.page:
        ap.error("--body 또는 --page")
    meta = {}
    if a.meta:
        with open(a.meta, encoding="utf-8") as f:
            meta = json.load(f)
    title, url, day = a.title or meta.get("title"), a.url or meta.get("url"), a.day or meta.get("day")
    if not title or not url:
        print(f"[cards] {a.card}: 제목 · 주소 없음 — 쓰지 않는다 (게시 안 된 날)")
        return 2
    if a.page:
        with open(a.page, encoding="utf-8") as f:
            body = post_body_of_page(f.read())
    else:
        with open(a.body, encoding="utf-8") as f:
            body = f.read()
    if not body.strip():
        print(f"[cards] {a.card}: 본문 비어 있음 — 쓰지 않는다")
        return 2
    data = build(a.card, body, title, url, day)
    if not data["sections"]:
        print(f"[cards] {a.card}: 구획을 하나도 못 찾음 — 쓰지 않는다 (홈은 피드로 돈다)")
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    size = os.path.getsize(a.out)
    print(f"[cards] {a.card}: {a.out} {size:,}B · 날짜 {data['date']} · 구획 {list(data['sections'])} · 그래프 {'있음' if data['chart'] else '없음'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
