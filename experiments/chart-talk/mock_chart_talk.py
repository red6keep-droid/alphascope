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
FACE = {"up": ("up_hello", "up_mid", "up_bye"), "down": ("down_hello", "down_mid", "down_bye"),
        "mid": ("mid_hello", "mid_mid", "mid_bye")}   # 인사 · 가운데 · 끝인사 컷 = chart-talk/chars (사용자 그림)
ALTS = {}   # 고르기 전 시안 — {컷: [(이름표, 컷), …]} 같은 말풍선을 컷만 바꿔 나란히 (2026-11-27 분석이 가운데 = B안 줄다리기 · 상승이 인사 = B안 새싹 화분 확정)
TONE = {"up": ("#FFF7EE", "#FEE6CA"), "down": ("#EFF6FF", "#D6E8FE"), "mid": ("#F8FAFC", "#E2E8F0")}   # design_kit.CARD_DIR 과 같은 색
# (원본 목업, 시장, 쓸 파일, 목록 이름, 봉을 여기까지만(없으면 전부))
CASES = [
    ("kr-stocks/output/mock_005930.html", "kr", "mock_chart_talk_down.html", "차트 읽기 버튼 · 하락 흐름 = 하락이 (삼성전자)", None),
    ("stock-radar/output/mock_AAPL.html", "us", "mock_chart_talk_up.html", "차트 읽기 버튼 · 상승 흐름 = 상승이 (애플)", None),
    ("kr-stocks/output/mock_005930.html", "kr", "mock_chart_talk_mid.html", "차트 읽기 버튼 · 팽팽한 날 = 분석이 (제안, 삼성전자 11월 2일까지)", "2026-11-02"),
]
CANDLE = re.compile(r'data-candle="([^"]+)"')
SPOT = 'style="min-height:300px;"></div></span></span>'   # 그래프 카드가 끝나는 자리 — 버튼은 카드 바로 아래 2px

CSS = """<style>
.ct-btn{display:flex;align-items:center;justify-content:center;gap:6px;width:calc(100% + 10px);height:40px;box-sizing:border-box;margin:2px -5px 0;padding:0;
  background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:15px;line-height:22px;font-weight:700;color:#111;cursor:pointer;}
.ct-btn:active{background:#F3F4F6;}
.ct-btn [data-ct-arrow]{transition:transform .2s;}
.ct-btn[aria-expanded=true] [data-ct-arrow]{transform:rotate(180deg);}
.ct-box{margin:2px -5px 0;padding:14px 12px;border-radius:8px;}
.ct-row{margin:8px 0 0;opacity:0;transform:translateY(6px);transition:opacity .3s,transform .3s;}
.ct-row.on{opacity:1;transform:none;}
.ct-talk{display:flex;align-items:flex-end;gap:12px;}
.ct-talk.ct-left{flex-direction:row-reverse;}
.ct-talk.ct-left .ct-say::after{right:auto;left:-6px;border-top:0;border-right:0;border-bottom:1px solid var(--bd);border-left:1px solid var(--bd);}
.ct-say b{font-weight:700;}
.ct-up{color:#B91C1C;font-weight:700;white-space:nowrap;}
.ct-dn{color:#1D4ED8;font-weight:700;white-space:nowrap;}
.ct-up i,.ct-dn i{font-style:normal;font-size:12px;vertical-align:1px;margin-right:2px;}
.ct-talk img{display:block;flex:0 0 auto;}
.ct-talk .ct-say{position:relative;flex:1 1 auto;min-width:0;}
.ct-talk .ct-say::after{content:"";position:absolute;right:-6px;bottom:var(--tail);width:10px;height:10px;box-sizing:border-box;background:#fff;
  border-top:1px solid var(--bd);border-right:1px solid var(--bd);transform:rotate(45deg);}
.ct-say{box-sizing:border-box;padding:10px 12px;border-radius:14px;background:#fff;border:1px solid var(--bd);font-size:15px;line-height:23px;color:#111;word-break:keep-all;}
.ct-pic{display:block;width:100%;max-width:280px;height:auto;margin:2px auto 8px;}
.ct-tag{margin:14px 0 0;padding-left:6px;font-size:13px;line-height:19px;font-weight:700;color:#B45309;}
</style>"""
JS = """<script>(function(){var b=document.querySelector('[data-ct-btn]'),x=document.querySelector('[data-ct-box]');if(!b||!x)return;
b.addEventListener('click',function(){var open=x.hidden;x.hidden=!open;b.setAttribute('aria-expanded',open?'true':'false');
b.querySelector('[data-ct-word]').textContent=open?'차트 읽기 접기':'차트 읽기';
var rows=x.querySelectorAll('.ct-row');for(var i=0;i<rows.length;i++){rows[i].classList.remove('on');
if(open)(function(r,k){setTimeout(function(){r.classList.add('on');},120+k*500);})(rows[i],i);}});})();</script>"""
R_, B_ = "#DC2626", "#2563EB"   # 상승 빨강 · 하락 파랑 (평균선 그림의 지금 종가 선과 같은 색)


def candles(spec):
    """봉 아이콘 — spec = [(색, 몸통 위, 몸통 아래, 꼬리 위, 꼬리 아래), …] 왼쪽부터. 면으로 채운 몸통 + 얇은 꼬리."""
    w = 4 if len(spec) == 2 else 3
    xs = [3.5, 10.5] if len(spec) == 2 else [2, 6.5, 11]
    out = ""
    for (col, top, bot, wt, wb), x in zip(spec, xs):
        cx = x + w / 2
        out += (f'<path d="M{cx} {wt}v{top - wt}M{cx} {bot}v{wb - bot}" stroke="{col}" stroke-width="1.5" stroke-linecap="round"/>'
                f'<rect x="{x}" y="{top}" width="{w}" height="{bot - top}" rx="0.75" fill="{col}"/>')
    return out


ICON = ('<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">'
        + candles([(R_, 4, 10, 2, 12.5), (B_, 6, 12, 3.5, 14.5)]) + '</svg>')   # 봉 둘 · 빨강 → 파랑 · 면으로 채움 16px (2026-11-27 A안 확정)
ICON_ALTS = []   # 버튼 아이콘 시안 — 고르기 전 (이름표, 그림). 고르면 ICON 으로 올리고 이 표는 비운다
ARROW = '<svg data-ct-arrow width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5l4 4 4-4"/></svg>'
UP, DN, AVG, AVG2, INK, MUTE = "#ED8E87", "#82B1F0", "#F8CE8C", "#CFC4FA", "#111111", "#64748B"   # 평균선 둘은 연하게(종가 선과 대비)
LINE = {"up": "#DC2626", "down": "#2563EB", "mid": "#475569"}   # 지금 종가 선 · 지금 값 점 = 그날 흐름 색
TXT = 'font-family="inherit" font-size="12" fill="' + MUTE + '"'


def face(name):
    """전용 컷(chart-talk/chars, 사용자 그림) 먼저, 아직 없는 캐릭터는 댓글 스티커로 임시."""
    own = os.path.join(BASE, "chars", name + ".webp")
    with open(own if os.path.exists(own) else os.path.join(STK, name + ".webp"), "rb") as f:
        return "data:image/webp;base64," + base64.b64encode(f.read()).decode()


def _line(ys, color, w=1):
    step = 200 // (len(ys) - 1)
    return f'<polyline points="{" ".join(f"{16 + i * step},{y}" for i, y in enumerate(ys))}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'


def pic_avg(pos, mood):
    """예시 그림 — 종가 선(검정)과 평균선. 모양만 보여 주는 그림이라 실제 값이 아니다(그림 아래 `예시 그림`)."""
    flip = pos in ("above", "split_down")   # 아래 꼴을 위아래로 뒤집으면 위 꼴
    two = pos in ("split_up", "split_down", "mixed")
    price = [30, 22, 34, 28, 44, 40, 58, 52, 70, 64, 74] if not two else [20, 30, 26, 42, 50, 62, 74, 80, 72, 64, 58]
    long_ = [26, 28, 30, 32, 35, 38, 41, 44, 47, 50, 53] if not two else [22, 24, 26, 28, 31, 34, 37, 40, 43, 45, 47]
    short = [24, 26, 29, 33, 40, 48, 57, 66, 71, 71, 68]
    f = (lambda ys: [96 - y for y in ys]) if flip else (lambda ys: ys)
    price, long_, short = f(price), f(long_), f(short)
    ink = LINE[mood]
    out = _line(long_, AVG) + (_line(short, AVG2) if two else "") + _line(price, ink, 1.5)
    out += f'<circle cx="216" cy="{price[-1]}" r="4" fill="{ink}"/><text x="226" y="{price[-1] + 4}" {TXT} fill="{ink}" font-weight="700">지금 종가</text>'
    out += f'<text x="226" y="{long_[-1] + (4 if not two else (-4 if not flip else 12))}" {TXT}>{"긴 평균선" if two else "평균선"}</text>'
    if two:
        out += f'<text x="226" y="{short[-1] + (16 if not flip else -8)}" {TXT}>짧은 평균선</text>'
    return f'<svg class="ct-pic" viewBox="0 0 300 96" role="img" aria-label="종가와 평균선 예시 그림">{out}</svg>'


def pic_rsi(v, mood):
    x = 20 + round(v / 100 * 240)
    out = (f'<rect x="20" y="34" width="72" height="12" rx="6" fill="{DN}" opacity="0.5"/><rect x="92" y="34" width="96" height="12" fill="#E2E8F0"/>'
           f'<rect x="188" y="34" width="72" height="12" rx="6" fill="{UP}" opacity="0.5"/><rect x="86" y="34" width="12" height="12" fill="#E2E8F0"/><rect x="182" y="34" width="12" height="12" fill="#E2E8F0"/>'
           f'<rect x="139" y="30" width="2" height="20" fill="#94A3B8"/>'
           f'<circle cx="{x}" cy="40" r="7" fill="{LINE[mood]}" stroke="#fff" stroke-width="2"/><text x="{x}" y="22" text-anchor="middle" {TXT} fill="{LINE[mood]}" font-weight="700">{v:.1f}</text>')
    for val, lab in ((30, "30"), (50, "50"), (70, "70")):
        out += f'<text x="{20 + round(val / 100 * 240)}" y="66" text-anchor="middle" {TXT}>{lab}</text>'
    out += f'<text x="20" y="84" {TXT}>낮은 자리 (과매도)</text><text x="260" y="84" text-anchor="end" {TXT}>높은 자리 (과매수)</text>'
    return f'<svg class="ct-pic" viewBox="0 0 280 90" role="img" aria-label="상대강도지수 {v:.1f}">{out}</svg>'


def pic_vol(ratio, day):
    base = 32
    h = max(4, min(72, round(base * ratio)))
    col = {"up": UP, "down": DN, "flat": "#CBD5E1"}[day]
    out = (f'<rect x="70" y="{84 - base}" width="44" height="{base}" rx="3" fill="#CBD5E1"/><text x="92" y="100" text-anchor="middle" {TXT}>평소 (20일 평균)</text>'
           f'<rect x="170" y="{84 - h}" width="44" height="{h}" rx="3" fill="{col}"/><text x="192" y="100" text-anchor="middle" {TXT}>마지막 거래일</text>'
           f'<text x="192" y="{84 - h - 6}" text-anchor="middle" {TXT} fill="{INK}" font-weight="700">{ratio:.1f}배</text>'
           f'<rect x="50" y="84" width="184" height="1" fill="#CBD5E1"/>')
    top = 84 - max(h, base) - 24
    return f'<svg class="ct-pic" viewBox="0 {top} 280 {104 - top}" role="img" aria-label="거래량 평소의 {ratio:.1f}배">{out}</svg>'


def picture(p, mood):
    if not p:
        return ""
    return pic_avg(p["pos"], mood) if p["kind"] == "avg" else pic_rsi(p["value"], mood) if p["kind"] == "rsi" else pic_vol(p["ratio"], p["day"])


def rich(text):
    """문장 틀의 표시 → 화면. `**굵게**` · `{+상승 색}`(▲) · `{-하락 색}`(▼)."""
    t = html.escape(text)
    t = re.sub(r"\{\+(.+?)\}", r'<span class="ct-up"><i>▲</i>\1</span>', t)
    t = re.sub(r"\{-(.+?)\}", r'<span class="ct-dn"><i>▼</i>\1</span>', t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


PX = 96   # 캐릭터 크기 — 세 번 모두 같게
PX_CUT = {"up_hello": 86, "up_bye": 86}   # 컷마다 다르게 (상승이 인사 · 끝인사 = 10% 작게, 2026-11-27)


def said(line, mood, who=None, left=False):
    """말풍선 한 줄 — 그림이 위, 글이 아래. who(캐릭터 컷)가 있으면 캐릭터가 옆에 서고 말풍선 꼬리가 캐릭터를 가리킨다(가운데 컷만 왼쪽)."""
    px = PX_CUT.get(who, PX)
    say = f'<div class="ct-say">{picture(line["pic"], mood)}{rich(line["text"])}</div>'
    if not who:
        return f'<div class="ct-row">{say}</div>'
    return (f'<div class="ct-row ct-talk{" ct-left" if left else ""}" style="--tail:{px // 3}px;">{say}'
            f'<img src="{face(who)}" alt="" width="{px}" height="{px}" style="width:{px}px;height:{px}px;"></div>')


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
        rows += f'<div class="ct-tag">{html.escape(label)}</div><div class="rt-tabs" style="{bar}">{btns}</div>'
    return f'<div style="margin:18px 0 0;">{rows}</div>' if rows else ""


def icon_alts():
    """아이콘 시안 줄 — 진짜 버튼과 같은 꼴(눌러도 안 열림)에 아이콘만 바꿔 이름표와 함께."""
    rows = "".join(f'<div class="ct-tag">{html.escape(label)}</div><div class="ct-btn" style="cursor:default;"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">{body}</svg><span>차트 읽기</span>{ARROW}</div>'
                   for label, body in ICON_ALTS)
    return f'<div style="margin:18px 0 0;">{rows}</div>' if rows else ""


def block(t):
    (bg, bd), cuts = TONE[t["mood"]], dict(zip(("hello", "mid", "bye"), FACE[t["mood"]]))
    rows = ""
    for x in t["lines"]:
        who = cuts.get(x["cut"])
        for label, cut in ALTS.get(who, [(None, who)]):
            if label:
                rows += f'<div class="ct-row ct-tag" style="margin:14px 0 0;">{html.escape(label)}</div>'
            rows += said(x, t["mood"], cut, x["cut"] == "mid")
    return (CSS + f'<button class="ct-btn" type="button" data-ct-btn aria-expanded="false">{ICON}<span data-ct-word>차트 읽기</span>{ARROW}</button>'
            f'<div class="ct-box" data-ct-box hidden style="--bd:{bd};background:{bg};border:1px solid {bd};">{rows}</div>' + (icon_alts() if t["mood"] == "up" else "") + (tab_alts() if t["mood"] == "down" else "") + JS)


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
        assert page.count(SPOT) == 1, src
        page = page.replace(SPOT, SPOT + block(t))
        page = page.replace("</head>", TAB_FIX + "</head>", 1)
        page = re.sub(r"(20\d\d-\d\d-\d\d)\s*사용자\b", r"\1", page)   # 베껴 온 테마 주석의 경위 꼴 — 공개 저장소 검사(.githooks) 기준
        page = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "", page)   # 베껴 온 테마의 Firebase 웹 키는 목업에 싣지 않는다(목업 댓글은 동작 X)
        page = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", page, count=1)
        with open(os.path.join(BASE, "output", out), "w", encoding="utf-8") as f:
            f.write(page)
        print(out, t["who"], round(t["net"], 2), len(t["lines"]), "줄", "|", *[x["text"] for x in t["lines"]], sep="\n  ")


if __name__ == "__main__":
    main()
