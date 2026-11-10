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


def nav(mkt):
    cur = lambda m: ' aria-current="page"' if m == mkt else ""
    return (
        '<nav class="menu-items" id="primary-menu" aria-label="주 메뉴">\n'
        f'      <a class="nav-item" href="{FILES["us"]}"{cur("us")}>미국</a>\n'
        f'      <a class="nav-item" href="{FILES["kr"]}"{cur("kr")}>한국</a>\n'
        '      <a class="nav-item" href="/p/forecast-list.html">증시 전망</a>\n'
        '    </nav>'
    )


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env,
                   check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        src = f.read()
    os.makedirs(OUT, exist_ok=True)
    for mkt, name in FILES.items():
        html = src
        html, n1 = re.subn(r'<body data-pv-view="home"', f'<body data-pv-view="home" data-home-mkt="{mkt}"', html, count=1)
        html, n2 = re.subn(r'<nav class="menu-items" id="primary-menu".*?</nav>', lambda m: nav(mkt), html, count=1, flags=re.S)
        html = html.replace('<a class="logo" href="/">', f'<a class="logo" href="{FILES["us"]}">', 1)
        # 미리보기 스크립트는 메뉴 첫 줄을 '현재'로 칠한다 — 이 목업에서는 그 시장 메뉴를
        html = html.replace("var homeLink = document.querySelector('.menu-items .nav-item');",
                            "var homeLink = document.querySelector('.menu-items .nav-item[aria-current]');", 1)
        # 미리보기 전환 막대(홈 · 목록 · 글 보기)는 이 목업과 상관없어 숨긴다
        html = html.replace("</head>", "<style>.pv-bar{display:none!important}</style>\n</head>", 1)
        title = "홈 나누기 — 미국 화면" if mkt == "us" else "홈 나누기 — 한국 화면"
        html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
        if not (n1 and n2):
            sys.exit(f"바꿀 자리를 못 찾음 (body {n1} · 메뉴 {n2}) — preview.html 구조 확인")
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(html)
        print("만듦:", os.path.join("experiments", "home-split", "output", name))


if __name__ == "__main__":
    main()
