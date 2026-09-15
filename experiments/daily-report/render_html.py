"""렌더링: 수집 원본 숫자 + 분석 계산값 + Gemini 문구 → HTML

모든 숫자는 수집 데이터(report_input.json)와 파이썬 분석(analysis.json)에서 직접
렌더링한다. Gemini는 분석 문구(summary 등)와 뉴스 선택(index)만 사용한다.

analysis.json이 없으면(시계열 수집 실패) 지수 표는 기존 3열로 떨어지고
"무엇이 달라졌나" 섹션은 통째로 빠진다. 리포트가 그것 때문에 멈추지는 않는다.
"""

import html as html_mod
import json
import os

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
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow", "^RUT": "Russell 2000",
    "^VIX": "VIX", "^TNX": "US10Y", "^FVX": "US5Y", "^IRX": "US3M",
}

INDEX_LABELS = {
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq",
    "dow": "Dow Jones",
    "russell": "Russell 2000",
    "vix": "VIX",
}

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
    return (
        f'<img src="{src}" alt="데일리 브리핑 커버 이미지" '
        f'style="width:100%;max-width:1024px;border-radius:8px;'
        f'margin:0 0 16px 0;display:block;">'
    )


def _index_table(indices, analysis):
    """지수 표. 가격·1D는 수집 원본(fast_info), 5D·20D·연속·위치는 분석값."""
    if not analysis:
        rows = []
        for key in ("sp500", "nasdaq", "dow", "russell", "vix"):
            rec = indices.get(key) or {}
            rows.append([
                _esc(INDEX_LABELS.get(key, key)),
                _fmt_price(rec.get("price")),
                _pct_cell(rec.get("change_pct")),
            ])
        return _paragraph(rows, ["지수", "가격", "등락률"])

    series = analysis.get("series") or {}
    position = analysis.get("position") or {}
    rows = []
    for key in ("sp500", "nasdaq", "dow", "russell", "vix"):
        rec = indices.get(key) or {}
        s = series.get(INDEX_SYMBOL[key]) or {}
        label = (position.get(key) or {}).get("position_label")
        rows.append([
            _esc(INDEX_LABELS.get(key, key)),
            _fmt_price(rec.get("price")),
            _pct_cell(rec.get("change_pct")),
            _pct_cell(s.get("ret_5d"), missing="—"),
            _pct_cell(s.get("ret_20d"), missing="—"),
            _arrows_cell(s.get("last5")),
            _esc(label) if label else '<span style="color:#999;">—</span>',
        ])
    return _scroll(_paragraph(rows, ["지수", "가격", "1D", "5D", "20D", "최근 5일", "20일 레인지 위치"]))


def _change_section(analysis, report):
    """'무엇이 달라졌나' — 상대강도 · VIX 5일 · 20일 중 상승/하락 일수 · 레인지 위치 + Gemini 해설.
    분석이 없으면 섹션 제목까지 통째로 비운다."""
    if not analysis:
        return ""
    series = analysis.get("series") or {}
    position = analysis.get("position") or {}
    rs = analysis.get("rs") or {}
    vix = analysis.get("vix") or {}

    rs_rows = [
        ["Nasdaq(QQQ) − S&P 500(SPY)", _pct_cell(rs.get("qqq_spy_5d"), unit="%p", missing="—"),
         "양수면 성장주 우위"],
        ["소형주(IWM) − S&P 500(SPY)", _pct_cell(rs.get("iwm_spy_5d"), unit="%p", missing="—"),
         "양수면 소형주·위험선호 우위"],
        ["동일가중(RSP) − 시총가중(SPY)", _pct_cell(rs.get("rsp_spy_5d"), unit="%p", missing="—"),
         "양수면 상승이 넓게 퍼짐"],
    ]
    streak = rs.get("qqq_streak")
    if streak is not None:
        rs_rows.append(["Nasdaq이 S&P 500을 웃돈 연속 일수",
                        f"{int(streak)}일" if streak else "0일", "길수록 성장주 주도가 뚜렷"])
    rs_table = _scroll(_paragraph(rs_rows, ["상대강도 (5거래일)", "차이", "읽는 법"]))

    def updown(key):
        s = series.get(INDEX_SYMBOL[key]) or {}
        if s.get("up_days_20") is None:
            return "—"
        return (f'<span style="color:{UP_COLOR};">{s["up_days_20"]}↑</span> '
                f'<span style="color:{DOWN_COLOR};">{s["down_days_20"]}↓</span>')

    def range_pos(key):
        p = position.get(key) or {}
        if p.get("from_high_pct") is None:
            return "—", "—", "—"
        return (_pct_cell(p["from_high_pct"], missing="—"),
                _pct_cell(p["from_low_pct"], missing="—"),
                _esc(p.get("position_label") or "—"))

    trend_rows = []
    for key in ("sp500", "nasdaq", "russell"):
        hi, lo, label = range_pos(key)
        trend_rows.append([_esc(INDEX_LABELS[key]), updown(key), hi, lo, label])
    trend_table = _scroll(_paragraph(
        trend_rows, ["지수", "최근 20거래일", "20일 고점 대비", "20일 저점 대비", "위치"]))

    if vix.get("now") is not None and vix.get("prev_5d") is not None:
        chg = vix.get("change_5d") or 0.0
        color = UP_COLOR if chg >= 0 else DOWN_COLOR
        vix_line = (f'<div style="margin:8px 0;">VIX 5거래일: {vix["prev_5d"]:.2f} → '
                    f'<b>{vix["now"]:.2f}</b> '
                    f'<span style="color:{color};font-weight:bold;">({chg:+.2f})</span></div>')
    else:
        vix_line = ""

    return (
        f'<h2 style="{H2_STYLE}">무엇이 달라졌나</h2>'
        + rs_table + trend_table + vix_line
        + f'<div style="margin-top:6px;">{_text_block(report.get("change_comment"))}</div>'
    )


def _regime_section(analysis, report):
    """'시장 상태' — 점수 · 등급 · 어제 대비 · 요소별 막대, 그리고 Gemini의 regime_comment.
    점수와 등급은 analyze.py가 만든 값을 그대로 찍는다. 분석이 없으면 '데이터 없음' 한 줄."""
    regime = (analysis or {}).get("regime") or {}
    comment = f'<div style="margin-top:6px;">{_text_block(report.get("regime_comment"))}</div>'
    head = f'<h2 style="{H2_STYLE}">시장 상태 <span style="color:#888;font-size:15px;font-weight:normal;">Market Regime</span></h2>'
    if regime.get("score") is None:
        return head + '<div style="color:#999;">데이터 없음 — 오늘은 시장 상태 점수를 계산하지 못했습니다.</div>' + comment

    light = regime.get("light") or "🟡"
    color = LIGHT_COLOR.get(light, "#888")
    if regime.get("score_prev") is not None:
        delta = regime.get("delta") or 0
        prev_txt = f'<span style="color:#666;font-size:16px;">어제 {regime["score_prev"]} · {delta:+d}</span>'
    else:
        prev_txt = '<span style="color:#999;font-size:16px;">어제 점수 없음</span>'
    badge = (
        f'<div style="margin:8px 0 12px 0;">'
        f'<span style="display:inline-block;background:{color};color:#fff;font-weight:bold;font-size:18px;'
        f'padding:4px 14px;border-radius:16px;vertical-align:middle;">{light} {_esc(regime.get("label") or "")}</span>'
        f'&nbsp;&nbsp;<span style="font-size:28px;font-weight:bold;color:#111;vertical-align:middle;">{int(regime["score"])}</span>'
        f'<span style="color:#888;font-size:16px;vertical-align:middle;"> / 100</span>'
        f'&nbsp;&nbsp;{prev_txt}</div>'
    )

    rows = ['<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:17px;">']
    for key, label in REGIME_COMPONENT_LABELS.items():
        c = (regime.get("components") or {}).get(key) or {}
        score, mx = c.get("score"), c.get("max")
        if score is None or not mx:
            continue
        frac = score / mx
        bar_color = LIGHT_COLOR["🟢"] if frac >= 0.7 else LIGHT_COLOR["🟡"] if frac >= 0.45 else LIGHT_COLOR["🔴"]
        rows.append(
            "<tr>"
            f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;width:22%;">{_esc(label)}</td>'
            f'<td style="border:1px solid #ddd;padding:6px 8px;">'
            f'<div style="background:#eee;height:14px;border-radius:2px;">'
            f'<div style="background:{bar_color};height:14px;width:{frac * 100:.0f}%;border-radius:2px;"></div></div></td>'
            f'<td style="border:1px solid #ddd;padding:6px 8px;text-align:right;white-space:nowrap;width:18%;">{int(score)} / {int(mx)}</td>'
            "</tr>"
        )
    rows.append("</table>")
    return head + badge + _scroll("".join(rows)) + comment


def _breadth_section(analysis):
    """'시장 폭' — 프록시 모드는 섹터 ETF 상승 개수와 RSP−SPY. 전수 모드(3단계)는 상승/하락 종목 수.
    파이썬 값만 찍는다. 해설 키는 3단계에서."""
    b = (analysis or {}).get("breadth") or {}
    if b.get("ratio") is None:
        return ""
    light = (b.get("label") or "")[:1]
    color = LIGHT_COLOR.get(light, "#888")
    if b.get("mode") == "full":
        count_line = (f'상승 <b style="color:{UP_COLOR};">{b.get("advancers")}</b> · '
                      f'하락 <b style="color:{DOWN_COLOR};">{b.get("decliners")}</b> 종목')
        extra = ""
        if b.get("new_high_52w") is not None:
            extra = f' · 52주 신고가 {b["new_high_52w"]} · 신저가 {b["new_low_52w"]}'
        basis = "S&P 500 구성종목"
    else:
        count_line = (f'섹터 ETF {b.get("sectors_counted")}개 중 상승 <b style="color:{UP_COLOR};">{b.get("sectors_up")}</b> · '
                      f'하락 <b style="color:{DOWN_COLOR};">{b.get("sectors_down")}</b>')
        extra = ""
        basis = "섹터 ETF 프록시"
    rsp_line = ""
    if b.get("rsp_spy_1d") is not None:
        rsp_line = (f'<div style="margin:4px 0;">동일가중(RSP) − 시총가중(SPY): 1D {_pct_cell(b["rsp_spy_1d"], unit="%p")} · '
                    f'5D {_pct_cell(b.get("rsp_spy_5d"), unit="%p", missing="—")} '
                    f'<span style="color:#888;font-size:15px;">— 양수면 상승이 소수 대형주에 몰리지 않은 것</span></div>')
    return (
        f'<h2 style="{H2_STYLE}">시장 폭 <span style="color:#888;font-size:15px;font-weight:normal;">Market Breadth · {_esc(basis)}</span></h2>'
        f'<div style="margin:8px 0;">{count_line}{extra} · 상승 비율 <b>{b["ratio"]:.1f}%</b>'
        f'&nbsp;&nbsp;<span style="display:inline-block;background:{color};color:#fff;font-weight:bold;font-size:15px;'
        f'padding:2px 10px;border-radius:12px;">{_esc(b.get("label") or "")}</span></div>'
        + rsp_line
    )


def _status_board(analysis):
    """'위험 지도' 상태판 — 신호등 5개 + 종합. 근거 열은 계산값을 그대로 옮긴 것이다."""
    a = analysis or {}
    status = a.get("status") or {}
    if not status.get("overall"):
        return ""
    spy = (a.get("series") or {}).get("SPY") or {}
    vix = a.get("vix") or {}
    breadth = a.get("breadth") or {}
    rates = a.get("rates") or {}
    pos = (a.get("position") or {}).get("SPY") or {}

    def ma_text():
        parts = []
        if spy.get("above_ma20") is not None:
            parts.append("20일선 " + ("위" if spy["above_ma20"] else "아래"))
        if spy.get("above_ma50") is not None:
            parts.append("50일선 " + ("위" if spy["above_ma50"] else "아래"))
        return "SPY " + " · ".join(parts) if parts else "—"

    def overheat_text():
        if spy.get("ret_20d") is None:
            return "—"
        t = f"SPY 20D {spy['ret_20d']:+.2f}%"
        if pos.get("from_high_pct") is not None:
            t += f" · 20일 고점 대비 {pos['from_high_pct']:+.2f}%"
        return t

    items = [
        ("추세 유지", status.get("trend"), ma_text()),
        ("변동성", status.get("volatility"), f"VIX {vix['now']:.2f}" if vix.get("now") is not None else "—"),
        ("시장 폭", status.get("breadth"), f"상승 비율 {breadth['ratio']:.1f}%" if breadth.get("ratio") is not None else "—"),
        ("금리 리스크", status.get("rates"), f"10Y 5D {int(rates['us10y_change_5d_bp']):+d}bp" if rates.get("us10y_change_5d_bp") is not None else "—"),
        ("과열 위험", status.get("overheat"), overheat_text()),
    ]
    rows = []
    for label, light, basis in items:
        light_cell = (f'<span style="font-size:20px;">{light}</span>' if light
                      else '<span style="color:#999;">—</span>')
        rows.append([_esc(label), light_cell, _esc(basis)])
    overall = status["overall"]
    color = LIGHT_COLOR.get(overall, "#888")
    overall_word = {"🟢": "정상", "🟡": "주의", "🔴": "경계"}.get(overall, "")
    return (
        _scroll(_paragraph(rows, ["항목", "신호", "근거"]))
        + f'<div style="margin:8px 0;">종합 &nbsp;<span style="display:inline-block;background:{color};color:#fff;'
        f'font-weight:bold;font-size:16px;padding:3px 12px;border-radius:14px;">{overall} {overall_word}</span>'
        f'&nbsp;<span style="color:#888;font-size:15px;">— 🔴가 하나라도 있으면 경계, 🟡가 둘 이상이면 주의</span></div>'
    )


def _rank_change_cell(delta):
    """5일 순위 대비 오늘 순위 변화. 양수면 올라온 것."""
    if delta is None:
        return ""
    if delta > 0:
        return f'<span style="color:{UP_COLOR};">▲{delta}</span>'
    if delta < 0:
        return f'<span style="color:{DOWN_COLOR};">▼{-delta}</span>'
    return '<span style="color:#999;">–</span>'


def _sector_section(analysis, report):
    """'섹터 · 테마' — 섹터 ETF 12개의 1D 막대와 5일 순위 변화, 주도/약세, Gemini 해설."""
    ranked = ((analysis or {}).get("sectors") or {}).get("ranked_1d") or []
    if not ranked:
        return ""
    max_abs = max(abs(r["ret_1d"]) for r in ranked) or 1.0

    parts = ['<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:17px;">',
             '<tr>'
             '<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;">테마 (ETF)</th>'
             '<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;width:38%;">1D</th>'
             '<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:right;">등락률</th>'
             '<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:right;">5D 순위 대비</th>'
             '</tr>']
    for r in ranked:
        pct = abs(r["ret_1d"]) / max_abs * 100
        color = UP_COLOR if r["ret_1d"] >= 0 else DOWN_COLOR
        parts.append(
            "<tr>"
            f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{_esc(r["theme"])} '
            f'<span style="color:#888;font-size:14px;">({_esc(r["etf"])})</span></td>'
            f'<td style="border:1px solid #ddd;padding:6px 8px;">'
            f'<div style="background:{color};height:14px;width:{pct:.0f}%;min-width:2px;border-radius:2px;"></div></td>'
            f'<td style="border:1px solid #ddd;padding:6px 8px;text-align:right;white-space:nowrap;">{_pct_cell(r["ret_1d"])}</td>'
            f'<td style="border:1px solid #ddd;padding:6px 8px;text-align:right;">{_rank_change_cell(r.get("rank_change"))}</td>'
            "</tr>"
        )
    parts.append("</table>")

    by_etf = {r["etf"]: r for r in ranked}

    def names(etfs):
        return " · ".join(f'{_esc(by_etf[e]["theme"])}({_esc(e)})' for e in etfs if e in by_etf)

    sectors = analysis["sectors"]
    lead_line = (
        f'<div style="margin:6px 0;"><b style="color:{UP_COLOR};">주도</b> {names(sectors.get("leaders") or [])}'
        f'&nbsp;&nbsp;<b style="color:{DOWN_COLOR};">약세</b> {names(sectors.get("laggards") or [])}</div>'
    )
    return (
        f'<h2 style="{H2_STYLE}">섹터 · 테마</h2>'
        + _scroll("".join(parts)) + lead_line
        + f'<div style="margin-top:6px;">{_text_block(report.get("sector_comment"))}</div>'
    )


def _bp_cell(bp):
    """금리 변화. 색을 쓰지 않는다 — 금리 상승이 좋은지 나쁜지는 문맥이 정한다."""
    if bp is None:
        return '<span style="color:#999;">—</span>'
    return f'<span style="color:#555;">{int(bp):+d}bp</span>'


def _macro_table(macro, analysis):
    """금리 · 경제지표 표. 금리 4행은 FRED(raw.macro)에서, 10Y의 당일값·bp 변화는 분석(^TNX)에서."""
    rates = (analysis or {}).get("rates") or {}

    def fred(key):
        rec = macro.get(key)
        if not rec or rec.get("value") is None:
            return "데이터 없음", ""
        return _esc(f"{rec['value']:.2f}"), _esc(rec.get("date", ""))

    rows = []
    v10, d10 = fred("us10y")
    if rates.get("us10y") is not None:
        v10 = _esc(f"{rates['us10y']:.2f}")
        d10 = _esc((analysis or {}).get("as_of") or d10)
    change_10y = (f"1D {_bp_cell(rates.get('us10y_change_1d_bp'))} · 5D {_bp_cell(rates.get('us10y_change_5d_bp'))}"
                  if rates.get("us10y_change_5d_bp") is not None else "")
    rows.append(["10년물 국채금리 (%)", v10, change_10y, d10])
    for key, label in (("us2y", "2년물 국채금리 (%)"),
                       ("spread_10_2", "10Y−2Y 스프레드 (%p)"),
                       ("fed_funds", "연방기금금리 (%)"),
                       ("unemployment_rate", "실업률 (%)"),
                       ("cpi", "CPI (지수)"),
                       ("vix", "VIX")):
        if key in ("us2y", "spread_10_2", "fed_funds") and not macro.get(key):
            continue  # 금리는 있을 때만 — 옛 입력 파일과도 호환
        v, d = fred(key)
        rows.append([label, v, "", d])
    table = _scroll(_paragraph(rows, ["지표", "값", "변화", "기준일"]))

    label = rates.get("growth_label")
    if label:
        table += f'<div style="margin:6px 0;">금리 ↔ 성장주: <b>{_esc(label)}</b></div>'
    return table


def _news_list(input_data, report, analysis):
    """뉴스 카드. 테마 태그와 '관련 자산'의 실제 1D는 파이썬이 채운다. Gemini는 index·테마·심볼만 고른다."""
    series = (analysis or {}).get("series") or {}
    rates = (analysis or {}).get("rates") or {}
    quotes = {q["symbol"]: q for q in input_data.get("gainers", []) + input_data.get("most_active", [])
              if q.get("symbol")}
    known = set(series) | set(quotes)

    def reaction(sym):
        if sym == "^TNX" and rates.get("us10y_change_1d_bp") is not None:
            return _bp_cell(rates["us10y_change_1d_bp"])
        if sym in series:
            return _pct_cell(series[sym].get("ret_1d"), missing="—")
        return _pct_cell(quotes[sym].get("change_pct"), missing="—")

    rows = []
    for item in report.get("news", []):
        idx = item.get("index")
        try:
            news_item = input_data.get("news", [])[idx]
        except (IndexError, TypeError):
            continue
        title = _esc(news_item.get("title") or "")
        link = _esc(news_item.get("link") or "#")
        why = _esc(item.get("why") or "")

        theme = item.get("theme")
        if theme and theme not in THEME_VOCAB:
            theme = "기타"
        tag = (f'<span style="display:inline-block;background:#eef3ff;color:#2a4d9b;font-size:14px;'
               f'padding:1px 8px;border-radius:10px;margin-right:6px;vertical-align:middle;">{_esc(theme)}</span>'
               if theme else "")

        related = [s for s in (item.get("related") or []) if isinstance(s, str) and s in known][:4]
        related_line = ""
        if related:
            cells = " · ".join(f'{_esc(SYMBOL_NAMES.get(s, s))} {reaction(s)}' for s in related)
            related_line = f'<div style="margin:4px 0 0 12px;font-size:16px;">관련 자산: {cells}</div>'

        rows.append(
            f'<div style="margin-bottom:12px;">'
            f'  {tag}<a href="{link}" target="_blank" rel="noopener nofollow" style="font-weight:bold;color:#2196f3;text-decoration:none;">{title}</a>'
            f'  {related_line}'
            f'  <div style="margin:4px 0 0 12px;color:#666;font-size:17px;">선정 이유: {why}</div>'
            f'</div>'
        )
    return "".join(rows) if rows else '<div>주요 뉴스 없음</div>'


def build_tables(input_data, report, cover_url=None, analysis=None):
    indices = input_data.get("market", {}).get("indices", {})
    index_table = _index_table(indices, analysis)

    def quote_rows(quotes):
        rows = []
        for q in quotes or []:
            rows.append([
                _esc(q.get("symbol") or "-"),
                _fmt_price(q.get("price")),
                _pct_cell(q.get("change_pct")),
                _fmt_volume(q.get("volume")),
            ])
        return rows

    gainers = input_data.get("gainers", [])
    gainers_table = _paragraph(quote_rows(gainers), ["종목", "가격", "등락률", "거래량"]) if gainers else _text_block("")

    most_active = input_data.get("most_active", [])
    attention_table = _paragraph(quote_rows(most_active), ["종목", "가격", "등락률", "거래량"]) if most_active else _text_block("")

    return {
        "COVER_IMAGE": _cover_image(cover_url),
        "ONE_LINE": _text_block(report.get("one_line")),
        "REGIME_SECTION": _regime_section(analysis, report),
        "SUMMARY": _text_block(report.get("summary")),
        "INDEX_TABLE": index_table,
        "CHANGE_SECTION": _change_section(analysis, report),
        "BREADTH_SECTION": _breadth_section(analysis),
        "SECTOR_SECTION": _sector_section(analysis, report),
        "STATUS_BOARD": _status_board(analysis),
        "GAINERS_TABLE": gainers_table,
        "GAINERS_COMMENT": _text_block(report.get("gainers_comment")),
        "ATTENTION_TABLE": attention_table,
        "ATTENTION_COMMENT": _text_block(report.get("attention_comment")),
        "NEWS_LIST": _news_list(input_data, report, analysis),
        "MACRO_TABLE": _macro_table(input_data.get("macro", {}), analysis),
        "MACRO_COMMENT": _text_block(report.get("macro_comment")),
        "OPINION": _text_block(report.get("opinion")),
        "RISK": _text_block(report.get("risk")),
        "DATE": _korean_date(input_data.get("date")),
        "UPDATED": _esc(input_data.get("updated_at") or ""),
    }


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

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()

    body = template
    built = build_tables(input_data, report, cover_url=cover_url, analysis=analysis)
    for marker in MARKERS:
        body = body.replace(f"__{marker}__", built[marker])

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