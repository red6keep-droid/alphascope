"""늦은 날 기준일 상자 목업 — 간단 종목 페이지의 맨 위 안내 상자만 `늦음` 모양으로 바꾼 것.

    python experiments/stock-quick/mock_late_stamp.py

mock_quick_page.py 가 복사해 둔 실제 조각(output/quick-data/)을 output/quick-data-late/ 로 옮겨 상자만 dk.price_stamp(..., late=True) 로 바꾸고,
같은 페이지 틀(quick_page.js)로 mock_qpage_late_<코드>.html 을 만든다. 평소 모양 = 옆의 mock_qpage_<코드>.html.
목업 서버(8800)로 열어야 조각을 받아 온다.
"""

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
import design_kit as dk  # noqa: E402
import candle_chart as CC  # noqa: E402

OUT = os.path.join(HERE, "output")
SRC = os.path.join(OUT, "quick-data")
DST = os.path.join(OUT, "quick-data-late")
SAMPLES = [("us", "UBER", "우버 UBER 주가"), ("kr", "011200", "HMM 주가")]
STAMP = re.compile(r'<p data-report-stamp="1".*?</p>', re.S)
DAY = re.compile(r"<span>(\d+)월 (\d+)일 (종가|새벽 마감) 기준")


def late_fragment(html):
    m = STAMP.search(html)
    if not m:
        raise SystemExit("조각에 기준일 상자가 없음")
    d = DAY.search(m.group(0))
    day_text, close = f"{d.group(1)}월 {d.group(2)}일", d.group(3)
    return html[:m.start()] + dk.report_stamp(day_text, "", close=close, late=True) + html[m.end():]


def main():
    if os.path.exists(DST):
        shutil.rmtree(DST)
    for d in ("us", "kr"):
        os.makedirs(os.path.join(DST, d), exist_ok=True)
    for fn in ("version.json", "bench.json"):
        if os.path.exists(os.path.join(SRC, fn)):
            shutil.copy(os.path.join(SRC, fn), os.path.join(DST, fn))
    js = open(os.path.join(HERE, "quick_page.js"), encoding="utf-8").read()
    for d, code, title in SAMPLES:
        html = open(os.path.join(SRC, d, code + ".html"), encoding="utf-8").read()
        open(os.path.join(DST, d, code + ".html"), "w", encoding="utf-8").write(late_fragment(html))
        body = (f'<div id="as-quick" data-local="quick-data-late/" data-default="{code}" data-list-us="/stock-radar/output/mock_list.html" '
                f'data-list-kr="/kr-stocks/output/mock_list.html"></div><script>{js}</script>' + CC.SCRIPT)
        print("만듦:", dk.write_mock(body, os.path.join(OUT, f"mock_qpage_late_{code}.html"), title))


if __name__ == "__main__":
    main()
