"""홈 목업 — `증시 전망` 카드가 네 번째로 들어간 홈 (2026-11-06 사용자: 이름 `증시 전망` · 메뉴에 넣기 · 질문마다 페이지).

    python experiments/issue_store/home_mock.py     # output/mock_home_hypo.html

alphaflow-home.html 의 CSS · 헤더를 그대로 가져오고, 카드 구역만 정적으로 그린다(미국 · 한국 · 인물 · 증시 전망 2×2 + 주목할 종목 전폭).
적용할 때 alphaflow-home.html 에 옮길 것: (1) 메뉴 `증시 전망` (2) `#radar-col { grid-column: 1 / -1 }` 삭제 (3) 카드 마크업 · CSS (4) CARDS 항목 + fillHypo. 그 뒤 build_theme.py → index.html → 테마 붙여넣기.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import design_kit as dk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
HOME = os.path.join(ROOT, "alphaflow-home.html")
LIST_URL = "https://alpha-scope.blogspot.com/p/forecast-list.html"

# 홈 카드 전용 CSS — 적용 때 alphaflow-home.html 의 #radar-col 블록 옆에 옮긴다
HYPO_CSS = """
/* ===== 증시 전망 카드 (2026-11-06 사용자, 홈 수정 H34) — 네 번째 카드, 인물 발언과 아래 줄 좌우(2×2 복귀: #radar-col 전폭 규칙 삭제).
   줄 모양 = 인물 발언 카드(= 주요 뉴스 기사 모양, 가이드 10절): 제목 18px 굵게 행간 34 · 라벨 줄(.news-tag + 14px 보조) · 소개 줄(.news-sum 16px). 새 클래스 없음 — 적용 때 #radar-card 선택자에 #hypo-card 를 덧붙인다 */
#radar-col { grid-column: auto; }
#hypo-card { padding: 0 16px; gap: 0; }
#hypo-card .kv-rows { padding: 12px 0 14px; }
#hypo-card .kv-row.plain-row { display: block; padding: 4px 0; border-top: 0; font-size: 18px; line-height: 34px; font-weight: 700; color: #111; word-break: keep-all; }
#hypo-card .kv-row.plain-row + .kv-row.plain-row { border-top: 1px solid #E2E8F0; padding-top: 12px; margin-top: 8px; }
#hypo-card .news-labels { margin-top: 8px; }   /* 홈 뉴스 라벨 줄 그대로 */
.mock-note { max-width: 1100px; margin: 16px auto 8px; padding: 12px 16px; background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 10px; font-size: 13px; line-height: 1.6; color: #7C2D12; }
.mock-note b { color: #9A3412; }
.mock-ph { padding: 14px 0 16px; font-size: 15px; line-height: 24px; color: #94A3B8; }
"""

ICON_SCALE = ('<span class="report-icon" style="background:#7C3AED;" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M8 2v12M4.5 14h7"/><path d="M2.5 5h11"/><path d="M4 5 2 9.5h4L4 5zM12 5l-2 4.5h4L12 5z"/></svg></span>')
ICON_BARS = ('<span class="report-icon" style="background:{bg};" aria-hidden="true"><svg viewBox="0 0 16 16" fill="currentColor"><rect x="2" y="9" width="3" height="5" rx=".5"/>'
             '<rect x="6.5" y="5" width="3" height="9" rx=".5"/><rect x="11" y="2" width="3" height="12" rx=".5"/></svg></span>')
ICON_PERSON = ('<span class="report-icon" style="background:#0F766E;" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
               '<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.6-2.6 2.6-4 5-4s4.4 1.4 5 4"/></svg></span>')
ICON_NOTABLE = ('<span class="report-icon" style="background:#B45309;" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M2 11.5l4-4 3 3 5-6"/><path d="M10.5 4.5H14v3.5"/></svg></span>')


def report_col(icon, name, day, href, inner, col_id=""):
    return (f'<div class="report-col"{f" id={chr(34)}{col_id}{chr(34)}" if col_id else ""}>'
            f'<h3 class="report-title" data-row-link="1" data-href="{href}">{icon}{dk.esc(name)}<span class="report-card-date">{day}</span></h3>'
            f'<a class="report-card"{f" id={chr(34)}{col_id.replace(chr(45)+chr(99)+chr(111)+chr(108), chr(45)+chr(99)+chr(97)+chr(114)+chr(100))}{chr(34)}" if col_id else ""} href="{href}">{inner}</a></div>')   # 카드 id = 칸 id 의 -col → -card (실제 홈과 같게: #radar-col / #radar-card)


def chart_card(src, alt, line):
    return (f'<img class="report-chart" src="{src}" alt="{dk.esc(alt)}"/>'
            f'<div class="report-block"><div class="report-columns"><ul><li><span>{dk.esc(line)}</span></li></ul></div></div>')


def hypo_card(card):
    """줄 = 전망 내용 + 분류 라벨(선거 · 반도체) + 게시일 — 국면 · 문장은 페이지에서 (2026-11-06 사용자)."""
    rows = ""
    for q in card["open"]:
        tags = "".join(f'<span class="news-tag">{dk.esc(t)}</span>' for t in q["tags"])
        rows += (f'<div class="kv-row plain-row" data-row-link="1" data-href="{q["url"]}">{dk.esc(q["title"])}'
                 f'<div class="news-labels">{tags}<span class="news-sub">{q["posted"]} 게시</span></div></div>')
    if not rows:
        rows = '<div class="mock-ph">지금 지켜보는 전망이 없습니다</div>'
    return f'<div class="kv-rows">{rows}</div>'


STATUS_WORD = {"hold": "유보", "support": "지지", "against": "반대"}


def build(card):
    home = open(HOME, encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", home, re.S).group(1)
    nav = re.search(r'<header class="navbar">.*?<div class="header-bar"></div>', home, re.S).group(0)
    nav = nav.replace('<a class="nav-item" href="/search/label/데일리%20브리핑">미국 증시</a>',
                      '<a class="nav-item" href="/search/label/데일리%20브리핑">미국 증시</a>\n      <a class="nav-item" href="/search/label/트럼프%20트렌드">트럼프 트렌드</a>\n'
                      f'      <a class="nav-item" href="{LIST_URL}">증시 전망</a>\n      <a class="nav-item" href="/p/us-market-cap-top10.html">시총 TOP 10</a>')
    nav = nav.replace('href="/"', 'href="#"').replace("aria-current=\"page\"", "aria-current=\"page\"")
    footer = re.search(r"<footer class=\"site-footer\">.*?</footer>", home, re.S).group(0)
    us = chart_card("https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/spx-price-2026-11-06.png", "S&P 500 30거래일 봉차트",
                    "기술주와 반도체 업종을 중심으로 매물이 출회되며 주요 지수가 동반 하락했습니다.")
    kr = chart_card("https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@kr-images/images/kospi-price-2026-11-05.png", "코스피 30거래일 봉차트",
                    "11월 5일 코스피는 5,383.80로 전일보다 −5.28% 움직여 마감했습니다.")
    radar = ('<div class="kv-rows"><div class="kv-row plain-row">지금 홈의 인물 발언 카드 그대로 (발언 세 줄)</div>'
             '<div class="kv-row plain-row">폭만 전폭 → 반폭 — 오른쪽에 증시 전망 카드</div><div class="kv-row plain-row">폰(900px 미만)은 세로 한 줄</div></div>')
    notable = ('<div class="nt-grid"><div class="nt-mkt"><div class="nt-note">지금 홈의 주목할 종목 카드 그대로 (미국)</div></div>'
               '<div class="nt-mkt"><div class="nt-note">(한국)</div></div></div>')
    cards = (report_col(ICON_BARS.format(bg="#E53E3E"), "미국 증시", "11.6", "#", us)
             + report_col(ICON_BARS.format(bg="#1D4ED8"), "한국 증시", "11.5", "#", kr)
             + report_col(ICON_PERSON, "주요 인물 발언", "11.6", "#", radar, col_id="radar-col")
             + report_col(ICON_SCALE, "증시 전망", "11.6", LIST_URL, hypo_card(card), col_id="hypo-col")
             + report_col(ICON_NOTABLE, "주목할 종목", "11.5", "#", notable, col_id="notable-col"))
    note = ('<div class="mock-note"><b>목업 · 2026-11-06 (5판 — 전망 2 반등 추가 · 사전 등록 흐름 샘플. 전망 1 등록일 10.27 은 예시, 실제 첫 등록은 11.06)</b> — 홈에 <b>증시 전망</b> 카드를 네 번째로. 카드 넷이 되어 2×2, 주목할 종목은 전폭. 메뉴에 <b>증시 전망</b>. '
            '줄 = 전망 내용 · 분류 라벨(선거 · 반도체) · 게시일. 국면 · 오늘 문장은 페이지에서. 줄을 누르면 그 전망 페이지(mock_forecast-1 · mock_forecast-2), 제목 줄 · 카드 바탕은 목록(mock_forecast-list). 다른 카드는 자리만.</div>')
    body = (f'{note}{nav}<main class="main-content"><div class="home-cards"><section class="briefing" aria-label="리포트 카드"><div class="briefing-body"><div class="briefing-main">'
            f'{cards}</div></div></section></div></main>{footer}')
    js = ("<script>document.addEventListener('click',function(e){var r=e.target.closest('[data-row-link]');if(!r)return;var a=e.target.closest('a');"
          "if(a&&a!==r&&!r.contains(a))return;var h=r.getAttribute('data-href');if(h&&h!=='#'){e.preventDefault();location.href=h;}});</script>")
    return ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>'
            '<title>목업 · 홈 — 증시 전망 카드</title><link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous"/>'
            '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;900&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet"/>'
            f'<style>{css}{HYPO_CSS}</style></head><body>{body}{js}</body></html>')


if __name__ == "__main__":
    out = os.path.join(_HERE, "output")
    card = json.load(open(os.path.join(out, "hypo.json"), encoding="utf-8"))
    # 목업 안 링크는 같은 폴더의 목업으로
    for q in card["open"]:
        q["url"] = "mock_" + q["url"].rsplit("/", 1)[1]   # p/forecast-2.html → mock_forecast-2.html
    p = os.path.join(out, "mock_home_hypo.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(build(card).replace(LIST_URL, "mock_forecast-list.html"))
    print(p)
