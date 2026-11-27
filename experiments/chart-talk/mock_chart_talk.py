"""목업 — 종목 페이지 맨 위 차트 아래 `차트 읽기` 버튼. 누르면 캐릭터가 지금 그래프를 대화체로 풀어 준다.

기존 종목 페이지 목업(삼성전자 · 애플)의 그래프 아래에 버튼과 말풍선을 끼워 output/ 에 따로 쓴다. 읽기만 · 쓰기 · AI 0.
문장 = experiments/chart_talk.py (목업 속 그래프와 같은 일봉으로 계산). 상승 흐름 = 상승이 · 하락 흐름 = 하락이 · 팽팽한 날 = 분석이(제안).
분석이 화면은 삼성전자 일봉을 중립이었던 가장 최근 날(2026-11-02)까지만 잘라 그래프와 글을 같이 그날로 맞춘 것.
    python experiments/chart-talk/mock_chart_talk.py
"""
import base64
import html
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(BASE, "..")
sys.path.insert(0, EXP)
import chart_talk as CT  # noqa: E402

STK = os.path.join(EXP, "comments", "output", "stickers")
ALTS = {}   # 고르기 전 시안 — {컷: [(이름표, 컷), …]} 같은 말풍선을 컷만 바꿔 나란히 (2026-11-27 분석이 가운데 = B안 줄다리기 · 상승이 인사 = B안 새싹 화분 확정)
# (원본 목업, 시장, 쓸 파일, 목록 이름, 봉을 여기까지만(없으면 전부))
CASES = [
    ("kr-stocks/output/mock_005930.html", "kr", "mock_chart_talk_down.html", "차트 읽기 버튼 · 하락 흐름 = 하락이 (삼성전자)", None),
    ("stock-radar/output/mock_AAPL.html", "us", "mock_chart_talk_up.html", "차트 읽기 버튼 · 상승 흐름 = 상승이 (애플)", None),
    ("kr-stocks/output/mock_005930.html", "kr", "mock_chart_talk_mid.html", "차트 읽기 버튼 · 팽팽한 날 = 분석이 (제안, 삼성전자 11월 2일까지)", "2026-11-02"),
]
CANDLE = re.compile(r'data-candle="([^"]+)"')
SPOT = 'style="min-height:300px;"></div></span></span>'   # 그래프 카드가 끝나는 자리 — 버튼은 카드 바로 아래 2px

TAG = "margin:14px 0 0;padding-left:6px;font-size:13px;line-height:19px;font-weight:700;color:#B45309;"   # 시안 이름표
JS = """<script>(function(){var b=document.querySelector('[data-ct-btn]'),x=document.querySelector('[data-ct-box]');if(!b||!x)return;
b.addEventListener('click',function(){var open=x.hidden;x.hidden=!open;b.setAttribute('aria-expanded',open?'true':'false');
b.querySelector('[data-ct-word]').textContent=open?'차트 읽기 접기':'차트 읽기';
var rows=x.querySelectorAll('.ct-row');for(var i=0;i<rows.length;i++){rows[i].classList.remove('on');
if(open)(function(r,k){setTimeout(function(){r.classList.add('on');},120+k*500);})(rows[i],i);}});})();</script>"""
ICON_ALTS = []   # 버튼 아이콘 시안 — 고르기 전 (이름표, 그림). 고르면 chart_talk.ICON 으로 올리고 이 표는 비운다


def face(name):
    """전용 컷(chart-talk/chars, 사용자 그림) 먼저, 아직 없는 캐릭터는 댓글 스티커로 임시."""
    own = os.path.join(BASE, "chars", name + ".webp")
    with open(own if os.path.exists(own) else os.path.join(STK, name + ".webp"), "rb") as f:
        return "data:image/webp;base64," + base64.b64encode(f.read()).decode()


# 종목 페이지 탭 밑줄 시안 (2026-11-27: 빨간 밑줄이 회색 선보다 1px 떠 있다 → 1px 내리고 굵기도 견주기).
# 테마 index.html: .rt-tabs = 회색 선 2px 를 border 로(overflow-x:auto 라 안쪽 상자가 border 를 못 넘는다), .rt-tab = 밑줄 3px · margin-bottom −2px
#   → 빨강이 회색 위에 얹혀 1px 떠 보이고, 내리기만 하면 잘려 얇아진다.
# 시안 = 회색 선을 상자 안쪽 바닥 그림자(inset)로 바꿔 빨강이 그 위에 겹치게 — 빨강 아래 끝 = 회색 아래 끝.
# (이름표, 밑줄 굵기, 새 방식?) — 고르면 테마 .rt-tabs · .rt-tab 만 바꾸고 이 표는 비운다
TAB_ALTS = []
# 고른 안을 진짜 탭 줄에 입혀 보기 — 테마에 붙이기 전 목업에서만 (2026-11-27: B안으로 다시 목업). 확정되면 테마 index.html .rt-tabs · .rt-tab 로 옮기고 이 줄은 지운다
TAB_FIX = ("<style>.post-body .rt-tabs{border-bottom:0;padding-bottom:0;box-shadow:inset 0 -2px 0 #eee;}"
           ".post-body .rt-tab{margin-bottom:0;border-bottom-width:4px;position:relative;}"
           ".post-body .rt-tab[aria-selected=\"true\"]{border-bottom-color:transparent;}"
           ".post-body .rt-tab[aria-selected=\"true\"]::after{content:\"\";position:absolute;left:5%;right:5%;bottom:-4px;height:4px;background:var(--accent);}</style>")   # 밑줄 길이 = 탭 폭의 90% (2026-11-27: 10% 줄여)
TABS = ("오늘", "매수의견", "실적", "업계상황", "기업")


def tab_alts():
    rows = ""
    for label, w, new in TAB_ALTS:
        bar = "margin:4px 0 6px;" + ("border-bottom:0;padding-bottom:0;box-shadow:inset 0 -2px 0 #eee;" if new else "")
        sel = f"border-bottom-width:{w};" + ("margin-bottom:0;" if new else "")
        btns = "".join(f'<button class="rt-tab" type="button" aria-selected="{str(i == 0).lower()}" style="{sel if i == 0 else ("margin-bottom:0;" if new else "")}">{n}</button>'
                       for i, n in enumerate(TABS))
        rows += f'<div style="{TAG}">{html.escape(label)}</div><div class="rt-tabs" style="{bar}">{btns}</div>'
    return f'<div style="margin:18px 0 0;">{rows}</div>' if rows else ""


def icon_alts():
    """아이콘 시안 줄 — 진짜 버튼과 같은 꼴(눌러도 안 열림)에 아이콘만 바꿔 이름표와 함께."""
    rows = "".join(f'<div style="{TAG}">{html.escape(label)}</div><div class="ct-btn" style="cursor:default;"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">{body}</svg><span>차트 읽기</span>{CT.ARROW}</div>'
                   for label, body in ICON_ALTS)
    return f'<div style="margin:18px 0 0;">{rows}</div>' if rows else ""


def block(t, page):
    hook = lambda x, who: "".join(f'<div class="ct-row" style="{TAG}">{html.escape(label)}</div>' for label, _ in ALTS.get(who, []))   # noqa: E731
    js = "" if "__asChartTalk" in page else JS   # 다시 그린 목업은 봉차트 스크립트(candle_chart.js)가 여닫기를 맡는다 — 둘이면 두 번 뒤집힌다
    return CT.render(t, img=face, rows_hook=hook) + (icon_alts() if t["mood"] == "up" else "") + (tab_alts() if t["mood"] == "down" else "") + js


def main():
    for src, market, out, title, until in CASES:
        page = open(os.path.join(EXP, src), encoding="utf-8").read()
        m = CANDLE.search(page)
        d = json.loads(html.unescape(m.group(1)))
        if until:
            d["bars"] = [b for b in d["bars"] if b[0] <= until]
            page = page[:m.start(1)] + html.escape(json.dumps(d, ensure_ascii=False, separators=(",", ":"))) + page[m.end(1):]
        bars = [{"day": b[0], "open": b[1], "high": b[2], "low": b[3], "close": b[4], "volume": b[5]} for b in d["bars"]]
        t = CT.talk(bars, d["name"], market)
        page = re.sub(r"<!--ct-->.*?<!--/ct-->", "", page, flags=re.S)   # 다시 그린 종목 목업에 이미 든 차트 읽기(page_block) — 빼고 이 목업 것으로
        assert page.count(SPOT) == 1, src
        page = page.replace(SPOT, SPOT + block(t, page))
        page = page.replace("</head>", TAB_FIX + "</head>", 1)
        page = re.sub(r"(20\d\d-\d\d-\d\d)\s*사용자\b", r"\1", page)   # 베껴 온 테마 주석의 경위 꼴 — 공개 저장소 검사(.githooks) 기준
        page = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "", page)   # 베껴 온 테마의 Firebase 웹 키는 목업에 싣지 않는다(목업 댓글은 동작 X)
        page = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", page, count=1)
        with open(os.path.join(BASE, "output", out), "w", encoding="utf-8") as f:
            f.write(page)
        print(out, t["who"], round(t["net"], 2), len(t["lines"]), "줄", "|", *[x["text"] for x in t["lines"]], sep="\n  ")


if __name__ == "__main__":
    main()
