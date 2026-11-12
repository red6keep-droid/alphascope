"""목업 보기 서버 — 태블릿·휴대폰에서 즐겨찾기 하나로 모든 목업을 연다 (2026-10-31 사용자).

    python experiments/mock_server.py          # 포트 8800 고정
    python experiments/mock_server.py 8801     # 포트 바꾸기

- `/` 인덱스는 열 때마다 experiments/*/output/*.html 을 새로 읽는다 — 목업이 늘거나 바뀌어도 새로고침만 하면 된다.
- 주소가 바뀌지 않게 포트를 고정하고, IP 대신 맥 이름(.local) 주소도 함께 찍는다.
- 같은 와이파이에 열리므로 output 폴더 밖(.env 등)은 내주지 않는다.
- 즐겨찾기(☆ 누르기)는 맨 위에 (2026-11-01 사용자). 기록은 맥의 experiments/.mock_prefs.json 하나 — 태블릿 · 맥이 같은 목록을 본다.
- 2026-11-07 사용자: 이름으로 찾기 · 자주 연 목업 삭제, 종목 목업은 `한국 종목` · `미국 종목` 대신 종목 이름(삼성전자 · 애플)을 보인다.
- 2026-11-12 사용자: ① 쓰지 않는 목업은 지우지 않고 `/archive` 한 곳에 묶는다(목록 · 최근 · 묶음에서 빠짐, 되돌리기 버튼). 기록 = .mock_prefs.json "archive".
  ② 사용자 여정 테스트 `/j/…` — 같은 목업 파일을 보내면서 하단 고정 메뉴(홈 · 미국 증시 · 한국 증시 · 종목 · 인물)를 붙이고,
  블로그 주소 링크(종목 페이지 · 리포트 · 인물 발언 · 증시 전망)를 다른 목업으로 이어 준다. 목업 파일은 건드리지 않는다(보낼 때만) — 목업을 다시 그리면 여정도 최신.
"""
import html
import re
import json
import threading
import os
import socket
import subprocess
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8800

# 폴더 이름 → 인덱스에 보일 이름. 없는 폴더는 폴더 이름 그대로.
LABELS = {
    "kr-stocks": "한국 종목",
    "kr-market-report": "한국 증시 리포트",
    "stock-radar": "미국 종목",
    "nvda-report": "엔비디아 리포트",
    "daily-report": "데일리 리포트",
    "trump-trend": "트럼프 트렌드",
    "people-radar": "주요 인물 발언",
    "theme-monitor": "테마",
    "media-daily": "미디어 데일리",
    "competitiveness": "국가 경쟁력",
    "home-split": "홈 나누기",   # 미국 화면 · 한국 화면 (2026-11-10 사용자, H35)
    "issue_store": "증시 전망",   # 사건 가설 질문 페이지 · 목록 · 홈 카드 목업 (2026-11-06)
    "site-search": "검색 · 질문하기",   # 헤더 검색 아이콘 · 즉답 카드 · 질문하기 (2026-11-10 사용자)
    "post-footer": "글 아래 버튼 줄",   # 💬 댓글 · 홈으로 · TOP 한 줄, 함께 보는 페이지는 그 아래 (2026-11-10 사용자)
    "stock-title": "종목 제목 줄",   # 제목 꼬리 13/19 · 공유 버튼 = 회색 기준 상자 오른쪽 (2026-11-11 사용자)
}
RECENT_N = 12
STOCK_DIRS = ("kr-stocks", "stock-radar")   # 폴더 이름 대신 종목 이름을 보이는 폴더 (2026-11-07 사용자)
PREFS = os.path.join(BASE, ".mock_prefs.json")   # {"star": ["폴더/파일"]} — output 밖이라 서버가 내주지 않는다
_lock = threading.Lock()


# 쓰지 않는 목업 첫 목록 (2026-11-12 Claude 판단 — 지금 블로그 기준). 한 번 prefs 에 적힌 뒤로는 prefs 가 기준(되돌리기 가능)
ARCHIVE_SEED = [
    "issue_store/mock_forecast-list-auto.html", "issue_store/mock_forecast-list-auto-2026-11-10.html",   # 11-11 자동 등록 일회 시험
    "issue_store/mock_forecast-2026-003.html", "issue_store/mock_forecast-2026-004.html",
    "issue_store/mock_kr_forecast-2026-001.html", "issue_store/mock_kr_forecast-2026-002.html",           # 11-12 한국 등록 일회 시험
    "people-radar/radar.html", "people-radar/radar_body.html",                                           # 게시용 본문 사본 (목업 = radar_mock)
    "home-preview/home_preview.html",                                                                    # 옛 홈 디자인 미리보기 (지금 = 홈 나누기)
    "post-footer/mock_post_footer.html", "stock-title/mock_stock_title_us.html", "stock-title/mock_stock_title_kr.html",   # 블로그에 반영 끝난 디자인 시안
    "competitiveness/mock_themes.html",                                                                  # 발행 안 한 기획 시안
]


def load_prefs():
    try:
        with open(PREFS, encoding="utf-8") as fh:
            p = json.load(fh)
    except (OSError, ValueError):
        p = {}
    return {"star": p.get("star", []), "archive": p.get("archive", list(ARCHIVE_SEED))}


def save_prefs(p):
    with open(PREFS + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(p, fh, ensure_ascii=False)
    os.replace(PREFS + ".tmp", PREFS)


_themed = {}   # 경로 → (수정 시각, 테마 있음, 종목 이름)
_TITLE = re.compile(r"<title>([^<]*?) 주가", re.I)


def themed(path, mtime):
    """블로그 테마(스타일)를 입힌 미리보기인가. 게시용 본문(X.html · *_body.html)은 스타일이 없어
    날것으로 보이므로 목록에서 뺀다 — 주소로는 그대로 열린다. 이름 규칙이 리포트마다 달라 내용으로 가른다."""
    hit = _themed.get(path)
    if not hit or hit[0] != mtime:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        s = raw.lower()
        m = _TITLE.search(raw)   # `애플 AAPL 주가 …` → 애플 · `삼성전자 주가 …` → 삼성전자
        nm = re.sub(r"\s+[A-Z][A-Z0-9.\-]*$", "", m.group(1).strip()) if m else ""
        hit = _themed[path] = (mtime, "<style" in s or 'rel="stylesheet"' in s, html.unescape(nm))
    return hit[1]


def stock_name(d, f):
    """종목 목업이면 제목의 종목 이름, 아니면 빈 문자열."""
    if d not in STOCK_DIRS:
        return ""
    hit = _themed.get(os.path.join(BASE, d, "output", f))
    return hit[2] if hit else ""


def mockups():
    """[(폴더, 파일 이름, 수정 시각)] — 최근 수정 순."""
    out = []
    for d in sorted(os.listdir(BASE)):
        od = os.path.join(BASE, d, "output")
        if not os.path.isdir(od):
            continue
        for f in os.listdir(od):
            p = os.path.join(od, f)
            if d in STOCK_DIRS and not f.startswith("mock_"):   # 게시용 본문(AAPL.html)은 목업이 아니다 — mock_AAPL 과 같은 내용, 주소로는 열린다 (2026-11-07 사용자)
                continue
            if f.endswith(".html") and themed(p, t := os.path.getmtime(p)):
                out.append((d, f, t))
    return sorted(out, key=lambda x: -x[2])


def row(d, f, t, show_dir=False, stars=(), restore=False):
    href = f"/{quote(d)}/output/{quote(f)}"
    when = datetime.fromtimestamp(t).strftime("%m-%d %H:%M")
    nm = stock_name(d, f)
    label = nm or (LABELS.get(d, d) if show_dir else "")
    sub = f"{label} · {when}" if label else when
    name = html.escape(f[:-5])
    key = html.escape(f"{d}/{f}")
    on = f"{d}/{f}" in stars
    if restore:   # 쓰지 않는 목업 화면 — 별 대신 되돌리기
        return (f'<div class="row"><a class="go" href="{href}">'
                f'<span class="name">{name}</span><span class="sub">{html.escape(sub)}</span></a>'
                f'<button class="back" data-k="{key}" aria-label="목록으로 되돌리기">되돌리기</button></div>')
    return (f'<div class="row"><a class="go" href="{href}">'
            f'<span class="name">{name}</span><span class="sub">{html.escape(sub)}</span></a>'
            f'<button class="star{" on" if on else ""}" data-k="{key}" aria-label="즐겨찾기">{"★" if on else "☆"}</button></div>')


JOURNEY_START = "/j/home-split/output/mock_home_kr.html"


def index_page(archive=False):
    items = mockups()
    with _lock:
        prefs = load_prefs()
    stars = prefs["star"]
    arch = set(prefs["archive"])
    old = [x for x in items if f"{x[0]}/{x[1]}" in arch]
    items = old if archive else [x for x in items if f"{x[0]}/{x[1]}" not in arch]
    by_key = {f"{d}/{f}": (d, f, t) for d, f, t in items}
    groups = {}
    for d, f, t in items:
        groups.setdefault(d, []).append((d, f, t))
    parts = []
    if archive:
        parts.append('<a class="big" href="/">← 목업 목록으로</a>')
        for d in sorted(groups, key=lambda k: -groups[k][0][2]):
            parts += [f'<section><h2>{html.escape(LABELS.get(d, d))}</h2>', *(row(*x, restore=True) for x in groups[d]), "</section>"]
        if not items:
            parts.append('<div class="meta">쓰지 않는 목업이 없습니다</div>')
    else:
        parts.append(f'<a class="big dark" href="{JOURNEY_START}">사용자 여정 테스트 <span>홈에서 시작 · 상단 · 하단 메뉴로 이동 ›</span></a>')
        parts.append('<a class="big" href="/icons">하단 메뉴 아이콘 비교 <span>스타일 8가지 ›</span></a>')
        fav = [by_key[k] for k in stars if k in by_key]   # 누른 순서대로
        if fav:
            parts += ['<section><h2>★ 즐겨찾기</h2>', *(row(*x, show_dir=True, stars=stars) for x in fav), "</section>"]
        parts += ['<section><h2>최근 바뀐 목업</h2>', *(row(*x, show_dir=True, stars=stars) for x in items[:RECENT_N]), "</section>"]
        for d in sorted(groups, key=lambda k: -groups[k][0][2]):   # 최근에 손댄 폴더가 위
            parts.append(f'<details><summary>{html.escape(LABELS.get(d, d))} <span class="n">{len(groups[d])}</span></summary>')
            parts += [row(*x, stars=stars) for x in groups[d]]
            parts.append("</details>")
        if old:
            parts.append(f'<a class="big" href="/archive">쓰지 않는 목업 <span>{len(old)}개 ›</span></a>')
    now = datetime.now().strftime("%m-%d %H:%M:%S")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>목업 목록</title>
<style>
body{{margin:0;padding:16px;font:16px/1.4 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#f6f7f9;color:#1d2127}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#8a919c;font-size:13px;margin-bottom:16px}}
h2{{font-size:15px;color:#5b6370;margin:0 0 8px}} section{{margin-bottom:20px}}
details{{background:#fff;border:1px solid #e3e6eb;border-radius:10px;margin-bottom:10px}}
summary{{padding:14px;font-weight:600;cursor:pointer}} .n{{color:#8a919c;font-weight:400;font-size:14px}}
details .row{{border:0;border-top:1px solid #eef0f3;border-radius:0;margin:0}}
.row{{display:flex;align-items:stretch;min-height:48px;background:#fff;border:1px solid #e3e6eb;border-radius:10px;margin-bottom:8px}}
.go{{flex:1 1 auto;min-width:0;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 4px 10px 14px;color:inherit;text-decoration:none}}
.go:active{{background:#eef2f8}} .name{{word-break:break-all}} .sub{{color:#8a919c;font-size:13px;white-space:nowrap}}
.star{{flex:0 0 48px;border:0;background:none;font-size:22px;color:#c3c8d0;cursor:pointer;padding:0}} .star.on{{color:#f5a623}}
.back{{flex:0 0 auto;border:0;background:none;font-size:13px;color:#5b6370;cursor:pointer;padding:0 14px}}
.big{{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:48px;padding:0 14px;margin:0 0 16px;background:#fff;border:1px solid #e3e6eb;border-radius:10px;color:inherit;text-decoration:none;font-weight:600}}
.big span{{color:#8a919c;font-weight:400;font-size:13px}} .big.dark{{background:#1d2127;border-color:#1d2127;color:#fff}} .big.dark span{{color:#c3c8d0}}
</style></head><body>
<h1>{"쓰지 않는 목업" if archive else "목업 목록"}</h1><div class="meta">{len(items)}개 · 불러온 시각 {now} · 새로고침하면 최신 목록</div>
{''.join(parts)}
<script>
const ds = [...document.querySelectorAll('details')];
document.querySelectorAll('.back').forEach(b => b.addEventListener('click', async () => {{
  await fetch('/archive?k=' + encodeURIComponent(b.dataset.k), {{method: 'POST'}}); location.reload();
}}));
// ☆ 누르면 즐겨찾기 넣기 · 빼기 → 목록을 다시 받아 맨 위 즐겨찾기에 반영
document.querySelectorAll('.star').forEach(b => b.addEventListener('click', async () => {{
  await fetch('/star?k=' + encodeURIComponent(b.dataset.k), {{method: 'POST'}});
  try {{ sessionStorage.setItem('mockIndex', JSON.stringify({{
    open: ds.filter(d => d.open).map(d => d.querySelector('summary').textContent), y: scrollY }})); }} catch (e) {{}}
  location.reload();
}}));
// 목업에서 '목록으로' 눌러 돌아오면 펼친 접기 · 스크롤을 그대로 (같은 창 전환)
try {{
  const s = JSON.parse(sessionStorage.getItem('mockIndex') || 'null');
  if (s) {{ ds.forEach((d, i) => d.open = s.open.includes(d.querySelector('summary').textContent));
           scrollTo(0, s.y); }}
}} catch (e) {{}}
addEventListener('pagehide', () => {{
  try {{ sessionStorage.setItem('mockIndex', JSON.stringify({{
    open: ds.filter(d => d.open).map(d => d.querySelector('summary').textContent), y: scrollY }})); }} catch (e) {{}}
}});
</script></body></html>"""

# 목업 맨 아래에 끼워 넣는 '목록으로' 버튼 — 목업 파일은 건드리지 않고 보낼 때만 붙인다.
BACK_BAR = ('<div style="padding:24px 16px 40px;text-align:center;background:#f6f7f9;border-top:1px solid #e3e6eb">'
            '<a href="/" style="display:inline-block;min-width:200px;padding:14px 24px;border-radius:10px;background:#1d2127;'
            'color:#fff;font:600 16px/1.2 -apple-system,\'Apple SD Gothic Neo\',sans-serif;text-decoration:none">← 목업 목록으로</a></div>')


# ---------------------------------------------------------------- 사용자 여정 테스트 (2026-11-12 사용자)
# 독자 여정: 홈 → 한국 증시 → 종목 → 인물 발언 → 증시 전망 … 을 목업끼리 눌러서 다닌다.
# 시험하는 것 (2차, 같은 날 사용자): ① 하단 고정 메뉴 5칸 = 홈 · 증시 리포트 · 종목 · 증시 전망 · 인물 발언 — 홈 · 리포트 · 종목은 지금 보는 나라(미국 · 한국)를 따라간다
#   ② 상단 전체 메뉴(서랍) — 주요 메뉴 전체 + 하위 칸(오늘 · 지난 리포트). 목업 껍데기(dk.write_mock)엔 헤더가 없어 여기서 붙인다
#   ③ 글 끝 = 최신 테마 순서(댓글 · TOP 버튼 줄 → 함께 보는 페이지 → 푸터)에서 검은 `목록` 버튼만 뺀 모양 — `지난 리포트`는 서랍 메뉴 하위 칸으로
J = "/j/"
J_PAGES = {
    "home_kr": "home-split/output/mock_home_kr.html", "home_us": "home-split/output/mock_home_us.html",
    "us": "daily-report/output/daily_mock.html", "kr": "kr-market-report/output/kr_report_mock.html",
    "list_us": "stock-radar/output/mock_list.html", "list_kr": "kr-stocks/output/mock_list.html",
    "people": "people-radar/output/radar_mock.html", "forecast": "issue_store/output/mock_forecast-list.html",
    "media": "media-daily/output/media_mock.html",
    "th_ai": "theme-monitor/output/mock_theme-ai-capex.html", "th_fed": "theme-monitor/output/mock_theme-fed-rate-cut-expectations.html",
    "th_ins": "theme-monitor/output/mock_theme-insider-trading.html",
}
_ICON = {   # 22px 선 아이콘 (viewBox 24, 선 1.8)
    "home": '<path d="M4 11l8-7 8 7"/><path d="M6 10v10h12V10"/>',
    "report": '<path d="M4 19h16"/><path d="M6 16l4-5 3 3 5-7"/>',
    "stock": '<path d="M9 7h11M9 12h11M9 17h11"/><path d="M4.5 7h.01M4.5 12h.01M4.5 17h.01"/>',   # 목록 모양 — 돋보기는 검색으로 읽힌다
    "forecast": '<path d="M12 3v18M7.5 21h9"/><path d="M4 7h16"/><path d="M6 7l-3 7h6zM18 7l-3 7h6z"/>',   # 저울 — 홈 · 증시 전망 질문 줄과 같은 그림 (2026-11-12 사용자)
    "people": '<circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
}
# 하단 메뉴 아이콘 스타일 비교 (2026-11-12 사용자: 여러 스타일을 그려 보고 고른다). 선 = 테두리만, 면 = 채운 모양
_FILL = {
    "home": '<path d="M3.2 10.6 12 3l8.8 7.6V20a1 1 0 0 1-1 1H15v-6.2H9V21H4.2a1 1 0 0 1-1-1z"/>',
    "report": '<path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M6.5 15.5l3.5-4 3 2.5 4.5-6" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "stock": '<rect x="3" y="4.5" width="18" height="4" rx="1.5"/><rect x="3" y="10" width="18" height="4" rx="1.5"/><rect x="3" y="15.5" width="18" height="4" rx="1.5"/>',
    "forecast": '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 4.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11z"/><circle cx="12" cy="12" r="2.6"/>',
    "people": '<circle cx="12" cy="7.5" r="4.5"/><path d="M3.5 21c.8-5 4.2-8 8.5-8s7.7 3 8.5 8z"/>',
}
ICON_STYLES = [   # (키, 이름, 설명)
    ("A", "가는 선", "지금 목업 — 선 1.8, 지금 칸은 검정 굵은 글자"),
    ("B", "굵은 선", "선 2.2 — 작은 화면에서 더 또렷 (정함)"),
    ("C", "채운 모양", "모든 칸을 채운 아이콘, 지금 칸만 검정"),
    ("D", "지금 칸만 채움", "다른 칸은 선, 지금 칸만 채운 모양 (앱에서 흔한 방식)"),
    ("E", "둥근 바탕", "지금 칸 아이콘 뒤에 옅은 둥근 바탕"),
    ("F", "글자만", "아이콘 없이 글자, 지금 칸 아래 짧은 막대"),
    ("G", "컬러 네모", "홈 카드 제목 앞과 같은 색 네모 + 흰 그림, 모든 칸 컬러 · 홈 = Alpha Scope 로고(신호 카드와 같음)"),
    ("H", "지금 칸만 컬러", "다른 칸은 같은 그림을 회색으로, 지금 칸만 색 네모"),
]
# 컬러 아이콘 = 홈 카드 제목 앞 .report-icon 과 같은 그림 · 색 (index.html, 2026-11-12 사용자: 강조 카드 컬러 아이콘도 비교에). 그림 viewBox 16
_HOME_GLYPH = {
    "report": ("fill", "<rect x='2' y='9' width='3' height='5' rx='.5'/><rect x='6.5' y='5' width='3' height='9' rx='.5'/><rect x='11' y='2' width='3' height='12' rx='.5'/>"),
    "stock": ("fill", "<rect x='2' y='8' width='3' height='6' rx='.5'/><rect x='6.5' y='3' width='3' height='11' rx='.5'/><rect x='11' y='10' width='3' height='4' rx='.5'/>"),
    "forecast": ("line", "<path d='M8 2v12M4.5 14h7'/><path d='M2.5 5h11'/><path d='M4 5 2 9.5h4L4 5zM12 5l-2 4.5h4L12 5z'/>"),
    "people": ("line", "<circle cx='8' cy='5.5' r='2.5'/><path d='M3 13.5c.6-2.6 2.6-4 5-4s4.4 1.4 5 4'/>"),
}
_HOME_COLOR = {"report_us": "#E53E3E", "report_kr": "#1D4ED8", "stock": "#6D28D9", "forecast": "#7C3AED", "people": "#0F766E"}   # 홈 카드 색 그대로 (미국 증시 · 한국 증시 · 시총 TOP 10 · 증시 전망 · 주요 인물 발언)
_LOGO_MARK = "<path d='M313 134L164.968 286H35L189.03 134H313Z' fill='{r}'/><path d='M164.519 0H287L128.954 147H0L164.519 0Z' fill='{k}'/>"


def _color_icon(key, on, all_color, mkt="kr"):
    """G · H 스타일 아이콘 — 24 칸 안. 색 칸 = 6 둥근 네모 + 흰 16 그림, 회색 칸 = 같은 그림 회색."""
    box = "class=\"ji jc\" style=\"display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:6px;{bg}\""
    if key == "home":   # 홈 = 블로그 로고 (Alpha Scope 신호 카드 제목 앞과 같은 그림)
        col = all_color or on
        r, k = ("#DD0000", "#000000") if col else ("#9CA3AF", "#9CA3AF")
        return f'<span class="ji" style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;"><svg viewBox="0 0 313 286" width="22" height="20" aria-hidden="true">{_LOGO_MARK.format(r=r, k=k)}</svg></span>'
    kind, g = _HOME_GLYPH[key]
    colored = all_color or on
    color = _HOME_COLOR.get(f"{key}_{mkt}") or _HOME_COLOR[key]
    attrs = "fill='currentColor'" if kind == "fill" else "fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'"
    bg = f"background:{color};color:#fff;" if colored else "color:#6B7280;"
    return f'<span {box.format(bg=bg)} aria-hidden="true"><svg viewBox="0 0 16 16" width="16" height="16" {attrs}>{g}</svg></span>'

JTABS = [("home", "홈"), ("report", "증시 리포트"), ("stock", "종목"), ("forecast", "증시 전망"), ("people", "인물 발언")]
BAR_PAD = 10   # 하단 메뉴 아래 여백 — 화면 맨 아래에서 10px 위로 (2026-11-12 사용자)
BAR_H = 56


# 종목 · 인물 아이콘 시안 (2026-11-12 사용자: B 스타일로, 종목 · 인물은 여러 시안). viewBox 24 선 그림. 0 = 지금 것
STOCK_V = [
    ("목록 (지금)", _ICON["stock"]),
    ("캔들 차트", '<path d="M7 3v18M17 3v18"/><rect x="4.5" y="7" width="5" height="8" rx="1"/><rect x="14.5" y="5" width="5" height="10" rx="1"/>'),
    ("세로 막대", '<path d="M4 20h16"/><path d="M7.5 16v-5M12 16V6M16.5 16v-8"/>'),
    ("네 칸 타일", '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>'),
    ("건물 (회사)", '<path d="M5 20V4.5h9V20M14 9h5v11M3 20h18"/><path d="M8 8h3M8 12h3M8 16h3"/>'),
    ("파이 차트", '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5V12h8.5"/>'),
    ("가방 (포트폴리오)", '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5h6v2M3 12.5h18"/>'),
]
PEOPLE_V = [
    ("사람 (지금)", _ICON["people"]),
    ("사람 + 말풍선", '<circle cx="9" cy="9" r="3.5"/><path d="M2.5 20.5c.6-3.6 3.1-5.6 6.5-5.6s5.9 2 6.5 5.6"/><path d="M15 3.5h6.5v5h-3.2L16 10.5v-2h-1z"/>'),
    ("말풍선", '<path d="M4 4.5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-8.5L6 20.5v-4H4a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M8 10.5h.01M12 10.5h.01M16 10.5h.01"/>'),
    ("마이크", '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>'),
    ("확성기", '<path d="M3.5 10v4h3.5l7.5 4.5v-13L7 10z"/><path d="M17.5 9a4.2 4.2 0 0 1 0 6M19.8 6.5a7.5 7.5 0 0 1 0 11"/>'),
    ("두 사람", '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.1-5.6 6.5-5.6s5.9 2 6.5 5.6"/><path d="M15.5 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c1.9.8 3.1 2.6 3.5 5.2"/>'),
    ("따옴표", '<path d="M10 6.5H6.5a2 2 0 0 0-2 2V12H10z"/><path d="M10 12c0 3.2-1.6 4.8-4.5 5.5"/><path d="M19.5 6.5H16a2 2 0 0 0-2 2V12h5.5z"/><path d="M19.5 12c0 3.2-1.6 4.8-4.5 5.5"/>'),
]


ON_STYLES = [   # 선택한 칸 표시 시안 (2026-11-12 사용자: 선택됐을 때 시안도 보고 싶다). 모두 회색 → 검정 색은 같고 그 위에 더하는 것만 다르다
    ("1", "색만 진하게", "지금 — 회색에서 검정으로만"),
    ("2", "색 + 굵은 글자", "예전 방식 — 글자 굵게"),
    ("3", "색 + 굵은 아이콘 선", "아이콘 선 2.2 → 2.8"),
    ("4", "색 + 위쪽 막대", "메뉴 줄 맨 위에 짧은 검정 막대"),
    ("5", "색 + 아래 점", "글자 아래 작은 점"),
    ("6", "색 + 둥근 바탕", "아이콘 뒤 옅은 회색 둥근 바탕"),
    ("7", "색 + 칸 바탕", "선택한 칸 전체에 옅은 회색 바탕, 아래 모서리 둥글게"),
]
ON_PICK = "7"   # 정함 = 칸 바탕 + 아래 모서리 둥글게 (2026-11-12 사용자)
ON_RADIUS = 10   # 칸 바탕 아래 모서리 — 카드 모서리(10)와 같게
ST_PICK, PP_PICK = 2, 3   # 정한 시안 (2026-11-12 사용자: 종목 = 세로 막대 · 인물 = 마이크)


def icon_svg(style, key, on, mkt="kr", sv=0, pv=0):
    """하단 메뉴 아이콘 한 개 — 스타일 · 지금 칸 여부에 따라."""
    if style == "F":
        return ""
    if style in ("G", "H"):
        return _color_icon(key, on, style == "G", mkt)
    if style == "C" or (style == "D" and on):
        return f'<svg class="ji" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true">{_FILL[key]}</svg>'
    w = {"forecast": "1.8", "people": "2"}.get(key, "2.2") if style == "B" else "1.8"   # B = 2.2px · 마이크 2px · 저울 1.8px (2026-11-12 사용자: 저울만 0.2 더 가늘게, 옛 2.4)
    g = STOCK_V[sv][1] if key == "stock" else PEOPLE_V[pv][1] if key == "people" else _ICON[key]
    return (f'<svg class="ji" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{g}</svg>')


def bar_css():
    """하단 메뉴 공통 CSS — 여정 화면 · 아이콘 비교 화면이 같이 쓴다. 스타일은 #jbar 의 data-style."""
    return (f"#jbar{{position:fixed;left:0;right:0;bottom:0;z-index:44;display:grid;grid-template-columns:repeat(5,1fr);box-sizing:border-box;"
            f"height:calc({BAR_H + BAR_PAD}px + env(safe-area-inset-bottom));padding-bottom:calc({BAR_PAD}px + env(safe-area-inset-bottom));background:#fff;border-top:1px solid #E2E8F0;font-family:inherit}}"
            "#jbar a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;color:#6B7280;text-decoration:none;font-size:11px;line-height:14px;-webkit-tap-highlight-color:transparent;position:relative}"
            "#jbar a.on{color:#111} #jbar a:active{background:#F1F5F9}"   # 선택 = 색만 진하게, 굵기는 그대로 (2026-11-12 사용자)
            "#jbar[data-on='2'] a.on{font-weight:700}"
            "#jbar[data-on='3'] a.on svg{stroke-width:2.8}"
            "#jbar[data-on='4'] a.on::before{content:'';position:absolute;top:-1px;left:50%;width:28px;height:2px;margin-left:-14px;border-radius:0 0 2px 2px;background:#111}"
            "#jbar[data-on='5'] a.on span{position:relative} #jbar[data-on='5'] a.on span::after{content:'';position:absolute;left:50%;bottom:-7px;width:4px;height:4px;margin-left:-2px;border-radius:50%;background:#111}"
            "#jbar[data-on='6'] a .ji{box-sizing:content-box;padding:3px 14px;border-radius:14px} #jbar[data-on='6'] a.on .ji{background:#E8EDF3}"
            f"#jbar[data-on='7'] a.on{{background:#F1F5F9;border-radius:0 0 {ON_RADIUS}px {ON_RADIUS}px}}"
            "#jbar svg *{vector-effect:non-scaling-stroke}"   # 선 굵기 = 화면 px 그대로 (22px 로 줄여 그려도 2.2 · 2 가 그대로 나온다)
            "#jbar[data-style=E] a .ji{box-sizing:content-box;padding:3px 16px;border-radius:15px}"
            "#jbar[data-style=E] a.on .ji{background:#E8EDF3}"
            "#jbar[data-style=F] a{font-size:13px;line-height:18px}"
            "#jbar[data-style=F] a.on::after{content:'';position:absolute;bottom:8px;left:50%;width:18px;height:2px;margin-left:-9px;border-radius:1px;background:#111}")


def bar_html(style, cur="", sv=0, pv=0, on="1"):
    return (f'<nav class="jsample" data-style="{style}" data-on="{on}">'
            + "".join(f'<a data-jt="{k}" href="#"' + (' class="on"' if k == cur else '') + f'>{icon_svg(style, k, k == cur, sv=sv, pv=pv)}<span>{t}</span></a>' for k, t in JTABS)
            + "</nav>")


def icons_page():
    """아이콘 스타일 비교 화면 — 스타일마다 하단 메뉴 견본(지금 칸 = 종목) + `이 스타일로 여정 보기`."""
    rows = ['<div class="sep">선택한 칸 표시 시안 (정한 아이콘 · 지금 칸 = 종목)</div>']
    for k, name, why in ON_STYLES:
        rows.append(f'<section><h2>선택 {k}. {html.escape(name)}{" ✓ 지금" if k == ON_PICK else ""}</h2><div class="why">{html.escape(why)}</div>'
                    f'{bar_html("B", "stock", sv=ST_PICK, pv=PP_PICK, on=k)}<a class="go" href="{JOURNEY_START}?icon=B&amp;on={k}">이 선택 표시로 여정 보기 ›</a></section>')
    rows.append('<details class="old"><summary>종목 · 인물 아이콘 시안 (세로 막대 · 마이크로 정함)</summary>')
    rows.append('<div class="sep">B 굵은 선 · 증시 전망 = 저울 — 종목 아이콘 시안 (지금 칸 = 종목)</div>')
    for i, (nm, _) in enumerate(STOCK_V):
        rows.append(f'<section><h2>종목 {i + 1}. {html.escape(nm)}{" ✓ 정함" if i == ST_PICK else ""}</h2>{bar_html("B", "stock", sv=i)}'
                    f'<a class="go" href="{JOURNEY_START}?icon=B&amp;st={i}">이 종목 아이콘으로 여정 보기 ›</a></section>')
    rows.append('<div class="sep">B 굵은 선 — 인물 아이콘 시안 (지금 칸 = 인물 발언)</div>')
    for i, (nm, _) in enumerate(PEOPLE_V):
        rows.append(f'<section><h2>인물 {i + 1}. {html.escape(nm)}{" ✓ 정함" if i == PP_PICK else ""}</h2>{bar_html("B", "people", pv=i)}'
                    f'<a class="go" href="{JOURNEY_START}?icon=B&amp;pp={i}">이 인물 아이콘으로 여정 보기 ›</a></section>')
    rows.append('</details><details class="old"><summary>지난 비교 — 스타일 8가지 (B 로 정함)</summary>')
    for k, name, why in ICON_STYLES:
        if k == "G":
            rows.append('<div class="sep">강조 카드 · 홈 카드 컬러 아이콘</div>')
        rows.append(f'<section><h2>{k}. {html.escape(name)}</h2><div class="why">{html.escape(why)}</div>{bar_html(k, "stock")}'
                    f'<a class="go" href="{JOURNEY_START}?icon={k}">이 스타일로 여정 보기 ›</a></section>')
    rows.append('</details>')
    css = bar_css().replace("#jbar", ".jsample").replace("position:fixed;left:0;right:0;bottom:0;z-index:44;", "position:relative;")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>하단 메뉴 아이콘 비교</title><style>
body{{margin:0;padding:16px;font:16px/1.4 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#f6f7f9;color:#1d2127}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#8a919c;font-size:13px;margin-bottom:16px}}
section{{background:#fff;border:1px solid #e3e6eb;border-radius:12px;margin:0 0 14px;overflow:hidden}}
h2{{font-size:16px;margin:14px 14px 2px}} .why{{color:#6B7280;font-size:13px;margin:0 14px 12px}}
.sep{{margin:22px 2px 10px;color:#5b6370;font-size:14px;font-weight:600}}
.old{{margin-top:28px}} .old>summary{{padding:14px;background:#fff;border:1px solid #e3e6eb;border-radius:10px;font-weight:600;cursor:pointer;margin-bottom:10px}}
.go{{display:block;padding:12px 14px;border-top:1px solid #eef0f3;color:#1d2127;text-decoration:none;font-size:14px;font-weight:600}}
{css}
</style></head><body><h1>하단 메뉴 아이콘 비교</h1><div class="meta">아래 여백 {BAR_PAD}px 포함 · 종목 · 인물 시안을 하나씩 고르면 여정에서 둘 다 기억 · <a href="/">목업 목록으로</a></div>
{''.join(rows)}</body></html>"""


LOGO = ('<svg viewBox="0 0 313 286" width="31" height="28" aria-hidden="true"><path d="M313 134L164.968 286H35L189.03 134H313Z" fill="#DD0000"/>'
        '<path d="M164.519 0H287L128.954 147H0L164.519 0Z" fill="#000000"/></svg>')
CM_ICON = ('<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M4.5 4.5h13a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2H10l-4 3.5v-3.5H4.5a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z"/></svg>')
# 서랍 메뉴 = 블로그 주요 메뉴 전체 (2026-11-12 Claude 정리, 같은 날 사용자 2차: 하위가 오늘 · 지난 둘뿐인 곳은 타이틀 없이 —
# 메뉴 이름을 누르면 오늘 화면, `지난 …` 은 같은 줄 오른쪽 작은 글자. 타이틀은 하위 이름만으로 뜻이 안 통하는 묶음(테마)에만).
# 줄 = ("row", 이름, 목업 키, 지난 이름 또는 None) · 묶음 = ("group", 타이틀, [(이름, 목업 키)])
MENU = [
    ("row", "미국 증시 리포트", "us", "지난 리포트"),
    ("row", "한국 증시 리포트", "kr", "지난 리포트"),
    ("row", "미국 시가총액 상위 10 종목", "list_us", None),
    ("row", "한국 시가총액 상위 10 종목", "list_kr", None),
    ("row", "증시 전망", "forecast", None),
    ("row", "주요 인물 발언", "people", "지난 발언"),
    ("row", "방송 브리핑", "media", "지난 브리핑"),
    ("group", "테마", [("AI 투자 자금 방향", "th_ai"), ("연준 금리 인하 기대", "th_fed"), ("임원 기관 매매 동향", "th_ins")]),
]


def _slug_map():
    """블로그 종목 페이지 주소(slug) → 목업 파일. 목업이 있는 종목만."""
    import importlib.util
    out = {}
    for rel, mod, name_of in (("stock-radar", "universe.py", lambda s: s), ("kr-stocks", "universe_kr.py", lambda s: s.split(".")[0])):
        try:
            spec = importlib.util.spec_from_file_location("_mock_" + mod[:-3], os.path.join(BASE, rel, mod))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            for c in m.CANDIDATES:
                f = f"mock_{name_of(c[0])}.html"
                if os.path.isfile(os.path.join(BASE, rel, "output", f)):
                    out[c[2]] = f"{rel}/output/{f}"
        except Exception:  # noqa: BLE001
            continue
    return out


_THEME = {}


def theme_parts():
    """지금 저장소 index.html 의 테마 CSS · JS (수정 시각이 바뀌면 다시 읽음) — dk.write_mock 과 같은 방법으로 꺼낸다."""
    path = os.path.join(os.path.dirname(BASE), "index.html")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    if _THEME.get("mt") != mt:
        idx = open(path, encoding="utf-8").read()
        css = re.search(r"<b:skin version='1.0'><!\[CDATA\[(.*?)\]\]></b:skin>", idx, re.S)
        js = re.search(r"//<!\[CDATA\[(.*?)//\]\]>", idx, re.S)
        _THEME.update(mt=mt, css=css.group(1) if css else None, js=js.group(1) if js else None)
    return _THEME


def fresh_theme(page):
    """목업은 그릴 때의 테마를 파일 안에 담는다(11-08 목업 = 11-08 테마). 여정 모드에서는 dk.write_mock 이 만든 글 보기 목업의
    테마 CSS · JS 를 지금 index.html 것으로 바꿔 끼운다 — 댓글 버튼 · 함께 보는 페이지 자리 등 최신 테마 기준 (2026-11-12 사용자: 최신 버전 기준으로)."""
    t = theme_parts()
    if not t or not t["css"] or '<body class="item-view no-dashboard">' not in page:
        return page
    i = page.find("<style>"); j = page.find("</style>", i)
    if 0 <= i < j < page.lower().find("</head>"):
        page = page[:i + 7] + t["css"] + page[j:]
    if t["js"]:
        k = page.rfind("<script>"); e = page.find("</script>", k)
        if k > 0 and e > k and page.find("</body>", e) >= 0:
            page = page[:k + 8] + t["js"] + page[e:]
    return page


def journey_head():
    """상단 헤더 + 전체 메뉴(서랍) — <body> 바로 뒤에 넣는다."""
    rows = []
    for it in MENU:
        if it[0] == "row":
            _, name, k, past = it
            pa = f'<a class="jpast" data-jnone href="#">{html.escape(past)}</a>' if past else ""
            rows.append(f'<div class="jrow"><a class="jmain" data-jk="{k}" href="#">{html.escape(name)}</a>{pa}</div>')
        else:
            _, title, subs = it
            items = "".join(f'<a data-jk="{k}" href="#">{html.escape(n)}<span aria-hidden="true">›</span></a>' for n, k in subs)
            rows.append(f'<div class="jgrp"><div class="jgt">{html.escape(title)}</div>{items}</div>')
    return f"""
<header id="jhead"><a class="jlogo" data-jk="home" href="#">{LOGO}<b>AlphaScope</b></a>
  <span class="jr"><a class="jflag" href="#"></a>
  <button class="jic" data-jsearch type="button" aria-label="검색"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg></button>
  <button class="jic" data-jmenu type="button" aria-label="전체 메뉴"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button></span></header>
<div id="jover" hidden></div>
<aside id="jdrawer" aria-label="전체 메뉴" hidden><div class="jdtop"><b>전체 메뉴</b><button class="jic" data-jclose type="button" aria-label="닫기"><svg viewBox="0 0 16 16" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3l10 10M13 3L3 13"/></svg></button></div>
  <div class="jmk"><a data-jmk="us" href="#">미국 홈</a><a data-jmk="kr" href="#">한국 홈</a></div>{"".join(rows)}</aside>"""


def journey_bar(d, f):
    """하단 고정 메뉴 · 글 끝 정리 · 푸터 · 링크 잇기 스크립트 — </body> 앞에 넣는다."""
    od = os.path.join(BASE, "issue_store", "output")
    fore = {x[:-5].replace("mock_", "", 1): f"issue_store/output/{x}" for x in os.listdir(od)
            if x.startswith("mock_forecast-") and x.endswith(".html")} if os.path.isdir(od) else {}
    tabs = JTABS
    icons = {st: {**{k: [icon_svg(st, k, False), icon_svg(st, k, True)] for k, _ in JTABS},
                  "stock_v": [[icon_svg(st, "stock", False, sv=i), icon_svg(st, "stock", True, sv=i)] for i in range(len(STOCK_V))],
                  "people_v": [[icon_svg(st, "people", False, pv=i), icon_svg(st, "people", True, pv=i)] for i in range(len(PEOPLE_V))],
                  **{f"report_{m}": [icon_svg(st, "report", False, m), icon_svg(st, "report", True, m)] for m in ("us", "kr")}} for st, _, _ in ICON_STYLES}
    btns = "".join(f'<a data-jt="{k}" href="#"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" '
                   f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICON[k]}</svg><span>{t}</span></a>' for k, t in tabs)
    cfg = json.dumps({"pages": J_PAGES, "slugs": _slug_map(), "fore": fore, "dir": d, "file": f, "icons": icons}, ensure_ascii=False)
    footer = ('<footer class="site-footer"><details class="footer-disclaimer"><summary><span class="footer-title">ALPHASCOPE 주식 리포트</span></summary>'
              '<p>해설 문장 일부는 AI 가 씁니다. 모든 정보는 참고용이며, 앞으로의 결과는 지난 기록과 다를 수 있습니다.</p></details>'
              '<p class="footer-copy">© 2026 ALPHASCOPE. All rights reserved.</p></footer>')
    bar_css_esc = bar_css()
    return f"""
{footer}
<style>
header.navbar, .header-bar {{display:none !important}}   /* 홈 목업의 옛 헤더 — 여정에서는 아래 헤더 하나로 */
#jhead{{display:flex;align-items:center;justify-content:space-between;height:56px;padding:0 6px 0 16px;background:#fff;border-bottom:1px solid #E2E8F0;box-sizing:border-box}}
#jhead .jlogo{{display:inline-flex;align-items:center;gap:8px;color:#111;text-decoration:none;font-size:20px;letter-spacing:-.3px}}
#jhead .jr{{display:inline-flex;align-items:center;gap:2px}}
.jflag{{display:inline-flex;align-items:center;height:32px;padding:0 10px;margin-right:4px;border:1px solid #E2E8F0;border-radius:16px;color:#111;text-decoration:none;font-size:14px;line-height:20px}}
.jic{{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border:0;background:none;color:#111;cursor:pointer;padding:0}}
#jover{{position:fixed;inset:0;z-index:58;background:rgba(15,23,42,.35)}}
#jdrawer{{position:fixed;top:0;right:0;bottom:0;z-index:60;width:min(320px,86vw);overflow-y:auto;background:#fff;box-shadow:-8px 0 30px rgba(15,23,42,.18);padding:0 0 24px}}
#jover[hidden],#jdrawer[hidden]{{display:none}}
.jdtop{{display:flex;align-items:center;justify-content:space-between;height:56px;padding:0 6px 0 20px;border-bottom:1px solid #E2E8F0;font-size:16px}}
.jmk{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:14px 20px}}
.jmk a{{display:flex;align-items:center;justify-content:center;height:40px;border:1px solid #E2E8F0;border-radius:8px;color:#111;text-decoration:none;font-size:15px}}
.jmk a.on{{border-color:#111;font-weight:700}}
.jrow{{display:flex;align-items:stretch;border-top:1px solid #E2E8F0}}
.jrow .jmain{{flex:1 1 auto;display:flex;align-items:center;min-height:52px;padding:0 12px 0 20px;color:#111;text-decoration:none;font-size:16px;line-height:24px;font-weight:600}}
.jrow .jpast{{flex:none;display:flex;align-items:center;padding:0 20px 0 12px;color:#6B7280;text-decoration:none;font-size:13px;line-height:18px}}
.jrow a:active{{background:#F1F5F9}} .jrow .jmain.on, .jgrp a.on{{background:#F8FAFC;box-shadow:inset 3px 0 0 #111;font-weight:700}}   /* 지금 보는 메뉴 — 빨강은 ▲상승과 겹쳐 안 씀 */
.jgrp{{padding:6px 0 8px;border-top:1px solid #E2E8F0}}
.jgt{{padding:12px 20px 4px;font-size:16px;line-height:24px;font-weight:700;color:#111}}
.jgrp a{{display:flex;align-items:center;justify-content:space-between;min-height:44px;padding:0 20px 0 32px;color:#333;text-decoration:none;font-size:15px;line-height:22px}}
.jgrp a span{{color:#9CA3AF}} .jgrp a[data-jnone]{{color:#6B7280}} .jgrp a:active{{background:#F1F5F9}} .jgrp a.on{{color:#111;font-weight:700}}
{bar_css_esc}
body{{padding-bottom:calc({BAR_H + BAR_PAD}px + env(safe-area-inset-bottom)) !important}}
/* 글 끝 순서 (같은 날 사용자 4차): 본문 → 함께 보는 페이지 → [댓글 · TOP] → 푸터. 버튼 줄 위아래 구분선 없음 */
.post-shell .post-nav, .post-shell.ends-text .post-nav{{border-top:0 !important;border-bottom:0 !important;padding-top:0 !important;padding-bottom:0 !important;margin-top:24px !important}}
.post-shell > [data-related].is-moved{{margin-top:40px !important}}
.post-nav .post-nav-list{{display:none !important}}   /* 검은 `목록` · `홈으로` 버튼 뺌 — 지난 리포트는 서랍 메뉴 하위 칸, 홈은 하단 메뉴 */
#jtoast{{position:fixed;left:50%;bottom:{BAR_H + BAR_PAD + 20}px;transform:translateX(-50%);z-index:10001;padding:10px 16px;border-radius:8px;background:#111;color:#fff;font-size:13px;line-height:18px;white-space:nowrap;opacity:0;transition:opacity .2s;pointer-events:none}}
#jmock{{display:block;padding:18px 16px 26px;text-align:center;font:13px/18px -apple-system,'Apple SD Gothic Neo',sans-serif;color:#8a919c}}
#jmock a{{color:#8a919c}}
</style>
<div id="jmock">사용자 여정 테스트 · <a href="/">목업 목록으로</a></div>
<nav id="jbar" data-style="A" aria-label="주요 페이지">{btns}</nav><div id="jtoast"></div>
<script>
(function () {{
  var ST_PICK = {ST_PICK}, PP_PICK = {PP_PICK};
  var C = {cfg}, J = '{J}', here = C.dir + '/output/' + C.file, P = C.pages;
  var mk = sessionStorage.getItem('jMarket') || 'kr';   // 지금 보는 나라 — 홈 · 증시 리포트 · 종목 칸이 따라간다
  if (/kr-stocks|kr-market-report|mock_home_kr/.test(here)) mk = 'kr';
  if (/stock-radar|daily-report|mock_home_us/.test(here)) mk = 'us';
  try {{ sessionStorage.setItem('jMarket', mk); }} catch (e) {{}}
  var tab = {{home: P['home_' + mk], report: P[mk], stock: P['list_' + mk], forecast: P.forecast, people: P.people}};
  var cur = /home-split/.test(here) ? 'home' : /daily-report|kr-market-report/.test(here) ? 'report' : /stock-radar|kr-stocks/.test(here) ? 'stock'
          : /issue_store/.test(here) ? 'forecast' : /people-radar/.test(here) ? 'people' : '';
  function go(key) {{ return J + (P[key] || key); }}
  var ic = (location.search.match(/[?&]icon=([A-H])/) || [])[1];   // 아이콘 스타일 — 비교 화면에서 고른 것을 이 탭 동안 기억
  if (ic) {{ try {{ sessionStorage.setItem('jIcon2', ic); }} catch (e) {{}} }}
  try {{ ic = ic || sessionStorage.getItem('jIcon2'); }} catch (e) {{}}
  ic = ic || 'B';   // 정한 스타일 = B 굵은 선 (2026-11-12 사용자)
  document.getElementById('jbar').setAttribute('data-style', ic);
  var onv = (location.search.match(/[?&]on=([1-7])/) || [])[1];   // 선택한 칸 표시 시안
  if (onv) {{ try {{ sessionStorage.setItem('jOn', onv); }} catch (e) {{}} }}
  try {{ onv = onv || sessionStorage.getItem('jOn'); }} catch (e) {{}}
  document.getElementById('jbar').setAttribute('data-on', onv || '{ON_PICK}');
  function pick(name, re, def) {{   // 종목 · 인물 시안 번호 — 주소에 있으면 기억, 없으면 기억한 것
    var v = (location.search.match(re) || [])[1];
    if (v) {{ try {{ sessionStorage.setItem(name, v); }} catch (e) {{}} }}
    try {{ v = v || sessionStorage.getItem(name); }} catch (e) {{}}
    return +(v || def);
  }}
  var stv = pick('jSt2', /[?&]st=(\\d+)/, ST_PICK), ppv = pick('jPp2', /[?&]pp=(\\d+)/, PP_PICK);   // 정한 시안 = 종목 세로 막대 · 인물 마이크
  document.querySelectorAll('#jbar a').forEach(function (a) {{
    var k = a.dataset.jt, on = k === cur, svg = a.querySelector('.ji') || a.querySelector('svg'), ics = C.icons[ic] || C.icons.A;
    var set = k === 'report' ? ics['report_' + mk] : k === 'stock' && ics.stock_v ? ics.stock_v[stv] || ics.stock : k === 'people' && ics.people_v ? ics.people_v[ppv] || ics.people : ics[k];
    var sv = set[on ? 1 : 0];
    if (svg) svg.remove();
    if (sv) a.insertAdjacentHTML('afterbegin', sv);
    a.href = J + tab[k]; if (on) a.className = 'on';
  }});
  // 헤더 — 로고 = 지금 나라 홈, 국기 스위치 = 다른 나라 홈
  document.querySelectorAll('[data-jk]').forEach(function (a) {{ var k = a.dataset.jk; a.href = k === 'home' ? J + P['home_' + mk] : go(k); if (go(k) === location.pathname) a.classList.add('on'); }});
  var other = mk === 'kr' ? 'us' : 'kr', fl = document.querySelector('.jflag');
  fl.textContent = other === 'kr' ? '한국' : '미국'; fl.href = J + P['home_' + other];
  fl.addEventListener('click', function () {{ try {{ sessionStorage.setItem('jMarket', other); }} catch (e) {{}} }});
  document.querySelectorAll('[data-jmk]').forEach(function (a) {{
    a.href = J + P['home_' + a.dataset.jmk]; if (a.dataset.jmk === mk) a.className = 'on';
    a.addEventListener('click', function () {{ try {{ sessionStorage.setItem('jMarket', a.dataset.jmk); }} catch (e) {{}} }});
  }});
  var ov = document.getElementById('jover'), dr = document.getElementById('jdrawer');
  function menu(open) {{ ov.hidden = dr.hidden = !open; document.body.style.overflow = open ? 'hidden' : ''; }}
  document.querySelector('[data-jmenu]').addEventListener('click', function () {{ menu(true); }});
  document.querySelector('[data-jclose]').addEventListener('click', function () {{ menu(false); }});
  ov.addEventListener('click', function () {{ menu(false); }});
  function toast(t) {{ var e = document.getElementById('jtoast'); e.textContent = t; e.style.opacity = 1; clearTimeout(e._t); e._t = setTimeout(function () {{ e.style.opacity = 0; }}, 1600); }}
  document.querySelectorAll('[data-jnone]').forEach(function (a) {{ a.addEventListener('click', function (e) {{ e.preventDefault(); toast('지난 글 목록 화면 (목업 없음)'); }}); }});
  document.querySelector('[data-jsearch]').addEventListener('click', function () {{ toast('검색 (목업에서는 열지 않음)'); }});
  // 글 끝 — 함께 보는 페이지(테마가 버튼 줄 아래로 옮겨 둔 것) 뒤로 버튼 줄 · 댓글 칸을 옮긴다
  document.querySelectorAll('.post-shell').forEach(function (sh) {{
    var nav = sh.querySelector('.post-nav'), rel = sh.querySelectorAll(':scope > [data-related]');
    if (!nav || !rel.length) return;
    var last = rel[rel.length - 1], cm = sh.querySelector(':scope > .comments');
    last.parentNode.insertBefore(nav, last.nextSibling);
    if (cm) nav.parentNode.insertBefore(cm, nav.nextSibling);
  }});
  // [댓글 · TOP] 줄. 목업 껍데기엔 댓글 칸이 없어 버튼만 흉내
  document.querySelectorAll('.post-nav').forEach(function (n) {{
    if (n.querySelector('.post-nav-cm')) return;
    var b = document.createElement('button'); b.type = 'button'; b.className = 'post-nav-cm'; b.innerHTML = '{CM_ICON}<span class="cm-label">댓글</span>';
    b.addEventListener('click', function () {{ toast('댓글 열림 (목업에서는 흉내만)'); }});
    n.insertBefore(b, n.firstChild);
  }});
  function map(href) {{   // 블로그 주소 → 목업 주소. null = 바깥 링크(그대로), '' = 목업 없음
    var u; try {{ u = new URL(href, location.href); }} catch (e) {{ return null; }}
    var blog = u.host === 'alpha-scope.blogspot.com';
    if (!blog && u.host !== location.host) return null;
    var p = decodeURIComponent(u.pathname);
    if (!blog && p.indexOf(J) === 0) return null;   // 이미 여정 안
    var m;
    if (p === '/' || p === '') return P['home_' + mk];
    if (p === '/p/korea.html') return P.home_kr;
    if ((m = p.match(/^\\/p\\/(.+-stock)\\.html$/))) return C.slugs[m[1]] || '';
    if (p === '/p/us-market-cap-top10.html') return P.list_us;
    if (p === '/p/kr-market-cap-top10.html') return P.list_kr;
    if (p === '/p/forecast-list.html') return P.forecast;
    if ((m = p.match(/^\\/p\\/(forecast-.+)\\.html$/))) return C.fore[m[1]] || P.forecast;
    if ((m = p.match(/^\\/p\\/theme-(.+)\\.html$/))) return {{'ai-capex': P.th_ai, 'fed-rate-cut-expectations': P.th_fed, 'insider-trading': P.th_ins}}[m[1]] || '';
    if (p.indexOf('/search/label/') === 0) {{
      if (/인물/.test(p)) return P.people; if (/한국/.test(p)) return P.kr; if (/데일리/.test(p)) return P.us; if (/미디어/.test(p)) return P.media; return '';
    }}
    if (/^\\/20\\d\\d\\//.test(p)) return /remarks|people/.test(p) ? P.people : /media/.test(p) ? P.media : /kr|korea/.test(p) ? P.kr : P.us;
    return blog ? '' : null;
  }}
  document.addEventListener('click', function (ev) {{
    var el = ev.target.closest && ev.target.closest('a[href],[data-href]');
    if (!el || el.closest('#jbar') || el.closest('#jmock') || el.closest('#jhead') || el.closest('#jdrawer')) return;
    if (el.classList.contains('pr-back')) {{   // 위쪽 뒤로 가기 = 방금 보던 화면, 없으면 홈 (인물 화면이 열려 있으면 테마가 맡는다)
      if (el.onclick) return;
      ev.preventDefault(); ev.stopPropagation();
      if (history.length > 1) history.back(); else location.href = J + P['home_' + mk];
      return;
    }}
    var raw = el.getAttribute('href') || el.getAttribute('data-href') || '';
    if (!raw || raw.charAt(0) === '#') return;
    var to = map(raw);
    if (to === null) return;
    ev.preventDefault(); ev.stopPropagation();
    if (to === '') {{ toast('목업에 없는 페이지입니다'); return; }}
    var hash = ''; try {{ hash = new URL(raw, location.href).hash; }} catch (e) {{}}
    location.href = J + to + hash;
  }}, true);
}})();
</script>"""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 목업을 고친 뒤 새로고침하면 바로 보이게
        super().end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in ("/star", "/archive"):
            self.send_error(404)
            return
        key = u.path[1:]
        k = unquote(dict(x.split("=", 1) for x in u.query.split("&") if "=" in x).get("k", ""))
        with _lock:
            p = load_prefs()
            p[key] = [x for x in p[key] if x != k] if k in p[key] else p[key] + [k]
            save_prefs(p)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        journey = path.startswith("/j/")   # 사용자 여정 테스트 — 같은 파일 + 하단 메뉴 · 링크 잇기
        if journey:
            path = path[2:]
        if path == "/icons":
            body = icons_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/", "/index.html", "/archive"):
            body = index_page(archive=path == "/archive").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        seg = path.strip("/").split("/")
        if len(seg) < 3 or seg[1] != "output" or ".." in seg:   # output 폴더 안만
            self.send_error(404)
            return
        fp = os.path.join(BASE, *seg)
        if len(seg) == 3 and fp.endswith(".html") and os.path.isfile(fp):
            with open(fp, encoding="utf-8", errors="replace") as fh:
                page = fh.read()
            if journey:
                page = fresh_theme(page)
            i = page.lower().rfind("</body>")
            extra = journey_bar(seg[0], seg[2]) if journey else BACK_BAR
            page = page[:i] + extra + page[i:] if i >= 0 else page + extra
            if journey:   # 상단 헤더 · 서랍 = <body …> 바로 뒤
                m = re.search(r"<body[^>]*>", page, re.I)
                page = page[:m.end()] + journey_head() + page[m.end():] if m else journey_head() + page
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if journey:   # 그림 등 딸린 파일 — /j 를 뗀 주소로
            self.path = path
        super().do_GET()

    def log_message(self, *a):
        pass


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "?"


if __name__ == "__main__":
    try:
        host = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip()
    except OSError:
        host = ""
    print("목업 목록:")
    if host:
        print(f"  http://{host}.local:{PORT}/   ← 즐겨찾기 추천 (와이파이 IP 가 바뀌어도 그대로)")
    print(f"  http://{lan_ip()}:{PORT}/")
    print("끄기: Ctrl+C", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
