"""간단 정보 고정 페이지 `stock-quick` 하나 만들기 · 고치기 (2026-11-14, 기획 6-6).

    python experiments/stock-quick/publish_quick_page.py --dry     # 본문만 만들어 보기
    python experiments/stock-quick/publish_quick_page.py           # Blogger 에 올리기 (처음 한 번 + quick_page.js 를 고칠 때만)

본문 = 빈 자리(#as-quick) + quick_page.js 를 본문 안에 그대로. 테마를 고치지 않는다(테마 붙여넣기 필요 없음).
종목 853개 내용은 이 페이지에 들어가지 않는다 — 방문자 브라우저가 주소 뒤 ?s= 로 quick-data 브랜치에서 받아 끼워 넣는다.
Blogger 쓰기 = 처음 1번(이후 JS 를 고칠 때만). 종목 분석 게시기(stock-radar/publish_pages.publish)를 그대로 쓴다(해시가 같으면 건너뜀).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP, os.path.join(EXP, "stock-radar")]
import publish_pages as PP  # noqa: E402
import universe as U  # noqa: E402

KEY = "stock-quick"
TITLE = "간단 종목 정보"
URL = f"{U.BLOG}/p/{KEY}.html"
DATA = os.path.join(HERE, "data")
BODY = os.path.join(HERE, "output", "stock_quick_page.html")


def body():
    js = open(os.path.join(HERE, "quick_page.js"), encoding="utf-8").read()
    if "</script" in js:
        sys.exit("quick_page.js 안에 </script — 본문이 끊긴다")
    return (f'<div id="as-quick" data-list="{U.LIST_URL}"></div>\n'
            f'<p style="font-size:13px;line-height:19px;color:#6B7280;margin:16px 0 0;padding-left:6px;">'
            f'종목 목록에서 종목을 누르면 이 페이지에 그 종목의 가격 · 기술지표 · 일정이 열립니다.</p>\n'
            f'<script>\n{js}\n</script>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(BODY), exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    open(BODY, "w", encoding="utf-8").write(body())
    PP.targets = lambda only=None: [(KEY, TITLE, "stock quick", URL, BODY)]
    PP.HASHES = os.path.join(DATA, "page_hashes.json")
    PP.PAGES_LIVE = os.path.join(DATA, "pages_live.json")
    PP._body = lambda path: open(path, encoding="utf-8").read()
    ok = PP.publish(dry=a.dry)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
