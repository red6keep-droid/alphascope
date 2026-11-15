"""홈 나누기 목업 — 미국 화면 · 한국 화면 (2026-11-10 사용자, 홈 수정 H35).

    python experiments/home-split/mock_home_split.py     # output/mock_home_us.html · mock_home_kr.html

실제 홈 미리보기(build_theme.py --preview → preview.html, 가짜 자료 포함)를 그대로 쓰고 두 가지만 바꾼다.
  (1) <body data-home-mkt="us"|"kr"> — alphaflow-home.html 의 H35 장치(CSS · HOME_MKT)가 그 시장만 보인다
  (2) 상단 메뉴 = 미국 · 한국 · 증시 전망 (목업에서는 미국 · 한국이 서로의 목업 파일로 간다)
적용 때: 메뉴는 build_theme.py 의 Blogger 메뉴, data-home-mkt 는 테마가 홈(/) = us · 고정 페이지 /p/korea.html = kr 로 붙인다.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")

FILES = {"us": "mock_home_us.html", "kr": "mock_home_kr.html"}


def nav(mkt, files=FILES):
    cur = lambda m: ' aria-current="page"' if m == mkt else ""
    return (
        '<nav class="menu-items" id="primary-menu" aria-label="주 메뉴">\n'
        # data-bar = 로고 줄 스위치 후보(지금 화면이 아닌 쪽 하나가 국기 data-flag 와 함께 보인다). 나머지(증시 전망)는 메뉴 아이콘 서랍에만 (2026-11-10 사용자)
        f'      <a class="nav-item" href="{files["us"]}"{cur("us")} data-bar="1" data-flag="us">미국</a>\n'
        f'      <a class="nav-item" href="{files["kr"]}"{cur("kr")} data-bar="1" data-flag="kr">한국</a>\n'
        '      <a class="nav-item" href="/p/forecast-list.html">증시 전망</a>\n'
        '    </nav>'
    )


# 가짜 한국 뉴스(목업 전용) — 테마 JS 가 미국 뉴스를 채운 뒤 덮어쓴다. 5건 + 더 보기 안 3건
KR_DUMMY_NEWS = [
    ("반도체 수출 두 달 연속 늘어, 메모리 가격 오름세 이어져", "11월 1~10일 반도체 수출이 1년 전보다 늘었고 D램 고정 거래 가격도 올랐다", "반도체", "11.15 09:12 · 연합뉴스"),
    ("외국인 사흘째 순매수, 코스피 4,000선 다시 넘봐", "", "시장", "11.15 08:40 · 한국경제"),
    ("한국은행 기준금리 동결 전망 우세, 환율 부담 여전", "", "금리", "11.15 08:05 · 매일경제"),
    ("2차전지 소재주 반등, 미국 공장 가동률 회복 기대", "", "2차전지", "11.15 07:31 · 이데일리"),
    ("조선 3사 수주 잔고 사상 최대, 내년 실적 개선 전망", "", "조선", "11.15 07:02 · 머니투데이"),
    ("방산 수출 계약 잇따라, 폴란드 2차 협상 막바지", "", "방산", "11.15 06:44 · 연합뉴스"),
    ("원 · 달러 환율 1,420원대, 수입 물가 부담 커져", "", "환율", "11.15 06:10 · 한국경제"),
    ("바이오 대형주 임상 결과 발표 앞두고 관망세", "", "바이오", "11.14 22:30 · 매일경제"),
]


def _kr_news_js():
    import html as _h
    items = []
    for k, (t, sm, tag, sub) in enumerate(KR_DUMMY_NEWS):
        items.append(f'<article class="news-item"{' hidden="" data-news-more="1"' if k >= 5 else ''}><a href="#">{_h.escape(t)}</a>'
                     + (f'<span class="news-sum">{_h.escape(sm)}</span>' if sm else '')
                     + f'<span class="news-labels"><span class="news-tag">{_h.escape(tag)}</span><span class="news-sub">{_h.escape(sub)}</span></span></article>')
    body = "".join(items).replace("'", "\\'")
    return ("<style>body[data-home-mkt=\"kr\"] .news-section{display:flex!important}body[data-home-mkt=\"kr\"] .news-section .section-note{display:none}</style>"
            "<script>window.addEventListener('load',function(){setTimeout(function(){var l=document.getElementById('news-list');if(!l)return;"
            f"l.innerHTML='{body}';var b=document.getElementById('news-toggle');if(b)b.hidden=false;}},300);}});</script>")


KR_NEWS_JS = _kr_news_js()


def split_html(src, mkt, files=FILES):
    """preview.html → 홈 나누기 화면(mkt = us | kr). 다른 목업(검색 · 질문하기 등)도 이걸 써서 지금 홈 기준으로 맞춘다 (2026-11-10)"""
    html = src
    html, n1 = re.subn(r'<body data-pv-view="home"', f'<body data-pv-view="home" data-home-mkt="{mkt}"', html, count=1)
    html, n2 = re.subn(r'<nav class="menu-items" id="primary-menu".*?</nav>', lambda m: nav(mkt, files), html, count=1, flags=re.S)
    html = html.replace('<a class="logo" href="/">', f'<a class="logo" href="{files["us"]}">', 1)
    # 미리보기 스크립트는 메뉴 첫 줄을 '현재'로 칠한다 — 이 목업에서는 그 시장 메뉴를
    html = html.replace("var homeLink = document.querySelector('.menu-items .nav-item');",
                        "var homeLink = document.querySelector('.menu-items .nav-item[aria-current]');", 1)
    # 미리보기 전환 막대(홈 · 목록 · 글 보기)는 이 목업과 상관없어 숨긴다
    html = html.replace("</head>", "<style>.pv-bar{display:none!important}</style>\n</head>", 1)
    # 증시 전망 카드 자료 = 로컬 forecast_daily 결과(experiments/issue_store/output/forecast/hypo.json) — 홈 화면이 그 나라 전망만 거르는지 본다 (2026-11-12)
    hp = os.path.join(ROOT, "experiments", "issue_store", "output", "forecast", "hypo.json")
    if os.path.exists(hp):
        with open(hp, encoding="utf-8") as f:
            html = html.replace("<head>", "<head>\n<script>window.PV_HYPO = " + f.read().replace("</", "<\\/") + ";</script>", 1)
    ip = os.path.join(ROOT, "experiments", "issue_store", "output", "issue", "issues.json")   # Hot Issue 카드 자료 = issue_watch_daily 결과 (2026-11-16)
    if os.path.exists(ip):
        with open(ip, encoding="utf-8") as f:
            html = html.replace("<head>", "<head>\n<script>window.PV_ISSUES = " + f.read().replace("</", "<\\/") + ";</script>", 1)
    if mkt == "kr":   # 한국 홈 주요 뉴스 — 수집 전이라 테마는 숨김. 목업만 가짜 한국 뉴스로 미국 홈과 같은 꼴을 본다 (2026-11-15 사용자: 한국 홈도 뉴스 넣을 것)
        html = html.replace("</body>", KR_NEWS_JS + "</body>", 1)
    # 주식 공부 배너 — gh-pages 에 올리기 전에는 로컬 그림을 그대로 넣어 본다 (2026-11-15)
    bp = os.path.join(ROOT, "experiments", "course", "banner", "home_banner.webp")
    if os.path.exists(bp):
        import base64
        with open(bp, "rb") as f:
            html = html.replace("https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/study/home_banner.webp",
                                "data:image/webp;base64," + base64.b64encode(f.read()).decode())
    if not (n1 and n2):
        sys.exit(f"바꿀 자리를 못 찾음 (body {n1} · 메뉴 {n2}) — preview.html 구조 확인")
    return html


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env,
                   check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        src = f.read()
    os.makedirs(OUT, exist_ok=True)
    for mkt, name in FILES.items():
        html = split_html(src, mkt)
        title = "홈 나누기 — 미국 화면" if mkt == "us" else "홈 나누기 — 한국 화면"
        html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(html)
        print("만듦:", os.path.join("experiments", "home-split", "output", name))


if __name__ == "__main__":
    main()
