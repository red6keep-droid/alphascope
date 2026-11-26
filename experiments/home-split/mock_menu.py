"""전체 메뉴(서랍) · 헤더 · 푸터 다시 짜기 목업 (2026-11-26 사용자).

    python experiments/home-split/mock_menu.py     # output/mock_menu_kr.html · mock_menu_us.html

블로그 테마(index.html)의 CSS · JS 를 그대로 쓰고, 헤더 · 서랍 · 푸터 마크업만 새 모양으로 바꾼다.
  ① 프로필(로그인) = 헤더에서 빼고 서랍 맨 위 왼쪽(닫기 버튼과 같은 줄)
  ② 미국 · 한국 → 미국 증시 · 한국 증시(헤더 스위치 · 서랍 버튼 둘 다), 스위치 = 둥근 사각(반지름 8, 메뉴 버튼과 같은 꼴)
  ③ 검색 = 아이콘만 → 테두리 상자 + `종목` 글자(스위치와 같은 꼴, 높이 36)
  ④ 서랍 메뉴 줄마다 아이콘(하단 고정 메뉴 아이콘과 같은 선 아이콘) · Hot Issue = 접기(아코디언) · 서랍 가로 360
  ⑤ 서랍 버튼 위 간격 36 → 18 · 버튼 높이 40 → 35
  ⑥ 빠져 있던 메뉴 = 증시 시황 · Newfact 뉴스 · 주식 공부 + 소개 · 개인정보처리방침 · 문의
  ⑦ 푸터 제목 `Newfact 주식 리포트` → `Newfact`, 첫 문장 줄임
적용 때: index.html 의 헤더(nav-right) · 서랍(#primary-menu) · 푸터 마크업 + CSS, 로그인 JS 는 서랍 자리에 그리게.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
FILES = {"us": "mock_menu_us.html", "kr": "mock_menu_kr.html"}


def svg(d, sw="1.8"):
    return (f'<svg class="mi" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>')


# 아이콘 — 하단 고정 메뉴(as-tabbar)에 이미 있는 것은 같은 그림을 쓴다(리포트 · 종목 · 증시 전망 · 인물 발언)
IC = {
    "report": svg("<path d='M4 19h16'/><path d='M6 16l4-5 3 3 5-7'/>"),
    "story": svg("<rect x='4' y='3.5' width='16' height='17' rx='2'/><path d='M8 8.5h8M8 12.5h8M8 16.5h5'/>"),
    "news": svg("<path d='M4 5h12v14H6.5A2.5 2.5 0 0 1 4 16.5z'/><path d='M16 9h4v7.5a2.5 2.5 0 0 1-5 0'/><path d='M7.5 9h5M7.5 12.5h5M7.5 16h3'/>"),
    "stock": svg("<path d='M4 20h16'/><path d='M7.5 16v-5M12 16V6M16.5 16v-8'/>"),
    "forecast": svg("<path d='M12 3v18M7.5 21h9'/><path d='M4 7h16'/><path d='M6 7l-3 7h6zM18 7l-3 7h6z'/>"),
    "issue": svg("<path d='M12 3.5c.6 3 4.5 4.8 4.5 9.5a4.5 4.5 0 0 1-9 0c0-2.2 1-3.6 2.2-4.6.1 1.7.8 2.8 2 3.1-.6-2.6-.3-5.4.3-8z'/>"),
    "people": svg("<rect height='11' rx='3' width='6' x='9' y='3'/><path d='M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7'/>"),
    "study": svg("<path d='M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15H7.5A2.5 2.5 0 0 0 5 20.5z'/><path d='M5 20.5A2.5 2.5 0 0 1 7.5 18H19v3H7.5'/>"),
    "chev": '<svg class="mc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>',
}
FLAG_US = ('<svg class="mf" viewBox="0 0 22 22" aria-hidden="true"><defs><clipPath id="mf-us"><circle cx="11" cy="11" r="11"/></clipPath></defs><g clip-path="url(#mf-us)"><rect width="22" height="22" fill="#fff"/>'
           + "".join(f'<rect y="{i * 22 / 13:.2f}" width="22" height="{22 / 13:.2f}" fill="#B22234"/>' for i in (0, 2, 4, 6, 8, 10, 12))
           + f'<rect width="11" height="{7 * 22 / 13:.2f}" fill="#3C3B6E"/></g><circle cx="11" cy="11" r="10.5" fill="none" stroke="rgba(0,0,0,.12)"/></svg>')
FLAG_KR = ('<svg class="mf" viewBox="0 0 22 22" aria-hidden="true"><g transform="rotate(33.7 11 11)"><circle cx="11" cy="11" r="11" fill="#0047A0"/>'
           '<path d="M0 11a11 11 0 0 1 22 0z" fill="#CD2E3A"/><circle cx="5.5" cy="11" r="5.5" fill="#CD2E3A"/><circle cx="16.5" cy="11" r="5.5" fill="#0047A0"/></g></svg>')   # 테마 NAV_FLAGS.kr 그대로

L = lambda s: "/search/label/" + __import__("urllib.parse").parse.quote(s)


def row(icon, name, href, past=None, latest=None):
    lt = f' data-latest="{latest}"' if latest else ""
    p = f'<a class="menu-past" href="{href}">{past}</a>' if past else ""
    return f'<div class="menu-row"><a class="nav-item"{lt} href="{href}">{IC[icon]}<span>{name}</span></a>{p}</div>'


def acc(icon, name, items, open_=False):
    li = "".join(f'<a class="nav-item" href="{h}">{n}</a>' for n, h in items)
    return (f'<details class="menu-acc"{" open" if open_ else ""}><summary>{IC[icon]}<span>{name}</span>{IC["chev"]}</summary>'
            f'<div class="menu-acc-b">{li}</div></details>')


def drawer(mkt, files):
    cur = lambda m: ' aria-current="page"' if m == mkt else ""
    me = ('<div class="menu-me"><button type="button" class="menu-me-btn" aria-label="로그인">'
          '<span class="menu-me-pic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          "<circle cx='12' cy='8.5' r='3.5'/><path d='M5 19.5c.9-3.3 3.6-5 7-5s6.1 1.7 7 5'/></svg></span><span class='menu-me-n'>로그인</span></button></div>")
    mk = ('<div class="menu-mk">'
          f'<a class="nav-item" data-bar="1" data-flag="us" href="{files["us"]}"{cur("us")}>{FLAG_US}미국 증시</a>'
          f'<a class="nav-item" data-bar="1" data-flag="kr" href="{files["kr"]}"{cur("kr")}>{FLAG_KR}한국 증시</a></div>')
    rows = [   # 순서 (2026-11-26 사용자): 리포트 둘 → 증시 시황 → 증시 전망 → Hot Issue → 종목 목록 → Newfact 뉴스 → 주요 인물 발언 → 주식 공부. 시가총액 상위 10 둘 · 방송 브리핑 · 테마 = 뺌
        row("report", "미국 증시 리포트", L("데일리 브리핑"), "지난 리포트", "데일리 브리핑"),
        row("report", "한국 증시 리포트", L("한국 증시 리포트"), "지난 리포트", "한국 증시 리포트"),
        row("story", "증시 시황", L("증시 시황"), "지난 시황", "증시 시황") + '<!--new-->',
        row("forecast", "증시 전망", "/p/forecast-list.html"),
        acc("issue", "Hot Issue", [("이란 전쟁", "/p/issue-iran.html"), ("관세", "/p/issue-tariff.html"),
                                   ("반도체 수출 통제", "/p/issue-export.html"), ("엔비디아 CEO 사임", "/p/issue-nvidia-ceo.html")]),
        row("stock", "종목 목록", "/p/stock-lists.html"),
        row("news", '<span class="brand-word">Newfact</span> 뉴스', L("Newfact 뉴스"), "지난 뉴스", "Newfact 뉴스") + '<!--new-->',
        row("people", "주요 인물 발언", L("인물 발언"), "지난 발언", "인물 발언"),
        row("study", "주식 공부", "/p/study.html") + '<!--new-->',
    ]
    rows = [r.replace('</a>', '<span class="mk-new">새로 넣음</span></a>', 1).replace('<!--new-->', '') if '<!--new-->' in r else r for r in rows]
    site = ('<div class="menu-site"><a href="/p/about.html">소개</a><i>·</i><a class="fl-privacy" href="/p/privacy.html">개인정보처리방침</a><i>·</i>'
            '<a href="/p/contact.html">문의</a></div>')   # 한 줄 · 아이콘 없음 · 위 구분선 (2026-11-26 사용자)

    return f'<nav class="menu-items" id="primary-menu">{me}{mk}{"".join(rows)}{site}</nav>'


CSS = """
/* ---- 2026-11-26 목업: 헤더 · 서랍 · 푸터 ---- */
/* ② 미국 증시 · 한국 증시 스위치 = 메뉴 버튼과 같은 둥근 사각(반지름 8) */
.nav-switch { border-radius: 8px; padding: 7px 10px 7px 8px; }
/* ③ 검색 = 테두리 상자 + 글자, 스위치와 같은 높이 36 · 글자 14/20 */
.as-search-btn.box { display: inline-flex; align-items: center; gap: 4px; width: auto; height: 36px; flex: none; padding: 0 10px 0 8px; border: 1px solid var(--border-strong); border-radius: 8px; background: #fff; color: #111; font: inherit; font-size: 14px; line-height: 20px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.as-search-btn.box svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.as-search-btn.box:hover { border-color: #94A3B8; background: #F8FAFC; }
.menu-quick { gap: 6px !important; }
/* ① 프로필 = 서랍 맨 위 왼쪽, 닫기 버튼(위 18 · 높이 32)과 같은 줄 */
.menu-items { padding-top: 61px !important; }
.menu-me { position: absolute; top: 18px; left: 20px; right: 64px; }
.menu-me-btn { display: flex; align-items: center; gap: 10px; height: 32px; padding: 0; border: 0; background: none; font: inherit; font-size: 15px; line-height: 22px; font-weight: 700; color: #111; cursor: pointer; }
.menu-me-pic { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; background: #F1F5F9; color: #6B7280; flex: none; overflow: hidden; }
.menu-me-pic svg { width: 20px; height: 20px; display: block; }
.menu-me-pic img { width: 32px; height: 32px; object-fit: cover; display: block; }
/* ⑤ 버튼 위 간격 36 → 18(프로필 줄 아래부터) · 버튼 높이 40 → 35 · `홈` 꼬리 뺌 */
.menu-items .menu-mk { padding: 7px 20px 14px; }
.menu-items .menu-mk .nav-item { height: 35px; gap: 6px; }
.menu-items .menu-mk .nav-item::after, .menu-items .menu-mk .nav-item[aria-current="page"]::after { content: none !important; }
.menu-items .menu-mk .mf { width: 18px; height: 18px; flex: none; display: block; }
/* ④ 줄 앞 아이콘 20 회색(기본형) · 글자는 아이콘 오른쪽 12 */
.menu-items .menu-row .nav-item { display: flex; flex-direction: row; align-items: center; justify-content: flex-start; gap: 12px; text-align: left; }
.menu-items .menu-row .nav-item > span { white-space: nowrap; }
.menu-items .mi { width: 20px; height: 20px; flex: none; display: block; color: #6B7280; }
.menu-items .mi * { vector-effect: non-scaling-stroke; }
.mk-new { margin-left: 6px; padding: 0 5px; border-radius: 4px; background: #FEF3C7; color: #92400E; font-size: 11px; line-height: 18px; font-weight: 700; flex: none; }
/* ④ 접기(아코디언) — 줄 모양은 다른 메뉴 줄과 같고 오른쪽 끝 화살표 */
.menu-items .menu-acc { border-bottom: 1px solid var(--border); }
.menu-items .menu-acc summary { display: flex; align-items: center; gap: 12px; padding: 14px 20px; font-size: 16px; line-height: 24px; font-weight: 600; color: #111; cursor: pointer; list-style: none; -webkit-tap-highlight-color: transparent; }
.menu-items .menu-acc summary::-webkit-details-marker { display: none; }
.menu-items .menu-acc summary:active { background: #F1F5F9; }
.menu-items .menu-acc .mc { width: 18px; height: 18px; margin-left: auto; color: #6B7280; transition: transform .15s ease; }
.menu-items .menu-acc[open] .mc { transform: rotate(180deg); }
.menu-items .menu-acc-b { padding: 0 0 8px; }
.menu-items .menu-acc-b .nav-item { border-bottom: 0 !important; padding: 10px 20px 10px 52px !important; font-size: 15px !important; line-height: 22px !important; font-weight: 400; color: #333; }
.menu-items .menu-acc-b .nav-item:active { background: #F1F5F9; }
/* ⑥ 소개 · 개인정보처리방침 · 문의 — 서랍 맨 아래 한 줄, 아이콘 없음, 위 구분선(메뉴 줄 마지막 선), 14/20 회색 · 개인정보처리방침만 굵게 · 검정(푸터와 같은 규칙) */
.menu-items .menu-site { display: flex; align-items: center; flex-wrap: wrap; margin-top: auto; padding: 12px 14px 0; border-top: 1px solid var(--border); }   /* 서랍 맨 아래에 붙는다(메뉴가 짧으면 화면 아래, 길면 마지막 메뉴 다음) (2026-11-26 사용자) */
.menu-items > * { flex-shrink: 0; }
.menu-items .menu-site a { display: block; padding: 6px 6px; font-size: 14px; line-height: 20px; color: #6B7280; text-decoration: none; }
.menu-items .menu-site i { font-style: normal; color: #CBD5E1; font-size: 14px; line-height: 20px; }
.menu-items .menu-site a.fl-privacy { color: #111; font-weight: 700; }
.menu-items .menu-site a:active { background: #F1F5F9; border-radius: 6px; }
/* 서랍 가로 넓힘 320 → 360(폰은 화면의 90%까지) (2026-11-26 사용자 "조금 더 크게") */
.menu-items { width: min(360px, 90vw) !important; }
/* 목업 설명 칸 */
.mk-note { box-sizing: border-box; max-width: 680px; margin: 16px 10px; overflow: hidden; padding: 18px 18px 6px; background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; font-size: 15px; line-height: 23px; color: #111; }
.mk-note h2 { margin: 0 0 10px; font-size: 18px; line-height: 26px; }
.mk-note h3 { margin: 18px 0 6px; font-size: 16px; line-height: 24px; }
.mk-note ol, .mk-note ul { margin: 0 0 12px; padding-left: 20px; }
.mk-note li { margin: 3px 0; }
.mk-note .was { color: #6B7280; text-decoration: line-through; }
.mk-note .pick { display: inline-block; margin-right: 4px; padding: 0 6px; border-radius: 4px; background: #111; color: #fff; font-size: 12px; line-height: 20px; font-weight: 700; }
.mk-note .alt { display: inline-block; margin-right: 4px; padding: 0 6px; border-radius: 4px; background: #E2E8F0; color: #111; font-size: 12px; line-height: 20px; font-weight: 700; }
.mk-open { display: block; width: 100%; height: 44px; margin: 4px 0 14px; border: 1px solid #111; border-radius: 8px; background: #111; color: #fff; font: inherit; font-size: 15px; font-weight: 700; cursor: pointer; }
.mk-strip { max-width: 100%; box-sizing: border-box; display: flex; align-items: center; gap: 6px; margin: 6px 0 4px; padding: 10px; border: 1px dashed #CBD5E1; border-radius: 8px; overflow-x: auto; }
.mk-strip .logo-full { width: 113px; height: 26px; flex: none; }
.mk-strip .sp { flex: 1; }
.mk-strip .nav-switch svg { width: 18px; height: 18px; }
.mk-strip .tg { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; flex: none; border: 1px solid var(--border-strong); border-radius: 8px; color: var(--gray-600); }
.mk-strip .tg svg { width: 20px; height: 20px; }
.mk-me2 { display: flex; align-items: center; gap: 10px; font-weight: 700; }
.mk-me2 i { display: block; width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #94A3B8, #475569); }
"""

LEAD_OLD = "Newfact 리포트는 공개된 시세 · SEC 공시 · FRED 경제 지표 · 뉴스를 정해진 규칙으로 계산해 정리한 기록이며, 특정 종목의 매수 · 매도를 권유하지 않습니다."
LEAD_A = "공개된 시세 · 공시 · 경제 지표 · 뉴스를 정해진 규칙으로 정리한 기록이며, 매수 · 매도를 권유하지 않습니다."
FOOT = ("공개된 시세 · 공시 · 경제 지표 · 뉴스를 정해진 규칙으로 정리한 기록이며, 해설 일부는 AI 가 씁니다. "
        "모든 정보는 참고용으로, 매수 · 매도를 권유하지 않으며 투자 판단과 책임은 투자자 본인에게 있습니다. 종목 로고는 각 회사의 상표입니다.")   # 푸터 한 문단 (2026-11-26)
MORE_OLD = ("해설 문장 일부는 AI 가 씁니다. 모든 정보는 참고용이며, 앞으로의 결과는 지난 기록과 다를 수 있습니다. 애널리스트 의견 · 목표가는 외부 의견을 옮긴 것입니다. "
            "개별 투자 상담을 하지 않으며, 투자 판단과 책임은 투자자 본인에게 있습니다. 종목 로고는 각 회사의 상표이며, 종목을 구분하는 용도로만 쓰고 해당 회사와 제휴 관계가 없습니다.")   # 11-26 전 접힌 글(비교용)
MORE_A = "해설 일부는 AI 가 씁니다. 모든 정보는 참고용이며, 투자 판단과 책임은 투자자 본인에게 있습니다. 종목 로고는 각 회사의 상표입니다."   # 접힌 글 줄임 추천 (2026-11-26 사용자 "장황하다, 소개 페이지에 있으니 짧게")
MORE_B = "해설 일부는 AI 가 씁니다. 투자 판단과 책임은 투자자 본인에게 있습니다."
LEAD_B = "공개 자료를 정해진 규칙으로 정리한 기록이며, 매수 · 매도를 권유하지 않습니다."

SEARCH_SVG = "<svg aria-hidden='true' viewBox='0 0 24 24'><circle cx='11' cy='11' r='7'/><path d='M20 20l-3.5-3.5'/></svg>"


def note(mkt, files, logo, hidden_p=""):
    other = "us" if mkt == "kr" else "kr"
    flag_o = FLAG_US if other == "us" else FLAG_KR
    name_o = "미국 증시" if other == "us" else "한국 증시"
    strip = lambda label: (f'<div class="mk-strip">{logo}<span class="sp"></span>'
                           f'<span class="as-search-btn box">{SEARCH_SVG}{label}</span>'
                           f'<span class="nav-switch">{flag_o}<span>{name_o}</span></span>'
                           '<span class="tg"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg></span></div>')
    return f"""
<section class="mk-note">
  <h2>전체 메뉴 · 헤더 · 푸터 고침 — 목업</h2>
  <button type="button" class="mk-open" onclick="document.querySelector('.nav-toggle').click()">전체 메뉴 열기</button>
  <h3>헤더</h3>
  <ol>
    <li>프로필(로그인) 버튼 = 헤더에서 빼고 <b>전체 메뉴 맨 위 왼쪽</b>(닫기 버튼과 같은 줄)</li>
    <li>스위치 <span class="was">한국</span> → <b>한국 증시</b> · <span class="was">미국</span> → <b>미국 증시</b>, 모양 = 알약 → 메뉴 버튼과 같은 <b>둥근 사각</b>(반지름 8 · 높이 36)</li>
    <li>검색 = 아이콘만 → <b>테두리 상자 + 글자</b>(스위치와 같은 높이 36)</li>
  </ol>
  <p><span class="pick">확정</span>검색 아이콘 + <b>종목</b> (2026-11-26 사용자 — 사람들이 종목을 가장 많이 찾는다). 누르면 지금 검색 창 그대로(종목 · 이슈 · 글 다 찾음)</p>
  {strip("종목")}
  <h3>전체 메뉴(서랍)</h3>
  <ol>
    <li><span class="was">미국 홈 · 한국 홈</span> → <b>미국 증시 · 한국 증시</b>(국기 아이콘), 버튼 위 간격 36 → <b>18</b> · 버튼 높이 40 → <b>35</b></li>
    <li>메뉴 줄마다 앞에 <b>아이콘</b>(하단 고정 메뉴와 같은 선 아이콘 · 회색)</li>
    <li><b>Hot Issue = 접기(아코디언)</b> — 처음엔 닫힘, 누르면 펼침</li>
    <li>순서 = 미국 · 한국 증시 리포트 → 증시 시황 → 증시 전망 → Hot Issue → 종목 목록 → Newfact 뉴스 → 주요 인물 발언 → 주식 공부</li>
    <li>뺌 = <span class="was">미국 · 한국 시가총액 상위 10 종목</span> · <span class="was">방송 브리핑</span> · <span class="was">테마</span></li>
    <li>전체 메뉴 가로 320 → <b>360</b>(폰은 화면의 90%까지)</li>
    <li>빠져 있던 메뉴 넣음(노란 <span class="mk-new" style="margin:0">새로 넣음</span>) = <b>증시 시황 · Newfact 뉴스 · 주식 공부</b></li>
    <li><b>소개 · 개인정보처리방침 · 문의 한 줄</b> = 서랍 화면 맨 아래(위에 구분선)(아이콘 없음, 푸터에도 그대로 둡니다 — 개인정보처리방침은 모든 화면에 보여야 해서)</li>
  </ol>
  <p>로그인 뒤 프로필 줄 모양:</p>
  <div class="mk-me2"><i></i>내 별명</div>
  <h3>푸터</h3>
  <ul>
    <li>제목 <span class="was">Newfact 주식 리포트</span> → <b>Newfact</b></li>
    <li>펼침 버튼 · 접힌 글 없앰 → <b>한 문단</b>으로 모두 보임</li>
    <li><span class="was">소개 · 개인정보처리방침 · 문의</span> 줄 = 푸터에서 뺌(전체 메뉴 맨 아래에 있음)</li>
  </ul>
  <p>지금(첫 문장 + 접힌 글):<br><span class="was">{LEAD_OLD} {hidden_p}</span></p>
  <p><span class="pick">추천</span>{FOOT}</p>
  <p style="color:#6B7280;font-size:14px;line-height:20px">순서 = 무엇인가(공개 자료를 규칙으로 정리 · 해설 일부 AI) → 어떻게 쓰나(참고용 · 권유 안 함 · 판단과 책임은 본인) → 로고. `권유하지 않습니다` 와 `판단과 책임` 을 한 문장으로 붙였습니다. 뺀 것(지난 기록과 다를 수 있음 · 애널리스트 의견 · 개별 상담)은 소개 페이지에 있습니다.</p>
</section>"""


def parts(mkt, files):
    """테마 CSS · JS · 글꼴 · 새 헤더 · 새 푸터"""
    idx = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    css = re.search(r"<b:skin version='1.0'><!\[CDATA\[(.*?)\]\]></b:skin>", idx, re.S).group(1)
    js = "\n".join(re.findall(r"//<!\[CDATA\[(.*?)//\]\]>", idx, re.S))
    fonts = "".join(re.findall(r"<link[^>]+fonts\.googleapis\.com/css2[^>]+>", idx)).replace("&amp;", "&")
    logo = re.search(r"<svg class='logo-full'.*?</svg>", idx, re.S).group(0)
    header = (f'<header class="navbar"><div class="nav-left"><div class="section"><div class="widget"><a class="logo" href="{files["us"]}">{logo}</a></div></div>'
              f'{drawer(mkt, files)}</div>'
              '<div class="nav-right">'
              f'<button aria-label="종목 검색 (단축키 /)" class="as-search-btn box" data-as-search="" type="button">{SEARCH_SVG}종목</button>'
              '<button class="nav-toggle" type="button" aria-controls="primary-menu" aria-expanded="false">'
              '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>'
              '<span class="sr-only">메뉴 열기</span></button></div></header>')
    # 펼침 버튼 · 접힌 글 없앰 → 한 문단 · 소개 줄은 전체 메뉴로 옮겨 푸터에서 뺌 (2026-11-26 사용자)
    footer = ('<footer class="site-footer"><div class="footer-disclaimer"><div class="footer-title"><span class="footer-name">' + logo.replace("class='logo-full'", "class='footer-logo'", 1) + '</span></div>'
              f'<p class="footer-lead">{FOOT}</p></div>'
              '<div class="attribution"><div class="footer-row"><p class="footer-copy">© 2026 <span class="brand-word">Newfact</span>. All rights reserved.</p>'
              '<nav class="footer-links" aria-label="사이트 안내"><a class="fl-privacy" href="/p/privacy.html">개인정보처리방침</a></nav></div></div></footer>')
    return css, js, fonts, logo, header, footer


def write(name, html):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", os.path.relpath(p, ROOT))


def build(mkt):
    files = FILES
    css, js, fonts, logo, header, footer = parts(mkt, files)
    title = "전체 메뉴 고침 — " + ("한국 증시 화면" if mkt == "kr" else "미국 증시 화면")
    write(files[mkt], '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
          f'<title>{title}</title>{fonts}<style>{css}</style><style>{CSS}</style></head>'
          f'<body class="no-dashboard" data-home-mkt="{mkt}">{header}<div class="header-bar"></div><main class="main-content">{note(mkt, files, logo, MORE_OLD)}</main>{footer}'
          f'<script>{js}</script><script>if(location.search.indexOf("open=1")>=0)setTimeout(function(){{document.querySelector(".nav-toggle").click()}},300);</script></body></html>')


HOME = {"us": "mock_menu_home_us.html", "kr": "mock_menu_home_kr.html"}
SRC_HOME = {"us": "mock_home_us.html", "kr": "mock_home_kr.html"}   # 홈 목업(mock_home_split.py 가 만든 것)에 새 헤더 · 서랍 · 푸터만 바꿔 끼운다


def build_home(mkt):
    """실제 홈 카드가 있는 홈 목업 + 새 헤더 · 서랍 · 푸터 (2026-11-26 사용자 "실제 홈에서 보고 싶어").
    홈 목업은 미리보기(build_theme --preview) CSS 라 서랍 CSS 가 옛것 — index.html 테마 CSS 를 홈 목업 CSS 뒤에 한 번 더 넣어 맞춘다"""
    src = os.path.join(OUT, SRC_HOME[mkt])
    if not os.path.exists(src):
        import subprocess, sys
        subprocess.run([sys.executable, os.path.join(HERE, "mock_home_split.py")], check=True)
    html = open(src, encoding="utf-8").read()
    css, js, fonts, logo, header, footer = parts(mkt, HOME)
    html, n1 = re.subn(r'<header class="navbar".*?</header>', lambda m: header, html, count=1, flags=re.S)
    html, n2 = re.subn(r'<footer class="site-footer".*?</footer>', lambda m: footer, html, count=1, flags=re.S)
    if not (n1 and n2):
        raise SystemExit(f"홈 목업에서 헤더 {n1} · 푸터 {n2} 자리를 못 찾음")
    html = html.replace("</head>", f"<style>{css}</style><style>{CSS}</style></head>", 1)
    # 검색 상자 = 스위치 왼쪽(테마 검색 JS 와 같은 자리), 홈 목업의 옛 JS 에는 그 장치가 없어 여기서 옮긴다
    html = html.replace("</body>", '<script>(function(){function mv(){var q=document.querySelector(".menu-quick"),b=document.querySelector(".as-search-btn");if(q&&b&&b.parentNode!==q){q.insertBefore(b,q.firstChild);}}'
                        'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){setTimeout(mv,0)});else setTimeout(mv,0);'
                        'if(location.search.indexOf("open=1")>=0)setTimeout(function(){document.querySelector(".nav-toggle").click()},400);})();</script></body>', 1)
    title = "전체 메뉴 고침 — " + ("한국 홈" if mkt == "kr" else "미국 홈")
    html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
    write(HOME[mkt], html)


ITEM_SRC = os.path.join(ROOT, "experiments", "kr-stocks", "output", "mock_005930.html")   # 상세 페이지 = 삼성전자 종목 페이지 목업


def build_item():
    """상세 페이지(종목 · 글) 푸터 확인용 — 종목 페이지 목업(헤더 · 푸터 없이 본문만)에 새 헤더 · 전체 메뉴 · 푸터를 붙인다 (2026-11-26 사용자 "상세 페이지 푸터는 어떻게 확인해?").
    body 가 item-view 라 푸터는 상세 모양(제목 · 저작권 줄 없음)으로 그려진다"""
    if not os.path.exists(ITEM_SRC):
        print("상세 페이지 목업 없음:", ITEM_SRC); return
    html = open(ITEM_SRC, encoding="utf-8").read()
    css, js, fonts, logo, header, footer = parts("kr", HOME)
    b = '<body class="item-view no-dashboard">'
    i = html.index(b) + len(b)
    j = html.index("</main>", i) + len("</main>")
    html = html[:i] + header + '<div class="header-bar"></div>' + html[i:j] + footer + html[j:]
    html = html.replace("</head>", f"<style>{css}</style><style>{CSS}</style></head>", 1)
    html = re.sub(r"<title>.*?</title>", "<title>전체 메뉴 고침 — 상세 페이지(삼성전자)</title>", html, count=1, flags=re.S)
    write("mock_menu_item_kr.html", html)


if __name__ == "__main__":
    build_item()
    for m in ("kr", "us"):
        build(m)
        build_home(m)
