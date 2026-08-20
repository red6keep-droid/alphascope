"""렌더링: 수집 원본 숫자 + Gemini 문구 → HTML

모든 숫자는 수집 데이터(report_input.json)에서 직접 렌더링한다.
Gemini는 분석 문구(summary 등)와 뉴스 선택(index)만 사용한다.
"""

import html as html_mod
import json
import os

TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "templates", "report.html")

MARKERS = [
    "SUMMARY", "MARKET_MOOD", "INDEX_TABLE", "GAINERS_TABLE", "GAINERS_COMMENT",
    "ATTENTION_TABLE", "ATTENTION_COMMENT", "NEWS_LIST", "MACRO_TABLE",
    "MACRO_COMMENT", "OPINION", "RISK", "DATE", "UPDATED",
]

INDEX_LABELS = {
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq",
    "dow": "Dow Jones",
    "russell": "Russell 2000",
    "vix": "VIX",
}

PREVIEW_WRAPPER = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>데일리 리포트 미리보기</title>
</head>
<body style="max-width:760px;margin:0 auto;padding:16px;background:#fff;">
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


def _pct_cell(change):
    if change is None:
        return '<span style="color:#999;">데이터 없음</span>'
    change = float(change)
    color = UP_COLOR if change >= 0 else DOWN_COLOR
    sign = "+" if change >= 0 else ""
    return (
        f'<span style="color:{color};font-weight:bold;">'
        f"{sign}{change:.2f}%</span>"
    )


def _paragraph(rows, headers):
    parts = ['<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:14px;">']
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


def build_tables(input_data, report):
    indices = input_data.get("market", {}).get("indices", {})

    index_rows = []
    for key in ("sp500", "nasdaq", "dow", "russell", "vix"):
        rec = indices.get(key) or {}
        index_rows.append([
            _esc(INDEX_LABELS.get(key, key)),
            _fmt_price(rec.get("price")),
            _pct_cell(rec.get("change_pct")),
        ])
    index_table = _paragraph(index_rows, ["지수", "가격", "등락률"])

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
            f'  <div style="margin:4px 0 0 12px;color:#666;font-size:14px;">선정 이유: {why}</div>'
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
        "SUMMARY": _text_block(report.get("summary")),
        "MARKET_MOOD": _text_block(report.get("market_mood")),
        "INDEX_TABLE": index_table,
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


def render(input_path, report_path, output_dir):
    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()

    body = template
    built = build_tables(input_data, report)
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
    render("report_input.json", "report.out.json", "output")