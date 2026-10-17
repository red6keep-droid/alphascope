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
VAL = f"font-size:{_dk.CHG_SIZE};"   # 흰 카드 오른쪽 정보 17px — 강조(색 배경) 카드 제외 (2026-10-13 사용자, 가이드라인 10-7)
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
    # inline-block: 한 줄에 못 들면 괄호째 다음 줄로 — design_kit.paren 과 같다 (2026-10-17 사용자: 52주 고점 대비 · 단기 과열 온도의 괄호가 중간에서 끊김)
    return _PAREN.sub(lambda m: f' <span style="display:inline-block;font-size:{MICRO};font-weight:400;">{m.group(1)}</span>', name_html)


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
    for i, row in enumerate(rows):
        name, value_html, tip = (tuple(row) + ("",))[:3]   # 세 번째 값 = 구분명 옆 ? 툴팁 (2026-10-14 사용자: 시가 갭)
        out += (f'<span style="{MULTI_ROW}{MULTI_SEP if i else ""}"><span style="{COL_L}font-weight:700;color:#111;font-size:{_dk.NAME};">{_name_tip(name, tip)}</span> '
                f'<span style="{COL_R}{VAL}font-weight:700;">{value_html}</span></span> ')   # 줄 사이 공백: 홈 카드가 한 줄로 읽을 때 단어를 띄운다
    return f'<span data-grid="2" style="{MULTI}">{out}</span> '   # data-grid=2: 데스크톱에서 테마 CSS가 2열 + 가운데 세로 구분선 (2026-10-11 사용자)


def _name(name):
    """카드 구분명: 글자는 이스케이프하고 괄호는 작게. 끝에 N 알약(HTML)이 붙어 있으면 그 부분은 그대로 둔다."""
    marker = ' <span style="display:inline-block;'
    if marker in name:
        text, pill = name.split(marker, 1)
        return _paren(_esc(text)) + marker + pill
    return _paren(_esc(name))


def _name_tip(name, tip):
    """구분명 + 툴팁 아이콘 — 아이콘은 굵은 제목 글자 바로 옆, 작은 (…) 설명 앞에 (2026-10-17 사용자: 툴팁 아이콘은 타이틀 옆. 설명 괄호 뒤에 두면 줄이 바뀌어 아이콘만 떨어졌다)."""
    if not tip:
        return _name(name)
    marker = ' <span style="display:inline-block;'
    pill = ""
    if marker in name:
        name, rest = name.split(marker, 1)
        pill = marker + rest
    head, sep, paren = name.partition(" (")
    icon = _tipx(tip)
    if not sep:
        return _paren(_esc(head)) + icon + pill
    return _paren(_esc(head)) + icon + _paren(_esc(" (" + paren)) + pill


def _multi2(items):
    """E타입 2열 멀티 카드 — design_kit.multi2 와 같다: 폰에서도 2열, 값이 안 들어가면 칸 안 다음 줄 오른쪽 (2026-10-12 사용자)."""
    html = _dk.multi2([(it[0], f'<span style="{VAL}">{it[1]}</span>') + tuple(it[2:]) for it in items])   # 오른쪽 값 17px (2026-10-13 사용자)
    # 왼쪽 정보 14px · 보통 굵기, 이름과 값을 한 줄로 (2026-10-14 사용자). data-pair 를 빼야 테마의 폰 규칙(값을 다음 줄로)이 걸리지 않는다
    # 카드 바깥 좌우 = 1열 카드와 같은 12, 세로 구분선 쪽 안쪽만 8 — 폰 반 폭 칸에 `AVGO 대비 ▲ 0.59%p` 가 한 줄로 들게 (2026-10-14 사용자)
    v = _dk.SEP_GAP - _dk.VP - 1
    pad = f"padding:{v}px 12px;"
    left = _dk.E_CELL.replace(pad, f"padding:{v}px 8px {v}px 12px;", 1)
    right = _dk.E_CELL.replace(pad, f"padding:{v}px 12px {v}px 8px;", 1)
    html = html.replace(f'style="{_dk.E_CELL}border-left', f'style="{right}border-left').replace(f'style="{_dk.E_CELL}"', f'style="{left}"')
    return (html.replace(_dk.E_NAME, f"flex:0 1 auto;min-width:0;white-space:nowrap;font-weight:400;color:#111;font-size:{TINY};")
            .replace("flex-wrap:wrap;", "flex-wrap:nowrap;").replace(' data-pair="1"', ""))


# ── 오늘 한눈에 (2026-10-16 사용자: "주식 초보자도 알기 쉽게" — 가이드 2-4 · 기획 9절) ─────────────────────────────
# 가격 카드 머리 작은 글씨 한 줄(glance_sub) + 평소 범위 밖일 때 펼침 맨 위 설명(glance_rows). 신호등 라벨은 2026-10-17 없앴다(사용자: 조용함 은 뜻을 모른다). 숫자는 전부 파이썬 값, 글은 고정 틀 — 모델이 쓰지 않는다.
GLANCE_TIP = ("평소 범위 : 이 종목의 최근 하루 움직임(최근일수록 무게를 더 둔 흔들림)을 기준으로, 오늘 등락이 그 2배 안이면 '안', 넘으면 '밖'\n"
              "· 평소 하루 ±1.8% : 그 기준 흔들림의 크기\n"
              f"· 함께 적는 것 : 거래량이 평소의 1.5배 이상 · 하루 흔들림(고가−저가) {config.RANGE_PCT_EVENT:.0f}% 이상 · 시장(S&P 500)보다 {config.REL_SPY_EVENT:.0f}%p 이상 다르게 움직인 날\n"
              "· 실적 발표 다음 거래일은 '실적 발표 반응일'로 따로 적는다")


def _glance_state(a):
    """신호등 판정 — 규칙은 GLANCE_TIP 과 같다. (상태, 이유 목록)"""
    h = a["headline"]
    r, sig = abs(h.get("ret_1d") or 0), h.get("ret_sigma_20d")
    nr = a.get("normal_range")
    k = abs(nr["z"]) if nr else (r / sig if sig else None)   # 자 = 검증된 평소 범위 EWMA (2026-10-17, 4단계 W1), 없으면 예전 20일
    vr, rg, vs = h.get("vol_ratio_20d") or 0, h.get("range_pct") or 0, abs(h.get("ret_vs_spy") or 0)
    big, mid = [], []
    if k is not None and k >= 2:
        big.append(f"등락이 평소의 {k:.1f}배")
    elif k is not None and k >= 1:
        mid.append(f"등락이 평소의 {k:.1f}배")
    if vr >= config.VOL_RATIO_EVENT:
        big.append(f"거래량 평소의 {vr:.1f}배")
    elif vr >= 1.5:
        mid.append(f"거래량 평소의 {vr:.1f}배")
    if rg >= config.RANGE_PCT_EVENT:
        big.append(f"하루 흔들림 {rg:.1f}%")
    if vs >= config.REL_SPY_EVENT:
        big.append(f"시장과 {vs:.1f}%p 다르게 움직임")
    # 신호등은 오늘 **움직임의 크기**만 잰다 (2026-10-17 사용자: "한 달 가격 범위의 끝에 닿음은 아래 카드와 중복") —
    # 소식 · 한 달 범위 · 과열은 각자 카드가 있어 판정에서 뺐다. 이유는 늘 숫자 (평소의 몇 배)
    if big:
        return "큰 변화", big + mid
    if mid:
        return "주의", mid
    return "조용함", []


def _plain_rows(rows):
    """펼친 카드 맨 위의 쉬운 말 줄 묶음 (2026-10-16 사용자: "오늘 요약을 별도 영역으로 두지 마, 강조 카드를 펼쳤을 때 추가 내용으로 상단에").
    소제목(14px 회색) 한 줄 아래 본문 한 줄, 항목 사이 10px, 아래 구분선. 홈 카드가 값 줄로 읽지 않게 space-between 을 쓰지 않는다."""
    lis = "".join(f'<div style="margin-top:{0 if i == 0 else 10}px;">' + (f'<div style="font-size:{TINY};line-height:20px;color:{NOTE};">{k}</div>' if k else "") +
                  f'<div style="line-height:{_dk.LH_BODY};color:#111;word-break:keep-all;">{v}</div></div>' for i, (k, v) in enumerate(rows))
    return f'<div style="padding:4px 12px 14px;margin:0 0 8px;border-bottom:1px solid #E2E8F0;">{lis}</div>'


def glance_sub(a):
    """가격 카드 머리 · 가격 줄 아래 작은 글씨 한 줄 (2026-10-17 사용자: 조용함 라벨은 뜻을 모르겠고, 등락률은 가격 줄과 겹친다 → 신호등을 없애고 글로).
    `평소 범위 안 (평소 하루 ±1.8%)` · 바깥이면 `평소 범위 밖 · 평소의 2.2배 (평소 하루 ±2.2%)` · 거래량 · 하루 흔들림 · 시장과 차이가 큰 날은 ` · ` 로 이어 붙인다. 숫자는 전부 파이썬 값."""
    h = a["headline"]
    if h.get("close") is None:
        return ""
    nr, sig, r = a.get("normal_range"), h.get("ret_sigma_20d"), h.get("ret_1d") or 0
    if nr:   # 자 = 검증된 평소 범위(EWMA λ 0.94, 실적 반응일 제외) — 밖 = 평소 하루 흔들림의 2배 이상 (4단계 W1)
        k, sd = abs(nr["z"]), nr["sigma_pct"]
        earn = nr.get("earnings_day")
    elif sig:
        k, sd, earn = abs(r) / sig, sig, False
    else:
        return ""
    if earn:
        first = f"실적 발표 반응일 · 평소의 {k:.1f}배"
    elif k < 2:
        first = "평소 범위 안" + (f" · 평소의 {k:.1f}배" if k >= 1 else "")
    else:
        first = f"평소 범위 밖 · 평소의 {k:.1f}배"
    first += f" (평소 하루 ±{sd:.1f}%)"
    _, reasons = _glance_state(a)
    parts = [first] + [x for x in reasons if not x.startswith("등락이 평소의")]   # 등락 배수는 첫 마디에 있다
    # 우측 정렬은 가격 숫자(`$214.13 ▼1.43%`)의 오른쪽 끝 세로선에 맞춘다 = 접기 버튼 폭 + 왼쪽 여백만큼 안쪽 (2026-10-17 사용자). 툴팁 아이콘은 글자 앞
    return (f'<span style="flex:0 0 100%;min-width:0;box-sizing:border-box;display:block;text-align:right;padding-right:{FOLD_LEFT + _dk.FOLD_BOX}px;margin-top:3px;'
            f'font-size:{TINY};line-height:20px;color:{NOTE};font-weight:400;white-space:normal;word-break:keep-all;">'
            f'{_tipx(GLANCE_TIP)}{_esc(" · ".join(parts))}</span>')


def glance_rows(a, n=None):
    """가격 카드 펼침 맨 위 — 평소 범위 **밖**인 날(충격 국면 아님)의 추가 설명 둘: 지난 1년 횟수 · 우리 검증. 평소 범위 안이면 없다
    (평소 범위 한 줄은 카드 머리 glance_sub 로 옮겼다 — 2026-10-17 사용자)."""
    nr = a.get("normal_range")
    if not nr or nr.get("earnings_day") or abs(nr["z"]) < 2:
        return ""
    extra = [f"지난 1년 이만큼 움직인 날은 {nr['n_year']}번이었다."]
    if not (nr.get("market_shock") or {}).get("active"):   # 충격 국면은 시장 충격 카드가 말한다 (A3)
        extra.append("S&P 500 종목 기준, 평소 국면에서 이렇게 크게 움직인 다음 날 사고판 것은 아무 날에 사고판 것과 다르지 않았다."
                     + _tipx(NORMAL_DAY_TIP))
    return _plain_rows([("", x) for x in extra])


NORMAL_DAY_TIP = ("우리 검증 : 1999년부터 S&P 500 소속 종목(일봉이 있는 568개)에서, 시장 충격이 아닌 때 하루 움직임이 평소의 2배를 넘은 다음 날 시가에 "
                  "팔거나 산 경우를 같은 종목 · 같은 시기의 아무 날과 비교\n"
                  "· 2010~2019년 · 2020년 이후 두 시기 모두 20일 · 60일 뒤 결과가 아무 날과 구분되지 않음\n"
                  "· 크게 움직인 하루는 그 자체로 사고팔 이유가 되지 않았다는 뜻 — 앞으로도 그렇다는 보장은 아님")
SHOCK_TIP = ("시장 충격 국면 : 시장 흔들림 지수(VIX) 종가가 35 이상이면 시작, 25 아래로 내려오면 끝\n"
             "· 1999년 이후 16번 (2010년 이후 9번 : 2010-05 · 2011-08 · 2015-08 · 2018-02 · 2018-12 · 2020-02 · 2022-03 · 2024-08 · 2025-04)\n"
             "· 우리 검증 : S&P 500 소속 종목에서 이 국면 중 급락 다음 날 시가에 판 경우 vs 계속 들고 있던 경우, 아무 날에 판 경우와 비교 — 2010~2019년 · 2020년 이후 모두 판 쪽이 특히 나빴음(종목의 67~79% 가 같은 쪽)\n"
             "· 흔들림이 가라앉는 시간 : 15종목 30년, 충격 첫 5일 흔들림 크기별 중앙값 — 가격 회복 시점이 아님")


def shock_lines(ms):
    lines = [("지금은 시장 충격 국면이다. 시장 흔들림 지수(VIX)가 35를 넘은 " + _fd(ms["start"]) + "에 시작해 오늘로 " + f"{ms.get('days_in') or 1}거래일째이고, "
              "25 아래로 내려오면 끝난 것으로 본다.", "plain"),
             ("과거 S&P 500 종목 기준, 이런 국면에서 급락 다음 날 판 경우는 20거래일 뒤 아무 날에 판 경우보다 약 2~3%p, 60거래일 뒤 약 3~7%p 더 손해였다. "
              "판 것이 나았던 경우도 있었다 — 중앙값 기준이다.", "plain")]
    rec = ms.get("recovery")
    if ms.get("early_complete") and rec:
        lines.append(("row", "충격 첫 5일 흔들림", f"평소의 {ms['early_x']:.1f}배", "1.5배 아래 작음 · 1.8배 넘으면 큼"))
        lines.append(("row", "흔들림이 가라앉기까지 (과거)", f"보통 {rec['median_days']}거래일", f"대개 {rec['q1']}~{rec['q3']}거래일 · 가격이 아니라 흔들림"))
    else:
        lines.append(("충격 첫 5거래일이 지나면 흔들림이 가라앉는 데 걸린 과거 기간을 함께 보여 준다.", "note"))
    if ms.get("vix") is not None:
        lines.append(("row", "VIX 종가", f"{ms['vix']:.1f}", "35 이상 시작 · 25 아래 끝"))
    return lines


def _fd(d):
    y, m, dd = d.split("-")
    return f"{int(y)}년 {int(m)}월 {int(dd)}일"


CHART_H, CHART_LBL = 150, 16


def _legend_chips(items):
    """색 범례 칩 한 줄 — 왼쪽 10px 들여쓰기, 칩 9px (범례 막대와 같은 모양). items = [(이름, 색)]."""
    chips = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 0 0;white-space:nowrap;">'
                     f'<span style="display:inline-block;width:{LEGEND_CHIP}px;height:{LEGEND_CHIP}px;border-radius:2px;background:{c};"></span>{_esc(nm)}</span>' for nm, c in items)
    return f'<span style="display:block;box-sizing:border-box;padding-left:{LEGEND_INDENT}px;font-size:{_dk.BAR_LABEL};line-height:{LH_CARD};color:{NOTE};margin:0 0 10px;">{chips}</span>'


def _col_chart(groups, colors, label_colors, height=CHART_H):
    """세로 막대 그래프 (0 기준선, 위 = 오름 · 아래 = 내림) — groups = [(가로축 이름, [값, ...])], 시리즈마다 색 함수. 값은 막대 끝에 숫자 (2026-10-17 사용자: 그래프화)."""
    vals = [v for _, vs in groups for v in vs if v is not None]
    if not vals:
        return ""
    mp, mn = max(0.0, max(vals)), max(0.0, -min(vals))
    scale = (height - 2 * CHART_LBL) / ((mp + mn) or 1)
    top = CHART_LBL + mp * scale
    n, ns = len(groups), len(groups[0][1])
    parts = [f'<span style="position:absolute;left:0;right:0;top:{top:.1f}px;height:1px;background:#CBD5E1;"></span>']
    for i, (_, vs) in enumerate(groups):
        for k, v in enumerate(vs):
            if v is None:
                continue
            h = max(1.0, abs(v) * scale)
            left = (i + (0.15 + 0.70 * k / ns)) * 100 / n
            width = 0.70 / ns * 100 / n
            y, ly = (top - h, top - h - 15) if v >= 0 else (top, top + h + 1)
            rad = "3px 3px 0 0" if v >= 0 else "0 0 3px 3px"
            parts.append(f'<span style="position:absolute;left:{left:.2f}%;width:{width:.2f}%;top:{y:.1f}px;height:{h:.1f}px;background:{colors[k](v)};border-radius:{rad};"></span>')
            txt = f"{v:+.1f}".replace("-", "−")
            parts.append(f'<span style="position:absolute;left:{left - 2:.2f}%;width:{width + 4:.2f}%;top:{ly:.1f}px;height:14px;line-height:14px;text-align:center;font-size:11px;'
                         f'font-weight:700;white-space:nowrap;color:{label_colors[k](v)};">{txt}</span>')
    xl = "".join(f'<span style="flex:1 1 0;min-width:0;text-align:center;">{_esc(g)}</span>' for g, _ in groups)
    return (f'<span style="display:block;position:relative;height:{height}px;">{"".join(parts)}</span>'
            f'<span style="display:flex;font-size:{TINY};line-height:20px;color:{NOTE};margin:2px 0 6px;">{xl}</span>')


_PASTEL_UP, _PASTEL_DN, _GRAY_BAR = "#F8C4BF", "#BCD3F5", "#CBD5E1"   # 막대 파스텔 — BAR_PASTEL 의 긍정 · 부정과 같은 값
_sign_bg = lambda v: _PASTEL_UP if v > 0 else _PASTEL_DN   # noqa: E731
_sign_fg = lambda v: UP if v > 0 else DOWN   # noqa: E731


PERIODS_TIP = ("기간별 수익률 : 지금 종가가 1주(5거래일) · 1개월(21) · 3개월(63) · 6개월(126) · 1년(252) 전 종가보다 몇 % 올랐거나 내렸는지\n"
               "· 괄호 안은 같은 기간 S&P 500(SPY)의 수익률 — 시장보다 더 올랐는지 덜 올랐는지 비교하는 용도\n"
               "· 과거 수익률이지 앞으로를 말하지 않는다. 우리 검증 : 15종목 30년(1999~), 최근 몇 달 오른 종목이 그 뒤에도 아무 날보다 잘 오르지는 않았다는 결론은 아직 없음 — 판단 유보")
YEAR_TIP = ("1년 가격 범위 : 지난 1년(52주) 동안의 최저가와 최고가(장중 기준) 사이에서 오늘 종가가 어디쯤인지. 오른쪽 끝이 1년 최고가\n"
            "· 최고가 대비 : 1년 최고가보다 몇 % 아래인지\n"
            "· 우리 검증(물림) : 15종목 30년(1999~), 52주 고점 근처 · 볼린저 하단 · 고점 대비 −25% 에서 산 뒤 6개월 · 1년 뒤 산 가격 아래인 비율은 아무 날에 산 것과 다르지 않았다. "
            "아무 날에 사도 6개월 뒤 약 30% 는 산 가격 아래였다")
VOL_TIP = ("거래량 : 오늘 거래된 주식 수가 최근 20일 평균의 몇 배인지. 평소보다 많이 거래된 날은 그만큼 많은 사람이 움직였다는 뜻일 뿐 방향을 말하지 않는다")


def sec_periods(a):
    """기간별 수익률 그래프 (2026-10-17 사용자: 1주 · 1개월 · 3개월 · 6개월 · 1년을 그래프로) — 엔비디아(오름 빨강 · 내림 파랑)와 S&P 500(회색) 세로 막대."""
    ps = [p for p in a.get("periods") or [] if p.get("nvda") is not None]
    if not ps:
        return ""
    pad = _dk.SEP_GAP - _dk.VP - 1
    chart = _col_chart([(p["label"], [p["nvda"], p.get("spy")]) for p in ps], [_sign_bg, lambda v: _GRAY_BAR], [_sign_fg, lambda v: NOTE])
    legend = _legend_chips([("엔비디아 오름", _PASTEL_UP), ("엔비디아 내림", _PASTEL_DN), ("S&P 500", _GRAY_BAR)])
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{MULTI}"><span style="display:block;padding:{pad + 6}px 12px 0;">{chart}{legend}</span></span></div>'
    return _sub_label("기간별 수익률 (%)", PERIODS_TIP) + card


def _multi_single(rows):
    """한 줄 카드 묶음 — `_multi` 와 같은 모양, 데스크톱 2열 없이 한 열."""
    return _multi(rows).replace(' data-grid="2"', "", 1)


def sec_year_range(a):
    """1년 가격 범위 막대 (2026-10-17 사용자: 쉬운 정보로) — 최저 · 최고 사이 오늘 종가 위치 + 최고가 대비 %."""
    y = a.get("year_range")
    if not y:
        return ""
    pad = _dk.SEP_GAP - _dk.VP - 1
    pos = max(0.0, min(100.0, y["pos_pct"]))
    head = (f'<span style="{MULTI_ROW}"><span style="flex:1 1 auto;min-width:0;font-weight:700;color:#111;font-size:{_dk.NAME};">1년 가격 범위{_tipx(YEAR_TIP)}</span>'
            f'<span style="flex:none;text-align:right;white-space:nowrap;{VAL}font-weight:700;"><span style="font-size:{TINY};font-weight:400;color:{NOTE};">(최고가 대비)</span> {_arrow(y["pct_from_high"], 1)}</span></span>')
    track = (f'<span style="display:block;position:relative;height:8px;border-radius:4px;background:#E2E8F0;margin:6px 0 10px;">'
             f'<span style="position:absolute;left:0;top:0;height:8px;width:{pos:.1f}%;border-radius:4px;background:#BFDBFE;"></span>'
             f'<span style="position:absolute;top:-4px;left:{pos:.1f}%;width:16px;height:16px;margin-left:-8px;border-radius:50%;background:#111;border:2px solid #fff;box-sizing:border-box;"></span></span>')
    ends = (f'<span style="display:flex;justify-content:space-between;gap:12px;font-size:{TINY};line-height:20px;color:{NOTE};">'
            f'<span>최저 ${y["low"]:,.2f}</span><span>(오늘 ${y["close"]:,.2f})</span><span>최고 ${y["high"]:,.2f}</span></span>')
    body = f'<span style="display:block;padding:0 12px {pad}px;">{track}{ends}</span>'
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{MULTI}">{head}{body}</span></div>'


DD_TIP = ("고점 하락 후 가격 회복 : 엔비디아 일봉 약 30년(1999년~) 기록에서, 종가가 직전 최고 종가보다 10% · 20% · 30% 넘게 내려갔다가 그 고점을 다시 넘을 때까지 걸린 거래일 수(고점 날짜부터 센다)\n"
          "· 숫자는 '절반은 이 기간 안에 회복했다'는 뜻(중앙값). 나머지 절반은 더 오래 걸렸다 — 분포가 매우 넓다(가장 긴 것 엔비디아 2,138거래일)\n"
          "· 'N번' 은 약 30년 동안 그만큼 내려간 일이 몇 번 있었는지\n"
          "· 엔비디아는 회복이 빨랐던 종목이라 15종목을 합치면 훨씬 오래 걸렸다(−20%: 엔비디아 1년 넘게 25% · 15종목 38%)\n"
          "· 우리 검증(물림) : 15종목 30년, 고점 근처 · 볼린저 하단 · 고점 대비 −25% 에서 산 뒤 6개월 · 1년 뒤 산 가격 아래인 비율은 아무 날에 산 것과 다르지 않았다")
EARN_TIP = ("실적 발표 후 가격 변동 : 엔비디아는 장 마감 뒤에 발표하므로 움직임은 다음 거래일에 나타난다. 평소 하루는 최근 1년 하루 등락 폭의 중앙값\n"
            "· 방향이 아니라 크기를 본다 — 우리 검증 : 15종목 30년(1999~), 예상을 크게 넘긴 실적도 꾸준히 좋은 실적도 발표 다음 거래일 이후 20 · 60 · 250거래일은 아무 날과 다르지 않았다. "
            "발표 다음 날 하루는 예상을 크게 넘기면 평균 +0.9%, 조금 넘기면 오히려 −0.8%, 못 미치면 −2.6% 였다")


def _row_html(left_html, right_html, note="", first=False):
    """카드 한 줄 — 왼쪽(이름 + 아래 작은 설명) · 오른쪽(값, 여러 줄 가능)."""
    pad = _dk.SEP_GAP - _dk.VP - 1
    sep = "" if first else MULTI_SEP
    nt = f'<span style="display:block;margin-top:2px;font-size:{TINY};line-height:20px;color:{NOTE};font-weight:400;white-space:normal;">{note}</span>' if note else ""
    return (f'<span style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:{pad}px 12px;line-height:{LH_CARD};{sep}">'
            f'<span style="flex:1 1 auto;min-width:0;color:#111;font-weight:700;white-space:normal;word-break:keep-all;">{left_html}{nt}</span>'
            f'<span style="flex:none;text-align:right;white-space:nowrap;font-weight:700;{VAL}">{right_html}</span></span>')


def sec_drawdown(a):
    """고점 하락 후 가격 회복 — 약 30년 기록, 엔비디아와 기술주 15개 (2026-10-17 사용자). 숫자 = 절반은 이 거래일 안에 회복."""
    d = a.get("drawdown")
    if not d:
        return ""
    st, pk = d["stats"]["nvda"], d["stats"]["peers"]
    span = _span_label(d["stats"])
    rows = _row_html("지금", _arrow(d["pct_from_high"], 1), f"1년 최고가 이후 {d['days_since_high']}거래일째", first=True)
    over = []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, pk.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None or y.get("median_days") is None:
            continue
        left = f'<span style="color:{DOWN};">−{lv}%</span> 넘게 내려가면'
        note = f"{span} 동안 엔비디아 {x['n']}번 · 기술주 15개 합쳐 {y['n']}번"
        right = f'엔비디아 {x["median_days"]}일<br>기술주 15개 {y["median_days"]}일'
        rows += _row_html(left, right, note)
        over.append(f"−{lv}% 엔비디아 {x['over_year'] / x['recovered'] * 100:.0f}% · 기술주 15개 {y['over_year'] / y['recovered'] * 100:.0f}%")
    tail = (f'<span style="display:block;{MULTI_SEP}padding:{_dk.SEP_GAP - _dk.VP - 1}px 12px;font-size:{TINY};line-height:20px;color:{NOTE};">'
            f'회복에 1년(250거래일) 넘게 걸린 비율 — {_esc(" / ".join(over))}</span>') if over else ""
    return _sub_label(f"고점 하락 후 가격 회복 ({span} 기록 · 절반은 이 거래일 안에 회복)", DD_TIP) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{MULTI}">{rows}{tail}</span></div>'


def sec_earnings(a):
    """실적 발표 후 가격 변동 — 다음 발표 · 발표 다음 날 보통 변동 · 최근 8번 막대 (2026-10-17 사용자). 방향이 아니라 크기만."""
    em = a.get("earnings_moves")
    nxt = a.get("next_earnings")
    if not em and not nxt:
        return ""
    rows, first = "", True
    if nxt:
        try:
            md = datetime.date.fromisoformat(str(nxt)[:10])
            left = (md - datetime.date.fromisoformat(a["day"])).days
            rows += _row_html("다음 실적 발표", f"{left}일 뒤" if left > 0 else "오늘", f"{md.month}월 {md.day}일 · 장 마감 뒤", first=first)
            first = False
        except ValueError:
            pass
    if em:
        n = len(em["moves"])
        times = em["median_abs"] / em["normal_abs"] if em["normal_abs"] else None
        note = f"최근 {n}번 기준" + (f" · 평소 하루 ±{em['normal_abs']:.1f}%의 약 {times:.0f}배" if times else "")
        rows += _row_html("발표 다음 날 보통 변동", f"±{em['median_abs']:.1f}%", note, first=first)
        chart = _col_chart([(f"{m['day'][2:4]}.{m['day'][5:7]}", [m["ret"]]) for m in em["moves"]], [_sign_bg], [_sign_fg], height=130)
        rows += (f'<span style="display:block;{MULTI_SEP}padding:{_dk.SEP_GAP - _dk.VP - 1}px 12px 0;">'
                 f'<span style="display:block;font-weight:700;color:#111;margin:0 0 6px;">최근 {n}번의 실적 발표 다음 날 (%)'
                 f'<span style="font-size:{TINY};font-weight:400;color:{NOTE};"> (왼쪽이 오래된 것 · 아래 숫자는 연.월)</span></span>{chart}</span>')
    return _sub_label("실적 발표 후 가격 변동", EARN_TIP) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{MULTI}">{rows}</span></div>'


def sec_headline(a, n=None):
    """오늘 한 줄 — 한 줄 카드 6장 (NVDA · SPY·SMH·AMD·AVGO 대비 · 거래량). 카드 안에 카드를 만들지 않는다.

    컨테이너 div 는 꾸밈 없음(data-cards 표시만) — 홈 카드의 linesOf 가 이 div 를 잎으로 보고 한 줄로 읽는다.
    """
    h = a["headline"]
    if h.get("close") is None:
        return f'<div style="{CARD}">휴장 — 시세는 다음 거래일에 채워집니다. 공시·기사·일정만 아래에 있습니다.</div>'
    r = h.get("ret_1d") or 0
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = ROW_UP if r > 0 else ROW_DOWN if r < 0 else ""
    bg, bd = ("#FFF7ED", "#FED7AA") if r > 0 else ("#EFF6FF", "#BFDBFE") if r < 0 else ("#fff", "#E2E8F0")
    # 가격 줄 맨 오른쪽 공식 접기 버튼, 기본 닫힘 — 펼치면 평균 대비 · 비교 · 시가 갭 등 (2026-10-13 사용자, 가이드라인 10-7). 버튼은 값 칸 안 — 홈 카드가 값 칸 글자를 읽는다
    price = (f'<span style="display:inline-flex;align-items:center;justify-content:flex-end;">'
             f'<span style="color:{pcol};font-weight:700;">${h["close"]:,.2f}</span>&nbsp;{_arrow(h.get("ret_1d"))}'
             f'{_fold_btn(_dk.lighten(bg), bd) if r else ACC_BTN}</span>')
    head = _row("NVDA", price, tone).replace("margin:0 0 6px;", "margin:0;", 1)
    sub = glance_sub(a)
    if sub:   # 같은 카드 안 두 번째 줄 — 가격 줄 아래 작은 글씨 (2026-10-17 사용자). 홈 카드는 data-acc 안을 읽지 않아 영향 없다
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1)   # 위쪽 여백 16 → 6px (60% 줄임, 2026-10-17 사용자) — 공통 gap:12px 가 세로 간격까지 12 로 덮어쓰고 있었다
        k = head.rstrip().rfind("</span>")
        head = head[:k] + sub + head[k:]
    # 펼침 1층 = 초보자도 읽는 정보 (2026-10-17 사용자: 평균선 · 갭 같은 차트 지표는 우리 방향과 다르다) — 기간별 수익률 · 1년 가격 범위 · 거래량.
    # 2층(접힘) = 차트 보는 분을 위한 지표 — 평균선 · 1일 비교 · 시가 갭 · 일중 변동폭 · 과열(RSI) · 교차, 우리 검증은 ? 툴팁
    rows = glance_rows(a, n) + sec_periods(a) + sec_year_range(a) + sec_drawdown(a) + sec_earnings(a)
    vr = h.get("vol_ratio_20d")
    rows += f'<div data-cards="1" style="margin:0 0 8px;">{_multi_single([("거래량 (평소의 몇 배)", f"<span style=\"font-weight:700;\">{_esc(rr.fmt(vr, 'x'))}</span>", VOL_TIP)])}</div>'
    deep = sec_ma(a)
    deep += _multi2([(f"{tk} 대비", _arrow(h.get(key), 2, "%p")) for key, tk in (("ret_vs_spy", "SPY"), ("ret_vs_smh", "SMH"), ("ret_vs_amd", "AMD"), ("ret_vs_avgo", "AVGO"))])   # 하루 등락 차이 (2026-10-11 사용자)
    items = []
    pc = {c["key"]: c for c in (a["status"].get("price") or [])}
    items.append(("시가 갭", _arrow((pc.get("gap") or {}).get("value"), 2), GAP_TIP))
    rg = pc.get("range_pct") or {}
    items.append((f"일중 변동폭 (고가−저가 · 흔히 {config.RANGE_PCT_EVENT:.0f}% 넘으면 큰 흔들림으로 봄)", f'<span style="color:#111;font-weight:700;">{_esc(rr.fmt(rg.get("value"), "pct"))}</span>'))
    tc = {c["key"]: c for c in (a["status"].get("technical") or [])}
    rsi = (tc.get("rsi14") or {}).get("value")
    items.append(("단기 과열 온도 (RSI 14 · 흔히 70 넘으면 과열 · 30 아래면 침체로 읽음)", f'<span style="color:#111;font-weight:700;">{rsi:.1f}</span>' if rsi is not None else f'<span style="color:{MUTED};">—</span>', RSI_TIP))
    mc = (tc.get("ma_cross") or {}).get("value")
    mc_html = {"golden": f'<span style="color:{UP};font-weight:700;">골든크로스</span>', "dead": f'<span style="color:{DOWN};font-weight:700;">데드크로스</span>'}.get(
        mc, f'<span style="color:{MUTED};">교차 없음</span>')
    items.append(("평균선 교차 (50일선이 200일선 위로 = 골든크로스)" + _new(a, "status:ma_cross"), mc_html, CROSS_TIP))
    if a.get("macro_today"):
        items.append(("거시 일정", _esc(", ".join(a["macro_today"]))))
    deep += _multi(items)
    rows += (f'<details data-fold="1" data-label="차트 지표 보기" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;">{_fold_row("차트 지표 보기")}</summary>'
             f'<div style="margin-top:6px;">{deep}</div></details>')
    out = (f'<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>'
           f'<div style="margin-top:6px;">{rows}</div></details></div>')
    out += sec_state_cards(a)   # 시장 국면 · 반도체 자금 — 이유를 담은 별도 카드 둘 (2026-10-11 사용자)
    if not a.get("is_latest_bar_today"):
        out += _muted("기준 거래일이 최신이 아닐 수 있습니다 — 일봉 수집 상태를 확인하세요.")
    return out


RSI_TIP = ("단기 과열 온도(RSI 14) : 최근 14일 오른 힘의 비율 0~100. 흔히 70 넘으면 과열, 30 아래면 침체로 읽는다\n"
           "· 우리 검증 : 15종목 30년(1999~), RSI 가 70 을 넘거나 30 아래로 내려간 뒤 20 · 60거래일은 아무 날과 다르지 않았다")
CROSS_TIP = ("평균선 교차 : 50일 평균선이 200일 평균선 위로 올라서면 골든크로스, 아래로 내려가면 데드크로스\n"
             "· 우리 검증 : 15종목 30년(1999~), 골든크로스 · 데드크로스 뒤 20 · 60거래일은 아무 날과 다르지 않았다 — 2010년대와 2020년 이후 방향도 서로 반대였다")
GAP_TIP = ("시가 갭 : 오늘 시가가 전날 종가보다 몇 % 높게(▲) 또는 낮게(▼)시작했는지\n"
           "· 밤사이 실적 · 뉴스 · 해외 시장이 반영된 출발 위치\n"
           "· 갭이 크면 장 초반 변동이 커지기 쉽다 — 장중에 메워지기도 한다")   # 2026-10-14 사용자: "시가 갭은 뭔지 툴팁"


REGIME_THEME = {"상승 추세": ("positive", UP), "단기 조정": ("neutral", MUTED), "조정장": ("negative", DOWN), "불안 국면": ("neutral", MUTED)}   # 불안 국면 노랑 → 회색 (2026-10-17 W7: 노랑 강조는 시장 충격 국면만)
FLOW_THEME = {"모이는 중": ("positive", UP), "빠져나가는 중": ("negative", DOWN), "뚜렷하지 않음": ("neutral", MUTED)}


PEERS_DEF = ("기술주 15개 : 엔비디아와 비교하려고 고른 미국 대형 기술주 — 반도체 10개(엔비디아 · AMD · 퀄컴 · 브로드컴 · 어플라이드머티어리얼즈 · 램리서치 · KLA · 마이크론 · 인텔 · 텍사스인스트루먼츠) "
             "+ 대형 기술 5개(애플 · 마이크로소프트 · 아마존 · 알파벳 · 시스코). 오늘 살아남은 종목들이라 실제보다 낙관적으로 나올 수 있다 (2026-10-17 사용자: 15종목이 무엇인지 설명)")


def _tipx(text):
    """툴팁 아이콘 — 글에 `15종목` 이 있으면 `기술주 15개` 로 바꾸고 구성 한 줄을 붙인다."""
    if text and "15종목" in text:
        text = text.replace("15종목", "기술주 15개") + "\n· " + PEERS_DEF
    return _dk.tip_icon(text)


def _title_with_icon(title, tail_html):
    """제목 + 툴팁 아이콘 · N 알약 — 마지막 단어와 아이콘을 줄바꿈 없이 묶어 아이콘이 다음 줄로 떨어지지 않게 (2026-10-17 사용자: 툴팁 아이콘은 타이틀 옆)."""
    t = _esc(title)
    head, sep, last = t.rpartition(" ")
    if not sep:
        return f'<span style="white-space:nowrap;">{_paren(t)}{tail_html}</span>'
    return f'{_paren(head)} <span style="white-space:nowrap;">{_paren(last)}{tail_html}</span>'


def _est_w(text, px):
    """글자 폭 어림 (px) — 한글 등 전각은 글자 크기만큼, 영문 · 숫자 · 기호는 0.55배."""
    return sum(px if ord(ch) > 0x2E80 else px * 0.55 for ch in str(text))


INLINE_W = 316   # 상태 카드 줄 안쪽 폭 어림 (390px 폰 − 여백 · 카드 안쪽) − 이름과 값 사이 간격


def _state_card(title, state, theme, color, lines, new_html="", tip="", fold=False, inline_notes=False):
    """상태 카드 (가이드라인 2-1 D, 2026-10-11 사용자: "별도 카드로 분리하고 이유도 카드에 포함" → "안내 아이콘 삭제, 글씨 검정, 블릿으로").
    첫 줄 구분명 좌·상태 우, 아래 얇은 선 뒤에 이유 글머리표(16px, 검정). 이유 묶음은 border-top — 홈 카드는 border-top 요소를 건너뛰므로 홈에는 첫 줄만 간다."""
    bg, bd = CARD_DIR[theme]
    # 글머리표는 3px 점, 글자 14px (2026-10-11 사용자). 규칙 줄은 안내 색(NOTE). lines 항목은 str 또는 (str, "note")
    def li(item):
        # 항목: str · (str, "note") · (str, "plain") · ("row", 이름, 값, 뜻)
        kind = "row" if isinstance(item, tuple) and item[0] == "row" else ("" if isinstance(item, str) else item[1])
        text = item if isinstance(item, str) else item[0]
        if kind == "row":   # 근거 줄 — 블릿 · 콜론 없이 이름 왼쪽 | 값 오른쪽, 아래 14px 회색 뜻 (2026-10-16 사용자: "블릿과 근거 사이 점들이 헷갈린다, 근거를 자세히")
            _, name, value, note = item
            multi = "\n" in str(value)
            fits = _est_w(name, 17) + _est_w(f"({note})", 14) + _est_w(value, 17) <= INLINE_W
            inline = bool(note) and not multi and (fits or inline_notes)   # 설명을 괄호로 이름 옆에 (2026-10-17 사용자). inline_notes=True 면 길어도 모두 괄호 — 줄이 바뀐다
            if multi:   # 값이 여러 줄이면 설명은 이름 아래 왼쪽 — 줄 수를 늘리지 않는다 (2026-10-17 사용자: 모바일에서 여러 단 쓰지 말 것)
                vals = _tint(_esc(value)).replace(chr(10), "<br>")
                return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd};">'
                        f'<span style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">'
                        f'<span style="flex:none;color:#111;">{_esc(name)}<span style="display:block;margin-top:2px;font-size:{TINY};line-height:20px;color:{NOTE};">{_esc(note)}</span></span>'
                        f'<span style="min-width:0;text-align:right;font-weight:700;word-break:keep-all;">{vals}</span></span></li>')
            if inline:
                lw = "flex:1 1 auto;min-width:0;word-break:keep-all;" if not fits else "flex:none;white-space:nowrap;"   # 안 들어가면 왼쪽 칸 안에서 줄바꿈
                return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd};">'
                        f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
                        f'<span style="{lw}color:#111;">{_esc(name)} <span style="font-size:{TINY};color:{NOTE};">({_esc(note)})</span></span>'
                        f'<span style="flex:none;text-align:right;font-weight:700;white-space:nowrap;">{_tint(_esc(value))}</span></span></li>')
            return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd};">'
                    f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
                    f'<span style="flex:none;white-space:nowrap;color:#111;">{_esc(name)}</span><span style="min-width:0;text-align:right;font-weight:700;word-break:keep-all;">{_tint(_esc(value)).replace(chr(10), "<br>")}</span></span>'
                    + (f'<span style="display:block;margin-top:2px;font-size:{TINY};line-height:20px;color:{NOTE};">{_esc(note)}</span>' if note else "") + '</li>')
        if kind == "plain":   # 쉬운 말 한 줄 — 점 없이 굵게, 아래 8px (2026-10-16 사용자: 강조 카드 펼침 맨 위에 쉬운 설명)
            return f'<li style="list-style:none;margin:9px 0 17px;font-weight:400;color:#111;line-height:{_dk.LH_EMPH};word-break:keep-all;">{_tint(_esc(text))}</li>'   # 상세 설명 2~3문장이라 보통 굵기 (2026-10-17)
        col = NOTE if kind == "note" else "#111"
        return _dot_li(_label_text(text), size=3, color=col, lh=_dk.LH_EMPH)   # 강조 카드 18px 글 → 행간 32 (2026-10-12 사용자)   # 16px → 3px 점, "**라벨** : 내용", 증감 색 (2026-10-11 사용자)
    lis = "".join(li(t) for t in lines)
    # fold: 첫 줄 맨 오른쪽 공식 접기 버튼(카드 색 20% 밝은 바탕), 기본 닫힘 — 펼치면 이유 글머리표 (2026-10-13 사용자: 시장 국면 · 반도체 자금, 가이드라인 10-7)
    state_html = (f'<span style="display:inline-flex;align-items:center;">{_esc(state)}{_fold_btn(_dk.lighten(bg), bd)}</span>' if fold else _esc(state))
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;">'   # position:relative — 툴팁 상자가 이 줄(카드 폭) 기준으로 놓인다
            f'<span style="{"flex:1 1 auto;min-width:0;" if fold else COL_L}font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};">{_title_with_icon(title, _tipx(tip) + new_html)}</span><span style="{"flex:none;white-space:nowrap;" if fold else COL_R}font-weight:700;color:{color};">{state_html}</span></span> ')   # fold: 상태 + 버튼은 한 줄, 이름 칸이 남은 폭
    body = (f'<div style="margin-top:{14 - _dk.VP_EMPH}px;padding-top:{14 - _dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{SMALL};">'   # 제목 ~ 구분선 14 · 구분선 ~ 글 14 (보이는 여백, 2026-10-12 사용자)
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul></div>")   # 음수 margin = 첫·끝 li 의 9px 지우기
    inner = (f'<details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>{body}</details>' if fold else head + body)
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{_dk.EMPH_PAD - _dk.VP_EMPH}px 14px;margin:0 0 8px;line-height:{_dk.LH_EMPH};">'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)
            f'{inner}</div>')


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


# 상태 카드 제목에 원래 용어 괄호를 두지 않는다 (2026-10-16 사용자: "() 내용은 삭제") — 용어는 ? 툴팁 규칙 글과 읽는 법 페이지에
# 쉬운 말 줄도 1절 규칙 — 평가어("좋음 · 조심") 없이 상태만 (2026-10-16)
REGIME_PLAIN = {"상승 추세": "시장이 1년 최고가 근처", "단기 조정": "시장이 고점보다 3~10% 아래",
                "조정장": "시장이 고점보다 10% 넘게 아래", "불안 국면": "시장 흔들림(VIX) 30 이상"}
FLOW_PLAIN = {"모이는 중": "한 달간 반도체가 시장보다 강함", "빠져나가는 중": "한 달간 반도체가 시장보다 약함",
              "뚜렷하지 않음": "한 달간 반도체와 시장 차이 작음"}


def regime_plain(mr):
    """2번 카드 첫 줄 — 값으로 만든 2문장 (2026-10-17 사용자: 상세하게 → "약간만 줄여"). 평가어 없이."""
    ph, above = mr["pct_from_high"], mr["above_ma200"]
    where = f"1년 최고가보다 {abs(ph):.1f}% 아래" if ph < -0.05 else "1년 최고가 근처"
    pm = mr.get("pct_vs_ma200")
    ma_part = f"200일 평균선보다 {abs(pm):.1f}% {'위' if above else '아래'}" if pm is not None else f"200일 평균선 {'위' if above else '아래'}"   # 괄호 설명은 첫 줄에 두지 않는다 (2026-10-17 사용자)
    first = f"S&P 500이 {where}, {ma_part}, '{mr['regime']}'이다."   # 사용자 문구 (2026-10-17)
    vix = mr.get("vix")
    if vix is not None:
        calm = "차분한 편" if vix < 20 else ("보통보다 높은 편" if vix < config.REGIME_VIX_HIGH else "크게 흔들리는 편")
        first += f" 시장 흔들림(VIX)은 {vix:.1f}로 {calm}이다."
    return first

def regime_lines(mr):
    """2번 카드 — 상세 첫 줄 + 근거 줄(이름 | 값 · 짧은 뜻). 규칙 전체는 툴팁 (regime_rule)."""
    pb, cr = abs(config.REGIME_PULLBACK_PCT), abs(config.REGIME_CORRECTION_PCT)
    st = mr.get("streak") or 0
    lines = [(regime_plain(mr), "plain"),
             ("row", "S&P 500 고점 대비", f"{mr['pct_from_high']:+.1f}%", f"−{pb:.0f}% 안 상승 추세 · −{cr:.0f}% 넘으면 조정장"),
             ("row", "200일 평균선과의 거리", (f"{mr['pct_vs_ma200']:+.1f}%" if mr.get("pct_vs_ma200") is not None else ("위" if mr["above_ma200"] else "아래")),
              "약 10개월 평균 가격보다 아래로 내려가면 조정장")]   # 사용자 문구 (2026-10-17)
    if mr.get("vix") is not None:
        lines.append(("row", "시장 흔들림 (VIX)", f"{mr['vix']:.1f}", f"20 아래 차분 · {config.REGIME_VIX_HIGH:.0f} 넘으면 불안"))
    lines.append(("row", "연속 등락", (f"{abs(st)}일 {'상승' if st > 0 else '하락'}" if st else "보합"), "S&P 500 같은 방향 마감 일수"))
    if mr.get("fng"):   # CNN 공포·탐욕 지수 — 국면 판정에는 쓰지 않고 보여 주기만
        lines.append(("row", "공포·탐욕 지수", f"{mr['fng']['score']:.0f} {mr['fng'].get('rating_ko') or mr['fng'].get('rating')}", "CNN 투자 심리 · 0 공포 ~ 100 탐욕"))
    return lines


def flow_plain(sf):
    """3번 카드 첫 줄 — 2문장 (2026-10-17 사용자)."""
    pp, rel, n = config.SECTOR_FLOW_PP, sf["rel_pp"], sf["days"]
    more = f"{abs(rel):.1f}%p 더 올랐다" if rel > 0.05 else (f"{abs(rel):.1f}%p 덜 올랐다" if rel < -0.05 else "비슷하게 움직였다")
    tail = {"모이는 중": f"차이가 +{pp:.0f}%p를 넘어 돈이 반도체로 모이는 중이다.",
            "빠져나가는 중": f"차이가 −{pp:.0f}%p 아래라 돈이 반도체에서 빠지는 중이다."}.get(sf["state"], f"차이가 ±{pp:.0f}%p 안이라 돈의 방향은 뚜렷하지 않다.")
    return f"최근 {n}거래일 반도체 ETF가 S&P 500보다 {more}. {tail}"

def sector_flow_lines(sf):
    """3번 카드 — 상세 첫 줄 + 근거 줄. 규칙 전체는 툴팁 (sector_flow_rule)."""
    pp = config.SECTOR_FLOW_PP
    lines = [(flow_plain(sf), "plain"),
             ("row", f"반도체 vs 시장 ({sf['days']}일)", f"{sf['rel_pp']:+.1f}%p", f"+{pp:.0f}%p 넘으면 유입 · −{pp:.0f}%p 아래면 유출")]
    if sf.get("smh_rank"):
        lines.append(("row", "섹터 순위", f"12개 중 {sf['smh_rank']}위", "같은 기간 수익률 순"))
    secs = sf.get("sectors") or []
    if secs:
        lines.append(("row", "앞선 섹터", "\n".join(f"{x['name']} {x['rel']:+.1f}%p" for x in secs[:2]), "시장보다 많이 오른 섹터"))   # 섹터마다 한 줄 (2026-10-17 사용자)
        lines.append(("row", "뒤처진 섹터", "\n".join(f"{x['name']} {x['rel']:+.1f}%p" for x in secs[-2:][::-1]), "시장보다 내린 섹터"))
    if sf.get("shares_5d") is not None:
        lines.append(("row", "반도체 ETF 주식 수 (5일)", f"{sf['shares_5d']:+.1f}%", "늘면 유입 · 줄면 유출"))
    return lines


BOLL_THEME = {"하단 도달": ("negative", DOWN), "상단 도달": ("positive", UP)}


def bollinger_rule():
    return (f"규칙: 20일 평균 ± 2σ 밴드. 종가가 하단 이하면 '하단 도달', 상단 이상이면 '상단 도달'. %B = (종가 − 하단) ÷ (상단 − 하단), 0 = 하단 · 1 = 상단. "
            f"밴드 안에 있는 날은 카드를 두지 않는다. 과거 통계는 진입일의 빈도이지 예측이 아니다\n"
            f"· 하락 범위 · 상승 범위 : 한 달 평소 범위(20일 평균 ± 2σ)의 아래 끝 이하 · 위 끝 이상. 지금 가격이 어디에 있는지를 말할 뿐 앞으로를 말하지 않는다\n"
            f"· 우리 검증 (하단) : 15종목 30년(1999~), 하단에 처음 닿은 날 산 뒤 가장 좋은 때 팔았다고 쳐도 아무 날에 산 것과 다르지 않았다 — "
            f"하단 무렵은 위아래로 크게 흔들리는 때일 뿐 바닥은 아니었다")


def _span_label(stats):
    """통계가 다룬 기간 — "약 30년 · 약 20년 · 약 10년" (2026-10-17 사용자). 시작 · 끝 날짜에서 가까운 10년 단위로."""
    try:
        yrs = (datetime.date.fromisoformat(stats["to"]) - datetime.date.fromisoformat(stats["from"])).days / 365.25
    except (KeyError, TypeError, ValueError):
        return "과거"
    return f"약 {max(10, round(yrs / 10) * 10)}년"


def bollinger_lines(bb):
    """4번 카드 — 상세 첫 줄 + 근거 줄 (2026-10-17 사용자)."""
    low = bb["state"] == "하단 도달"
    st = (bb.get("stats") or {}).get("boll_lower" if low else "boll_upper")
    base = (bb.get("stats") or {}).get("base") or {}
    zone, days = ("하락" if low else "상승"), bb.get("days", 0)   # 2026-10-17 사용자: "아래 끝을 넘어 있다" 대신 "하락 범위에 닿음"
    reach = "닿았다" if days <= 1 else f"{days}일째 닿아 있다"
    plain = f"최근 한 달 평소 ${bb['lower']:,.0f}~${bb['upper']:,.0f}에서 움직였는데 오늘 ${bb['close']:,.2f}로 {zone} 범위에 {reach}."   # 2문장 (2026-10-17 사용자: 약간만 줄여)
    lines = [(plain, "plain"),
             ("row", "한 달 범위", f"${bb['lower']:,.0f} ~ ${bb['upper']:,.0f}", "20일 평균 ± 보통 흔들림 2배"),
             ("row", "오늘 종가", f"${bb['close']:,.2f}", f"{zone} 범위")]
    if bb.get("days", 0) > 1:
        lines.append(("row", "연속", f"{bb['days']}일째", f"{zone} 범위에 머문 날"))
    if st and base:
        lines.append(("row", f"{_span_label(bb.get('stats'))} 같은 날", f"{st['n']}회", f"{zone} 범위에 처음 닿은 날"))
        lines.append(("row", "20일 뒤 오른 비율", f"{st['up20']}%", f"일반적인 날 {base['up20']}%"))
        lines.append(("row", "60일 뒤 오른 비율", f"{st['up60']}%", f"일반적인 날 {base['up60']}% · 예측 아님"))
    return lines


def overheat_rule():
    return (f"규칙: RSI 14 ≥ {config.OVERHEAT_RSI:.0f} · 종가가 200일 평균보다 +{config.OVERHEAT_MA200_PCT:.0f}% 이상 위 · 20거래일 수익률 +{config.OVERHEAT_RET20_PCT:.0f}% 이상. "
            f"하나라도 해당하는 날만 카드. 통계는 그 조건에 처음 들어간 날의 20·60일 뒤 수익률 빈도이지 예측이 아니다\n"
            f"· 우리 검증 : 15종목 30년(1999~), 과열 조건에 처음 들어간 뒤 20 · 60거래일은 아무 날과 다르지 않았다 — "
            f"과열이라고 더 떨어지지도, 더 크게 빠지지도 않았다")


OVERHEAT_SHORT = {"rsi80": ("단기 과열 온도 (RSI 14)", "80 이상", "", "14일 오른 힘 비율 0~100"),
                  "ma200_40": ("200일 평균선과의 거리", "+40% 이상", "%", "10개월 평균보다 얼마나 위"),
                  "ret20_25": ("20일 수익률", "+25% 이상", "%", "한 달 동안 오른 폭")}
OVERHEAT_PLAIN = {"rsi80": "단기 과열 온도(RSI 14)가 {v:.0f}로 기준 80을 넘었다",
                  "ma200_40": "가격이 200일 평균선보다 {v:.0f}% 위로 기준 40%를 넘었다",
                  "ret20_25": "최근 20거래일 동안 {v:.0f}% 올라 기준 25%를 넘었다"}


def overheat_lines(oh):
    """과열 카드 — 상세 첫 줄 + 조건마다 근거 줄 (2026-10-17 사용자: 2번 카드와 같게)."""
    stats, base = (oh.get("stats") or {}), ((oh.get("stats") or {}).get("base") or {})
    parts = [OVERHEAT_PLAIN[k].format(v=oh["values"].get(k) or 0) for k in oh["active"]]
    plain = " · ".join(parts) + "."
    k0 = oh["active"][0] if oh["active"] else None
    lines = [(plain, "plain")]
    for k in oh["active"]:
        name, rule, unit, note = OVERHEAT_SHORT[k]
        v = oh["values"].get(k)
        lines.append(("row", name, (f"{v:+.1f}{unit}" if unit else f"{v:.1f}"), f"기준 {rule} · {note}"))
        st = stats.get(k) or {}
        if st and base:
            lines.append(("row", f"{_span_label(stats)} 같은 날", f"{st['n']}회", "이 조건에 처음 들어간 날"))
            lines.append(("row", "20일 뒤 오른 비율", f"{st['up20']}%", f"일반적인 날 {base['up20']}%"))
            lines.append(("row", "60일 뒤 오른 비율", f"{st['up60']}%", f"일반적인 날 {base['up60']}% · 예측 아님"))
    return lines


def sec_state_cards(a):
    out = ""
    ms = (a.get("normal_range") or {}).get("market_shock") or {}
    if ms.get("active"):   # 시장 충격 국면 (4단계 W2 · 적용 기준 A3) — 강조를 쓰는 유일한 경우, 그날만 맨 앞
        out += _state_card("시장 충격 국면은?", "충격 국면 중", "uncertain", WARN, shock_lines(ms), "", tip=SHOCK_TIP, fold=True)
    mr = a.get("market_regime")
    if mr:
        theme, col = REGIME_THEME.get(mr["regime"], ("neutral", MUTED))
        out += _state_card("시장 분위기는?", mr["regime"], theme, col, regime_lines(mr), _new(a, "regime"), tip=regime_rule(), fold=True)
    sf = a.get("sector_flow")
    if sf:
        theme, col = FLOW_THEME.get(sf["state"], ("neutral", MUTED))
        out += _state_card("반도체로 돈이 올까?", sf["state"], theme, col, sector_flow_lines(sf), _new(a, "sector_flow"), tip=sector_flow_rule(), fold=True)
    bb = a.get("bollinger")
    if bb and bb.get("state") in BOLL_THEME:   # 하단·상단에 닿은 날만 (2026-10-11 사용자)
        theme, col = BOLL_THEME[bb["state"]]
        out += _state_card("한 달간 변화 범위는?", {"하단 도달": "하락 범위에 닿음", "상단 도달": "상승 범위에 닿음"}[bb["state"]], theme, col, bollinger_lines(bb), "", tip=bollinger_rule(), fold=True, inline_notes=True)   # 작은 글씨는 모두 괄호 (2026-10-17 사용자)   # 접기 버튼 (2026-10-16 사용자: 시장 국면 · 반도체 자금과 같게)
    oh = a.get("overheat")
    if oh and oh.get("active"):   # 과열 조건 하나라도 해당하는 날만 (2026-10-11 사용자) — 노랑(불확실) 테마, 상태 = 해당 조건 수
        out += _state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", MUTED, overheat_lines(oh), "", tip=overheat_rule())   # 노랑 → 회색 (2026-10-17 W7)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""   # 데스크톱에서 2열 (테마 CSS, 2026-10-11 사용자)


def _chart_json(output_dir=None):
    path = os.path.join(output_dir or config.OUTPUT_DIR, "chart.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sec_chart(output_dir=None, a=None):
    """가격 그래프 (chart_price.py가 만든 chart.json) — 본문 맨 앞, 탭 줄 위 (2026-10-13 사용자: 증시 리포트 커버 이미지 자리 · 여백). 없으면 빈 문자열.
    data-cards 가 없어 테마 탭 JS가 첫 탭으로 옮기지 않는다. <img>는 글자가 없어 홈 카드에 잡히지 않는다."""
    c = _chart_json(output_dir)
    if not c:
        return ""
    zoom = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')
    # 확대 보기: 그림 전체가 원본 링크(새 창), 오른쪽 아래 돋보기 아이콘 (2026-10-11 사용자). 아래 16px = 데일리 커버 이미지 (2026-10-13 사용자)
    # data-zoom: 테마 JS 가 새 창 대신 전체 화면 팝업 + 가로 스크롤로 연다 (2026-10-16 사용자, 가이드 8절). JS 없으면 원본 링크
    return (f'<a href="{_esc(c["url"])}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{_esc(c["url"])}" alt="NVDA {c.get("window", 30)}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{zoom}</span></a>')


def sec_ma(a=None, output_dir=None):
    """평균선 대비 카드 (E타입 2열: 20일|60일 / 120일|200일) — 현재가가 n일 평균선보다 몇 % 위·아래 (2026-10-11 사용자).
    NVDA 가격 카드 바로 아래 (2026-10-13 사용자: "20일 평균이 있는 카드는 엔비디아 가격 카드 아래로")."""
    c = _chart_json(output_dir) or {}
    mr = c.get("ma_rel") or {}
    items = [(f"{n}일 평균", _arrow(mr[n], 1)) for n in ("20", "60", "120", "200") if mr.get(n) is not None]   # 5일선 삭제, 이름은 'n일 평균' (2026-10-11 사용자)
    return f'<div data-cards="1" style="margin:0 0 8px;">{_multi2(items)}</div>' if items else ""


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
        fact = ""
    else:
        head = _esc(e["title"])
        fact = f" — {_esc(e['fact'])}" if e.get("fact") and e["fact"] != e["title"] else ""
    when = f' <span style="color:{SUB};font-size:{TINY};white-space:nowrap;">({_esc(_d(e["published_at"][:10]))})</span>' if e.get("published_at") else ""   # 날짜가 두 줄로 쪼개지지 않게
    # 라벨 줄: 여백 없이 왼쪽 정렬, 기사 맨 아래 (2026-10-13 사용자) · 라벨 사이 3px (2026-10-14 사용자: 0 → 3, 가이드라인 10-7)
    lab = f'<span style="display:block;line-height:1;margin:8px 0 0;">{tag.replace(f"margin:0 {_dk.PILL_GAP}px;", "margin:0 3px 0 0;").replace("</span> <span", "</span><span")}</span>'
    # 일반 기사와 강조 카드 모두: 새 창 아이콘 없이 제목이 원문 링크 → 사실 · 날짜 → 라벨 줄 (2026-10-13 사용자: "강조 카드 내의 정보는 일반 뉴스의 정보 배치로")
    tip_t = _esc(f"{src}: {e['title'][:90]}" if e["kind"] in rr.DOC_KINDS else f"{src} 원문").replace(chr(34), "&quot;")
    head_html = (f'<a href="{_esc(e["url"])}" title="{tip_t}" target="_blank" rel="noopener" style="font-weight:700;color:#111;text-decoration:none;">{head}</a>'
                 if e.get("url") else f'<span style="font-weight:700;color:#111;">{head}</span>')
    if e.get("emphasis"):   # 법무·규제 등 우선 영역: 굵게·크게 대신 연한 배경 카드 (가이드라인 2절) — 배경 · 테두리만 방향 색
        bg, bd = CARD_DIR.get(e.get("direction"), CARD_DIR["neutral"])
        return (f'<div style="background:{bg};border:1px solid {bd};border-radius:8px;padding:{_dk.SEP_GAP - _dk.NEWS_VP}px 12px {_dk.SEP_GAP - _dk.VP}px;margin:0 0 8px;line-height:{_dk.LH_BODY};">'   # 폭은 다른 카드와 같게, 대신 일반 기사를 NEWS_INDENT 만큼 들여 제목 왼쪽 선을 맞춘다 (2026-10-16 사용자; 10-14 의 좌우 −13 은 되돌림)   # 끝 줄이 라벨(행간 1)이라 아래는 VP 만 뺀다
                f"{head_html}{fact}{when}{lab}</div>")
    return f"{head_html}{fact}{when}{lab}"


# 막대는 파스텔 톤 (2026-10-11 사용자: 너무 빨갛다, 눈의 피로) — (배경, 글자)
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"),
              "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
RATING_PASTEL = [("strongBuy", "강매수", "#F4ACA6", "#7F1D1D"), ("buy", "매수", "#FAD3CF", "#7F1D1D"),
                 ("hold", "보유", "#E2E8F0", "#475569"), ("sell", "매도", "#C9DCF7", "#1E3A8A"), ("strongSell", "강매도", "#A9C5F2", "#1E3A8A")]


NEWS_INDENT = 13   # 일반 기사 좌우 들여쓰기 = 강조 카드 테두리 1 + 안쪽 12 (2026-10-16 사용자: 강조 카드 폭은 다른 카드와 같게, 제목 왼쪽 선은 맞게)
BAR_H, BAR_NUM, BAR_PAD = 30, "17px", 5   # 막대 안 숫자 18 → 17 (2026-10-14 사용자)   # 높이 26 → 30 (+15%, 2026-10-14 사용자) · 막대 위아래 +5   # 막대 높이 24 → 26 (+10%, 정수) · 막대 안 숫자 19 → 18 (2026-10-13 사용자, 가이드라인 10-7)


LEGEND_CHIP = 9      # 범례 색 사각형 11 → 9px (20% 줄임, 2026-10-17 사용자)
LEGEND_INDENT = 10   # 범례 왼쪽 들여쓰기 (2026-10-17 사용자)


def _legend_bar(title, segs):
    """막대 + 색 범례 — 제목(왼쪽, 검정 굵게) · 막대 · 막대 색과 같은 범례 칩 (애널리스트 · 뉴스 공통, 2026-10-17 사용자: 뉴스도 같은 모양).
    segs = [(이름, 개수, 배경, 글자)], 0건은 뺀다. 범례는 왼쪽에서 10px 들여쓴다."""
    segs = [x for x in segs if x[1]]
    total = sum(x[1] for x in segs)
    if not total:
        return ""
    head = f'<span style="display:block;font-size:{_dk.BAR_LABEL};line-height:{LH_CARD};margin:0 0 3px;color:#111;font-weight:700;">{_esc(title)}</span>'
    body = "".join(f'<span style="display:block;width:{c / total * 100:.1f}%;background:{bg};color:{fg};font-size:{BAR_NUM};font-weight:700;'
                   f'text-align:center;line-height:{BAR_H}px;overflow:hidden;white-space:nowrap;">{f"{c / total * 100:.0f}%" if c / total >= 0.08 else ""}</span>' for _, c, bg, fg in segs)
    bar_html = f'<span style="display:flex;width:100%;height:{BAR_H}px;border-radius:6px;overflow:hidden;background:#F1F5F9;margin:{BAR_PAD}px 0 {3 + BAR_PAD}px;">{body}</span>'
    legend = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 0 0;white-space:nowrap;">'
                     f'<span style="display:inline-block;width:{LEGEND_CHIP}px;height:{LEGEND_CHIP}px;border-radius:2px;background:{bg};"></span>{nm} {c / total * 100:.0f}%</span>' for nm, c, bg, _ in segs)
    return head + bar_html + (f'<span style="display:block;box-sizing:border-box;padding-left:{LEGEND_INDENT}px;font-size:{_dk.BAR_LABEL};line-height:{LH_CARD};color:{NOTE};margin:0 0 10px;">{legend}</span>')


def _rating_bar(n, rc):
    """애널리스트 등급 막대 — 제목 `애널리스트 62명 의견` (2026-10-17 사용자)."""
    return _legend_bar(f"애널리스트 {n}명 의견", [(nm, rc.get(k, 0), bg, fg) for k, nm, bg, fg in RATING_PASTEL])


def _ratio_bar(label, counts):
    """뉴스 방향 막대: 긍정 · 부정 · 불확실 · 중립 (파스텔) — 애널리스트와 같은 범례 모양 (2026-10-17 사용자)."""
    total = sum(counts.values())
    return _legend_bar(f"{label} {total}건", [(rr.DIR_KO[d], counts.get(d, 0), *BAR_PASTEL[d]) for d in ("positive", "negative", "uncertain", "neutral")])


ACC_CHEV = ('<svg class="acc-chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>')


FOLD_LEFT = _dk.FOLD_LEFT + 8   # 접기 버튼 왼쪽 여백 4 → 12 (2026-10-14 사용자: "접기 버튼 좌측 여백 8픽셀 추가", 엔비디아)


def _fold_btn(bg="#fff", bd="#E2E8F0"):
    return _dk.fold_btn(bg, bd).replace(f"margin-left:{_dk.FOLD_LEFT}px;", f"margin-left:{FOLD_LEFT}px;")


ACC_BTN = _fold_btn()   # 네모 박스 안 화살표 버튼 (2026-10-11 사용자) = 공식 접기 버튼, 28 → 31px (2026-10-13 사용자, 가이드라인 10-6)


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
    # 강조 카드만 카드, 나머지는 가로 구분선 목록 (2026-10-13 사용자). 일반 기사는 카드 안쪽만큼(테두리 1 + 안쪽 12) 들여 제목 왼쪽 선을 강조 카드 제목에 맞춘다 (2026-10-16 사용자)
    out = "".join(_event_html(e) for e in cards) + _dk.item_rules([f'<span style="display:block;padding:0 {NEWS_INDENT}px;">{_event_html(e)}</span>' for e in plain])
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
            f'<span style="{COL_R}{VAL}font-weight:700;">{value_html}</span></span> ')   # 왼쪽 65% · 오른쪽 35%, 값이 모두 5자 미만이면 80 · 20 (2026-10-11 사용자)


def _ccard(rows, left=None):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html)]. 카드 하나, 줄 사이 가로 구분선."""
    short = _dk.short_values(rows)
    inner = "".join(_crow(n, v, sb, first=(i == 0), short=short) for i, (n, v, sb) in enumerate(rows))
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{MULTI}">{inner}</span></div>'   # 데스크톱 2열 (테마 CSS)


def _sub_label(t, tip=""):
    """카드 묶음 위 소제목 — F 막대 라벨과 같은 모양 (14px 안내 회색). data-sub: 탭이 서브탭으로 쓴다. tip = 제목 바로 옆 ? 툴팁."""
    return f'<div data-sub="1" style="font-size:{SMALL};line-height:{LH_CARD};color:{NOTE};margin:10px 0 3px;">{_paren(_esc(t))}{_tipx(tip) if tip else ""}</div>'   # 소제목 16px


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
                  f'<span style="{COL_R}{VAL}font-weight:700;">{right_html}</span></span> ')
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
    return (f'<span style="color:#111;font-weight:700;">{v}</span>' if c["flag"] else v), ""   # 경고색 없이 굵게만 (2026-10-17 W7)


# 묶음 설명 — 카드 아래 ⓘ 한 줄 (디자인-가이드라인 3-4, 2026-10-11). 뜻만 적고 평가하지 않는다
GROUP_NOTE = {   # 제목 있는 안내 (_guide) — 짧으면 한 줄, 길면 글머리표 (2026-10-11 사용자)
    "options": ("옵션", [("뜻", "옵션 시장이 가격에 담은 기대치"), ("수집", "미국 장 마감 후 1회 스냅샷")]),
    "estimates": ("예상 실적", [("값", "애널리스트 예상치의 평균"), ("7일 변화", "예상치가 일주일 사이 움직인 폭")]),
    "flows": ("수급", [("ETF 발행주식수", "자금 유입·유출 (yfinance)"), ("공매도 잔고", "격주 집계"),
                      ("장외 공매도 비율", "FINRA에 보고된 장외 거래만, 거래소 체결 제외 · 당일 파일이 늦으면 다음 실행에 채움")]),
    "valuation": ("주가 수준", "주가가 앞으로 12개월 예상 이익의 몇 배인지"),
}


def _fold_row(label):
    """카드 안 접기 줄 — 지수 더 보기와 같은 버튼 모양 (가이드 10-6). 테마 JS 가 펼친 내용을 이 줄 위로 옮기고 글자를 `접기` 로 바꾼다."""
    return (f'<span style="display:flex;justify-content:center;align-items:center;gap:6px;padding:8px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;'
            f'font-size:{TINY};line-height:20px;font-weight:700;color:#111;"><span>{_esc(label)}</span>{_dk.ACC_CHEV}</span>')


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
        card = _ccard(rows) + (_guide(*GROUP_NOTE[group]) if GROUP_NOTE.get(group) else "")
        if group == "options":   # 전문 지표는 기본 접힘 — 카드 안 접기(details[data-fold], 테마 JS) (2026-10-16 초보자 원칙, 가이드 2-4)
            card = (f'<details data-fold="1" data-label="자세한 숫자 보기"><summary style="list-style:none;cursor:pointer;">{_fold_row("자세한 숫자 보기")}</summary>{card}</details>')
        out.append(_sub_label(rr.GROUP_KO[group]) + card)
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
                      f'<span style="font-weight:700;">{_esc(v)}</span>' if c.get("flag") else _esc(v)))   # 경고색 없이 (2026-10-17 W7)
    if not items:
        return ""
    # 줄 오른쪽 끝 ? — 세 수치의 뜻 (2026-10-14 사용자). 팝업 제목은 숨긴 글자 `뉴스 수치`
    tipc = (f'<span style="flex:none;display:inline-flex;align-items:center;padding:0 6px 0 2px;">'
            f'<span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;">뉴스 수치</span>{_tipx(NEWS_STAT_TIP)}</span>')
    html = _dk.stat_line(items)
    return html[:-len("</div>")] + tipc + "</div>"


NEWS_STAT_TIP = ("기사 : 기준 거래일에 나온 NVDA 관련 기사(뉴스 · 엔비디아 뉴스룸 · 블로그) 전체 수\n"
                 "· 다른 매체에 실린 같은 기사도 세고, 키워드 거르기에서 빠진 기사는 뺀다\n"
                 "· 위 막대의 ‘오늘 n건’은 그중 기준을 넘어 이벤트로 뽑힌 기사만이라 더 적다\n"
                 "· 5건 이상이면서 7일 평균의 2배 이상이면 주황\n"
                 "7일 평균 : 직전 7일 동안 하루 평균 기사 수\n"
                 "대기 문서 : 수집했지만 아직 분류하지 못한 문서 수 — 다음 실행에서 이어서 분류")


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
    tr = f"flex:1 1 0;min-width:0;text-align:right;white-space:nowrap;font-weight:700;{VAL}"
    vs = f'<span style="color:{SUB};font-weight:400;font-size:{TINY};">· 현재가 대비</span>'
    rc = (cells.get("rating_counts") or {}).get("value") or {}
    n = sum(rc.values()) if rc else 0
    bar = _rating_bar(n, rc) if n else ""   # 제목 왼쪽 굵게 · 인원 오른쪽 연하게 · 색 범례 (2026-10-17 사용자)
    tn = next((_new(a, "status:" + k) for k in ("pt_mean", "pt_median", "pt_high", "pt_low", "rating_counts") if _new(a, "status:" + k)), "")   # 목표가·등급 중 하나라도 바뀐 날
    # 접힌 상태: 애널리스트 N명 등급 분포 막대가 맨 위 + 평균 등급 줄 (화살표는 이 줄 오른쪽). 목표가 평균은 펼친 영역의 첫 줄로
    # (2026-10-16 사용자: "애널리스트 62명 내용을 맨 처음에, 목표가 평균은 목표가 중앙 위에 · 펼쳤을 때 나오는 영역에")
    if n:
        summary = f'<span style="display:block;padding:{_dk.SEP_GAP - _dk.VP - 1}px 0 10px;">{bar}</span>'   # 막대 아래 margin 10 + 10 ≈ 보이는 22 (2026-10-12)
        # 평균 등급 (2026-10-11 사용자: 네이버 컨센서스처럼 한 숫자로) — 강매수 5 … 강매도 1 가중 평균. 애널리스트 의견의 평균이지 리포트의 판단이 아니다
        mean_r = sum(w * rc.get(k, 0) for k, w in (("strongBuy", 5), ("buy", 4), ("hold", 3), ("sell", 2), ("strongSell", 1))) / n
        summary += (f'<span style="{MULTI_ROW}padding:{_dk.SEP_GAP - _dk.VP - 1}px 0 0;{MULTI_SEP}"><span style="{COL_L}font-weight:700;color:#111;font-size:{_dk.NAME};">{_paren("평균 등급 (강매수 5 · 강매도 1)")}</span> '
                    f'<span style="{COL_R}{VAL}font-weight:700;display:inline-flex;align-items:center;justify-content:flex-end;">{mean_r:.1f}&nbsp;<span style="color:{MUTED};font-weight:400;">/ 5</span>{ACC_BTN}</span></span>')
    else:
        summary = f'<span style="display:flex;justify-content:flex-end;padding:4px 0 0;">{ACC_BTN}</span>'
    # 펼친 상태: 목표가 평균·중앙·최고·최저 (같은 줄 모양) — 바뀐 날 표시(tn)는 평균 줄에
    rows = ""
    for key, name in (("pt_mean", "평균"), ("pt_median", "중앙"), ("pt_high", "최고"), ("pt_low", "최저")):
        v = (cells.get(key) or {}).get("value")
        if v is None:
            continue
        rows += (f'<span style="{MULTI_ROW}padding:{_dk.SEP_GAP - _dk.VP - 1}px 0;{MULTI_SEP if rows else ""}"><span style="{tl}">목표가 {name}{tn if key == "pt_mean" else ""}</span> '
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
        return _muted("어제 이후 새로 바뀐 중요 소식이 없습니다." if not a["events"] or (n is not None and not n.get("today")) else "서술을 만들지 못했습니다 — 수치 섹션만 참고하세요.")   # 같은 줄을 매일 반복하지 않는다 (2026-10-17 사용자)
    areas = "|".join(re.escape(v) for v in rr.AREA_KO.values())
    lines = [re.sub(rf"^({areas})\s+(?!·)", r"\1 · ", t) for t in n["today"]]   # 영역 머리 뒤 구분점 보정
    lis = "".join(_dot_li(_esc(t), size=3, lh=_dk.LH_BODY, margin=_dk.LI_MARGIN) for t in lines)   # 18px 글 → 3px 점 (2026-10-12 사용자)
    # 카드 없이 본문 글머리표 — 제목 아래 구분선은 _section 이 긋는다 (2026-10-13 사용자: "중요 이슈 카드 디자인 삭제하고 타이틀 아래 구분선")
    return _dk.dot_ul([lis])


def sec_footer(a):
    ds = a["data_status"]
    return (f'<div data-footer="1" style="margin-top:3px;padding-top:2px;border-top:1px solid #f3f3f3;font-size:{TINY};line-height:{LH_TINY};color:{NOTE};{_dk.GUIDE_IND}">'
            f"{INFO_ICON}데이터: yfinance(일봉·옵션·예상 실적·애널리스트·기관·공매도) · SEC 공시(임원 거래·수시·분기 보고) · FRED(거시 일정) · "
            f"NVIDIA 뉴스룸·블로그 · CNBC · Google News · 연방관보 · CourtListener · trump-trend. "
            f"분류 Gemini(한도 때는 예비 모델이 임시 분류, 다음 실행에서 Gemini 로 다시), 판정·계산 파이썬. 생성 {_esc(a['generated_at'])} (UTC) · 기준 거래일 {_esc(_d(a['day']))} · 일봉 마지막 {_esc(_d(ds['bars_last_day']) or '—')}.<br>"
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
        sec_chart(a=a), sec_headline(a, n), sec_targets(a),   # 쉬운 말 줄은 가격 카드 펼침 안 (2026-10-16 사용자)   # 그래프는 탭 위, 평균 카드는 가격 카드 아래 (2026-10-13 사용자)
        # 목표가는 상태 카드 아래 (아코디언) — 제목 없이 본문 머리에 (2026-10-11 사용자: 오늘 한 줄 타이틀 삭제)
        # 테스트 운영 안내는 머리 카드 뒤 (2026-10-13 사용자: 구글 검색) — 맨 앞이면 검색 결과 · 공유 미리보기 문구가 "테스트 운영 중 …"이 된다
        _notice(a),
        _section("중요 이슈", sec_narrative(a, n), tab="오늘"),   # 그래프 아래로 (2026-10-11 사용자)
        _section("뉴스", sec_direction_bars(a) + sec_news_counts(a) + sec_events(a), line=False, tab="오늘"),   # 바로 아래가 카드라 제목 밑 구분선 없음 (2026-10-13 사용자)   # 막대가 바로 와도 구분선
        # 탭 이름과 같은 제목(캘린더·시장 지표·재무)은 탭 화면에서 숨긴다 — 본문(탭 없음)에서는 구획 경계로 남는다
        _section("캘린더", sec_upcoming(a) + _guide("범위", f"{config.CALENDAR_LOOKAHEAD_DAYS}일 이내 · 법원 일정은 {config.COURT_LOOKAHEAD_DAYS}일"), tab="캘린더"),   # 안내는 카드 아래 (2026-10-11 사용자)
        _section("진행 중 사안", sec_cases(a), tab="캘린더"),
        # "기술지표" → "시장 지표" (2026-10-16 사용자): 내용이 옵션 · 예상 실적 · 수급 · 주가 수준이고, 진짜 기술지표(이평선 · RSI)는 10-11 에 오늘 탭으로 갔다
        _section("시장 지표", sec_status(a), tab="시장 지표"),
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
