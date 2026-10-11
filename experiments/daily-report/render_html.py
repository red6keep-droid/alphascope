"""렌더링: 수집 원본 숫자 + 분석 계산값 + Gemini 문구 → HTML (디자인-가이드라인.md · experiments/design_kit.py, 2026-10-11)

모든 숫자는 수집 데이터(report_input.json)와 파이썬 분석(analysis.json)에서 직접
렌더링한다. Gemini는 분석 문구(summary 등)와 뉴스 선택(index)만 사용한다.

analysis.json이 없으면(시계열 수집 실패) 지수 표는 기존 3열로 떨어지고
"무엇이 달라졌나" 섹션은 통째로 빠진다. 리포트가 그것 때문에 멈추지는 않는다.
"""

import html as html_mod
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402  — 디자인-가이드라인.md 공통 조각 (2026-10-11)

TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "templates", "report.html")

MARKERS = [
    "ONE_LINE", "REGIME_SECTION", "SUMMARY", "INDEX_TABLE", "CHANGE_SECTION",
    "BREADTH_SECTION", "SECTOR_SECTION", "GAINERS_TABLE", "GAINERS_COMMENT",
    "ATTENTION_TABLE", "ATTENTION_COMMENT", "NEWS_LIST", "MACRO_TABLE",
    "MACRO_COMMENT", "STATUS_BOARD", "OPINION", "RISK", "DATE", "UPDATED",
    "COVER_IMAGE",
]

# 신호등 색. 등락률의 빨강/파랑과 헷갈리지 않게 따로 둔다.
LIGHT_COLOR = {"🟢": "#2e9e5b", "🟡": "#d9a400", "🔴": "#d9534f"}

REGIME_COMPONENT_LABELS = {
    "trend": "추세",
    "breadth": "시장 폭",
    "volatility": "변동성",
    "rates": "금리 환경",
    "risk_appetite": "위험선호",
}

# 뉴스 테마 어휘. 프롬프트·validate_report와 같은 목록이어야 한다. 밖의 값은 '기타'로 접는다.
THEME_VOCAB = ["금리", "AI/반도체", "실적", "매크로", "에너지", "정책/규제", "지정학", "기타"]

# 뉴스 '관련 자산' 줄에서 심볼 대신 보여줄 이름
SYMBOL_NAMES = {
    "^GSPC": "S&P 500", "^IXIC": "나스닥", "^DJI": "다우", "^RUT": "러셀 2000",
    "^VIX": "VIX", "^TNX": "미국 10년물 금리", "^FVX": "미국 5년물 금리", "^IRX": "미국 3개월물 금리",
}

INDEX_LABELS = {   # 한국어 위주 (가이드라인 3-4). S&P 500·VIX 는 고유명으로 둔다
    "sp500": "S&P 500",
    "nasdaq": "나스닥",
    "dow": "다우존스",
    "russell": "러셀 2000",
    "vix": "VIX (변동성 지수)",
}
# 영어 용어 → 한국어 (Gemini 문구·라벨 표시용)
TERM_KO = {"위험선호(Risk-On)": "위험 선호", "위험회피(Risk-Off)": "위험 회피", "위험 선호(Risk-On)": "위험 선호", "위험 회피(Risk-Off)": "위험 회피",
           "Risk-On": "위험 선호", "Risk-Off": "위험 회피", "Risk On": "위험 선호", "Risk Off": "위험 회피", "Neutral": "중립",
           "Nasdaq": "나스닥", "Dow Jones": "다우존스", "Dow": "다우", "Russell 2000": "러셀 2000", "Market Regime": "시장 상태"}
TAB_TODAY, TAB_MARKET, TAB_STOCKS, TAB_RISK = "오늘", "시장", "종목·뉴스", "위험"

# report_input.json의 지수 키 → analysis.json series의 심볼 (analyze.INDEX_SYMBOL과 동일)
INDEX_SYMBOL = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "russell": "^RUT",
    "vix": "^VIX",
}

H2_STYLE = "color:#111;border-bottom:2px solid #eee;padding-bottom:8px;"

PREVIEW_WRAPPER = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>데일리 리포트 미리보기</title>
</head>
<body style="max-width:1440px;margin:0 auto;padding:16px;background:#fff;">
__BODY__
</body>
</html>
"""

UP_COLOR = "#d93025"
DOWN_COLOR = "#1a73e8"
MUTED = dk.MUTED


def _esc(text):
    return html_mod.escape(str(text), quote=False)


def _na(value):
    return value is None


def _fmt_price(value):
    if value is None:
        return "데이터 없음"
    return f"${float(value):,.2f}"


def _fmt_volume(value):
    if value is None:
        return "데이터 없음"
    return f"{int(value):,}"


def _pct_cell(change, unit="%", missing="데이터 없음"):
    if change is None:
        return f'<span style="color:#999;">{missing}</span>'
    change = float(change)
    color = UP_COLOR if change >= 0 else DOWN_COLOR
    sign = "+" if change >= 0 else ""
    return (
        f'<span style="color:{color};font-weight:bold;">'
        f"{sign}{change:.2f}{unit}</span>"
    )


def _arrows_cell(last5):
    """최근 5거래일 방향. 마지막이 오늘. 상승 빨강 · 하락 파랑 · 보합 회색."""
    if not last5:
        return '<span style="color:#999;">—</span>'
    colors = {"↑": UP_COLOR, "↓": DOWN_COLOR}
    return '<span style="font-family:monospace;letter-spacing:2px;">' + "".join(
        f'<span style="color:{colors.get(a, "#999")};">{a}</span>' for a in last5
    ) + "</span>"


def _scroll(table_html):
    """열이 많은 표는 좁은 화면에서 본문 대신 표만 가로 스크롤되게 감싼다."""
    return f'<div style="overflow-x:auto;">{table_html}</div>'


def _paragraph(rows, headers):
    parts = ['<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:17px;">']
    parts.append(
        "<tr>"
        + "".join(
            f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;">{_esc(h)}</th>'
            for h in headers
        )
        + "</tr>"
    )
    for row in rows:
        parts.append(
            "<tr>"
            + "".join(
                f'<td style="border:1px solid #ddd;padding:6px 8px;">{c}</td>' for c in row
            )
            + "</tr>"
        )
    parts.append("</table>")
    return "".join(parts)


def _text_block(text):
    if not str(text).strip():
        return '<span style="color:#999;">데이터 없음</span>'
    return "".join(f"<div>{_esc(line)}</div>" for line in str(text).splitlines())


def _korean_date(date_str):
    if not date_str:
        return date_str
    try:
        y, m, d = str(date_str).split("-")[:3]
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except Exception:
        return str(date_str)


def _cover_image(cover_url):
    if not cover_url:
        return ""
    src = html_mod.escape(str(cover_url), quote=True)
    return f'<img src="{src}" alt="데일리 브리핑 커버 이미지" style="width:100%;max-width:1024px;border-radius:8px;margin:0 0 16px 0;display:block;">'


def _text(text):
    """Gemini 문구 — 줄마다 문단(18px), 영어 용어는 한국어로. 비어 있으면 ⓘ 안내."""
    if not str(text or "").strip():
        return dk.muted("데이터 없음")
    return "".join(f'<div style="margin:0 0 6px;">{_esc(dk.ko(line, TERM_KO))}</div>' for line in str(text).splitlines() if line.strip())


def _light_word(light):
    return {"🟢": "정상", "🟡": "주의", "🔴": "경계"}.get(light, "")


def _light_pill(light, text=None):
    kind = {"🟢": "positive", "🟡": "uncertain", "🔴": "negative"}.get(light, "neutral")
    return dk.pill(text or _light_word(light) or "—", kind)


def sec_lead(report, analysis):
    """글 머리(제목 없음, data-lead): 한 줄 결론 D 카드. 홈 카드는 '(머리)'로 읽는다."""
    one = str(report.get("one_line") or "").strip()
    inner = f'<div style="font-weight:700;color:#111;">{_esc(dk.ko(one, TERM_KO))}</div>' if one else dk.muted("한 줄 결론 없음")
    return dk.cards(dk.dcard(inner, "neutral"))


def sec_regime(analysis, report):
    """시장 상태 — C 카드: 점수·등급·어제 대비 + 요소별 막대. 점수는 analyze.py 규칙값."""
    regime = (analysis or {}).get("regime") or {}
    comment = _text(report.get("regime_comment"))
    if regime.get("score") is None:
        return dk.muted("오늘은 시장 상태 점수를 계산하지 못했습니다.") + comment
    light = regime.get("light") or "🟡"
    rows = [("점수", f'{int(regime["score"])} <span style="color:{MUTED};font-weight:400;">/ 100</span> ' + _light_pill(light, dk.ko(regime.get("label") or "", TERM_KO)), "")]
    if regime.get("score_prev") is not None:
        rows.append(("어제 대비", dk.arrow(regime.get("delta") or 0, 0, ""), _esc(f"어제 {regime['score_prev']}점")))
    else:
        rows.append(("어제 대비", dk.dash(), "어제 점수 없음"))
    for key, label in REGIME_COMPONENT_LABELS.items():
        c = (regime.get("components") or {}).get(key) or {}
        score, mx = c.get("score"), c.get("max")
        if score is None or not mx:
            continue
        frac = score / mx
        col = LIGHT_COLOR["🟢"] if frac >= 0.7 else LIGHT_COLOR["🟡"] if frac >= 0.45 else LIGHT_COLOR["🔴"]
        rows.append((_esc(label), dk.hbar(score, mx, col) + f"{int(score)} <span style='color:{MUTED};font-weight:400;'>/ {int(mx)}</span>", ""))
    return dk.ccard(rows) + comment


def sec_indices(indices, analysis, report):
    """주요 지수 — C 카드: 지수, 값 가격 + 1일 등락, 보조 줄 5일·20일·최근 5일·위치."""
    series = (analysis or {}).get("series") or {}
    position = (analysis or {}).get("position") or {}
    rows = []
    for key in ("sp500", "nasdaq", "dow", "russell", "vix"):
        rec = indices.get(key) or {}
        s = series.get(INDEX_SYMBOL[key]) or {}
        label = (position.get(key) or {}).get("position_label")
        value = f'{_esc(_fmt_price(rec.get("price")))} {dk.arrow(rec.get("change_pct"))}'
        sub = []
        if s.get("ret_5d") is not None:
            sub.append(f"5일 {s['ret_5d']:+.2f}%")
        if s.get("ret_20d") is not None:
            sub.append(f"20일 {s['ret_20d']:+.2f}%")
        if s.get("last5"):
            sub.append("최근 5일 " + "".join(s["last5"]))
        if label:
            sub.append(label)
        rows.append((_esc(INDEX_LABELS.get(key, key)), value, _esc(" · ".join(sub))))
    return dk.ccard(rows) + _text(report.get("summary"))


def sec_change(analysis, report):
    """달라진 것 — 상대강도·추세·VIX C 카드 + 해설. 분석이 없으면 빈 문자열(구획 생략)."""
    if not analysis:
        return ""
    series = analysis.get("series") or {}
    position = analysis.get("position") or {}
    rs = analysis.get("rs") or {}
    vix = analysis.get("vix") or {}
    rows = [("성장주 − 시장 (Nasdaq − S&P 500 · 5일)", dk.arrow(rs.get("qqq_spy_5d"), 2, "%p"), "양수면 성장주 우위"),
            ("소형주 − 시장 (Russell 2000 − S&P 500 · 5일)", dk.arrow(rs.get("iwm_spy_5d"), 2, "%p"), "양수면 소형주·위험선호 우위"),
            ("동일가중 − 시총가중 (RSP − SPY · 5일)", dk.arrow(rs.get("rsp_spy_5d"), 2, "%p"), "양수면 상승이 넓게 퍼짐")]
    streak = rs.get("qqq_streak")
    if streak is not None:
        rows.append(("Nasdaq이 S&P 500을 웃돈 연속 일수", f"{int(streak)}일", "길수록 성장주 주도가 뚜렷"))
    out = dk.sub_label("상대강도") + dk.ccard(rows, left="60%")
    trows = []
    for key in ("sp500", "nasdaq", "russell"):
        s = series.get(INDEX_SYMBOL[key]) or {}
        p = position.get(key) or {}
        sub = []
        if s.get("up_days_20") is not None:
            sub.append(f"20일 중 상승 {s['up_days_20']} · 하락 {s['down_days_20']}")
        if p.get("from_high_pct") is not None:
            sub.append(f"20일 고점 대비 {p['from_high_pct']:+.2f}% · 저점 대비 {p['from_low_pct']:+.2f}%")
        trows.append((_esc(INDEX_LABELS[key]), _esc(p.get("position_label") or "—"), _esc(" · ".join(sub))))
    out += dk.sub_label("20일 위치") + dk.ccard(trows, left="40%")
    if vix.get("now") is not None and vix.get("prev_5d") is not None:
        out += dk.ccard([("VIX (5거래일)", f'{vix["prev_5d"]:.2f} → <b>{vix["now"]:.2f}</b> {dk.arrow(vix.get("change_5d") or 0.0, 2, "")}', "")])
    return out + _text(report.get("change_comment"))


def sec_breadth(analysis):
    """시장 폭 — C 카드. 프록시 모드는 섹터 ETF 상승 개수, 전수 모드는 상승/하락 종목 수."""
    b = (analysis or {}).get("breadth") or {}
    if b.get("ratio") is None:
        return ""
    light = (b.get("label") or "")[:1]
    rows = [("상승 비율", f'{b["ratio"]:.1f}% ' + _light_pill(light, (b.get("label") or "")[1:].strip() or None), "")]
    if b.get("mode") == "full":
        rows.append(("상승 / 하락 종목", f'<span style="color:{UP_COLOR};">{b.get("advancers")}</span> / <span style="color:{DOWN_COLOR};">{b.get("decliners")}</span>', "S&P 500 구성종목"))
        if b.get("new_high_52w") is not None:
            rows.append(("52주 신고가 / 신저가", f'{b["new_high_52w"]} / {b["new_low_52w"]}', ""))
    else:
        rows.append(("섹터 ETF 상승 / 하락", f'<span style="color:{UP_COLOR};">{b.get("sectors_up")}</span> / <span style="color:{DOWN_COLOR};">{b.get("sectors_down")}</span>',
                     f"{b.get('sectors_counted')}개 섹터 ETF 기준"))
    if b.get("rsp_spy_1d") is not None:
        rows.append(("동일가중 − 시총가중 (1일)", dk.arrow(b["rsp_spy_1d"], 2, "%p"), "양수면 상승이 소수 대형주에 몰리지 않은 것"))
        if b.get("rsp_spy_5d") is not None:
            rows.append(("동일가중 − 시총가중 (5일)", dk.arrow(b["rsp_spy_5d"], 2, "%p"), ""))
    return dk.ccard(rows, left="60%")


def sec_sectors(analysis, report):
    """섹터 — C 카드: 테마(ETF), 값 = 막대 + 등락률, 보조 줄 5일 순위 대비. 주도·약세 줄, 해설."""
    ranked = ((analysis or {}).get("sectors") or {}).get("ranked_1d") or []
    if not ranked:
        return ""
    max_abs = max(abs(r["ret_1d"]) for r in ranked) or 1.0
    rows = []
    for r in ranked:
        col = UP_COLOR if r["ret_1d"] >= 0 else DOWN_COLOR
        d = r.get("rank_change")
        sub = "" if d is None else (f"5일 순위 대비 ▲{d}" if d > 0 else f"5일 순위 대비 ▼{-d}" if d < 0 else "5일 순위와 같음")
        rows.append((f"{_esc(r['theme'])} ({_esc(r['etf'])})", dk.hbar(r["ret_1d"], max_abs, col) + dk.arrow(r["ret_1d"]), _esc(sub)))
    by_etf = {r["etf"]: r for r in ranked}
    names = lambda etfs: " · ".join(_esc(by_etf[e]["theme"]) for e in etfs if e in by_etf)  # noqa: E731
    sectors = analysis["sectors"]
    lead = dk.ccard([("주도", names(sectors.get("leaders") or []) or dk.dash(), ""), ("약세", names(sectors.get("laggards") or []) or dk.dash(), "")])
    return lead + dk.ccard(rows, left="45%") + _text(report.get("sector_comment"))


def _bp(bp):
    return "—" if bp is None else f"{int(bp):+d}bp"


def sec_macro(macro, analysis, report):
    """금리·지표 — C 카드: 지표, 값, 보조 줄 변화·기준일. 금리 변화에는 색을 쓰지 않는다."""
    rates = (analysis or {}).get("rates") or {}

    def fred(key):
        rec = macro.get(key)
        if not rec or rec.get("value") is None:
            return None, ""
        return f"{rec['value']:.2f}", rec.get("date", "")

    rows = []
    v10, d10 = fred("us10y")
    if rates.get("us10y") is not None:
        v10, d10 = f"{rates['us10y']:.2f}", (analysis or {}).get("as_of") or d10
    chg = f"1일 {_bp(rates.get('us10y_change_1d_bp'))} · 5일 {_bp(rates.get('us10y_change_5d_bp'))}" if rates.get("us10y_change_5d_bp") is not None else ""
    rows.append(("10년물 국채금리 (%)", _esc(v10) if v10 else dk.dash(), _esc(" · ".join(x for x in (chg, dk.day(d10)) if x))))
    for key, label in (("us2y", "2년물 국채금리 (%)"), ("spread_10_2", "10년 − 2년 (%p)"), ("fed_funds", "연방기금금리 (%)"),
                       ("unemployment_rate", "실업률 (%)"), ("cpi", "소비자물가 CPI (지수)"), ("vix", "VIX")):
        if key in ("us2y", "spread_10_2", "fed_funds") and not macro.get(key):
            continue
        v, d = fred(key)
        rows.append((label, _esc(v) if v else dk.dash(), _esc(dk.day(d))))
    out = dk.ccard(rows, left="55%")
    if rates.get("growth_label"):
        out += dk.ccard([("금리와 성장주", _esc(rates["growth_label"]), "")])
    return out + _text(report.get("macro_comment"))


def _quote_rows(quotes):
    """급등주·관심 종목 — 종목, 값 가격 + 등락, 보조 줄 거래량. data-pick: 홈 '오늘의 급등주' 카드가 읽는다."""
    rows = []
    for q in quotes or []:
        sym = q.get("symbol") or "-"
        r = dk.crow(_esc(sym), f'{_esc(_fmt_price(q.get("price")))} {dk.arrow(q.get("change_pct"))}', _esc(f"거래량 {_fmt_volume(q.get('volume'))}"), first=not rows)
        chg = q.get("change_pct")
        r = r.replace('<span style="', f'<span data-pick="1" data-sym="{_esc(sym)}" data-price="{_esc(_fmt_price(q.get("price")))}" data-chg="{"" if chg is None else f"{float(chg):+.2f}%"}" style="', 1)
        rows.append(r)
    if not rows:
        return dk.muted("데이터 없음")
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(rows)}</span></div>'


def _named_reaction(sym, value_html):
    """관련 자산 한 칸 — 이름까지 증감 색 (2026-10-11 사용자: % 만이 아니라 종목도 같이 색). 값이 bp 등 색 없는 경우는 이름도 기본색."""
    name = _esc(SYMBOL_NAMES.get(sym, sym))
    col = UP_COLOR if "▲" in value_html else DOWN_COLOR if "▼" in value_html else None
    return f'<span style="color:{col};">{name}</span> {value_html}' if col else f"{name} {value_html}"


def sec_news(input_data, report, analysis):
    """뉴스 — 목록: 테마 라벨 · 제목(글자) + 링크 아이콘, 보조 줄 관련 자산 반응 · 선정 이유 (14px)."""
    series = (analysis or {}).get("series") or {}
    rates = (analysis or {}).get("rates") or {}
    quotes = {q["symbol"]: q for q in input_data.get("gainers", []) + input_data.get("most_active", []) if q.get("symbol")}
    known = set(series) | set(quotes)

    def reaction(sym):
        if sym == "^TNX" and rates.get("us10y_change_1d_bp") is not None:
            return _esc(_bp(rates["us10y_change_1d_bp"]))
        if sym in series:
            return dk.arrow(series[sym].get("ret_1d"))
        return dk.arrow(quotes[sym].get("change_pct"))

    items = []
    for item in report.get("news", []):
        try:
            news_item = input_data.get("news", [])[item.get("index")]
        except (IndexError, TypeError):
            continue
        theme = item.get("theme")
        if theme and theme not in THEME_VOCAB:
            theme = "기타"
        tag = (dk.pill(theme) + " ") if theme else ""
        title = _esc(news_item.get("title_ko") or news_item.get("title") or "")
        link = dk.link_icon(news_item.get("link"), news_item.get("title") or "원문")
        related = [s for s in (item.get("related") or []) if isinstance(s, str) and s in known][:4]
        subs = []
        if related:
            subs.append("관련 자산 " + " · ".join(_named_reaction(s, reaction(s)) for s in related))   # 종목 이름도 증감 색 (가이드라인 3-3)
        if item.get("why"):
            subs.append("선정 이유 " + _esc(item["why"]))
        sub_html = "".join(f'<span style="display:block;color:{MUTED};font-size:{dk.TINY};">{x}</span>' for x in subs)
        items.append(f"<li style='{dk.LI}'>{tag}<span style='color:#111;'>{title}</span>{link}{sub_html}</li>")
    return dk.ul(items) if items else dk.muted("주요 뉴스 없음")


def sec_status(analysis, report):
    """위험 지도 — C 카드: 종합 신호등 + 항목 5개(신호·근거). 규칙 설명은 ⓘ."""
    a = analysis or {}
    status = a.get("status") or {}
    if not status.get("overall"):
        return _text(report.get("risk"))
    spy = (a.get("series") or {}).get("SPY") or {}
    vix = a.get("vix") or {}
    breadth = a.get("breadth") or {}
    rates = a.get("rates") or {}
    pos = (a.get("position") or {}).get("SPY") or {}
    ma = [("20일선 " + ("위" if spy["above_ma20"] else "아래")) if spy.get("above_ma20") is not None else "",
          ("50일선 " + ("위" if spy["above_ma50"] else "아래")) if spy.get("above_ma50") is not None else ""]
    overheat = f"SPY 20일 {spy['ret_20d']:+.2f}%" + (f" · 20일 고점 대비 {pos['from_high_pct']:+.2f}%" if pos.get("from_high_pct") is not None else "") if spy.get("ret_20d") is not None else "—"
    items = [("추세 유지", status.get("trend"), "SPY " + " · ".join(x for x in ma if x) if any(ma) else "—"),
             ("변동성", status.get("volatility"), f"VIX {vix['now']:.2f}" if vix.get("now") is not None else "—"),
             ("시장 폭", status.get("breadth"), f"상승 비율 {breadth['ratio']:.1f}%" if breadth.get("ratio") is not None else "—"),
             ("금리 위험", status.get("rates"), f"10년물 5일 {int(rates['us10y_change_5d_bp']):+d}bp" if rates.get("us10y_change_5d_bp") is not None else "—"),
             ("과열 위험", status.get("overheat"), overheat)]
    overall = status["overall"]
    rows = [("종합", _light_pill(overall, f"{overall} {_light_word(overall)}"), "")]
    rows += [(_esc(label), _light_pill(light) if light else dk.dash(), _esc(basis)) for label, light, basis in items]
    out = dk.ccard(rows, left="40%") + dk.guide("판정", "🔴가 하나라도 있으면 경계, 🟡가 둘 이상이면 주의")
    if str(report.get("risk") or "").strip():
        out += dk.sub_label("주의할 위험요인") + _text(report.get("risk"))
    return out


def sec_footer(input_data):
    return dk.footer(
        f"데이터 수집(FRED · Yahoo Finance · CNBC)과 파이썬 계산, AI 해설(Gemini)을 자동으로 결합해 만든 글입니다. "
        f"기준일 {_esc(dk.day(input_data.get('date')))} · 데이터 갱신 {_esc(input_data.get('updated_at') or '')}.",
        "시장 상태 점수와 신호등은 규칙 기반 계산값이며 투자 판단의 근거로 활용하지 마십시오. 투자 권고가 아닙니다.")


def build_body(input_data, report, cover_url=None, analysis=None):
    """구획 제목은 짧은 명사 (가이드라인 2절). 홈 카드 CARDS: summary = (머리)·주요 지수, insight = 종합, picks = 급등주."""
    indices = input_data.get("market", {}).get("indices", {})
    parts = [
        dk.WRAP_OPEN,
        _cover_image(cover_url),
        sec_lead(report, analysis),
        dk.section("시장 상태", sec_regime(analysis, report), summary="규칙 점수 0~100", tab=TAB_TODAY),
        dk.section("주요 지수", sec_indices(indices, analysis, report), tab=TAB_TODAY),
    ]
    change = sec_change(analysis, report)
    if change:
        parts.append(dk.section("달라진 것", change, tab=TAB_TODAY))
    parts.append(dk.section("종합", _text(report.get("opinion")), tab=TAB_TODAY))
    breadth = sec_breadth(analysis)
    if breadth:
        parts.append(dk.section("시장 폭", breadth, tab=TAB_MARKET))
    sectors = sec_sectors(analysis, report)
    if sectors:
        parts.append(dk.section("섹터", sectors, summary="1일 등락률", tab=TAB_MARKET))
    parts += [
        dk.section("금리·지표", sec_macro(input_data.get("macro", {}), analysis, report), tab=TAB_MARKET),
        dk.section("급등주", _quote_rows(input_data.get("gainers", [])) + _text(report.get("gainers_comment")), summary="상위 5", tab=TAB_STOCKS),
        dk.section("관심 종목", _quote_rows(input_data.get("most_active", [])) + _text(report.get("attention_comment")), summary="거래 상위 5", tab=TAB_STOCKS),
        dk.section("뉴스", sec_news(input_data, report, analysis), tab=TAB_STOCKS),
        dk.section("위험 지도", sec_status(analysis, report), tab=TAB_RISK),
        sec_footer(input_data),
        dk.WRAP_CLOSE,
    ]
    return dk.fix_colons("\n".join(p for p in parts if p))   # ":" 앞뒤 띄우기 (2026-10-11 사용자: 모든 페이지)


def build_tables(input_data, report, cover_url=None, analysis=None):
    """(호환) 옛 템플릿 마커 — 더 쓰지 않는다. build_body 가 본문을 만든다."""
    return {"BODY": build_body(input_data, report, cover_url, analysis)}


def render(input_path, report_path, output_dir, cover_url=None, analysis_path=None):
    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    analysis = None
    if analysis_path and os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    else:
        print("analysis.json 없음 — 지수 표 3열, '무엇이 달라졌나' 생략")

    body = build_body(input_data, report, cover_url=cover_url, analysis=analysis)   # 템플릿 대신 코드로 (2026-10-11 디자인 가이드라인)

    body_path = os.path.join(output_dir, "report_body.html")
    preview_path = os.path.join(output_dir, "report.html")

    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW_WRAPPER.replace("__BODY__", body))

    print(f"HTML 렌더 완료 -> {body_path}")
    print(f"미리보기 완료 -> {preview_path}")
    return body, body_path, preview_path


if __name__ == "__main__":
    render("report_input.json", "report.out.json", "output", analysis_path="analysis.json")