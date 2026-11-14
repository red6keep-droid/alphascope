"""홈 미국 증시 · 한국 증시 카드 — 하루(장중) 그래프 시안, 실제 홈 카드 그대로 (2026-11-14 사용자).

    python experiments/home-thumb/mock_card_day.py     # design-samples/output/mock_home_card_day.html (목업 목록 = 디자인 샘플 · 홈 카드 그래프)

사용자 정정(같은 날): 네이버 화면은 '그래프 느낌'만 참고 — 숫자 · 글꼴 · 정보 배치는 우리 것으로.
  - 카드는 홈 그대로: 홈 목업(home-split/output/mock_home_us.html)의 CSS 를 통째로 넣고 같은 마크업(아이콘 · 제목 · 날짜 · 그래프 상자 · 요약 한 줄)
  - 그래프 상자 크기도 지금 그림과 같은 비율(2.27 : 1) — 작은 자리에서 다 보이는지 보려고
  - 정보 넣는 방식 4안(종가만 / 종가 + 최고 · 최저 / …), 글자 크기는 맨 위 버튼으로 바꿔 보며 정한다
그래프 = 인라인 SVG(선 · 면 · 점선 · 점) — 글자는 모두 카드 HTML 글자. 자료 = intraday_sample.json(11-13 5분봉, 목업용 한 번 받음).
홈 목업이 없으면 먼저 python experiments/home-split/mock_home_split.py.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
OUT = os.path.join(EXP, "design-samples", "output")   # 목업 목록 = 디자인 샘플 묶음 (2026-11-14 사용자)
UP, DN, INK, NOTE = "#d93025", "#1a73e8", "#111", "#6B7280"
UP_FILL, DN_FILL = "rgba(217,48,37,.16)", "rgba(26,115,232,.16)"
VW, VH = 340, 150   # 그래프 상자 = 지금 카드 그림 비율 2.27 : 1 (폰 실제 폭 약 316 ~ 338)
SLOTS = 78
START = {"^KS11": (9, 0), "^GSPC": (9, 30)}
SUMMARY = {"^GSPC": "전통 대기업과 금융, 소비재가 시장을 끌어올린 하루였습니다.",
           "^KS11": "반도체가 밀리며 오후 내내 약했던 하루였습니다."}
META = {"^GSPC": ("미국 증시", "#E53E3E", "us-report-col", "report-card", "11월 14일 아침"),
        "^KS11": ("한국 증시", "#1D4ED8", "kr-report-col", "kr-report-card", "11월 13일 오후")}
ICON = ('<svg viewBox="0 0 16 16" fill="currentColor"><rect x="2" y="9" width="3" height="5" rx=".5"/>'
        '<rect x="6.5" y="5" width="3" height="9" rx=".5"/><rect x="11" y="2" width="3" height="12" rx=".5"/></svg>')


def fmt(v):
    return f"{v:,.2f}"


def slot(sym, hm):
    h, m = map(int, hm.split(":"))
    h0, m0 = START[sym]
    return ((h * 60 + m) - (h0 * 60 + m0)) // 5


def geom(sym, d, top, bot):
    """점 좌표(viewBox) — top · bot = 그리는 높이 범위 비율(0 = 위). 마지막 값은 장 마감 칸까지 잇는다."""
    xs = [slot(sym, t) for t in d["t"]]
    ys = list(d["c"])
    if xs[-1] < SLOTS:
        xs.append(SLOTS); ys.append(ys[-1])
    pc = d["prev"]
    lo, hi = min(min(ys), pc), max(max(ys), pc)
    X = lambda i: 2 + i / SLOTS * (VW - 4)
    Y = lambda v: VH * top + (hi - v) / (hi - lo) * VH * (bot - top)
    pts = [(X(x), Y(v), v) for x, v in zip(xs, ys)]
    return pts, Y(pc)


def svg(sym, d, top, bot, uid):
    pts, by = geom(sym, d, top, bot)
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
    area = f"M{pts[0][0]:.1f},{by:.1f} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts) + f" L{pts[-1][0]:.1f},{by:.1f} Z"
    hi = min(pts, key=lambda p: p[1]); lo = max(pts, key=lambda p: p[1])
    dots = "".join(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="#fff" stroke="{c}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
                   for p, c in ((hi, UP if hi[2] >= d["prev"] else DN), (lo, UP if lo[2] >= d["prev"] else DN)))
    s = (f'<svg viewBox="0 0 {VW} {VH}" style="display:block;width:100%;height:auto;" aria-hidden="true">'
         f'<defs><clipPath id="u{uid}"><rect x="0" y="0" width="{VW}" height="{by:.1f}"/></clipPath>'
         f'<clipPath id="d{uid}"><rect x="0" y="{by:.1f}" width="{VW}" height="{VH - by:.1f}"/></clipPath>'
         f'<linearGradient id="gu{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{UP}" stop-opacity=".22"/><stop offset="1" stop-color="{UP}" stop-opacity=".02"/></linearGradient>'
         f'<linearGradient id="gd{uid}" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{DN}" stop-opacity=".22"/><stop offset="1" stop-color="{DN}" stop-opacity=".02"/></linearGradient></defs>'
         f'<g clip-path="url(#u{uid})"><path d="{area}" fill="url(#gu{uid})"/><polyline points="{line}" fill="none" stroke="{UP}" stroke-width="1.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></g>'
         f'<g clip-path="url(#d{uid})"><path d="{area}" fill="url(#gd{uid})"/><polyline points="{line}" fill="none" stroke="{DN}" stroke-width="1.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></g>'
         f'<line x1="0" x2="{VW}" y1="{by:.1f}" y2="{by:.1f}" stroke="#9CA3AF" stroke-width="1" stroke-dasharray="2 3" vector-effect="non-scaling-stroke"/>'
         f'{dots}</svg>')
    return s, hi, lo


def mark(p, kind, avoid=None, val=None):
    """최고 · 최저 글자(HTML) — 최고는 점 위, 최저는 점 아래. 좌우 끝 가까우면 점 안쪽으로 붙인다.
    avoid = 겹치면 안 되는 왼쪽 위 숫자 영역(가로 %, 세로 %) — 최고 글자가 그 안이면 점 오른쪽 옆으로 옮긴다."""
    x, y = p[0] / VW * 100, p[1] / VH * 100
    col = UP if kind == "최고" else DN
    if x < 18:
        hx, tx = f"left:{max(x, 1):.1f}%;", "-4px"
    elif x > 82:
        hx, tx = f"right:{max(100 - x, 1):.1f}%;", "4px"
    else:
        hx, tx = f"left:{x:.1f}%;", "-50%"
    ty = "calc(-100% - 5px)" if kind == "최고" else "5px"
    if avoid and kind == "최고" and x < avoid[0] and y < avoid[1] + 14:
        hx, tx, ty = f"left:{x:.1f}%;", "8px", "-50%"
    return (f'<span class="hc-mark" style="{hx}top:{y:.1f}%;transform:translate({tx},{ty});color:{col};">'
            f'<span class="hc-k">{kind}</span> {fmt(val if val is not None else p[2])}</span>')


def head(d, inside=False):
    c, pc = d["c"][-1], d["prev"]
    ch = c - pc
    col = UP if ch > 0 else DN if ch < 0 else INK
    tri = "▲" if ch > 0 else "▼" if ch < 0 else ""
    sign = "+" if ch > 0 else "−" if ch < 0 else ""
    cls = "hc-head in" if inside else "hc-head"
    return (f'<div class="{cls}"><span class="hc-num">{fmt(c)}</span>'
            f'<span class="hc-chg" style="color:{col};">{tri}{fmt(abs(ch))} ({sign}{abs(ch / pc * 100):.2f}%)</span></div>')


def chart_box(sym, d, kind, uid):
    """kind: A 종가만(겹침) · B 종가 + 최고 · 최저(겹침) · C 숫자 줄 위 + 최고 · 최저 점 · D 숫자 줄 위 + 아래 칸"""
    if kind in ("A", "B"):
        s, hi, lo = svg(sym, d, .40, .86, uid)
        marks = (mark(hi, "최고", avoid=(48, 30), val=d["h"]) + mark(lo, "최저", val=d["l"])) if kind == "B" else ""
        return f'<div class="hc-box">{s}{head(d, inside=True)}{marks}</div>'
    if kind == "C":
        s, hi, lo = svg(sym, d, .20, .80, uid)
        return head(d) + f'<div class="hc-box">{s}{mark(hi, "최고", val=d["h"])}{mark(lo, "최저", val=d["l"])}</div>'
    s, hi, lo = svg(sym, d, .08, .92, uid)
    row = (f'<div class="hc-row"><span><span class="hc-k">최고</span> <b style="color:{UP};">{fmt(d["h"])}</b></span>'
           f'<span><span class="hc-k">최저</span> <b style="color:{DN};">{fmt(d["l"])}</b></span></div>')
    return head(d) + f'<div class="hc-box">{s}</div>' + row


def card(sym, d, kind):
    name, color, col_id, card_id, date = META[sym]
    return (f'<div class="report-col" id="{col_id}">'
            f'<h3 class="report-title"><span class="report-icon" style="background:{color};" aria-hidden="true">{ICON}</span>{name}'
            f'<span class="report-card-date">{date}</span></h3>'
            f'<a class="report-card" id="{card_id}" href="#">{chart_box(sym, d, kind, card_id + kind)}'
            f'<div class="report-block"><div class="report-columns"><ul><li>{SUMMARY[sym]}</li></ul></div></div></a></div>')


SPECS = [
    ("A", "종가만 — 그래프 위에 겹침", "그래프 상자 왼쪽 위에 종가 · 전날 대비. 최고 · 최저는 넣지 않음. 카드 높이 = 지금과 같음"),
    ("B", "종가 + 최고 · 최저 — 그래프 위에 겹침", "A 에 최고 · 최저 점 글자를 더함. 최고 점이 종가 글자 자리에 오면 점 오른쪽 옆으로 비킨다. 카드 높이 = 지금과 같음"),
    ("C", "종가 줄은 그래프 위 + 최고 · 최저 점", "종가 · 전날 대비를 그래프 상자 밖 위 줄로 빼서 그래프를 가리지 않음. 최고 · 최저는 점 옆. 카드가 숫자 한 줄만큼 길어짐"),
    ("D", "종가 줄은 그래프 위 + 최고 · 최저는 아래 한 줄", "그래프 안엔 글자 없음(선 · 점만). 최고 · 최저는 상자 아래 한 줄. 카드가 두 줄만큼 길어짐"),
]

CSS = """
:root { --hc-num: 20px; --hc-chg: 14px; --hc-mark: 12px; }
.hc-box { position: relative; border: 1px solid #eee; border-radius: 8px; overflow: hidden; background: #fff; }
.hc-head { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0 8px; margin: 0 0 -8px; font-family: var(--num); font-variant-numeric: tabular-nums; }
.hc-head.in { position: absolute; left: 10px; top: 8px; margin: 0; }
.hc-num { font-size: var(--hc-num); line-height: calc(var(--hc-num) + 6px); font-weight: 700; color: #111; }
.hc-chg { font-size: var(--hc-chg); line-height: calc(var(--hc-chg) + 6px); font-weight: 700; }
.hc-mark { position: absolute; white-space: nowrap; font-family: var(--num); font-size: var(--hc-mark); line-height: calc(var(--hc-mark) + 6px); font-weight: 700; font-variant-numeric: tabular-nums; }
.hc-k { color: #6B7280; font-weight: 400; }
.hc-row { display: flex; gap: 16px; margin: -8px 0 0; font-family: var(--num); font-size: var(--hc-mark); line-height: calc(var(--hc-mark) + 8px); font-variant-numeric: tabular-nums; }
/* 비교 화면 틀 */
.hc-page { max-width: 760px; margin: 0 auto; padding: 0 10px 40px; }
.hc-bar { position: sticky; top: 0; z-index: 5; background: #F3F4F6; padding: 10px 0; border-bottom: 1px solid #E5E7EB; }
.hc-bar h1 { font-size: 19px; line-height: 27px; margin: 0 0 6px; }
.hc-ctl { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; line-height: 19px; color: #374151; }
.hc-ctl > span { display: inline-flex; align-items: center; gap: 4px; }
.hc-ctl button { font: inherit; padding: 4px 9px; border: 1px solid #CBD5E1; border-radius: 6px; background: #fff; color: #374151; }
.hc-ctl button[aria-pressed="true"] { border-color: #111; color: #111; font-weight: 700; }
.hc-sec { margin: 22px 0 0; }
.hc-sec h2 { font-size: 18px; line-height: 26px; margin: 0 0 2px; }
.hc-why { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; display: block !important; font-size: 14px; line-height: 21px; color: #6B7280; margin: 0 0 10px; }
.hc-sec .home-cards { margin-top: 0; padding: 0; }   /* 홈 맨 위 회색 띠용 -36 은 비교 화면에서 뺀다 */
.hc-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
.hc-pair .report-col { background: #fff; }
"""

JS = """
(function(){
  var root=document.documentElement;
  document.querySelectorAll('.hc-ctl [data-v]').forEach(function(b){
    b.addEventListener('click',function(){
      root.style.setProperty(b.dataset.var,b.dataset.v);
      b.parentNode.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
    });
  });
  document.querySelectorAll('a.report-card').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();});});
})();
"""


def controls():
    def grp(label, var, vals, cur):
        bs = "".join(f'<button type="button" data-var="{var}" data-v="{v}px" aria-pressed="{"true" if v == cur else "false"}">{v}</button>' for v in vals)
        return f'<span>{label} {bs}</span>'
    return ('<div class="hc-ctl">' + grp("종가", "--hc-num", (18, 20, 22, 24), 20) + grp("전날 대비", "--hc-chg", (13, 14, 15), 14)
            + grp("최고 · 최저", "--hc-mark", (11, 12, 13), 12) + "</div>")


def home_css():
    p = os.path.join(EXP, "home-split", "output", "mock_home_us.html")
    with open(p, encoding="utf-8") as f:
        s = f.read()
    head = s[:s.find("<body")]
    styles = "".join(re.findall(r"<style[^>]*>.*?</style>", head, flags=re.S))
    links = "".join(re.findall(r'<link href="https://fonts[^>]*>', head))
    return links + styles


def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(os.path.join(HERE, "intraday_sample.json"), encoding="utf-8"))
    secs = []
    for kind, name, why in SPECS:
        cards = "".join(card(sym, data[sym], kind) for sym in ("^GSPC", "^KS11"))
        secs.append(f'<section class="hc-sec"><h2>{kind}. {name}</h2><div class="hc-why">{why}</div>'
                    f'<div class="home-cards"><div class="hc-pair">{cards}</div></div></section>')
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>홈 카드 그래프</title>' + home_css() + f"<style>{CSS}</style></head>"
            '<body data-pv-view="home" style="background:#F3F4F6;"><div class="hc-page">'
            '<div class="hc-bar"><h1>홈 증시 카드 하루 그래프</h1>' + controls() + '</div>'
            '<p style="font-size:14px;line-height:21px;color:#6B7280;margin:10px 0 0;">실제 홈 카드 그대로(아이콘 · 제목 · 날짜 · 요약 한 줄)이고, 그래프 상자는 지금 그림과 같은 크기입니다. '
            '위 버튼으로 글자 크기를 바꿔 보세요. 자료 = 11월 13일 실제 5분봉(미국은 한국 시간 11월 14일 아침 마감).</p>'
            + "".join(secs) + f"</div><script>{JS}</script></body></html>")
    out = os.path.join(OUT, "mock_home_card_day.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", out)


if __name__ == "__main__":
    main()
