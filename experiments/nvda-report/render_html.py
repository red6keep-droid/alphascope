"""nvda_analysis.json (+ narrative.json) → Blogger 본문 HTML (기획서 10절). 섹션·라벨은 render_report(MD)와 같고 시각 규칙은 trump-trend와 같다
— 18px 본문, 회색 밑줄 H2, 상승 빨강·하락 파랑, 좁은 화면에서 표만 가로 스크롤. 숫자는 파이썬이 그리고 문장은 narrative.json에서만.

출력:
    output/nvda_report_body.html   Blogger 본문
    output/nvda_report.html        브라우저 미리보기
    output/title.txt               게시 제목
"""

import datetime
import html as html_mod
import json
import os
import re
import sys

import config
import render_report as rr
import report_title
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as _dk  # noqa: E402  — 공통 마무리 처리 (fix_colons)

# 구획 제목 (디자인-가이드라인.md 2절): 아래 여백 14px. 구분선은 바로 아래가 글(목록·문장)일 때만 — 카드·표·그림이 오면 그 테두리가 경계라 선을 긋지 않는다
H2 = f"color:#111;font-size:{_dk.H2_SIZE};font-weight:700;line-height:{_dk.LH_H2};margin:28px 0 11px;padding:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;"   # 옆 요약이 폰에서는 제목 아래 줄로 내려온다
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:6px;"   # 구분선 위 여백 8 → 6 (20% 줄임, 2026-10-11)
_NO_LINE_START = re.compile(r'^\s*(<div style="(?:overflow-x:auto;|background:)|<div data-cards|<img\b)')   # 표 래퍼 · 카드 · 카드 묶음 · 그림
UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
SUB = "#7A7A7A"   # 카드 보조 글(보조 줄·· 현재가·/ 100·날짜) — #999 보다 20% 진하게 (2026-10-11 사용자). "—" 자리 표시는 MUTED 그대로
# 글자 크기 체계 (디자인-가이드라인.md 3절): 본문은 바깥 div의 18px 하나 — 강조한다고 키우지 않는다. 라벨·날짜는 한 단계 작게(16px), 안내 글·범례·면책은 두 단계 작게(14px)
SMALL, TINY = "19px", "14px"   # 본문 19 (2026-10-13 사용자)   # 안내 글(14px)을 빼고 모두 18px (2026-10-12 사용자)
LH_CARD, LH_TINY = _dk.LH_CARD, _dk.LH_TINY   # 행간은 px 정수만 (2026-10-12 사용자)
MICRO = "14px"   # 카드 구분명 안 괄호 부분 — 카드 글자(16px)보다 한 단계 작게, 볼드 없음 (2026-10-11 사용자: 안내 글 빼고 14 → 16)
# 강조 카드 (가이드라인 2절): 크기 대신 연한 배경 카드로 강조. 라벨 pill 색
CARD = f"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:{14 - _dk.VP}px 14px;line-height:{LH_CARD};"   # 보이는 위아래 14 (2026-10-12)           # 기본 카드 (오늘 한 줄)
CARD_EMPH = f"background:#FFF7ED;border:1px solid #FFEDD5;border-radius:10px;padding:{12 - _dk.VP}px 14px;line-height:{LH_CARD};"       # (옛) 강조 카드
# 강조 이벤트 카드는 방향 테마 (2026-10-11 사용자): 긍정 오렌지 · 부정 파랑 · 중립 회색 · 불확실 노랑
CARD_DIR = {"positive": ("#FFF7ED", "#FED7AA"), "negative": ("#EFF6FF", "#BFDBFE"),
            "neutral": ("#F8FAFC", "#E2E8F0"), "uncertain": ("#FFFBEB", "#FDE68A")}
# 라벨 (가이드라인 5절, 2026-10-11 사용자): 외곽선 박스, 모서리 4px, 볼드 없음, 14px. (테두리색, 글자색)
PILL = {"area": ("#CBD5E1", "#334155"), "positive": ("#FCA5A5", "#B91C1C"), "negative": ("#93C5FD", "#1D4ED8"),
        "uncertain": ("#FDBA74", "#C2410C"), "neutral": ("#CBD5E1", "#64748B")}
PILL_BG = {"positive": "#FEF2F2", "negative": "#EFF6FF"}   # 연한 배경은 긍정·부정에만 (2026-10-11 사용자). 나머지는 흰 배경
DIR_COLOR = {"positive": UP, "negative": DOWN, "uncertain": WARN, "neutral": MUTED}
PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""


_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


_FQ = re.compile(r"FY(\d{4})Q([1-4])")
_FQ_MONTHS = {1: (2, 4), 2: (5, 7), 3: (8, 10), 4: (11, 1)}   # NVIDIA 회계연도: FY = 전년 2월 ~ 그해 1월


def _fq(t):
    """FY2027Q2 → 2026년 5~7월 (엔비디아 회계 분기를 달력 월로, 2026-10-11 사용자: 쉬운 정보로)."""
    def one(m):
        fy, q = int(m.group(1)), int(m.group(2))
        a, b = _FQ_MONTHS[q]
        y = fy - 1
        return f"{y}년 {a}~{b}월" if q < 4 else f"{y}년 11월~{fy}년 1월"
    if not t:
        return t
    t = re.sub(r"(FY\d{4}Q[1-4]) 발표\)", r"\1 실적과 함께 발표)", str(t))   # "2026년 5~7월 발표"로 읽히지 않게
    return _FQ.sub(one, t)


def _d(t):
    """날짜 표기 2026.10.9 (점, 앞자리 0 없음 — 디자인-가이드라인 3-3, 2026-10-11 사용자). 문자열 안의 YYYY-MM-DD 를 모두 바꾼다."""
    if not t:
        return t
    return _ISO_DAY.sub(lambda m: f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}", str(t))


_PAREN = re.compile(r"\s*(\([^()]*\))")


def _paren(name_html):
    """카드 구분명의 (…) 부분을 한 단계 작게(12px)·보통 굵기로. 이미 이스케이프된 HTML 에 적용한다."""
    return _PAREN.sub(lambda m: f' <span style="font-size:{MICRO};font-weight:400;">{m.group(1)}</span>', name_html)


def _esc(t):
    return html_mod.escape(str(t), quote=False)


def _signed(v, digits=2, suffix="%"):
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    return f'<span style="color:{UP if v >= 0 else DOWN};font-weight:bold;">{v:+.{digits}f}{suffix}</span>'


WRAP_AT = 24   # 이보다 긴 글자 칸만 줄바꿈 허용 (어절 단위) — 나머지는 한 줄로


def _cell(c):
    """표 칸 — 모바일에서 글자를 좁은 칸에 밀어 넣지 않는다 (2026-10-11 사용자).

    짧은 칸은 nowrap: 열이 좁아지면 표가 옆으로 넘쳐 가로 스크롤이 된다(테마 .post-body table이 overflow-x:auto).
    긴 문장 칸만 넓이를 확보해(min-width) 어절 단위로만 줄을 바꾼다. 테마의 overflow-wrap:anywhere(글자 중간 끊김)는 칸에서 끈다.
    """
    text = re.sub(r"<[^>]+>", "", str(c))
    if len(text) > WRAP_AT:
        return f'<td style="border:1px solid #ddd;padding:6px 8px;min-width:18em;word-break:keep-all;overflow-wrap:normal;">{c}</td>'
    return f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{c}</td>'


def _table(headers, rows):
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;">{_esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(_cell(c) for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:0 0 8px;">'
            f"<tr>{th}</tr>{body}</table></div>")


def _h2(t, line=True, summary="", tab=None):
    """구획 제목. summary 가 있으면 제목 오른쪽에 요약(14px 회색, data-summary — 홈 카드는 제목 글자에서 이를 뺀다).
    tab = 들어갈 탭 이름(data-tab) — 테마 JS가 읽는다 (가이드라인 11절, 2026-10-11 세 리포트 공통)."""
    sm = (f' <span data-summary="1" style="font-size:{TINY};line-height:{LH_TINY};font-weight:400;color:{NOTE};white-space:normal;flex:1 1 220px;">{INFO_ICON}{summary}</span>'
          if summary else "")
    tb = f' data-tab="{_esc(tab)}"' if tab else ""
    return f'<h2{tb} style="{H2}{H2_LINE if line else ""}">{_esc(t)}{sm}</h2>'


def _section(title, html, summary="", line=None, tab=None):
    """제목(+옆 요약) + 내용. 내용의 첫 요소가 카드·표·그림이면 제목 밑 구분선을 뺀다 (2026-10-11 사용자 규칙).

    안내글 대신 제목 옆 요약을 쓴다 (2026-10-11 사용자: 안내글은 삭제하고 타이틀 옆에 요약)."""
    if line is None:
        line = not _NO_LINE_START.match(html or "")
    return _h2(title, line=line, summary=summary, tab=tab) + (html or "")


INFO_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;margin-right:4px;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>')
QUESTION_ICON = ('<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" style="display:block;" fill="none">'   # 원 선 1.2 × 20/16 = 보이는 1.5px (2026-10-13)
                 '<circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>'
                 '<text x="8" y="11.6" text-anchor="middle" fill="currentColor" stroke="none" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="700">?</text></svg>')   # ? 는 또렷한 글꼴의 글자 (2026-10-13 사용자: "다른 폰트로 명확하게")
NOTE = "#6B7280"   # 안내 줄 회색 (테마 gray-500)


def _note(t):
    """구획 안내 줄 — 내용 아래, 본문보다 한 단계 작게(15px), 회색, 안내 아이콘 (디자인-가이드라인.md 2절).

    제목에 넣던 조건·범위("7일 이내 · 법원 일정 30일", "15건")를 여기로 옮긴다. 홈 카드는 border-top 요소를 건너뛰므로 카드에 섞이지 않는다.
    """
    return f'<div style="margin:3px 0 1px;padding-top:2px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};{_dk.GUIDE_IND}">{INFO_ICON}{_esc(t)}</div>'


_LABEL = re.compile(r"^([^:：]{1,24}?)\s*:\s+(.+)$", re.S)


def _tint(html_text):
    """이스케이프된 글 안의 증감에 색 — 증가 빨강 · 감소 파랑 (가이드라인 3-3, 2026-10-11 사용자).
    앞에 종목 이름(이름(티커) 또는 'n위 이름')이 붙어 있으면 이름까지 한 덩어리로 칠한다: 산업재(XLI) -0.25% 전체 파랑. 범위(-0.63 ~ +0.63%)는 칠하지 않는다."""
    return _dk.tint(html_text)   # 공통 규칙: 짧은 덩어리는 구분명·종목명까지 통째로 (2026-10-12 사용자: 모든 페이지)


def _label_text(text):
    """"라벨: 내용" 글 → **라벨** : 내용(증감 색). 라벨이 없으면 내용만 (가이드라인 3-3)."""
    m = _LABEL.match(str(text))
    if m:
        return f"<b>{_esc(m.group(1))}</b> : {_tint(_esc(m.group(2)))}"
    return _tint(_esc(text))


def _dot_li(inner_html, size=3, color="#111", lh=None, margin="9px 0"):
    """점 글머리표 한 줄 — 18px 글 3px 점 · 14px 안내 글 2px 점, 두 가지뿐 (2026-10-12 사용자). design_kit.dot_li 와 같다."""
    return _dk.dot_li(inner_html, size=size, color=color, lh=lh, margin=margin)


def _guide(title, body, line=True):
    """제목이 있는 안내 글 (가이드라인 3-3, 2026-10-11 사용자) — design_kit.guide 와 같은 규칙.
    짧으면 한 줄 "ⓘ **제목**: 내용", 길거나 항목이 여럿이면 "ⓘ **제목**" 다음 줄부터 글머리표 "이름 = 내용"."""
    top = ("margin:3px 0 1px;padding-top:2px;border-top:1px solid #f3f3f3;" if line else "margin:1px 0 0;") + _dk.GUIDE_IND   # 여백 40% 줄임 (2026-10-11 사용자)   # 카드 밖 안내 20px 들여쓰기 (2026-10-11 사용자)
    head = f'{INFO_ICON}<b style="color:#4B5563;">{_esc(title)}</b>'
    if isinstance(body, str) and len(body) <= 70:
        return f'<div data-guide="1" style="{top}font-size:{TINY};line-height:{LH_TINY};color:{NOTE};">{head} : {_esc(body)}</div>'   # data-guide: 홈 카드가 건너뛴다 (2026-10-12)
    items = [body] if isinstance(body, str) else body
    lis = "".join(_dot_li(_tint(_esc(it[0]) + ' = ' + _esc(it[1])) if isinstance(it, tuple) else _tint(_esc(it)), size=2, color=NOTE, margin="8px 0") for it in items)   # 14px 안내 → 2px 점
    return f'<div data-guide="1" style="{top}font-size:{TINY};line-height:{LH_TINY};color:{NOTE};">{head}<ul style="margin:-4px 0 -6px 2px;padding:0;list-style:none;">{lis}</ul></div>'


def _muted(t):
    """짧은 안내 글 (기준 거래일, 빈 구획 안내 등) — 안내 글에는 아이콘을 꼭 붙인다 (2026-10-11 사용자)."""
    return f'<div style="color:{NOTE};font-size:{TINY};line-height:{LH_TINY};margin:2px 0;{_dk.GUIDE_IND}">{INFO_ICON}{_esc(t)}</div>'


NEW_PILL = ('<span style="display:inline-block;background:#B91C1C;color:#fff;border-radius:3px;padding:1px 4px 0;font-size:10px;font-weight:700;'
            'line-height:13px;vertical-align:middle;margin-left:4px;">N</span>')   # 안내 아이콘(14px)만 한 크기, 흰 글자·진한 바탕 (2026-10-11 사용자)


def _new(a, key):
    """"N" 라벨 — 전 리포트와 값이 달라진 가끔 바뀌는 칸에 그날만 (가이드라인 5절, 2026-10-11 사용자)."""
    return (" " + NEW_PILL) if key in (a.get("new_flags") or ()) else ""


def _pill(text, kind):
    bd, fg = PILL.get(kind, PILL["neutral"])
    bg = PILL_BG.get(kind, "#fff")
    # 박스는 글자에 맞게: line-height 1 + 위아래 같은 안쪽 여백 → 글자가 위로 쏠리지 않는다. 본문 줄 가운데에 맞춤(middle)
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {bd};border-radius:4px;padding:3px 5px 2px;margin:0 {_dk.PILL_GAP}px;{_dk.PILL_MID}'
            f'font-size:{_dk.PILL_SIZE};font-weight:400;line-height:1;white-space:nowrap;vertical-align:middle;">{_esc(text)}</span>')   # 라벨 14px, 어디서나 (2026-10-12 사용자)


def _tag(area, direction):
    """영역·방향 라벨 — 알약 두 개, 본문보다 한 단계 작게 (가이드라인 5절 라벨)."""
    return _pill(rr.AREA_KO.get(area, area), "area") + " " + _pill(rr.DIR_KO.get(direction, direction), direction)


# ── 섹션 ────────────────────────────────────────────────────────────────

def _notice(a):
    ds = a["data_status"]
    parts = []
    if ds.get("test_mode"):
        parts.append(f"{INFO_ICON}<b>테스트 운영 중</b> — {_esc(config.TEST_NOTICE)}")
    if ds.get("items_pending"):
        parts.append(f"{INFO_ICON}기사 {ds['items_pending']}건이 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다 (다음 실행에서 이어서 분류).")
    if not parts:
        return ""
    return (f'<div style="background:#fff8e1;border:1px solid #f4d37a;border-radius:6px;padding:{12 - _dk.VP}px 14px;font-size:{TINY};line-height:{LH_TINY};margin:12px 0 0;">'   # 안내 상자도 안내 글 크기(14px). 머리 카드 아래라 위로 띄움 (2026-10-13)
            + "<br>".join(parts) + "</div>")


# 카드 유형 (디자인-가이드라인.md 2절): 모든 증감 표시는 구분명 왼쪽 · 값 오른쪽, 여러 줄은 한 카드 안에서 가로 구분선으로 나눈다
COL_L = "flex:0 0 65%;max-width:65%;min-width:0;white-space:normal;"   # 카드 왼쪽 65% (가이드라인 2-1, 2026-10-11 사용자: 꼭 지킨다)
COL_R = "flex:1 1 0;min-width:0;text-align:right;white-space:normal;word-break:keep-all;"   # 카드 오른쪽 35%
ROW = (f"display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 6px;padding:{10 - _dk.VP}px 12px;"
       f"background:#fff;border:1px solid #E2E8F0;border-radius:8px;white-space:nowrap;line-height:{LH_CARD};")   # A타입 (기준 카드, 본문 크기)
ROW_SMALL = f"font-size:{SMALL};padding:{7 - _dk.VP}px 12px;"       # B타입 (비교 카드)
# A타입 색 배경(상승 오렌지 · 하락 파랑)은 강조 카드 — 행간 32 · 위아래 보이는 24 (2026-10-12 사용자: "NVDA 강조 카드는 왜 공통 여백 적용이 안 된 거지")
_EMPH_ROW = f"padding:{_dk.EMPH_PAD - _dk.VP_EMPH}px 12px;line-height:{_dk.LH_EMPH};"
ROW_UP = "background:#FFF7ED;border-color:#FED7AA;" + _EMPH_ROW     # A타입 상승: 연한 오렌지
ROW_DOWN = "background:#EFF6FF;border-color:#BFDBFE;" + _EMPH_ROW   # A타입 하락: 연한 파랑
MULTI = f"display:block;margin:0 0 6px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};line-height:{LH_CARD};"   # C타입 (멀티 카드, 16px — 2026-10-11 사용자: 안내 글 빼고 14 → 16)
MULTI_ROW = f"display:flex;justify-content:space-between;align-items:center;gap:12px;padding:{_dk.SEP_GAP - _dk.VP - 1}px 12px;white-space:nowrap;line-height:{LH_CARD};"   # 가로 구분선 기준 위아래 14px, 카드 가장자리도 같게 (2026-10-12 사용자)
MULTI_SEP = "border-top:1px solid #E2E8F0;"            # C타입 줄 사이 가로 구분선


def _arrow(v, digits=2, unit="%"):
    """증감 표기 (가이드라인 4절·graph-v1 arrow): ▲ 상승 빨강 · ▼ 하락 파랑 · 0은 회색. 부호 대신 삼각형, 숫자는 절댓값."""
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    col = UP if v > 0 else DOWN if v < 0 else MUTED
    tri = "▲" if v > 0 else "▼" if v < 0 else "–"
    return f'<span style="color:{col};font-weight:700;white-space:nowrap;">{tri}&nbsp;{abs(v):.{digits}f}{unit}</span>'


def _row(name, value_html, extra=""):
    """한 줄 카드: 이름 왼쪽, 가격 정보 오른쪽 (2026-10-11 사용자 규칙). span 으로만 짜서 홈 카드가 한 줄로 읽는다."""
    # 두 span 사이 공백: flex 컨테이너라 화면엔 안 보이고, 홈 카드가 textContent 로 읽을 때 이름과 값을 띄운다
    return (f'<span style="{ROW}{extra}"><span style="{_dk.ROW_L}font-weight:700;color:#111;">{_dk.ticker_logo(name)}{_esc(name)}</span> '
            f'<span style="{_dk.ROW_R}">{value_html}</span></span> ')   # 값 `$229.28 ▼ 0.52%` 한 줄 (2026-10-12 사용자)


def _multi(rows):
    """C타입: (이름, 값HTML) 여러 줄을 한 카드에, 줄 사이 가로 구분선. span 으로만 짜서 홈 카드가 한 줄로 읽는다."""
    out = ""
    for i, (name, value_html) in enumerate(rows):
        out += (f'<span style="{MULTI_ROW}{MULTI_SEP if i else ""}"><span style="{COL_L}font-weight:700;color:#111;font-size:{_dk.NAME};">{_name(name)}</span> '
                f'<span style="{COL_R}font-weight:700;">{value_html}</span></span> ')   # 줄 사이 공백: 홈 카드가 한 줄로 읽을 때 단어를 띄운다
    return f'<span data-grid="2" style="{MULTI}">{out}</span> '   # data-grid=2: 데스크톱에서 테마 CSS가 2열 + 가운데 세로 구분선 (2026-10-11 사용자)


def _name(name):
    """카드 구분명: 글자는 이스케이프하고 괄호는 작게. 끝에 N 알약(HTML)이 붙어 있으면 그 부분은 그대로 둔다."""
    marker = ' <span style="display:inline-block;'
    if marker in name:
        text, pill = name.split(marker, 1)
        return _paren(_esc(text)) + marker + pill
    return _paren(_esc(name))


def _multi2(items):
    """E타입 2열 멀티 카드 — design_kit.multi2 와 같다: 폰에서도 2열, 값이 안 들어가면 칸 안 다음 줄 오른쪽 (2026-10-12 사용자)."""
    return _dk.multi2(items)


def sec_headline(a):
    """오늘 한 줄 — 한 줄 카드 6장 (NVDA · SPY·SMH·AMD·AVGO 대비 · 거래량). 카드 안에 카드를 만들지 않는다.

    컨테이너 div 는 꾸밈 없음(data-cards 표시만) — 홈 카드의 linesOf 가 이 div 를 잎으로 보고 한 줄로 읽는다.
    """
    h = a["headline"]
    if h.get("close") is None:
        return f'<div style="{CARD}">휴장 — 시세는 다음 거래일에 채워집니다. 공시·기사·일정만 아래에 있습니다.</div>'
    r = h.get("ret_1d") or 0
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = ROW_UP if r > 0 else ROW_DOWN if r < 0 else ""
    rows = _row("NVDA", f'<span style="color:{pcol};font-weight:700;">${h["close"]:,.2f}</span> {_arrow(h.get("ret_1d"))}', tone)   # A타입
    # 비교 4개는 따로 한 카드, 2열 + 세로 구분선 (E타입, 2026-10-11 사용자)
    rows += _multi2([(f"{tk} 대비", _arrow(h.get(key), 2, "%p")) for key, tk in (("ret_vs_spy", "SPY"), ("ret_vs_smh", "SMH"), ("ret_vs_amd", "AMD"), ("ret_vs_avgo", "AVGO"))])   # 비교 4종 앞 로고는 두지 않는다 (2026-10-13 사용자)
    items = []
    pc = {c["key"]: c for c in (a["status"].get("price") or [])}   # 상태판 가격·거래량 중 머리 카드에 없던 칸 (2026-10-11 사용자: 오늘로 모으고 기술지표에서 삭제)
    items.append(("시가 갭", _arrow((pc.get("gap") or {}).get("value"), 2)))
    rg = pc.get("range_pct") or {}
    items.append(("일중 변동폭", f'<span style="color:{WARN if rg.get("flag") else "#111"};font-weight:700;">{_esc(rr.fmt(rg.get("value"), "pct"))}</span>'))
    vr = h.get("vol_ratio_20d")
    vcol = WARN if (vr or 0) >= config.VOL_RATIO_EVENT else "#111"
    items.append(("거래량 (20일 평균 대비)", f'<span style="color:{vcol};font-weight:700;">{_esc(rr.fmt(vr, "x"))}</span>'))
    # 거래량 정보에 52주 고점 대비 · RSI · 이평 교차 포함 (2026-10-11 사용자)
    tc = {c["key"]: c for c in (a["status"].get("technical") or [])}
    items.append(("52주 고점 대비", _arrow((tc.get("pct_from_52w_high") or {}).get("value"), 2)))
    rsi = (tc.get("rsi14") or {}).get("value")
    items.append(("RSI 14 (과열 70 · 침체 30)", f'<span style="color:#111;font-weight:700;">{rsi:.1f}</span>' if rsi is not None else f'<span style="color:{MUTED};">—</span>'))
    mc = (tc.get("ma_cross") or {}).get("value")
    mc_html = {"golden": f'<span style="color:{UP};font-weight:700;">골든크로스</span>', "dead": f'<span style="color:{DOWN};font-weight:700;">데드크로스</span>'}.get(
        mc, f'<span style="color:{MUTED};">교차 없음</span>')
    items.append(("평균선 교차 (50·200일)" + _new(a, "status:ma_cross"), mc_html))
    if a.get("macro_today"):
        items.append(("거시 일정", _esc(", ".join(a["macro_today"]))))
    rows += _multi(items)   # C타입: 비교 항목은 한 카드 안에 가로 구분선으로 (2026-10-11 사용자)
    out = f'<div data-cards="1" style="margin:0 0 8px;">{rows}</div>'
    out += sec_state_cards(a)   # 시장 국면 · 반도체 자금 — 이유를 담은 별도 카드 둘 (2026-10-11 사용자)
    if not a.get("is_latest_bar_today"):
        out += _muted("기준 거래일이 최신이 아닐 수 있습니다 — 일봉 수집 상태를 확인하세요.")
    return out


REGIME_THEME = {"상승 추세": ("positive", UP), "단기 조정": ("neutral", MUTED), "조정장": ("negative", DOWN), "불안 국면": ("uncertain", WARN)}
FLOW_THEME = {"모이는 중": ("positive", UP), "빠져나가는 중": ("negative", DOWN), "뚜렷하지 않음": ("neutral", MUTED)}


def _state_card(title, state, theme, color, lines, new_html="", tip=""):
    """상태 카드 (가이드라인 2-1 D, 2026-10-11 사용자: "별도 카드로 분리하고 이유도 카드에 포함" → "안내 아이콘 삭제, 글씨 검정, 블릿으로").
    첫 줄 구분명 좌·상태 우, 아래 얇은 선 뒤에 이유 글머리표(16px, 검정). 이유 묶음은 border-top — 홈 카드는 border-top 요소를 건너뛰므로 홈에는 첫 줄만 간다."""
    bg, bd = CARD_DIR[theme]
    # 글머리표는 3px 점, 글자 14px (2026-10-11 사용자). 규칙 줄은 안내 색(NOTE). lines 항목은 str 또는 (str, "note")
    def li(item):
        text, kind = (item, "") if isinstance(item, str) else item
        col = NOTE if kind == "note" else "#111"
        return _dot_li(_label_text(text), size=3, color=col, lh=_dk.LH_EMPH)   # 강조 카드 18px 글 → 행간 32 (2026-10-12 사용자)   # 16px → 3px 점, "**라벨** : 내용", 증감 색 (2026-10-11 사용자)
    lis = "".join(li(t) for t in lines)
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{_dk.EMPH_PAD - _dk.VP_EMPH}px 14px;margin:0 0 8px;line-height:{_dk.LH_EMPH};">'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)
            f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;">'   # position:relative — 툴팁 상자가 이 줄(카드 폭) 기준으로 놓인다
            f'<span style="{COL_L}font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};">{_esc(title)}{_dk.tip_icon(tip)}{new_html}</span><span style="{COL_R}font-weight:700;color:{color};">{_esc(state)}</span></span> '
            f'<div style="margin-top:{14 - _dk.VP_EMPH}px;padding-top:{14 - _dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{SMALL};">'   # 제목 ~ 구분선 14 · 구분선 ~ 글 14 (보이는 여백, 2026-10-12 사용자)
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul></div></div>")   # 음수 margin = 첫·끝 li 의 9px 지우기


def _tip(text):
    """규칙 툴팁 — 구분명 옆 ⓘ 아이콘. 글은 data-tip 속성에, 모양은 테마 CSS(`.post-body [data-tip]::after`, build_theme.py)가 그린다:
    PC는 마우스를 올리면, 폰은 누르면(tabindex 포커스) 바로 뜬다. title 툴팁은 느리고 폰에서 안 떠서 쓰지 않는다 (2026-10-11 사용자)."""
    if not text:
        return ""
    t = _esc(text).replace(chr(34), "&quot;")
    return (f' <span data-tip="{t}" tabindex="0" role="button" aria-label="{t}" '
            f'style="display:inline-flex;align-items:center;color:{NOTE};cursor:help;vertical-align:middle;position:relative;top:-1px;margin:0 {_dk.TIP_GAP}px;">{QUESTION_ICON}</span>')   # 20px, 글자와 세로 가운데 (2026-10-13 사용자)   # 툴팁 상자는 position:relative 인 제목 줄 기준 — 카드 폭 안에 들어간다


def regime_rule():
    pb, cr, vx = abs(config.REGIME_PULLBACK_PCT), abs(config.REGIME_CORRECTION_PCT), config.REGIME_VIX_HIGH
    return (f"규칙: S&P 500(SPY) 종가가 52주 고점 대비 −{pb:.0f}% 이내이고 200일 평균 위 = 상승 추세 · −{pb:.0f}~−{cr:.0f}% = 단기 조정 · "
            f"−{cr:.0f}% 아래 또는 200일 평균 아래 = 조정장 · VIX {vx:.0f} 이상 = 불안 국면")


def sector_flow_rule():
    n, pp = config.SECTOR_FLOW_DAYS, config.SECTOR_FLOW_PP
    return (f"규칙: 반도체 ETF(SMH) {n}일 수익률이 시장(S&P 500)보다 +{pp:.0f}%p 이상 = 모이는 중 · −{pp:.0f}%p 이하 = 빠져나가는 중 · 사이 = 뚜렷하지 않음 · "
            f"발행주식수 5일 변화가 반대면 뚜렷하지 않음")


def regime_lines(mr):
    """시장 국면 이유 — 오늘 수치 두 줄 (규칙은 툴팁)."""
    st = mr.get("streak") or 0
    second = f"200일 평균 {'위' if mr['above_ma200'] else '아래'}" + (f" · VIX {mr['vix']:.1f}" if mr.get("vix") is not None else "") \
             + (f" · {abs(st)}일 연속 {'상승' if st > 0 else '하락'}" if st else " · 보합")
    lines = [f"S&P 500(SPY) 52주 고점 대비 {mr['pct_from_high']:+.1f}%", second]   # 규칙은 툴팁 (regime_rule)
    if mr.get("fng"):   # CNN 공포·탐욕 지수 (2026-10-11 사용자) — 국면 판정에는 쓰지 않고 보여 주기만
        lines.append(f"공포·탐욕 지수 {mr['fng']['score']:.0f} ({mr['fng'].get('rating_ko') or mr['fng'].get('rating')}) · 0 극단적 공포 ~ 100 극단적 탐욕")
    return lines


def sector_flow_lines(sf):
    """반도체 자금 이유 — 반도체 수치와 뜻, 섹터 순위(앞선 셋·뒤처진 셋), 발행주식수 (2026-10-11 사용자: 순위를 알려주기)."""
    n, rel = sf["days"], sf["rel_pp"]
    rank = f" · 11개 섹터와 같이 세우면 {sf['smh_rank']}위" if sf.get("smh_rank") else ""
    meaning = {"모이는 중": "돈이 반도체로 옮겨 오는 중", "빠져나가는 중": "돈이 다른 섹터로 돌고 있는 중"}.get(sf["state"], "섹터 간 이동이 뚜렷하지 않음")
    if sf.get("shares_5d") is not None and sf["state"] == "뚜렷하지 않음" and abs(rel) >= config.SECTOR_FLOW_PP:
        meaning = "가격과 실제 자금(발행주식수)이 엇갈려 방향을 두지 않음"
    lines = [f"반도체 ETF(SMH) {n}일 수익률, 시장(S&P 500) 대비 {rel:+.1f}%p{rank} → {meaning}"]
    secs = sf.get("sectors") or []
    if secs:
        top = " · ".join(f"{x['rank']}위 {x['name']} {x['rel']:+.1f}%p" for x in secs[:3])
        bot = " · ".join(f"{x['rank']}위 {x['name']} {x['rel']:+.1f}%p" for x in secs[-3:][::-1])
        lines.append(f"앞선 섹터: {top}")
        lines.append(f"뒤처진 섹터: {bot}")
    if sf.get("shares_5d") is not None:
        lines.append(f"반도체 ETF 발행주식수 5일 {sf['shares_5d']:+.1f}%")
    return lines   # 규칙은 툴팁 (sector_flow_rule)


BOLL_THEME = {"하단 도달": ("negative", DOWN), "상단 도달": ("positive", UP)}


def bollinger_rule():
    return (f"규칙: 20일 평균 ± 2σ 밴드. 종가가 하단 이하면 '하단 도달', 상단 이상이면 '상단 도달'. %B = (종가 − 하단) ÷ (상단 − 하단), 0 = 하단 · 1 = 상단. "
            f"밴드 안에 있는 날은 카드를 두지 않는다. 과거 통계는 10년간 진입일의 빈도이지 예측이 아니다")


def bollinger_lines(bb):
    low = bb["state"] == "하단 도달"
    lines = [f"종가 ${bb['close']:,.2f} · {'하단' if low else '상단'} ${(bb['lower'] if low else bb['upper']):,.2f} · 20일 평균 ${bb['ma20']:,.2f} · %B {bb['pctb']:.2f}"]
    if bb.get("days", 0) > 1:
        lines.append(f"{bb['days']}일째 {'하단 아래' if low else '상단 위'}")
    st = (bb.get("stats") or {}).get("boll_lower" if low else "boll_upper")
    base = (bb.get("stats") or {}).get("base") or {}
    if st and base:
        lines.append(f"과거 10년 {'하단' if low else '상단'} 진입 {st['n']}회 — 20일 뒤 상승 {st['up20']}% (아무 날 {base['up20']}%) · "
                     f"60일 뒤 상승 {st['up60']}% (아무 날 {base['up60']}%) · 중앙값 20일 {st['med20']:+.1f}%")
    return lines


def overheat_rule():
    return (f"규칙: RSI 14 ≥ {config.OVERHEAT_RSI:.0f} · 종가가 200일 평균보다 +{config.OVERHEAT_MA200_PCT:.0f}% 이상 위 · 20거래일 수익률 +{config.OVERHEAT_RET20_PCT:.0f}% 이상. "
            f"하나라도 해당하는 날만 카드. 통계는 10년간 그 조건에 처음 들어간 날의 20·60일 뒤 수익률 빈도이지 예측이 아니다")


def overheat_lines(oh):
    lines = []
    stats, base = (oh.get("stats") or {}), ((oh.get("stats") or {}).get("base") or {})
    for k in oh["active"]:
        v = oh["values"].get(k)
        head = f"{config.OVERHEAT_KEYS[k]} — 현재 {v:.1f}{'' if k == 'rsi80' else '%'}"
        st = stats.get(k) or {}
        if st and base:
            head += (f" · 과거 10년 진입 {st['n']}회: 20일 뒤 상승 {st['up20']}% (아무 날 {base['up20']}%) · 60일 뒤 {st['up60']}% (아무 날 {base['up60']}%) · "
                     f"중앙값 20일 {st['med20']:+.1f}%")
        lines.append(head)
    return lines


def sec_state_cards(a):
    out = ""
    mr = a.get("market_regime")
    if mr:
        theme, col = REGIME_THEME.get(mr["regime"], ("neutral", MUTED))
        out += _state_card("시장 국면", mr["regime"], theme, col, regime_lines(mr), _new(a, "regime"), tip=regime_rule())
    sf = a.get("sector_flow")
    if sf:
        theme, col = FLOW_THEME.get(sf["state"], ("neutral", MUTED))
        out += _state_card("반도체 자금", sf["state"], theme, col, sector_flow_lines(sf), _new(a, "sector_flow"), tip=sector_flow_rule())
    bb = a.get("bollinger")
    if bb and bb.get("state") in BOLL_THEME:   # 하단·상단에 닿은 날만 (2026-10-11 사용자)
        theme, col = BOLL_THEME[bb["state"]]
        out += _state_card("볼린저 밴드", bb["state"], theme, col, bollinger_lines(bb), "", tip=bollinger_rule())
    oh = a.get("overheat")
    if oh and oh.get("active"):   # 과열 조건 하나라도 해당하는 날만 (2026-10-11 사용자) — 노랑(불확실) 테마, 상태 = 해당 조건 수
        out += _state_card("과열 지표", f"{len(oh['active'])}개 조건 해당", "uncertain", WARN, overheat_lines(oh), "", tip=overheat_rule())
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""   # 데스크톱에서 2열 (테마 CSS, 2026-10-11 사용자)


def sec_chart(output_dir=None, a=None):
    """① 아래 가격 그래프 (chart_price.py가 만든 chart.json). 없으면 빈 문자열.

    설명 글자는 그림 안에 영문으로 있고, 여기엔 5·20·30일 변화율 한 줄만 둔다 — 홈 카드가 ① 구획의 줄을 그대로 읽어
    "오늘 한 줄" 아래에 붙이므로 누적 방향이 홈에서도 보인다. <img>는 글자가 없어 카드에 잡히지 않는다.
    """
    path = os.path.join(output_dir or config.OUTPUT_DIR, "chart.json")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        c = json.load(f)
    ch = c.get("changes") or {}
    # 전부 평균선 대비 (2026-10-11 사용자): 현재가가 n일 평균선보다 몇 % 위·아래. 5│20 / 60│120 / 200
    mr = c.get("ma_rel") or {}
    items = [(f"{n}일 평균", _arrow(mr[n], 1)) for n in ("20", "60", "120", "200") if mr.get(n) is not None]   # 5일선 삭제, 이름은 'n일 평균' (2026-10-11 사용자)
    zoom = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')
    # 확대 보기: 그림 전체가 원본 링크(새 창), 오른쪽 위에 돋보기 아이콘 (2026-10-11 사용자)
    return (f'<a href="{_esc(c["url"])}" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:12px 0 6px;max-width:1024px;">'
            f'<img src="{_esc(c["url"])}" alt="NVDA {c.get("window", 30)}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{zoom}</span></a>'
            + (f'<div data-cards="1" style="margin:0 0 8px;">{_multi2(items)}</div>' if items else ""))   # E타입: 5일|20일 / 60일|120일. 범례 줄은 뺐다 (2026-10-11 사용자)


LINK_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M9 3h4v4"/><path d="M13 3 7 9"/><path d="M11 9v4H3V5h4"/></svg>')


def _link_icon(url, label):
    """출처 링크는 아이콘만 (2026-10-11 사용자: 출처 텍스트 링크, 특히 영문 제목은 필요 없다). 제목은 툴팁(title)으로만."""
    if not url:
        return ""
    return (f' <a href="{_esc(url)}" title="{_esc(label)}" aria-label="{_esc(label)}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;text-decoration:none;white-space:nowrap;">{LINK_ICON}</a>')


def _event_html(e):
    tag = _tag(e["area"], e["direction"])
    if e.get("speaker"):   # 발언자 라벨 — 영역·방향 뒤 세 번째 알약 (2026-10-11 사용자: 대표 발언에 "누가 말했다")
        tag += " " + _pill(config.SPEAKER_KO.get(e["speaker"], e["speaker"]), "area")
    src = rr.SOURCE_KO.get(e.get("source") or "", e.get("source") or "")
    if e["kind"] in rr.DOC_KINDS:
        head = _esc(e["fact"])
        link = _link_icon(e.get("url"), f"{src}: {e['title'][:90]}")   # 원문 제목은 툴팁에만
        fact = ""
    else:
        head = _esc(e["title"])
        link = _link_icon(e.get("url"), f"{src} 원문")
        fact = f" — {_esc(e['fact'])}" if e.get("fact") and e["fact"] != e["title"] else ""
    when = f' <span style="color:{SUB};font-size:{TINY};white-space:nowrap;">({_esc(_d(e["published_at"][:10]))})</span>' if e.get("published_at") else ""   # 날짜가 두 줄로 쪼개지지 않게
    inner = f'<span style="font-weight:700;color:#111;">{head}</span>{fact} {tag}{link}{when}'   # 기사 제목 굵게 (2026-10-13 사용자)   # 라벨은 제목 끝 (2026-10-12 사용자: 법무·부정 등 라벨은 타이틀 끝에)
    if e.get("emphasis"):   # 법무·규제 등 우선 영역: 굵게·크게 대신 연한 배경 카드 (가이드라인 2절)
        bg, bd = CARD_DIR.get(e.get("direction"), CARD_DIR["neutral"])
        return f'<div style="background:{bg};border:1px solid {bd};border-radius:8px;padding:{_dk.SEP_GAP - _dk.NEWS_VP}px 12px;margin:0 0 8px;line-height:{_dk.LH_BODY};">{inner}</div>'   # 뉴스 제목 행간 34 (2026-10-12 사용자)   # 일반 기사 카드와 같은 크기·여백, 배경만 방향 색
    # 일반 기사: 라벨 줄이 제목 위, 새 창 아이콘 없이 제목이 원문 링크 (2026-10-13 사용자 — 강조 카드는 제외)
    lab = f'<span style="display:block;line-height:1;margin:8px 0 0;">{tag.replace(f"margin:0 {_dk.PILL_GAP}px;", "margin:0;")}</span>'   # 라벨 줄: 여백 없이 왼쪽 정렬, 기사 맨 아래 (2026-10-13 사용자)
    tip_t = _esc(f"{src}: {e['title'][:90]}" if e["kind"] in rr.DOC_KINDS else f"{src} 원문").replace(chr(34), "&quot;")
    head_html = (f'<a href="{_esc(e["url"])}" title="{tip_t}" target="_blank" rel="noopener" style="font-weight:700;color:#111;text-decoration:none;">{head}</a>'
                 if e.get("url") else f'<span style="font-weight:700;color:#111;">{head}</span>')
    return f"{head_html}{fact}{when}{lab}"


# 막대는 파스텔 톤 (2026-10-11 사용자: 너무 빨갛다, 눈의 피로) — (배경, 글자)
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"),
              "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
RATING_PASTEL = [("strongBuy", "강매수", "#F4ACA6", "#7F1D1D"), ("buy", "매수", "#FAD3CF", "#7F1D1D"),
                 ("hold", "보유", "#E2E8F0", "#475569"), ("sell", "매도", "#C9DCF7", "#1E3A8A"), ("strongSell", "강매도", "#A9C5F2", "#1E3A8A")]


def _bar(label, segs, split="right"):
    """F 막대 (가이드라인 2-1): 위 14px 라벨(합계 + 항목별 %), 아래 콘텐츠 폭 전부 가로 누적 막대. segs = [(이름, 개수, 배경, 글자)]."""
    total = sum(n for _, n, _, _ in segs)
    if not total:
        return ""
    pcts = " · ".join(f"{nm} {n / total * 100:.0f}%" for nm, n, _, _ in segs if n)
    body = "".join(f'<span style="display:block;width:{n / total * 100:.1f}%;background:{bg};color:{fg};font-size:{SMALL};font-weight:700;'
                   f'text-align:center;line-height:24px;overflow:hidden;white-space:nowrap;">{f"{n / total * 100:.0f}%" if n / total >= 0.08 else ""}</span>' for _, n, bg, fg in segs if n)   # 8% 미만 조각은 글자 생략 (라벨에 있음)
    bar_html = f'<span style="display:flex;width:100%;height:24px;border-radius:6px;overflow:hidden;background:#F1F5F9;margin:0 0 3px;">{body}</span>'
    return _dk.bar_label(label, pcts) + bar_html + _dk.bar_pcts(pcts)   # 라벨(검정 굵게) 위 · 막대 · 비율 아래 — 뉴스 · 애널리스트 모두 (2026-10-13 사용자)


def _ratio_bar(label, counts):
    """뉴스 방향 막대: 긍정 · 부정 · 불확실 · 중립 (파스텔)."""
    total = sum(counts.values())
    return _bar(f"{label} {total}건", [(rr.DIR_KO[d], counts.get(d, 0), *BAR_PASTEL[d]) for d in ("positive", "negative", "uncertain", "neutral")], split="below")


ACC_CHEV = ('<svg class="acc-chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>')


ACC_BTN = _dk.fold_btn()   # 네모 박스 안 화살표 버튼 (2026-10-11 사용자) = 공식 접기 버튼, 28 → 31px (2026-10-13 사용자, 가이드라인 10-6)


def _accordion(summary_html, body_html, open_=False, block=False):
    """아코디언 (가이드라인 2-1 H): <details data-acc>. 요약 줄 오른쪽 화살표(펼치면 위로 — 테마 CSS가 회전). JS 없이 동작.
    block=True 면 요약이 여러 줄(세로로 쌓인 행)로 카드 오른쪽 끝까지 꽉 차고, 화살표는 호출자가 마지막 줄 안에 ACC_BTN(네모 버튼)으로 넣는다
    (2026-10-11 사용자: "항상 보이는 부분은 카드 우측까지 꽉 차게, 화살표는 네모 박스 안 버튼")."""
    if block:
        return (f'<details data-acc="1"{" open" if open_ else ""} style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};line-height:{LH_CARD};">'
                f'<summary style="display:block;padding:0 12px {_dk.SEP_GAP - _dk.VP - 1}px;cursor:pointer;list-style:none;">{summary_html}</summary>'
                f'<div style="padding:0 12px;border-top:1px solid #E2E8F0;">{body_html}</div></details>')   # 줄마다 위아래 10px (줄이 갖는다)
    return (f'<details data-acc="1"{" open" if open_ else ""} style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};line-height:{LH_CARD};">'
            f'<summary style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:{_dk.SEP_GAP - _dk.VP - 1}px 12px;cursor:pointer;list-style:none;">'
            f'<span style="flex:1;min-width:0;display:flex;justify-content:space-between;gap:12px;">{summary_html}</span>{ACC_BTN}</summary>'
            f'<div style="padding:{_dk.SEP_GAP - _dk.VP - 1}px 12px;border-top:1px solid #E2E8F0;">{body_html}</div></details>')


def direction_summary(a):
    """뉴스 제목 옆 요약: 오늘 건수와 방향별 건수(%)."""
    today = (a.get("direction_counts") or {}).get("today") or {}
    total = sum(today.values())
    if not total:
        return ""
    parts = [f"{rr.DIR_KO[d]} {today[d]} ({today[d] / total * 100:.0f}%)" for d in ("positive", "negative", "uncertain", "neutral") if today.get(d)]
    return _esc(f"오늘 {total}건 · " + " · ".join(parts))


BAR_GROUP_GAP = 24   # 뉴스 막대 묶음(오늘 · 최근 7일) 사이 보이는 여백 (2026-10-12 사용자)


def sec_direction_bars(a):
    """뉴스 제목 아래 비율 막대 두 개 (오늘 · 최근 7일), 콘텐츠 폭 전부. 안내글 없음 — 수치는 제목 옆 요약에."""
    dc = a.get("direction_counts") or {}
    today, week = dc.get("today") or {}, dc.get("week") or {}
    if not sum(today.values()) and not sum(week.values()):
        return ""
    # 두 막대 묶음 사이 보이는 24px (2026-10-12 사용자) — 앞 묶음 비율 글자 → 다음 라벨 글자, 행간 반쪽 3 + 3 을 뺀 값
    return (f'<div data-cards="1" style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:{_dk.SEP_GAP - 3}px 12px {_dk.SEP_GAP - 3 - 10}px;">{_ratio_bar("오늘", today)}'   # 두 막대를 카드 하나에 (2026-10-13 사용자)
            f'<span style="display:block;height:{BAR_GROUP_GAP - 5}px;"></span>{_ratio_bar("최근 7일", week)}</div>')


def sec_events(a):
    if not a["events"]:
        return _muted("오늘은 임계값을 넘은 이벤트가 없습니다 — 공시·기사·가격·옵션·예상 실적 어느 쪽도 기준에 걸리지 않았다는 뜻입니다.")
    cards = [e for e in a["events"] if e.get("emphasis")]
    plain = [e for e in a["events"] if not e.get("emphasis")]
    out = "".join(_event_html(e) for e in cards) + _dk.item_rules([_event_html(e) for e in plain])   # 강조 카드만 카드, 나머지는 가로 구분선 목록 (2026-10-13 사용자)
    if a["events_overflow"]:
        # 카드 버튼 (가운데, 검정) — 2026-10-11 사용자
        out += (f'<details data-acc="1" style="margin:8px 0;"><summary style="{_dk.FOLD_BTN}">그 외 {len(a["events_overflow"])}건 {ACC_CHEV}</summary>'
                + '<div style="margin-top:8px;">' + _dk.item_rules([_event_html(dict(e, emphasis=False)) for e in a["events_overflow"]]) + "</div></details>")
    if a.get("analyst_target_only"):
        out += _muted(f"목표가만 바뀐 애널리스트 {len(a['analyst_target_only'])}건 (등급 변경 아님): "
                      + " · ".join(t["title"] for t in a["analyst_target_only"][:6]))
    return out


SIGNED_FMTS = ("pct_signed", "pct_signed2", "pp_signed")
STATUS_KO = {"active": "진행 중", "closed": "종결", "stayed": "중지", "settled": "합의", "dismissed": "기각"}


def _crow(name_html, value_html, sub="", first=False, left=None, short=False):
    """C 카드의 한 줄 (가이드라인 2-1): 왼쪽 구분명(굵게) + 그 아래 보조 줄(14px #999), 오른쪽 값. 줄 사이 가로 구분선."""
    return (f'<span style="{MULTI_ROW}{"" if first else MULTI_SEP}">'
            f'<span style="display:block;line-height:{LH_CARD};{_dk.COL_L75 if short else COL_L}">{_dk.crow_left(name_html, sub, 80 if short else 65)}</span> '
            f'<span style="{COL_R}font-weight:700;">{value_html}</span></span> ')   # 왼쪽 65% · 오른쪽 35%, 값이 모두 5자 미만이면 80 · 20 (2026-10-11 사용자)


def _ccard(rows, left=None):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html)]. 카드 하나, 줄 사이 가로 구분선."""
    short = _dk.short_values(rows)
    inner = "".join(_crow(n, v, sb, first=(i == 0), short=short) for i, (n, v, sb) in enumerate(rows))
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{MULTI}">{inner}</span></div>'   # 데스크톱 2열 (테마 CSS)


def _sub_label(t):
    """카드 묶음 위 소제목 — F 막대 라벨과 같은 모양 (14px 안내 회색). data-sub: 탭이 서브탭으로 쓴다."""
    return f'<div data-sub="1" style="font-size:{SMALL};line-height:{LH_CARD};color:{NOTE};margin:10px 0 3px;">{_paren(_esc(t))}</div>'   # 소제목 16px


CAL_DATE = "font-weight:700;color:#111;"   # G 캘린더 카드: 날짜 첫 칸 굵게 (왼쪽 칸 전체 16px — 2026-10-12 사용자)


def _gcard(rows):
    """G 캘린더 카드: 왼쪽 두 줄 [날짜 16px 굵게 + 라벨 / 내용 · 덧붙임], 오른쪽 D-n. 줄 사이 가로 구분선, 14px.
    rows = (날짜HTML, 라벨HTML, 내용HTML, 보조줄, D-n)."""
    inner = ""
    for i, (date_html, label_html, name_html, sub, right_html) in enumerate(rows):
        sub_html = f'<span style="display:block;color:{SUB};font-size:{TINY};line-height:{LH_TINY};white-space:normal;">{_dk.sub_line(sub)}</span>' if sub else ""   # 보조 줄은 14px, 증감 색
        inner += (f'<span style="{MULTI_ROW}{"" if i == 0 else MULTI_SEP}">'
                  f'<span style="display:block;{COL_L}font-size:{_dk.NAME};">'
                  f'<span style="display:block;"><span style="{CAL_DATE}">{date_html}</span></span> '
                  f'<span style="display:block;">{name_html}{" " + label_html if label_html else ""}</span>{sub_html}</span> '   # 라벨은 내용 끝 — 뉴스 라벨과 같은 모양·자리 (2026-10-12 사용자)
                  f'<span style="{COL_R}font-weight:700;">{right_html}</span></span> ')
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{MULTI}">{inner}</span></div>'


def _dn(d0, day):
    dn = (datetime.date.fromisoformat(day) - d0).days
    return "D-day" if dn == 0 else f"D{dn:+d}"


def sec_upcoming(a):
    """캘린더 — G 카드: 날짜 첫 칸, [종류 라벨] 내용, D-n (2026-10-11 사용자: 예정 → 캘린더, 날짜 강조)."""
    d0 = datetime.date.fromisoformat(a["day"])
    rows = []
    for c in a["upcoming"]:
        extra = ""
        if c["kind"] == "EARNINGS":
            im = next((x["value"] for x in a["status"]["options"] if x["key"] == "implied_move_next_earnings"), None)
            extra = f"예상 변동폭 ±{im:.1f}%" if im else ""   # implied move (가이드라인 3-4)
        court = c["kind"] == "COURT"
        kind = rr.KIND_KO.get(c["kind"], c["kind"]).replace("⚠ ", "")
        label = _pill(kind, "uncertain" if court else "area") + _new(a, f"calendar:{c['kind']}:{c['day']}:{c['label']}")   # 라벨은 날짜 옆 (2026-10-11 사용자) · 새 일정은 N
        tail = "".join(f'<span style="color:{SUB};white-space:nowrap;"> · {_esc(x)}</span>'
                       for x in ("추정" if not c.get("confirmed", 1) else "", extra) if x)   # '추정'은 구분점 뒤 같은 줄, 줄바꿈 없음
        name = (f'<span style="color:{WARN};">{_esc(c["label"])}</span>' if court else f'<span style="color:#111;">{_esc(c["label"])}</span>') + tail
        dcol = WARN if court else "#111"
        rows.append((f'<span style="color:{dcol};">{_esc(_d(c["day"]))}</span>', label, name, "", f'<span style="color:{dcol};">{_dn(d0, c["day"])}</span>'))
    if not rows:
        return _muted("잡힌 일정이 없습니다.")
    return _gcard(rows)


def _status_value(c, st):
    """상태판 값: 부호 있는 수치는 ▲▼, 임계 넘은 칸은 경고색, 없는 값은 — (이유는 보조 줄)."""
    if c["value"] is None or c["value"] == "":
        hint = config.MISSING_HINTS.get(c["key"], config.MISSING_DEFAULT_HINT)
        if c["key"] == "iv_rank_60d":
            hint += f" (현재 {st.get('iv_rank_n', 0)}/{config.IV_RANK_WINDOW}일)"
        return f'<span style="color:{MUTED};">—</span>', INFO_ICON + _esc(hint)
    if c["fmt"] in SIGNED_FMTS and isinstance(c["value"], (int, float)):
        return _arrow(c["value"], 2, "%p" if c["fmt"] == "pp_signed" else "%"), ""
    v = _esc(_d(rr.fmt(c["value"], c["fmt"])))
    return (f'<span style="color:{WARN};font-weight:700;">{v}</span>' if c["flag"] else v), ""


# 묶음 설명 — 카드 아래 ⓘ 한 줄 (디자인-가이드라인 3-4, 2026-10-11). 뜻만 적고 평가하지 않는다
GROUP_NOTE = {   # 제목 있는 안내 (_guide) — 짧으면 한 줄, 길면 글머리표 (2026-10-11 사용자)
    "options": ("옵션", [("뜻", "옵션 시장이 가격에 담은 기대치"), ("수집", "미국 장 마감 후 1회 스냅샷")]),
    "estimates": ("예상 실적", [("값", "애널리스트 예상치의 평균"), ("7일 변화", "예상치가 일주일 사이 움직인 폭")]),
    "flows": ("수급", [("ETF 발행주식수", "자금 유입·유출 (yfinance)"), ("공매도 잔고", "격주 집계"),
                      ("장외 공매도 비율", "FINRA에 보고된 장외 거래만, 거래소 체결 제외 · 당일 파일이 늦으면 다음 실행에 채움")]),
    "valuation": ("주가 수준", "주가가 앞으로 12개월 예상 이익의 몇 배인지"),
}


def sec_status(a):
    """상태판 — 묶음마다 소제목 + C 카드 (지표 왼쪽, 값 오른쪽) + ⓘ 설명 한 줄."""
    st = a["status"]
    out = []
    for group in ("options", "estimates", "flows", "valuation"):   # 가격·거래량·기술·뉴스·애널리스트는 오늘 탭으로 (2026-10-11 사용자)
        cells = st.get(group) or []
        if not cells:
            continue
        rows = []
        for c in cells:
            v, sub = _status_value(c, st)
            rows.append((_esc(rr.LABEL_KO.get(c["key"], c["key"])) + _new(a, "status:" + c["key"]), v, sub))
        out.append(_sub_label(rr.GROUP_KO[group]) + _ccard(rows) + (_guide(*GROUP_NOTE[group]) if GROUP_NOTE.get(group) else ""))
    return "".join(out)


def sec_cases(a):
    """진행 중 사안 — 캘린더 탭 안, G 카드: 다음 일정 날짜 첫 칸, 사건명 + ↗, 보조 줄에 일정 내용·상태 (2026-10-11 사용자: 사안은 캘린더와 통합)."""
    if not a["cases"]:
        return _muted("추적 사안 없음.")
    d0 = datetime.date.fromisoformat(a["day"])
    rows = []
    for c in a["cases"]:
        name = f'<span style="font-weight:700;color:#111;">{_paren(_esc(c.get("short_name") or c["title"]))}</span>' + _link_icon(c.get("url"), "도켓 보기") + _new(a, "case:" + c["case_id"])
        status = STATUS_KO.get(c.get("status") or "", c.get("status") or "—")
        sub = [c["next_label"] if c.get("next_day") else "잡힌 일정 없음", status]
        if c.get("last_activity_summary"):
            sub.append(f"최근 {_d(c['last_activity_at'][:10])} {c['last_activity_summary']}")
        date = _esc(_d(c["next_day"])) if c.get("next_day") else f'<span style="color:{MUTED};font-weight:400;">—</span>'
        right = _dn(d0, c["next_day"]) if c.get("next_day") else ""
        rows.append((date, "", name, _esc(" · ".join(sub)), right))
    return _gcard(rows)


def _group_card(a, group):
    st = a["status"]
    rows = []
    for c in st.get(group) or []:
        v, sub = _status_value(c, st)
        rows.append((_esc(rr.LABEL_KO.get(c["key"], c["key"])), v, sub))
    return _ccard(rows) if rows else ""


def sec_technical(a):
    """기술 — 오늘 탭 (2026-10-11 사용자: 기술 정보도 오늘에). 50·200일선, 52주 고점 대비, RSI, 이평 교차."""
    return _group_card(a, "technical")


NEWS_STAT_KO = {"news_count": "기사", "news_avg_7d": "7일 평균", "news_pending": "대기 문서"}   # 짧은 이름 (2026-10-12 사용자)


def sec_news_counts(a):
    """뉴스 수치 — 뉴스 구획 안, 막대 아래 한 줄 카드: 기사 18 │ 7일 평균 22.6 │ 대기 문서 1 (2026-10-12 사용자: 구분선을 추가하여 한 줄에)."""
    items = []
    for c in a["status"].get("news") or []:
        v = rr.fmt(c["value"], c["fmt"]) if c.get("value") is not None else "—"
        items.append((NEWS_STAT_KO.get(c["key"], rr.LABEL_KO.get(c["key"], c["key"])),
                      f'<span style="color:{WARN};">{_esc(v)}</span>' if c.get("flag") else _esc(v)))
    return _dk.stat_line(items) if items else ""


def sec_targets(a):
    """목표가 — 오늘 탭, 그래프 아래 변화 카드(50·200일선) 바로 다음 (2026-10-11 사용자).
    아코디언: 접힌 상태 = 목표가 평균 줄 + 등급 분포 막대 + 평균 등급 줄(화살표는 이 줄 오른쪽), 펼치면 목표가 중앙·최고·최저 (같은 줄 모양) (2026-10-11 사용자: 막대도 계속 보이는 영역)."""
    cells = {c["key"]: c for c in (a["status"].get("analysts") or [])}
    close = (a.get("headline") or {}).get("close")
    mean = (cells.get("pt_mean") or {}).get("value")
    if mean is None:
        return ""
    gap = lambda v: _arrow((v / close - 1) * 100, 1) if close else ""
    # 목표가 줄은 값 `$329 · 현재가 대비 ▲ 43.4%` 를 한 줄로 (2026-10-12 사용자) — 이름은 글자 폭만, 값은 남은 폭 줄바꿈 없이, `· 현재가 대비` 14px
    tl = f"flex:none;font-weight:700;color:#111;font-size:{_dk.NAME};"
    tr = "flex:1 1 0;min-width:0;text-align:right;white-space:nowrap;font-weight:700;"
    vs = f'<span style="color:{SUB};font-weight:400;font-size:{TINY};">· 현재가 대비</span>'
    rc = (cells.get("rating_counts") or {}).get("value") or {}
    n = sum(rc.values()) if rc else 0
    bar = _bar(f"애널리스트 {n}명", [(nm, rc.get(k, 0), bg, fg) for k, nm, bg, fg in RATING_PASTEL], split="break") if n else ""   # 인원 다음 줄에 비율 (2026-10-12 사용자)
    tn = next((_new(a, "status:" + k) for k in ("pt_mean", "pt_median", "pt_high", "pt_low", "rating_counts") if _new(a, "status:" + k)), "")   # 목표가·등급 중 하나라도 바뀐 날
    # 접힌 상태: 목표가 평균 줄 + 평균 등급 줄 (화살표는 평균 등급 줄 오른쪽, 2026-10-11 사용자)
    summary = (f'<span style="{MULTI_ROW}padding:{_dk.SEP_GAP - _dk.VP - 1}px 0;"><span style="{tl}">목표가 평균{tn}</span> '
               f'<span style="{tr}">{_esc(rr.fmt(mean, "usd0"))} {vs} {gap(mean)}</span></span>')
    if n:   # 등급 분포 막대는 접힌 상태에도 보인다 (2026-10-11 사용자) — 목표가 평균 줄 아래
        summary += f'<span style="display:block;padding:{_dk.SEP_GAP - _dk.VP - 1}px 0 10px;{MULTI_SEP}">{bar}</span>'   # 막대 아래 margin 10 + 10 ≈ 보이는 22 (2026-10-12)
        # 평균 등급 (2026-10-11 사용자: 네이버 컨센서스처럼 한 숫자로) — 강매수 5 … 강매도 1 가중 평균. 애널리스트 의견의 평균이지 리포트의 판단이 아니다
        mean_r = sum(w * rc.get(k, 0) for k, w in (("strongBuy", 5), ("buy", 4), ("hold", 3), ("sell", 2), ("strongSell", 1))) / n
        summary += (f'<span style="{MULTI_ROW}padding:{_dk.SEP_GAP - _dk.VP - 1}px 0 0;{MULTI_SEP}"><span style="{COL_L}font-weight:700;color:#111;font-size:{_dk.NAME};">{_paren("평균 등급 (강매수 5 · 강매도 1)")}</span> '
                    f'<span style="{COL_R}font-weight:700;display:inline-flex;align-items:center;justify-content:flex-end;">{mean_r:.1f}&nbsp;<span style="color:{MUTED};font-weight:400;">/ 5</span>{ACC_BTN}</span></span>')
    else:
        summary += f'<span style="display:flex;justify-content:flex-end;padding:4px 0 0;">{ACC_BTN}</span>'
    # 펼친 상태: 목표가 중앙·최고·최저 (평균 줄과 같은 모양)
    rows = ""
    for key, name in (("pt_median", "중앙"), ("pt_high", "최고"), ("pt_low", "최저")):
        v = (cells.get(key) or {}).get("value")
        if v is None:
            continue
        rows += (f'<span style="{MULTI_ROW}padding:{_dk.SEP_GAP - _dk.VP - 1}px 0;{MULTI_SEP if rows else ""}"><span style="{tl}">목표가 {name}</span> '
                 f'<span style="{tr}">{_esc(rr.fmt(v, "usd0"))} {vs} {gap(v)}</span></span>')   # 펼친 줄도 구분선 위아래 22 (2026-10-12 사용자: 콘텐츠 카드 일괄)
    return _accordion(summary, f'<span style="display:block;">{rows}</span>', block=True)


def checklist_summary(a):
    """재무 제목 옆 안내: 기준 분기(가장 많이 쓰인 FY 분기) · ▲▼ 뜻 (2026-10-11 사용자: 재무는 기준일을 안내)."""
    qs = [r.get("asof") for r in a["checklist"] if r.get("asof") and str(r["asof"]).startswith("FY")]
    q = max(set(qs), key=qs.count) if qs else None
    return _esc(f"기준 {q} 실적 · 수치별 기준일은 각 줄 아래 · ▲▼ 직전 분기 대비" if q else "▲▼ 직전 분기 대비")


def sec_checklist(a):
    """보유 논리 점검표 — C 카드: 왼쪽 지표 + 보조 줄(기준 분기 · 출처), 오른쪽 값 + ▲▼ (직전 분기 대비)."""
    rows = []
    for r in a["checklist"]:
        sub = _fq(" · ".join(x for x in (_d(r.get("asof")), r.get("detail") or r.get("source")) if x)).replace("가이던스", "회사 전망")   # 저장된 출처 문구도 쉬운 한국어로 (가이드라인 3-4)
        if r.get("value") is None:
            rows.append((_esc(r["label"]) + _new(a, "checklist:" + r["metric"]), f'<span style="color:{MUTED};">—</span>',
                         INFO_ICON + _esc(r.get("note") or "이번 실행에서 받지 못함 — 다음 실행에서 재시도")))   # 안내는 아이콘 필수
            continue
        if r["unit"] == "USD":
            v = f"${r['value'] / 1e9:,.2f}B" if abs(r["value"]) >= 1e9 else f"${r['value'] / 1e6:,.1f}M"
        elif r["unit"] in ("%", "% of shares"):
            v = f"{r['value']:.1f}%"
        elif r["unit"] == "배":
            v = f"{r['value']:.1f}배"
        else:
            v = f"{r['value']:,}"
        arrow = r.get("arrow")
        if arrow in ("↑", "↓"):
            col, tri = (UP, "▲") if arrow == "↑" else (DOWN, "▼")
            v = f'<span style="color:{col};font-weight:700;">{tri} {_esc(v)}</span>'
        else:
            v = _esc(v)
        rows.append((_esc(r["label"]) + _new(a, "checklist:" + r["metric"]), v, _esc(sub)))
    return _ccard(rows, left="65%")   # 재무: 왼쪽 65% 고정 — 긴 지표 이름·출처는 다음 줄로 (2026-10-11 사용자)


def sec_narrative(a, n):
    if not n or not n.get("today"):
        return _muted("오늘은 이벤트가 없어 해석을 생략합니다." if not a["events"] else "서술을 만들지 못했습니다 — 수치 섹션만 참고하세요.")
    areas = "|".join(re.escape(v) for v in rr.AREA_KO.values())
    lines = [re.sub(rf"^({areas})\s+(?!·)", r"\1 · ", t) for t in n["today"]]   # 영역 머리 뒤 구분점 보정
    lis = "".join(_dot_li(_esc(t), size=3, lh=_dk.LH_BODY, margin=_dk.LI_MARGIN) for t in lines)   # 18px 글 → 3px 점 (2026-10-12 사용자)
    # 내용은 흰 카드 안 (2026-10-13 사용자: "중요 이슈의 내용 부분만 카드 디자인") — 보이는 위아래 14 = padding 14 − 행간 반쪽 7, 첫 · 끝 글머리표 margin 은 음수 margin 으로
    return (f'<div style="background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:{_dk.SEP_GAP - _dk.NEWS_VP}px 14px;margin:0 0 8px;line-height:{_dk.LH_BODY};">'   # 보이는 위아래 22 (콘텐츠 카드, 2026-10-13 사용자)
            f"<ul style='margin:-12px 0;padding:0;list-style:none;'>{lis}</ul></div>")


def sec_footer(a):
    ds = a["data_status"]
    return (f'<div data-footer="1" style="margin-top:3px;padding-top:2px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};{_dk.GUIDE_IND}">'
            f"{INFO_ICON}데이터: yfinance(일봉·옵션·예상 실적·애널리스트·기관·공매도) · SEC 공시(임원 거래·수시·분기 보고) · FRED(거시 일정) · "
            f"NVIDIA 뉴스룸·블로그 · CNBC · Google News · 연방관보 · CourtListener · trump-trend. "
            f"분류 Gemini, 판정·계산 파이썬. 생성 {_esc(a['generated_at'])} (UTC) · 기준 거래일 {_esc(_d(a['day']))} · 일봉 마지막 {_esc(_d(ds['bars_last_day']) or '—')}.<br>"
            f"{INFO_ICON}이 글은 보유 종목의 사실 추적입니다. 매수·매도 판단을 담지 않으며, 사건과 가격 변화 사이의 인과를 단정하지 않습니다. "
            f"옵션 지표는 장 마감 후 1회 스냅샷이고 감마 노출은 조잡한 근사입니다. 트럼프 과거 반응 통계는 다중 검정 보정(q)을 거친 값만 인용합니다. 투자 권고가 아닙니다."
            + (f"<br>{INFO_ICON}용어와 각 구획을 읽는 법은 <b>리포트 읽는 법</b>{_link_icon(config.GUIDE_URL, '리포트 읽는 법')}" if config.GUIDE_URL else "")   # 고정 페이지 (가이드라인 3-4·6절)
            + "</div>")


# ── 조립 ─────────────────────────────────────────────────────────────────

def build_body(a, n):
    return _dk.fix_colons("\n".join([   # ":" 앞뒤 띄우기 (2026-10-11 사용자: 꼭 반드시, 모든 페이지)
        # data-design="2": 테마의 옛 글 보정 규칙(div 14px → 17px !important)에서 이 글을 제외한다 (2026-10-11 — 안내 글이 17px로 커지던 원인)
        f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:{_dk.BODY};line-height:{_dk.LH_BODY};color:#333;">',   # 행간 24px (2026-10-12 사용자, 소수점 금지 — 2026-10-12 사용자)
        # 기준 거래일 안내 줄 삭제 (2026-10-12 사용자) — 날짜는 글 제목에 있다
        sec_headline(a), sec_chart(a=a), sec_targets(a),   # 목표가는 200일선 카드 아래 (아코디언)   # 제목 없이 본문 머리에 (2026-10-11 사용자: 오늘 한 줄 타이틀 삭제)
        # 테스트 운영 안내는 머리 카드 뒤 (2026-10-13 사용자: 구글 검색) — 맨 앞이면 검색 결과 · 공유 미리보기 문구가 "테스트 운영 중 …"이 된다
        _notice(a),
        _section("중요 이슈", sec_narrative(a, n), tab="오늘"),   # 그래프 아래로 (2026-10-11 사용자)
        _section("뉴스", sec_direction_bars(a) + sec_news_counts(a) + sec_events(a), line=False, tab="오늘"),   # 바로 아래가 카드라 제목 밑 구분선 없음 (2026-10-13 사용자)   # 막대가 바로 와도 구분선
        # 탭 이름과 같은 제목(캘린더·기술지표·재무)은 탭 화면에서 숨긴다 — 본문(탭 없음)에서는 구획 경계로 남는다
        _section("캘린더", sec_upcoming(a) + _guide("범위", f"{config.CALENDAR_LOOKAHEAD_DAYS}일 이내 · 법원 일정은 {config.COURT_LOOKAHEAD_DAYS}일"), tab="캘린더"),   # 안내는 카드 아래 (2026-10-11 사용자)
        _section("진행 중 사안", sec_cases(a), tab="캘린더"),
        _section("기술지표", sec_status(a), tab="기술지표"),
        _section("재무", sec_checklist(a), tab="재무"),

        sec_footer(a),
        "</div>",
    ]))


def render(analysis_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    analysis_path = analysis_path or os.path.join(output_dir, "nvda_analysis.json")
    narrative_path = narrative_path or os.path.join(output_dir, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    n = None
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            n = json.load(f)
    title = report_title.post_title(a.get("run_date") or report_title.today_kst())
    body = build_body(a, n)
    body_path = os.path.join(output_dir, "nvda_report_body.html")
    preview_path = os.path.join(output_dir, "nvda_report.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    print(f"[html] {len(body):,}자 → {body_path} · 미리보기 {preview_path}")
    return body_path, preview_path, title


MOCK_TABS = os.path.join(config.OUTPUT_DIR, "mock_tabs.html")


def write_mock_tabs(body_path=None, mock_path=None):
    """탭 목업 (가이드라인 11절) — 저장소 index.html(블로그 테마)의 CSS·JS로 본문을 감싼다 (design_kit.write_mock, 데일리·트럼프와 같은 방식).
    예전에는 mock_tabs.html 안에 테마 CSS를 손으로 복사해 두어 테마가 바뀌면 목업만 옛 모양으로 남았다 (2026-10-12 발견: 탭 16px)."""
    mock_path = mock_path or MOCK_TABS
    body_path = body_path or os.path.join(config.OUTPUT_DIR, "nvda_report_body.html")
    with open(body_path, "r", encoding="utf-8") as f:
        body = f.read()
    title_path = os.path.join(config.OUTPUT_DIR, "title.txt")
    title = open(title_path, encoding="utf-8").read().strip() if os.path.exists(title_path) else "엔비디아 리포트"
    out = _dk.write_mock(body, mock_path, title)
    print(f"[mock-tabs] {'목업 → ' + out if out else 'index.html 이 없어 목업을 만들지 않음'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
    if "--mock-tabs" in sys.argv:
        write_mock_tabs()
