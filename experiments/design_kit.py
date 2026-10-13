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
BODY, SMALL, TINY, MICRO = "19px", "19px", "14px", "14px"   # 본문 18 → 19 (2026-10-13 사용자: "모든 리포트의 블로그 전체의 본문 폰트는 19포인트")   # 안내 글(14px)을 빼고 모두 18px (2026-10-12 사용자: "안내 14포인트를 제외하고 본문 폰트는 모두 18")
NAME = "16px"   # 가로 구분선이 있는 카드의 왼쪽 정보(구분명) — 2026-10-12 사용자: "가로 구분선이 있는 카드의 좌측 정보는 16포인트"
EMPH_NAME = "19px"   # 본문과 같이 19 (2026-10-13)   # 강조 카드(색 배경: 상태·결론·흐름·강조 C 카드)의 왼쪽 정보는 18px (2026-10-12 사용자)
PILL_SIZE = "14px"   # 라벨(알약)은 어디서나 14px (2026-10-12 사용자: "라벨 폰트는 14 적용")
# 카드 위아래 여백은 "보이는 여백"으로 정한다 (2026-10-12 사용자: "카드의 패딩은 상하 여백만 수정, 좌우는 유지").
# 보이는 여백 = padding + 행간 반쪽(18px 글자 · 행간 24 → 약 2px). 그래서 위아래 padding = 목표 − VP. 카드 안 첫·끝 목록의 margin 은 ul 의 음수 margin 으로 지운다.
VP = 2
SEP_GAP = 22   # 줄 padding = 22 − VP − 1(보조 줄 · 괄호 글자 상자, 잰 값에 맞춤). 가로 구분선이 있는 콘텐츠 카드(C · E · G · 막대 줄 · H · 글 항목 카드)의 구분선 위아래 · 카드 가장자리 보이는 22px — 강조 카드 · 버튼 제외 (2026-10-12 사용자: "주요 지수 카드의 구분선 상하 여백을 일괄 적용")
# 강조 카드(색 배경: 상태 · 결론 · 흐름 · 데일리 머리 · 강조 글머리표): 18px 글 행간 32, 카드 위 · 아래 보이는 여백 24 (2026-10-12 사용자: "강조 카드는 위 24 아래 24로 일괄").
# 행간 32 · 18px 글자의 반쪽 ≈ 6px = VP_EMPH → padding = 24 − 6 (끝 줄이 14px 글이면 − 2). 가로 구분선이 여러 개인 강조 C 카드만 위아래 14 그대로("구분선이 여러 개 있는 건 기존 유지")
LH_EMPH, VP_EMPH, EMPH_PAD = "32px", 6, 24
H2_SIZE = "22px"   # 구획 제목 21 → 22 (2026-10-13 사용자: "타이틀 사이즈도 1포인트 크게")
LH_BODY, LH_CARD, LH_TINY, LH_H2 = "34px", "24px", "20px", "28px"   # 구획 제목 22px → 행간 28 (2026-10-13)   # 행간은 px 정수만. 본문(카드 밖 문단·글머리표)·툴팁 34 (2026-10-12 사용자: "툴팁도 본문 행간으로 동일하게, 34픽셀") · 카드 안 18·16px 24 (2026-10-12 사용자: "24픽셀만") · 16px 카드 이름도 24 · 14px 안내 20 · 21px 구획 제목 27. 행간 숫자를 직접 적지 말고 이 상수만
H2 = f"position:relative;color:#111;font-size:{H2_SIZE};font-weight:700;line-height:{LH_H2};margin:28px 0 11px;padding:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;"
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:6px;"
_NO_LINE_START = re.compile(r'^\s*(<(?:div|ul) style="(?:overflow-x:auto;|background:)|<div data-cards|<div data-lead|<img\b|<details\b)')
CARD = f"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:{14 - VP}px 14px;line-height:{LH_CARD};"   # 보이는 위아래 14px (2026-10-12 사용자)
CARD_DIR = {"positive": ("#FFF7ED", "#FED7AA"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#E2E8F0"), "uncertain": ("#FFFBEB", "#FDE68A")}
PILL = {"area": ("#CBD5E1", "#334155"), "positive": ("#FCA5A5", "#B91C1C"), "negative": ("#93C5FD", "#1D4ED8"),
        "uncertain": ("#FDBA74", "#C2410C"), "neutral": ("#CBD5E1", "#64748B"),
        "good": ("#86EFAC", "#15803D")}   # 신호등 🟢 정상·양호 (2026-10-12 사용자: 정상 라벨은 녹색)
PILL_BG = {"positive": "#FEF2F2", "negative": "#EFF6FF", "good": "#F0FDF4"}
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"), "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
COL_L = "flex:0 0 65%;max-width:65%;min-width:0;white-space:normal;"
COL_L75 = "flex:0 0 80%;max-width:80%;min-width:0;white-space:normal;"   # 이름은 그대로, 값은 80% (2026-10-11 사용자: 75 → 80)   # 값이 짧은 카드 (오른쪽 값 모두 5자 미만) — 2026-10-11 사용자   # 카드 왼쪽 65% (가이드라인 2-1, 2026-10-11 사용자: 꼭 지킨다)
COL_R = "flex:1 1 0;min-width:0;text-align:right;white-space:normal;word-break:keep-all;"   # 카드 오른쪽 35%
ROW = (f"display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 6px;padding:{10 - VP}px 12px;"   # A 기준 카드 보이는 10px
       f"background:#fff;border:1px solid #E2E8F0;border-radius:8px;white-space:nowrap;line-height:{LH_CARD};")
ROW_UP, ROW_DOWN = "background:#FFF7ED;border-color:#FED7AA;", "background:#EFF6FF;border-color:#BFDBFE;"
MULTI = f"display:block;margin:0 0 6px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};line-height:{LH_CARD};"
MULTI_ROW = f"display:flex;justify-content:space-between;align-items:center;gap:12px;padding:{SEP_GAP - VP - 1}px 12px;white-space:nowrap;line-height:{LH_CARD};"   # 가로 구분선 기준 위아래 14px, 카드 가장자리도 같게 (2026-10-12 사용자)
MULTI_SEP = "border-top:1px solid #E2E8F0;"
INFO_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;margin-right:4px;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>')
QUESTION_ICON = ('<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" style="display:block;" fill="none">'   # 원 선 1.2 × 20/16 = 보이는 1.5px (2026-10-13)
                 '<circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>'
                 '<text x="8" y="11.6" text-anchor="middle" fill="currentColor" stroke="none" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="700">?</text></svg>')   # ? 는 또렷한 글꼴의 글자 (2026-10-13 사용자: "다른 폰트로 명확하게")
LINK_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M9 3h4v4"/><path d="M13 3 7 9"/><path d="M11 9v4H3V5h4"/></svg>')
NEW_PILL = ('<span style="display:inline-block;background:#B91C1C;color:#fff;border-radius:3px;padding:1px 4px 0;font-size:10px;font-weight:700;'
            'line-height:13px;vertical-align:middle;margin-left:4px;">N</span>')
WRAP_OPEN = ('<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
             f'font-size:{BODY};line-height:{LH_BODY};color:#333;">')   # 본문 행간 34px — 카드는 각자 LH_CARD 24px 를 단다 (2026-10-12 사용자)
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
    return _PAREN.sub(lambda m: f' <span style="display:inline-block;font-size:{MICRO};font-weight:400;">{m.group(1)}</span>', name_html)   # inline-block: 한 줄에 못 들면 괄호째 다음 줄로 (2026-10-13 사용자)


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
    sm = (f' <span data-summary="1" style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};white-space:normal;flex:1 1 220px;">{INFO_ICON}{summary}</span>'
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
    return f'<div style="margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};">{INFO_ICON}{esc(t)}</div>'


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


def dot_li(inner_html, size=3, color="#111", lh=None, margin="9px 0"):   # 사이 3 → 9 (글머리표 사이 +6px, 2026-10-12 사용자)
    """점 글머리표 한 줄 — 점은 두 가지뿐: 18px 글 3px · 14px 안내 글 2px (2026-10-12 사용자). 점은 첫 줄 가운데 (행간 lh 에서 계산)."""
    lh = int(str(lh or (LH_TINY if size == 2 else LH_CARD)).replace("px", ""))
    return (f'<li style="display:flex;align-items:flex-start;gap:7px;margin:{margin};color:{color};line-height:{lh}px;">'
            f'<span style="flex:none;width:{size}px;height:{size}px;border-radius:50%;background:{color};margin-top:{(lh - size) // 2}px;"></span><span>{inner_html}</span></li>')


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
        top = ("margin:3px 0 1px;padding-top:2px;border-top:1px solid #f3f3f3;" if line else "margin:1px 0 0;") + GUIDE_IND   # 여백은 정수 px만 (2026-10-12 사용자: 2.76 · 1.38 · 2.07 반올림)
    head = f'{INFO_ICON}<b style="color:#4B5563;">{esc(title)}</b>'
    if isinstance(body, str) and len(body) <= GUIDE_SHORT:
        return f'<div data-guide="1" style="{top}font-size:{TINY};line-height:{LH_TINY};color:{NOTE};">{head} : {esc(body)}</div>'   # data-guide: 홈 카드가 건너뛴다
    items = [body] if isinstance(body, str) else body
    lis = "".join(dot_li(tint(esc(it[0]) + ' = ' + esc(it[1])) if isinstance(it, tuple) else tint(esc(it)), size=2, color=NOTE, margin="8px 0") for it in items)   # 14px 안내 → 2px 점
    return (f'<div data-guide="1" style="{top}font-size:{TINY};line-height:{LH_TINY};color:{NOTE};">{head}'
            f"<ul{GRID_ATTR if grid else ''} style='margin:-4px 0 -6px 2px;padding:0;list-style:none;'>{lis}</ul></div>")   # grid: 데스크톱 2열 (테마 CSS)



def guide_card(title, body, notes=()):
    """읽는 법 카드 (2026-10-11 사용자: "읽는 법만 카드를 분리하여 그래프 아래에, 일괄") — 그래프·표 바로 아래 옅은 회색 카드 안에 guide().
    notes = [(제목, 내용), …] — 주의처럼 짧은 안내도 같은 카드 안 아래쪽에 한 줄씩 (2026-10-11 사용자: "주의도 읽는 법 카드에 포함")."""
    extra = "".join(guide(t, x, line=False, in_card=True) for t, x in notes)
    return (f'<div data-guide="1" style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:{12 - VP - 3}px 14px {12 - VP - 2}px;margin:8px 0;line-height:{LH_CARD};">'   # data-guide: 홈 카드가 건너뛴다 (2026-10-12) · 보이는 위아래 12 (안쪽 안내의 margin 3 · 2 를 뺌)
            + guide(title, body, line=False, grid=True, in_card=True) + (f'<div style="margin-top:{14 - VP - 2}px;padding-top:{14 - VP - 4}px;border-top:1px solid #E2E8F0;">{extra}</div>' if extra else "") + "</div>")   # 글머리표는 데스크톱에서 2열 (2026-10-11 사용자)




TIP_GAP = 3   # 툴팁 아이콘 좌우 바깥 여백 — 항상 (2026-10-13 사용자: "툴팁도 좌우 여백 3픽셀 여유는 항상")


def tip(text):
    """ⓘ 툴팁 아이콘 — 글은 data-tip 속성, 모양은 테마 CSS(build_theme.py `[data-tip]::after`). 줄바꿈(\n)은 툴팁 안에서 줄을 바꾼다.
    상자는 position:relative 인 가장 가까운 줄 기준으로 놓인다 — 아이콘은 그런 줄 안에 둔다."""
    t = esc(text).replace(chr(34), "&quot;").replace("\n", "&#10;")
    return (f'<span data-tip="{t}" tabindex="0" role="button" aria-label="{t}" '
            f'style="display:inline-flex;align-items:center;color:{NOTE};cursor:help;vertical-align:middle;position:relative;top:-1px;margin:0 {TIP_GAP}px;">{QUESTION_ICON}</span>')   # 좌우 3px 항상 (2026-10-13 사용자)   # 글자와 세로 가운데 (2026-10-13 사용자)


def read_text(items, notes=()):
    """읽는 법 툴팁 글 — 항목은 `· 이름 = 내용` 줄(팝업이 글머리표로 그린다), notes 는 `제목 : 내용` 줄. 읽는 법 카드를 대신한다 (2026-10-12 사용자)."""
    lines = [f"· {k} = {v}" if isinstance(k, str) and v is not None else f"· {k}" for k, v in ((it if isinstance(it, tuple) else (it, None)) for it in items)]
    return "\n".join(lines + [f"{t} : {x}" for t, x in notes])


def tip_label(label, text):
    """`읽는 법 ?` 같은 라벨 + ? 툴팁 — 14px 안내 회색, 팝업 제목은 이 라벨. 툴팁 아이콘은 늘 라벨과 짝 — 읽는 법 · 용어 · 주의 · 처음 등장, 그 밖은 `안내` (2026-10-13 사용자: "아이콘만 있는 경우는 안내 + 아이콘")."""
    return f'<span style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};white-space:nowrap;margin-left:6px;">{esc(label)}{tip(text)}</span>'


def tip_icon(text):
    """상태 카드 제목 옆 툴팁 — `안내` 글자 없이 아이콘만 (2026-10-13 사용자: "점수 옆의 툴팁의 안내 글자는 삭제")."""
    return tip(text)   # 감싸지 않는다 — inline-flex 로 감싸면 아이콘이 글자 위로 뜬다. 좌우 3px 는 tip 이 갖는다


def tip_anno(text):
    """이름 옆 `안내 ?` — 라벨이 따로 없는 툴팁 (카드 구분명 · 상태 카드 제목 옆)."""
    return tip_icon(text)   # `안내` 글자는 모두 삭제 — 아이콘만 (2026-10-13 사용자: "안내 + 툴팁은 전부 안내라는 글자 삭제")


TIP_RIGHT = 10   # 줄 오른쪽 끝 툴팁 묶음의 오른쪽 여백 (2026-10-13 사용자: "우측 여백 들여쓰기 10픽셀")


def tips_right(pairs):
    """제목 줄 오른쪽 끝에 툴팁 묶음 `읽는 법 ? · 주의 ?` — 모든 리포트의 툴팁 배치 (2026-10-13 사용자: "타이틀 줄에 우측 정렬로 툴팁 배치"). pairs = [(라벨, 글)]."""
    inner = ' <span style="color:#CBD5E1;">·</span> '.join(f'<span style="white-space:nowrap;">{esc(k)}{tip(v)}</span>' for k, v in pairs if v)
    return f'<span style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};margin-left:auto;margin-right:{TIP_RIGHT}px;align-self:center;white-space:nowrap;flex:none;">{inner}</span>' if inner else ""   # 오른쪽 10px 안쪽 (2026-10-13 사용자)


def tip_line(items, in_title=False):
    """용어 툴팁 줄 — "용어ⓘ · 용어ⓘ". 14px 안내 회색. items = [(용어, 설명)]. 줄이 position:relative 라 상자가 줄 폭 안에 뜬다."""
    inner = ' <span style="color:#CBD5E1;">·</span> '.join(f'<span style="white-space:nowrap;">{esc(k)}{tip(v)}</span>' for k, v in items)
    if in_title:   # 구획 제목 줄 오른쪽 (2026-10-11 사용자: "급상승 주제 타이틀 우측에") — 툴팁 상자는 position:relative 인 h2 기준
        return f'<span style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};margin-left:auto;margin-right:{TIP_RIGHT}px;align-self:center;white-space:nowrap;flex:none;">{inner}</span>'
    return f'<div style="position:relative;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};margin:2px 0 1px;{GUIDE_IND}">{inner}</div>'



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


_DOT = re.compile(r"[ \t]*·[ \t]*")


def _space_dots(t):
    """글자 "·" 앞뒤 한 칸 (2026-10-13 사용자: 앞뒤 모두 띄워쓰기). 글자 노드 맨 앞 · 맨 끝, 줄 첫머리 글머리표(`· `), &nbsp; 옆은 그대로 둔다."""
    def fix(m):
        s, e = m.start(), m.end()
        before, after = t[s - 1:s], t[e:e + 1]
        m0 = m.group(0)
        lead = (" " if m0[:1] in " \t" else "") if s == 0 else ("" if before in "\n;" else " ")   # ; = &nbsp; · &#10; 같은 문자 참조 끝. 글자 노드 맨 앞은 원래 공백만
        tail = (" " if m0[-1:] in " \t" else "") if e == len(t) else ("" if after in "\n&" else " ")
        return f"{lead}·{tail}"
    return _DOT.sub(fix, t)


def fix_colons(html):
    """보이는 글의 ":" · "·" 는 앞뒤를 한 칸씩 띄운다 ("·" 는 2026-10-13 사용자) — "라벨 : 값" (2026-10-11 사용자: 꼭 반드시, 모든 페이지 일괄).
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
            out.append(_TIP_ATTR.sub(lambda m: m.group(1) + _space_dots(_space_colons(m.group(2))) + m.group(3), part))
        else:
            out.append(part if skip else _space_dots(_space_colons(part)))
    return "".join(out)


def capsules(items, size=None, in_title=False):
    """캡슐 줄 (2026-10-11 사용자: "게시물 : 9건 캡슐 라인 디자인으로 연속해서") — 알약 모양 칸을 한 줄에 이어 놓고, 넘치면 다음 줄로.
    items = [(라벨, 값HTML)]. 라벨 16px 안내 회색 · 값 16px 검정 굵게, "라벨 : 값". 흰 바탕, 테두리 #E2E8F0, 모서리 끝까지 둥글게."""
    pill = (f"display:inline-flex;align-items:center;gap:4px;padding:{6 - VP}px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:999px;"
            f"font-size:{size or SMALL};font-weight:400;line-height:{LH_TINY if (size or SMALL) == TINY else LH_CARD};white-space:nowrap;")
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
    return f'<div style="color:{NOTE};font-size:{TINY};line-height:{LH_TINY};margin:2px 0;{GUIDE_IND}">{INFO_ICON}{esc(t)}</div>'   # 여백 40% 줄임 (2026-10-11 사용자), 정수 px (2026-10-12)


def notice(parts):
    """안내 상자 (노랑) — 14px."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return (f'<div style="background:#fff8e1;border:1px solid #f4d37a;border-radius:6px;padding:{12 - VP}px 14px;font-size:{TINY};line-height:{LH_TINY};margin:0 0 12px;">'
            + "<br>".join(INFO_ICON + p for p in parts) + "</div>")


PILL_GAP = 5   # 라벨 좌우 바깥 여백 — 모든 라벨 (2026-10-13 사용자: 4 → "5픽셀, 반드시 모든 라벨에 공통")
PILL_MID = "position:relative;top:-1px;"   # vertical-align:middle 은 한글 가운데보다 약 1px 낮다 (잰 값) — 이어지는 글자와 가운데 (2026-10-13 사용자)


def pill(text, kind="area", lead=False, bare=False):
    """라벨(알약). 이어지는 글자와 세로 가운데, 좌우 5px. bare=True: 바깥 여백 없음 — 줄에 홀로 놓인 라벨(급등주 섹터 · 뉴스 라벨 줄, 2026-10-13 사용자) (lead 는 옛 인자, 무시)."""
    bd, fg = PILL.get(kind, PILL["neutral"])
    bg = PILL_BG.get(kind, "#fff")
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {bd};border-radius:4px;padding:3px 5px 2px;margin:0 {0 if bare else PILL_GAP}px;{PILL_MID}'
            f'font-size:{PILL_SIZE};font-weight:400;line-height:1;white-space:nowrap;vertical-align:middle;">{esc(text)}</span>')   # 라벨 14px, 어디서나 (2026-10-12 사용자)


LOGO_URL = "https://financialmodelingprep.com/image-stock/{sym}.png"   # 티커 로고 (키 없이 받아진다, 2026-10-13 확인). 없으면 img 가 스스로 숨는다


def ticker_logo(sym, size=20):
    """종목 이름 앞 티커 로고 (2026-10-13 사용자: "엔비디아는 티커 로고, 각각의 종목명에도 티커 아이콘"). 둥근 20px, 못 받으면 숨김(onerror)."""
    sym = str(sym or "").strip().upper()
    if not sym or not sym.replace("-", "").replace(".", "").isalnum():
        return ""
    return (f'<img src="{LOGO_URL.format(sym=sym)}" alt="" width="{size}" height="{size}" loading="lazy" onerror="this.style.display=\'none\'" '
            f'style="width:{size}px;height:{size}px;border-radius:50%;vertical-align:-4px;margin-right:6px;background:#F1F5F9;">')


def link_icon(url, label):
    if not url:
        return ""
    return (f' <a href="{esc(url)}" title="{esc(label)}" aria-label="{esc(label)}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;text-decoration:none;white-space:nowrap;">{LINK_ICON}</a>')


NEWS_VP = 7   # 18px 글 · 행간 34 의 반쪽


def item_cards(items_html, sub=False):   # sub=True: 카드 끝 줄이 14px 보조 줄
    """기사 카드 — 뉴스 기사 하나가 카드 하나 (2026-10-12 사용자: "뉴스 기사는 카드 타입으로 각각"). 흰 바탕, 테두리, 모서리 8px,
    위아래 14px · 좌우 12px, 카드 사이 8px. 18px · 행간 27. 항목은 li — 홈 카드가 글머리표로 읽는다."""
    # 뉴스 제목은 본문 행간 34 (2026-10-12 사용자: "뉴스의 제목도 본문 행간 여백을 적용") — 행간 반쪽 7 만큼 padding 을 덜어 보이는 위아래 22 (콘텐츠 카드 여백, 2026-10-13 사용자)
    lis = "".join(f'<li style="margin:0 0 8px;padding:{SEP_GAP - NEWS_VP}px 12px {SEP_GAP - (VP if sub else NEWS_VP)}px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;line-height:{LH_BODY};">{h}</li>'
                  for h in items_html)
    return f'<ul style="margin:0 0 8px;padding:0;list-style:none;font-size:{SMALL};">{lis}</ul>' if lis else ""


def list_card(items_html):
    """글 항목 카드 — 뉴스처럼 문장 항목을 한 카드 안에 가로 구분선으로 (2026-10-12 사용자: "뉴스는 카드 형식으로"). 18px, 행간 27.
    항목은 li 로 둔다 — 홈 카드가 글머리표로 읽는다. 구분선은 border-top 대신 box-shadow (홈 카드는 border-top 요소를 건너뛴다)."""
    lis = "".join(f'<li style="margin:0;padding:{SEP_GAP - VP - 1}px 12px;line-height:{LH_CARD};{"" if i == 0 else "box-shadow:inset 0 1px 0 #E2E8F0;"}">{h}</li>'
                  for i, h in enumerate(items_html))
    return (f'<ul style="background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:0;margin:0 0 8px;list-style:none;'
            f'font-size:{SMALL};">{lis}</ul>') if lis else ""


def stat_line(items):
    """한 줄 수치 카드 (2026-10-12 사용자: "기사 · 7일 평균 · 대기 문서, 구분선을 추가하여 한 줄에") — 카드 하나에 `이름 값`을 세로 구분선으로 나란히.
    이름 16px(왼쪽 정보) · 값 18px 굵게. items = [(이름, 값HTML)]. 칸은 글자 폭만큼, 남는 폭은 고르게."""
    cells = "".join(f'<span style="flex:1 1 auto;text-align:center;white-space:nowrap;padding:0 8px;{"border-left:1px solid #E2E8F0;" if i else ""}">'
                    f'<span style="font-size:{NAME};font-weight:700;color:#111;">{esc(k)}</span> : <b style="color:#111;">{v}</b></span>'   # `기사 : 29` (2026-10-13 사용자)
                    for i, (k, v) in enumerate(items))
    return (f'<div style="display:flex;align-items:center;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:{10 - VP}px 4px;'
            f'margin:0 0 8px;font-size:{SMALL};line-height:{LH_CARD};">{cells}</div>')


def bullets(texts):
    """18px 글 목록 — 3px 점, 행간 33 (2026-10-12 사용자: 점은 18px 3px · 14px 2px 두 가지만). 서술 문장의 증감도 같은 색 규칙."""
    return dot_ul(dot_li(tint(esc(t)), size=3, lh=LH_BODY, margin=LI_MARGIN) for t in texts)


LI_MARGIN = "12px 0"   # 본문 글머리표 사이 6 → 12 (글머리표 사이 +6px, 2026-10-12 사용자)


def dot_ul(items_html):
    """점 글머리표 목록 (dot_li 묶음) — 기본 원형 글머리표는 쓰지 않는다."""
    return "<ul style='margin:0 0 8px;padding:0;list-style:none;'>" + "".join(items_html) + "</ul>"


ROW_L = "flex:0 0 40%;max-width:40%;min-width:0;white-space:normal;"   # A 카드 이름 40% — 값 `$229.28 ▼ 0.52%` 한 줄 (2026-10-12 사용자)
ROW_R = "flex:1 1 0;min-width:0;text-align:right;white-space:nowrap;"


def row(name, value_html, tone=""):
    """A타입 한 줄 카드: 이름 좌 · 값 우 한 줄 (18px, 구분선 없는 카드라 이름도 18px)."""
    return f'<span style="{ROW}{tone}"><span style="{ROW_L}font-weight:700;color:#111;">{esc(name)}</span> <span style="{ROW_R}">{value_html}</span></span> '


def multi(rows):
    """C타입: (이름, 값HTML) 여러 줄을 한 카드에. data-grid=2: 데스크톱에서 2열 (테마 CSS)."""
    out = ""
    for i, (name, value_html) in enumerate(rows):
        out += (f'<span style="{MULTI_ROW}{MULTI_SEP if i else ""}"><span style="{COL_L}font-weight:700;color:#111;font-size:{NAME};">{paren(esc(name))}</span> '
                f'<span style="{COL_R}font-weight:700;">{value_html}</span></span> ')
    return f'<span data-grid="2" style="{MULTI}">{out}</span> '


E_CELL = f"display:flex;flex:1;min-width:0;flex-wrap:wrap;justify-content:space-between;align-items:center;column-gap:8px;padding:{SEP_GAP - VP - 1}px 12px;white-space:nowrap;line-height:{LH_CARD};"
E_NAME = "flex:0 1 auto;min-width:0;white-space:nowrap;font-weight:700;color:#111;font-size:16px;"
E_VALUE = "flex:none;margin-left:auto;white-space:nowrap;font-weight:700;"


def multi2(items):
    """E타입 2열 멀티 카드: 한 줄에 둘, 세로 구분선 — 폰에서도 2열 (2026-10-12 사용자: "왜 2열 카드 유형 적용 안 했냐").
    칸 안은 65/35 대신 이름 왼쪽 · 값 오른쪽, 한 줄에 안 들어가면 값이 칸 안 다음 줄 오른쪽으로 내려간다."""
    out = ""
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        r = ""
        for j, it in enumerate(pair):
            name, value_html = it[0], it[1]
            logo = ticker_logo(it[2]) if len(it) > 2 and it[2] else ""   # 3번째 값 = 티커 로고 (2026-10-13 사용자: SPY · SMH · AMD · AVGO)
            r += (f'<span style="{E_CELL}{"border-left:1px solid #E2E8F0;" if j else ""}">'
                  f'<span style="{E_NAME}">{logo}{paren(esc(name))}</span> <span style="{E_VALUE}">{value_html}</span></span> ')
        if len(pair) == 1:
            r += f'<span style="{E_CELL}border-left:1px solid #E2E8F0;"></span>'
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


def fits_inline(name_html, sub, left_pct=65, name_px=16):
    """구분명 │ 보조 줄 첫 덩어리(뒤 가운뎃점 포함)가 폰 한 줄에 들어가는가. 안 들어가면 보조 줄은 이름 아래(구분선 없이) —
    구분선이 둘째 줄 첫머리로 밀리지 않게 (2026-10-12, 트럼프 급상승 주제에서 발견)."""
    chunks = str(sub).split(" · ")
    pill = 18 if ">N</span>" in name_html else 0
    need = _px(name_html.replace(">N</span>", "></span>"), name_px) * 1.04 + pill + 17 + _px(chunks[0], 14) + (10 if len(chunks) > 1 else 0)
    return need <= INLINE_ROOM * left_pct / 100 - 4


def crow_left(name_html, sub="", left_pct=65, block=False, name_size=None, tip_text=None):
    """C 카드 왼쪽 칸 안: 구분명(굵게) │ 보조 줄(14px #7A7A7A) 한 줄로 (2026-10-12 사용자: "구분선 넣고 한 줄로 표기 가능한 것은 모두").
    넘치면 · 에서 다음 줄로 이어진다. 엔비디아 렌더러도 이것을 쓴다."""
    ns = name_size or NAME
    t = tip_anno(tip_text) if tip_text else ""   # 구분명 옆 `안내 ?` — 그 줄의 읽는 법 (2026-10-12 · 13 사용자)
    if t:
        return _crow_left_tip(name_html, sub, left_pct, block, ns, t)
    if not sub:
        return f'<span style="font-weight:700;color:#111;font-size:{ns};">{paren(name_html)}</span>'
    if block or not fits_inline(name_html, sub, left_pct, int(ns[:-2])):   # 한 줄에 못 들어가면(또는 block) 이름 아래 블록
        return (f'<span style="font-weight:700;color:#111;font-size:{ns};">{paren(name_html)}</span>'
                f'<span style="display:block;color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};">{sub_line(sub)}</span>')
    return (f'<span style="font-weight:700;color:#111;font-size:{ns};">{paren(name_html)}</span>'
            f'<span style="color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};">{sub_line(sub, lead=VSEP)}</span>')


def _crow_left_tip(name_html, sub, left_pct, block, ns, t):
    core, sep, par = name_html.partition(" (")   # `안내 ?` 는 이름 바로 뒤, 괄호는 그 뒤에(괄호째 줄바꿈) — 2026-10-13
    name = (f'<span><span style="font-weight:700;color:#111;font-size:{ns};">{core}</span>{t}'
            + (f'<span style="font-weight:700;color:#111;font-size:{ns};">{paren(sep + par)}</span>' if sep else "") + "</span>")   # 한 span 으로 묶어 팝업 제목 = 구분명
    if not sub:
        return name
    if block or not fits_inline(name_html + "??", sub, left_pct, int(ns[:-2])):
        return name + f'<span style="display:block;color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};">{sub_line(sub)}</span>'
    return name + f'<span style="color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};">{sub_line(sub, lead=VSEP)}</span>'


VSEP = '<span style="display:inline-block;width:1px;height:14px;background:#E2E8F0;margin:0 8px;vertical-align:-1px;"></span>'


CHG_SIZE = "18px"   # 흰 카드 오른쪽 증감 숫자 19 → 18 (2026-10-13 사용자: 강조 카드 제외)
_ARROW_SPAN = re.compile(r'(<span style="color:#[0-9A-Fa-f]{3,6};font-weight:700;white-space:nowrap;)(">[▲▼–])')


def small_chg(value_html):
    """값 칸의 증감(arrow) 글자만 CHG_SIZE 로."""
    return _ARROW_SPAN.sub(lambda m: f"{m.group(1)}font-size:{CHG_SIZE};{m.group(2)}", value_html)


def crow(name_html, value_html, sub="", first=False, left=None, short=False, nowrap=False, sub_below=False, sub_block=False, name_size=None, tip_text=None):
    """C 카드 한 줄: 왼쪽 구분명 │ 보조 줄, 오른쪽 값. name_html 은 이스케이프된 HTML.
    left = 왼쪽 칸 % (카드별 예외, 가이드라인 2-1 — 2026-10-12 사용자). nowrap = 값을 한 줄로.
    sub_below = 보조 줄을 구분명 옆이 아니라 줄 아래 카드 폭 전체 한 줄로 (옆에 들어가지 않을 때, 2026-10-12 사용자).
    sub_block = 보조 줄을 구분명 아래 줄로 (왼쪽 칸 안) — 종목 아래 거래량 (2026-10-12 사용자)."""
    if name_size != EMPH_NAME:   # 흰 카드만 증감 18px — 강조 카드 제외 (2026-10-13 사용자)
        value_html = small_chg(value_html)
    col_l = f"flex:0 0 {left}%;max-width:{left}%;min-width:0;white-space:normal;" if left else COL_L75 if short else COL_L
    col_r = COL_R.replace("white-space:normal;", "white-space:nowrap;") if nowrap else COL_R
    below = (f'<span style="flex:0 0 100%;color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};white-space:nowrap;">{sub_line(sub)}</span>'
             if sub and sub_below else "")
    row_st = MULTI_ROW + ("flex-wrap:wrap;row-gap:0;" if below else "")
    return (f'<span style="{row_st}{"" if first else MULTI_SEP}">'
            f'<span style="display:block;line-height:{LH_CARD};{col_l}">{crow_left(name_html, "" if below else sub, left or (80 if short else 65), block=sub_block, name_size=name_size, tip_text=tip_text)}</span> '
            f'<span style="{col_r}font-weight:700;">{value_html}</span>{below}</span> ')   # 왼쪽 65% · 오른쪽 35%, 값이 모두 짧으면 80 · 20, left 가 있으면 그 값


EMPH_BG, EMPH_BD = "#FFF7ED", "#FED7AA"   # 강조 카드 배경·테두리 (오렌지)


def ccard(rows, left=None, attrs="", emph=False, pad=None, fold_at=None, noun=""):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html[, left_pct[, nowrap[, sub_below]]])]. left = 카드 전체 왼쪽 %. emph=True 면 강조 카드 배경(오렌지, 줄 구분선도 오렌지) — 2026-10-11 사용자: 급상승 주제."""
    short = short_values(rows)   # 값이 모두 5자 미만 → 왼쪽 80% (2026-10-11 사용자)
    # 줄 튜플 4번째 값 = 그 줄의 왼쪽 % (예: 시장 상태 막대 줄 30), 없으면 카드의 left (2026-10-12 사용자)
    parts = [crow(r[0], r[1], r[2], first=(i == 0 or i == fold_at), short=short, left=(r[3] if len(r) > 3 else left), nowrap=bool(len(r) > 4 and r[4]),
                         sub_below=bool(len(r) > 5 and r[5]), name_size=EMPH_NAME if emph else None,
                         tip_text=(r[6] if len(r) > 6 else None))   # 7번째 값 = 구분명 옆 ? 툴팁 (읽는 법, 2026-10-12 사용자)   # 강조 카드는 왼쪽 18px (2026-10-12 사용자)
             for i, r in enumerate(rows)]
    if pad is not None:
        parts = [x.replace(f"padding:{SEP_GAP - VP - 1}px 12px;", f"padding:{pad - VP}px 12px;") for x in parts]
    if fold_at is not None and len(parts) > fold_at:   # 펼침은 같은 카드 안 (2026-10-13 사용자)
        return fold_card("".join(parts[:fold_at]), "".join(parts[fold_at:]), f"{noun} {len(parts) - fold_at}개 더 보기", attrs=attrs)
    inner = "".join(parts)
    box = MULTI
    if emph:   # 강조 C 카드: 행간 32, 구분선 위아래 14 그대로, 구분선이 여러 개라 카드 위 · 아래도 14 그대로 (2026-10-12 사용자)
        inner = inner.replace(MULTI_SEP, f"border-top:1px solid {EMPH_BD};").replace(f"line-height:{LH_CARD};", f"line-height:{LH_EMPH};")
        inner = inner.replace(f"padding:{SEP_GAP - VP - 1}px 12px;", f"padding:{14 - VP_EMPH}px 12px {14 - VP}px;")   # 줄 위는 18px 이름(반쪽 6), 줄 아래는 14px 보조 줄(반쪽 2)
        box = MULTI.replace("background:#fff;border:1px solid #E2E8F0;", f"background:{EMPH_BG};border:1px solid {EMPH_BD};--grid-line:{EMPH_BD};").replace(
            f"line-height:{LH_CARD};", f"line-height:{LH_EMPH};")   # 구분선이 여러 개인 강조 카드 — 위아래 14 그대로(줄이 갖는다)
    return f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span data-grid="2" style="{box}">{inner}</span></div>'


def cards(html):
    """글 머리 카드 묶음 — data-lead: 홈 카드가 제목 없는 머리 구획으로 읽는다 (data-cards 는 엔비디아 탭 JS 가 보므로 여기선 쓰지 않는다)."""
    return f'<div data-lead="1" style="margin:0 0 8px;">{html}</div>'


def dcard(html, theme="neutral"):
    """D 본문 카드 (문장·목록). 배경은 방향 테마."""
    bg, bd = CARD_DIR.get(theme, CARD_DIR["neutral"])
    if theme == "neutral":   # 기본 카드 — 보이는 위아래 14
        return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{14 - VP}px 14px;margin:0 0 8px;line-height:{LH_CARD};">{html}</div>'
    return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{EMPH_PAD - VP_EMPH}px 14px;margin:0 0 8px;line-height:{LH_EMPH};">{html}</div>'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)


STATE_CARD = {"good": ("#F0FDF4", "#BBF7D0"), "uncertain": ("#FFFBEB", "#FDE68A"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#CBD5E1")}   # 신호 라벨 색의 카드판


def state_card(head_html, kind="neutral", right_html="", sub_html="", items=(), chev=False, center=False):
    """상태 카드 (2026-10-12 사용자: 종합·점수 카드 분리, 배경은 신호 라벨 색). 첫 줄 왼쪽 결론(굵게 검정 16px) · 오른쪽 값,
    둘째 줄 sub_html(14px 한 줄 설명), items = [(라벨, 내용)] 은 얇은 선 아래 3px 점 글머리표 14px."""
    bg, bd = STATE_CARD.get(kind, STATE_CARD["neutral"])
    head = (f'<span style="display:flex;justify-content:{"center" if center else "space-between"};align-items:center;gap:12px;{"text-align:center;" if center else ""}">'
            f'<span style="font-weight:700;color:#111;font-size:{EMPH_NAME};">{head_html}</span>'
            + (f'<span style="display:inline-flex;align-items:center;font-weight:700;white-space:nowrap;font-size:{SMALL};{"margin-left:auto;" if chev else ""}">{right_html}</span>' if right_html else "")   # 라벨 · 숫자 세로 가운데 (2026-10-13 사용자)
            + ((("" if right_html else '<span style="margin-left:auto;"></span>') + fold_btn(lighten(bg), bd)) if chev else "") + "</span>")   # chev: 맨 오른쪽 공식 접기 버튼, 바탕은 카드 색 20% 밝게 (2026-10-13 사용자)
    sub = f'<div style="font-size:{TINY};line-height:{LH_TINY};color:#374151;margin-top:2px;{"text-align:center;" if center else ""}">{sub_html}</div>' if sub_html else ""   # center: 종합 상태 카드 가운데 (2026-10-13 사용자)
    lis = "".join(dot_li((f"<b>{esc(k)}</b> : " if k else "") + esc(v), size=2, color="#374151", margin="8px 0") for k, v in items)
    body = (f'<div style="margin-top:{14 - VP_EMPH}px;padding-top:{14 - VP}px;border-top:1px solid {bd};font-size:{TINY};line-height:{LH_TINY};">'   # 제목 ~ 구분선 14 · 구분선 ~ 글 14 (보이는 여백, 2026-10-12 사용자: 4 → 14)
            f"<ul style='margin:-8px 0;padding:0;list-style:none;'>{lis}</ul></div>") if lis else ""   # 음수 margin = 첫·끝 li 의 8px 지우기
    # 위아래 24 — 끝 줄이 14px 글(행간 20)이면 반쪽 2, 18px 제목이면 6 (2026-10-12 사용자)
    bottom = EMPH_PAD - (VP if (lis or sub_html) else VP_EMPH)
    return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{EMPH_PAD - VP_EMPH}px 14px {bottom}px;margin:0 0 8px;line-height:{LH_EMPH};">{head}{sub}{body}</div>'


def emph_list(lines):
    """강조 카드 + 3px 점 글머리표 16px (2026-10-12 사용자: 주의할 위험요인 글을 강조 카드로). lines = 이스케이프 전 문장들. 증감은 색."""
    lis = "".join(dot_li(tint(esc(t)), size=3, lh=LH_EMPH) for t in lines if str(t).strip())   # 강조 카드 18px 글 → 행간 32
    if not lis:
        return ""
    return (f'<div style="background:{EMPH_BG};border:1px solid {EMPH_BD};border-radius:10px;padding:{EMPH_PAD - VP_EMPH}px 14px;margin:0 0 8px;line-height:{LH_EMPH};">'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)
            f"<ul style='margin:-9px 0;padding:0;list-style:none;font-size:{SMALL};color:#111;'>{lis}</ul></div>")   # 음수 margin = 첫·끝 li 의 9px 지우기


ACC_CHEV = ('<svg class="acc-chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>')


def lighten(hex_color, amt=0.2):
    """흰색 쪽으로 amt 만큼 섞은 색 — 공식 접기 버튼 바탕 (색 배경 위에서 20% 밝게, 2026-10-13 사용자)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{round(c + (255 - c) * amt):02X}" for c in (r, g, b))


FOLD_BOX, FOLD_RADIUS, FOLD_ICON, FOLD_LEFT = 31, 7, 18, 4   # 공식 접기 버튼: 엔비디아 평균 등급 네모 28 → 10% 크게 31, 화살표 16 → 18, 왼쪽 여백 4 (2026-10-13 사용자)


def fold_btn(bg="#fff", bd="#E2E8F0"):
    """공식 접기 버튼 — 줄 오른쪽 끝 네모 안 화살표 (가이드라인 10-6). 흰 카드 위에선 흰 바탕, 색 배경 카드 위에선 bg = 그 배경을 20% 밝게(lighten), bd = 카드 테두리.
    바깥 details[data-acc][open] 이면 테마 CSS가 화살표를 위로 돌린다."""
    chev = ACC_CHEV.replace('width="16" height="16"', f'width="{FOLD_ICON}" height="{FOLD_ICON}"')
    return (f'<span style="display:inline-flex;flex:none;align-items:center;justify-content:center;width:{FOLD_BOX}px;height:{FOLD_BOX}px;box-sizing:border-box;'
            f'border:1px solid {bd};border-radius:{FOLD_RADIUS}px;background:{bg};color:#111;margin-left:{FOLD_LEFT}px;vertical-align:middle;">{chev}</span>')


# 펼침 · 접기 카드 버튼 (`○○ n개 더 보기` · `그 외 n건` · `표 보기`) — 글자 14px (2026-10-12 사용자: "더 보기 버튼의 폰트 사이즈는 14, 블로그 모두 일괄")
FOLD_BTN = ("cursor:pointer;list-style:none;display:flex;justify-content:center;align-items:center;gap:6px;"
            f"padding:{10 - VP}px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;color:#111;font-size:{TINY};line-height:{LH_TINY};font-weight:700;")


def fold(label, inner_html):
    """펼침 버튼 (가이드라인 2-1 H 카드 버튼) — 눌러야 inner_html 이 보인다. details data-acc: 테마 CSS가 화살표를 돌리고 홈 카드는 건너뛴다."""
    return (f'<details data-acc="1" style="margin:0 0 8px;"><summary style="{FOLD_BTN}">{esc(label)} {ACC_CHEV}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


def state_fold(card_html, inner_html):
    """상태 카드를 버튼으로 — 누르면 아래 inner_html(카드)이 펼쳐진다, 기본 닫힘 (2026-10-13 사용자: "점수 … 우측 끝에 펼침아이콘, 6개 정보를 펼쳤을 때").
    card_html 은 state_card(..., chev=True). details data-acc: 테마 CSS가 열리면 화살표를 위로 돌리고 홈 카드는 건너뛴다."""
    card = card_html.replace("margin:0 0 8px;", "margin:0;", 1)   # 카드 아래 8px 은 details 가 갖는다
    return (f'<details data-acc="1" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;display:block;">{card}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


SUB_DOT = 4   # 소제목 앞 점 (2026-10-13 사용자: 2 → 3 → 4)
SUB_TOP_EXTRA = 15   # 소제목 위 여백 +15 → 29 (2026-10-13 사용자)


RULE_GAP = SEP_GAP + 5   # 카드 없이 가로 구분선만 둔 목록 — 선 위아래 보이는 27 (2026-10-13 사용자: "기존 구분선 여백 상하 여백에 5픽셀씩 더")


def item_rules(items_html, sub=False):
    """기사 목록 — 카드 없이 기사 사이 가로 구분선 (2026-10-13 사용자: "뉴스는 강조 뉴스 카드를 제외하고 가로 구분선으로 뉴스 영역을 구분").
    18px · 행간 34. 첫 기사 위는 구획 제목 밑줄이 대신한다. 항목은 li — 홈 카드가 글머리표로 읽는다. 구분선은 box-shadow (홈 카드는 border-top 요소를 건너뛴다)."""
    bottom = RULE_GAP - (VP if sub else NEWS_VP)
    lis = "".join(f'<li style="margin:0;padding:{(RULE_GAP - NEWS_VP) if i else 2}px 0 {bottom}px;line-height:{LH_BODY};{"box-shadow:inset 0 1px 0 #E2E8F0;" if i else ""}">{h}</li>'
                  for i, h in enumerate(items_html))
    return f'<ul style="margin:0 0 8px;padding:0;list-style:none;font-size:{SMALL};">{lis}</ul>' if lis else ""


def rule_rows(rows):
    """C 카드 줄을 카드 없이 가로 구분선으로만 (2026-10-13 사용자: "위험 탭에 추세유지 변동성 영역도 구분선으로") — 선 위아래 27, 좌우 여백 없음.
    rows 는 ccard 와 같은 튜플."""
    html = ccard(rows, pad=RULE_GAP - 1)
    html = html.replace(MULTI, f"display:block;margin:0 0 6px;font-size:{SMALL};line-height:{LH_CARD};border-bottom:1px solid #E2E8F0;", 1)   # 맨 위 선은 없음, 아래 끝만 (2026-10-13 사용자: "추세유지 위쪽 구분선은 삭제")
    html = html.replace(f"padding:{RULE_GAP - 1 - VP}px 12px;", f"padding:{RULE_GAP - 1 - VP + 5}px 0 {RULE_GAP - 1 - VP}px;", 1)   # 첫 줄 위 여백 +5 (같은 날 사용자)
    return html.replace(f"padding:{RULE_GAP - 1 - VP}px 12px;", f"padding:{RULE_GAP - 1 - VP}px 0;")


def sub_label(t, tip_text=None):
    """소제목. tip_text 가 있으면 소제목 바로 옆 ? 툴팁 — 그 소제목 내용의 읽는 법 (2026-10-12 사용자)."""
    lh = int(LH_CARD[:-2])
    dot = f'<span style="flex:none;align-self:flex-start;width:{SUB_DOT}px;height:{SUB_DOT}px;border-radius:50%;background:#111;margin-top:{(lh - SUB_DOT) // 2}px;"></span>'   # 2px 점 (2026-10-13 사용자)
    t_html = dot + f"<span>{paren(esc(t))}</span>" + (tips_right([("읽는 법", tip_text)]) if tip_text else "")   # 읽는 법 ? 는 줄 오른쪽 끝 (2026-10-13 사용자)
    # 바깥 div 에 display 를 주지 않는다 — 테마가 서브탭을 만들 때 hidden 을 거는데 인라인 display 가 이기면 숨지 않는다 (2026-10-13 발견)
    return f'<div data-sub="1" style="position:relative;font-size:{SMALL};line-height:{LH_CARD};color:#111;font-weight:700;margin:{14 + SUB_TOP_EXTRA}px 0 6px;"><span style="display:flex;align-items:center;gap:7px;">{t_html}</span></div>'   # 굵게 검정 (2026-10-13 사용자)


BAR_LABEL = "16px"   # F 막대 라벨 — `오늘 15건 … 긍정 67% · 부정 20% · 중립 13%` 가 폰 한 줄에 들도록 (2026-10-12)


def bar_label(label, pcts, split="right"):
    """F 막대 위 라벨 (2026-10-12 사용자): split="right" — 왼쪽 `오늘 15건` · 비율은 오른쪽 정렬, 모자라면 비율이 다음 줄 오른쪽으로.
    split="break" — 라벨 다음 줄에 비율 (`애널리스트 61명` / `강매수 16% · 매수 79% …`)."""
    return f'<span style="display:block;font-size:{BAR_LABEL};line-height:{LH_CARD};color:#111;font-weight:700;margin:0 0 3px;">{esc(label)}</span>'   # 막대 위 라벨은 검정 굵게, 비율은 막대 아래 (2026-10-13 사용자)


def bar_pcts(pcts):
    """막대 아래 비율 줄 `긍정 68% · 부정 16% …` (14px 안내 회색)."""
    return f'<span style="display:block;font-size:{BAR_LABEL};line-height:{LH_CARD};color:{NOTE};margin:0 0 10px;">{esc(pcts)}</span>'


def bar(label, segs, split="right"):
    """F 비율 막대: segs = [(이름, 개수, 배경, 글자)]."""
    total = sum(n for _, n, _, _ in segs)
    if not total:
        return ""
    pcts = " · ".join(f"{nm} {n / total * 100:.0f}%" for nm, n, _, _ in segs if n)
    body = "".join(f'<span style="display:block;width:{n / total * 100:.1f}%;background:{bg};color:{fg};font-size:{SMALL};font-weight:700;'
                   f'text-align:center;line-height:24px;overflow:hidden;white-space:nowrap;">{f"{n / total * 100:.0f}%" if n / total >= 0.08 else ""}</span>' for _, n, bg, fg in segs if n)
    return (bar_label(label, pcts, split) +
            f'<span style="display:flex;width:100%;height:24px;border-radius:6px;overflow:hidden;background:#F1F5F9;margin:0 0 3px;">{body}</span>' + bar_pcts(pcts))


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
    value_html, lv = small_chg(value_html), [small_chg(x) for x in lv]   # 증감 18px (2026-10-13 사용자)
    pct = max(0.0, min(1.0, frac)) * 100
    sub_html = f'<span style="display:block;color:{SUB};font-weight:400;font-size:{TINY};line-height:{LH_TINY};white-space:normal;">{sub_line(sub)}</span>' if sub else ""
    return (f'<span style="display:block;padding:{SEP_GAP - VP - 1}px 12px;line-height:{LH_CARD};{"" if first else MULTI_SEP}">'
            f'<span style="display:flex;align-items:center;white-space:nowrap;">'
            f'<span style="font-weight:700;color:#111;font-size:{NAME};display:flex;">{_sized(paren(name_html), [paren(x) for x in ln])}</span>'
            f'<span style="flex:1 1 0;min-width:24px;margin-left:{BAR_GAP};height:10px;background:#F1F5F9;border-radius:3px;overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{pct:.0f}%;background:{color};"></span></span>'
            f'<span style="margin-left:10px;font-weight:700;display:flex;">{_sized(value_html, lv, "right")}</span></span>{sub_html}</span> ')


def card_of(rows_html, attrs="", fold_at=None, noun=""):
    """미리 만든 줄(crow·bar_row)을 C 카드 하나로. fold_at 이 있으면 그 줄부터는 **같은 카드 안** 펼침 버튼 아래 (2026-10-13 사용자: "더 보기 버튼은 지수 더 보기처럼 카드에 포함").
    줄은 첫 줄만 first=True 로 만든다 — 펼친 줄도 같은 카드의 이어지는 줄이라 구분선이 있다."""
    rows_html = list(rows_html)
    if fold_at is None or len(rows_html) <= fold_at:
        return f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span data-grid="2" style="{MULTI}">{"".join(rows_html)}</span></div>'
    return fold_card("".join(rows_html[:fold_at]), "".join(rows_html[fold_at:]), f"{noun} {len(rows_html) - fold_at}개 더 보기", attrs=attrs)


FOLD_IN_CARD = ("cursor:pointer;list-style:none;display:flex;justify-content:center;align-items:center;gap:6px;"
                f"padding:{10 - VP}px 12px;border-top:1px solid #E2E8F0;color:#111;font-size:{TINY};line-height:{LH_TINY};font-weight:700;")


def fold_card(shown_html, more_html, label, attrs="", box=None):
    """카드 안 펼침 — 보이는 줄 · (펼친 줄) · 맨 아래 카드 폭 버튼 줄 `○○ n개 더 보기 ⌄` / 펼치면 `접기 ⌃` (2026-10-13 사용자).
    JS 없이도 details 로 열리고(버튼이 펼친 줄 위), 테마 JS(details[data-fold])가 펼친 줄을 버튼 위로 옮기고 글자를 `접기`로 바꾼다. data-acc: 홈 카드가 건너뛴다."""
    box = box or MULTI
    return (f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span style="{box}">'
            f'<span data-grid="2" style="display:block;">{shown_html}</span>'
            f'<details data-acc="1" data-fold="1" data-label="{esc(label)}"><summary style="{FOLD_IN_CARD}"><span>{esc(label)}</span> {ACC_CHEV}</summary>'
            f'<span data-grid="2" style="display:block;border-top:1px solid #E2E8F0;">{more_html}</span></details></span></div>')


def table(headers, rows, note_text=""):
    """표 — 카드로 못 푸는 통계 행렬에만. 16px, 칸은 어절 단위로만 줄바꿈, 좁은 화면은 표만 가로 스크롤."""
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};font-weight:400;">{esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:0 0 8px;font-size:{SMALL};line-height:{LH_CARD};">'
            f"<tr>{th}</tr>{body}</table></div>") + (note(note_text) if note_text else "")


def as_rules(html):
    """카드 → 구분선 (2026-10-13 사용자: "증시 리포트의 카드 형식의 정보들은 모두 구분선 정보로, 강조 카드는 위 · 아래 구분선이 있는 배경 컬러").
    흰 콘텐츠 카드(MULTI 상자)는 위 · 아래 선만, 줄 좌우 여백 0. 색 배경 카드(모서리 10)는 배경 + 위 · 아래 선, 옆 테두리 · 모서리 없음. 데일리 build_body 끝에서 한 번."""
    html = html.replace(MULTI, f"display:block;margin:0 0 6px;border-top:1px solid #E2E8F0;border-bottom:1px solid #E2E8F0;font-size:{SMALL};line-height:{LH_CARD};")
    html = html.replace(f"padding:{SEP_GAP - VP - 1}px 12px;", f"padding:{SEP_GAP - VP - 1}px 0;")
    return re.sub(r"border:1px solid (#[0-9A-Fa-f]{6});border-radius:10px;", r"border-top:1px solid \1;border-bottom:1px solid \1;", html)


def footer(data_line, disclaimer_line, indent=True):
    """출처 · 면책 줄. indent=False: 들여쓰기 없이 위 목록과 같은 왼쪽 선 (데일리 위험 탭, 2026-10-13 사용자)."""
    return (f'<div data-footer="1" style="margin-top:3px;padding-top:2px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};{GUIDE_IND if indent else ""}">'
            f"{INFO_ICON}{data_line}<br>{INFO_ICON}{disclaimer_line}</div>")
