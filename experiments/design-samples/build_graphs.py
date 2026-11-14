"""그래프 유형 — 통일 뒤 더 합칠 수 없는 그래프 유형만 하나씩 (2026-11-14 사용자: "막대 · 가로 막대 · 선 그래프를 모아 통일, 통일이 안 되는 유형만 목업에").

    python experiments/design-samples/build_graphs.py           # output/mock_graphs.html (유형 샘플)
    python experiments/design-samples/build_graphs.py --all     # + output/mock_graphs_all.html (모든 그래프 · 잰 값)

experiments/*/output/*.html (실제 목업 결과) 에서 그래프 흰 카드를 그대로 떼어 와 종류별로 묶는다.
같은 그래프(제목에서 종목 · 날짜 · 숫자를 지운 이름이 같은 것)는 하나만 보이고, 몇 쪽에서 쓰였는지 센다.
그래프마다 막대 폭 · 모서리 · 선 굵기 · 색 · 글자 크기를 재서, 같은 종류 안에서 가장 흔한 값과 다르면 빨갛게 표시한다.
봉차트(candle_chart · TradingView · 장중 차트)는 뺀다. 규칙 원본 = 디자인-가이드라인.md 9절.
"""
import collections
import glob
import html as _html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
OUT = os.path.join(HERE, "output", "mock_graphs.html")

# 같은 그래프가 여러 목업에 들어가 있으면 이 순서의 폴더 것을 대표로 쓴다
PRIORITY = ["stock-radar", "kr-stocks", "stock-etf", "nvda-report", "daily-report", "kr-market-report", "issue_store",
            "people-radar", "ops-dashboard", "stock-quick", "course", "my-stocks", "competitiveness", "theme-monitor", "media-daily"]
SKIP_DIRS = {"design-samples"}
PAGE_KO = {"stock-radar": "미국 종목", "kr-stocks": "한국 종목", "stock-etf": "ETF", "nvda-report": "엔비디아", "daily-report": "데일리(미국 증시)",
           "kr-market-report": "한국 증시", "issue_store": "증시 전망 · 이슈", "people-radar": "인물 발언", "ops-dashboard": "운영 현황",
           "stock-quick": "간단 정보", "course": "강좌", "my-stocks": "내 종목", "home-preview": "홈 미리보기", "home-split": "홈 나누기",
           "post-footer": "글 끝", "site-search": "검색", "stock-title": "종목 제목", "competitiveness": "국가 경쟁력", "theme-monitor": "테마"}

TAG = re.compile(r'<(/?)(span|div|details|section|figure|a)\b[^>]*?>', re.S)
WHITE = re.compile(r'<(span|div) style="[^"]*background:#(?:fff|FFF|ffffff)\b[^"]*border-radius:8px[^"]*"')
TRACK = re.compile(r'<span style="display:flex;(?:width:[^;"]*;)?height:24px;border-radius:6px;overflow:hidden;background:#F1F5F9;')   # dk.legend_bar 비율 막대
HBAR = re.compile(r'<span style="[^"]*height:10px;background:#F1F5F9;border-radius:3px;overflow:hidden;')         # dk.hbar 줄 막대
PEOPLE = re.compile(r'<span style="display:flex;(?:width:[^;"]*;)?height:6px;border-radius:3px;overflow:hidden;flex:0 0 auto;background:#F1F5F9;')
ETFW = re.compile(r'<span style="display:block;width:[\d.]+%;height:8px;background:#')
COURSE = re.compile(r'<span style="display:block;width:[\d.]+%;min-width:4px;height:16px;border-radius:4px;')


def block(s, i):
    m = TAG.match(s, i)
    if not m:
        return None
    name, depth = m.group(2), 0
    for t in TAG.finditer(s, i):
        if t.group(2) != name:
            continue
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return s[i:t.end()]
    return None


def enclosing(s, i, limit=6000, min_len=600):
    """i 를 품는 가장 가까운 블록 (줄 막대 한 줄 · 카드) — 뒤로 걸으며 첫 여는 태그 중 i 를 덮는 것."""
    j = i
    for _ in range(40):
        j = max(s.rfind("<span", max(0, i - limit), j), s.rfind("<div", max(0, i - limit), j))
        if j < 0:
            return None
        b = block(s, j)
        if b and j + len(b) > i + 100 and len(b) > min_len:
            return b
    return None


def text(h):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def title_before(s, at):
    pre = text(s[max(0, at - 2500):at])
    m = re.search(r"※\s*([^※]*)$", pre)
    if m and len(m.group(1)) < 90:
        return re.sub(r"\s*\?\s*$", "", m.group(1)).strip()
    return ""


GUESS = [("시가 갭 장중 종가", "하루 조각 (시가 · 갭 · 장중 · 종가)"), ("중앙값 ·", "12개월 모멘텀 비교 막대"), ("빠져나가는", "돈 흐름 게이지 (업종 vs 시장)"),
         ("우리 63종목 순위", "12개월 모멘텀 순위"), ("한 달 범위", "한 달간 변화 범위"), ("중앙", "애널리스트 목표가 범위"), ("전체요약", "기술 지표 큰 반원"),
         ("기술지표", "기술 지표 · 이동평균 작은 반원"), ("이동평균", "기술 지표 · 이동평균 작은 반원"), ("뉴스는 어느 쪽", "이슈 뉴스 방향 반원 (바늘)"), ("애널리스트", "애널리스트 의견 비율"), ("오늘 소식", "이슈 소식 방향 비율"), ("건", "뉴스 방향 비율"),
         ("다음 실적 발표", "다음 실적 발표 막대"), ("비교 대상", "비교 막대 (제목 못 찾음)")]
KIND_GUESS = {"etfw": "ETF 구성 비중", "hbar": "업종별 등락 줄 막대", "course": "강좌 비교 막대", "people": "인물 발언 작은 막대"}


def guess(k, t):
    if k in KIND_GUESS:
        return KIND_GUESS[k]
    for a, name in GUESS:
        if a in t:
            return name
    return t[:28]


def norm(t):
    t = re.split(r" [▲▼—–]| 최고가 대비| 1년 최고 대비| \(강매수", t)[0]
    t = re.sub(r"발표 다음 날 .+? 움직임", "발표 다음 날 (종목) 움직임", t)
    t = re.sub(r"^.+? vs .+? \(%p\)", "(대상) vs (비교) (%p)", t)
    t = re.sub(r"^평균 등급.*", "평균 등급 (애널리스트 목표가)", t)
    t = re.sub(r"^.+?, 올해와 작년 같은 (달|분기)", r"(업계 지표), 올해와 작년 같은 \1", t)
    t = re.sub(r"^날마다 .+? 기사", "날마다 (이슈) 기사", t)
    t = re.sub(r"\d+월 \d+일", "(날짜)", t)
    t = re.sub(r"[\d.]+ 종가 대비", "(날짜) 종가 대비", t)
    t = re.sub(r"\d+", "N", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(b):
    if re.search(r"candle|<canvas|data-ichart|tradingview|TradingView", b):
        return None
    if "data-range-gauge" in b:
        return "hgauge"
    if "<polyline" in b or re.search(r'<path[^>]*fill="none"[^>]*stroke-dasharray|<path d="M[\d.]+,[\d.]+ L', b):
        return "line"
    if re.search(r'<path d="M[\d.]+,[\d.]+ A\d+', b):
        return "arc"
    if b.count("position:absolute") >= 6 and re.search(r"position:absolute;left:calc\([^\"]*width:[\d.]+px;top:[\d.]+px;height:[\d.]+px;background:#", b):
        return "col"
    if "data-zoom" in b and "<img" in b:
        return "img"
    return None


# ---------- 재기 ----------
def most(c):
    return c.most_common(1)[0][0] if c else None


def specs(kind, b):
    """종류별로 비교할 값 — {이름: 값 문자열}. 값은 여러 개면 · 로 잇는다."""
    out = {}
    fs = sorted({int(x) for x in re.findall(r"font-size:(\d+)px", b)} | {int(float(x)) for x in re.findall(r'font-size="([\d.]+)"', b)})
    out["글자 크기"] = " · ".join(map(str, fs))
    if kind == "col":
        bars = re.findall(r"position:absolute;left:calc\([^\"]*?width:([\d.]+)px;top:[\d.]+px;height:[\d.]+px;background:(#[0-9A-Fa-f]{6});border-radius:([^;\"]+)", b)
        out["막대 폭"] = " · ".join(sorted({f"{float(w):g}" for w, _, _ in bars}, key=float))
        out["모서리"] = " · ".join(sorted({r for _, _, r in bars}))
        out["막대 색"] = " · ".join(sorted({c.upper() for _, c, _ in bars}))
        nums = re.findall(r"text-align:center;font-size:(\d+)px;font-weight:(\d+)", b)
        out["막대 숫자"] = " · ".join(sorted({f"{a}px {w}" for a, w in nums}))
        out["눈금선"] = " · ".join(sorted({c.upper() for c in re.findall(r"right:0;top:[\d.]+px;height:1px;background:(#[0-9A-Fa-f]{6})", b)}))
    elif kind == "line":
        pl = re.findall(r"<polyline [^>]*>", b) + re.findall(r'<path d="M[^"]*L[^>]*fill="none"[^>]*>', b)
        st = []
        for p in pl:
            c = re.search(r'stroke="(#[0-9A-Fa-f]{3,6})"', p)
            w = re.search(r'stroke-width="([\d.]+)"', p)
            d = re.search(r'stroke-dasharray="([^"]+)"', p)
            st.append(f"{c.group(1).upper() if c else '?'} {w.group(1) if w else '1'}{' 점선 ' + d.group(1) if d else ''}")
        out["선"] = " · ".join(dict.fromkeys(st))
        rs = re.findall(r'<circle [^>]*r="([\d.]+)"[^>]*stroke-width="([\d.]+)"', b)
        out["점 (반지름/테두리)"] = " · ".join(sorted({f"{r}/{w}" for r, w in rs}, key=lambda x: float(x.split('/')[0])))
        h = re.search(r'<svg [^>]*viewBox="0 0 [\d.]+ ([\d.]+)"', b)
        out["그림 높이"] = h.group(1) if h else ""
        out["눈금선"] = " · ".join(sorted({c.upper() for c in re.findall(r'<line [^>]*stroke="(#[0-9A-Fa-f]{6})" stroke-width="1"/>', b)} - {"#F5B971", "#CBD5E1"}))
    elif kind in ("hgauge", "track", "hbar", "people", "etfw", "course"):
        hs = re.findall(r"height:(\d+)px;[^\"]*?border-radius:(\d+)px", b)
        out["막대 높이/모서리"] = " · ".join(sorted({f"{h}/{r}" for h, r in hs if int(h) <= 30}, key=lambda x: int(x.split('/')[0])))
        out["색"] = " · ".join(sorted({c.upper() for c in re.findall(r"background:(#[0-9A-Fa-f]{6})", b)} - {"#FFFFFF"}))[:120]
    elif kind == "arc":
        out["호 굵기"] = " · ".join(sorted(set(re.findall(r'stroke-width="(\d+)" fill="none"', b))))
        out["크기"] = " · ".join(dict.fromkeys(re.findall(r'<svg [^>]*width="(\d+)" height="(\d+)"', b) and [f"{w}×{h}" for w, h in re.findall(r'<svg [^>]*width="(\d+)" height="(\d+)"', b)]))
    return out


# ---------- 모으기 ----------
def collect():
    items = {}   # key → dict
    files = sorted(glob.glob(os.path.join(EXP, "*", "output", "*.html")))
    for f in files:
        d = os.path.relpath(f, EXP).split(os.sep)[0]
        if d in SKIP_DIRS:
            continue
        s = open(f, encoding="utf-8", errors="ignore").read()
        found = []
        pos = 0
        for m in WHITE.finditer(s):
            if m.start() < pos:
                continue
            b = block(s, m.start())
            if not b or len(b) < 700:
                continue
            k = classify(b)
            if not k:
                continue
            pos = m.start() + len(b)
            found.append((k, m.start(), b))
        for rx, k in ((TRACK, "track"), (HBAR, "hbar"), (PEOPLE, "people"), (ETFW, "etfw"), (COURSE, "course")):
            last = -1
            for m in rx.finditer(s):
                if m.start() < last:
                    continue
                b = enclosing(s, m.start(), min_len=300 if k == "people" else 600)
                if not b:
                    continue
                j = s.find(b, max(0, m.start() - 8000))
                last = j + len(b)
                found.append((k, j, b))
        for k, at, b in found:
            t = "" if k in ("arc", "etfw", "hbar", "course", "people") else title_before(s, at)   # 제목이 그래프 안에 있거나 없는 꼴
            if not t:
                t = "(제목 없음) " + guess(k, text(b))
            if t.startswith("(제목 없음)"):
                if True:   # 제목 없는 그래프 = 알아본 이름으로 묶는다
                    key = (k, "~" + guess(k, text(b)))
                elif k in ("etfw", "hbar", "course", "people"):   # 이름 · 숫자가 자료마다 달라 글자로는 못 묶는다 — 폴더마다 하나
                    key = (k, "~" + d)
                elif k == "arc":
                    w = re.search(r'<svg [^>]*width="(\d+)"', b)
                    key = (k, "~" + (w.group(1) if w else ""))
                else:
                    key = (k, "~" + re.sub(r"[−+\-–$]|[\d.,%]+|‹ 넘겨 보기|\s+", "", text(b))[:10])
            else:
                key = (k, norm(t))
            it = items.get(key)
            rank = PRIORITY.index(d) if d in PRIORITY else 99
            if not it:
                items[key] = it = {"kind": k, "title": t, "html": b, "dir": d, "file": os.path.relpath(f, EXP), "rank": rank, "pages": collections.Counter()}
            elif (rank < it["rank"] or "오늘 0건" in it["html"]) and "오늘 0건" not in b and not (it["kind"] == "arc" and "전체요약" in it["html"]):
                it.update(title=t, html=b, dir=d, file=os.path.relpath(f, EXP), rank=rank)
            it["pages"][d] += 1
    for it in items.values():
        it["spec"] = specs(it["kind"], it["html"])
    return list(items.values())


SECTIONS = [
    ("col", "세로 막대", "R._col_chart · daily-report/cards.col_chart · kr-market-report _bars · kr-stocks _yoy_chart → dk.col_frame"),
    ("line", "선 그래프", "R.line_chart · dk.trend_card · R.line_tabs · 이슈 · 전망 페이지 자체 선"),
    ("hgauge", "가로 막대 — 범위 · 말풍선 (게이지)", "R._zone_gauge · year_range_in · month_range_in · target_gauge · flow_gauge"),
    ("track", "가로 막대 — 비율 막대 (100% 쌓기)", "dk.legend_bar · dk.direction_bars (뉴스 방향 · 애널리스트 의견)"),
    ("hbar", "가로 막대 — 줄 막대 (이름 · 막대 · 값)", "dk.hbar · dk.bar_row"),
    ("people", "가로 막대 — 인물 발언 작은 막대", "people-radar 자체"),
    ("etfw", "가로 막대 — ETF 구성 비중", "stock-etf 자체"),
    ("course", "가로 막대 — 강좌", "course 자체"),
    ("arc", "기타 — 반원 게이지", "tech_signals.gauge_svg (기술 지표 판정)"),
    ("img", "기타 — 그림 파일 그래프", "matplotlib PNG (data-zoom 확대)"),
]


COL_OK = {"#ED8E87", "#82B1F0", "#CBD5E1", "#F5B971", "#5FBFAF", "#BFA2E8"}   # 9절 · design_kit LEGEND_SIGN · LEGEND_GRAY · CHART_SERIES
LINE_RULE = {"#F5B971": "2", "#CBD5E1": "1 점선 6 5", "#5FBFAF": "2", "#BFA2E8": "2"}   # 9절 선 그래프: 주황 2 · 비교 회색 점선(6 5) 1 · 여러 계열


def rule_off(kind, k, v, mode):
    """빨강 기준 — 색 · 선은 규칙표와, 나머지는 같은 종류에서 가장 흔한 값과 비교. 글자 · 가로 막대 색(자료마다 다름)은 표시만."""
    if k == "글자 크기" or (k == "색" and kind != "col"):
        return False
    if k == "막대 폭":   # 9절: 숫자 폭 × 0.45, 최소 14 · 최대 20 — 그래프마다 다른 게 규칙
        return any(not 14 <= float(w) <= 20 for w in v.split(" · "))
    if k == "모서리":     # 9절: 바깥쪽 끝만 3
        return any(r not in ("3px 3px 0 0", "0 0 3px 3px") for r in v.split(" · "))
    if k == "막대 색":
        return any(c not in COL_OK for c in v.split(" · "))
    if k == "선":
        for one in v.split(" · "):
            c, _, rest = one.partition(" ")
            if LINE_RULE.get(c) != rest:
                return True
        return False
    return v != mode


def esc(t):
    return _html.escape(t, quote=True)


def render(items):
    by = collections.defaultdict(list)
    for it in items:
        by[it["kind"]].append(it)
    out = []
    toc = []
    for kind, name, src in SECTIONS:
        lst = sorted(by.get(kind, []), key=lambda x: (-sum(x["pages"].values()), x["title"]))
        if not lst:
            continue
        # 같은 종류 안에서 가장 흔한 값 (쓰인 쪽수로 무게)
        modes = {}
        for k in {k for it in lst for k in it["spec"]}:
            c = collections.Counter()
            for it in lst:
                v = it["spec"].get(k, "")
                if v:
                    c[v] += sum(it["pages"].values())
            modes[k] = most(c)
        cards = []
        n_off = 0
        for it in lst:
            rows = []
            off_any = False
            for k, v in it["spec"].items():
                if not v:
                    continue
                off = rule_off(kind, k, v, modes.get(k))
                off_any |= off and k != "글자 크기"
                rows.append(f'<div class="sp{" off" if off else ""}"><b>{esc(k)}</b> {esc(v)}</div>')
            n_off += off_any
            pages = " · ".join(f"{PAGE_KO.get(d, d)} {n}" for d, n in it["pages"].most_common())
            cards.append(
                f'<article class="g{" has-off" if off_any else ""}"><h3><span class="mk">※</span> {esc(it["title"])}</h3>'
                f'<div class="where">{esc(pages)}쪽 · <code>{esc(it["file"])}</code></div>'
                f'<div class="frame">{it["html"]}</div><div class="specs">{"".join(rows)}</div></article>')
        mode_rows = "".join(f'<div class="sp"><b>{esc(k)}</b> {esc(v)}</div>' for k, v in sorted(modes.items()) if v)
        anchor = f"s-{kind}"
        toc.append(f'<a href="#{anchor}">{esc(name)} <em>{len(lst)}</em></a>')
        out.append(f'<section id="{anchor}"><h2>{esc(name)} <em>{len(lst)}종</em></h2><p class="src">만드는 곳: {esc(src)}</p>'
                   f'<div class="mode"><div class="mt">이 종류에서 가장 흔한 값 — 빨강 = 이 값과 다름(색 · 선은 9절 규칙과 다름) · {n_off}종</div>{mode_rows}</div>'
                   f'<div class="grid">{"".join(cards)}</div></section>')
    css = """
body{margin:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#111;}
header{padding:24px 16px 8px;max-width:1400px;margin:0 auto;}
header h1{font-size:24px;line-height:32px;margin:0 0 6px;} header p{margin:0 0 6px;font-size:14px;line-height:22px;color:#4B5563;}
nav{position:sticky;top:0;z-index:5;background:#F1F5F9;border-bottom:1px solid #E2E8F0;padding:8px 16px;display:flex;gap:8px;flex-wrap:wrap;}
nav a{font-size:13px;line-height:20px;padding:4px 10px;border:1px solid #CBD5E1;border-radius:8px;background:#fff;color:#111;text-decoration:none;}
nav a em,h2 em{font-style:normal;color:#6B7280;font-weight:400;}
label.f{font-size:13px;line-height:20px;padding:4px 10px;color:#B91C1C;}
section{max-width:1400px;margin:0 auto;padding:24px 16px 8px;}
h2{font-size:20px;line-height:28px;margin:0 0 4px;} .src{margin:0 0 10px;font-size:13px;line-height:20px;color:#6B7280;}
.mode{background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:10px 12px;margin:0 0 16px;font-size:13px;line-height:20px;}
.mt{font-weight:700;margin:0 0 4px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;align-items:start;}
article.g{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:12px 14px;min-width:0;}
article.g.has-off{border-color:#F8C4BF;}
h3{font-size:16px;line-height:24px;margin:0;font-weight:700;} .mk{font-weight:400;font-size:14px;position:relative;top:-2px;}
.where{font-size:12px;line-height:18px;color:#6B7280;margin:2px 0 7px;word-break:break-all;} .where code{font-size:11px;}
.frame{width:312px;max-width:100%;margin:0 auto;overflow:hidden;padding:0 5px;box-sizing:border-box;font-size:16px;line-height:24px;}
.specs{margin:10px 0 0;border-top:1px solid #E2E8F0;padding:8px 0 0;font-size:12px;line-height:18px;color:#374151;}
.sp{word-break:break-all;} .sp b{display:inline-block;min-width:92px;color:#6B7280;font-weight:600;}
.sp.off{color:#B91C1C;} .sp.off b{color:#B91C1C;}
body.only-off article.g:not(.has-off){display:none;}
"""
    total = sum(len(v) for k, v in by.items())
    head = (f'<header><h1>그래프 모음</h1>'
            f'<p>목업 결과(experiments/*/output) 에서 그래프 흰 카드를 그대로 떼어 와 종류별로 모았습니다. 봉차트(캔들 · TradingView · 장중 차트)는 뺐습니다. 같은 그래프는 하나만 보이고 몇 쪽에서 쓰였는지 셉니다.</p>'
            f'<p>그래프마다 잰 값을 아래에 적고, 같은 종류에서 가장 흔한 값과 다르면 빨갛게 표시했습니다. 모두 {total}종. 규칙 원본 = 디자인-가이드라인.md 9절.</p></header>')
    nav = ('<nav>' + "".join(toc) + '<label class="f"><input type="checkbox" onchange="document.body.classList.toggle(\'only-off\',this.checked)"> 다른 값만 보기</label></nav>')
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>그래프 모음</title><style>{css}</style></head><body>{head}{nav}{"".join(out)}</body></html>')


# ---------- 통일 뒤 유형 샘플 (2026-11-14 사용자: "통일된 샘플만, 통일이 안 되는 유형만 하나씩") ----------
def _stub_imports():
    """render_html 이 부르는 pandas 등이 없는 PC 에서도 그림 함수만 쓰게 — 그래프 함수는 이것들을 쓰지 않는다."""
    import sys
    import types

    class _Stub(types.ModuleType):
        def __getattr__(self, k):
            return _Stub(k)

        def __call__(self, *a, **k):
            return _Stub("x")
    for m in ("pandas", "numpy", "yfinance", "requests"):
        try:
            __import__(m)
        except ImportError:
            sys.modules[m] = _Stub(m)
    sys.path[:0] = [EXP, os.path.join(EXP, "nvda-report")]


def samples():
    import sys
    """그림 함수를 지금 코드 그대로 불러 만든 샘플(선 · 줄 막대 — 이번에 고친 것)."""
    _stub_imports()
    import design_kit as dk
    import render_html as R
    pct = lambda v: f"{v:+.1f}".replace("-", "−")   # noqa: E731
    months = ["25.12", "26.01", "26.02", "26.03", "26.04", "26.05", "26.06", "26.07", "26.08", "26.09", "26.10", "26.11"]
    main = [3.1, 3.2, 2.8, 3.1, 2.9, 3.4, 3.0, 2.6, 2.9, 3.3, 3.6, 3.2]
    cmp_ = [2.4, 2.5, 2.5, 2.6, 2.4, 2.5, 2.6, 2.6, 2.5, 2.6, 2.7, 2.6]
    sparse = dk.trend_card("", months, [("이 종목", main, dk.CHART_MAIN, "solid"), ("시장", cmp_, dk.CHART_CMP, "dash")], pct)
    import math
    days = [""] * 60
    for i, lb in ((5, "26.9"), (27, "26.10"), (49, "26.11")):
        days[i] = lb
    a = [1350 + 30 * math.sin(i / 6) + i * 0.6 for i in range(60)]
    dense = dk.trend_card("", days, [("원/달러", a, dk.CHART_MAIN, "solid"), ("60거래일 평균", [sum(a) / 60] * 60, dk.CHART_CMP, "dash")],
                          lambda v: f"{v:,.0f}")
    import random
    rnd = random.Random(7)
    yv, v = [], 72.0
    for i in range(220):
        v += rnd.gauss(0, 1.6) + (2.2 if 40 <= i < 52 else -1.4 if 100 <= i < 112 else 0)
        yv.append(round(v, 1))
    ylb = [""] * 220
    ylb[40], ylb[110], ylb[-1] = "개전", "휴전", "11.13"
    year = dk.trend_card("", ylb, [("브렌트유", yv, dk.CHART_MAIN, "solid")], lambda v: f"{v:.0f}", small_end=True)
    dense = dense + '<span style="display:block;height:16px;"></span>' + year
    tabs = R.line_tabs("gsample", months[-8:], [("외국인", [1.2, -0.4, 0.8, 2.1, -1.0, 0.5, 1.6, 0.9], dk.CHART_SERIES[0]),
                                                ("기관", [-0.6, 0.9, -0.2, -1.1, 0.7, 0.2, -0.8, 0.4], dk.CHART_SERIES[1]),
                                                ("개인", [-0.5, -0.4, -0.6, -1.0, 0.3, -0.7, -0.8, -1.3], dk.CHART_SERIES[2])], pct)
    # 업종의 움직임 — daily-report/market.py 와 같은 재료 꼴: 이름 · |등락| 비율 막대 · dk.arrow 값 · 보조 줄(ETF · 5일 순위)
    sect = [("금융", 1.21, "XLF", 3), ("에너지", -0.42, "XLE", 0), ("헬스케어", 0.33, "XLV", -2), ("기술", -1.05, "XLK", None)]
    mx = max(abs(r) for _, r, _, _ in sect)
    bars = [(n, abs(r) / mx, dk.UP if r >= 0 else dk.DOWN, dk.arrow(r),
             " · ".join(x for x in (e, "" if d is None else (f"5일 순위 대비 ▲{d}" if d > 0 else f"5일 순위 대비 ▼{-d}" if d < 0 else "5일 순위와 같음")) if x))
            for n, r, e, d in sect]
    w = dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])
    rows = [dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)]
    sys.path.insert(0, os.path.join(EXP, "daily-report"))
    import cards as C   # 데일리 질문 카드 — 줄 막대 · 얇은 막대는 강조 카드 안에서 쓴다
    rowbar = C.question_card("업종의 움직임은?", "금융 강세", "positive", dk.UP, [("오늘 S&P 500 업종 가운데 금융이 가장 많이 올랐습니다.", "plain"), (C.rows_block(rows, "positive"), "html")], opened=True)
    # 얇은 비교 막대 = 한국 증시 `_hpair` 를 그대로 (main.py 는 matplotlib 등을 불러서 함수만 떼어 실행)
    import ast
    src = open(os.path.join(EXP, "kr-market-report", "main.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "_hpair") or
            (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "HPAIR_BAR_H" for t in n.targets))]
    ns = {"_dk": dk, "NOTE": dk.NOTE}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "kr-main-part", "exec"), ns)
    thin = ns["_hpair"]([("오늘", 142000, dk.CHART_MAIN), ("20일 평균", 105000, dk.CHART_CMP)], 142000)
    thinbar = C.question_card("거래는 활발한가?", "활발", "neutral", "#111",
                              [("오늘 유가증권시장 거래대금은 최근 20일 평균의 1.4배였습니다.", "plain"), (thin, "html")], opened=True)
    n = 30
    import math as _m
    band_v = [None] * 10 + [round(2.2 * _m.sin(i / 3) + i * 0.05, 2) for i in range(20)]
    band_lb = ["" for _ in range(n)]
    band_lb[0], band_lb[15], band_lb[-1] = "10.14", "11.04", "11.13"
    band = dk.trend_card("", band_lb, [("S&P 500 수익률", band_v, dk.CHART_MAIN, "solid"), ("상승 기준", [3] * n, "#FCA5A5", "dash"),
                                       ("하락 기준", [-3] * n, "#93C5FD", "dash")], pct)
    groups = [("1년", [23.2, 11.8]), ("6개월", [17.0, 4.8]), ("3개월", [6.8, -1.8]), ("1개월", [-0.3, -2.6]), ("1주", [-4.4, -2.0])]
    col = R._chart_card(groups, [R._sign_bg, R._gray], [R._sign_fg, R._note_fg], [("애플 올림", R._PASTEL_UP), ("애플 내림", R._PASTEL_DN), ("S&P 500", R._GRAY_BAR)],
                        fmt=lambda v: f"{v:+.1f}".replace("-", "−"))
    out = {"col": col, "sparse": sparse, "dense": dense, "tabs": tabs, "rowbar": rowbar, "thinbar": thinbar, "band": band}
    return {k: dk.fix_colons(v) for k, v in out.items()}   # 리포트 마지막 공용 마무리 — 증감 삼각형 = 글자 80% (5절) 등, 실제 페이지와 같게


# (키, 묶음, 이름, 왜 따로인가, 어디서, 샘플 = ("call", 키) | ("pick", 종류, 제목에 든 글자))
TYPES = [
    ("col", "세로 막대", "세로 막대",
     "하나로 통일됨. 이 종목 오름 · 내림(연빨강 · 연파랑) + 비교 회색, 또는 주황 · 회색 두 계열. 막대 폭 14~20(숫자 폭 × 0.45) · 모서리 3 · 숫자 13 굵게 · 눈금선 #ECF0F5 · 축 오른쪽.",
     "R._col_chart · cards.col_chart · kr-market-report · kr-stocks · 테마 · 운영 현황 — 38곳, 하루 조각(시가 · 갭 · 장중 · 종가)만 오름 · 내림 칩 범례 예외",
     ("call", "col")),
    ("sparse", "선 그래프", "점 있는 선 (월별 · 분기 · 24점 이하)",
     "값마다 읽어야 해서 점 · 숫자 · 가로축 이름이 다 있다. 끝 값은 점 오른쪽.",
     "R.line_chart · dk.trend_card — 종목 분기 매출 · 업계 지표 · 한국 증시 12개월 · 8분기 · 공매도 비율",
     ("call", "sparse")),
    ("dense", "선 그래프", "촘촘한 선 (일별 60거래일 · 1년)",
     "점이 많아 점 · 숫자를 다 찍으면 읽을 수 없다 — 끝 값만, 가로축은 달이 바뀌는 자리만, 카드 폭에 다 넣는다.",
     "dk.trend_card — 데일리 환율 · 원화 S&P 500 · 한국 증시 금리 · 환율 · 거래대금 · 간단 정보 1년 · 증시 전망 · 이슈 올해 그래프(아래, 사건 날 가로축 이름)",
     ("call", "dense")),
    ("tabs", "선 그래프", "버튼으로 고르는 선 (선 셋 이상)",
     "선이 셋 이상이면 겹쳐 읽을 수 없다 — 버튼을 누른 선만 색 · 숫자, 한 번 더 누르면 처음(모든 선 제 색).",
     "R.line_tabs — 투자자별 순매수 · 의견 건수",
     ("call", "tabs")),
    ("band", "선 그래프", "기준선 두 개가 있는 선 (증시 전망)",
     "전망 채점 기준(상승 기준 · 하락 기준)이 방향을 뜻해서 연빨강 · 연파랑 실선 1 — 회색 하나로 합치면 두 기준을 구별할 수 없다.",
     "증시 전망 · 이슈 페이지 (dk.trend_card ends_only)",
     ("call", "band")),
    ("range", "가로 막대", "범위 막대 + 말풍선 (연속)",
     "최저 ~ 최고 사이 지금 위치. 목표가 막대는 같은 꼴에 중앙 · 평균 눈금만 더한다.",
     "R.year_range_in · cards.range_gauge · R.target_gauge — 가격 범위 (1년) · 변동성 지수 범위 · 애널리스트 목표가",
     ("pick", "hgauge", "가격 범위 (1년)")),
    ("zone", "가로 막대", "세 칸 막대 + 말풍선 (판정)",
     "값이 어느 칸(하락 · 범위 안 · 상승 같은 판정)에 드는지가 답 — 칸 이름 · 진한 칸이 있다.",
     "R._zone_gauge — 한 달간 변화 범위 · 12개월 모멘텀 · 돈 흐름",
     ("pick", "hgauge", "한 달간 변화 범위")),
    ("track", "가로 막대", "100% 비율 막대",
     "전체를 나눈 몫(뉴스 방향 · 애널리스트 의견) — 막대 안에 % 숫자, 높이 24.",
     "dk.legend_bar · dk.direction_bars — 뉴스 방향 · 애널리스트 의견 · 이슈 소식",
     ("pick", "track", "애널리스트")),
    ("rowbar", "가로 막대", "줄 막대 (강조 카드 안 · 이름 · 막대 · 값)",
     "여러 줄의 크기를 견준다 — 줄마다 구분선, 이름 · 값 15 굵게, 값 = 증감 색 + 삼각형(글자의 80%), 보조 줄 13. 막대 9 · 모서리 3 · 색 카드 위라 바탕 흰색. 흰 카드 안에서는 막대 10 · 바탕 #F1F5F9(ETF 구성 비중).",
     "dk.bar_row · dk.hbar — 데일리 업종 등락 · 큰손 선물 · 한국 증시 업종 · 운영 현황 · ETF 구성 비중 · 강좌",
     ("call", "rowbar")),
    ("thinbar", "가로 막대", "얇은 비교 막대 (강조 카드 안 · 둘 견주기)",
     "카드 문장 아래 두세 개(오늘 · 평균)만 작게 견준다 — 이름 · 값이 작은 글씨, 막대 7 · 색 카드 위라 바탕 흰색.",
     "kr-market-report _hpair — 한국 증시 거래대금 (오늘 · 20일 평균)",
     ("call", "thinbar")),
    ("arc", "기타", "반원 게이지",
     "여러 지표를 하나의 판정(강한 하락 ~ 강한 상승)으로 모은 바늘. 큰 것(칸 이름 있음)과 나란히 놓는 작은 것은 같은 함수의 크기 차이.",
     "tech_signals.gauge_svg — 기술 지표 · 이동평균 · 이슈 뉴스 방향",
     ("pick", "arc", "큰 반원")),
]

DONE = [
    "선 그래프 그림 칸 높이 = 130 하나로 — 종목 페이지 선(R.line_chart 230 → 212) · 점 있는 선(dk.trend_card +12 → +14) · 촘촘한 선(150)이 같은 그림 칸",
    "주황 진하게 #F5B971 → #F59E0B (선 · 막대 · 점 · 범례 모두), 주황 글자(최신 가로축 이름 · 누른 버튼 글자)는 한 단계 더 진한 #D97706 (2026-11-14 사용자)",
    "그래프 범례 · `넘겨 보기` · 범례 단위 14 → 13 (LEGEND_FS) — 가로축 이름(13) · 세로축 숫자는 그대로 (2026-11-14 사용자)",
    "비교 선 · 기준선 점선 폐지 → 실선 1 (범례 칩도). 상승 기준 연빨강 · 하락 기준 연파랑 색은 그대로 (2026-11-14 사용자)",
    "선 그래프 값 글자 = 모두 검정(최신 13 굵게 · 나머지 12 보통) — 점 있는 선 · 촘촘한 선 · 버튼 선 · 기준선 선 하나로 (2026-11-14 사용자)",
    "여러 계열 청록 · 보라도 진하게 #5FBFAF → #14B8A6 · #BFA2E8 → #A78BFA (2026-11-14 사용자)",
    "촘촘한 선 · 기준선 선의 끝 점 = 점 있는 선 최신 점과 같은 크기(반지름 5 · 테두리 4), 지그재그 1년(브렌트유)만 옛 작은 점 (2026-11-14 사용자)",
    "평평한 비교선(상승 · 하락 기준 · 60거래일 평균) = 눈금선처럼 세로축 숫자 앞까지 (2026-11-14 사용자)",
    "버튼 외곽선 #B5BAC0 → #D5DAE0 (2026-11-14 사용자)",
    "버튼 선: 누른 버튼을 한 번 더 누르면 처음(모든 선 제 색)으로 (2026-11-14 사용자)",
    "점 있는 선 최신 가로축 이름 = 선 색 + 위 3px 점 — 한국 증시 · 업계 지표 쪽이 검정 · 점 없음이었다(9절 규칙)",
    "촘촘한 선의 둘째 실선 계열 굵기 1 → 2 (국고채 10년 · 코스닥 같은 것) — 비교 대상(점선 · 얇은 선)만 1",
    "간단 정보 · ETF 목업 1년 선: 오름 · 내림 색 선 + #94A3B8 → 주황 + 회색 점선(그래프 색 표)",
    "ETF 구성 비중 막대: 8 · 모서리 4 · 회색 → dk.hbar(10 · 3 · 바탕 #F1F5F9) · 주황(부호 없는 크기)",
    "강좌 막대: 16 · 모서리 4 · 주황 #F59E0B · 청록 #0F766E → 10 · 3 · 그래프 색 표(주황 · 회색 · 청록)",
]


def render_types(items, made):
    pick = {}
    for key, _, _, _, _, (how, *arg) in TYPES:
        if how == "call":
            pick[key] = made[arg[0]]
            continue
        kind, needle = arg
        cand = [it for it in items if it["kind"] == kind and needle in it["title"]]
        pick[key] = cand[0]["html"] if cand else ""
    groups = collections.OrderedDict()
    for key, grp, name, why, where, _ in TYPES:
        groups.setdefault(grp, []).append(
            f'<article class="g"><h3>{esc(name)}</h3><p class="why">{esc(why)}</p><div class="frame">{pick[key]}</div>'
            f'<p class="where">{esc(where)}</p></article>')
    body = "".join(f'<section><h2>{esc(g)} <em>{len(v)}종</em></h2><div class="grid">{"".join(v)}</div></section>' for g, v in groups.items())
    done = "".join(f"<li>{esc(x)}</li>" for x in DONE)
    css = """
body{margin:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#111;}
header,section{max-width:1200px;margin:0 auto;padding:24px 16px 8px;}
h1{font-size:24px;line-height:32px;margin:0 0 6px;} header p{margin:0 0 6px;font-size:14px;line-height:22px;color:#4B5563;}
header ul{margin:8px 0 0;padding:10px 12px 10px 28px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:13px;line-height:21px;color:#374151;}
h2{font-size:20px;line-height:28px;margin:0 0 12px;} h2 em{font-style:normal;color:#6B7280;font-weight:400;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;align-items:start;}
article.g{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:14px;min-width:0;}
h3{font-size:16px;line-height:24px;margin:0 0 4px;} .why{margin:0 0 10px;font-size:13px;line-height:20px;color:#374151;}
.where{margin:10px 0 0;font-size:12px;line-height:18px;color:#6B7280;}
.frame{width:312px;max-width:100%;margin:0 auto;padding:0 5px;box-sizing:border-box;font-size:16px;line-height:24px;}
"""
    n = len(TYPES)
    head = (f'<header><h1>그래프 유형</h1><p>비슷한 그래프는 하나로 맞추고, 정보의 꼴 때문에 더 합칠 수 없는 유형만 하나씩 남겼습니다 — {n}종. '
            f'봉차트와 확대 보기 그림 파일(PNG, 삭제 예정)은 뺐습니다. 규칙 원본 = 디자인-가이드라인.md 9절.</p>'
            f'<p>선 · 줄 막대 샘플은 지금 코드를 바로 불러 그렸고, 나머지는 목업 결과에서 떼어 왔습니다.</p>'
            f'<p><b>이번에 맞춘 것</b></p><ul>{done}</ul></header>')
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>그래프 유형</title><style>{css}</style></head><body>{head}{body}</body></html>')


if __name__ == "__main__":
    import sys
    items = collect()
    if "--all" in sys.argv:   # 옛 전체 목록(종류별 모든 그래프 · 잰 값) — 통일 확인용
        open(os.path.join(HERE, "output", "mock_graphs_all.html"), "w", encoding="utf-8").write(render(items))
    open(OUT, "w", encoding="utf-8").write(render_types(items, samples()))
    print(OUT)
