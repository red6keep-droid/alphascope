"""하단 메뉴 `종목` 고정 페이지 /p/stock-lists.html 하나 만들기 · 고치기 (2026-11-17 사용자 "1단계 구현 진행해").

    python experiments/stock-lists/publish_stock_lists_page.py --dry     # 본문만 만들어 보기 (output/stock_lists_page.html)
    python experiments/stock-lists/publish_stock_lists_page.py           # Blogger 에 올리기 (처음 한 번 + stock_lists.js 를 고칠 때만)
    python experiments/stock-lists/publish_stock_lists_page.py --mock    # 로컬 목업 output/mock_stock-lists-live-us.html · -kr (실제 스크립트 + 로컬 목록 파일)

본문 = 탭 뼈대(h2 data-tab 여섯 개 + 빈 칸) + stock_lists.js. 테마를 고치지 않는다 — 탭은 테마가 h2 로 만들고, 목록은 스크립트가 목록 파일(build_lists.py)로 채운다.
Blogger 쓰기 = 처음 1번(이후 스크립트를 고칠 때만). 종목 분석 게시기(stock-radar/publish_pages.publish)를 그대로 쓴다(해시가 같으면 건너뜀).
검색: 본문에 글이 거의 없는 목록 페이지 — 검색 유입은 시총 상위 10 · 종목 페이지가 맡는다(기획 4절). 설정(robots · noindex)은 바꾸지 않는다.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP, os.path.join(EXP, "stock-radar")]

KEY = "stock-lists"   # 주소 /p/stock-lists.html — 처음 만들 때 제목 = 이 글자(Blogger 가 제목으로 주소를 정한다), 바로 TITLE 로 바꾼다
TITLE = "종목 모아보기"   # 옛 `종목` (2026-11-18 사용자 "제목을 좀 더", 목업 mock_stock_lists.write 와 같게)
OUT = os.path.join(HERE, "output")
BODY = os.path.join(OUT, "stock_lists_page.html")
TABS = [("watch", "관심"), ("move", "오늘 움직임"), ("theme", "테마"), ("sector", "업종"), ("cap", "시가총액"), ("etf", "ETF")]
FIRST_TAB = 1   # 처음 열리는 탭 = 오늘 움직임 (관심 종목이 없을 때, 기획 9-4). 1단계 관심 탭 = 최근 본 종목

# 묶음 줄 = 홈 `테마 종목` 아래 줄(#watch-tabs) 모양 — alphaflow-home.html `.home-cards #watch-tabs` 를 옮긴 것. 기준일 = 제목 줄(.post-title-meta) 공유 버튼 앞
CSS = ("<style>[data-sl-panel][hidden]{display:none !important;}"
       ".sl-joined{display:flex;gap:0 !important;padding:0 !important;margin:0 0 12px;overflow-x:auto;scrollbar-width:none;}.sl-joined::-webkit-scrollbar{display:none;}"
       ".sl-joined .seg{flex:1 0 auto;padding:6px 14px;border:1px solid #E2E8F0;border-radius:0;background:#fff;color:#4B5563;font-weight:400;text-align:center;}"
       ".sl-joined .seg+.seg{border-left:0;}.sl-joined .seg:first-child{border-radius:7px 0 0 7px;}.sl-joined .seg:last-child{border-radius:0 7px 7px 0;}"
       ".sl-joined .seg:only-child{border-radius:7px;}"
       ".sl-joined .seg[aria-selected=\"true\"]{background:#fff;color:#111;font-weight:700;box-shadow:inset 0 0 0 1px #111;}"
       ".sl-title-day{flex:none;font-size:14px;line-height:20px;font-weight:400;color:#6B7280;white-space:nowrap;letter-spacing:0;}"
       "#sl-day{margin:0 0 8px;padding-left:6px;text-align:right;}"
       # 히트맵(테마 · 업종 묶음 고르기) — mock_stock_lists.PAGE_CSS 의 .hm 과 같게 (2026-11-18 사용자)
       ".hm{position:relative;margin:0 0 14px;background:#fff;}"
       ".hm-c{position:absolute;box-sizing:border-box;margin:0;padding:4px;border:2px solid #fff;border-radius:6px;font:inherit;cursor:pointer;"
       "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;overflow:hidden;text-align:center;-webkit-tap-highlight-color:transparent;}"
       ".hm-n{display:block;max-width:100%;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
       ".hm-p{display:block;font-weight:400;white-space:nowrap;}"
       ".hm-c[aria-selected=\"true\"]{box-shadow:inset 0 0 0 1.5px var(--hm-fg);}"
       ".hm-c:active{filter:brightness(.94);}</style>")


def body(local=""):
    js = open(os.path.join(HERE, "stock_lists.js"), encoding="utf-8").read()
    if "</script" in js:
        sys.exit("stock_lists.js 안에 </script — 본문이 끊긴다")
    wait = '<p style="font-size:15px;line-height:24px;color:#6B7280;margin:12px 0;padding-left:6px;">불러오는 중…</p>'
    # 탭 해시가 없으면 오늘 움직임 탭으로 — 테마 탭 장치(글 끝에서 돈다)보다 먼저 주소를 고친다
    pre = f"<script>if(!/#tab-/.test(location.hash))try{{history.replaceState(null,'',location.pathname+location.search+'#tab-{FIRST_TAB}');}}catch(e){{}}</script>"
    skel = "".join(f'<h2 data-tab="{name}">{name}</h2><div id="sl-{key}">{wait}</div>' for key, name in TABS)
    return (pre + CSS + f'<div id="as-lists"{f" data-local={chr(34)}{local}{chr(34)}" if local else ""}></div><div id="sl-day" hidden></div>'
            '<span data-lead="1" hidden></span>'   # 테마 탭 장치가 첫 칸의 카드를 머리로 끌어올리지 않게 (목업에서 확인)
            + skel + f"\n<script>\n{js}\n</script>\n")


def mock():
    """로컬 목업 — 실제 스크립트 그대로, 목록 파일은 output/lists/<시장>/_lists.json(build_lists.py --out output/lists)."""
    import design_kit as dk
    for m in ("us", "kr"):
        b = body(local="lists/").replace("location.pathname+location.search+", f"location.pathname+'?m={m}'+")
        path = dk.write_mock(b, os.path.join(OUT, f"mock_stock-lists-live-{m}.html"), TITLE)
        print(f"[종목 페이지] 목업 {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.mock:
        return mock()
    open(BODY, "w", encoding="utf-8").write(body())
    import publish_pages as PP
    import universe as U
    PP.targets = lambda only=None: [(KEY, TITLE, KEY, f"{U.BLOG}/p/{KEY}.html", BODY)]
    PP.HASHES = os.path.join(HERE, "data", "page_hashes.json")
    PP.PAGES_LIVE = os.path.join(HERE, "data", "pages_live.json")
    PP._body = lambda path: open(path, encoding="utf-8").read()
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    ok = PP.publish(dry=a.dry)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
