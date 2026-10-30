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

dk.TIP_SRC = "CNN · Yahoo Finance"   # 툴팁 기본 데이터 출처 — 게시물(CNN Truth Social 아카이브) · 가격. 게시물만 세는 툴팁은 CNN (2026-10-20 사용자)

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

def sec_counts(a):
    """지난 24시간 집계 — 14px 캡슐 줄을 발언 제목 오른쪽에 (2026-10-11 사용자). 글 머리 카드는 없앴다. → (제목 옆 캡슐, 미분류 안내 줄)"""
    v = a["post_volume"]["last_24h"]
    ev = a["recent_events"]
    top = ev[0] if ev else None
    items = [("게시물", f"{v['total']}건"), ("정책 관련", f"{v['policy']}건"), ("시장 관련", f"{len(ev)}건")]
    if top:
        items.append(("가장 강한 발언", f"{_esc(_k(top['topic']))}{' / ' + _esc(_k(top['subtopic'])) if top['subtopic'] else ''} · 강도 {top['intensity']}"))
    note = dk.muted(f"최근 게시물 {v['pending']}건은 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다.") if v["pending"] else ""
    return dk.capsules(items, size=dk.TINY, in_title=True), note


SEO_LEAD_MAX = 120   # 검색 결과 요약 문단 글자 수 상한 (2026-10-18 검색 노출)


def _topic_name(topic, subtopic=None):
    return _k(topic) + (f" / {_k(subtopic)}" if subtopic else "")


def sec_seo_lead(a, date_str):
    """본문 맨 위 요약 한 문단 — 구글 · 네이버가 검색 결과 요약으로 쓰게 (2026-10-18 검색 노출).
    파이썬 값만으로 만든다(LLM 없음). data-lead · data-cards 를 달지 않는다 — 홈 카드 파서(reportSections)가 머리로 읽지 않게.
    빠진 값은 그 조각을 뺀다. 길면 뒤 조각부터 뺀다: 30일 최다 주제 → 가장 강한 발언 → 급상승 주제."""
    try:
        _, m, d = date_str.split("-")[:3]
        date = f"{int(m)}월 {int(d)}일 "
    except (ValueError, AttributeError):
        date = ""
    ev = a.get("recent_events") or []
    head = f"{date}트럼프 SNS 발언 가운데 최근 24시간 시장 관련 이벤트는 {len(ev)}건입니다."
    parts = []
    ts = a.get("trend_scores") or []
    if ts:
        parts.append(f"최근 7일 가장 빠르게 늘어난 주제는 {_k(ts[0]['key'])}")
    if ev:
        parts.append(f"가장 강한 발언은 {_topic_name(ev[0]['topic'], ev[0].get('subtopic'))}(강도 {ev[0]['intensity']})")   # recent_events 는 강도 순
    top30 = next((x for x in ((a.get("windows") or {}).get("30D") or {}).get("dims", {}).get("topic", []) if x["events"] > 0), None)
    if top30:
        parts.append(f"30일 동안 가장 많이 말한 주제는 {_k(top30['key'])}")
    while parts:
        text = head + " " + ", ".join(parts) + "입니다."
        if len(text) <= SEO_LEAD_MAX:
            break
        parts.pop()
    else:
        text = head
    return (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">'
            f"{_esc(text)}</p>")


def sec_recent(a):
    """발언 — C 카드: 주제/하위주제 + 방향·세션 라벨, 보조 줄에 시각·대상·연타, 값은 강도."""
    rows = []
    for e in a["recent_events"]:
        name = f"<b>{_esc(_k(e['topic']))}</b>" + (f" / {_esc(_k(e['subtopic']))}" if e["subtopic"] else "") + dk.pill_row(_dir_pill(e["direction"]) + dk.pill(SESSION_KO.get(e["session"], e["session"])), outer=dk.PILL_GAP)
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
    out = dk.ccard(rows, emph=True)   # 읽는 법 · 용어는 제목 오른쪽 툴팁 둘 (2026-10-12 사용자: "읽는 법과 나머지를 통합해서 2개만 툴팁으로") — build_body
    return out   # 처음 등장은 제목 줄 툴팁 (2026-10-13 사용자)


# 강도 척도 (prompts/classify.txt) — 툴팁에서 오늘 평균 강도를 쉬운 말로 읽어 준다
INTENSITY_WORDS = ((2, "지나가는 언급"), (4, "의견 · 평가"), (6, "조치 없는 강한 주장"), (8, "정책 경고나 구체적 조치 언급"),
                   (9, "정책 발표 예고"), (10, "바로 시행하는 정책 발표"))


def _inten_word(v):
    r = round(v)
    return next(w for top, w in INTENSITY_WORDS if r <= top)


def _trend_tips(a):
    """급상승 주제 툴팁 — 계산은 aggregate.trend_scores(), 강도 척도는 prompts/classify.txt.
    툴팁 글 틀은 디자인-가이드라인 2-6 (뜻 · 오늘 · 기록상, 2026-10-18 사용자). 점수 = 늘어난 정도 · 강도 · 최근성 · 새로움의
    주제 사이 순위를 config.TREND_WEIGHTS 비중대로 더한 값 — 공식은 툴팁에 두지 않는다."""
    t = a["trend_scores"][0]
    read = ("최근 7일 동안 갑자기 많이 말하기 시작한 세부 주제를 점수 순으로 줄 세운 것\n"
            f"· 오늘 1위 : {_k(t['key'])}, 그 앞 7일 {t['events_prev_7d']}건에서 이번 7일 {t['events_7d']}건이 됐다\n"
            "· 30일 흐름과 차이 : 30일 흐름은 큰 주제별 한 달 건수, 여기는 최근 1주에 갑자기 늘어난 세부 주제")
    terms = ("카드 오른쪽 점수와 아래 작은 줄 숫자의 뜻\n"
             f"· 점수 {t['score']:.0f}점 : 늘어난 정도 · 구체성 · 최근인지 · 처음인지를 합쳐 오늘 주제끼리 견준 값. 다른 날과는 견주지 않는다\n"
             f"· 7일 이벤트 {t['events_7d']}건 : 이어 올린 글은 한 건으로 센 발언 수. 괄호는 그 앞 7일\n"
             f"· 평균 강도 {t['avg_intensity']:.1f} : 정책이 얼마나 구체적인지 1~10으로 매긴 값. 이 정도면 {_inten_word(t['avg_intensity'])}")
    ne = a["new_entrants"]
    names = ne["target"] + ne["symbol"]
    first = ("그 앞 90일 동안 없다가 최근 7일에 처음 이름이 나온 나라 · 종목\n"
             f"· 오늘 {len(names)}개 : {', '.join(names)}") if names else ""
    return [(k, dk.with_src(v, "CNN")) for k, v in [("읽는 법", read), ("용어", terms)] + ([("처음 등장", first)] if first else [])]   # 처음 등장도 툴팁 (2026-10-13 사용자)


FLOW_FLAT_PCT = 10   # 직전 30일 대비 전체 건수 변화가 이 % 미만이면 "비슷함"


def _flow_card(blk):
    """30일 흐름 요약 — 강조 카드 (2026-10-11 사용자: "결과 건수를 자료를 바탕으로 요약, 강조 카드 형식, 타이틀과 설명으로").
    첫 줄 `발언 흐름 : 늘어남 / 줄어듦 / 비슷함`(증감 색), 얇은 선 아래 3px 점 글머리표 — 설명 문장, `**라벨** : 내용`.
    사실만: 건수·차이·비율. 평가어·전망은 쓰지 않는다."""
    rows = [x for x in blk.get("dims", {}).get("topic", []) if x["events"] > 0]
    if not rows:
        return ""
    has_prev = blk.get("compare_to_previous")
    total = sum(r["events"] for r in rows)
    allr = blk["dims"]["topic"]
    prev = sum(r["prev_events"] or 0 for r in allr) if has_prev else None
    neg = sum((r["neg_ratio"] or 0) * r["events"] for r in rows) / total
    k = lambda r: _k(r["key"])
    if prev:
        pct = (total - prev) / prev * 100
        state, color = (("비슷함", "#64748B") if abs(pct) < FLOW_FLAT_PCT else ("늘어남", dk.UP) if pct > 0 else ("줄어듦", dk.DOWN))
        up = [r for r in allr if (r["delta_events"] or 0) > 0]
        down = [r for r in allr if (r["delta_events"] or 0) < 0]
        tail = ("모든 주제가 줄었습니다" if not up and down else "모든 주제가 늘었습니다" if up and not down
                else f"{len(up)}개 주제가 늘고 {len(down)}개 주제가 줄었습니다")
        desc = f"최근 30일 시장 관련 이벤트는 {total}건으로, 그 앞 30일 {prev}건보다 {abs(total - prev)}건 {'많습니다' if total > prev else '적습니다' if total < prev else '같습니다'} ({pct:+.0f}%). {tail}"
    else:
        state, color = f"이벤트 {total}건", "#111"
        desc = f"최근 30일 시장 관련 이벤트는 {total}건입니다. 그 앞 30일 데이터가 아직 없어 늘고 줄었는지는 보지 않습니다"
    items = [(None, desc)]
    top = rows[0]
    items.append(("가장 많은 주제", f"{k(top)} {top['events']}건, 전체의 {top['events'] / total * 100:.0f}%"))
    if prev:
        if up:
            items.append(("늘어난 주제", " · ".join(f"{k(r)} {r['prev_events']}건 → {r['events']}건" for r in sorted(up, key=lambda r: -r["delta_events"])[:3])))
        if down:
            d = min(down, key=lambda r: r["delta_events"])
            items.append(("가장 크게 줄어든 주제", f"{k(d)} {d['prev_events']}건 → {d['events']}건 ({d['delta_events']:+d}건)"))
    big = [r for r in rows if r["events"] >= 3]   # 3건 미만은 비율이 한두 건에 흔들려 뺀다
    if big:
        hi = max(big, key=lambda r: (r["neg_ratio"] or 0, r["events"]))
        items.append(("부정 발언 비율", f"전체 {neg * 100:.0f}% · 가장 높은 주제 {k(hi)} {(hi['neg_ratio'] or 0) * 100:.0f}% ({round((hi['neg_ratio'] or 0) * hi['events'])}/{hi['events']}건)"))
        mx = max(r["avg_intensity"] for r in big)
        tops = [k(r) for r in big if abs(r["avg_intensity"] - mx) < 0.05]
        items.append(("평균 강도가 가장 높은 주제", f"{'·'.join(tops)} {mx:.1f} (1~10)"))
    bg, bd = dk.EMPH_BG, dk.EMPH_BD

    def li(t, x):
        head = f'<b>{_esc(t)}</b> : ' if t else ""
        return dk.dot_li(head + dk.tint(_esc(x)), size=3, lh=dk.LH_EMPH)   # 강조 카드 18px 글 → 행간 32
    lis = "".join(li(t, x) for t, x in items)
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{dk.EMPH_PAD - dk.VP_EMPH}px 14px;margin:8px 0;line-height:{dk.LH_EMPH};">'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)
            f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
            f'<span style="font-weight:700;color:#111;font-size:{dk.EMPH_NAME};">발언 흐름 : <span style="color:{color};">{_esc(state)}</span></span></span> '
            f'<div style="margin-top:{14 - dk.VP_EMPH + 3}px;padding-top:{14 - dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{dk.SMALL};">'   # 제목 ~ 구분선 14px (2026-10-12 사용자: 4 → 14)
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul></div></div>")


def _windows_tip(blk):
    """주제별 30일 읽는 법 툴팁 — 가이드라인 2-6 틀. 맨 위 주제의 건수 · 직전 30일 차이 · 평균 강도를 읽어 준다.
    부정 발언 비율 줄은 툴팁에 두지 않는다 (2026-10-11 사용자)."""
    top = next(x for x in blk["dims"]["topic"] if x["events"] > 0)
    if blk.get("compare_to_previous") and top["delta_events"] is not None:
        d = top["delta_events"]
        cmp_ = f"그 앞 30일 {top['prev_events']}건보다 {abs(d)}건 {'많다' if d > 0 else '적다'}" if d else f"그 앞 30일과 같은 {top['prev_events']}건"
        now = f"· {_k(top['key'])} {top['events']}건 : 가장 많이 말한 주제. {cmp_}"
    else:
        now = f"· {_k(top['key'])} {top['events']}건 : 가장 많이 말한 주제. 그 앞 30일 자료가 아직 없어 늘고 준 것은 보지 않는다"
    lines = ["큰 주제(무역 · 연준 등)별로 최근 30일 동안 몇 번 말했는지를 많은 순으로 본 것", now]
    if top["avg_intensity"]:
        lines.append(f"· 평균 강도 {top['avg_intensity']:.1f} : 정책이 얼마나 구체적인지 1~10으로 매긴 값. 이 정도면 {_inten_word(top['avg_intensity'])}")
    lines.append("· 급상승 주제와 차이 : 여기는 한 달 동안 꾸준히 말한 양, 급상승 주제는 최근 1주에 갑자기 늘어난 것")
    return "\n".join(lines)


def sec_windows(a):
    """30일 흐름 — C 카드: 주제, 값 이벤트 수, 보조 줄 평균 강도·부정 발언 비율·직전 30일 대비."""
    blk = a["windows"].get("30D") or {}
    rows = []
    for r in [x for x in blk.get("dims", {}).get("topic", []) if x["events"] > 0][:8]:
        delta = "직전 30일 대비 —" if r["delta_events"] is None else f"직전 30일 대비 {r['delta_events']:+.0f}건"   # 건수 차이 (전에는 % 로 잘못 붙어 있었다, 2026-10-11 수정)
        rows.append((_esc(_k(r["key"])), f"{r['events']}건",
                     _esc(f"평균 강도 {r['avg_intensity']:.1f} · 부정 발언 비율 {int((r['neg_ratio'] or 0) * 100)}% · {delta}" if r["avg_intensity"] else delta)))
    if not rows:
        return dk.muted("30일 데이터가 아직 없습니다.")
    return _flow_card(blk) + dk.section("주제별 30일", dk.ccard(rows), tab=TAB_FLOW, one_line=True, aside=dk.tips_right([("읽는 법", dk.with_src(_windows_tip(blk), "CNN"))]))   # 일반 구획 제목 + 읽는 법 ? 오른쪽 (2026-10-13 사용자)   # 읽는 법은 소제목 옆 ? (2026-10-12 사용자)   # 요약 강조 카드는 맨 위 (2026-10-11 사용자)   # 기준(최근 30일)은 읽는 법 카드 안으로 (2026-10-11 사용자: 건수·차이를 안내 글에 자세히)


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
    q_html = f'<span style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};"> q{q:.2f}</span>' if q is not None else ""
    if pl["indistinguishable"]:
        return f'<span style="color:{dk.SUB};">{pl["p_two_sided"]:.2f}</span>{q_html}'
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


def _chart_card(rows, horizon, read=""):   # read = 그래프 읽는 법 — 제목 줄 오른쪽 `읽는 법 ?` (2026-10-12 사용자)
    """결론 카드 — 엔비디아 상태 카드(시장 국면) 형식 (2026-10-11 사용자: "배치·컬러·스타일 참고, 회색 배경 / 강조 컬러 배경").
    첫 줄 왼쪽 `자산 n개`(굵게) · 오른쪽 상태(굵게: 모두 범위 안 = 회색 / k개 범위 밖 = 주황), 얇은 선 아래 3px 점 글머리표 16px 검정,
    맨 아래 ⓘ 주의(5일). 배경: 남은 반응 없음 = 회색 #F8FAFC, 있음 = 강조 오렌지 #FFF7EE."""
    span = "당일" if horizon == "close" else "5거래일 동안"
    robust = [r for r in rows if r["robust"]]
    loose = [r for r in rows if not r["robust"] and r["lo"] is not None and not (r["lo"] <= r["mean"] <= r["hi"])]
    n = len(rows)
    # 쉬운 말 (2026-10-11 사용자: "범위 밖 · 모두 범위 안은 어렵다, 자세히") — "보통 날" = 발언이 없던 날
    if robust:
        state, color, (bg, bd) = f"평소와 다른 자산 {len(robust)}개", dk.WARN, dk.CARD_DIR["positive"]
        names = " · ".join(f"{_asset(r['sym'])} {r['mean']:+.2f}%" for r in robust)
        desc = (f"{n}개 자산 중 {names}만 발언이 없던 날에는 보기 드문 크기로 움직였습니다. "
                f"나머지 {n - len(robust)}개는 이 주제 발언 뒤 {span}에도 평소와 비슷했습니다")
    else:
        state, color, bg, bd = "평소와 같음", "#64748B", "#F8FAFC", "#CBD5E1"
        desc = (f"{n}개 자산 모두 이 주제 발언 뒤 {span} 발언이 없던 날과 비슷한 정도로만 움직였습니다. "
                f"이 발언이 시장을 따로 움직였다고 볼 근거가 없습니다")
    items = [(None, desc)]
    items += [("평소와 다른 움직임", f"{_asset(r['sym'])} {r['mean']:+.2f}%. 발언이 없던 날에는 보통 {r['lo']:+.2f} ~ {r['hi']:+.2f}% 사이에서 움직입니다. "
                                   f"{n}개 자산을 한꺼번에 따져도 우연으로 보기 어려운 크기입니다 (q {r['q']:.2f})") for r in robust]
    if loose:
        items.append(("우연일 수 있는 움직임", " · ".join(f"{_asset(r['sym'])} {r['mean']:+.2f}%" for r in loose)
                      + f". 이 자산 하나만 보면 평소보다 크지만, {n}개 자산을 동시에 보면 이 정도는 우연으로도 나올 수 있어 근거로 삼지 않습니다"))
    big = max((r for r in rows if not r["robust"] and r not in loose), key=lambda r: abs(r["mean"]), default=None)
    if big:
        items.append(("가장 크게 움직인 자산", f"{_asset(big['sym'])} {big['mean']:+.2f}%. 그래도 발언이 없던 날에 흔히 나오는 크기입니다 (p {big['p']:.2f})"))

    def li(t, x):
        head = f'<b>{_esc(t)}</b> : ' if t else ""   # 라벨 글머리표 "**라벨** : 내용", 증감 색 (가이드라인 3-3, 2026-10-11 사용자)
        return dk.dot_li(head + dk.tint(_esc(x)), size=3, lh=dk.LH_EMPH)   # 강조 카드 18px 글 → 행간 32
    lis = "".join(li(t, x) for t, x in items)
    note = ""   # 주의는 제목 줄의 주의 ? 툴팁 (_read_text) — 2026-10-13 사용자
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{dk.EMPH_PAD - dk.VP_EMPH}px 14px;margin:8px 0;line-height:{dk.LH_EMPH};">'   # 강조 카드: 위아래 24 · 행간 32 (2026-10-12 사용자)
            f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
            f'<span style="font-weight:700;color:#111;font-size:{dk.EMPH_NAME};">시장의 반응 : <span style="color:{color};">{_esc(state)}</span></span>'
            f'{dk.tips_right(read) if read else ""}</span> '   # "시장의 반응: 평소와 같음" (2026-10-11 사용자). 자산 수는 설명 문장에
            f'<div style="margin-top:{14 - dk.VP_EMPH + 3}px;padding-top:{14 - dk.VP_EMPH}px;border-top:1px solid {bd};font-size:{dk.SMALL};">'   # 제목 ~ 구분선 14px (2026-10-12 사용자: 4 → 14)
            f"<ul style='margin:-9px 0;padding:0;list-style:none;'>{lis}</ul>{note}</div></div>")


def _read_text(rows, horizon):
    """그래프 읽는 법 · 주의 — 결론 카드 제목 줄 오른쪽 툴팁 (2026-10-12 사용자: 읽는 법 카드 대신 제목 옆 툴팁).
    가이드라인 2-6 틀. 진한 막대 = placebo.robust (다중 검정 보정 q < PLACEBO_NOISE_P), 회색 띠 = 발언 없는 날 평균의 95% 범위."""
    span = "당일" if horizon == "close" else "5거래일 동안"
    robust = [r for r in rows if r["robust"]]
    if robust:
        now = f"· 진한 막대 {len(robust)}개 : 발언 없던 날에는 보기 드문 크기로 움직인 자산. {', '.join(_asset(r['sym']) for r in robust)}"
    else:
        now = "· 진한 막대 0개 : 모든 자산이 평소 범위 안이라 발언 뒤 따로 움직였다고 보기 어렵다"
    read = (f"이 주제 발언 뒤 {span} 자산마다 S&P 500보다 더 오르거나 내린 평균을 막대로 그린 것\n" + now + "\n"
            "· 나누는 법 : 막대가 회색 띠(발언 없던 날에 흔한 범위) 밖이고, 여러 자산을 함께 따져도 남으면 진하게")
    caution = ("5일 동안의 움직임은 발언이 몰린 시기에 기간이 겹쳐 실제보다 강해 보일 수 있다\n"
               "· 참고 : 발언 뒤에 관찰된 움직임일 뿐, 발언이 원인이라는 뜻은 아니다") if horizon == "d5" else ""
    return [("읽는 법", read), ("주의", caution)]   # 주의도 툴팁, 둘 다 제목 줄 오른쪽 (2026-10-13 사용자)


def _table_fold(inner_html):
    """표 접기 — '표 보기' 버튼을 누르면 펼친다 (details data-acc). 버튼에 툴팁을 두지 않는다 — 읽는 법은 펼친 표 아래 본문에 (2026-10-13 사용자)."""
    return (f'<details data-acc="1" style="margin:4px 0 8px;"><summary style="{dk.FOLD_BTN}">표 보기 {ACC_CHEV}</summary>'
            f'<div style="margin-top:8px;">{inner_html}</div></details>')


EMPTY_ATTR = ' data-empty="1"'   # f-string 안에 \" 를 쓰면 파이썬 3.10(CI)에서 문법 오류
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
    """펼친 표 아래 본문 안내 — ⓘ 읽는 법 글머리표 + ⓘ 주의 한 줄 (2026-10-13 사용자: 버튼 툴팁 대신 표 아래 본문에)."""
    return (dk.guide("읽는 법", [("수치", f"{config.BENCHMARK} 대비 초과 반응(%), {config.BENCHMARK} 행만 원수익률"),
                             ("즉각", "장외 발언은 다음 개장 갭, 정규장 발언은 시가 → 종가"),
                             ("변동폭 · 거래량", f"직전 {config.REL_LOOKBACK_DAYS}거래일 평소 대비 배수, 1.00× = 보통"),
                             ("p", f"발언 없는 날에서 같은 수만큼 뽑았을 때 이 정도 평균이 우연히 나올 비율. {noise_p:.2f} 이상(회색)이면 보통 날과 구분되지 않음"),
                             ("q", f"자산 × 구간 수십 개를 한꺼번에 검정한 데 대한 보정값. {noise_p:.2f} 미만(굵게)만 보정 뒤에 남는 값")])
            + dk.guide("주의", "+5일은 창이 겹친 관측이고, 모두 발언 뒤 관찰된 값이라 인과가 아닙니다", line=False))


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
            hz_html += (f'<div data-hz-panel="{h}"><div data-hz-label="1" style="font-size:{dk.SMALL};line-height:{dk.LH_CARD};font-weight:700;color:#111;margin:8px 0 4px;">{HORIZON_KO[h]}</div>'
                        + dk.muted(f"{HORIZON_KO[h]} 구간은 표본 축적 중. 관측일 {n_h}일 / 필요 {config.MIN_CLEAN_N}일. 쌓이면 그래프가 나옵니다.") + "</div>")
            continue
        img = ""
        if info:
            img = (f'<a href="{_esc(info["url"])}" target="_blank" rel="noopener" title="그래프 확대 보기" style="display:block;max-width:720px;">'
                   f'<img src="{_esc(info["url"])}" alt="{_esc(_k(gkey.split("#")[0]))} {HORIZON_KO[h]} 반응 그래프" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/></a>')
        hz_html += (f'<div data-hz-panel="{h}"><div data-hz-label="1" style="font-size:{dk.SMALL};line-height:{dk.LH_CARD};font-weight:700;color:#111;margin:8px 0 4px;">{HORIZON_KO[h]}</div>'
                    + _chart_card(rows, h, _read_text(rows, h) if img else "") + img + "</div>")
    rows = _table_rows(blk)
    if not rows:
        return dk.muted(f"표본 축적 중. 관측일 {c['clean']}일 / 필요 {config.MIN_CLEAN_N}일. 쌓이면 그래프가 나옵니다.")
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
        btns += (f'<button type="button" data-switch-btn="{i}" class="rt-dir"{"" if ok else EMPTY_ATTR}>{_esc(label)} '
                 f'<span style="font-size:{dk.MICRO};font-weight:400;">({n}일)</span></button>')   # 괄호는 한 단계 작게 (가이드라인 3-3)
        body = _group_panel(blk, gkey, charts, noise_p) if blk else dk.muted("아직 이 방향의 발언이 없습니다.")
        panels += f'<div data-switch-panel="{i}"><div data-switch-label="1" style="font-size:{dk.SMALL};line-height:{dk.LH_CARD};font-weight:700;color:#111;margin:10px 0 4px;">{_esc(label)} <span style="font-size:{dk.MICRO};font-weight:400;">({n}일)</span></div>{body}</div>'
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
    return dk.ccard(rows, left="65%") + dk.guide("관찰 종목", [("고르는 법", "정적 매핑 규칙(섹터 → ETF → 상위 10종목 + 본문에 나온 기업)"), ("성격", "AI 판단이 아닙니다")])


# 내일 볼 것 주의 툴팁 — 가이드라인 2-6 틀. 고르는 근거 = placebo.robust (주제당 수십 개 조합을 검정해 보정 q 로 거른다, narrate.check_watch)
WATCH_TIP = ("과거 같은 주제 발언 뒤 평소와 다르게 움직였던 자산만 골라 적은 관찰 목록\n"
             "· 고르는 법 : 여러 자산을 한꺼번에 따져도 우연으로 보기 어려운 움직임만 남긴다\n"
             "· 참고 : 과거에 관찰된 움직임일 뿐, 내일 방향을 알려 주지 않는다")


def _has_watch(n):
    """'내일 볼 것'에 고정 문장(관찰 대상 없음) 말고 실제 문장이 있나."""
    return any(config.NONE_WATCH[:14] not in s for s in (n or {}).get("watch_tomorrow") or [])


def sec_narrative(n, key):
    if not n or not n.get(key):
        return dk.muted("서술 없음.")
    return dk.bullets(_k(t) for t in n[key])   # Gemini 문장 안의 영어 주제·섹터 이름도 한국어로


# ── 조립 (구획 제목은 짧은 명사 — 가이드라인 2절. 홈 카드 CARDS: speech = (머리)·달라진 것, watch = 내일 볼 것) ──

def build_body(a, n):
    counts_aside, counts_note = sec_counts(a)
    return dk.fix_colons(dk.align_titles("\n".join([   # ":" 앞뒤 띄우기 (2026-10-11 사용자: 꼭 반드시, 모든 페이지) · 카드 밖 제목은 좌측 기준선(ALIGN_PX) (2026-10-23 사용자)
        dk.WRAP_OPEN,
        sec_seo_lead(a, report_title.today_kst()),   # 본문 첫 요소 = 검색 결과 요약 문단 (2026-10-18 검색 노출). 날짜는 글 제목과 같은 today_kst
        dk.section("급상승 주제", sec_trends(a), tab=TAB_TODAY, one_line=True,
                   aside=dk.tips_right(_trend_tips(a)) if a["trend_scores"] else ""),   # ? 툴팁은 제목 오른쪽, 폰에서도 한 줄 · "최근 7일"은 카드 아래 (2026-10-11 사용자)
        dk.section("발언", counts_note + sec_recent(a), tab=TAB_TODAY, aside=counts_aside),   # 급상승 주제 아래로 (2026-10-14 사용자) · 24시간 집계 캡슐은 발언 제목 오른쪽 (2026-10-11 사용자)
        # 서술이 없거나 "없다" 고정 문장뿐이면 구획을 통째로 뺀다 — 매일 같은 문장이 반복되는 글은 비슷한 글로 분류된다 (2026-10-16 사용자, 인물-발언-레이더-기획 5절)
        dk.section("달라진 것", sec_narrative(n, "what_changed"), tab=TAB_TODAY) if (n or {}).get("what_changed") else "",
        dk.section("내일 볼 것", sec_narrative(n, "watch_tomorrow"), tab=TAB_TODAY, one_line=True,   # 주의는 제목 줄 오른쪽 툴팁 (2026-10-13 사용자)
                   aside=dk.tips_right([("주의", WATCH_TIP)]))
        if _has_watch(n) else "",
        dk.section(TAB_FLOW, sec_windows(a), tab=TAB_FLOW),   # 탭 이름과 같은 제목 → 테마가 숨긴다 (2026-10-11 사용자: 30일 흐름 타이틀 삭제)
        dk.section("시장 반응", sec_reactions(a), tab=TAB_REACT),   # 탭 이름과 같아 제목은 숨고, 탭 아래 안내 문구는 두지 않는다 (2026-10-11 사용자)
        dk.section("관찰 종목", sec_why(a), tab=TAB_REACT),
        # 출처 · 면책 꼬리말 없음 — 블로그 공통 푸터가 맡는다 (2026-10-18 사용자: 중복 안내 금지)
        dk.WRAP_CLOSE,
    ])))


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
    body = build_body(a, n)   # 글 끝 "AI 서술" 줄 없음 — 공통 푸터의 AI 고지와 중복 (2026-10-25 사용자)
    body_path = os.path.join(output_dir, "trump_report_body.html")
    preview_path = os.path.join(output_dir, "trump_report.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    mock = dk.write_mock(body, os.path.join(output_dir, "trump_mock.html"), title)   # 테마 입힌 목업 (2026-10-11 사용자)
    print(f"[html] {len(body):,}자 → {body_path} · 미리보기 {preview_path}" + (f" · 목업 {mock}" if mock else ""))
    return body_path, preview_path, title


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
