"""trump_analysis.json (+ narrative.json) → Blogger 본문 HTML (기획서 10절, 별도 글).

시각 규칙은 디자인-가이드라인.md 와 experiments/design_kit.py (2026-10-11): 18px 본문, 21px 구획 제목, C 카드, ⓘ 안내 글 14px, 라벨 알약, 표는 통계 행렬(과거 반응)에만.
숫자는 여기서 파이썬이 그리고, 문장은 narrative.json에서만 가져온다.

출력:
    output/trump_report_body.html   Blogger에 올리는 본문
    output/trump_report.html        브라우저 미리보기 (본문을 감싼 것)
"""

import html as html_mod
import json
import os
import sys

import config
import report_title

# 시각 규칙은 디자인-가이드라인.md — 공통 조각 experiments/design_kit.py (2026-10-11 사용자: 데일리·트럼프도 새 디자인 규칙으로)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402

UP, DOWN, MUTED = dk.UP, dk.DOWN, dk.MUTED
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
SESSION_KO = {"regular": "정규장", "pre": "장전", "after": "장후", "closed": "휴장"}

PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""

_esc = dk.esc
TAB_TODAY, TAB_FLOW, TAB_REACT = "오늘", "흐름", "시장 반응"   # 탭 이름 = 구획 이름이면 테마 JS가 구획 제목을 숨긴다 (2026-10-11 사용자: 과거 반응 타이틀 삭제)   # 탭 셋 (가이드라인 11절)


def _k(text):
    """주제 / 하위주제 / 섹터 영어 → 한국어 (config.TERM_KO). 'Energy / Diesel Fuel' → '에너지 / 경유'."""
    return dk.ko(text, config.TERM_KO)


def _pct(v, digits=2, unit="%"):
    return dk.arrow(v, digits, unit)


def _dir_pill(d):
    return dk.pill(DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral")


# ── 구획 ────────────────────────────────────────────────────────────────

def sec_lead(a, n):
    """글 머리(제목 없음, data-lead): 24시간 집계 C 카드 + 가장 강한 발언 한 줄. 홈 카드는 이 묶음을 '(머리)'로 읽는다."""
    v = a["post_volume"]["last_24h"]
    ev = a["recent_events"]
    top = ev[0] if ev else None
    rows = [("게시물 (지난 24시간)", f"{v['total']}건"), ("정책 관련", f"{v['policy']}건"), ("시장 관련 이벤트", f"{len(ev)}개")]
    if top:
        rows.append(("가장 강한 발언", f"{_esc(_k(top['topic']))}{' / ' + _esc(_k(top['subtopic'])) if top['subtopic'] else ''} · 강도 {top['intensity']}"))
    out = dk.cards(dk.multi(rows))
    if v["pending"]:
        out += dk.muted(f"최근 게시물 {v['pending']}건은 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다.")
    return out


def sec_recent(a):
    """발언 — C 카드: 주제/하위주제 + 방향·세션 라벨, 보조 줄에 시각·대상·연타, 값은 강도."""
    rows = []
    for e in a["recent_events"]:
        name = f"<b>{_esc(_k(e['topic']))}</b>" + (f" / {_esc(_k(e['subtopic']))}" if e["subtopic"] else "") + " " + _dir_pill(e["direction"]) + " " + dk.pill(SESSION_KO.get(e["session"], e["session"]))
        sub = [report_title.kst_hm(e["first_post_at"]), f"대상 {e['target']}" if e.get("target") else ""]
        if e["post_count"] > 1:
            sub.append(f"연타 {e['post_count']}")
        if e["confounded_daily"]:
            sub.append("거시 발표 겹침")
        rows.append((name, f"강도 {e['intensity']}", _esc(" · ".join(x for x in sub if x))))
    if not rows:
        return dk.muted("최근 24시간에 시장 관련 발언 이벤트가 없습니다.")
    return dk.ccard(rows, left="65%")


def sec_trends(a):
    """급상승 주제 (7일) — C 카드: 주제(+N: 90일 내 처음), 값 점수, 보조 줄 7일 이벤트·평균 강도."""
    rows = []
    for i, t in enumerate(a["trend_scores"][:8], 1):
        name = f"{i}. {_esc(_k(t['key']))}" + (dk.NEW_PILL if t["is_new_90d"] else "")
        rows.append((name, f"{t['score']:.0f}점", _esc(f"7일 이벤트 {t['events_7d']} (직전 {t['events_prev_7d']}) · 평균 강도 {t['avg_intensity']:.1f}")))
    if not rows:
        return dk.muted("최근 7일 이벤트가 없어 점수를 내지 않습니다.")
    out = dk.ccard(rows, left="65%")
    ne = a["new_entrants"]
    if ne["target"] or ne["symbol"]:
        out += dk.guide("처음 등장", "직전 90일 없이 7일 안에 처음 나온 대상 — " + ", ".join(ne["target"] + ne["symbol"]))
    return out


def sec_windows(a):
    """30일 흐름 — C 카드: 주제, 값 이벤트 수, 보조 줄 평균 강도·부정 비율·직전 30일 대비."""
    blk = a["windows"].get("30D") or {}
    rows = []
    for r in [x for x in blk.get("dims", {}).get("topic", []) if x["events"] > 0][:8]:
        delta = "직전 30일 대비 —" if r["delta_events"] is None else f"직전 30일 대비 {r['delta_events']:+.0f}%"
        rows.append((_esc(_k(r["key"])), f"{r['events']}건",
                     _esc(f"평균 강도 {r['avg_intensity']:.1f} · 부정 비율 {int((r['neg_ratio'] or 0) * 100)}% · {delta}" if r["avg_intensity"] else delta)))
    if not rows:
        return dk.muted("30일 데이터가 아직 없습니다.")
    note = "최근 30일" + ("" if blk.get("compare_to_previous") else " · 직전 30일 데이터가 없어 변화량은 표시하지 않습니다")
    return dk.ccard(rows, left="55%") + dk.guide("기준", note)


def _x(v):
    if v is None:
        return dk.dash()
    return f'<span style="font-weight:{"700" if v >= 1.5 else "400"};">{v:.2f}×</span>'


def _p(st):
    """p (보정 전) + q (주제 안 다중 검정 BH 보정). 회색 = 보통 날과 구분 안 됨, 굵게 = 보정 뒤에도 유의."""
    pl = (st or {}).get("placebo")
    if not pl:
        return dk.dash()
    q = pl.get("q_bh")
    q_html = f'<span style="color:{MUTED};font-size:{dk.TINY};"> q{q:.2f}</span>' if q is not None else ""
    if pl["indistinguishable"]:
        return f'<span style="color:{MUTED};">{pl["p_two_sided"]:.2f}</span>{q_html}'
    if pl.get("robust"):
        return f'<b>{pl["p_two_sided"]:.2f}</b>{q_html}'
    return f'{pl["p_two_sided"]:.2f}{q_html}'


ASSET_KO = {"SPY": "S&P 500", "QQQ": "나스닥 100", "SMH": "반도체", "XLK": "기술", "XLF": "금융", "XLE": "에너지", "XLV": "헬스케어",
            "XLI": "산업재", "XLY": "경기소비재", "XLP": "필수소비재", "XLU": "유틸리티", "XLB": "소재", "XLRE": "부동산", "XLC": "통신",
            "NVDA": "엔비디아", "TSLA": "테슬라", "AAPL": "애플", "MSFT": "마이크로소프트", "AMZN": "아마존", "GOOGL": "알파벳", "META": "메타",
            "TLT": "장기 국채", "GLD": "금", "USO": "원유", "UUP": "달러"}
HORIZON_KO = {"close": "오늘", "d5": "5일"}   # 전환 버튼 이름 (2026-10-11 사용자)


def _asset(sym):
    return f"{ASSET_KO[sym]}({sym})" if sym in ASSET_KO else sym


ACC_CHEV = ('<svg class="acc-chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>')


def _chart_card(rows, horizon):
    """그래프 설명 카드 (2026-10-11 사용자): 제목 = 결론 한 줄, 그 아래 설명 한 문장, 글머리표(16px 검정) 나머지, 읽는 법·주의는 카드 안 ⓘ 안내 글."""
    span = "당일" if horizon == "close" else "5거래일 동안"
    robust = [r for r in rows if r["robust"]]
    loose = [r for r in rows if not r["robust"] and r["lo"] is not None and not (r["lo"] <= r["mean"] <= r["hi"])]
    if robust:
        title = f"{len(rows)}개 자산 중 {len(robust)}개만 보통 날 범위 밖"
        desc = (" · ".join(_asset(r["sym"]) for r in robust) + f"만 이 주제 발언 뒤 {span} 보통 날과 다르게 움직였고, 나머지는 구분되지 않았습니다.")
        theme = "uncertain"
    else:
        title = f"{len(rows)}개 자산 모두 보통 날 범위 안"
        desc = f"이 주제 발언 뒤 {span} 시장이 평소와 다르게 움직였다고 볼 근거가 없습니다."
        theme = "neutral"
    items = [("남은 반응", f"{_asset(r['sym'])} {r['mean']:+.2f}% · 보통 날 범위 {r['lo']:+.2f} ~ {r['hi']:+.2f}% 밖 · 보정 q {r['q']:.2f}") for r in robust]
    if loose:
        items.append(("띠 밖이지만 옅은 막대", " · ".join(f"{_asset(r['sym'])} {r['mean']:+.2f}%" for r in loose)
                      + f" — 하나만 보면 드물지만 {len(rows)}개 자산을 함께 보면 우연으로도 나올 수 있어 근거로 삼지 않습니다"))
    big = max((r for r in rows if not r["robust"] and r not in loose), key=lambda r: abs(r["mean"]), default=None)
    if big:
        items.append(("가장 크게 움직인 자산", f"{_asset(big['sym'])} {big['mean']:+.2f}% — 보통 날과 구분되지 않음 (p {big['p']:.2f})"))
    lis = "".join(f'<li style="margin:4px 0;"><b style="color:#111;">{_esc(t)}</b> · {_esc(x)}</li>' for t, x in items)
    note_html = ""   # 읽는 법은 그래프 아래 별도 카드(_read_card) — 2026-10-11 사용자
    if horizon == "d5":
        note_html += dk.guide("주의", "5일 구간은 창이 겹쳐 실제보다 강해 보일 수 있고, 원인을 뜻하지 않습니다", line=False)
    bg, bd = dk.CARD_DIR[theme]
    if theme == "neutral":
        bd = "#CBD5E1"   # 회색 강조 카드도 일반 카드와 구분되게 테두리 한 단계 진하게 (2026-10-11 사용자: 1번 — 모양은 항상 강조 카드, 색만 결과로)
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:10px 14px;margin:8px 0;">'   # 강조 카드 형식 (가이드라인 2절)
            f'<div style="font-weight:700;color:#111;">{_esc(title)}</div>'
            f'<div style="font-size:{dk.SMALL};color:#111;margin:2px 0 0;">{_esc(desc)}</div>'
            + (f'<ul style="margin:8px 0 0 20px;padding:0;list-style:disc;font-size:{dk.SMALL};color:#111;line-height:1.55;">{lis}</ul>' if lis else "")
            + (f'<div style="margin-top:8px;padding-top:6px;border-top:1px solid {bd};">{note_html}</div>' if note_html else "") + "</div>")


def _read_card(horizon):
    """그래프 읽는 법 — 그래프 바로 아래 별도 카드 (dk.guide_card)."""
    span = "당일" if horizon == "close" else "5거래일 동안"
    return dk.guide_card("읽는 법", [("막대", f"발언 뒤 {span} S&P 500 대비 평균"),
                                    ("회색 띠", "발언 없는 날에도 흔히 나오는 범위(95%)"),
                                    ("진한 막대", "여러 자산을 함께 본 보정 뒤에도 남은 값")])


def _table_fold(inner_html):
    """표 접기 — '표 보기' 버튼을 누르면 펼친다 (details data-acc, 테마 CSS가 화살표를 돌린다)."""
    return (f'<details data-acc="1" style="margin:4px 0 8px;"><summary style="cursor:pointer;list-style:none;display:flex;justify-content:center;align-items:center;gap:6px;'
            f'padding:8px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;color:#111;font-size:{dk.SMALL};font-weight:700;">표 보기 {ACC_CHEV}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


DIR_TABS = (("negative", "부정 발언"), ("positive", "긍정 발언"), ("", "전체"))   # 하위탭 (2026-10-11 사용자)


def _charts():
    try:
        with open(os.path.join(config.OUTPUT_DIR, "reaction_charts.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _table_rows(blk):
    rows = []
    for sym in config.ALL_SYMBOLS:
        hz = blk["symbols"].get(sym, {})
        st = hz.get("close")
        if not st or not st["publishable"]:
            continue
        g = lambda h: (hz.get(h) or {}).get("mean") if (hz.get(h) or {}).get("publishable") else None  # noqa: E731
        rows.append([f"<b>{sym}</b>", st["n"], _pct(g("immediate")), _pct(st["mean"]), _pct(g("next_close")),
                     _pct(g("d5")), f"{st['neg_pct']:.0f}%", _x(g("rel_range")), _x(g("rel_volume")), _p(st)])
    return rows


def _table_legend(noise_p):
    return (dk.guide_card("읽는 법", [("수치", f"{config.BENCHMARK} 대비 초과 반응(%) — {config.BENCHMARK} 행만 원수익률"),
                                ("즉각", "장외 발언은 다음 개장 갭, 정규장 발언은 시가→종가"),
                                ("변동폭·거래량", f"직전 {config.REL_LOOKBACK_DAYS}거래일 평소 대비 배수, 1.00× = 보통"),
                                ("p", f"발언 없는 날에서 같은 수만큼 뽑았을 때 이 정도 평균이 우연히 나올 비율 — {noise_p:.2f} 이상(회색)이면 보통 날과 구분되지 않음"),
                                ("q", f"자산 × 구간 수십 개를 한꺼번에 검정한 데 대한 보정값 — {noise_p:.2f} 미만(굵게)만 보정 뒤에 남는 값")])
            + dk.guide("주의", "+5일은 창이 겹친 관측이고, 모두 발언 뒤 관찰된 값이라 인과가 아닙니다"))


def _group_panel(blk, gkey, charts, noise_p):
    """한 그룹(주제 × 방향) — 오늘·5일 패널(data-hz-panel: 설명 카드가 그래프 위) + 표 접기."""
    import chart_reaction
    c = blk["counts"]
    hz_html = ""
    for h in ("close", "d5"):
        rows = chart_reaction.rows_for(blk, h)
        info = (charts.get(gkey) or {}).get(h)
        if not rows:   # 이 구간만 표본이 모자람 (5일 뒤 가격이 아직 없는 최근 발언 등) — 빈 화면 대신 안내
            n_h = max((((blk["symbols"].get(sym) or {}).get(h) or {}).get("n") or 0) for sym in config.ALL_SYMBOLS)
            hz_html += (f'<div data-hz-panel="{h}"><div data-hz-label="1" style="font-size:{dk.SMALL};font-weight:700;color:#111;margin:8px 0 4px;">{HORIZON_KO[h]}</div>'
                        + dk.muted(f"{HORIZON_KO[h]} 구간은 표본 축적 중 — 관측일 {n_h}일 / 필요 {config.MIN_CLEAN_N}일. 쌓이면 그래프가 나옵니다.") + "</div>")
            continue
        img = ""
        if info:
            img = (f'<a href="{_esc(info["url"])}" target="_blank" rel="noopener" title="그래프 확대 보기" style="display:block;max-width:720px;">'
                   f'<img src="{_esc(info["url"])}" alt="{_esc(_k(gkey.split("#")[0]))} {HORIZON_KO[h]} 반응 그래프" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/></a>')
        hz_html += (f'<div data-hz-panel="{h}"><div data-hz-label="1" style="font-size:{dk.SMALL};font-weight:700;color:#111;margin:8px 0 4px;">{HORIZON_KO[h]}</div>'
                    + _chart_card(rows, h) + img + (_read_card(h) if img else "") + "</div>")
    rows = _table_rows(blk)
    if not rows:
        return dk.muted(f"표본 축적 중 — 관측일 {c['clean']}일 / 필요 {config.MIN_CLEAN_N}일. 쌓이면 그래프가 나옵니다.")
    ik = c.get("immediate_kinds", {})
    table = _table_fold(dk.muted(f"과거 관측일 {c['clean']}일 · 이벤트 {c['total']} · 거시 발표 겹침 제외 {c['confounded']} · 장외 {ik.get('gap', 0)} / 정규장 {ik.get('intraday', 0)} · 검정 {c.get('tests', 0)}개")
                        + dk.table(["자산", "N", "즉각", "당일", "익일", "+5일", "하락 비율", "변동폭", "거래량", "p · q"], rows) + _table_legend(noise_p))
    return hz_html + table


def _dir_switch(topic, a, charts, noise_p):
    """부정 발언 · 긍정 발언 · 전체 — 하위탭 (data-switch). 버튼에 관측일 수, 표본이 모자란 쪽은 회색. 첫 선택은 표본이 있는 첫 탭."""
    btns, panels, first = "", "", None
    for i, (d, label) in enumerate(DIR_TABS):
        gkey = f"{topic}#{d}" if d else topic
        blk = a["reactions"].get(gkey)
        n = (blk or {}).get("counts", {}).get("clean", 0)
        ok = bool(blk and _table_rows(blk))
        if ok and first is None:
            first = i
        btns += (f'<button type="button" data-switch-btn="{i}" class="rt-dir"{"" if ok else " data-empty=\"1\""}>{_esc(label)} '
                 f'<span style="font-size:{dk.MICRO};font-weight:400;">({n}일)</span></button>')   # 괄호는 한 단계 작게 (가이드라인 3-3)
        body = _group_panel(blk, gkey, charts, noise_p) if blk else dk.muted("아직 이 방향의 발언이 없습니다.")
        panels += f'<div data-switch-panel="{i}"><div data-switch-label="1" style="font-size:{dk.SMALL};font-weight:700;color:#111;margin:10px 0 4px;">{_esc(label)} <span style="font-size:{dk.MICRO};font-weight:400;">({n}일)</span></div>{body}</div>'
    return (f'<div data-switch="1" data-switch-first="{first or 0}" style="margin:0 0 8px;">'
            f'<div class="rt-dirs" data-switch-bar="1" hidden>{btns}</div>{panels}</div>')


def sec_reactions(a):
    """시장 반응 — 주제 서브탭(data-sub) × 방향 하위탭(부정·긍정·전체) × 오늘·5일 버튼(data-hz-control, 테마 JS가 서브탭 줄 오른쪽으로 옮긴다).
    각 화면: 설명 카드(강조) → 그래프 → 표 접기 (2026-10-11 사용자)."""
    import chart_reaction
    keys = chart_reaction.topics_for(a)
    noise_p = a.get("config", {}).get("placebo_noise_p", config.PLACEBO_NOISE_P)
    charts = _charts()
    out, waiting = [], []
    for k in keys:
        blk = a["reactions"].get(k)
        if not blk:
            continue
        if _table_rows(blk):
            out.append(dk.sub_label(_k(k)) + _dir_switch(k, a, charts, noise_p))
        else:
            waiting.append(f"{_k(k)} ({blk['counts']['clean']}/{config.MIN_CLEAN_N})")
    if waiting:
        out.append(dk.muted("표본 축적 중 (관측일 / 필요 20): " + ", ".join(waiting)))
    if not out:
        return dk.muted("오늘 이벤트 주제에 해당하는 과거 반응 데이터가 아직 없습니다.")
    control = ('<div class="rt-segs" data-hz-control="1" hidden>'
               + "".join(f'<button type="button" class="rt-seg" data-hz="{h}">{HORIZON_KO[h]}</button>' for h in ("close", "d5")) + "</div>")
    return control + "".join(out)


def sec_why(a):
    """관찰 종목 — C 카드: 주제, 값 ETF, 보조 줄 경로·관찰 종목."""
    rows, seen = [], set()
    for e in a["recent_events"]:
        if not e["rule_id"] or e["rule_id"] in seen:
            continue
        seen.add(e["rule_id"])
        name = f"<b>{_esc(_k(e['topic']))}</b>" + (f" / {_esc(_k(e['subtopic']))}" if e["subtopic"] else "")
        rows.append((name, _esc(e["etf"] or "—"), _esc(f"경로 {_k(e['path_text']) or '—'} · 관찰 {', '.join(e['affected'][:10]) or '—'}")))
    if not rows:
        return dk.muted("오늘 이벤트에 연결된 매핑 규칙이 없습니다.")
    return dk.ccard(rows, left="65%") + dk.guide("관찰 종목", [("고르는 법", "정적 매핑 규칙 — 섹터 → ETF → 상위 10종목 + 본문에 나온 기업"), ("성격", "AI 판단이 아닙니다")])


def sec_narrative(n, key):
    if not n or not n.get(key):
        return dk.muted("서술 없음.")
    return dk.bullets(_k(t) for t in n[key])   # Gemini 문장 안의 영어 주제·섹터 이름도 한국어로


def sec_footer(a):
    s = a["data_status"]
    return dk.footer(
        f"데이터: Truth Social 게시물 공개 아카이브(CNN) · 가격 Yahoo Finance · 거시 일정 FRED. 분류 Gemini, 집계·통계 파이썬. "
        f"이벤트 누적 {s['events_total']:,}개 · 가격 기준일 {_esc(dk.day(s['bars_last_day']) or '—')}.",
        "이 글의 시장 반응 수치는 과거 발언 이후 관찰된 값이며 인과 관계나 향후 방향을 의미하지 않습니다. 투자 권고가 아닙니다.")


# ── 조립 (구획 제목은 짧은 명사 — 가이드라인 2절. 홈 카드 CARDS: speech = (머리)·달라진 것, watch = 내일 볼 것) ──

def build_body(a, n):
    return "\n".join([
        dk.WRAP_OPEN,
        sec_lead(a, n),
        dk.section("발언", sec_recent(a), tab=TAB_TODAY),
        dk.section("급상승 주제", sec_trends(a), summary="최근 7일", tab=TAB_TODAY),
        dk.section("달라진 것", sec_narrative(n, "what_changed"), tab=TAB_TODAY),
        dk.section("내일 볼 것", sec_narrative(n, "watch_tomorrow")
                   + dk.guide("주의", [("근거", "시장 반응 탭에서 보정 q가 함께 작은 값만 고릅니다 — 주제당 수십 개 조합을 검정했기 때문"),
                                       ("+3일·+5일", "창이 겹친 관측"), ("성격", "인과나 방향 예측이 아닙니다")]), tab=TAB_TODAY),
        dk.section("30일 흐름", sec_windows(a), tab=TAB_FLOW),
        dk.section("시장 반응", sec_reactions(a), tab=TAB_REACT),   # 탭 이름과 같아 제목은 숨고, 탭 아래 안내 문구는 두지 않는다 (2026-10-11 사용자)
        dk.section("관찰 종목", sec_why(a), tab=TAB_REACT),
        sec_footer(a),
        dk.WRAP_CLOSE,
    ])


def render(analysis_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    analysis_path = analysis_path or os.path.join(output_dir, "trump_analysis.json")
    narrative_path = narrative_path or os.path.join(output_dir, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    n = None
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            n = json.load(f)

    title = report_title.post_title(report_title.today_kst())
    body = build_body(a, n)
    body_path = os.path.join(output_dir, "trump_report_body.html")
    preview_path = os.path.join(output_dir, "trump_report.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    print(f"[html] {len(body):,}자 → {body_path} · 미리보기 {preview_path}")
    return body_path, preview_path, title


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
