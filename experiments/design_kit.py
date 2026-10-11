"""디자인 가이드라인(디자인-가이드라인.md) 공통 조각 — 데일리 리포트·트럼프 트렌드 렌더러가 같이 쓴다 (2026-10-11).

엔비디아 리포트(experiments/nvda-report/render_html.py)에서 굳은 규칙을 그대로 옮겼다: 18px 본문, 21px 구획 제목, 카드 A·C·D·E·F,
안내 글은 ⓘ + 14px 회색, 라벨은 외곽선 알약 16px, 링크는 아이콘, 날짜는 점 표기. 숫자는 파이썬이 그린다.
의존성 없음 — 각 파이프라인은 sys.path 에 experiments/ 를 넣고 `import design_kit as dk` 로 쓴다.
"""

import html as html_mod
import re

UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
NOTE = "#6B7280"          # 안내 글 회색
BODY, SMALL, TINY, MICRO = "18px", "16px", "14px", "14px"
H2 = "position:relative;color:#111;font-size:21px;font-weight:700;line-height:1.3;margin:28px 0 11px;padding:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;"
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:6px;"
_NO_LINE_START = re.compile(r'^\s*(<div style="(?:overflow-x:auto;|background:)|<div data-cards|<div data-lead|<img\b|<details\b)')
CARD = "background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:12px 14px;"
CARD_DIR = {"positive": ("#FFF7ED", "#FED7AA"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#E2E8F0"), "uncertain": ("#FFFBEB", "#FDE68A")}
PILL = {"area": ("#CBD5E1", "#334155"), "positive": ("#FCA5A5", "#B91C1C"), "negative": ("#93C5FD", "#1D4ED8"),
        "uncertain": ("#FDBA74", "#C2410C"), "neutral": ("#CBD5E1", "#64748B")}
PILL_BG = {"positive": "#FEF2F2", "negative": "#EFF6FF"}
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"), "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
COL_L = "flex:0 0 65%;max-width:65%;min-width:0;white-space:normal;"   # 카드 왼쪽 65% (가이드라인 2-1, 2026-10-11 사용자: 꼭 지킨다)
COL_R = "flex:1 1 0;min-width:0;text-align:right;white-space:normal;word-break:keep-all;"   # 카드 오른쪽 35%
ROW = ("display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 6px;padding:8px 12px;"
       "background:#fff;border:1px solid #E2E8F0;border-radius:8px;white-space:nowrap;line-height:1.5;")
ROW_UP, ROW_DOWN = "background:#FFF7ED;border-color:#FED7AA;", "background:#EFF6FF;border-color:#BFDBFE;"
MULTI = f"display:block;margin:0 0 6px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};"
MULTI_ROW = "display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 12px;white-space:nowrap;line-height:1.5;"
MULTI_SEP = "border-top:1px solid #E2E8F0;"
UL, LI = "margin:0 0 8px 20px;padding:0;list-style:disc;", "margin:6px 0;"
INFO_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;margin-right:4px;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>')
QUESTION_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'   # 툴팁 아이콘 = ? (2026-10-11 사용자)
                 '<circle cx="8" cy="8" r="6.5"/><path d="M6.1 6.2a1.95 1.95 0 1 1 2.7 1.8c-.5.2-.8.6-.8 1.1v.5"/><circle cx="8" cy="11.4" r=".9" fill="currentColor" stroke="none"/></svg>')
LINK_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M9 3h4v4"/><path d="M13 3 7 9"/><path d="M11 9v4H3V5h4"/></svg>')
NEW_PILL = ('<span style="display:inline-block;background:#B91C1C;color:#fff;border-radius:3px;padding:1px 4px 0;font-size:10px;font-weight:700;'
            'line-height:13px;vertical-align:middle;margin-left:4px;">N</span>')
WRAP_OPEN = ('<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
             f'font-size:{BODY};line-height:1.53;color:#333;">')
WRAP_CLOSE = "</div>"
_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_PAREN = re.compile(r"\s*(\([^()]*\))")


def esc(t):
    return html_mod.escape(str(t), quote=False)


def day(t):
    """2026-10-09 → 2026.10.9 (가이드라인 3-3). 문자열 안의 날짜를 모두 바꾼다."""
    return _ISO_DAY.sub(lambda m: f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}", str(t)) if t else t


def paren(name_html):
    """카드 구분명의 (…) 부분을 한 단계 작게·보통 굵기로 (이미 이스케이프된 HTML)."""
    return _PAREN.sub(lambda m: f' <span style="font-size:{MICRO};font-weight:400;">{m.group(1)}</span>', name_html)


def arrow(v, digits=2, unit="%"):
    """증감 ▲ 빨강 · ▼ 파랑 · 0 회색, 숫자는 절댓값."""
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    col = UP if v > 0 else DOWN if v < 0 else MUTED
    tri = "▲" if v > 0 else "▼" if v < 0 else "–"
    return f'<span style="color:{col};font-weight:700;white-space:nowrap;">{tri}&nbsp;{abs(v):.{digits}f}{unit}</span>'


def dash():
    return f'<span style="color:{MUTED};">—</span>'


def h2(t, line=True, summary="", tab=None, aside="", one_line=False):
    """구획 제목. tab = 이 구획이 들어갈 탭 이름 (가이드라인 11절) — 테마 JS가 h2[data-tab]을 읽어 탭을 만든다."""
    sm = (f' <span data-summary="1" style="font-size:{TINY};font-weight:400;color:{NOTE};line-height:1.5;white-space:normal;flex:1 1 220px;">{INFO_ICON}{summary}</span>'
          if summary else "")
    tb = f' data-tab="{esc(tab)}"' if tab else ""
    st = H2.replace("flex-wrap:wrap;", "flex-wrap:nowrap;") if one_line else H2   # one_line: 제목과 aside 를 폰에서도 한 줄로 (2026-10-11 사용자)
    return f'<h2{tb} style="{st}{H2_LINE if line else ""}">{esc(t)}{sm}{aside}</h2>'   # aside = 제목 줄 오른쪽 요소 (캡슐 줄 등)


def section(title, html, summary="", line=None, tab=None, aside="", one_line=False):
    """제목(+옆 요약) + 내용. 바로 아래가 카드·표·그림이면 구분선을 긋지 않는다 (가이드라인 2절)."""
    if line is None:
        line = not _NO_LINE_START.match(html or "")
    return h2(title, line=line, summary=summary, tab=tab, aside=aside, one_line=one_line) + (html or "")


def ko(text, table):
    """영어 용어 → 한국어 (가이드라인 3-4). table 의 키를 긴 것부터 단어 경계로 바꾼다. 없는 말은 그대로."""
    if not text:
        return text
    out = str(text)
    for en in sorted(table, key=len, reverse=True):
        out = re.sub(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", table[en], out)
    return out


def note(t):
    """구획 안내 줄 — 내용 아래, ⓘ, 14px 회색, 윗선."""
    return f'<div style="margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;font-size:{TINY};color:{NOTE};">{INFO_ICON}{esc(t)}</div>'


_SIGNED = re.compile(r"(?<![\w.~])(?<!~ )([+\-−])(\d+(?:\.\d+)?)(%p|%|bp)(?!\s*~)")   # 범위(-0.63 ~ +0.63%)는 칠하지 않는다
_LABEL = re.compile(r"^([^:：]{1,24}?)\s*:\s+(.+)$", re.S)


# 증감 값 앞의 종목 이름 — "산업재(XLI)", "나스닥 100(QQQ)", "1위 기술" (2026-10-11 사용자: 종목도 같이 색)
_NAMED = re.compile(r"((?:\d+위 )?(?:[A-Za-z][A-Za-z&;]* |[가-힣A-Za-z]+ (?=\d))?[가-힣A-Za-z0-9&;]+(?:\([A-Z0-9^.&;\s]{1,12}\))|\d+위 [가-힣A-Za-z&;·]+)\s"
                    r"(?<![\w.~])([+\-−])(\d+(?:\.\d+)?)(%p|%|bp)(?!\s*~)")


def tint(html_text):
    """이스케이프된 글 안의 증감에 색 — 증가 빨강 · 감소 파랑 (가이드라인 3-3, 2026-10-11 사용자).
    앞에 종목 이름(이름(티커) 또는 'n위 이름')이 붙어 있으면 이름까지 한 덩어리로 칠한다: 산업재(XLI) -0.25% 전체 파랑. 범위(-0.63 ~ +0.63%)는 칠하지 않는다."""
    def named(m):
        col = UP if m.group(2) == "+" else DOWN
        return f'<span style="color:{col};">{m.group(1)} <span style="white-space:nowrap;">{m.group(2)}{m.group(3)}{m.group(4)}</span></span>'
    out = _NAMED.sub(named, html_text)
    parts = re.split(r"(<span[^>]*>.*?</span></span>)", out)   # 이미 칠한 덩어리는 건너뛰고 나머지의 맨 숫자만
    return "".join(p if p.startswith("<span") else _SIGNED.sub(lambda m: f'<span style="color:{UP if m.group(1) == "+" else DOWN};white-space:nowrap;">{m.group(0)}</span>', p) for p in parts)


def label_text(text):
    """"라벨: 내용" 글 → **라벨** : 내용(증감 색). 라벨이 없으면 내용만 (가이드라인 3-3)."""
    m = _LABEL.match(str(text))
    if m:
        return f"<b>{esc(m.group(1))}</b> : {tint(esc(m.group(2)))}"
    return tint(esc(text))


def dot_li(inner_html, size=3, color="#111", top=11, margin="3px 0"):
    """점 글머리표 한 줄 — 16px 글은 3px 점, 14px 안내 글은 2px 점 (가이드라인 3-3)."""
    return (f'<li style="display:flex;align-items:flex-start;gap:7px;margin:{margin};color:{color};">'
            f'<span style="flex:none;width:{size}px;height:{size}px;border-radius:50%;background:{color};margin-top:{top}px;"></span><span>{inner_html}</span></li>')


GUIDE_SHORT = 70   # 이보다 짧은 한 문장은 한 줄 "제목: 내용"


GUIDE_IND = "padding-left:14px;"   # 카드 밖 안내 줄은 왼쪽 14px 들여쓰기, 카드 안 안내는 제외 (2026-10-11 사용자: 일괄)


def guide(title, body, line=True, grid=False, in_card=False):
    """제목이 있는 안내 글 (가이드라인 3-3, 2026-10-11 사용자). 14px 안내 회색 + ⓘ.
    - 짧으면 한 줄: ⓘ **주의**: 내용
    - 길거나 항목이 여럿이면: ⓘ **읽는 법** 다음 줄부터 글머리표 "막대 = 내용", "회색 띠 = 내용"
    body: 문자열 또는 [(이름, 내용) | 문자열, ...]. line=True 면 위에 얇은 선(구획 안내 줄), 카드 안에서는 False."""
    if in_card:
        top = "margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;" if line else "margin:4px 0 0;"
    else:   # 카드 밖: 위아래 여백 40% 줄임 + 20px 들여쓰기 (2026-10-11 사용자)
        top = ("margin:3.07px 0 1.54px;padding-top:2.3px;border-top:1px solid #f3f3f3;" if line else "margin:1.54px 0 0;") + GUIDE_IND
    head = f'{INFO_ICON}<b style="color:#4B5563;">{esc(title)}</b>'
    if isinstance(body, str) and len(body) <= GUIDE_SHORT:
        return f'<div style="{top}font-size:{TINY};color:{NOTE};line-height:1.5;">{head} : {esc(body)}</div>'
    items = [body] if isinstance(body, str) else body
    lis = "".join(dot_li(tint(esc(it[0]) + ' = ' + esc(it[1])) if isinstance(it, tuple) else tint(esc(it)), size=2, color=NOTE, top=9, margin="2px 0") for it in items)   # 14px 안내 → 2px 점
    return (f'<div style="{top}font-size:{TINY};color:{NOTE};line-height:1.5;">{head}'
            f"<ul{' data-guide-grid=\"1\"' if grid else ''} style='margin:2px 0 0 2px;padding:0;list-style:none;'>{lis}</ul></div>")   # grid: 데스크톱 2열 (테마 CSS)



def guide_card(title, body, notes=()):
    """읽는 법 카드 (2026-10-11 사용자: "읽는 법만 카드를 분리하여 그래프 아래에, 일괄") — 그래프·표 바로 아래 옅은 회색 카드 안에 guide().
    notes = [(제목, 내용), …] — 주의처럼 짧은 안내도 같은 카드 안 아래쪽에 한 줄씩 (2026-10-11 사용자: "주의도 읽는 법 카드에 포함")."""
    extra = "".join(guide(t, x, line=False, in_card=True) for t, x in notes)
    return (f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:8px 14px 10px;margin:8px 0;">'
            + guide(title, body, line=False, grid=True, in_card=True) + (f'<div style="margin-top:6px;padding-top:4px;border-top:1px solid #E2E8F0;">{extra}</div>' if extra else "") + "</div>")   # 글머리표는 데스크톱에서 2열 (2026-10-11 사용자)




def tip(text):
    """ⓘ 툴팁 아이콘 — 글은 data-tip 속성, 모양은 테마 CSS(build_theme.py `[data-tip]::after`). 줄바꿈(\n)은 툴팁 안에서 줄을 바꾼다.
    상자는 position:relative 인 가장 가까운 줄 기준으로 놓인다 — 아이콘은 그런 줄 안에 둔다."""
    t = esc(text).replace(chr(34), "&quot;").replace("\n", "&#10;")
    return (f'<span data-tip="{t}" tabindex="0" role="button" aria-label="{t}" '
            f'style="color:{NOTE};cursor:help;vertical-align:middle;margin-left:2px;">{QUESTION_ICON}</span>')


def tip_line(items, in_title=False):
    """용어 툴팁 줄 — "용어ⓘ · 용어ⓘ". 14px 안내 회색. items = [(용어, 설명)]. 줄이 position:relative 라 상자가 줄 폭 안에 뜬다."""
    inner = ' <span style="color:#CBD5E1;">·</span> '.join(f'<span style="white-space:nowrap;">{esc(k)}{tip(v)}</span>' for k, v in items)
    if in_title:   # 구획 제목 줄 오른쪽 (2026-10-11 사용자: "급상승 주제 타이틀 우측에") — 툴팁 상자는 position:relative 인 h2 기준
        return f'<span style="font-size:{TINY};font-weight:400;color:{NOTE};line-height:1.6;margin-left:auto;align-self:center;white-space:nowrap;flex:none;">{inner}</span>'
    return f'<div style="position:relative;font-size:{TINY};color:{NOTE};line-height:1.6;margin:2.3px 0 0.77px;{GUIDE_IND}">{inner}</div>'



_COLON = re.compile(r"[ \t]*:[ \t]*")
_TAG = re.compile(r"(<[^>]+>)")
_TIP_ATTR = re.compile(r'((?:data-tip|title|aria-label)=")([^"]*)(")')


def _space_colons(t):
    def fix(m):
        s, e = m.start(), m.end()
        before, after = t[s - 1:s], t[e:e + 1]
        if (before.isdigit() and after.isdigit()) or t[e:e + 2] == "//" or t[s:e].startswith("://"):
            return m.group(0)   # 시각 09:30 · 비율 35:2 · 주소 https:// 는 그대로
        return " : "
    return _COLON.sub(fix, t)


def fix_colons(html):
    """보이는 글의 ":" 는 앞뒤를 한 칸씩 띄운다 — "라벨 : 값" (2026-10-11 사용자: 꼭 반드시, 모든 페이지 일괄).
    글자 노드와 툴팁·제목 속성(data-tip · title · aria-label)만 고친다. style · script 안, 시각·비율(숫자:숫자), 주소(://)는 건드리지 않는다.
    각 리포트의 build_body 마지막에 한 번 건다 — LLM 서술도 같이 고쳐진다."""
    out, skip = [], False
    for part in _TAG.split(html):
        if part.startswith("<") and part.endswith(">"):
            low = part[:8].lower()
            if low.startswith(("<script", "<style")):
                skip = True
            elif low.startswith(("</script", "</style")):
                skip = False
            out.append(_TIP_ATTR.sub(lambda m: m.group(1) + _space_colons(m.group(2)) + m.group(3), part))
        else:
            out.append(part if skip else _space_colons(part))
    return "".join(out)


def capsules(items, size=None, in_title=False):
    """캡슐 줄 (2026-10-11 사용자: "게시물 : 9건 캡슐 라인 디자인으로 연속해서") — 알약 모양 칸을 한 줄에 이어 놓고, 넘치면 다음 줄로.
    items = [(라벨, 값HTML)]. 라벨 16px 안내 회색 · 값 16px 검정 굵게, "라벨 : 값". 흰 바탕, 테두리 #E2E8F0, 모서리 끝까지 둥글게."""
    pill = ("display:inline-flex;align-items:center;gap:4px;padding:5px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:999px;"
            f"font-size:{size or SMALL};font-weight:400;line-height:1.4;white-space:nowrap;")
    inner = "".join(f'<span style="{pill}"><span style="color:{NOTE};">{esc(k)} : </span><b style="color:#111;">{v}</b></span>' for k, v in items)
    if in_title:   # 구획 제목 줄 오른쪽 (2026-10-11 사용자: "14 폰트로, 발언 타이틀 우측에") — 좁으면 제목 아래로 내려간다
        return f'<span data-capsules="1" style="display:flex;flex-wrap:wrap;gap:6px;margin-left:auto;align-self:center;">{inner}</span>'
    return f'<div data-capsules="1" style="display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px;">{inner}</div>'


def muted(t):
    """짧은 안내 글 (빈 구획 안내 등) — ⓘ 필수."""
    return f'<div style="color:{NOTE};font-size:{TINY};margin:2.3px 0;{GUIDE_IND}">{INFO_ICON}{esc(t)}</div>'   # 여백 40% 줄임 (2026-10-11 사용자)


def notice(parts):
    """안내 상자 (노랑) — 14px."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return (f'<div style="background:#fff8e1;border:1px solid #f4d37a;border-radius:6px;padding:10px 14px;font-size:{TINY};line-height:1.6;margin:0 0 12px;">'
            + "<br>".join(INFO_ICON + p for p in parts) + "</div>")


def pill(text, kind="area"):
    bd, fg = PILL.get(kind, PILL["neutral"])
    bg = PILL_BG.get(kind, "#fff")
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {bd};border-radius:4px;padding:3px 5px 2px;'
            f'font-size:{SMALL};font-weight:400;line-height:1;white-space:nowrap;vertical-align:middle;">{esc(text)}</span>')


def link_icon(url, label):
    if not url:
        return ""
    return (f' <a href="{esc(url)}" title="{esc(label)}" aria-label="{esc(label)}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;text-decoration:none;white-space:nowrap;">{LINK_ICON}</a>')


def ul(items_html):
    return f"<ul style='{UL}'>" + "".join(items_html) + "</ul>"


def bullets(texts):
    return ul(f"<li style='{LI}'>{tint(esc(t))}</li>" for t in texts)   # 서술 문장의 증감도 같은 색 규칙


def row(name, value_html, tone=""):
    """A타입 한 줄 카드: 이름 좌 · 값 우 (18px)."""
    return f'<span style="{ROW}{tone}"><span style="{COL_L}font-weight:700;color:#111;">{esc(name)}</span> <span style="{COL_R}">{value_html}</span></span> '


def multi(rows):
    """C타입: (이름, 값HTML) 여러 줄을 한 카드에. data-grid=2: 데스크톱에서 2열 (테마 CSS)."""
    out = ""
    for i, (name, value_html) in enumerate(rows):
        out += (f'<span style="{MULTI_ROW}{MULTI_SEP if i else ""}"><span style="{COL_L}font-weight:700;color:#111;">{paren(esc(name))}</span> '
                f'<span style="{COL_R}font-weight:700;">{value_html}</span></span> ')
    return f'<span data-grid="2" style="{MULTI}">{out}</span> '


def multi2(items):
    """E타입 2열 멀티 카드: 한 줄에 둘, 세로 구분선."""
    cell = "display:flex;flex:1;min-width:0;justify-content:space-between;align-items:center;gap:8px;padding:8px 12px;white-space:nowrap;line-height:1.5;"
    out = ""
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        r = ""
        for j, (name, value_html) in enumerate(pair):
            r += (f'<span style="{cell}{"border-left:1px solid #E2E8F0;" if j else ""}">'
                  f'<span style="{COL_L}font-weight:700;color:#111;">{paren(esc(name))}</span> <span style="{COL_R}font-weight:700;">{value_html}</span></span> ')
        if len(pair) == 1:
            r += f'<span style="{cell}border-left:1px solid #E2E8F0;"></span>'
        out += f'<span data-pair="1" style="display:flex;{MULTI_SEP if i else ""}">{r}</span> '
    return f'<span style="{MULTI}">{out}</span> '


def crow(name_html, value_html, sub="", first=False, left=None):
    """C 카드 한 줄 + 보조 줄(14px #999). name_html 은 이스케이프된 HTML."""
    sub_html = f'<span style="display:block;color:{MUTED};font-weight:400;font-size:{TINY};white-space:normal;">{paren(sub)}</span>' if sub else ""
    return (f'<span style="{MULTI_ROW}{"" if first else MULTI_SEP}">'
            f'<span style="display:block;{COL_L}"><span style="font-weight:700;color:#111;">{paren(name_html)}</span>{sub_html}</span> '
            f'<span style="{COL_R}font-weight:700;">{value_html}</span></span> ')   # 왼쪽 65% · 오른쪽 35% 고정 — left 인자는 무시


EMPH_BG, EMPH_BD = "#FFF7ED", "#FED7AA"   # 강조 카드 배경·테두리 (오렌지)


def ccard(rows, left=None, attrs="", emph=False):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html)]. emph=True 면 강조 카드 배경(오렌지, 줄 구분선도 오렌지) — 2026-10-11 사용자: 급상승 주제."""
    inner = "".join(crow(n, v, sb, first=(i == 0), left=left) for i, (n, v, sb) in enumerate(rows))
    box = MULTI
    if emph:
        inner = inner.replace(MULTI_SEP, f"border-top:1px solid {EMPH_BD};")
        box = MULTI.replace("background:#fff;border:1px solid #E2E8F0;", f"background:{EMPH_BG};border:1px solid {EMPH_BD};--grid-line:{EMPH_BD};")
    return f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span data-grid="2" style="{box}">{inner}</span></div>'


def cards(html):
    """글 머리 카드 묶음 — data-lead: 홈 카드가 제목 없는 머리 구획으로 읽는다 (data-cards 는 엔비디아 탭 JS 가 보므로 여기선 쓰지 않는다)."""
    return f'<div data-lead="1" style="margin:0 0 8px;">{html}</div>'


def dcard(html, theme="neutral"):
    """D 본문 카드 (문장·목록). 배경은 방향 테마."""
    bg, bd = CARD_DIR.get(theme, CARD_DIR["neutral"])
    return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:12px 14px;margin:0 0 8px;">{html}</div>'


def sub_label(t):
    return f'<div data-sub="1" style="font-size:{SMALL};color:{NOTE};margin:10px 0 3px;">{paren(esc(t))}</div>'


def bar(label, segs):
    """F 비율 막대: segs = [(이름, 개수, 배경, 글자)]."""
    total = sum(n for _, n, _, _ in segs)
    if not total:
        return ""
    pcts = " · ".join(f"{nm} {n / total * 100:.0f}%" for nm, n, _, _ in segs if n)
    body = "".join(f'<span style="display:block;width:{n / total * 100:.1f}%;background:{bg};color:{fg};font-size:{SMALL};font-weight:700;'
                   f'text-align:center;line-height:24px;overflow:hidden;white-space:nowrap;">{f"{n / total * 100:.0f}%" if n / total >= 0.08 else ""}</span>' for _, n, bg, fg in segs if n)
    return (f'<span style="display:block;font-size:{SMALL};color:{NOTE};margin:0 0 3px;">{esc(label)} · {esc(pcts)}</span>'
            f'<span style="display:flex;width:100%;height:24px;border-radius:6px;overflow:hidden;background:#F1F5F9;margin:0 0 10px;">{body}</span>')


def hbar(value, max_value, color):
    """가로 막대 하나 (섹터 등락 등) — 카드 값 칸 안에 작게."""
    pct = 0 if not max_value else min(100, abs(value) / max_value * 100)
    return (f'<span style="display:inline-block;vertical-align:middle;width:80px;height:10px;background:#F1F5F9;border-radius:3px;overflow:hidden;margin-right:8px;">'
            f'<span style="display:block;height:100%;width:{pct:.0f}%;background:{color};"></span></span>')


def table(headers, rows, note_text=""):
    """표 — 카드로 못 푸는 통계 행렬에만. 16px, 칸은 어절 단위로만 줄바꿈, 좁은 화면은 표만 가로 스크롤."""
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;font-size:{TINY};color:{NOTE};font-weight:400;">{esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:0 0 8px;font-size:{SMALL};">'
            f"<tr>{th}</tr>{body}</table></div>") + (note(note_text) if note_text else "")


def footer(data_line, disclaimer_line):
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:{TINY};color:{NOTE};line-height:1.6;{GUIDE_IND}">'
            f"{INFO_ICON}{data_line}<br>{INFO_ICON}{disclaimer_line}</div>")
