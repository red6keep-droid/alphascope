"""디자인 가이드라인(디자인-가이드라인.md) 공통 조각 — 데일리 리포트·트럼프 트렌드 렌더러가 같이 쓴다 (2026-10-11).

엔비디아 리포트(experiments/nvda-report/render_html.py)에서 굳은 규칙을 그대로 옮겼다: 18px 본문, 21px 구획 제목, 카드 A·C·D·E·F,
안내 글은 ⓘ + 14px 회색, 라벨은 외곽선 알약 16px, 링크는 아이콘, 날짜는 점 표기. 숫자는 파이썬이 그린다.
의존성 없음 — 각 파이프라인은 sys.path 에 experiments/ 를 넣고 `import design_kit as dk` 로 쓴다.
"""

import html as html_mod
import json
import math
import os
import re

UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
SUB = "#7A7A7A"   # 카드 보조 글(보조 줄·· 현재가·/ 100·날짜) — #999 보다 20% 진하게 (2026-10-11 사용자). "—" 자리 표시는 MUTED 그대로
NOTE = "#6B7280"          # 안내 글 회색
BODY, SMALL, TINY, MICRO = "19px", "19px", "14px", "14px"   # 본문 18 → 19 (2026-10-13 사용자: "모든 리포트의 블로그 전체의 본문 폰트는 19포인트")   # 안내 글(14px)을 빼고 모두 18px (2026-10-12 사용자: "안내 14포인트를 제외하고 본문 폰트는 모두 18")
NAME = "16px"   # 가로 구분선이 있는 카드의 왼쪽 정보(구분명) — 2026-10-12 사용자: "가로 구분선이 있는 카드의 좌측 정보는 16포인트"
EMPH_NAME = "19px"   # 본문과 같이 19 (2026-10-13)   # 강조 카드(색 배경: 상태·결론·흐름·강조 C 카드)의 왼쪽 정보는 18px (2026-10-12 사용자)
EMPH_Q, LH_EMPH_Q = "18px", "30px"   # 강조(상태) 카드 머리 줄 질문 · 대답 — 19 → 18, 행간도 같은 비율 32 → 30 (2026-10-27 사용자). 행간 반쪽은 그대로 6 이라 위아래 보이는 여백은 같다
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
LINK_ICON = ('<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" style="vertical-align:-1px;" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M4.5 11.5 11.5 4.5"/><path d="M6 4.5h5.5V10"/></svg>')
NEW_PILL = ('<span style="display:inline-block;background:#B91C1C;color:#fff;border-radius:3px;padding:1px 4px 0;font-size:10px;font-weight:700;'
            'line-height:13px;vertical-align:middle;margin-left:4px;">N</span>')
WRAP_OPEN = ('<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
             f'font-size:{BODY};line-height:{LH_BODY};color:#333;">')   # 본문 행간 34px — 카드는 각자 LH_CARD 24px 를 단다 (2026-10-12 사용자)
WRAP_CLOSE = "</div>"
SEO_LEAD = f"font-size:{BODY};line-height:{LH_BODY};color:#333;margin:0 0 12px;word-break:keep-all;"   # 글 맨 앞 요약 p[data-seo-lead] — 본문과 같은 19px · 행간 34 (2026-10-18 사용자: "이 문장은 폰트 사이즈가 다른데", 16px 이던 것). 모든 리포트 · 종목 페이지 공통
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


# 차트 제목 — 앞에 ※ · 한 단계 작게(19 → 16px) · 굵게 (2026-10-26 사용자: "※ 그 일정 뒤 코스피 움직임 (%) 처럼 기호를 앞에, 폰트는 한 단계 작게"). 뒤에 제목 글 + </span>
CHART_MARK = '<span style="font-weight:400;font-size:.85em;position:relative;top:calc(-.05em - 1px);">※</span> '   # ※ 는 보통 굵기 · 조금 작게 · 위로 보정 — 폰 글꼴에서 굵은 ※ 가 무겁고 가운데가 안 맞았다 (2026-10-26 사용자, 비교 C-1)
_CHART_TITLE_STYLE = f"display:block;font-weight:700;color:#111;font-size:{NAME};line-height:{LH_CARD};"
CHART_TITLE = f'<span style="{_CHART_TITLE_STYLE}">' + CHART_MARK
CHART_TITLE_M = f'<span style="{_CHART_TITLE_STYLE}margin:0 0 6px;">' + CHART_MARK   # 아래 6px 를 두던 질문 카드 안 차트 제목


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


ALIGN_PX = 6   # 좌측 기준선 — 카드 밖 구획 제목 · 글의 왼쪽 시작선 = 홈 실시간 뉴스 글자 (폰: 화면 가장자리 20 = 본문 영역 14 + 6, 2026-10-24 사용자). 옛 13(카드 안 글자, 2026-10-23)을 대체


def align_titles(html, px=ALIGN_PX):
    """카드 밖 구획 제목(h2) · 소제목(data-sub) · 카드 제목 · 맨 앞 요약(data-seo-lead)을 기준선까지 들여쓴다. 이미 padding-left 가 있으면 건드리지 않는다 (탭 막대 · 카드 안 글은 이 함수 대상이 아니다)."""
    def add(mo):
        st = mo.group(2)
        return mo.group(0) if "padding-left" in st else f'{mo.group(1)}{st}padding-left:{px}px;"'
    return re.sub(r'(<h2[^>]*? style="|<div data-sub="1" style="|<p data-seo-lead="1"[^>]*? style="|<div style="(?=font-size:19px;line-height:24px;font-weight:700;color:#111;margin:25px 0 8px;))([^"]*)"', add, html)   # 마지막 = 카드 제목(기간별 수익률 · 1년 가격 범위 …)   # 맨 앞 요약(data-seo-lead)도 같은 선 (2026-10-23 사용자)


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


_UNITS = r"(%p|%|bp|p(?![A-Za-z])|원|억|조)"   # 원 · 억 · 조 · p(VIX 포인트) 추가, 쉼표 숫자도 (2026-10-26 사용자: "증감 표현에 있는 모든 정보는 증감 컬러")
_SIGNED = re.compile(r"(?<![\w.~])(?<!~ )([+\-−])(\d[\d,]*(?:\.\d+)?)" + _UNITS + r"(?!\s*~)")   # 범위(-0.63 ~ +0.63%)는 칠하지 않는다
_LABEL = re.compile(r"^([^:：]{1,24}?)\s*:\s+(.+)$", re.S)


# 증감 값 앞의 종목 이름 — "산업재(XLI)", "나스닥 100(QQQ)", "1위 기술" (2026-10-11 사용자: 종목도 같이 색)
_NAMED = re.compile(r"((?:\d+위 )?(?:[A-Za-z][A-Za-z&;]* |[가-힣A-Za-z]+ (?=\d))?[가-힣A-Za-z0-9&;]+(?:\([A-Z0-9^.&;\s]{1,12}\))|\d+위 [가-힣A-Za-z&;·]+)\s"
                    r"(?<![\w.~])([+\-−])(\d[\d,]*(?:\.\d+)?)" + _UNITS + r"(?!\s*~)")


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
    if plain.rstrip().endswith(("순매수", "순매도")):   # `9,778억 순매도` — 부호 대신 말로 적은 수급 값 (2026-10-29 사용자, 한국 증시 리포트 M42)
        dirs.add("+" if plain.rstrip().endswith("순매수") else "-")
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


DOT_W = 10   # 가운뎃점 칸 폭 (dot_chunks) — 점 앞 4px, 뒤는 남은 폭 + 덩어리 사이 공백이라 앞뒤가 비슷하다


def dot_chunks(parts_html):
    """덩어리 목록 → 가운뎃점으로 이은 한 줄 (**오른쪽 정렬 줄 전용**). 줄바꿈은 점 사이에서만 (점은 앞 덩어리 끝에 붙는다), 한 줄보다 긴 덩어리만 안에서 바뀐다.
    줄 끝에 남는 점은 보이지 않는다 (2026-10-26 사용자: "줄바꿈을 하고 나면 가운데 점은 삭제") — 모든 덩어리 끝에 같은 폭(DOT_W)의 점 칸을 붙이고,
    안쪽 상자를 오른쪽으로 DOT_W 만큼 넓혀 overflow 로 자른다. 오른쪽 정렬이라 줄마다 마지막 점 칸이 잘린 자리에 떨어진다."""
    dot = f'<span style="display:inline-block;width:{DOT_W}px;padding-left:4px;box-sizing:border-box;text-align:left;">·</span>'
    inner = " ".join(f'<span style="display:inline-block;max-width:100%;vertical-align:top;">{x}{dot}</span>' for x in parts_html)
    return f'<span style="display:block;overflow:hidden;"><span style="display:block;margin-right:-{DOT_W}px;">{inner}</span></span>'


# ── 세로 막대 그래프 — 숫자 겹침 금지 · 모자라면 가로 스크롤 (2026-10-26 사용자, 가이드라인 8절) ──
CHART_PHONE_W = 290   # 폰에서 그래프가 쓰는 폭 (본문 320 − 카드 안 여백)
CHART_PAD_PX = 4      # 막대 묶음 양옆 최소 틈 (가로 스크롤로 넘어갈 때)


def text_px(text, fs):
    """글자 폭 어림 (px) — 굵은 숫자 기준, 한글은 1em. 겹침 판정용이라 넉넉하게 잡는다."""
    w = 0.0
    for c in re.sub(r"<[^>]+>", "", html_mod.unescape(str(text))):
        w += 1.0 if ord(c) >= 0x1100 else 0.3 if c in ".,:" else 0.9 if c == "%" else 0.62
    return w * fs


BAR_W = 28     # 막대 기준 폭 px — 엔비디아 · 한국 `최근 12개월 풋/콜 거래량 비율` 막대(숫자 세 자리 0.86 폭) (2026-10-26 사용자: "막대 가로 사이즈를 맞춰 줘")
BAR_MAX = 36   # 숫자가 길면(+2.72 · −4.12 같은 네 자리) 이만큼까지만 넓힌다 — 막대가 적어도 화면을 채우려 늘리지 않는다
GROUP_PAD_MULTI = 1.8   # 시리즈가 둘 이상인 묶음의 양옆 틈 배수 (묶음 사이 8 → 약 14px)
BAR_NUM_PX = 13   # 막대 위 숫자 글자 — 모든 세로 막대 하나로, 가로축 이름(AXIS_FS)과 같은 크기 · 굵게 (2026-10-27 사용자: "그래프 위 숫자 폰트가 다 다르다" → 13 통일. 옛 막대 수별 11~17 · 데일리 11)
BAR_RATIO = 0.8   # 막대 폭 = 숫자 폭 × 0.8, 최소 BAR_W · 최대 BAR_MAX (2026-10-27 사용자: "막대가 숫자보다 굵다, 숫자의 80% 정도")
COL_GAP = 2    # 한 묶음 안 시리즈 막대 사이 (BAR_GAP 은 가로 막대 줄 간격으로 따로 있다)


LEGEND_SIGN = ("#ED8E87", "#82B1F0")   # 이 종목(대상) 오름 · 내림 막대 색 — 범례에 쓰지 않는다
LEGEND_GRAY = "#CBD5E1"   # 비교 막대(회색)


def legend_items(items):
    """그래프 범례 정리 (2026-10-27 사용자: "애플 늘어남 · 애플 줄어듦 같은 범례는 전부 삭제, 회색이 있으면 `비교 대상 : 시총 상위 20개` 처럼 짧게").
    오름 · 내림 색 칩은 뺀다(빨강 · 파랑 뜻은 블로그 공통), 회색 칩은 `비교 대상 : 이름` — 이름 끝 `(중앙값)` · `중앙값` 은 뗀다. 다른 색(주황 · 올해/작년 등)은 그대로."""
    out = []
    for nm, c in items:
        if str(c).upper() in LEGEND_SIGN:
            continue
        if str(c).upper() == LEGEND_GRAY and not nm.startswith("비교 대상"):
            nm = "비교 대상 : " + re.sub(r"\s*\(?중앙값\)?$", "", nm).strip()
        out.append((nm, c))
    return out


def col_layout(n, ns, label_px, axis_px):
    """막대 묶음 n개 × 시리즈 ns개 — (막대 폭 px, 숫자 칸 폭 px, 그래프 최소 폭 px).
    막대 폭은 어디서나 BAR_W(숫자가 길면 BAR_MAX 까지) — 막대가 적어도 넓히지 않고 묶음 사이만 벌어진다 (2026-10-26 사용자).
    숫자 칸은 숫자 폭 이상이라 막대보다 넓을 수 있다(숫자는 절대 겹치지 않게, 가이드라인 8절). 묶음 폭은 가로축 이름 폭 이상, 모자라면 가로 스크롤."""
    w = max(BAR_W, min(round(label_px * BAR_RATIO), BAR_MAX))   # 숫자 폭의 80% — 막대가 숫자보다 한 단계 가늘게 (2026-10-27 사용자)
    lw = max(w, label_px)
    group = max(ns * lw + (ns - 1) * COL_GAP + 2 * CHART_PAD_PX * (GROUP_PAD_MULTI if ns > 1 else 1), axis_px)   # 여러 막대 묶음은 묶음 사이를 80% 넓게 (2026-10-26 사용자: "월 월 사이가 너무 붙어 있다")
    return w, lw, int(n * group + 0.999)


def bar_x(i, k, n, ns, w, lw, label=False):
    """묶음 i 의 시리즈 k 막대(label=True 면 그 위 숫자 칸)의 `left:…;width:…;` — 묶음 가운데에 고정 폭으로 놓는다."""
    step = lw + COL_GAP
    off = (k - (ns - 1) / 2) * step - (lw if label else w) / 2
    return f"left:calc({(i + 0.5) * 100 / n:.3f}% + {off:.1f}px);width:{lw if label else w}px;"


GRID_LINE = "#ECF0F5"   # 막대 그래프 가로 눈금선 — 0 기준선(#CBD5E1)보다 연하게. #EEF2F7 에서 1% 진하게 (2026-10-26 사용자: 5% → 2% → 눈금선만 1%)
GRID_FS = 10            # 왼쪽 세로축 숫자 글자


def _nice_step(span):
    """눈금 간격 — 범위를 4칸 안팎으로 나누는 1 · 2 · 5 × 10ⁿ (3칸이면 눈금이 0 하나뿐인 그래프가 생겼다)."""
    raw = span / 4 if span > 0 else 1
    e = 10 ** math.floor(math.log10(raw))
    return next(m * e for m in (1, 2, 5, 10) if raw <= m * e)


CHART_CARD_X = -5   # 그래프 흰 카드를 양쪽 5px 씩 넓게 (가로 +10px: +4 → +2 → +4, 2026-10-26 사용자) — 제목은 카드 밖이라 그대로
CHART_CARD_PAD = 10   # 그래프 흰 카드 안 위 여백 = 아래 여백 — 아래(가로축 이름 줄 6 + 빈 줄 4 = 10)가 기준 (2026-10-26 사용자: "고용 지표 아래 여백 기준으로 보통 날 위 여백을")
AXIS_FS = "13px"   # 가로축 이름 — 안내 14px 보다 1px 작게 (2026-10-26 사용자: "아래 숫자 1, 2, 6, 7 … 1포인트 작게")
AXIS_PAD = 16   # 맨 아래 눈금선 ~ 가로축 이름 위 (2026-10-26 사용자: "막대와 FOMC 같은 이름 사이 위쪽 여백을 이 그래프 기준으로" — 데일리 막대 숫자 자리 16)


def col_axis(vals, height, lbl):
    """세로축 — (눈금 목록, 0 의 y, 1 단위 px). 범위는 막대보다 **한 칸 바깥 눈금까지** (2026-10-26 사용자: "항상 막대 범위 밖 눈금, 1.7 이면 2.0 까지").
    위 여백 = 막대 위 숫자 자리(lbl), 아래 여백 = AXIS_PAD — 음수 막대 아래 숫자가 가로축 이름에 닿을 때만 늘린다."""
    mp, mn = max(0.0, max(vals)), max(0.0, -min(vals))
    step = _nice_step(mp + mn)
    hi = (math.floor(mp / step + 1e-9) + 1) * step if mp > 0 else 0.0
    lo = -(math.floor(mn / step + 1e-9) + 1) * step if mn > 0 else 0.0
    bottom = AXIS_PAD
    for _ in range(2):
        scale = (height - lbl - bottom) / ((hi - lo) or 1)
        need = lbl - (min(vals) - lo) * scale if mn > 0 else 0   # 가장 낮은 막대 아래 숫자가 눈금선 밑으로 나가는 만큼
        if need <= bottom:
            break
        bottom = need
    ticks = [round(lo + k * step, 10) for k in range(int(round((hi - lo) / step)) + 1)]
    return ticks, lbl + hi * scale, scale


def col_frame(bars_html, axis_names, height, top, scale, ticks, min_w):
    """세로 막대 그래프 틀 — 왼쪽 세로축 숫자 + 연한 가로 눈금선 + 0 기준선, 막대 · 가로축 이름은 그 오른쪽 (2026-10-26 사용자: "막대 그래프에 가로 눈금선, 좌측에 눈금 기준").
    bars_html 은 막대 칸(0~100%) 기준으로 놓인 막대 · 숫자. 눈금 · top · scale 은 col_axis 가 정한다."""
    step = (ticks[1] - ticks[0]) if len(ticks) > 1 else 1
    dec = max(0, -math.floor(math.log10(step) + 1e-9)) if step < 1 else 0
    fmt = lambda v: f"{abs(v):.{dec}f}" if abs(v) < 10 ** -(dec + 1) else f"{v:.{dec}f}".replace("-", "−")   # noqa: E731
    gut = int(max(text_px(fmt(v), GRID_FS) for v in ticks) + 6)
    grid = []
    for v in ticks:
        y = top - v * scale
        if abs(v) > 1e-12:
            grid.append(f'<span style="position:absolute;left:{gut}px;right:0;top:{y:.1f}px;height:1px;background:{GRID_LINE};"></span>')
        grid.append(f'<span style="position:absolute;left:0;width:{gut - 6}px;top:{y - 7:.1f}px;height:14px;line-height:14px;text-align:right;font-size:{GRID_FS}px;color:{NOTE};">{fmt(v)}</span>')
    plot = (f'<span style="position:absolute;left:{gut}px;right:0;top:0;bottom:0;">'
            f'<span style="position:absolute;left:0;right:0;top:{top:.1f}px;height:1px;background:#CBD5E1;"></span>{bars_html}</span>')
    xl = "".join(f'<span style="flex:1 1 0;min-width:0;text-align:center;white-space:nowrap;">{"<br>".join(esc(x) for x in g.split(chr(10)))}</span>' for g in axis_names)   # 이름 아래 줄(연결 이유 · `지금`)은 줄바꿈 (2026-10-27 P31 · P36)
    return scroll_x(f'<span style="display:block;position:relative;height:{height}px;">{"".join(grid)}{plot}</span>'
                    f'<span style="display:flex;padding-left:{gut}px;font-size:{AXIS_FS};line-height:20px;color:{NOTE};margin:2px 0 6px;">{xl}</span>', min_w + gut)


_HINT_RE = re.compile(r'^(<span data-scroll-hint="1"[^>]*>.*?</span>)', re.S)
_LEGEND_RE = re.compile(r'^<span style="[^"]*">(.*)</span>$', re.S)
_CHIP_RE = re.compile(r'<span style="display:inline-flex[^"]*"><span [^>]*></span>[^<]*(?:<span data-unit="1"[^>]*>[^<]*</span>)?</span>')   # 범례 칩 하나 (색 네모 + 이름 [+ 단위])
LEGEND_LEFT = 5   # 범례 왼쪽 여백 (2026-10-28 사용자 P50: 모든 그래프)


LEGEND_TOP = 5   # 그래프 카드 첫 줄(범례 또는 `밀어서 보기`) 위 +5px — 카드 위 테두리 ~ 첫 줄 = 10 + 5 (2026-10-26 사용자: 기준 = `오늘 움직임과 평소 하루 크기` 그래프)


_JOSA = {"은": ("은", "는"), "는": ("은", "는"), "이": ("이", "가"), "가": ("이", "가"), "을": ("을", "를"), "를": ("을", "를"),
         "과": ("과", "와"), "와": ("과", "와"), "으로": ("으로", "로"), "로": ("으로", "로")}
_DIGIT_TAIL = {"0": 21, "1": 8, "2": 0, "3": 16, "4": 0, "5": 0, "6": 1, "7": 8, "8": 8, "9": 0}   # 숫자 읽는 소리의 받침 (0 은 아래에서 자리로)
_ZERO_TAIL = {1: 17, 2: 1, 3: 4, 4: 4}   # 끝 0 개수 → 십(ㅂ) · 백(ㄱ) · 천(ㄴ) · 만(ㄴ)


def _tail(word):
    """마지막 글자 소리의 받침 번호 (0 = 받침 없음, 8 = ㄹ) — 한글은 글자, 숫자는 읽는 소리(96 → 육, 10 → 십), % 는 퍼센트."""
    w = re.sub(r"<[^>]+>", "", str(word)).rstrip()
    if not w:
        return 0
    c = w[-1]
    if "가" <= c <= "힣":
        return (ord(c) - 0xAC00) % 28
    if c.isdigit():
        digits = re.sub(r"[^\d.]", "", w).split(".")
        tail = digits[-1] if len(digits) > 1 else digits[0]
        if len(digits) > 1 or tail[-1] != "0":
            return _DIGIT_TAIL[tail[-1]]
        z = len(tail) - len(tail.rstrip("0"))
        return 21 if z == len(tail) else _ZERO_TAIL.get(min(z, 4), 4)
    return 0   # % (퍼센트) · p (포인트) · 영문 등 — 받침 없음으로 본다


def josa(word, p):
    """word 뒤에 맞는 조사 — josa("삼성전자", "은") → "삼성전자는", josa("96", "로") → "96으로" (2026-10-28 P69: 자동 문장의 `96로` · `삼성전자은`)."""
    yes, no = _JOSA[p]
    t = _tail(word)
    if yes == "으로":
        return f"{word}{'로' if t in (0, 8) else '으로'}"
    return f"{word}{yes if t else no}"


def q_axis(q):
    """분기 가로축 이름 `2025Q3` · `2025-Q3` → `25년\n3분기` (2026-10-28 사용자 P63 · P66: `Q` 약어 대신 한글, 두 줄)."""
    q = str(q)
    return f"{q[2:4]}년\n{q[-1]}분기"


def legend_unit(legend_html, unit):
    """범례 `비교 대상 : …` 바로 오른쪽에 단위 (2026-10-28 사용자 P54: `비교 대상 : KOSPI` 우측에 `회복일`). 비교 칩이 없으면 마지막 칩 뒤."""
    i = legend_html.rfind("비교 대상")
    j = legend_html.find("</span>", i if i >= 0 else 0) if i >= 0 else legend_html.rfind("</span>", 0, legend_html.rfind("</span>"))
    if j < 0:
        return legend_html
    return legend_html[:j] + f'<span data-unit="1" style="margin-left:7px;">단위 : {unit}</span>' + legend_html[j:]


def legend_top(chart_html, legend_html):
    """그래프 위 한 줄 — 왼쪽 범례 · 오른쪽 `넘겨 보기 ›`(넘칠 때만) (2026-10-26 사용자: "넘겨 보기는 항상 우측, 범례는 좌측 — 넘겨 보기가 없어도 범례는 좌측").
    legend_html = 범례 칩 줄(_legend_chips · legend_chips). 좁으면 `넘겨 보기` 가 다음 줄 오른쪽으로 내려간다. 그래프 아래에는 범례가 없으니 빈 4px 로 아래 여백을 맞춘다."""
    hint = ""
    m = _HINT_RE.match(chart_html or "")
    if m:
        hint, chart_html = m.group(1).replace(f"margin:{LEGEND_TOP}px 0 4px;", "margin:0 0 0 auto;", 1), chart_html[m.end():]   # 위 5px 는 범례 줄이 갖는다 · 오른쪽 끝
        chart_html = chart_html.replace(f'data-shade-up="{SCROLL_SHADE_UP}"', 'data-shade-up="0"', 1).replace(f"padding-top:{SCROLL_SHADE_UP}px;margin-top:-{SCROLL_SHADE_UP}px;", "padding-top:0px;margin-top:-0px;", 1)
    lm = _LEGEND_RE.match(legend_html or "")
    chips = (lm.group(1) if lm else legend_html or "").replace("margin:0 0 0 12px;", "margin:0;").replace("margin:0 12px 0 0;", "margin:0;")   # 칩 사이는 줄의 column-gap 12px
    # 칩마다 따로 줄바꿈 — 길면 `비교 대상 : …` 이 아랫줄로 내려가고 `넘겨 보기` 는 그 같은 줄 오른쪽 (2026-10-28 사용자 P73). 범례 왼쪽 5px (P50)
    items = _CHIP_RE.findall(chips)
    if items and "".join(items) == chips:
        cmp_ = [c for c in items if "비교 대상" in c][-1:]
        rest = "".join(c for c in items if c not in cmp_)
        tail = (f'<span style="flex:1 1 auto;display:flex;justify-content:space-between;align-items:center;column-gap:12px;">{cmp_[0]}{hint}</span>'
                if cmp_ else hint)
        # 비교 대상 · 넘겨 보기가 없으면 바깥 space-between 이 칩들을 줄 전체에 벌려 놓는다(시가 갭 · 장중 · 하루) → 칩 묶음은 왼쪽에 모아 둔다 (2026-10-29 사용자 M57)
        body = (f'<span style="display:flex;flex-wrap:wrap;align-items:center;column-gap:12px;">{rest}</span>' if rest else "") + tail
    else:
        body = f'<span style="text-align:left;">{chips}</span>{hint}'
    top = (f'<span data-chart-top="1" style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;column-gap:12px;'
           f'font-size:{MICRO};line-height:{LH_CARD};color:{NOTE};margin:{LEGEND_TOP}px 0 4px;padding-left:{LEGEND_LEFT}px;">{body}</span>')
    return top + chart_html + '<span style="display:block;height:4px;"></span>'


SCROLL_SHADE = ("background:linear-gradient(to left,#fff 30%,rgba(255,255,255,0)) 100% 0/28px 100% no-repeat local,"
                "radial-gradient(farthest-side at 100% 50%,rgba(15,23,42,.18),rgba(15,23,42,0)) 100% 0/14px 100% no-repeat scroll;background-color:#fff;")


SCROLL_CHEV = ('<svg viewBox="0 0 6 10" width="0.42em" height="0.7em" aria-hidden="true" style="margin-left:4px;vertical-align:-0.02em;position:relative;top:-1px;" '
               'fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M1.2 1.2 4.8 5 1.2 8.8"/></svg>')   # `›` 글자는 폰 글꼴에서 찌그러지고 가운데가 낮았다 — 직접 그림, 1px 위 (2026-10-26 사용자)
SCROLL_SHADE_UP = 8   # 그림자를 그래프 위로 더 (안내 줄 쪽)
SCROLL_HINT = "넘겨 보기"   # 옛 `밀어서 보기` (2026-10-26 사용자)
FAINT = "#9CA3AF"   # 블로그 푸터 설명글의 흐린 글씨(테마 --gray-350) — `넘겨 보기` (같은 날 사용자)


def scroll_x(html, min_w):
    """화면이 그래프 최소 폭보다 좁으면 가로 스크롤 (넓으면 그대로 꽉 채운다).
    더 있다는 표시 (2026-10-26 사용자: "밀어서 보기를 오른쪽 상단에, 오른쪽에 세로로 그림자를 넣어 더 있다는 걸"):
    ① 오른쪽 세로 그림자 — 오른쪽에 더 있을 때만 보이고 끝까지 밀면 사라진다(CSS 만: 덮개 local · 그림자 scroll 배경) ·
    ② 그래프 오른쪽 위 `밀어서 보기 ›` — 폰 폭에서 넘칠 때만 넣고, 화면이 넓어 안 넘치면 테마 JS(`data-scroll-hint`)가 숨긴다."""
    hint = (f'<span data-scroll-hint="1" style="display:block;text-align:right;font-size:{TINY};line-height:{LH_TINY};color:{FAINT};margin:{LEGEND_TOP}px 0 4px;">{SCROLL_HINT}{SCROLL_CHEV}</span>'
            if min_w > CHART_PHONE_W else "")   # 범례 없는 그래프는 오른쪽 위 (2026-10-26 사용자) — 범례가 있으면 legend_top 이 범례 줄 왼쪽으로 옮긴다
    up = SCROLL_SHADE_UP if hint else 0   # 오른쪽 그림자를 위로 더 길게 — 안내 줄 높이까지 (2026-10-26 사용자)
    return (f'{hint}<span data-scroll-x="1" data-shade-up="{up}" style="display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;{SCROLL_SHADE}padding-top:{up}px;margin-top:-{up}px;">'
            f'<span style="display:block;min-width:{min_w}px;">{html}</span></span>')


def sub_line(sub_html, lead=""):
    """C 카드 보조 줄 내용 — 증감 색(tint) + 모든 덩어리는 통째로 (줄바꿈은 가운뎃점 `·` 사이에서만).
    lead(세로 구분선)는 첫 덩어리에 붙여 줄 끝에 홀로 남지 않게 한다."""
    chunks = tint(sub_html).split(" · ")
    chunks[0] = lead + chunks[0]
    parts = []
    for i, c in enumerate(chunks):
        sep = f'<span style="color:{SUB};">&nbsp;·</span>' if i < len(chunks) - 1 else ""   # 가운뎃점은 앞 덩어리에 붙여 줄 첫머리에 오지 않게
        plain = html_mod.unescape(re.sub(r"<[^>]+>", "", c))
        if i == 0 and lead:
            plain = plain.strip()
        parts.append(f'<span style="display:inline-block;max-width:100%;vertical-align:top;">{c}{sep}</span>')   # 덩어리마다 통째로 — 줄바꿈은 가운뎃점 사이에서만, 한 줄보다 긴 덩어리만 안에서 줄이 바뀐다 (2026-10-23 사용자: 가격 정보 하단 글)
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


# 툴팁 데이터 근거 (2026-10-20 사용자: "툴팁에 데이터 근거가 명시되어야 한다 · 짧게 반복되는 내용이라 일괄 표시").
# 리포트마다 기본 출처를 TIP_SRC 에 정하고, 다른 데이터를 쓰는 툴팁만 with_src() 로 바꾼다. 출처는 data-src 속성으로 나가고
# 테마 팝업이 맨 아래에 `출처 : X 데이터로 계산한 내용입니다.` 한 줄로 그린다. 출처 줄은 글 끝 줄로 실어 나르므로 툴팁 글을 고치는 함수(replace · split)를 거쳐도 남는다.
TIP_SRC = ""
SRC_MARK = "출처 : "


def with_src(text, src):
    """이 툴팁만 기본(TIP_SRC)과 다른 데이터 출처 — 예: with_src(tip, "CNN")."""
    return f"{text}\n{SRC_MARK}{src}" if text and src else text


def src_sentence(src):
    return f"출처 : {src} 데이터로 계산한 내용입니다."


def _split_src(text):
    lines = str(text).split("\n")
    found = [x[len(SRC_MARK):].strip() for x in lines if x.startswith(SRC_MARK)]
    return "\n".join(x for x in lines if not x.startswith(SRC_MARK)), (found[-1] if found else TIP_SRC)


def tip(text):
    """ⓘ 툴팁 아이콘 — 글은 data-tip 속성, 모양은 테마 CSS(build_theme.py `[data-tip]::after`). 줄바꿈(\n)은 툴팁 안에서 줄을 바꾼다.
    상자는 position:relative 인 가장 가까운 줄 기준으로 놓인다 — 아이콘은 그런 줄 안에 둔다. 데이터 출처는 data-src (위 TIP_SRC)."""
    text, src = _split_src(text)
    q = lambda x: esc(x).replace(chr(34), "&quot;").replace("\n", "&#10;")   # noqa: E731
    t = q(text)
    s = f' data-src="{q(src)}"' if src else ""
    label = q(text + ("\n" + src_sentence(src) if src else ""))
    return (f'<span data-tip="{t}"{s} tabindex="0" role="button" aria-label="{label}" '
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


_DASH = re.compile(r"[ \t]+—[ \t]+")


def _no_dash(t):
    """줄표 ` — ` 는 쓰지 않는다 (2026-10-18 사용자: "이 기호는 이제 안 쓸 거야", 가이드라인 2-6). 손으로 고친 고정 글 뒤의 안전망 — LLM 서술 · 기사 제목에 남은 것은 쉼표로.
    빈 값 자리 표시 `—`(앞뒤 공백 없음)는 그대로."""
    return _DASH.sub(", ", t)


# 변화 숫자 앞 부호 (2026-10-18 사용자: "늘었다 앞의 % 는 +106% 늘었다, 줄었다 앞은 −50%, 증감 색도", 가이드라인 3-3-1)
_NUM = r"(?<![+\-−±~\d.,])(\d[\d,]*(?:\.\d+)?)(%p|%)"
_UP_V = r"(?:더 )?(?:올랐|올라|오른|오르고|올렸|올린|늘었|늘어|늘고|늘린|늘며|증가|상승|앞섰|앞선|앞서|많았|많고|뛰었)"
_DN_V = r"(?:내렸|내려|내린|내리고|떨어졌|떨어진|줄었|줄어|줄고|줄인|줄며|감소|하락|뒤처졌|뒤처진|뒤처져|적었|적고|빠졌|빠진)"
_CHANGE = re.compile(_NUM + r"(\s*)(?=(" + _UP_V + r")|(" + _DN_V + r"))")   # "덜 올랐다" 는 방향이 반대라 잡지 않는다 (코드에서 앞섰다 · 뒤처졌다로)
_WHERE = re.compile(r"보다 " + _NUM + r" ?(위|아래)(?=로|에|인|이고|이다|였|,|\.|\s|\)|$)")   # "고점보다 2.0% 아래" → "고점 대비 −2.0%"


def _sign_text(t, color):
    """변화를 말하는 숫자에 + · − 를 붙이고(이미 있으면 그대로), 글자 노드면 증감 색. 크기(±) · 수준(공매도 비율 1.35%) · 범위(3~10%)는 건드리지 않는다.
    위치를 말하는 `보다 n% 위 · 아래` 는 이중 부정이 되지 않게 `대비 +n% · −n%` 로 바꾼다."""
    def paint(sign, num, unit):
        s = f"{sign}{num}{unit}"
        return f'<span style="color:{UP if sign == "+" else DOWN};white-space:nowrap;">{s}</span>' if color else s
    t = _WHERE.sub(lambda m: " 대비 " + paint("+" if m.group(3) == "위" else "−", m.group(1), m.group(2)), t)
    return _CHANGE.sub(lambda m: paint("+" if m.group(4) else "−", m.group(1), m.group(2)) + m.group(3), t)


# ---------------------------------------------------------------- 합니다체 (2026-10-18 사용자: "반말 문장은 -했습니다 · -입니다로, 엔비디아 · 종목 페이지 모두")
# 문장 끝 "…다" 만 바꾼다 — 끝 = 마침표 · 줄바꿈 · 글 끝 앞(괄호 덧붙임은 건너뜀). "S&P 500보다 " 같은 문장 중간 "다" 는 그대로.
_FINAL_DA = re.compile(r"([가-힣]+)다(?=(?:\([^()<>]*\))?(?:\.|\n|$|<))")
_IRREG = {"아니": "아닙니다", "다르": "다릅니다", "크": "큽니다", "빠르": "빠릅니다", "느리": "느립니다", "이르": "이릅니다", "모르": "모릅니다", "보": None, "마": None}


def _jong(ch):
    return (ord(ch) - 0xAC00) % 28 if "가" <= ch <= "힣" else -1


def _with_jong(ch, j):
    return chr(ord(ch) - _jong(ch) + j)


def _formal_word(w):
    """`…다` 앞 낱말 w → 합니다체 꼬리. None 이면 바꾸지 않는다."""
    if w.endswith("니") and len(w) >= 2 and _jong(w[-2]) == 17 or w.endswith("습니"):   # 이미 합니다체 (없습니다 · 합니다 · 입니다)
        return None
    for k, v in _IRREG.items():
        if w.endswith(k) and (len(w) == len(k) or k not in ("크", "보", "마")):
            return None if v is None else w[: -len(k)] + v
    x = w[-1]
    if w.endswith("는"):                       # 받는다 · 않는다 → 받습니다 · 않습니다
        return w[:-1] + "습니다"
    if x == "이":                              # …이다 → …입니다
        return w[:-1] + "입니다"
    j = _jong(x)
    if j == 4:                                 # ㄴ받침 현재형 : 한다 · 된다 · 만든다 → 합니다 · 됩니다 · 만듭니다
        return w[:-1] + _with_jong(x, 17) + "니다"
    if j > 0:                                  # 했다 · 있다 · 같다 · 없다 → …습니다
        return w + "습니다"
    if x == "하":                              # 비슷하다 → 비슷합니다
        return w[:-1] + "합니다"
    return w + "입니다"                        # 받침 없는 이름씨 + 다 : 회사다 · 날짜다 → 회사입니다 · 날짜입니다


def _formal_text(s):
    return _FINAL_DA.sub(lambda m: (_formal_word(m.group(1)) or m.group(1) + "다"), s)


# ---------------------------------------------------------------- 뉴스 · 중요 이슈 = 명사형 헤드라인체 (2026-10-18 사용자: "원래 이슈와 뉴스 문체는 다 로 끝나지 않았다 — 데일리 확인")
# 분류 프롬프트가 헤드라인체로 쓰게 했고, 이미 저장된 "-했다." 사실 문장은 화면에 낼 때 여기서 바꾼다(안전망). 모르는 끝말은 마침표만 뺀다.
_HEAD_WORD = {"말했다": "발언", "밝혔다": "발표", "늘었다": "증가", "줄었다": "감소", "올랐다": "상승", "내렸다": "하락", "떨어졌다": "하락",
              "넘었다": "돌파", "밑돌았다": "하회", "웃돌았다": "상회", "알려졌다": "알려짐", "밝혀졌다": "밝혀짐", "나왔다": "나옴", "받았다": "받음",
              "보였다": "보임", "있다": "있음", "없다": "없음", "않았다": "않음", "않는다": "않음", "같다": "같음", "높였다": "상향", "낮췄다": "하향",
              "올렸다": "상향", "내놓았다": "공개", "내놨다": "공개", "세웠다": "수립", "맺었다": "체결", "잡았다": "확보", "얻었다": "확보", "섰다": "진입"}
_HEAD_RULES = [(re.compile(r"할 예정이다$"), " 예정"), (re.compile(r"(?:되고|하고) 있다$"), " 중"), (re.compile(r"(?:하였|했|되었|됐|한|된)다$"), ""),
               (re.compile(r"(?:이었|였|이)다$"), ""), (re.compile(r"(?<=[가-힣])다$"), "")]


def headline(text):
    """사실 문장 → 명사형 헤드라인 (`…를 공식 출시했다.` → `…를 공식 출시`). 이미 헤드라인이면 그대로."""
    if not text:
        return text
    s = text.strip().rstrip(".").rstrip()
    for rx, rep in _HEAD_RULES[:2]:   # `할 예정이다` · `-고 있다` 가 낱말 표(있다 → 있음)보다 먼저
        if rx.search(s):
            return rx.sub(rep, s)
    last = s.rsplit(" ", 1)[-1]
    if last in _HEAD_WORD:
        return s[: len(s) - len(last)] + _HEAD_WORD[last]
    for rx, rep in _HEAD_RULES:
        if rx.search(s):
            out = rx.sub(rep, s)
            if rx.pattern == r"(?<=[가-힣])다$" and not re.search(r"[가-힣]{2,}$", out):
                break
            return out
    return s


TONE_OFF, TONE_ON = "<!--tone:off-->", "<!--tone:on-->"   # 이 사이는 문체를 바꾸지 않는다 — 뉴스 · 중요 이슈 (2026-10-18 사용자: "뉴스와 중요 이슈는 원복")


def keep_tone(html):
    """뉴스 · 중요 이슈처럼 원래 문체(사실 문장 · 요약 헤드라인)를 그대로 두는 구획을 감싼다."""
    return TONE_OFF + html + TONE_ON if html else html


def formal(html):
    """보이는 글과 툴팁 속성의 반말 문장 끝을 합니다체로 (엔비디아 리포트 · 종목 페이지 build 마지막에 한 번). style · script 안 · keep_tone 구획은 건드리지 않는다."""
    out, skip, off = [], False, False
    for part in _TAG.split(html):
        if part == TONE_OFF or part == TONE_ON:
            off = part == TONE_OFF
            continue   # 표시는 결과에 남기지 않는다
        if off:
            out.append(part)
            continue
        if part.startswith("<") and part.endswith(">"):
            low = part[:8].lower()
            if low.startswith(("<script", "<style")):
                skip = True
            elif low.startswith(("</script", "</style")):
                skip = False
            out.append(_TIP_ATTR.sub(lambda m: m.group(1) + _formal_text(m.group(2).replace("&#10;", "\n")).replace("\n", "&#10;") + m.group(3)
                                     if "&#10;" in m.group(2) else m.group(1) + _formal_text(m.group(2)) + m.group(3), part))
        else:
            out.append(part if skip else _formal_text(part))
    return "".join(out)


MINUS_W, MINUS_H = 0.38, 0.11   # 숫자 앞 빼기 — 글꼴의 굵은 − 는 길고 무거워 보여(2026-10-26 사용자) 줄을 직접 그린다: 폭 0.38 · 두께 0.11 글자 (비교 E4-c)
MINUS_BAR = (f'<span style="display:inline-block;width:{MINUS_W}em;height:{MINUS_H}em;background:currentColor;vertical-align:{0.36 - MINUS_H / 2:.3f}em;'
             'margin-right:.04em;border-radius:.03em;overflow:hidden;text-indent:2em;line-height:0;white-space:nowrap;">−</span>')   # 안의 − 는 밀어내 안 보이게 — 복사 · 화면 읽기에는 남는다
_MINUS_NUM = re.compile(r"−(?=\d)")


def _minus_bar(t):
    return _MINUS_NUM.sub(MINUS_BAR, t)


def fix_colons(html):
    """보이는 글의 ":" · "·" 는 앞뒤를 한 칸씩 띄운다 ("·" 는 2026-10-13 사용자) — "라벨 : 값" (2026-10-11 사용자: 꼭 반드시, 모든 페이지 일괄).
    글자 노드와 툴팁·제목 속성(data-tip · title · aria-label)만 고친다. style · script 안, 시각·비율(숫자:숫자), 주소(://)는 건드리지 않는다.
    각 리포트의 build_body 마지막에 한 번 건다 — LLM 서술도 같이 고쳐진다. 줄표 ` — ` 도 여기서 쉼표로 (_no_dash).
    숫자 앞 빼기(−3)는 그린 줄(MINUS_BAR)로, 툴팁 속 빼기는 엔 대시(–)로 (2026-10-26 사용자)."""
    out, skip = [], False
    for part in _TAG.split(html):
        if part.startswith("<") and part.endswith(">"):
            low = part[:8].lower()
            if low.startswith(("<script", "<style")):
                skip = True
            elif low.startswith(("</script", "</style")):
                skip = False
            out.append(_TIP_ATTR.sub(lambda m: m.group(1) + _MINUS_NUM.sub("–", _sign_text(_space_dots(_space_colons(_no_dash(m.group(2)))), False)) + m.group(3), part))   # 툴팁 글은 HTML 을 못 넣어 엔 대시로
        else:
            out.append(part if skip else _minus_bar(_sign_text(_space_dots(_space_colons(_no_dash(part))), True)))   # 숫자 앞 − 는 그린 줄로 (MINUS_BAR)
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
    body = re.sub(r"https://cdn\.jsdelivr\.net/gh/[^\"]+?@(?:gh-pages|kr-images)/(images/(?!logos/)[^\"]+)", r"\1", body)   # 로고는 로컬 사본이 없다 — gh-pages 주소 그대로 (2026-10-25)
    # 글 아래 [목록] · TOP 줄 — 블로그 테마의 글 보기와 같은 마크업 (2026-10-18 사용자: 모든 페이지 공통). 목록 주소는 본문 [data-list-url] 이 있으면 그것
    lu = re.search(r'data-list-url="([^"]+)"', body)
    nav = (f'<p class="post-nav"><a class="post-nav-list" href="{lu.group(1) if lu else "#"}">목록</a>'
           '<button aria-label="맨 위로" class="post-nav-top" type="button">TOP<svg aria-hidden="true" fill="none" height="22" stroke="currentColor" stroke-linecap="round" '
           'stroke-linejoin="round" stroke-width="1.6" viewBox="0 0 22 22" width="22"><circle cx="11" cy="11" r="10"/><path d="M11 15.5V7M7.5 10.5 11 7l3.5 3.5"/></svg></button></p>')
    # 블로거 공유 위젯 흉내 — 실제 블로그 목록(링크 · Facebook · X · Pinterest · 이메일 · 다른 앱)을 그대로 두고 테마 JS 가 정리하는지 본다 (2026-10-23)
    share = ('<div class="post-share-buttons post-share-buttons-bottom"><div class="byline post-share-buttons goog-inline-block"><div class="sharing">'
             '<button class="sharing-button touch-icon-button"></button><div class="share-buttons-container"><ul class="share-buttons hidden">'
             + "".join(f'<li><span class="sharing-platform-button"><span class="platform-sharing-text">{n}</span></span></li>'
                       for n in ("링크 가져오기", "Facebook", "X", "Pinterest", "이메일", "다른 앱")) + '</ul></div></div></div></div>')
    page = ('<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)} — 목업</title><style>{css.group(1)}</style></head>'
            '<body class="item-view no-dashboard"><main class="main-content"><div class="post-shell"><article class="post-outer-container"><div class="post">'
            f'<h3 class="post-title">{esc(title)}</h3><div class="post-body entry-content">{body}</div>{share}</div></article>{nav}</div></main>'
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


PILL_PAIR_GAP = 2   # 라벨끼리 사이 — 어디서나 2px (2026-10-26 사용자: "라벨끼리는 어디서나 2px, 라벨과 글자 사이는 5px"). 옛: 엔비디아 3 · 공용 카드 띄어쓰기(약 5) · 트럼프 약 14
_PILL_MARGIN = re.compile(r"margin:0(?: [\d.]+(?:px)?){1,3};")   # 끝의 0 은 px 없이 오기도 한다 (엔비디아 margin:0 3px 0 0)
_PILL_SPACE = re.compile(r">\s+<")


def pill_row(labels_html, outer=0):
    """라벨 여럿을 한 묶음으로 — 라벨끼리 PILL_PAIR_GAP, 묶음 바깥 좌우 outer px(글자 사이에 놓이면 PILL_GAP).
    라벨마다 붙은 바깥 여백 · 사이 띄어쓰기는 지운다(pill · 엔비디아 _pill · 링크 라벨 모두)."""
    inner = _PILL_SPACE.sub("><", _PILL_MARGIN.sub("margin:0;", labels_html or ""))
    return (f'<span style="display:inline-flex;align-items:center;gap:{PILL_PAIR_GAP}px;margin:0 {outer}px;vertical-align:middle;white-space:nowrap;">{inner}</span>'
            if inner else "")


LOGO_BASE = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/logos/"   # 우리 gh-pages 사본 (핫링크 아님)
_LOGO_META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref", "ticker_logos.json")   # fetch_ticker_logos.py 가 만든다
_logos = None


def _logo_files():
    global _logos
    if _logos is None:
        try:
            import json
            with open(_LOGO_META, encoding="utf-8") as f:
                _logos = json.load(f).get("logos") or {}
        except (OSError, ValueError):
            _logos = {}
    return _logos


def ticker_logo(sym, size=20):
    """종목 이름 앞 둥근 로고 (2026-10-13 사용자: "각각의 종목명에도 티커 아이콘").
    2026-10-21: 제3자 핫링크(financialmodelingprep)를 빼고 티커 두 글자 배지로 바꿨다 (D4-6).
    2026-10-22 사용자: 로고는 신뢰도 — 우리 gh-pages 에 복사한 로고(ref/ticker_logos.json 에 있는 종목)만 쓴다. 식별 용도로
    원래 모양 그대로 작게. 목록에 없는 종목(ETF · 삭제 요청)은 예전처럼 두 글자 배지 (운영지침 4-6)."""
    sym = str(sym or "").strip().upper()
    if not sym or not sym.replace("-", "").replace(".", "").isalnum():
        return ""
    rec = _logo_files().get(sym)
    if rec:
        return (f'<img src="{LOGO_BASE}{esc(rec["file"])}" alt="" width="{size}" height="{size}" loading="lazy" '
                f'style="display:inline-block;width:{size}px;height:{size}px;border-radius:50%;vertical-align:-4px;margin-right:6px;'
                f'background:#F1F5F9;object-fit:cover;">')
    txt = sym.replace("-", "").replace(".", "")[:2]
    fs = max(8, int(size * 0.42))
    return (f'<span aria-hidden="true" style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;border-radius:50%;'
            f'vertical-align:-4px;margin-right:6px;background:#E2E8F0;color:#334155;font-size:{fs}px;font-weight:700;text-align:center;'
            f'letter-spacing:0;white-space:nowrap;overflow:hidden;">{txt}</span>')


def link_icon(url, label):
    if not url:
        return ""
    return (f' <a href="{esc(url)}" title="{esc(label)}" aria-label="{esc(label)}" target="_blank" rel="noopener" '
            f'style="color:#9AA4B2;text-decoration:none;white-space:nowrap;">{LINK_ICON}</a>')


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
                    f'<span style="font-size:{NAME};font-weight:400;color:#111;">{esc(k)}</span> : <b style="color:#111;font-size:18px;">{v}</b></span>'   # 이름 보통 굵기 · 숫자 18px (2026-10-14 사用자)   # `기사 : 29` (2026-10-13 사용자)
                    for i, (k, v) in enumerate(items))
    return (f'<div style="display:flex;align-items:center;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:{10 - VP}px 4px;'
            f'margin:0 0 8px;font-size:{SMALL};line-height:{LH_CARD};">{cells}</div>')


def bullets(texts):
    """18px 글 목록 — 3px 점, 행간 33 (2026-10-12 사용자: 점은 18px 3px · 14px 2px 두 가지만). 서술 문장의 증감도 같은 색 규칙."""
    return dot_ul(dot_li(tint(esc(t)), size=3, lh=LH_BODY, margin=LI_MARGIN) for t in texts)


LI_MARGIN = "12px 0"   # 본문 글머리표 사이 6 → 12 (글머리표 사이 +6px, 2026-10-12 사용자)


def dot_ul(items_html):
    """점 글머리표 목록 (dot_li 묶음) — 기본 원형 글머리표는 쓰지 않는다."""
    return "<ul style='margin:0 0 8px;padding:0 0 0 14px;list-style:none;'>" + "".join(items_html) + "</ul>"   # 카드 밖 글머리표는 왼쪽 14px 들여쓰기 (2026-10-14 사용자: 블로그 모든 곳)


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


CHG_SIZE = "17px"   # 흰 카드 오른쪽 증감 숫자 19 → 18 → 17 (2026-10-13 사용자: 강조 카드 제외)
_ARROW_SPAN = re.compile(r'(<span style="color:#[0-9A-Fa-f]{3,6};font-weight:700;white-space:nowrap;)(">[▲▼–])')


def small_chg(value_html):
    """값 칸의 증감(arrow) 글자만 CHG_SIZE 로."""
    return _ARROW_SPAN.sub(lambda m: f"{m.group(1)}font-size:{CHG_SIZE};{m.group(2)}", value_html)


def crow(name_html, value_html, sub="", first=False, left=None, short=False, nowrap=False, sub_below=False, sub_block=False, name_size=None, tip_text=None):
    """C 카드 한 줄: 왼쪽 구분명 │ 보조 줄, 오른쪽 값. name_html 은 이스케이프된 HTML.
    left = 왼쪽 칸 % (카드별 예외, 가이드라인 2-1 — 2026-10-12 사용자). nowrap = 값을 한 줄로.
    sub_below = 보조 줄을 구분명 옆이 아니라 줄 아래 카드 폭 전체 한 줄로 (옆에 들어가지 않을 때, 2026-10-12 사용자).
    sub_block = 보조 줄을 구분명 아래 줄로 (왼쪽 칸 안) — 종목 아래 거래량 (2026-10-12 사용자)."""
    if isinstance(left, str):   # 호출부가 left="65%" 로 넘기는 곳이 있다 — 숫자로 (2026-10-14: 트럼프 발언 카드에서 fits_inline 이 '65%' / 100 으로 죽던 것)
        left = int(left.rstrip("%"))
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
            f'<span style="font-weight:700;color:#111;font-size:{EMPH_Q};line-height:{LH_EMPH_Q};">{head_html}</span>'
            + (f'<span style="display:inline-flex;align-items:center;font-weight:700;white-space:nowrap;font-size:{EMPH_Q};line-height:{LH_EMPH_Q};{"margin-left:auto;" if chev else ""}">{right_html}</span>' if right_html else "")   # 라벨 · 숫자 세로 가운데 (2026-10-13 사용자)
            + ((("" if right_html else '<span style="margin-left:auto;"></span>') + fold_btn(lighten(bg), bd)) if chev else "") + "</span>")   # chev: 맨 오른쪽 공식 접기 버튼, 바탕은 카드 색 20% 밝게 (2026-10-13 사용자)
    sub = f'<div style="font-size:{TINY};line-height:{LH_TINY};color:#374151;margin-top:2px;{"text-align:center;" if center else ""}">{sub_html}</div>' if sub_html else ""   # center: 종합 상태 카드 가운데 (2026-10-13 사용자)
    lis = "".join(dot_li((f"<b>{esc(k)}</b> : " if k else "") + esc(v), size=2, color="#374151", margin="8px 0") for k, v in items)
    body = (f'<div style="margin-top:{14 - VP_EMPH + 3}px;padding-top:{14 - VP}px;border-top:1px solid {bd};font-size:{TINY};line-height:{LH_TINY};">'   # 제목 ~ 구분선 14 · 구분선 ~ 글 14 (보이는 여백, 2026-10-12 사용자: 4 → 14)
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
    h = "".join(c * 2 for c in h) if len(h) == 3 else h   # #fff 같은 3자리도 (등락 0% 종목의 바탕 #fff 에서 죽던 것, 2026-10-26)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{round(c + (255 - c) * amt):02X}" for c in (r, g, b))


def darken(hex_color, amt=0.05):
    """검정 쪽으로 amt 만큼 섞은 색 (2026-10-26 사용자: 질문 카드 줄 구분선 · 막대 눈금선 2% 진하게 — 처음 5% 는 취소)."""
    h = hex_color.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h   # #fff 같은 3자리도 (등락 0% 종목의 바탕 #fff 에서 죽던 것, 2026-10-26)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{round(c * (1 - amt)):02X}" for c in (r, g, b))


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
    """펼침 버튼 (가이드라인 2-1 H 카드 버튼) — 눌러야 inner_html 이 보인다. details data-acc: 테마 CSS가 화살표를 돌리고 홈 카드는 건너뛴다.
    data-fold · data-label: 테마 JS(details[data-fold])가 펼친 내용을 버튼 위로 옮기고 글자를 `접기`로 바꾼다 — 펼친 뒤에도 버튼이 맨 아래 (2026-10-21 사용자:
    "더 보기를 누르면 펼쳐진 것 아래에 버튼이 있어야 한다"). fold_card 와 같은 동작. JS 없으면 그냥 details."""
    return (f'<details data-acc="1" data-fold="1" data-label="{esc(label)}" style="margin:0 0 8px;"><summary style="{FOLD_BTN}"><span>{esc(label)}</span> {ACC_CHEV}</summary>'
            f'<div style="margin-top:8px;margin-bottom:8px;">{inner_html}</div></details>')


def state_fold(card_html, inner_html):
    """상태 카드를 버튼으로 — 누르면 아래 inner_html(카드)이 펼쳐진다, 기본 닫힘 (2026-10-13 사용자: "점수 … 우측 끝에 펼침아이콘, 6개 정보를 펼쳤을 때").
    card_html 은 state_card(..., chev=True). details data-acc: 테마 CSS가 열리면 화살표를 위로 돌리고 홈 카드는 건너뛴다."""
    card = card_html.replace("margin:0 0 8px;", "margin:0;", 1)   # 카드 아래 8px 은 details 가 갖는다
    return (f'<details data-acc="1" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;display:block;">{card}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


SUB_DOT = 4   # 소제목 앞 점 (2026-10-13 사용자: 2 → 3 → 4)
SUB_TOP_EXTRA = 15   # 소제목 위 여백 +15 → 29 (2026-10-13 사용자)


RULE_GAP = SEP_GAP + 5   # 카드 없이 가로 구분선만 둔 목록 — 선 위아래 보이는 27 (2026-10-13 사용자: "기존 구분선 여백 상하 여백에 5픽셀씩 더")


def item_rules(items_html, sub=False, indent=0):
    """기사 목록 — 카드 없이 기사 사이 가로 구분선 (2026-10-13 사용자: "뉴스는 강조 뉴스 카드를 제외하고 가로 구분선으로 뉴스 영역을 구분").
    18px · 행간 34. 첫 기사 위는 구획 제목 밑줄이 대신한다. 항목은 li — 홈 카드가 글머리표로 읽는다. 구분선은 box-shadow (홈 카드는 border-top 요소를 건너뛴다)."""
    bottom = RULE_GAP - (VP if sub else NEWS_VP)
    lis = "".join(f'<li style="margin:0;padding:{(RULE_GAP - NEWS_VP) if i else 2}px {indent}px {bottom}px;line-height:{LH_BODY};{"box-shadow:inset 0 1px 0 #E2E8F0;" if i else ""}">{h}</li>'
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


# 범례 막대 — 지금 기준 모양 (가이드라인 1절 4-1 9 · 10-7: 엔비디아 `_legend_bar` 애널리스트 · 뉴스 막대와 같은 값). 위 bar() 는 2026-10-13 이전 모양이라
# 새 막대는 이것을 쓴다 (2026-10-23 사용자: "다른 막대 그래프와 같은 규칙인지 — 범례 · 타이틀 · 막대 높이 · 막대 안 숫자 크기가 다르다")
LEGEND_BAR_H, LEGEND_BAR_NUM, LEGEND_BAR_PAD = 30, "17px", 5   # 막대 높이 30 · 막대 안 숫자 17 · 위아래 바깥 +5 (2026-10-14 사용자)
LEGEND_CHIP, LEGEND_INDENT = 9, 10   # 범례 색 사각형 9px · 범례 왼쪽 들여쓰기 10px (2026-10-17 사용자)


def legend_bar(title, segs, aside="", legend_top=False):
    """제목(왼쪽, 16px 검정 굵게) · 막대 · 막대 색과 같은 범례 칩 `■ 긍정 47% ■ 부정 37%`. segs = [(이름, 개수, 배경, 글자)], 0건은 뺀다.
    aside: 제목 줄 오른쪽 글(14px 안내 회색) — 기준 규칙은 비워 두지만, 미디어 데일리는 `영상 n개 · 방송 n곳` (2026-10-23 사용자).
    legend_top=True: 제목을 쓰지 않고 범례를 막대 위 줄 왼쪽에, aside 를 같은 줄 오른쪽에 둔다 (미디어 데일리, 2026-10-23 사용자)."""
    segs = [x for x in segs if x[1]]
    total = sum(x[1] for x in segs)
    if not total:
        return ""
    title_html = f'<b style="color:#111;font-weight:700;">{esc(title)}</b>'
    if aside:
        title_html += f'<span style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};white-space:nowrap;">{aside}</span>'
    head = f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:{BAR_LABEL};line-height:{LH_CARD};margin:0 0 3px;">{title_html}</span>'
    body = "".join(f'<span style="display:block;width:{c / total * 100:.1f}%;background:{bg};color:{fg};font-size:{LEGEND_BAR_NUM};font-weight:700;'
                   f'text-align:center;line-height:{LEGEND_BAR_H}px;overflow:hidden;white-space:nowrap;">{f"{c / total * 100:.0f}%" if c / total >= 0.08 else ""}</span>' for _, c, bg, fg in segs)
    bar_html = (f'<span style="display:flex;width:100%;height:{LEGEND_BAR_H}px;border-radius:6px;overflow:hidden;background:#F1F5F9;'
                f'margin:{LEGEND_BAR_PAD}px 0 {3 + LEGEND_BAR_PAD}px;">{body}</span>')
    legend = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 0 0;white-space:nowrap;">'
                     f'<span style="display:inline-block;width:{LEGEND_CHIP}px;height:{LEGEND_CHIP}px;border-radius:2px;background:{bg};"></span>{esc(nm)} {c / total * 100:.0f}%</span>'
                     for nm, c, bg, _ in segs)
    if legend_top:
        aside_html = (f'<span style="margin-left:auto;font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};white-space:nowrap;">{aside}</span>' if aside else "")
        top = (f'<span style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0 8px;box-sizing:border-box;padding-left:{LEGEND_INDENT}px;'
               f'font-size:{MICRO};line-height:{LH_CARD};color:{NOTE};margin:0 0 3px;"><span>{legend}</span>{aside_html}</span>')
        return top + bar_html.replace(f"margin:{LEGEND_BAR_PAD}px 0 {3 + LEGEND_BAR_PAD}px;", f"margin:0 0 {3 + LEGEND_BAR_PAD}px;", 1)
    return head + bar_html + (f'<span style="display:block;box-sizing:border-box;padding-left:{LEGEND_INDENT}px;font-size:{MICRO};line-height:{LH_CARD};color:{NOTE};margin:0 0 10px;">{legend}</span>')


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


NEWS_SUM = "display:block;color:#333;font-size:16px;line-height:26px;font-weight:400;margin-top:4px;word-break:keep-all;"   # 뉴스 요약 줄 = 홈 주요 뉴스 기사 소개(.news-sum)와 같게 (2026-10-26 사용자: 14px 로 더 작았다)


def news_item(headline_html, url=None, detail="", subs=(), labels="", meta=(), link_attrs=""):
    """공용 뉴스 카드 한 줄 (doc/기획/뉴스-형식-통일.md 2절, 기준 = 인물 발언 카드, 2026-10-25 사용자: 뉴스 형식 통일).
        헤드라인(굵게, 원문 링크) / 요약 한 줄(16px #333 = 홈 기사 소개, 없으면 생략) / 보조 줄들(subs) / [라벨] [라벨]  회색 메타(시각 · 매체)
    headline_html = 이스케이프한 헤드라인(명사형). detail = 요약 글(이스케이프 전 — 뉴스 문체로 바꾼다). labels = 알약 HTML 묶음. meta = 글자 목록.
    link_attrs = a 태그에 더할 속성(title · data-trhelp 등). 헤드라인 · 요약은 합니다체로 바꾸지 않는다(keep_tone)."""
    head = (f'<a href="{esc(url)}" target="_blank" rel="noopener"{link_attrs} style="color:#111;font-weight:700;text-decoration:none;">{headline_html}</a>'
            if url else f'<span style="color:#111;font-weight:700;">{headline_html}</span>')
    out = keep_tone(head)
    if detail:
        out += keep_tone(f'<span style="{NEWS_SUM}">{esc(headline(detail))}</span>')
    out += "".join(subs)
    meta = [m for m in meta if m]
    return (out + f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 0;line-height:1;">'
            + pill_row(labels)   # 라벨끼리 2px (PILL_PAIR_GAP)
            + (f'<span style="color:{SUB};font-size:{TINY};line-height:{LH_TINY};">{esc(" · ".join(meta))}</span>' if meta else "") + "</span>")


def footer(data_line, disclaimer_line, indent=True):
    """출처 · 면책 줄. indent=False: 들여쓰기 없이 위 목록과 같은 왼쪽 선 (데일리 위험 탭, 2026-10-13 사용자)."""
    return (f'<div data-footer="1" style="margin-top:3px;padding-top:2px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};{GUIDE_IND if indent else ""}">'
            f"{INFO_ICON}{data_line}<br>{INFO_ICON}{disclaimer_line}</div>")


# ── 종목 링크 (2026-10-25 사용자: "블로그의 모든 종목은 우리 종목 상세 페이지로 — 페이지가 있으면 링크, 없으면 그대로") ──
# 상세 페이지 목록 = 홈 종목 카드가 쓰는 gh-pages stocks.json 의 page 플래그 (stock-radar/home_feed.py · publish_pages 의 pages_live.json).
# 없는 페이지로는 링크하지 않는다. 목록을 못 읽으면 링크 없이(안전).
STOCK_LINK = "#7C3AED"   # 기사 속 종목 링크 — 보라색 · 굵게 아님 (2026-10-25 사용자: 파란색 → 보라색, 하락 파랑과 겹치지 않게)
STOCK_BLOG = "https://alpha-scope.blogspot.com"
_STOCKS_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/stocks.json"
_stock_pages = None


def stock_pages():
    """{티커: 상세 페이지 주소} — 페이지가 발행된 종목만. 환경변수 STOCK_PAGES_JSON(파일)이 있으면 그것, 없으면 gh-pages 의 stocks.json."""
    global _stock_pages
    if _stock_pages is not None:
        return _stock_pages
    data = None
    try:
        path = os.environ.get("STOCK_PAGES_JSON")
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            import urllib.request
            with urllib.request.urlopen(urllib.request.Request(_STOCKS_URL, headers={"User-Agent": "alphascope"}), timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[design_kit] 종목 페이지 목록 없음 — 링크 없이: {str(e)[:80]}")
    _stock_pages = {x["s"]: f'{STOCK_BLOG}/p/{x["slug"]}.html' for x in ((data or {}).get("stocks") or []) if x.get("page") and x.get("slug")}
    return _stock_pages


def stock_href(sym):
    return stock_pages().get(str(sym or "").strip().upper())


def stock_link(sym, text_html, color=True):
    """종목 글자 → 상세 페이지 링크. color=True: 기사 속 종목(파란색 · 보통 굵기), False: 글자 색 그대로(카드 · 목록 줄).
    페이지가 없으면 text_html 그대로 (기사 속은 검정)."""
    href = stock_href(sym)
    if not href:
        return text_html
    style = f"color:{STOCK_LINK};font-weight:400;text-decoration:none;" if color else "color:inherit;text-decoration:none;"
    return f'<a href="{esc(href)}" data-stock="{esc(sym)}" style="{style}">{text_html}</a>'


def stock_row_link(row_html, sym):
    """카드 한 줄(crow 등) 전체를 그 종목 상세 페이지로 — 색은 그대로, 테마의 줄 링크([data-row-link] + data-href, 가이드라인 10-9)."""
    href = stock_href(sym)
    if not href or not row_html.lstrip().startswith("<span "):
        return row_html
    return row_html.replace("<span ", f'<span data-row-link="1" data-href="{esc(href)}" ', 1)
