"""디자인 가이드라인(디자인-가이드라인.md) 공통 조각 — 데일리 리포트·트럼프 트렌드 렌더러가 같이 쓴다 (2026-10-11).

엔비디아 리포트(experiments/nvda-report/render_html.py)에서 굳은 규칙을 그대로 옮겼다: 18px 본문, 21px 구획 제목, 카드 A·C·D·E·F,
안내 글은 ⓘ + 14px 회색, 라벨은 외곽선 알약 16px, 링크는 아이콘, 날짜는 점 표기. 숫자는 파이썬이 그린다.
의존성 없음 — 각 파이프라인은 sys.path 에 experiments/ 를 넣고 `import design_kit as dk` 로 쓴다.
"""

import html as html_mod
import os
import re

UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
SUB = "#7A7A7A"   # 카드 보조 글(보조 줄·· 현재가·/ 100·날짜) — #999 보다 20% 진하게 (2026-10-11 사용자). "—" 자리 표시는 MUTED 그대로
NOTE = "#6B7280"          # 안내 글 회색
BODY, SMALL, TINY, MICRO = "18px", "16px", "14px", "14px"
H2 = "position:relative;color:#111;font-size:21px;font-weight:700;line-height:1.3;margin:28px 0 11px;padding:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;"
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:6px;"
_NO_LINE_START = re.compile(r'^\s*(<div style="(?:overflow-x:auto;|background:)|<div data-cards|<div data-lead|<img\b|<details\b)')
CARD = "background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:12px 14px;"
CARD_DIR = {"positive": ("#FFF7ED", "#FED7AA"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#E2E8F0"), "uncertain": ("#FFFBEB", "#FDE68A")}
PILL = {"area": ("#CBD5E1", "#334155"), "positive": ("#FCA5A5", "#B91C1C"), "negative": ("#93C5FD", "#1D4ED8"),
        "uncertain": ("#FDBA74", "#C2410C"), "neutral": ("#CBD5E1", "#64748B"),
        "good": ("#86EFAC", "#15803D")}   # 신호등 🟢 정상·양호 (2026-10-12 사용자: 정상 라벨은 녹색)
PILL_BG = {"positive": "#FEF2F2", "negative": "#EFF6FF", "good": "#F0FDF4"}
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"), "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
COL_L = "flex:0 0 65%;max-width:65%;min-width:0;white-space:normal;"
COL_L75 = "flex:0 0 80%;max-width:80%;min-width:0;white-space:normal;"   # 이름은 그대로, 값은 80% (2026-10-11 사용자: 75 → 80)   # 값이 짧은 카드 (오른쪽 값 모두 5자 미만) — 2026-10-11 사용자   # 카드 왼쪽 65% (가이드라인 2-1, 2026-10-11 사용자: 꼭 지킨다)
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
QUESTION_ICON = ('<svg viewBox="0 0 16 16" width="15.4" height="15.4" aria-hidden="true" style="vertical-align:-2.5px;" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'   # 툴팁 아이콘 = ? (2026-10-11 사용자), 14 → 15.4px (2026-10-12 사용자: 10% 크게, 모든 페이지)
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


_DIR_WORD = re.compile(r"(상승|하락)\s?\d+(?:건|개|일)?$")   # "상승 9" · "하락 11" (끝에 올 때만 — "상승 52% (…)" 같은 확률은 아님)
CHUNK_TINT = 32   # 이보다 짧은 덩어리는 이름·구분명까지 통째로 칠한다
CHUNK_NOWRAP = 18   # 보조 줄에서 이보다 짧은 덩어리는 가운데서 줄을 바꾸지 않는다 (· 에서만 바뀜)


def _chunk_dir(plain):
    """덩어리 하나의 증감 방향: '+' · '-' · None(없음 또는 섞임·범위)."""
    if "~" in plain:
        return None
    dirs = {"+" if m.group(1) == "+" else "-" for m in _SIGNED.finditer(plain)}
    dirs |= {"+" if t == "▲" else "-" for t in re.findall("[▲▼]", plain)}
    m = _DIR_WORD.search(plain.strip())
    if m:
        dirs.add("+" if m.group(1) == "상승" else "-")
    return dirs.pop() if len(dirs) == 1 else None


def tint(html_text):
    """증감 색 (2026-10-12 사용자: "증감 정보는 모두 증감 컬러, 종목명·구분명도 같이"). " · " 로 나눈 덩어리마다:
    짧은 덩어리(CHUNK_TINT 자 미만)에 증감이 한 방향뿐이면 통째로 — `SPY 20일 +2.12%` 전체 빨강, `20일 고점 대비 -0.07%` 전체 파랑,
    `5일 순위 대비 ▲6` 빨강, `하락 11` 파랑. 긴 문장·섞인 덩어리는 아래 _tint_inline(숫자, 앞 종목 이름까지). 이미 태그가 든 덩어리는 그대로."""
    out = []
    for c in str(html_text).split(" · "):
        if "<" not in c:
            plain = html_mod.unescape(c).strip()
            d = _chunk_dir(plain)
            if d and len(plain) < CHUNK_TINT:
                out.append(f'<span style="color:{UP if d == "+" else DOWN};">{c}</span>')
                continue
            out.append(_tint_inline(c))
        else:
            out.append(c)
    return " · ".join(out)


def sub_line(sub_html, lead=""):
    """C 카드 보조 줄 내용 — 증감 색(tint) + 짧은 덩어리는 줄바꿈 없이 (· 에서만 줄이 바뀐다).
    lead(세로 구분선)는 첫 덩어리에 붙여 줄 끝에 홀로 남지 않게 한다."""
    chunks = tint(sub_html).split(" · ")
    chunks[0] = lead + chunks[0]
    parts = []
    for i, c in enumerate(chunks):
        sep = f'<span style="color:{SUB};">&nbsp;·</span>' if i < len(chunks) - 1 else ""   # 가운뎃점은 앞 덩어리에 붙여 줄 첫머리에 오지 않게
        plain = html_mod.unescape(re.sub(r"<[^>]+>", "", c))
        if i == 0 and lead:
            plain = plain.strip()
        parts.append(f'<span style="white-space:nowrap;">{c}{sep}</span>' if len(plain) < CHUNK_NOWRAP else c + sep)
    return paren(" ".join(parts))


def _tint_inline(html_text):
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


GRID_ATTR = ' data-guide-grid="1"'   # f-string 안에 \" 를 쓰면 파이썬 3.10(CI)에서 문법 오류
GUIDE_SHORT = 70   # 이보다 짧은 한 문장은 한 줄 "제목: 내용"


GUIDE_IND = "padding-left:12px;"   # 카드 밖 안내 줄은 왼쪽 12px 들여쓰기, 카드 안 안내는 제외 (2026-10-11 사용자: 일괄)


def guide(title, body, line=True, grid=False, in_card=False):
    """제목이 있는 안내 글 (가이드라인 3-3, 2026-10-11 사용자). 14px 안내 회색 + ⓘ.
    - 짧으면 한 줄: ⓘ **주의**: 내용
    - 길거나 항목이 여럿이면: ⓘ **읽는 법** 다음 줄부터 글머리표 "막대 = 내용", "회색 띠 = 내용"
    body: 문자열 또는 [(이름, 내용) | 문자열, ...]. line=True 면 위에 얇은 선(구획 안내 줄), 카드 안에서는 False."""
    if in_card:
        top = "margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;" if line else "margin:4px 0 0;"
    else:   # 카드 밖: 위아래 여백 40% 줄임 + 20px 들여쓰기 (2026-10-11 사용자)
        top = ("margin:2.76px 0 1.38px;padding-top:2.07px;border-top:1px solid #f3f3f3;" if line else "margin:1.38px 0 0;") + GUIDE_IND
    head = f'{INFO_ICON}<b style="color:#4B5563;">{esc(title)}</b>'
    if isinstance(body, str) and len(body) <= GUIDE_SHORT:
        return f'<div style="{top}font-size:{TINY};color:{NOTE};line-height:1.5;">{head} : {esc(body)}</div>'
    items = [body] if isinstance(body, str) else body
    lis = "".join(dot_li(tint(esc(it[0]) + ' = ' + esc(it[1])) if isinstance(it, tuple) else tint(esc(it)), size=2, color=NOTE, top=9, margin="2px 0") for it in items)   # 14px 안내 → 2px 점
    return (f'<div style="{top}font-size:{TINY};color:{NOTE};line-height:1.5;">{head}'
            f"<ul{GRID_ATTR if grid else ''} style='margin:2px 0 0 2px;padding:0;list-style:none;'>{lis}</ul></div>")   # grid: 데스크톱 2열 (테마 CSS)



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
    return f'<div style="position:relative;font-size:{TINY};color:{NOTE};line-height:1.6;margin:2.07px 0 0.69px;{GUIDE_IND}">{inner}</div>'



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



_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def write_mock(body, path, title):
    """목업 화면 — 저장소의 index.html(블로그 테마) CSS·JS로 본문을 감싸 글 보기 화면처럼 보이게 한다 (2026-10-11 사용자: 목업으로 확인).
    탭·툴팁·2열·읽는 법 2열이 블로그와 같게 그려진다. 그림은 gh-pages 주소 대신 로컬 output/images 를 쓴다.
    index.html 이 없으면 만들지 않는다 (CI 등)."""
    theme = os.path.join(_ROOT, "index.html")
    if not os.path.exists(theme):
        return None
    idx = open(theme, encoding="utf-8").read()
    css = re.search(r"<b:skin version='1.0'><!\[CDATA\[(.*?)\]\]></b:skin>", idx, re.S)
    js = re.search(r"//<!\[CDATA\[(.*?)//\]\]>", idx, re.S)
    if not (css and js):
        return None
    body = re.sub(r"https://cdn\.jsdelivr\.net/gh/[^\"]+?@gh-pages/(images/[^\"]+)", r"\1", body)
    page = ('<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)} — 목업</title><style>{css.group(1)}</style></head>'
            '<body class="item-view no-dashboard"><main class="main-content"><div class="post-shell"><article class="post-outer-container"><div class="post">'
            f'<h3 class="post-title">{esc(title)}</h3><div class="post-body entry-content">{body}</div></div></article></div></main>'
            f'<script>{js.group(1)}</script></body></html>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def muted(t):
    """짧은 안내 글 (빈 구획 안내 등) — ⓘ 필수."""
    return f'<div style="color:{NOTE};font-size:{TINY};margin:2.07px 0;{GUIDE_IND}">{INFO_ICON}{esc(t)}</div>'   # 여백 40% 줄임 (2026-10-11 사용자)


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


SHORT_VALUE = 5   # 오른쪽 값이 모두 이 글자 수 미만인 카드는 왼쪽 80% (2026-10-11 사용자: 30일 흐름 "1건" 같은 짧은 값)


def value_len(value_html):
    """값의 보이는 글자 수 (태그·공백 빼고)."""
    t = html_mod.unescape(re.sub(r"<[^>]+>", "", value_html or ""))
    return len(re.sub(r"\s+", "", t))


def short_values(rows):
    """카드의 오른쪽 값이 모두 SHORT_VALUE 자 미만인가 — 카드 단위로 정해 줄마다 칸이 같게."""
    return bool(rows) and all(value_len(r[1]) < SHORT_VALUE for r in rows)


def _px(html_text, size):
    """글자 폭 어림(px) — 한글 0.95em · 영문 대문자 0.68 · 소문자 0.52 · 숫자 0.58 · 공백 0.28 · 문장부호 0.32 (320px 화면에서 잰 값에 맞춤).
    한 줄에 들어가는지 고르는 데만 쓴다."""
    t = html_mod.unescape(re.sub(r"<[^>]+>", "", html_text or ""))

    def w(ch):
        if "\uac00" <= ch <= "\ud7a3":
            return 0.95
        if ch.isdigit():
            return 0.58
        if ch.isupper():
            return 0.68
        if ch.isalpha():
            return 0.52
        return 0.28 if ch == " " else 0.32
    return sum(w(ch) for ch in t) * size


INLINE_ROOM = 294   # 폰(본문 320px)에서 C 카드 줄 안쪽 폭 — 왼쪽 칸 = 이 폭 × 65%(짧은 값 카드 80%)


def fits_inline(name_html, sub, left_pct=65):
    """구분명 │ 보조 줄 첫 덩어리(뒤 가운뎃점 포함)가 폰 한 줄에 들어가는가. 안 들어가면 보조 줄은 이름 아래(구분선 없이) —
    구분선이 둘째 줄 첫머리로 밀리지 않게 (2026-10-12, 트럼프 급상승 주제에서 발견)."""
    chunks = str(sub).split(" · ")
    pill = 18 if ">N</span>" in name_html else 0
    need = _px(name_html.replace(">N</span>", "></span>"), 16) * 1.04 + pill + 17 + _px(chunks[0], 14) + (10 if len(chunks) > 1 else 0)
    return need <= INLINE_ROOM * left_pct / 100 - 4


def crow_left(name_html, sub="", left_pct=65):
    """C 카드 왼쪽 칸 안: 구분명(굵게) │ 보조 줄(14px #7A7A7A) 한 줄로 (2026-10-12 사용자: "구분선 넣고 한 줄로 표기 가능한 것은 모두").
    넘치면 · 에서 다음 줄로 이어진다. 엔비디아 렌더러도 이것을 쓴다."""
    if not sub:
        return f'<span style="font-weight:700;color:#111;">{paren(name_html)}</span>'
    if not fits_inline(name_html, sub, left_pct):   # 한 줄에 못 들어가면 예전처럼 이름 아래 블록
        return (f'<span style="font-weight:700;color:#111;">{paren(name_html)}</span>'
                f'<span style="display:block;color:{SUB};font-weight:400;font-size:{TINY};">{sub_line(sub)}</span>')
    return (f'<span style="font-weight:700;color:#111;">{paren(name_html)}</span>'
            f'<span style="color:{SUB};font-weight:400;font-size:{TINY};">{sub_line(sub, lead=VSEP)}</span>')


VSEP = '<span style="display:inline-block;width:1px;height:14px;background:#E2E8F0;margin:0 8px;vertical-align:-1px;"></span>'


def crow(name_html, value_html, sub="", first=False, left=None, short=False, nowrap=False, sub_below=False):
    """C 카드 한 줄: 왼쪽 구분명 │ 보조 줄, 오른쪽 값. name_html 은 이스케이프된 HTML.
    left = 왼쪽 칸 % (카드별 예외, 가이드라인 2-1 — 2026-10-12 사용자). nowrap = 값을 한 줄로.
    sub_below = 보조 줄을 구분명 옆이 아니라 줄 아래 카드 폭 전체 한 줄로 (옆에 들어가지 않을 때, 2026-10-12 사용자)."""
    col_l = f"flex:0 0 {left}%;max-width:{left}%;min-width:0;white-space:normal;" if left else COL_L75 if short else COL_L
    col_r = COL_R.replace("white-space:normal;", "white-space:nowrap;") if nowrap else COL_R
    below = (f'<span style="flex:0 0 100%;color:{SUB};font-weight:400;font-size:{TINY};white-space:nowrap;">{sub_line(sub)}</span>'
             if sub and sub_below else "")
    row_st = MULTI_ROW + ("flex-wrap:wrap;row-gap:0;" if below else "")
    return (f'<span style="{row_st}{"" if first else MULTI_SEP}">'
            f'<span style="display:block;line-height:1.5;{col_l}">{crow_left(name_html, "" if below else sub, left or (80 if short else 65))}</span> '
            f'<span style="{col_r}font-weight:700;">{value_html}</span>{below}</span> ')   # 왼쪽 65% · 오른쪽 35%, 값이 모두 짧으면 80 · 20, left 가 있으면 그 값


EMPH_BG, EMPH_BD = "#FFF7ED", "#FED7AA"   # 강조 카드 배경·테두리 (오렌지)


def ccard(rows, left=None, attrs="", emph=False):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html[, left_pct[, nowrap[, sub_below]]])]. left = 카드 전체 왼쪽 %. emph=True 면 강조 카드 배경(오렌지, 줄 구분선도 오렌지) — 2026-10-11 사용자: 급상승 주제."""
    short = short_values(rows)   # 값이 모두 5자 미만 → 왼쪽 80% (2026-10-11 사용자)
    # 줄 튜플 4번째 값 = 그 줄의 왼쪽 % (예: 시장 상태 막대 줄 30), 없으면 카드의 left (2026-10-12 사용자)
    inner = "".join(crow(r[0], r[1], r[2], first=(i == 0), short=short, left=(r[3] if len(r) > 3 else left), nowrap=bool(len(r) > 4 and r[4]),
                         sub_below=bool(len(r) > 5 and r[5]))
                    for i, r in enumerate(rows))
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


STATE_CARD = {"good": ("#F0FDF4", "#BBF7D0"), "uncertain": ("#FFFBEB", "#FDE68A"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#CBD5E1")}   # 신호 라벨 색의 카드판


def state_card(head_html, kind="neutral", right_html="", sub_html="", items=()):
    """상태 카드 (2026-10-12 사용자: 종합·점수 카드 분리, 배경은 신호 라벨 색). 첫 줄 왼쪽 결론(굵게 검정 16px) · 오른쪽 값,
    둘째 줄 sub_html(14px 한 줄 설명), items = [(라벨, 내용)] 은 얇은 선 아래 3px 점 글머리표 14px."""
    bg, bd = STATE_CARD.get(kind, STATE_CARD["neutral"])
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
            f'<span style="font-weight:700;color:#111;font-size:{SMALL};">{head_html}</span>'
            + (f'<span style="font-weight:700;white-space:nowrap;font-size:{SMALL};">{right_html}</span>' if right_html else "") + "</span>")
    sub = f'<div style="font-size:{TINY};color:#374151;line-height:1.5;margin-top:2px;">{sub_html}</div>' if sub_html else ""
    lis = "".join(dot_li((f"<b>{esc(k)}</b> : " if k else "") + esc(v), size=3, color="#374151", top=9, margin="2px 0") for k, v in items)
    body = (f'<div style="margin-top:6px;padding-top:4px;border-top:1px solid {bd};font-size:{TINY};line-height:1.5;">'
            f"<ul style='margin:0;padding:0;list-style:none;'>{lis}</ul></div>") if lis else ""
    return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:10px 14px;margin:0 0 8px;">{head}{sub}{body}</div>'


def emph_list(lines):
    """강조 카드 + 3px 점 글머리표 16px (2026-10-12 사용자: 주의할 위험요인 글을 강조 카드로). lines = 이스케이프 전 문장들. 증감은 색."""
    lis = "".join(dot_li(tint(esc(t)), size=3) for t in lines if str(t).strip())
    if not lis:
        return ""
    return (f'<div style="background:{EMPH_BG};border:1px solid {EMPH_BD};border-radius:10px;padding:10px 14px;margin:0 0 8px;">'
            f"<ul style='margin:0;padding:0;list-style:none;font-size:{SMALL};line-height:1.5;color:#111;'>{lis}</ul></div>")


ACC_CHEV = ('<svg class="acc-chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>')


def fold(label, inner_html):
    """펼침 버튼 (가이드라인 2-1 H 카드 버튼) — 눌러야 inner_html 이 보인다. details data-acc: 테마 CSS가 화살표를 돌리고 홈 카드는 건너뛴다."""
    return (f'<details data-acc="1" style="margin:0 0 8px;"><summary style="cursor:pointer;list-style:none;display:flex;justify-content:center;align-items:center;gap:6px;'
            f'padding:8px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;color:#111;font-size:{SMALL};font-weight:700;">{esc(label)} {ACC_CHEV}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


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


def hbar(value, max_value, color, width="80px"):
    """가로 막대 하나 (섹터 등락 등) — 카드 값 칸 안에 작게. width 는 CSS 폭 (값 칸을 채우려면 calc(100% - n px))."""
    pct = 0 if not max_value else min(100, abs(value) / max_value * 100)
    return (f'<span style="display:inline-block;vertical-align:middle;width:{width};height:10px;background:#F1F5F9;border-radius:3px;overflow:hidden;margin-right:8px;">'
            f'<span style="display:block;height:100%;width:{pct:.0f}%;background:{color};"></span></span>')


BAR_GAP = "14px"   # 가장 긴 이름과 막대 사이 (2026-10-12 사용자: "금리 환경 기준 14픽셀 여백")


def bar_widths(names, values):
    """막대 카드 한 묶음의 이름·값 목록 (HTML, 중복 제거). 칸마다 모두를 보이지 않게 겹쳐 두어 칸 폭 = 가장 넓은 글자 폭 (글꼴과 상관없이 정확).
    접힌 부분까지 같은 목록을 써서 막대 길이가 모두 같다."""
    return list(dict.fromkeys(names)), list(dict.fromkeys(values))


def _sized(html, others, align="left"):
    """html 을 칸에 두되, 칸 폭은 others 가운데 가장 넓은 것 — 같은 칸에 보이지 않게 겹침 (CSS grid 한 칸)."""
    ghost = "".join(f'<span aria-hidden="true" style="grid-area:1/1;visibility:hidden;">{o}</span>' for o in others if o != html)
    return f'<span style="display:grid;flex:none;text-align:{align};"><span style="grid-area:1/1;">{html}</span>{ghost}</span>'


def bar_row(name_html, frac, color, value_html, widths, sub="", first=False):
    """막대 줄 (2026-10-12 사용자: 막대는 가장 긴 이름 + 14px 뒤에서 왼쪽 정렬, 모든 막대 같은 길이).
    이름 칸(고정 폭) · 14px · 막대(남은 폭) · 값 칸(고정 폭, 오른쪽 정렬). sub 는 줄 아래 전체 폭 14px 보조 줄."""
    ln, lv = widths
    pct = max(0.0, min(1.0, frac)) * 100
    sub_html = f'<span style="display:block;color:{SUB};font-weight:400;font-size:{TINY};white-space:normal;">{sub_line(sub)}</span>' if sub else ""
    return (f'<span style="display:block;padding:8px 12px;line-height:1.5;{"" if first else MULTI_SEP}">'
            f'<span style="display:flex;align-items:center;white-space:nowrap;">'
            f'<span style="font-weight:700;color:#111;display:flex;">{_sized(paren(name_html), [paren(x) for x in ln])}</span>'
            f'<span style="flex:1 1 0;min-width:24px;margin-left:{BAR_GAP};height:10px;background:#F1F5F9;border-radius:3px;overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{pct:.0f}%;background:{color};"></span></span>'
            f'<span style="margin-left:10px;font-weight:700;display:flex;">{_sized(value_html, lv, "right")}</span></span>{sub_html}</span> ')


def card_of(rows_html, attrs=""):
    """미리 만든 줄(crow·bar_row)을 C 카드 하나로."""
    return f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span data-grid="2" style="{MULTI}">{"".join(rows_html)}</span></div>'


def table(headers, rows, note_text=""):
    """표 — 카드로 못 푸는 통계 행렬에만. 16px, 칸은 어절 단위로만 줄바꿈, 좁은 화면은 표만 가로 스크롤."""
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;font-size:{TINY};color:{NOTE};font-weight:400;">{esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:0 0 8px;font-size:{SMALL};">'
            f"<tr>{th}</tr>{body}</table></div>") + (note(note_text) if note_text else "")


def footer(data_line, disclaimer_line):
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:{TINY};color:{NOTE};line-height:1.6;{GUIDE_IND}">'
            f"{INFO_ICON}{data_line}<br>{INFO_ICON}{disclaimer_line}</div>")
