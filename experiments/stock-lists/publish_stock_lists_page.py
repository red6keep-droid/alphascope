"""하단 메뉴 `종목` 고정 페이지 /p/stock-lists.html 하나 만들기 · 고치기.

    python experiments/stock-lists/publish_stock_lists_page.py --dry     # 본문만 만들어 보기 (output/stock_lists_page.html)
    python experiments/stock-lists/publish_stock_lists_page.py           # Blogger 에 올리기 (처음 한 번 + stock_lists.js 를 고칠 때만)
    python experiments/stock-lists/publish_stock_lists_page.py --mock    # 로컬 목업 output/mock_stock-lists-live-us.html · -kr (실제 스크립트 + 로컬 목록 파일)

본문 = 탭 뼈대(h2 data-tab 여섯 개 + 빈 칸) + stock_lists.js. 테마를 고치지 않는다 — 탭은 테마가 h2 로 만들고, 목록은 스크립트가 목록 파일(build_lists.py)로 채운다.
    python experiments/stock-lists/publish_stock_lists_page.py --lists /tmp/qd   # 간단 종목 실행(quick-data.yml)이 목록 파일을 만든 뒤 — 고치기만(새 페이지 X)

Blogger 쓰기 = 간단 종목 실행마다 이 페이지 고치기 최대 1번(새 글 · 새 페이지 만들기 0). 종목 분석 게시기(stock-radar/publish_pages.publish)를 그대로 쓴다(해시가 같으면 건너뜀).
검색: 탭 목록은 스크립트로만 그려 HTML 에 종목 링크가 없다 → 탭 밖 맨 아래 `전체 종목 · 업종별`(all_links) 정적 링크로 검색 로봇이 종목 페이지를 찾는다. 설정(robots · noindex)은 바꾸지 않는다.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP, os.path.join(EXP, "stock-radar")]

KEY = "stock-lists"   # 주소 /p/stock-lists.html — 처음 만들 때 제목 = 이 글자(Blogger 가 제목으로 주소를 정한다), 바로 TITLE 로 바꾼다
TITLE = "종목 모아보기"   # 옛 `종목`
OUT = os.path.join(HERE, "output")
BODY = os.path.join(OUT, "stock_lists_page.html")
TABS = [("watch", "관심"), ("move", "오늘 움직임"), ("theme", "테마"), ("sector", "업종"), ("cap", "시가총액"), ("etf", "ETF")]
FIRST_TAB = 1   # 처음 열리는 탭 = 오늘 움직임 (관심 종목이 없을 때, 기획 9-4). 관심 종목이 있으면 관심 탭(본문 맨 앞 스크립트)

# 묶음 줄 = 홈 `테마 종목` 아래 줄(#watch-tabs) 모양 — alphaflow-home.html `.home-cards #watch-tabs` 를 옮긴 것. 기준일 = 제목 줄(.post-title-meta) 공유 버튼 앞
CSS = ("<style>[data-sl-panel][hidden]{display:none !important;}"
       ".sl-joined{display:flex;gap:0 !important;padding:0 !important;margin:0 0 12px;overflow-x:auto;scrollbar-width:none;}.sl-joined::-webkit-scrollbar{display:none;}"
       ".sl-joined .seg{flex:1 0 auto;padding:6px 14px;border:1px solid #E2E8F0;border-radius:0;background:#fff;color:#4B5563;font-weight:400;text-align:center;}"
       ".sl-joined .seg+.seg{border-left:0;}.sl-joined .seg:first-child{border-radius:7px 0 0 7px;}.sl-joined .seg:last-child{border-radius:0 7px 7px 0;}"
       ".sl-joined .seg:only-child{border-radius:7px;}"
       ".sl-joined .seg[aria-selected=\"true\"]{background:#fff;color:#111;font-weight:700;box-shadow:inset 0 0 0 1px #111;}"
       ".post-body .rt-tab .sl-tab-star{display:inline-block;width:16px;height:16px;margin:0 4px 0 0;vertical-align:-2px;}"   # 관심 탭 앞 별 — 채운 노랑 = 종목 제목 옆 담긴 별과 같은 색
       ".sl-title-day{flex:none;font-size:13px;line-height:19px;font-weight:400;color:#6B7280;white-space:nowrap;letter-spacing:0;}"
       "#sl-day{margin:0 0 8px;padding-left:6px;text-align:right;}"
       # 히트맵(테마 · 업종 묶음 고르기) — mock_stock_lists.PAGE_CSS 의 .hm 과 같게
       ".hm{position:relative;margin:0 0 14px;background:#fff;}"
       ".hm-c{position:absolute;box-sizing:border-box;margin:0;padding:4px;border:2px solid #fff;border-radius:6px;font:inherit;cursor:pointer;"
       "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;overflow:hidden;text-align:center;-webkit-tap-highlight-color:transparent;}"
       ".hm-n{display:block;max-width:100%;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
       ".hm-p{display:block;font-weight:400;white-space:nowrap;}"
       ".hm-c[aria-selected=\"true\"]{box-shadow:inset 0 0 0 1.5px var(--hm-fg);}"
       ".hm-c:active{filter:brightness(.94);}"
       # 관심 탭 편집 모드 · 검색 팝업 · 알림 — mock_stock_lists.PAGE_CSS · TOAST_CSS 와 같게
       "[data-sl-watch] [data-row-link]{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-rm]{display:inline-block !important;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-grip]{display:inline-flex !important;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-price]{display:none !important;}"
            "[data-sl-editing] [data-sl-watch] [data-row-link]{cursor:default;}"
            "[data-sl-editing] [data-sl-foot]{visibility:hidden;}"
            "[data-sl-watch] .sl-drag{background:#F8FAFC;box-shadow:0 4px 14px rgba(15,23,42,.12);position:relative;z-index:2;}"
            "[data-sl-bar]{display:none;position:fixed;left:0;right:0;bottom:0;z-index:50;gap:10px;padding:10px 16px calc(10px + env(safe-area-inset-bottom));background:#fff;border-top:1px solid #E2E8F0;box-sizing:border-box;}"
            "[data-sl-editing] [data-sl-bar]{display:flex;}"
            ".sl-bar-btn{flex:1 1 0;height:48px;border-radius:8px;border:1px solid #CBD5E1;background:#fff;color:#111;font:inherit;font-size:16px;line-height:24px;font-weight:700;cursor:pointer;}"
            ".sl-bar-main{background:#111;border-color:#111;color:#fff;}"
            "[data-sl-editing] .sl-toast{bottom:calc(84px + env(safe-area-inset-bottom)) !important;}"
            ".sl-pop{position:fixed;left:0;right:0;top:-100px;bottom:-100px;z-index:1000;display:flex;justify-content:center;align-items:center;padding:100px 16px;box-sizing:border-box;background:rgba(15,23,42,.45);}"
            ".sl-pop.sl-top-pop{align-items:flex-start;padding-top:calc(100px + 6vh);}"
            ".sl-pop>div{width:100%;max-width:520px;max-height:min(640px,80vh);display:flex;flex-direction:column;background:#fff;border-radius:12px;overflow:hidden;}"
            ".sl-pop.sl-short>div{max-width:400px;}"
            ".sl-pop-head{flex:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 12px 12px 18px;border-bottom:1px solid #E2E8F0;font-size:19px;line-height:28px;font-weight:700;color:#111;}"
            ".sl-x{flex:none;width:32px;height:32px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;}"
            ".sl-x:hover{border-color:#111;}"
            ".sl-pop-body{flex:1 1 auto;overflow:auto;padding:14px 18px 18px;}"
            ".sl-q{width:100%;box-sizing:border-box;height:44px;border:1px solid #CBD5E1;border-radius:8px;padding:0 12px 0 38px;font:inherit;font-size:16px;color:#111;background:#fff url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='8.5' cy='8.5' r='5.5' fill='none' stroke='%239CA3AF' stroke-width='1.8'/%3E%3Cpath d='M13 13l4 4' stroke='%239CA3AF' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E\") no-repeat 12px 50%/18px;outline:none;}"
            ".sl-q:focus{border-color:#111;}"
            ".sl-res-h{font-size:15px;line-height:22px;font-weight:700;color:#111;margin:18px 0 4px;}"
            ".sl-res{display:flex;align-items:center;gap:10px;padding:12px 0;cursor:pointer;-webkit-tap-highlight-color:transparent;}"
            ".sl-res+.sl-res{border-top:1px solid #E2E8F0;}"
            ".sl-res-star{flex:none;width:32px;height:32px;display:flex;align-items:center;justify-content:center;margin-left:auto;color:#9CA3AF;}"
            ".sl-res-star[aria-pressed=\"true\"]{color:#F5B400;}"
       ".sl-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;z-index:60;display:flex;gap:14px;align-items:center;padding:12px 16px;"
             "background:#111;color:#fff;border-radius:10px;font-size:15px;line-height:22px;box-shadow:0 6px 20px rgba(0,0,0,.2);white-space:nowrap;}"
             ".sl-toast a{color:#FCD34D;font-weight:700;text-decoration:none;}"
             "@media (max-width:900px){.sl-toast{bottom:calc(85px + env(safe-area-inset-bottom));}}"
       "</style>")


ALL_CSS = ("<style>.sl-all{margin:28px 0 8px;padding:16px 0 0;border-top:1px solid #E2E8F0;}"
           ".sl-all h3{margin:0 0 4px;padding-left:6px;font-size:19px;line-height:28px;font-weight:700;color:#111;}"
           ".sl-all-note{margin:0 0 12px;padding-left:6px;font-size:14px;line-height:20px;color:#6B7280;}"
           ".sl-all-g{padding:10px 6px;border-top:1px solid #F1F5F9;}"
           ".sl-all-h{font-size:16px;line-height:24px;font-weight:700;color:#111;margin:0 0 4px;}"
           ".sl-all-h span{font-size:14px;font-weight:400;color:#6B7280;margin-left:4px;}"
           ".sl-all-l{font-size:15px;line-height:26px;color:#9CA3AF;}"
           ".sl-all-l a{color:#111;text-decoration:none;border-bottom:1px dotted #CBD5E1;}"
           ".sl-all-l a:hover{border-bottom-color:#111;}"
           ".sl-all-l i{font-style:normal;color:#6B7280;}"   # 아직 페이지가 없는 종목 = 이름만(회색)
           ".sl-all details{display:inline;}.sl-all summary{display:inline;cursor:pointer;color:#6B7280;font-size:14px;list-style:none;}"
           ".sl-all summary::-webkit-details-marker{display:none;}.sl-all details[open] summary{display:none;}"
           "</style>")
SHOW = 5   # 업종마다 처음 보이는 종목 수 — 나머지는 접기(상한으로 버리지 않음, 링크는 접힌 채로도 HTML 에 있다)


def all_links(lists):
    """전체 종목 정적 링크 — 시장마다 업종별(시가총액 순) + ETF. 탭 밖 글 맨 아래(data-related)에 둔다.
    목적 = 검색 로봇이 사이트맵 말고도 종목 페이지를 찾는 길(목록 탭은 스크립트로만 그려 HTML 에 링크가 없다).
    lists = {"us": _lists.json, "kr": _lists.json}. 나라는 위 목록과 같게 한 나라만 보인다(스크립트가 다른 나라 묶음을 숨김)."""
    import html as H
    import design_kit as dk
    esc = H.escape
    for d in lists.values():   # 목록 파일에 주소가 없는 종목 = 모든 화면이 쓰는 주소 찾기(dk.stock_url)로 한 번 더
        for r in d.get("rows", []) + d.get("etf", []):
            if not r.get("u"):
                u = dk.stock_url(r.get("t"))
                if u:
                    r["u"] = u.replace("https://www.newfact.app", "")
    out = []
    for m, label in (("us", "미국"), ("kr", "한국")):
        d = lists.get(m)
        if not d:
            continue
        groups = {}
        for r in d.get("rows", []):
            groups.setdefault(r.get("s") or "기타", []).append(r)
        order = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if d.get("etf"):
            order.append(("ETF", d["etf"]))

        def item(r):
            nm = esc(r.get("n") or r.get("t", ""))
            return f'<a href="{esc(r["u"])}">{nm}</a>' if r.get("u") else f"<i>{nm}</i>"

        gs = []
        for sec, rs in order:
            rs = sorted(rs, key=lambda r: -(r.get("c") or 0))
            head, rest = rs[:SHOW], rs[SHOW:]
            line = " · ".join(item(r) for r in head)
            if rest:
                line += (f' · <details><summary>나머지 {len(rest)}개 보기 ›</summary>'
                         + " · ".join(item(r) for r in rest) + "</details>")
            gs.append(f'<div class="sl-all-g"><div class="sl-all-h">{esc(sec)}<span>{len(rs)}</span></div><div class="sl-all-l">{line}</div></div>')
        n = len(d.get("rows", [])) + len(d.get("etf", []))
        out.append(f'<section class="sl-all" data-sl-all="{m}"><h3>{label} 전체 종목 · 업종별</h3>'
                   f'<p class="sl-all-note">{label} 종목 {n}개 · 업종마다 시가총액 순</p>{"".join(gs)}</section>')
    if not out:
        return ""
    hide = ("<script>(function(){var q='';try{q=(new URLSearchParams(location.search).get('m')||'').toLowerCase();}catch(e){}"
            "if(q!=='us'&&q!=='kr'){try{q=localStorage.getItem('as-home-mkt')||'';}catch(e){}}if(q!=='us'&&q!=='kr')q='us';"
            "[].forEach.call(document.querySelectorAll('[data-sl-all]'),function(s){if(s.getAttribute('data-sl-all')!==q)s.hidden=true;});})();</script>")
    return ALL_CSS + f'<div data-related="1">{"".join(out)}</div>' + hide


def body(local="", links=""):
    js = open(os.path.join(HERE, "stock_lists.js"), encoding="utf-8").read()
    if "</script" in js:
        sys.exit("stock_lists.js 안에 </script — 본문이 끊긴다")
    wait = '<p style="font-size:15px;line-height:24px;color:#6B7280;margin:12px 0;padding-left:6px;">불러오는 중…</p>'
    # 탭 해시가 없으면 오늘 움직임 탭으로 — 테마 탭 장치(글 끝에서 돈다)보다 먼저 주소를 고친다
    # 이 나라 관심 종목(브라우저 as-watch)이 있으면 관심 탭(0), 없으면 오늘 움직임(FIRST_TAB) — 기획 9-4 (2026-11-19 관심 종목 적용)
    pre = ("<script>if(!/#tab-/.test(location.hash))try{var q=(new URLSearchParams(location.search).get('m')||'').toLowerCase(),k;"
           "if(q!=='us'&&q!=='kr'){try{q=localStorage.getItem('as-home-mkt')||'';}catch(e){}}if(q!=='us'&&q!=='kr')q='us';"
           "try{k=(JSON.parse(localStorage.getItem('as-watch')||'[]')||[]).some(function(x){return x&&x.m===q;});}catch(e){k=false;}"
           f"history.replaceState(null,'',location.pathname+location.search+'#tab-'+(k?0:{FIRST_TAB}));}}catch(e){{}}</script>")
    skel = "".join(f'<h2 data-tab="{name}">{name}</h2><div id="sl-{key}">{wait}</div>' for key, name in TABS)
    return (pre + CSS + f'<div id="as-lists"{f" data-local={chr(34)}{local}{chr(34)}" if local else ""}></div><div id="sl-day" hidden></div>'
            '<span data-lead="1" hidden></span>'   # 테마 탭 장치가 첫 칸의 카드를 머리로 끌어올리지 않게 (목업에서 확인)
            + skel + links + f"\n<script>\n{js}\n</script>\n")


PAGES_URL = "https://alpha-scope.pages.dev/"   # 목록 파일이 이 실행에 없는 나라는 어제 올린 것 (stock_lists.js 가 읽는 곳과 같다)


def load_lists(folder):
    """{"us": …, "kr": …} — folder/<시장>/_lists.json, 없으면 Pages 에서. 둘 다 못 구한 나라는 빠진다(그 나라 묶음 없이)."""
    import json
    import urllib.request
    out = {}
    for m in ("us", "kr"):
        p = os.path.join(folder, m, "_lists.json")
        try:
            if os.path.isfile(p):
                out[m] = json.load(open(p, encoding="utf-8"))
            else:
                req = urllib.request.Request(f"{PAGES_URL}{m}/_lists.json", headers={"User-Agent": "alphascope"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    out[m] = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[종목 페이지] {m} 목록 못 읽음 — 그 나라 전체 종목 묶음 없이: {e}")
    return out


def mock():
    """로컬 목업 — 실제 스크립트 그대로, 목록 파일은 output/lists/<시장>/_lists.json(build_lists.py --out output/lists)."""
    import design_kit as dk
    links = all_links(load_lists(os.path.join(OUT, "lists")))
    for m in ("us", "kr"):
        b = body(local="lists/", links=links.replace("location.search", f"'?m={m}'")).replace("location.pathname+location.search+", f"location.pathname+'?m={m}'+")
        path = dk.write_mock(b, os.path.join(OUT, f"mock_stock-lists-live-{m}.html"), TITLE)
        print(f"[종목 페이지] 목업 {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--lists", default="", help="목록 파일 폴더(<폴더>/<시장>/_lists.json, 간단 종목 실행 = /tmp/qd). 없는 나라는 Pages 에서")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.mock:
        return mock()
    links = all_links(load_lists(a.lists or os.path.join(OUT, "lists")))
    open(BODY, "w", encoding="utf-8").write(body(links=links))
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
