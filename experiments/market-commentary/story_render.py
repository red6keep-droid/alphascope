"""AlphaScope 시황 해설 — 글 화면 그리기 (목업 mock_story.py · 발행기 publish_commentary.py 공용, 2026-11-19 사용자 "목업 확정 → 발행기").

재료 = 수집기 글 columns/{날짜}-{am|pm} (format story, News-doc 23절) + 블로그 묶음 briefing/{날짜}-{am|pm}.json.
모양 = 디자인 가이드라인 14절 `시황 해설`(이 페이지 전용). AI 0 · 네트워크는 종목 페이지 목록(dk.stock_pages)만.

    from story_render import render
    title, html, meta = render(column, briefing, banner_url=…, banner_alt=…)
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "kr-stocks"))
import design_kit as dk  # noqa: E402
import universe_kr as UKR  # noqa: E402  한국 종목 페이지 주소

BLOG = "https://alpha-scope.blogspot.com/"
LABELS = {"am": ["증시 시황", "미국 증시"], "pm": ["증시 시황", "한국 증시"]}   # Blogger 라벨 — `증시 시황` 하나로 아침 · 저녁을 모아 본다
REPORT_LABEL = {"am": ("미국 증시 리포트", "%EB%AF%B8%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"),
                "pm": ("한국 증시 리포트", "%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8")}
FORECAST_URL = f"{BLOG}search/label/%EC%A6%9D%EC%8B%9C%20%EC%A0%84%EB%A7%9D"
# 지수 이름 (가이드라인 5절 `이름 (의미)`) — 묶음 이름 → 화면 이름
INDEX_NAMES = {"S&P 500": "S&P 500 (대형주)", "나스닥 종합": "나스닥 (기술주)", "나스닥": "나스닥 (기술주)", "다우존스": "다우존스 (우량주)",
               "러셀 2000": "러셀 2000 (소형주)", "코스피": "코스피", "코스닥": "코스닥"}

DOWN_W = r"(?:내리|내린|내려|하락|떨어|급락|빠지|빠졌|줄)"
UP_W = r"(?:오르|올랐|오른|상승|급등|뛰|늘)"
NUM = r"\d+(?:\.\d+)?(?:%p|%)"


def chg(v, unit="%"):
    """증감 = 부호 숫자 + 증감 색 + 굵게. 마무리 fix_colons 가 삼각형(글자의 80% · 위로 1 · 숫자와 2)으로 바꾼다 (가이드라인 5절).
    글자 크기 그대로의 ▲ 를 박는 dk.arrow 는 쓰지 않는다 (2026-11-19 사용자 "삼각형 가이드에 맞나")."""
    if not v:
        return f'<span style="font-weight:700;">0.00{unit}</span>'
    col = dk.UP if v > 0 else dk.DOWN
    return f'<span style="color:{col};font-weight:700;white-space:nowrap;">{v:+.2f}{unit}</span>'


def directional(html):
    """수집기 꼴 `2.39% 하락` · `0.05%p 상승` · `각각 1.91%, 1.72% 떨어졌다` → 삼각형 + 증감 색 (가이드라인 5절). `보합`은 그대로(삼각형 없음)."""
    def paint(m, up):
        nums = re.sub(r"(\d+(?:\.\d+)?)(%p|%)", lambda n: chg(float(n.group(1)) * (1 if up else -1), n.group(2)), m.group(1))
        return nums + m.group(2)
    for words, up in ((DOWN_W, False), (UP_W, True)):
        html = re.sub(r"((?:" + NUM + r"(?:,\s*)?)+)(\s*(?:씩\s*)?" + words + ")", lambda m, up=up: paint(m, up), html)
    return html


class Linker:
    """기사 속 종목 링크 — 글 전체에서 처음 나온 이름 하나만 보라 #7C3AED (가이드라인 10절). 페이지가 없는 종목은 글자 그대로."""

    def __init__(self, column, briefing):
        names = {}
        for m in ((briefing or {}).get("close") or {}).get("movers") or []:
            if m.get("name") and m.get("ticker"):
                names[str(m["ticker"]).upper()] = m["name"]
        self.items = []
        for t in dict.fromkeys([str(x).upper() for x in column.get("tickers") or []] + list(names)):
            name, href = names.get(t), None
            if re.fullmatch(r"\d{6}", t):   # 한국 종목 코드
                sym = next((s for s in UKR.BY_SYM if s.split(".")[0] == t), None)
                if sym:
                    name, href = name or UKR.BY_SYM[sym][1], UKR.page_url(sym)
            else:
                href = dk.stock_href(t)
            if name and href:
                self.items.append((t, name, href))
        self.items.sort(key=lambda x: -len(x[1]))   # 긴 이름 먼저 (`SK하이닉스` 안의 `SK` 같은 겹침)
        self.seen = set()

    def __call__(self, html):
        for t, name, href in self.items:
            if t in self.seen or name not in html:
                continue
            html = re.sub(r"(?<![\w])" + re.escape(name),
                          f'<a href="{dk.esc(href)}" data-stock="{dk.esc(t)}" style="color:{dk.STOCK_LINK};font-weight:400;text-decoration:none;">{name}</a>',
                          html, count=1)
            self.seen.add(t)
        return html


def para(html):
    return f'<p style="margin:0 0 14px;padding:0 0 0 {dk.ALIGN_PX}px;word-break:keep-all;">{html}</p>'


def index_row(indices):
    cells, themes = [], []
    for x in indices:
        if x.get("close") is None or x.get("chg_pct") is None:
            continue
        cells.append(f'<span data-idx-cell="1" style="display:block;flex:0 0 auto;min-width:150px;box-sizing:border-box;background:#fff;padding:{14 - dk.VP}px 16px {14 - dk.VP}px 12px;">'
                     f'<span style="display:block;font-weight:700;color:#111;font-size:{dk.NAME};line-height:{dk.LH_CARD};white-space:nowrap;">{dk.paren(dk.esc(INDEX_NAMES.get(x["name"], x["name"])))}</span>'
                     f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{dk.NAME};color:#111;">{x["close"]:,.2f}</span> '
                     f'<span style="font-size:{dk.CHG_SIZE};">{chg(x["chg_pct"])}</span></span></span>')
        themes.append("neutral")
    if not cells:
        return ""
    return (f'<div data-cards="1" style="overflow-x:auto;margin:0 0 16px;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
            f'<span style="display:flex;width:max-content;border-radius:8px;overflow:hidden;">{dk.dir_cells(cells, themes)}</span></div>')


def iconed(sec, icon):
    """구획 제목 앞 기본형 아이콘(회색 원 22 · 글자와 6) — 지수 · 업종 흐름 추세선 · 장을 움직인 변수 기사 · 업종별로 볼 것 막대 · 관전 포인트 과녁 (2026-11-19 사용자)."""
    return re.sub(r"(<h2[^>]*>)", lambda m: m.group(1) + f'<span style="flex:none;display:flex;align-self:center;margin-right:-4px;">{dk.soft_icon(icon)}</span>', sec, count=1)


def points(items, link):
    rows = []
    for p in items:
        when, _, what = p.partition(" — ") if " — " in p else ("", "", p)
        if re.fullmatch(r"\d{1,2}:\d{2}", when.strip()) and "첫 반응" in what:
            when = ""   # 장 시작 줄의 시각은 뺀다 (2026-11-19 사용자 "고정이면 삭제")
        lead = f'<b style="color:#111;">{dk.esc(when)}</b> : ' if when else ""
        rows.append(dk.dot_li(lead + link(directional(dk.tint(dk.esc(what)))), lh=35, margin="12px 0"))
    return f'<ul style="list-style:none;margin:0 0 8px;padding:0 0 0 {dk.ALIGN_PX}px;">{"".join(rows)}</ul>'


def md(iso):
    y, m, d = iso.split("-")
    return int(m), int(d)


def titles(column):
    """(화면 제목 줄, 저장 제목) — `11.17 증시 시황` · `11.17 증시 시황 : 그날 주제` (가이드 14절)."""
    m, d = md(column["date"])
    line = f"{m}.{d:02d} 증시 시황"
    return line, f"{line} : {column['title'].strip()}"


def render(column, briefing, banner_url=None, banner_alt=""):
    """→ (저장 제목, 본문 HTML, meta). 수집기 칸이 비면 그 구획만 뺀다."""
    col, br = column, briefing or {}
    slot = col["slot"]
    close = br.get("close") or {}
    indices = close.get("indices") or []
    link = Linker(col, br)

    def prose(text):
        return link(directional(dk.tint(dk.esc(dk.formal(text or "")))))

    _, stored = titles(col)
    m, d = md(col["date"])
    td = br.get("trade_date") or col["date"]
    tm, tdd = md(td)
    basis = f'{tm}.{tdd:02d} {"미국" if slot == "am" else "한국"} 종가'   # 제목 줄 오른쪽 기준 줄 (테마가 [data-title-basis] 를 옮김)
    body = [f'<p data-title-basis="1" data-commentary="{dk.esc(col["date"])}-{slot}" style="margin:0 0 14px;font-size:13px;line-height:19px;color:#6B7280;">{basis}</p>']
    if banner_url:
        body.append(f'<figure style="margin:0 0 16px;"><img src="{dk.esc(banner_url)}" alt="{dk.esc(banner_alt or "AI 생성 이미지")}" '
                    f'width="900" height="350" style="display:block;width:100%;height:auto;"></figure>')
    body.append(f'<h2 data-headline="1" style="margin:0 0 12px;padding:0 0 0 {dk.ALIGN_PX}px;font-size:22px;line-height:32px;font-weight:700;color:#111;'
                f'word-break:keep-all;">{directional(dk.tint(dk.esc(col["title"])))}</h2>')
    lead_txt = col.get("summary") or ""
    body.append(f'<p data-seo-lead="1" data-lead="1" style="{dk.SEO_LEAD}padding:0 0 0 {dk.ALIGN_PX}px;">'
                f'{m}월 {d}일 {"아침" if slot == "am" else "저녁"}, {link(directional(dk.tint(dk.esc(dk.formal(lead_txt)))))}</p>')

    cp0 = next((x["chg_pct"] for x in indices if x.get("chg_pct") is not None), 0) or 0
    bg = dk.CARD_DIR["positive" if cp0 > 0 else "negative" if cp0 < 0 else "neutral"][0]

    def soft_card(inner, head="", margin="0 0 8px", bg=bg):
        return (f'<div style="background:{bg};border-radius:10px;padding:{18 - dk.VP}px 14px;margin:{margin};">'
                f'{head}<p style="margin:0;word-break:keep-all;">{inner}</p></div>')

    if col.get("overview"):
        head = (f'<h2 style="display:flex;align-items:center;gap:8px;margin:0 0 8px;padding:0;font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;color:#111;">'
                f'{dk.solid_icon("pulse", "#7C3AED")}<span>한눈에 보기</span></h2>')
        body.append(soft_card(prose(col["overview"]), head, "24px 0 8px", dk.CARD_DIR["uncertain"][0]))

    sents = re.split(r"(?<=다\.)\s+", (col.get("market") or "").strip())
    wrap_up = sents.pop() if len(sents) > 1 and re.match(r"(이는|이 같은|이처럼|결국)", sents[-1]) else ""
    mk = index_row(indices) + (para(prose(" ".join(sents))) if " ".join(sents).strip() else "")
    if wrap_up:
        mk += soft_card(prose(wrap_up))
    if mk:
        body.append(iconed(dk.section("지수 · 업종 흐름", mk), "trend"))

    drivers = [x for x in col.get("drivers") or [] if x.get("heading") and x.get("body")]
    if drivers:
        drv = "".join(dk.sub_label(f'{i}. {dk.esc(x["heading"])}') + para(prose(x["body"])) for i, x in enumerate(drivers, 1))
        body.append(iconed(dk.section("장을 움직인 변수", drv), "news"))

    sectors = [s for s in col.get("sectors") or [] if s.get("name") and s.get("chg_pct") is not None]
    if sectors:
        rows = [(f'<b>{dk.esc(s["name"])}</b>', chg(s["chg_pct"]), dk.esc(s.get("check") or "")) for s in sectors]
        body.append(iconed(dk.section("업종별로 볼 것", '<div data-cards="1">' + dk.ccard(rows) + '</div>'), "bars"))

    if col.get("points"):
        body.append(iconed(dk.section(col.get("pointsTitle") or "관전 포인트", points(col["points"], link)), "target"))

    if col.get("oneLine"):
        nb, nd = dk.CARD_DIR["neutral"]
        body.append(f'<div style="background:{nb};border:1px solid {nd};border-radius:10px;padding:{24 - dk.VP}px 14px;margin:8px 0 0;">'
                    f'<div style="font-size:14px;line-height:20px;font-weight:700;color:#6B7280;margin:0 0 6px;">핵심 한 줄</div>'
                    f'<div style="font-size:18px;line-height:30px;font-weight:500;color:#111;word-break:keep-all;">{prose(col["oneLine"])}</div></div>')

    # 글 끝 꼬리말 없음(가이드 2절 8). 함께 보는 페이지 = 공용 블록
    rep_name, rep_q = REPORT_LABEL[slot]
    body.append(dk.related_buttons([(rep_name, f"{BLOG}search/label/{rep_q}"), ("증시 전망", FORECAST_URL)]))
    html = dk.WRAP_OPEN + dk.fix_colons("".join(body)) + dk.WRAP_CLOSE
    return stored, html, {"labels": LABELS[slot], "basis": basis, "linked": sorted(link.seen)}
