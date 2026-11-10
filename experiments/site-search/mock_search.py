"""블로그 검색 · 질문하기 목업 (2026-11-10 사용자: "로고 영역에 검색 아이콘, 검색하면 해당 내용 + 블로그용 챗봇").

    python experiments/site-search/mock_search.py     # output/mock_search.html

실제 홈 미리보기(build_theme.py --preview → preview.html)에 세 가지를 붙인다.
  (1) 헤더 오른쪽(메뉴 버튼 앞)에 검색 아이콘 — 누르면 검색 창, `/` 키로도 열림
  (2) 오른쪽 아래 `질문하기` 버튼 — 같은 판별 엔진으로 대화처럼 답한다
  (3) 색인(build_search_index.py 결과)을 파일 안에 넣는다 — 적용 때는 jsDelivr 에서 읽는다
시험 주소: mock_search.html?ask=엔비디아 실적 — 검색 창을 그 질문으로 연다.
관련 글은 실제 블로그 공개 피드를 읽는다(인터넷 필요).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output", "mock_search.html")
ICON = ('<button class="as-search-btn" type="button" data-as-search aria-label="검색 (단축키 /)">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg></button>\n\n    ')


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(HERE, "build_search_index.py")], env=env, check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    html = read(os.path.join(ROOT, "preview.html"))
    html, n = re.subn(r'(<button class="nav-toggle")', lambda m: ICON + m.group(1), html, count=1)
    if not n:
        sys.exit("헤더 메뉴 버튼 자리를 못 찾음 — preview.html 구조 확인")
    css = read(os.path.join(HERE, "search.css"))
    html = html.replace("</head>", f"<style>.pv-bar{{display:none!important}}\n{css}</style>\n</head>", 1)
    index = read(os.path.join(HERE, "output", "search_index.json")).replace("</", "<\\/")
    js = read(os.path.join(HERE, "search.js"))
    # 미리보기 안의 가짜 글 자료(JS 문자열)에도 "</body>" 가 있다 — 맨 마지막 진짜 </body> 앞에 넣는다
    head, tail = html.rsplit("</body>", 1)
    html = f"{head}<script>window.AS_SEARCH_INDEX = {index};</script>\n<script>{js}</script>\n</body>{tail}"
    html = re.sub(r"<title>.*?</title>", "<title>검색 · 질문하기 목업</title>", html, count=1, flags=re.S)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
