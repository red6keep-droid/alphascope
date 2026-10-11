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
H2 = "color:#111;font-size:21px;font-weight:700;line-height:1.3;margin:28px 0 11px;padding:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;"
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:6px;"
_NO_LINE_START = re.compile(r'^\s*(<div style="(?:overflow-x:auto;|background:)|<div data-cards|<div data-lead|<img\b|<details\b)')
CARD = "background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:12px 14px;"
CARD_DIR = {"positive": ("#FFF7ED", "#FED7AA"), "negative": ("#EFF6FF", "#BFDBFE"), "neutral": ("#F8FAFC", "#E2E8F0"), "uncertain": ("#FFFBEB", "#FDE68A")}
PILL = {"area": ("#CBD5E1", "#334155"), "positive": ("#FCA5A5", "#B91C1C"), "negative": ("#93C5FD", "#1D4ED8"),
        "uncertain": ("#FDBA74", "#C2410C"), "neutral": ("#CBD5E1", "#64748B")}
PILL_BG = {"positive": "#FEF2F2", "negative": "#EFF6FF"}
BAR_PASTEL = {"positive": ("#F8C4BF", "#7F1D1D"), "negative": ("#BCD3F5", "#1E3A8A"), "uncertain": ("#FADDB0", "#7C2D12"), "neutral": ("#E2E8F0", "#475569")}
ROW = ("display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 6px;padding:8px 12px;"
       "background:#fff;border:1px solid #E2E8F0;border-radius:8px;white-space:nowrap;line-height:1.5;")
ROW_UP, ROW_DOWN = "background:#FFF7ED;border-color:#FED7AA;", "background:#EFF6FF;border-color:#BFDBFE;"
MULTI = f"display:block;margin:0 0 6px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:{SMALL};"
MULTI_ROW = "display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 12px;white-space:nowrap;line-height:1.5;"
MULTI_SEP = "border-top:1px solid #E2E8F0;"
UL, LI = "margin:0 0 8px 20px;padding:0;list-style:disc;", "margin:6px 0;"
INFO_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;margin-right:4px;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>')
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
    return f'<span style="color:{col};font-weight:700;">{tri} {abs(v):.{digits}f}{unit}</span>'


def dash():
    return f'<span style="color:{MUTED};">—</span>'


def h2(t, line=True, summary=""):
    sm = (f' <span data-summary="1" style="font-size:{TINY};font-weight:400;color:{NOTE};line-height:1.5;white-space:normal;flex:1 1 220px;">{INFO_ICON}{summary}</span>'
          if summary else "")
    return f'<h2 style="{H2}{H2_LINE if line else ""}">{esc(t)}{sm}</h2>'


def section(title, html, summary="", line=None):
    """제목(+옆 요약) + 내용. 바로 아래가 카드·표·그림이면 구분선을 긋지 않는다 (가이드라인 2절)."""
    if line is None:
        line = not _NO_LINE_START.match(html or "")
    return h2(title, line=line, summary=summary) + (html or "")


def note(t):
    """구획 안내 줄 — 내용 아래, ⓘ, 14px 회색, 윗선."""
    return f'<div style="margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;font-size:{TINY};color:{NOTE};">{INFO_ICON}{esc(t)}</div>'


def muted(t):
    """짧은 안내 글 (빈 구획 안내 등) — ⓘ 필수."""
    return f'<div style="color:{NOTE};font-size:{TINY};margin:6px 0;">{INFO_ICON}{esc(t)}</div>'


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
    return ul(f"<li style='{LI}'>{esc(t)}</li>" for t in texts)


def row(name, value_html, tone=""):
    """A타입 한 줄 카드: 이름 좌 · 값 우 (18px)."""
    return f'<span style="{ROW}{tone}"><span style="font-weight:700;color:#111;">{esc(name)}</span> <span>{value_html}</span></span> '


def multi(rows):
    """C타입: (이름, 값HTML) 여러 줄을 한 카드에. data-grid=2: 데스크톱에서 2열 (테마 CSS)."""
    out = ""
    for i, (name, value_html) in enumerate(rows):
        out += (f'<span style="{MULTI_ROW}{MULTI_SEP if i else ""}"><span style="font-weight:700;color:#111;">{paren(esc(name))}</span> '
                f'<span style="font-weight:700;">{value_html}</span></span> ')
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
                  f'<span style="font-weight:700;color:#111;">{paren(esc(name))}</span> <span style="font-weight:700;">{value_html}</span></span> ')
        if len(pair) == 1:
            r += f'<span style="{cell}border-left:1px solid #E2E8F0;"></span>'
        out += f'<span style="display:flex;{MULTI_SEP if i else ""}">{r}</span> '
    return f'<span style="{MULTI}">{out}</span> '


def crow(name_html, value_html, sub="", first=False, left=None):
    """C 카드 한 줄 + 보조 줄(14px #999). name_html 은 이스케이프된 HTML."""
    sub_html = f'<span style="display:block;color:{MUTED};font-weight:400;font-size:{TINY};white-space:normal;">{paren(sub)}</span>' if sub else ""
    return (f'<span style="{MULTI_ROW}{"" if first else MULTI_SEP}">'
            f'<span style="display:block;min-width:0;white-space:normal;{f"flex:0 0 {left};" if left else ""}"><span style="font-weight:700;color:#111;">{paren(name_html)}</span>{sub_html}</span> '
            f'<span style="{"flex:1;min-width:0;" if left else "flex:none;"}text-align:right;font-weight:700;">{value_html}</span></span> ')


def ccard(rows, left=None, attrs=""):
    """C 카드 묶음: rows = [(name_html, value_html, sub_html)]."""
    inner = "".join(crow(n, v, sb, first=(i == 0), left=left) for i, (n, v, sb) in enumerate(rows))
    return f'<div data-cards="1" {attrs} style="margin:0 0 8px;"><span data-grid="2" style="{MULTI}">{inner}</span></div>'


def cards(html):
    """글 머리 카드 묶음 — data-lead: 홈 카드가 제목 없는 머리 구획으로 읽는다 (data-cards 는 엔비디아 탭 JS 가 보므로 여기선 쓰지 않는다)."""
    return f'<div data-lead="1" style="margin:0 0 8px;">{html}</div>'


def dcard(html, theme="neutral"):
    """D 본문 카드 (문장·목록). 배경은 방향 테마."""
    bg, bd = CARD_DIR.get(theme, CARD_DIR["neutral"])
    return f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:12px 14px;margin:0 0 8px;">{html}</div>'


def sub_label(t):
    return f'<div data-sub="1" style="font-size:{SMALL};color:{NOTE};margin:10px 0 3px;">{esc(t)}</div>'


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
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:{TINY};color:{NOTE};line-height:1.6;">'
            f"{INFO_ICON}{data_line}<br>{INFO_ICON}{disclaimer_line}</div>")
