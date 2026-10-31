"""질문 카드 · 세로 막대 그래프 — 엔비디아 리포트(experiments/nvda-report/render_html.py _state_card · _col_chart · _chart_card)와
같은 모양을 데일리에 옮긴 것 (2026-10-18 재설계, 가이드라인 2-7 질문 카드 · 1-4-1 그래프에는 비교 대상).

엔비디아 쪽은 그대로 둔다(같은 이름의 모듈 config · report_title 이 겹쳐 그쪽을 직접 import 할 수 없다).
모양을 바꿀 때는 두 곳을 같이 본다.
"""

import html as html_mod
import os
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
    return dk.fold_btn(bg, bd).replace(f"margin-left:{dk.FOLD_LEFT}px;", f"margin-left:{FOLD_LEFT}px;")


def _title_with_icon(title, tail_html):
    t = esc(title)
    head, sep, last = t.rpartition(" ")
    if not sep:
        return f'<span style="white-space:nowrap;">{dk.paren(t)}{tail_html}</span>'
    return f'{dk.paren(head)} <span style="white-space:nowrap;">{dk.paren(last)}{tail_html}</span>'


def question_card(title, state, theme, color, lines, tip="", fold=True, opened=False):
    """질문 카드 — 첫 줄 질문 · 오른쪽 답(상태), 펼치면 쉬운 말 · 근거 줄 · 그래프.
    lines 항목: (글, "plain") 쉬운 말 · ("row", 이름, 값, 뜻) 근거 줄 · (html, "html") 그래프 · (글, "note") 안내 · 글 = 점 글머리표."""
    bg, bd = CARD_DIR[theme]
    bd_row = dk.darken(dk.lighten(dk.lighten(bd), 0.3), 0.02)   # 줄 구분선 2% 진하게 (2026-10-26 사용자: 5% → 2%)

    def li(item):
        kind = "row" if isinstance(item, tuple) and item[0] == "row" else ("" if isinstance(item, str) else item[1])
        text = item if isinstance(item, str) else item[0]
        if kind == "row":   # 근거 줄 18px · 행간 30 — 질문 · 대답과 같게, 설명 문장은 19 그대로 (2026-10-27 사용자)
            _, name, value, note = item
            fits = _est_w(name, 17) + _est_w(f"({note})", 14) + _est_w(value, 17) <= INLINE_W
            nt = f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:20px;color:{NOTE};white-space:normal;">{dk.tint(esc(note))}</span>' if note else ""
            if note and fits:
                return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd_row};font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};">'
                        f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                        f'<span style="flex:none;white-space:nowrap;color:#111;">{esc(name)} <span style="font-size:{dk.TINY};color:{NOTE};">({dk.tint(esc(note))})</span></span>'
                        f'<span style="flex:none;text-align:right;font-weight:700;white-space:nowrap;">{dk.tint(esc(value))}</span></span></li>')
            return (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {bd_row};font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};">'
                    f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                    f'<span style="flex:1 1 auto;min-width:0;color:#111;"><span style="white-space:nowrap;">{esc(name)}</span>{nt}</span>'
                    f'<span style="flex:none;text-align:right;font-weight:700;word-break:keep-all;">{dk.tint(esc(value))}</span></span></li>')
        if kind == "html":
            return f'<li style="list-style:none;margin:6px 0 12px;">{text}</li>'
        if kind == "plain":
            return f'<li style="list-style:none;margin:14px 0 17px;font-weight:400;color:#111;line-height:{dk.LH_EMPH};word-break:keep-all;">{dk.tint(esc(text))}</li>'
        col = NOTE if kind == "note" else "#111"
        return dk.dot_li(dk.label_text(text), size=3, color=col, lh=dk.LH_EMPH)

    lis = "".join(li(t) for t in lines)
    ans = state if str(state).startswith("<span") else dk.tint(esc(state))   # 이미 색을 입힌 답(HTML)은 그대로 — 한국 증시 리포트 결과 단어 색 (2026-10-26)
    state_html = (f'<span style="display:inline-flex;align-items:center;">{ans}{_fold_btn(dk.lighten(bg), bd)}</span>' if fold else ans)   # 답 글자의 증감도 색 (가이드라인 3-3-1)
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;line-height:{dk.LH_EMPH_Q};">'   # 질문 · 대답 18px · 행간 30 (2026-10-27 사용자)
            f'<span style="{"flex:1 1 auto;min-width:0;" if fold else dk.COL_L}font-weight:700;color:#111;font-size:{dk.EMPH_Q};">{_title_with_icon(title, dk.tip_icon(tip) if tip else "")}</span>'
            f'<span style="{"flex:none;white-space:nowrap;" if fold else dk.COL_R}font-weight:700;color:{color};font-size:{dk.EMPH_Q};">{state_html}</span></span> ')
    body = (f'<div style="margin-top:{14 - dk.VP_EMPH + 3}px;padding-top:{14 - dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{dk.SMALL};">'
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul></div>")
    inner = (f'<details data-acc="1"{" open" if opened else ""}><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>{body}</details>' if fold else head + body)
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


def col_chart(groups, colors, label_colors, height=CHART_H, fmt=None, right=False):
    """세로 막대 (0 기준선, 위 = 오름 · 아래 = 내림) — groups = [(가로축 이름, [값, ...])], 시리즈마다 색 함수.
    숫자는 자기 막대 폭 안에만, 화면이 모자라면 가로 스크롤 (2026-10-26 사용자, 가이드라인 8절 — 엔비디아 _col_chart 와 같은 규칙)."""
    vals = [v for _, vs in groups for v in vs if v is not None]
    if not vals:
        return ""
    fs = dk.BAR_NUM_PX   # 막대 위 숫자 13px — 모든 그래프 같게 (2026-10-27 사용자, 옛 11)
    lbl = max(CHART_LBL, fs + 4)
    ticks, top, scale = dk.col_axis(vals, height, lbl)   # 한 칸 바깥 눈금까지 · 아래 여백 통일 (2026-10-26 사용자)
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
            y, ly = (top - h, top - h - lbl + 1) if v >= 0 else (top, top + h + 1)
            rad = "3px 3px 0 0" if v >= 0 else "0 0 3px 3px"
            parts.append(f'<span style="position:absolute;{dk.bar_x(i, k, n, ns, bw, lw)}top:{y:.1f}px;height:{h:.1f}px;background:{colors[k](v)};border-radius:{rad};"></span>')
            parts.append(f'<span style="position:absolute;{dk.bar_x(i, k, n, ns, bw, lw, label=True)}top:{ly:.1f}px;height:{lbl - 2}px;line-height:{lbl - 2}px;text-align:center;font-size:{fs}px;'
                         f'font-weight:700;white-space:nowrap;color:{label_colors[k](v)};">{txt(v)}</span>')
    return dk.col_frame("".join(parts), [g for g, _ in groups], height, top, scale, ticks, min_w, right=right)


def chart_card(title, groups, colors, label_colors, legend, fmt=None, keep_legend=False, right=False):
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
