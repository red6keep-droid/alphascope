"""종목 제목 줄 목업 — 제목 꼬리 13/19 · 공유 버튼을 회색 기준 상자 오른쪽으로 (2026-11-11 사용자).

    python experiments/stock-title/mock_stock_title.py     # output/mock_stock_title_kr.html · _us.html

지금 블로그의 실제 종목 페이지(삼성물산 · 엔비디아)를 받아, 이번 테마 변경(build_theme.py CSS · alphaflow-home.html 공유 버튼 IIFE)을 그대로 끝에 붙인다.
테마를 붙여넣으면 같은 모양이 된다. 인터넷 필요.
"""
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
PAGES = {"kr": "https://alpha-scope.blogspot.com/p/samsung-cnt-028260-stock.html",
         "us": "https://alpha-scope.blogspot.com/p/nvidia-nvda-stock.html"}


def theme_bits():
    css_src = open(os.path.join(ROOT, "build_theme.py"), encoding="utf-8").read()
    css = [l for l in css_src.splitlines() if l.startswith(".post-title-sub {") or "[data-report-stamp].has-share" in l]
    js_src = open(os.path.join(ROOT, "alphaflow-home.html"), encoding="utf-8").read()
    m = re.search(r"/\* =+ 종목 페이지 공유 버튼.*?\n\}\)\(\);\n", js_src, re.S)
    return "<style>\n" + "\n".join(css) + "\n</style>\n<script>\n" + m.group(0) + "</script>\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    add = theme_bits()
    for k, url in PAGES.items():
        html = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
        i = html.rfind("</body>")
        path = os.path.join(OUT, f"mock_stock_title_{k}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html[:i] + add + html[i:])
        print("만듦:", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
