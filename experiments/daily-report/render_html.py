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
    "SUMMARY", "MARKET_MOOD", "INDEX_TABLE", "CHANGE_SECTION", "GAINERS_TABLE",
    "GAINERS_COMMENT", "ATTENTION_TABLE", "ATTENTION_COMMENT", "NEWS_LIST",
    "MACRO_TABLE", "MACRO_COMMENT", "OPINION", "RISK", "DATE", "UPDATED",
    "COVER_IMAGE",
]

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

    news_rows = []
    for item in report.get("news", []):
        idx = item.get("index")
        try:
            news_item = input_data.get("news", [])[idx]
        except (IndexError, TypeError):
            continue
        title = _esc(news_item.get("title") or "")
        link = _esc(news_item.get("link") or "#")
        why = _esc(item.get("why") or "")
        news_rows.append(
            f'<div style="margin-bottom:10px;">'
            f'  <a href="{link}" target="_blank" rel="noopener nofollow" style="font-weight:bold;color:#2196f3;text-decoration:none;">{title}</a>'
            f'  <div style="margin:4px 0 0 12px;color:#666;font-size:17px;">선정 이유: {why}</div>'
            f'</div>'
        )
    news_list = "".join(news_rows) if news_rows else '<div>주요 뉴스 없음</div>'

    macro = input_data.get("macro", {})
    macro_rows = []
    for key, label in (("unemployment_rate", "실업률 (%)"),
                       ("cpi", "CPI (지수)"),
                       ("vix", "VIX")):
        rec = macro.get(key)
        value = _esc(f"{rec['value']:.2f}") if (rec and rec.get("value") is not None) else "데이터 없음"
        date = _esc(rec.get("date", "")) if rec else ""
        macro_rows.append([label, value, date])
    macro_table = _paragraph(macro_rows, ["지표", "값", "기준일"])

    return {
        "COVER_IMAGE": _cover_image(cover_url),
        "SUMMARY": _text_block(report.get("summary")),
        "MARKET_MOOD": _text_block(report.get("market_mood")),
        "INDEX_TABLE": index_table,
        "CHANGE_SECTION": _change_section(analysis, report),
        "GAINERS_TABLE": gainers_table,
        "GAINERS_COMMENT": _text_block(report.get("gainers_comment")),
        "ATTENTION_TABLE": attention_table,
        "ATTENTION_COMMENT": _text_block(report.get("attention_comment")),
        "NEWS_LIST": news_list,
        "MACRO_TABLE": macro_table,
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