"""테마 페이지 HTML (doc/기획/테마-모니터-기획.md 4절) — 종목 페이지와 같은 뼈대: 맨 앞 요약 → 질문 · 상태 머리 카드(제목 옆 ? = 읽는 법) → 질문 카드 → 종목 그래프.
2026-10-21 사용자: 탭 없음 · 읽는 법은 상단 제목 옆 툴팁 · 증감은 모두 색 · 종목은 전부 그래프.
숫자 · 문장 전부 파이썬. 카드 조각은 엔비디아 렌더러(R._state_card · R._col_chart)와 레이더(render_pages.wrap)를 그대로 쓴다.
"""

import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "stock-radar"))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))

import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402
import render_pages as RP  # noqa: E402
import themes as T  # noqa: E402
import universe as U  # noqa: E402

UP, DOWN, MUTED, WARN, NOTE, TINY = R.UP, R.DOWN, R.MUTED, R.WARN, dk.NOTE, dk.TINY
KIND_COLOR = {"positive": UP, "negative": DOWN, "neutral": MUTED, "uncertain": WARN}


def _esc(t):
    return dk.esc(t)


def _md(d):
    d = datetime.date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _pp(v, digits=1):
    return "—" if v is None else f"{v:+.{digits}f}".replace("-", "−")


def _usd_m(m):
    """$M → 한국어 금액. 192.6 → 1.9억 달러, 3.5 → 350만 달러."""
    if m >= 100:
        return f"{m / 100:.1f}억 달러"
    return f"{m * 100:,.0f}만 달러"


def _url(sym):
    if sym not in U.BY_SYM:
        return None
    return U.NVDA_REPORTS_URL if sym in U.REPORT_TYPE else U.page_url(sym)


def _short(sym):
    """그래프 가로축 이름 — 한글 이름이 길면 티커."""
    nm = U.name(sym) if sym in U.BY_SYM else sym
    return nm if len(nm) <= 5 else sym


def _cards(html):
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{html}</div>'


def _lead(text):
    """맨 앞 요약 문장 — 증감(−7.0%p · +14bp …)도 색 (2026-10-21 사용자: "디자인 규칙에 반드시 있을 텐데" — 가이드라인 3-3, 요약 문장 포함)."""
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{dk.tint(_esc(text))}</p>'


def page_title(t, day):
    """페이지 제목 = 이름 + 기준 날짜 — 테마 JS 가 날짜를 제목 오른쪽 끝에 놓는다 (가이드라인 10-5, 2026-10-21 사용자: 기준 날짜 표기 위치는 제목 우측)."""
    d = datetime.date.fromisoformat(str(day)[:10])
    return f"{t['title']} {d.year}년 {d.month}월 {d.day}일"


def _head(t, state, kind, sub, guide):
    """머리 상태 카드 — 질문 제목 옆 ? 툴팁이 읽는 법 (2026-10-21 사용자: 탭 대신 상단 제목 옆 툴팁). 둘째 줄 요약은 증감 색."""
    card = R._state_card(t["question"], state, kind, KIND_COLOR[kind], [(dk.tint(_esc(sub)), "html")], "", tip=guide)
    return dk.cards(card)


def _stock_chart(title, members, key="ret_20d", fmt=None, height=140):
    """종목별 세로 막대 (2026-10-21 사용자: 종목은 전부 그래프). members = [{"sym", key}]. 오름 빨강 · 내림 파랑.
    그래프 아래 종목 이름 줄은 두지 않는다 — 그래프 가로축과 중복 (2026-10-21 사용자). 종목 페이지 링크는 2단계에서 가로축 이름에."""
    ms = [m for m in members if m.get(key) is not None]
    if not ms:
        return ""
    chart = R._col_chart([(m.get("label") or _short(m["sym"]), [m[key]]) for m in ms], [R._sign_bg], [R._sign_fg], height=height, fmt=fmt)
    return R._card_title(title) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:12px 12px 4px;">{chart}</span></span></div>'


# ── A. AI 투자 ──────────────────────────────────────────────────────────

def body_ai(t, a, day, guide):
    bs = a["baskets"]
    whole = a["whole"]
    ins = [b["name"] for b in bs if b["state"] == "유입"]
    outs = [b["name"] for b in bs if b["state"] == "유출"]
    n_all = whole["n"]
    lead = (f"{_md(day)} 기준 AI 투자 테마 {n_all}종목은 지난 20거래일 동안 S&P 500 보다 {_pp(whole['rel_20d'])}%p {'높았다' if (whole['rel_20d'] or 0) >= 0 else '낮았다'}. "
            + (f"세 갈래({' / '.join(b['name'] for b in bs)}) 가운데 유입은 {', '.join(ins) if ins else '없고'}" + (f", 유출은 {', '.join(outs)}" if outs else "") + "이다. ")
            + (f"{n_all}종목 중 {whole['breadth']['above_ma20']}종목이 20일선 위에 있다." if whole.get("breadth") else ""))
    sub = f"20일 S&P 500 대비 {_pp(whole['rel_20d'])}%p · 유입 {len(ins)}갈래 · 유출 {len(outs)}갈래"
    out = _lead(lead) + _head(t, a["state"], a["theme_kind"], sub, guide)

    # ① 돈이 몰리나 — 갈래별 20일 상대 수익률 + 막대
    lines = [("row", b["name"], f"{_pp(b['rel_20d'])}%p", f"{b['state']} · 20일 {_pp(b['ret_20d'])}% (S&P {_pp(a['bench_ret_20d'])}%)") for b in bs]
    chart = R._col_chart([(b["name"], [b["ret_20d"], a["bench_ret_20d"]]) for b in bs], [R._sign_bg, lambda v: R._GRAY_BAR], [R._sign_fg, lambda v: NOTE], height=130)
    legend = R._legend_chips([("갈래 오름", R._PASTEL_UP), ("갈래 내림", R._PASTEL_DN), ("S&P 500", R._GRAY_BAR)])
    lines.append((f'<span style="display:block;padding:6px 12px 0;">{chart}{legend}</span>', "html"))
    tip = (f"갈래마다 동일가중 바스켓의 20거래일 수익률에서 S&P 500 수익률을 뺀 값. +{T.FLOW_PP:.0f}%p 넘으면 유입, −{T.FLOW_PP:.0f}%p 아래면 유출\n"
           "· 세 갈래가 같이 유입이면 AI 테마 자체로 돈이 오는 것, 한 갈래만이면 다른 이유일 수 있다")
    cards = R._state_card("돈이 몰리나?", a["state"], a["theme_kind"], KIND_COLOR[a["theme_kind"]], lines, "", tip=dk.with_src(tip, "Yahoo Finance"), fold=True, opened=True)

    # ② 넓게 오르나
    br = whole.get("breadth") or {}
    share = br["above_ma20"] / br["n"] if br.get("n") else None
    st2 = "넓게 오름" if share is not None and share >= 0.6 else "몇 종목만" if share is not None and share <= 0.4 else "반반"
    k2 = "positive" if st2 == "넓게 오름" else "negative" if st2 == "몇 종목만" else "neutral"
    # 값 = 20일선 위 종목 수, 설명 = 그 뜻 + 오늘 오른 종목 수 (2026-10-21 사용자: "0/5 가 뭐지?" — 두 숫자가 한 줄에 섞여 있었다)
    # 값 = "20일선 위는 (0/5)" — 앞말은 보통 굵기, 숫자만 굵게. 뜻 = "5종목 오름" (2026-10-21 사용자)
    lines = [("row", b["name"], f'<span style="font-weight:400;">20일선 위는</span> ({b["breadth"]["above_ma20"]}/{b["breadth"]["n"]})', f"{b['breadth']['up_today']}종목 오름", True)
             for b in bs if b.get("breadth")]
    cards += R._state_card("넓게 오르나?", st2, k2, KIND_COLOR[k2], lines, "",
                           tip=f"{n_all}종목 가운데 20일 이동평균선(최근 20거래일 평균 가격) 위에 있는 종목이 몇인가. 60% 이상이면 넓게 오름, 40% 이하면 몇 종목만\n"
                               f"· 오늘 {br.get('above_ma20', 0)}종목 / {n_all}종목 : 테마가 올라도 몇 종목이 끌고 있으면 넓게 오른 게 아니다", fold=True,
                           below_notes=True)   # "5종목 오름" 은 괄호 없이 이름 아래 줄 (2026-10-21 사용자)

    # ③ 평소와 다른가
    nz = whole.get("normal") or {}
    z = nz.get("z")
    st3 = "평소 범위 밖" if z is not None and abs(z) >= 2 else "평소 범위 안"
    k3 = ("positive" if nz.get("today_pct", 0) > 0 else "negative") if st3 == "평소 범위 밖" else "neutral"
    lines = [("row", "오늘 테마 전체", f"{_pp(nz.get('today_pct'), 2)}%", f"평소 하루 ±{nz.get('sigma_pct', 0):.2f}% 의 {abs(z):.1f}배" if z is not None else "")]
    if whole.get("rsi") is not None:
        lines.append(("row", "RSI 14", f"{whole['rsi']:.0f}", "70 위 과열 · 30 아래 과매도"))
    cards += R._state_card("평소와 다른가?", st3, k3, KIND_COLOR[k3], lines, "", tip=f"테마 바스켓의 오늘 수익률을 지난 {nz.get('n', 0)}일 하루 수익률 표준편차로 나눈 값. 2배를 넘으면 평소 범위 밖", fold=True)

    # ④ 거래는 늘었나
    vrs = [b["vol_ratio"] for b in bs if b.get("vol_ratio")]
    vr = sum(vrs) / len(vrs) if vrs else None
    st4 = "평소보다 많음" if vr and vr >= 1.5 else "평소보다 적음" if vr and vr <= 0.7 else "평소 수준"
    k4 = "uncertain" if st4 == "평소보다 많음" else "neutral"
    lines = [("row", b["name"], f"{b['vol_ratio']:.1f}배", "20일 평균 거래량 대비 중앙값") for b in bs if b.get("vol_ratio")]
    cards += R._state_card("거래는 늘었나?", st4, k4, KIND_COLOR[k4], lines, "", tip="갈래 종목들의 오늘 거래량 ÷ 지난 20일 평균, 그 중앙값. 1.5배 이상이면 많음", fold=True)
    out += _cards(cards)

    # 종목별 — 갈래마다 그래프 (2026-10-21 사용자)
    for b in bs:
        out += _stock_chart(f"{b['name']} {len(b['members'])}종목 · 20일 수익률 (%)", b["members"])
    return out


# ── B. 연준 인하 기대 ───────────────────────────────────────────────────

def body_fed(t, a, day, guide):
    if a.get("state") == "자료 없음":
        return _lead(f"{_md(day)} 기준 금리 자료를 받지 못했습니다.") + dk.muted("FRED 자료를 받지 못해 오늘은 비어 있습니다. 다음 갱신 때 채웁니다.")
    gap, chg = a["gap_bp"], a["gap_change_bp"]
    d = a["direction"]
    what = (f"기준금리({a['policy']:.2f}%)보다 2년물({a['y2']:.2f}%)이 {abs(gap):.0f}bp {'낮아' if gap > 0 else '높아'}, 시장은 앞으로 2년 동안 "
            + {"인하": "금리가 내려갈 것으로", "인상": "금리가 오르거나 동결이 길어질 것으로", "동결": "지금 수준이 이어질 것으로"}[d] + " 보고 있다.")
    lead = f"{_md(a['day'])} 기준 {what} 20거래일 전보다 그 차이는 {_pp(chg, 0)}bp {'커졌다' if (chg or 0) > 0 else '줄었다' if (chg or 0) < 0 else '그대로다'}. 오늘 상태는 {a['state']}다."
    sub = f"기준금리 − 2년물 {_pp(gap, 0)}bp · 20일 변화 {_pp(chg, 0)}bp"
    out = _lead(lead) + _head(t, a["state"], a["theme_kind"], sub, guide)

    st1 = {"인하": f"{abs(gap):.0f}bp 인하를 본다", "인상": f"{abs(gap):.0f}bp 인상 쪽", "동결": "동결에 가깝다"}[d]
    k1 = "positive" if d == "인하" else "negative" if d == "인상" else "neutral"
    lines = [("row", "기준금리 (실효 연방기금)", f"{a['policy']:.2f}%", "FRED DFF"),
             ("row", "2년물 국채", f"{a['y2']:.2f}%", "FRED DGS2 — 앞으로 2년 기준금리 평균에 대한 시장의 생각"),
             ("row", "차이 (기준 − 2년물)", f"{_pp(gap, 0)}bp", "양수 = 인하 기대, 음수 = 인상 · 동결 장기화")]
    cards = R._state_card("시장은 인하를 보나?", st1, k1, KIND_COLOR[k1], lines, "", tip=dk.with_src("2년물은 선물 시장 없이도 볼 수 있는 '시장이 보는 기준금리 경로'. 기준금리와의 차이가 인하 기대의 크기", "FRED"), fold=True, opened=True)

    lines = [("row", "20거래일 전 차이", f"{_pp(a['gap_bp_20d_ago'], 0)}bp", ""), ("row", "변화", f"{_pp(chg, 0)}bp", f"±{t['change_bp']}bp 넘으면 상태가 바뀐다")]
    if a.get("y10_change_20d") is not None:
        lines.append(("row", "10년물 20일 변화", f"{_pp(a['y10_change_20d'], 0)}bp", f"지금 {a['y10']:.2f}%"))
    if a.get("curve_change_20d") is not None:
        lines.append(("row", "장단기 차 (10년 − 2년)", f"{_pp((a['curve'] or 0) * 100, 0)}bp", f"20일 변화 {_pp(a['curve_change_20d'], 0)}bp"))
    gs = a.get("gap_series") or []
    if len(gs) >= 20:
        pts = [gs[-1 - k] for k in (60, 40, 20, 10, 5, 0) if k < len(gs)]
        chart = R._col_chart([(f"{p[0][5:7]}.{p[0][8:10]}", [p[1]]) for p in pts], [R._sign_bg], [R._sign_fg], height=120, fmt=lambda v: f"{v:+.0f}".replace("-", "−"))
        lines.append((f'<span style="display:block;padding:6px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{dk.NAME};">기준금리 − 2년물 (bp)</span>{chart}</span>', "html"))
    cards += R._state_card("기대가 커지나, 줄어드나?", a["state"], a["theme_kind"], KIND_COLOR[a["theme_kind"]], lines, "", tip="차이의 20거래일 변화. 커지면 시장이 더 빨리 · 더 많이 내릴 것으로 보는 것", fold=True)

    cd = a.get("cpi_days") or []
    if cd:
        last = cd[-1]
        st3 = f"{_md(last['day'])} {_pp(last['y2_change_bp'], 0)}bp"
        k3 = "negative" if last["y2_change_bp"] > 0 else "positive" if last["y2_change_bp"] < 0 else "neutral"   # 2년물 오름 = 인하 기대 후퇴 → 파랑
        lines = [("row", f"{_md(x['day'])} CPI 발표", f"{_pp(x['y2_change_bp'], 0)}bp", "발표일 2년물 변화 (전일 대비)") for x in reversed(cd)]
        chart = R._col_chart([(f"{x['day'][5:7]}.{x['day'][8:10]}", [x["y2_change_bp"]]) for x in cd], [R._sign_bg], [R._sign_fg], height=110, fmt=lambda v: f"{v:+.0f}".replace("-", "−"))
        lines.append((f'<span style="display:block;padding:6px 12px 0;">{chart}</span>', "html"))
        cards += R._state_card("CPI 발표 뒤 2년물은?", st3, k3, KIND_COLOR[k3], lines, "", tip="소비자물가 발표일 2년물 금리의 하루 변화. 오르면 시장이 인하 기대를 줄인 날. 30건이 쌓이기 전에는 통계를 말하지 않는다", fold=True)
    out += _cards(cards)

    sens = a.get("sensitive") or []
    if sens:
        out += _stock_chart("금리 민감 자산 · 20일 수익률 (%)", [{"sym": x["sym"], "ret_20d": x["ret_20d"], "label": x["name"]} for x in sens])
    return out


# ── D. 임원 · 기관 매매 ────────────────────────────────────────────────

def body_insider(t, a, day, guide):
    lead = (f"{_md(day)} 기준 지난 {a['days']}일 동안 후보 {a['universe']}종목의 임원 거래 공시에서 계획 외 매수는 {a['buy_n']}건({_usd_m(a['buy_usd'])}), "
            f"계획 외 매도는 {a['sell_n']}건({_usd_m(a['sell_usd'])}), 사전 계획 매도는 {a['plan_n']}건이었다. 오늘 상태는 {a['state']}다.")
    sub = f"계획 외 매수 {a['buy_n']}건 · 계획 외 매도 {a['sell_n']}건 · 사전 계획 매도 {a['plan_n']}건 / {a['days']}일"
    out = _lead(lead) + _head(t, a["state"], a["theme_kind"], sub, guide)
    lines = [("row", "계획 외 매수", f"{a['buy_n']}건 · {_usd_m(a['buy_usd'])}", "임원이 자기 돈으로 장내 매수 (10만 달러 이상)"),
             ("row", "계획 외 매도", f"{a['sell_n']}건 · {_usd_m(a['sell_usd'])}", "사전 매도 계획(10b5-1) 아닌 매도"),
             ("row", "사전 계획 매도", f"{a['plan_n']}건 · {_usd_m(a['plan_usd'])}", "미리 정한 일정대로 파는 것 — 신호로 세지 않는다"),
             ("row", "공시가 있던 회사", f"{a['n_companies']}/{a['universe']}", "")]
    tip = ("매수 건수가 2건 이상이고 계획 외 매도의 2배 이상이면 순매수, 계획 외 매도가 3건 이상이고 매수의 2배 이상이면 순매도\n"
           "· 10% 보유자(기관) 공시는 발행사 확인 전이라 빼고 센다 (2단계)")
    cards = R._state_card("임원은 사나, 파나?", a["state"], a["theme_kind"], KIND_COLOR[a["theme_kind"]], lines, "", tip=dk.with_src(tip, "SEC EDGAR Form 4"), fold=True, opened=True)
    sh = a.get("short")
    if sh:
        st4 = "느는 종목이 더 많음" if sh["rising"] > sh["falling"] else "주는 종목이 더 많음" if sh["falling"] > sh["rising"] else "반반"
        k4 = "negative" if sh["rising"] > sh["falling"] else "positive" if sh["falling"] > sh["rising"] else "neutral"
        lines = [("row", "공매도 비율이 늘어난 종목", f"{sh['rising']}/{sh['n']}", "직전 집계 대비"), ("row", "줄어든 종목", f"{sh['falling']}/{sh['n']}", "")]
        cards += R._state_card("하락에 거는 돈은?", st4, k4, KIND_COLOR[k4], lines, "", tip=dk.with_src("FINRA 공매도 잔고(월 2회)의 유통주식 대비 비율이 직전 집계보다 늘었는지", "FINRA · Yahoo Finance"), fold=True)
    out += _cards(cards)
    # 누가 샀나 · 팔았나 — 한 그래프, 회사마다 순매수 금액(매수 − 계획 외 매도): 위 빨강 · 아래 파랑, 백만 달러 (2026-10-21 사용자: 종목은 전부 그래프)
    net = {}
    for p in a["buyers"]:
        net[p["sym"]] = net.get(p["sym"], 0.0) + p["buy_usd"]
    for p in a["sellers"]:
        net[p["sym"]] = net.get(p["sym"], 0.0) - p["sell_usd"]
    members = sorted(({"sym": s, "usd": v} for s, v in net.items() if abs(v) >= 0.05), key=lambda m: -m["usd"])
    if members:
        out += _stock_chart(f"누가 샀나 · 팔았나 (계획 외 순매수, 백만 달러 · {a['days']}일)", members, key="usd", fmt=lambda v: f"{v:+.1f}".replace("-", "−"), height=150)
    return out


# ── 공통 ────────────────────────────────────────────────────────────────

def reading_guide(t):
    """읽는 법 — 머리 카드 제목 옆 ? 툴팁 (2026-10-21 사용자: 탭 대신 상단 타이틀 옆 툴팁)."""
    items = {
        "ai": ["세 갈래 : 반도체(만드는 쪽) · 데이터 센터(짓고 쓰는 쪽 — 클라우드 사업자 · 데이터센터 리츠) · 전력 설비(전기 · 냉각 · 네트워크). 세 쪽이 같이 가면 AI 투자 자체로 돈이 오는 것",
               f"유입 · 유출 : 갈래 바스켓(동일가중)의 {T.FLOW_DAYS}거래일 수익률 − S&P 500. ±{T.FLOW_PP:.0f}%p 가 기준",
               "사실 기록이다 — 오를지 내릴지를 말하지 않는다. 상태가 바뀐 뒤 어땠는지는 30건이 쌓인 뒤 기록으로"],
        "fed": ["2년물 국채 금리 ≈ 시장이 보는 앞으로 2년의 기준금리 평균. 기준금리보다 낮으면 인하를, 높으면 인상 · 동결 장기화를 보는 것",
                f"상태는 그 차이의 {T.FLOW_DAYS}거래일 변화로 정한다 (±{t.get('change_bp', 10)}bp)",
                "CPI 발표일 반응은 기록만 — 30건 전에는 평균을 말하지 않는다"],
        "insider": ["Form 4 = 임원 · 이사 · 10% 보유자가 자사주를 사고팔 때 2영업일 안에 내는 공시",
                    "계획 외 매수만 신호로 본다. 매도는 보상 · 세금 · 분산 이유가 많고, 사전 매도 계획(10b5-1)은 미리 정한 일정이다",
                    "10만 달러 미만 매수(주식 지급 등)와 10% 보유자 공시는 세지 않는다"],
    }[t["key"]]
    return "\n· ".join(items)


def page_body(t, a, day):
    fn = {"ai": body_ai, "fed": body_fed, "insider": body_insider}[t["key"]]
    body = fn(t, a["themes"][t["key"]], day, reading_guide(t))
    body += dk.muted("매일 아침 갱신 · 기록이 30일 쌓이면 상태가 바뀐 뒤의 분포를 함께 보여 줍니다")
    return RP.wrap(body)


def write_all(a, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    pages = {}
    for t in T.THEMES:
        if t["key"] not in a["themes"]:
            continue
        body = page_body(t, a, a["day"])
        title = page_title(t, a["day"])
        pages[t["slug"]] = (title, body)
        with open(os.path.join(out_dir, f"{t['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        dk.write_mock(body, os.path.join(out_dir, f"mock_{t['slug']}.html"), title)
    return pages
