"""질문 카드 · 세로 막대 그래프 — 엔비디아 리포트(experiments/nvda-report/render_html.py _state_card · _col_chart · _chart_card)와
같은 모양을 데일리에 옮긴 것 (2026-10-18 재설계, 가이드라인 2-7 질문 카드 · 1-4-1 그래프에는 비교 대상).

엔비디아 쪽은 그대로 둔다(같은 이름의 모듈 config · report_title 이 겹쳐 그쪽을 직접 import 할 수 없다).
모양을 바꿀 때는 두 곳을 같이 본다.
"""

import html as html_mod
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402

UP, DOWN = "#d93025", "#1a73e8"
NOTE = dk.NOTE
SOON = "#6D28D9"
CARD_DIR = dict(dk.CARD_DIR, soon=("#F5F3FF", "#E8E4FE"))   # 보라 테두리 10% · 20% 밝게 (P127, 불확실 카드와 같은 보라)
FOLD_LEFT = dk.FOLD_LEFT + 8
INLINE_W = 316
CHART_H, CHART_LBL = 150, 16
LEGEND_CHIP, LEGEND_INDENT = 9, 10
PASTEL_UP, PASTEL_DN, GRAY_BAR, AMBER = "#ED8E87", "#82B1F0", "#CBD5E1", "#F5B971"


def esc(t):
    return html_mod.escape(str(t), quote=False)


def _est_w(text, px):
    return sum(px if ord(ch) > 0x2E80 else px * 0.55 for ch in str(text))


def _fold_btn(bg="#fff", bd="#E2E8F0"):
    return dk.emph_fold_btn(bg, bd, FOLD_LEFT)   # 화살표 = 검정에 카드 테마 색 20% — 종목 페이지와 같은 공용 함수 (P187, 2026-11-07)


def _title_with_icon(title, tail_html):
    t = esc(title)
    head, sep, last = t.rpartition(" ")
    if not sep:
        return f'<span style="white-space:nowrap;">{dk.paren(t)}{tail_html}</span>'
    return f'{dk.paren(head)} <span style="white-space:nowrap;">{dk.paren(last)}{tail_html}</span>'


def _ends_white(html):
    """html 조각이 흰 카드(dk.MULTI 틀)로 끝나는가 — 끝 여백을 맞출 대상. 흰 카드 뒤에 글(안내 줄 · 칸 이름)이 있으면 아니다."""
    i = html.rfind(f'<span style="{dk.MULTI}')
    if i < 0:
        return False
    depth = 0
    for m in re.finditer(r"<(/?)span\b[^>]*>", html[i:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return not html[i + m.end():].strip()
    return False


def question_card(title, state, theme, color, lines, tip="", fold=True, opened=False):
    """질문 카드 — 첫 줄 질문 · 오른쪽 답(상태), 펼치면 쉬운 말 · 근거 줄 · 그래프.
    lines 항목: (글, "plain") 쉬운 말 · ("row", 이름, 값, 뜻) 근거 줄 · (html, "html") 그래프 · (글, "note") 안내 · 글 = 점 글머리표."""
    bg, bd = CARD_DIR[theme]
    if theme == "neutral" and color == "#111":   # 중립(회색) 카드 답 = 흐린 회색 — 종목 페이지와 같게 (R.MUTED, 2026-11-07)
        color = dk.MUTED
    bd_row = dk.darken(dk.lighten(dk.lighten(bd), 0.3), 0.02)   # 줄 구분선 2% 진하게 (2026-10-26 사용자: 5% → 2%)

    def li(item):
        kind = "row" if isinstance(item, tuple) and item[0] == "row" else ("" if isinstance(item, str) else item[1])
        text = item if isinstance(item, str) else item[0]
        if kind == "row":   # 근거 줄 18px · 행간 30 — 질문 · 대답과 같게, 설명 문장은 19 그대로 (2026-10-27 사용자)
            _, name, value, note = item
            val = value if str(value).startswith("<span") else dk.tint(esc(value))   # 이미 색 · 줄바꿈을 입힌 값(HTML)은 그대로 (2026-11-07 P330)
            fits = _est_w(name, 17) + _est_w(f"({note})", 14) + _est_w(value, 17) <= INLINE_W
            nt = f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:20px;color:{NOTE};white-space:normal;">{dk.tint(esc(note))}</span>' if note else ""
            if note and fits:
                return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd_row};font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};">'
                        f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                        f'<span style="flex:none;white-space:nowrap;color:#111;">{esc(name)} <span style="font-size:{dk.TINY};color:{NOTE};">({dk.tint(esc(note))})</span></span>'
                        f'<span style="flex:none;text-align:right;font-weight:{dk.STATE_VAL_W};white-space:nowrap;">{val}</span></span></li>')
            return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd_row};font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};">'
                    f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                    f'<span style="flex:1 1 auto;min-width:0;color:#111;"><span style="white-space:nowrap;">{esc(name)}</span>{nt}</span>'
                    f'<span style="flex:none;text-align:right;font-weight:{dk.STATE_VAL_W};word-break:keep-all;">{val}</span></span></li>')
        if kind == "html":
            return f'<li style="list-style:none;margin:6px 0 12px;">{text}</li>'
        if kind == "rich":   # plain 과 같은 모양, 글은 이미 만든 HTML (강조 숫자 — 한국 증시 리포트 주식 비중, 2026-11-05 M69)
            return f'<li {dk.SENT_ATTR} style="list-style:none;margin:{dk.SENT_TOP}px 0 17px;font-weight:400;color:#111;font-size:{dk.STATE_SENT_FS};line-height:{dk.LH_EMPH};word-break:keep-all;">{dk.bold_pct(text)}</li>'
        if kind == "plain":   # 펼친 설명 문장 18/32 · 증감 숫자 굵게 — 종목 페이지 _state_card 와 같게 (P132 · P279, 2026-11-07)
            return f'<li {dk.SENT_ATTR} style="list-style:none;margin:{dk.SENT_TOP}px 0 17px;font-weight:400;color:#111;font-size:{dk.STATE_SENT_FS};line-height:{dk.LH_EMPH};word-break:keep-all;">{dk.bold_pct(dk.tint(esc(text)))}</li>'
        if kind == "note":   # 늘 같은 안내 = 작은 회색 14/20 (P67 · 0절, 옛 19/32 점 줄)
            return f'<li data-note="1" style="list-style:none;margin:0 0 12px;font-size:{dk.TINY};line-height:20px;color:{NOTE};word-break:keep-all;">{dk.tint(esc(text))}</li>'
        col = "#111"
        return dk.dot_li(dk.label_text(text), size=3, color=col, lh=dk.LH_EMPH)

    lis = ""
    for k, t in enumerate(lines):   # 그래프 바로 아래 또 그래프 — 아래 그래프 제목 위 12 + CHART_STACK_GAP(10) = 22, 보이는 간격 24 (가이드라인 P176 · P179, 엔비디아 _state_card 와 같게 — 2026-11-05 사용자 M79: 한국 증시 리포트에 빠져 있었다)
        h = li(t)
        prev = lines[k - 1] if k else None
        if (isinstance(t, tuple) and len(t) == 2 and t[1] == "html" and dk.CHART_MARK in t[0][:600]
                and isinstance(prev, tuple) and len(prev) == 2 and prev[1] == "html" and dk.CHART_MARK in prev[0][:600]):
            h = h.replace('<li style="list-style:none;margin:6px 0 12px;">', f'<li style="list-style:none;margin:{12 + dk.CHART_STACK_GAP}px 0 12px;">', 1)
        if k == len(lines) - 1 and isinstance(t, tuple) and len(t) == 2 and t[1] == "html" and _ends_white(t[0]):
            # 강조 카드가 흰 카드로 끝나면 아래 여백 = 좌우 여백 (가이드라인 7-1 끝 여백, 엔비디아 R._pull_end_chart 와 같은 결과).
            # li 아래 12 를 0 으로 — ul −9 와 겹쳐 보이는 아래 22 → 10 = 좌우 10 (Chrome 실측, 2026-11-07 사용자: "넌 왜 이걸 지키지 않았어")
            h = re.sub(r'^(<li style="list-style:none;margin:\d+px 0) 12px;">', r'\1 0;">', h, count=1)   # 위 여백은 그대로(연달은 그래프면 22)
        lis += h
    ans = state if str(state).startswith("<span") else dk.tint(esc(state))   # 이미 색을 입힌 답(HTML)은 그대로 — 한국 증시 리포트 결과 단어 색 (2026-10-26)
    state_html = (f'<span style="display:inline-flex;align-items:center;">{ans}{_fold_btn(dk.lighten(bg), bd)}</span>' if fold else ans)   # 답 글자의 증감도 색 (가이드라인 3-3-1)
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;line-height:{dk.LH_EMPH_Q};">'   # 질문 · 대답 18px · 행간 30 (2026-10-27 사용자)
            f'<span style="{"flex:1 1 auto;min-width:0;" if fold else dk.COL_L}font-weight:{dk.STATE_TITLE_W};color:#111;font-size:{dk.EMPH_Q};">{_title_with_icon(title, dk.tip_icon(tip) if tip else "")}</span>'
            f'<span style="{"flex:none;white-space:nowrap;" if fold else dk.COL_R}font-weight:{dk.STATE_ANS_W};color:{color};font-size:{dk.EMPH_Q};">{state_html}</span></span> ')
    body = (f'<div style="margin-top:{14 - dk.VP_EMPH + 3}px;padding-top:{14 - dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{dk.SMALL};">'
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul></div>")
    inner = (f'<details data-acc="1"{" open" if opened else ""}><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>{body}</details>' if fold else head + body)
    inner = dk.emph_white(inner)   # 강조 카드 안 흰 카드 외곽선 50% (P188)
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{dk.EMPH_PAD - dk.VP_EMPH}px 14px;margin:0 0 8px;line-height:{dk.LH_EMPH};">'
            f'{inner}</div>')


def cards_grid(html):
    """질문 카드 묶음 — 엔비디아 캘린더 탭과 같은 data-cards · data-grid (테마가 PC 에서 두 칸으로 놓는다)."""
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{html}</div>'


def legend_chips(items, keep=False):
    items = items if keep else dk.legend_items(items)   # keep = 막대 색이 '대상 · 비교' 가 아니라 하루를 나눈 조각(시가 갭 · 장중 · 하루)인 그래프   # 오름 · 내림 칩 삭제 · 회색 = `비교 대상 : …` (2026-10-27 사용자, 모든 그래프)
    chips = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 0 0;white-space:nowrap;">'
                     f'<span style="display:inline-block;width:{LEGEND_CHIP}px;height:{LEGEND_CHIP}px;border-radius:2px;background:{c};"></span>{esc(nm)}</span>' for nm, c in items)
    return f'<span style="display:block;box-sizing:border-box;padding-left:{LEGEND_INDENT}px;font-size:{dk.MICRO};line-height:{dk.LH_CARD};color:{NOTE};margin:0 0 10px;">{chips}</span>'


def col_chart(groups, colors, label_colors, height=CHART_H, fmt=None, right=True):   # 기본 = 오른쪽 모양 (P166)
    """세로 막대 (0 기준선, 위 = 오름 · 아래 = 내림) — groups = [(가로축 이름, [값, ...])], 시리즈마다 색 함수.
    숫자는 자기 막대 폭 안에만, 화면이 모자라면 가로 스크롤 (2026-10-26 사용자, 가이드라인 8절 — 엔비디아 _col_chart 와 같은 규칙)."""
    vals = [v for _, vs in groups for v in vs if v is not None]
    if not vals:
        return ""
    fs = dk.BAR_NUM_PX   # 막대 위 숫자 13px — 모든 그래프 같게 (2026-10-27 사용자, 옛 11)
    lbl = max(CHART_LBL, fs + 4)
    ticks, top, scale = dk.col_axis(vals, height, lbl + max(dk.LBL_LIFT, dk.LBL_LIFT_DN))   # 한 칸 바깥 눈금까지 · 아래 여백 통일 (2026-10-26 사용자) · 숫자 띄우기 자리 (P181)
    cut = dk.col_top_cut(vals, ticks, scale, lbl + max(dk.LBL_LIFT, dk.LBL_LIFT_DN))   # 쓰지 않는 위 숫자 자리만큼 세로를 줄인다 (P190)
    top, height = top - cut, height - cut
    n, ns = len(groups), len(groups[0][1])
    txt = lambda v: fmt(v) if fmt else f"{v:+.2f}".replace("-", "−")   # noqa: E731
    label_px = max(dk.text_px(txt(v), fs) for v in vals) + 4
    axis_px = max(dk.text_px(g, int(dk.TINY[:-2])) for g, _ in groups) + 8
    bw, lw, min_w = dk.col_layout(n, ns, label_px, axis_px)   # 막대 고정 폭 (2026-10-26 사용자: 모든 막대 그래프 같은 폭)
    parts = []   # 0 기준선 · 눈금선 · 세로축 숫자는 col_frame 이 (2026-10-26 사용자: 가로 눈금선)
    for i, (_, vs) in enumerate(groups):
        for k, v in enumerate(vs):
            if v is None:
                continue
            h = max(1.0, abs(v) * scale)
            y, ly = (top - h, top - h - lbl + 1 - dk.LBL_LIFT) if v >= 0 else (top, top + h + 1 + dk.LBL_LIFT_DN)   # 막대 ~ 숫자 2배 (P181)
            rad = "3px 3px 0 0" if v >= 0 else "0 0 3px 3px"
            parts.append(f'<span style="position:absolute;{dk.bar_x(i, k, n, ns, bw, lw)}top:{y:.1f}px;height:{h:.1f}px;background:{colors[k](v)};border-radius:{rad};"></span>')
            parts.append(f'<span style="position:absolute;{dk.bar_x(i, k, n, ns, bw, lw, label=True)}top:{ly:.1f}px;height:{lbl - 2}px;line-height:{lbl - 2}px;text-align:center;font-size:{fs}px;'
                         f'font-weight:700;white-space:nowrap;color:{label_colors[k](v)};">{txt(v)}</span>')
    return dk.col_frame("".join(parts), [g for g, _ in groups], height, top, scale, ticks, min_w, right=right)


def chart_card(title, groups, colors, label_colors, legend, fmt=None, keep_legend=False, right=True):
    pad = dk.SEP_GAP - dk.VP - 1
    chart = col_chart(groups, colors, label_colors, fmt=fmt, right=right)
    if not chart:
        return ""
    head = f'{dk.CHART_TITLE_M}{esc(title)}</span>' if title else ""   # 제목 없이 그래프만 — 한국 증시 리포트 머리 그래프 (2026-10-26)
    return head + f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">{dk.legend_top(chart, legend_chips(legend, keep_legend))}</span></span>'


sign_bg = lambda v: PASTEL_UP if v > 0 else PASTEL_DN   # noqa: E731
sign_fg = lambda v: UP if v > 0 else DOWN   # noqa: E731
gray = lambda v: GRAY_BAR   # noqa: E731
note_fg = lambda v: NOTE   # noqa: E731
amber = lambda v: AMBER   # noqa: E731


# ── 범위 막대 (1년) — 엔비디아 year_range_in 의 사본 (nvda-report/render_html.py, 2026-11-07 시장 탭 `시장은 얼마나 긴장했나?`) ──
# 엔비디아 렌더러를 통째로 읽으면 수집 모듈(판다스)까지 따라와 데일리 3.10 실행에서 깨진다 — 막대 · 말풍선 값은 저쪽과 같게 둔다 (가이드라인 9절).
GAUGE_INSET = 14   # 점 · 꼬리가 막대 끝 · 말풍선 가장자리에서 떨어지는 최소 px = 말풍선 모서리 8 + 꼬리 반폭 6
BUBBLE_FONT, BUBBLE_H, BUBBLE_W_STRONG, GAUGE_H = 14, 24, 500, 50   # 말풍선 글자 14 · 높이 24 · 굵기 500 · 막대 칸 50 (P183 · P186)


def _bubble_w(text):
    """말풍선 폭 px (글자 폭 어림 + 좌우 8) — 폭을 정해 두어야 CSS 만으로 카드 안에 가둘 수 있다."""
    return round(16 + sum(5 if ch in ",. " else 17 if "가" <= ch <= "힣" else 10 for ch in text) * BUBBLE_FONT / 17) + 2


def _gauge_tip(x, text, col, dot_col, weight=400):
    """말풍선 + 꼬리 + 원형 점. x = 위치 %. 점 · 꼬리는 막대 끝에서 GAUGE_INSET 안쪽까지, 말풍선은 카드 안에 멈추고 꼬리만 그 안에서 움직인다."""
    x = max(0.0, min(100.0, x))
    w = _bubble_w(text)
    at = f"clamp({GAUGE_INSET}px, {x:.1f}%, calc(100% - {GAUGE_INSET}px))"
    return (f'<span style="position:absolute;left:clamp(0px, calc({at} - {w / 2:g}px), calc(100% - {w}px));width:{w}px;bottom:16px;z-index:1;background:{col};color:#fff;font-weight:{weight};'
            f'font-size:{BUBBLE_FONT}px;display:flex;align-items:center;justify-content:center;height:{BUBBLE_H}px;line-height:1;padding:0;box-sizing:border-box;border-radius:8px;white-space:nowrap;"><span>{esc(text)}</span></span>'
            f'<span style="position:absolute;left:{at};bottom:10px;z-index:1;transform:translateX(-50%);width:0;height:0;'
            f'border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid {col};"></span>'
            f'<span style="position:absolute;left:{at};bottom:-3px;transform:translateX(-50%);z-index:3;box-sizing:border-box;width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid {dot_col};"></span>')


def range_gauge(low, high, pos_pct, pct_from_high, fmt, tip, title, legend, near_text, marks=None):
    """1년 범위 막대 — 얇은 막대(최저~최고, 지금까지 연한 파랑) + 지금 위치 점 · 꼬리 · 말풍선(최고 대비 %). 제목 줄은 카드 밖, 막대는 흰 카드.
    fmt = 값 표기 함수. 질문 카드 lines 의 ("html") 항목으로 넣는다.
    tip 이 비면 ? 없음. 최고가가 며칠 전인지는 싣지 않는다 (2026-11-07 사용자: 종목 페이지와 같게).
    marks = [(글자, 위치 %)] — 막대 위 파란 세로 눈금 + 최저 · 최고 아래 줄 글자 (애널리스트 목표가 막대의 중앙 · 평균 눈금과 같은 모양, 2026-11-07 사용자: 200일 평균)."""
    pos = max(0.0, min(100.0, pos_pct))
    near = pct_from_high > -0.5
    text = near_text if near else f"{pct_from_high:.1f}%".replace("-", "−")
    col, dot = ("#64748B", "#64748B") if near else (dk.lighten(dk.DOWN, 0.2), dk.DOWN)
    head = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
            f'<span style="font-weight:700;color:#111;font-size:{dk.NAME};">{dk.CHART_MARK}{dk.paren(esc(title))}{dk.tip_icon(tip) if tip else ""}</span>'
            f'<span style="flex:none;font-size:{dk.MICRO};color:{NOTE};white-space:nowrap;">{esc(legend)}</span></span>')
    at = f"clamp({GAUGE_INSET}px, {pos:.1f}%, calc(100% - {GAUGE_INSET}px))"
    bar = (f'<span style="position:absolute;left:0;right:0;bottom:0;height:6px;border-radius:3px;background:#E2E8F0;">'
           f'<span style="position:absolute;left:0;top:0;bottom:0;width:{at};border-radius:3px;background:#BFDBFE;"></span>'
           + "".join(f'<span style="position:absolute;left:{max(0.0, min(100.0, p)):.2f}%;top:-4px;z-index:1;width:2px;height:14px;margin-left:-1px;background:{dk.DOWN};"></span>' for _t, p in (marks or []))
           + '</span>')
    aria = esc(f"1년 범위 {fmt(low)}~{fmt(high)}, {text}")
    gauge = (f'<span data-range-gauge="1" aria-label="{aria}" style="position:relative;display:block;height:{GAUGE_H}px;">'
             f'{_gauge_tip(pos, text, col, dot, BUBBLE_W_STRONG)}{bar}</span>')
    ends = (f'<span style="display:flex;justify-content:space-between;gap:12px;margin-top:6px;font-size:{dk.TINY};line-height:20px;color:{NOTE};">'
            f'<span style="white-space:nowrap;">최저 {fmt(low)}</span><span style="white-space:nowrap;">최고 {fmt(high)}</span></span>')
    below = ""
    for t, p in (marks or []):   # 눈금 글자 = 막대 아래 둘째 줄, 가운데를 눈금 자리에 두되 카드 안으로 가둔다 (target_gauge 와 같게)
        w = round(len(t) * 14 * 0.62) + 2
        below += (f'<span style="position:absolute;top:0;left:clamp(0px, calc({max(0.0, min(100.0, p)):.1f}% - {w / 2:g}px), calc(100% - {w}px));'
                  f'font-size:{dk.TINY};line-height:20px;color:#111;white-space:nowrap;">{esc(t)}</span>')
    if below:
        ends += f'<span style="position:relative;display:block;height:20px;margin-top:2px;">{below}</span>'
    card = f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.SEP_GAP - dk.VP - 1}px 12px {12 - 3}px;">{gauge}{ends}</span></span>'
    return f'<span style="display:block;margin:0 0 {dk.CHART_TITLE_GAP}px;">{head}</span>{card}'
