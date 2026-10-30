"""렌더링: 수집 원본 숫자 + 분석 계산값 + Gemini 문구 → HTML (디자인-가이드라인.md · experiments/design_kit.py, 2026-10-11)

모든 숫자는 수집 데이터(report_input.json)와 파이썬 분석(analysis.json)에서 직접
렌더링한다. Gemini는 분석 문구(summary 등)와 뉴스 선택(index)만 사용한다.

analysis.json이 없으면(시계열 수집 실패) 지수 표는 기존 3열로 떨어지고
"무엇이 달라졌나" 섹션은 통째로 빠진다. 리포트가 그것 때문에 멈추지는 않는다.
"""

import html as html_mod
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402  — 디자인-가이드라인.md 공통 조각 (2026-10-11)

dk.TIP_SRC = "Yahoo Finance"   # 툴팁 기본 데이터 출처. 금리 · 경제 일정이 들어간 툴팁만 with_src (2026-10-20 사용자)
import cards  # noqa: E402  — 질문 카드 · 막대 그래프 (2026-10-18 재설계)
import sections as sx  # noqa: E402  — 독자 질문 D1 ~ D6 · K1 ~ K3 구획 (doc/기획/데일리-리포트-기획.md 6절)
import datetime  # noqa: E402
import media_feed  # noqa: E402  — 방송 줄 (미디어 데일리 재료의 시장 · 업종 이슈, 2026-10-25 사용자)
import kr_news  # noqa: E402  — 한국장 탭 `한국장에 영향을 줄 만한 소식` (미디어 데일리 뒤에 이 칸만 갱신)

MEDIA_SHOWN = 5    # 뉴스 구획 끝의 방송 줄 — 앞 5건만 펼쳐 두고 나머지는 `방송 n건 더 보기` 접기 (2026-10-30 사용자: 상한 없이 다 싣는다. 옛 MEDIA_MAX=3 은 미디어 데일리가 나머지를 들던 때 숫자)
MEDIA_HOURS = 48   # 글을 만드는 시각 기준 최근 48시간 영상 (2026-10-30 사용자, 옛 24)
_media_cache = None
_rows_cache = None


def _media_rows():
    global _rows_cache
    if _rows_cache is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        _rows_cache = media_feed.rows(media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=3))   # 48시간이 edition 사흘에 걸친다
    return _rows_cache


def _media_lines():
    """한 번만 읽는다. 키 · 패키지가 없거나 실패하면 [] — 뉴스는 기사만으로 나간다."""
    global _media_cache
    if _media_cache is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        since = (now - datetime.timedelta(hours=MEDIA_HOURS)).strftime("%Y-%m-%dT%H:%M")
        _media_cache = media_feed.market_top(media_feed.issues(_media_rows(), since), None)   # 같은 이슈는 한 줄로 정리한 뒤 — 전부 (방송 수 → 영상 수 → 최근 순)
    return _media_cache


def _kst_hm(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(media_feed.KST).strftime("%H:%M")
    except ValueError:
        return ""

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
    **sx.MEGA_KO, "^SOX": "미국 반도체 지수", "KRW=X": "원/달러",
    "^GSPC": "S&P 500", "^IXIC": "나스닥", "^DJI": "다우", "^RUT": "러셀 2000",
    "^VIX": "VIX", "^TNX": "미국 10년물 금리", "^FVX": "미국 5년물 금리", "^IRX": "미국 3개월물 금리",
}

INDEX_LABELS = {   # 한국어 위주 (가이드라인 3-4). S&P 500·VIX 는 고유명으로 둔다. 이름 옆 (의미)는 작은 글씨 — dk.paren (2026-10-14 사용자: 블로그 모든 지수 이름)
    "sp500": "S&P 500 (대형주)",
    "nasdaq": "나스닥 (기술주)",
    "dow": "다우존스 (우량주)",
    "russell": "러셀 2000 (소형주)",
    "vix": "VIX (변동성 지수)",
}
# 영어 용어 → 한국어 (Gemini 문구·라벨 표시용)
TERM_KO = {"위험선호(Risk-On)": "위험 선호", "위험회피(Risk-Off)": "위험 회피", "위험 선호(Risk-On)": "위험 선호", "위험 회피(Risk-Off)": "위험 회피",
           "Risk-On": "위험 선호", "Risk-Off": "위험 회피", "Risk On": "위험 선호", "Risk Off": "위험 회피", "Neutral": "중립",
           "Nasdaq": "나스닥", "Dow Jones": "다우존스", "Dow": "다우", "Russell 2000": "러셀 2000", "Market Regime": "시장 상태"}
TAB_TODAY, TAB_MARKET, TAB_STOCKS, TAB_RISK = "오늘", "시장", "종목 · 뉴스", "위험"   # "·" 앞뒤 띄우기 (2026-10-13 사용자)
TAB_KOREA, TAB_CAL = "한국장", "일정"   # 2026-10-18 재설계: 오늘 · 한국장 · 시장 · 일정 (종목 · 뉴스 · 위험 탭은 없앰 — 기획 6절)

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

STATE_HISTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "state", "history")   # analyze.STATE_DIR/history — report-state 브랜치에서 불러온 분석 이력

SECTOR_KO = {   # yfinance info.sector → 섹터 라벨 (섹터 표의 이름과 같게, 2026-10-13 사용자: 급등주 · 관심 종목 섹터 라벨)
    "Technology": "기술", "Financial Services": "금융", "Energy": "에너지", "Healthcare": "헬스케어",
    "Consumer Cyclical": "소비 (경기민감)", "Consumer Defensive": "소비 (필수)", "Utilities": "유틸리티",
    "Industrials": "산업", "Basic Materials": "소재", "Real Estate": "부동산", "Communication Services": "통신",
}

UP_COLOR = "#d93025"
DOWN_COLOR = "#1a73e8"
MUTED = dk.MUTED


def _prev_analysis(analysis):
    """어제(이 글 날짜 바로 앞) 분석 이력 — 값마다 어제 대비를 그리려고 (2026-10-13 사용자: "모든 데이터는 어제 기준으로 증가했는지 감소했는지").
    이력이 없으면 {} — 어제 대비는 빠진다."""
    today = (analysis or {}).get("date")
    if not today or not os.path.isdir(STATE_HISTORY):
        return {}
    days = sorted(f[:-5] for f in os.listdir(STATE_HISTORY) if f.endswith(".json") and f[:-5] < today)
    if not days:
        return {}
    try:
        with open(os.path.join(STATE_HISTORY, days[-1] + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _get(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _vs(cur, prev, digits=2, unit="%p", word="어제 대비"):
    """`어제 대비 ▲ 0.12%p` — 증감 색, 0 은 회색 –. 둘 중 하나라도 없으면 ""."""
    if cur is None or prev is None:
        return ""
    d = round(float(cur) - float(prev), digits)
    return f'<span style="white-space:nowrap;">{word} {dk.arrow(d, digits, unit)}</span>'   # 덩어리 가운데서 줄이 바뀌지 않게


def _join(*parts):
    return " · ".join(p for p in parts if p)


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


ZOOM_ICON = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
             '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')


def sec_chart(output_dir):
    """S&P 500 가격 그래프 — 본문 맨 앞, 탭 줄 위 (2026-10-18 사용자: "다른 리포트처럼 상단에, 클릭하면 새 창"). 엔비디아 sec_chart 와 같은 모양.
    data-zoom: 테마 JS 가 전체 화면 팝업 + 가로 스크롤로 연다(가이드 8절), JS 없으면 원본 링크 새 창. chart.json 이 없으면 빈 문자열."""
    path = os.path.join(output_dir or "", "chart.json")
    if not output_dir or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    url = _esc(c["url"])
    return (f'<a href="{url}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{url}" alt="S&amp;P 500 {c.get("window", 30)}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{ZOOM_ICON}</span></a>')


def _cover_image(cover_url):
    if not cover_url:
        return ""
    src = html_mod.escape(str(cover_url), quote=True)
    return f'<img src="{src}" alt="데일리 브리핑 커버 이미지" style="width:100%;max-width:1024px;border-radius:8px;margin:0 0 16px 0;display:block;">'


PARA_GAP = int(dk.LH_BODY[:-2])   # 문단 사이 = 빈 줄 하나 (본문 행간)


def _paragraphs(text):
    """Gemini 문구 → [[문장, …], …]. 빈 줄이 문단 경계(내용이 바뀌는 곳), 마침표 뒤 공백이나 줄바꿈이 문장 끝.
    (2026-10-16 사용자: "문장이 길면 마침표 뒤에 줄바꿈, 내용이 바뀌면 줄바꿈 두 번") — 프롬프트가 주제가 바뀌는 곳에 빈 줄을 넣는다."""
    paras = []
    for block in re.split(r"\n\s*\n", str(text or "").strip()):
        sents = [s.strip() for s in re.split(r"(?<=\.)\s+|\n", block) if s.strip()]
        if sents:
            paras.append(sents)
    return paras


def _text(text):
    """Gemini 문구 — 문장마다 한 줄, 문단 사이 빈 줄 하나(PARA_GAP), 영어 용어는 한국어로. 비어 있으면 ⓘ 안내."""
    paras = _paragraphs(text)
    if not paras:
        return dk.muted("데이터 없음")
    # data-para · data-sent: 테마 CSS 가 PC 에서는 문장을 블록(한 줄씩), 모바일(≤900px)에서는 인라인(이어 흐름)으로 — 문장 뒤 공백은 인라인일 때의 띄어쓰기
    return "".join(f'<div data-para="1" style="margin:{PARA_GAP if i else 0}px 0 6px;padding-left:{dk.ALIGN_PX}px;">' + "".join(f'<span data-sent="1">{dk.tint(_esc(dk.ko(s, TERM_KO)))}</span> ' for s in sents) + "</div>"   # 증감 색 (2026-10-12 사용자: 모든 곳)
                   for i, sents in enumerate(paras))


def _light_word(light):
    return {"🟢": "정상", "🟡": "주의", "🔴": "경계"}.get(light, "")


LIGHT_KIND = {"🟢": "good", "🟡": "uncertain", "🔴": "negative"}   # 신호등 → 라벨·상태 카드 색 (🟢 녹색, 2026-10-12 사용자)
SCORE_SIZE = "20px"   # 점수 카드의 "86 / 100" — 20px 굵게 (2026-10-12 사용자, 18·16·14 밖의 유일한 예외)
# 툴팁 글은 뜻 · 오늘 · 기록상(또는 참고) 세 줄 (디자인-가이드라인.md 2-6, 2026-10-18 사용자: "툴팁은 어려운 용어를 쉽게 전달하는 것인데 숫자만 나열돼 있다").
# 오늘 값을 읽어 줘야 하므로 툴팁은 상수가 아니라 데이터를 받는 함수. 이 리포트의 지표는 아직 우리 검증 결과가 없어 `기록상` 줄은 두지 않는다.
# 등급 경계는 analyze.py 와 같아야 한다 — 시장 상태 70 · 45 (REGIME_RISK_ON · OFF), 상승 비율 65 · 45 (breadth_proxy), 위험 신호는 status_board.
REGIME_GRADE_NOW = {   # 점수 카드 툴팁의 오늘 줄 — 등급의 뜻 (옛 GRADE_MEANING, 2026-10-12 사용자)
    "위험 선호": "위험 선호 구간. 투자자들이 위험을 감수하고 주식 쪽으로 움직이기 쉬운 환경",
    "중립": "중립 구간. 위험 선호와 위험 회피 어느 쪽으로도 크게 기울지 않았다",
    "위험 회피": "위험 회피 구간. 투자자들이 위험을 피해 안전한 자산 쪽으로 움직이기 쉬운 환경",
}
BREADTH_GRADE_NOW = {   # 상승 비율 카드 툴팁의 오늘 줄 — 등급의 뜻 (옛 BREADTH_MEANING, 2026-10-12 사용자)
    "양호": "상승이 시장 전반에 넓게 퍼졌다",
    "보통": "오른 쪽과 내린 쪽이 비슷하게 섞였다",
    "취약": "내린 쪽이 더 많아 상승이 일부에 몰렸다",
}
STATUS_KEYS = {"trend": "추세 유지", "volatility": "변동성", "breadth": "시장 폭", "rates": "금리 위험", "overheat": "과열 위험"}


def _ahead(v, a, b):
    """상대강도 값 → `나스닥이 S&P 500보다 1.23%p 앞섰다` (둘 다 내린 날도 맞게 '더 올랐다' 대신 앞섰다 · 뒤처졌다). a 는 조사까지 붙여 넘긴다."""
    if v > 0:
        return f"{a} {b}보다 {abs(v):.2f}%p 앞섰다"
    if v < 0:
        return f"{a} {b}보다 {abs(v):.2f}%p 뒤처졌다"
    return "두 지수가 같았다"


def score_tip(regime):
    """점수 카드 ? — 오늘 점수가 어느 등급인지와 등급의 뜻 (구성 요소 규칙은 구획 제목 옆 `점수 0~100` 툴팁, regime_rule)."""
    s = int(regime["score"])
    grade = "위험 선호" if s >= 70 else "중립" if s >= 45 else "위험 회피"
    return ("지금 시장이 주식에 우호적인 환경인지를 점수로 나타낸 것. 높을수록 우호적\n"
            f"· 오늘 {s}점 : {REGIME_GRADE_NOW[grade]}\n"
            "· 나누는 법 : 70 이상 위험 선호, 45~69 중립, 45 미만 위험 회피")


def regime_rule(regime):
    """구획 제목 옆 `점수 0~100` ? — 다섯 항목이 무엇이고 오늘 가장 강한 · 약한 항목 (옛 REGIME_TIP 의 점수표는 analyze.regime_score() 에)."""
    comps = [(REGIME_COMPONENT_LABELS[k], c["score"], c["max"]) for k, c in ((regime or {}).get("components") or {}).items()
             if k in REGIME_COMPONENT_LABELS and c.get("score") is not None and c.get("max")]
    now = ""
    if comps and regime.get("score") is not None:
        hi = max(comps, key=lambda c: c[1] / c[2])
        lo = min(comps, key=lambda c: c[1] / c[2])
        if hi[1] / hi[2] == lo[1] / lo[2]:
            now = f"\n· 오늘 {int(regime['score'])}점 : 다섯 항목이 고르게 {hi[1] / hi[2] * 100:.0f}% 수준"
        else:
            now = (f"\n· 오늘 {int(regime['score'])}점 : 가장 탄탄한 항목은 {hi[0]}({int(hi[2])}점 중 {int(hi[1])}점), "
                   f"가장 약한 항목은 {lo[0]}({int(lo[2])}점 중 {int(lo[1])}점)")
    return ("추세 · 시장 폭 · 변동성 · 금리 환경 · 위험 선호 다섯 항목의 점수를 더한 것" + now +
            "\n· 점수 매기는 법 : 지수가 평균 가격선 위에 있을수록, 상승 비율이 높을수록, VIX가 낮을수록, 금리가 내릴수록, "
            "성장주 · 소형주처럼 위험한 자산이 강할수록 점수가 오른다"
            "\n· 참고 : 정해 둔 규칙으로 계산한 값이라, 앞으로 오를지를 맞힌다는 뜻은 아니다"
            "\n" + dk.SRC_MARK + "Yahoo Finance · FRED")   # 금리 환경 = FRED (2026-10-20 툴팁 출처)


def breadth_tip(b):
    """상승 비율 카드 ? — 무엇 가운데 몇 개가 올랐고 그 등급이 무슨 뜻인지."""
    full = b.get("mode") == "full"
    ratio = b["ratio"]
    grade = (b.get("label") or "")[1:].strip() or ("양호" if ratio >= 65 else "보통" if ratio >= 45 else "취약")
    if full:
        head = "오늘 S&P 500 종목 가운데 오른 종목이 얼마나 되는지"
        cnt = f"{b.get('advancers')}개 오르고 {b.get('decliners')}개 내렸다" if b.get("advancers") is not None else ""
    else:
        head = "오늘 미국 주요 업종 가운데 오른 업종이 얼마나 되는지"
        cnt = f"업종 {b.get('sectors_counted')}개 중 {b.get('sectors_up')}개가 올랐다" if b.get("sectors_up") is not None else ""
    mean = BREADTH_GRADE_NOW.get(grade, "")
    return (head + f"\n· 오늘 {ratio:.1f}% : " + ". ".join(x for x in (cnt, mean) if x) +
            "\n· 나누는 법 : 65% 이상 양호, 45~65% 보통, 45% 미만 취약")


def rs_group_tip(rs):
    """`상대강도` 소제목 ? — 세 비교 가운데 앞쪽이 강했던 것."""
    won = [w for k, w in (("qqq_spy_5d", "성장주"), ("iwm_spy_5d", "소형주"), ("rsp_spy_5d", "고르게 담은 지수")) if (rs.get(k) or 0) > 0]
    known = [k for k in ("qqq_spy_5d", "iwm_spy_5d", "rsp_spy_5d") if rs.get(k) is not None]
    now = ""
    if known:
        now = (f"\n· 오늘 {len(known)}개 중 {len(won)}개 : " +
               (" · ".join(won) + " 쪽이 시장 전체보다 강했다" if won else "모두 큰 회사 위주의 시장 전체 쪽이 강했다"))
    return ("최근 일주일 동안 두 지수 중 어느 쪽이 더 강했는지 견준 것" + now +
            "\n· 참고 : 값이 플러스면 앞에 적힌 쪽이 더 많이 올랐다는 뜻")


def _sgn(v):
    return f"{v:+.2f}".replace("-", "−")   # 툴팁 숫자 부호는 엔비디아와 같게 `−`


def qqq_tip(v):
    now = "" if v is None else f"\n· 오늘 {_sgn(v)}%p : {_ahead(v, '나스닥이', 'S&P 500')}. " + (
        "성장주 쪽이 강했던 한 주" if v > 0 else "성장주가 쉬어 간 한 주" if v < 0 else "어느 쪽도 앞서지 않았다")
    return "나스닥(성장주)이 S&P 500(시장 전체)보다 최근 일주일 동안 더 강했는지" + now


def iwm_tip(v):
    now = "" if v is None else f"\n· 오늘 {_sgn(v)}%p : {_ahead(v, '러셀 2000이', 'S&P 500')}. " + (
        "위험을 감수하는 쪽으로 돈이 움직일 때 흔히 보이는 모습" if v > 0 else "돈이 큰 회사 쪽에 머문 한 주" if v < 0 else "어느 쪽도 앞서지 않았다")
    return "러셀 2000(소형주)이 S&P 500보다 최근 일주일 동안 더 강했는지" + now


def rsp_tip(v, span="최근 일주일"):
    """동일가중(RSP) − 시총가중(SPY). span = `최근 일주일`(달라진 것) · `오늘 하루`(시장 탭)."""
    if v is None:
        now = ""
    elif v > 0:
        now = f"\n· 오늘 {_sgn(v)}%p : 고르게 담은 쪽이 {abs(v):.2f}%p 앞섰다. 상승이 소수 대형주가 아니라 넓게 퍼졌다"
    elif v < 0:
        now = f"\n· 오늘 {_sgn(v)}%p : 큰 회사 위주 쪽이 {abs(v):.2f}%p 앞섰다. 소수 대형주가 지수를 끌었다"
    else:
        now = f"\n· 오늘 {_sgn(v)}%p : 두 지수가 같았다"
    return f"종목을 똑같이 담은 지수와 큰 회사 위주 지수 중 {span} 어느 쪽이 더 강했는지" + now


POSITION_NOW = {"20일 고점 부근": "고점 근처", "단기 고점 부근 · 과열 주의": "고점 근처인데 한 달 새 5% 넘게 올라 과열 주의",
                "20일 저점 부근": "저점 근처", "박스 중간": "고점과 저점 사이"}   # analyze.position_stats 라벨 → 쉬운 말


def position_tip(p):
    """`20일 위치` 소제목 ? — S&P 500 으로 오늘을 읽어 준다."""
    now = ""
    fh, fl, label = (p or {}).get("from_high_pct"), (p or {}).get("from_low_pct"), (p or {}).get("position_label")
    if fh is not None and label:
        if "저점" in label and fl is not None:
            where = f"한 달 저점보다 {abs(fl):.1f}% 위"
        else:
            where = "한 달 고점에 있다" if fh >= -0.05 else f"한 달 고점보다 {abs(fh):.1f}% 아래"
        now = f"\n· 오늘 S&P 500 : {where}, {POSITION_NOW.get(label, label)}"
    return ("최근 한 달 동안 가장 높았던 값과 가장 낮았던 값 사이에서 지수가 지금 어디쯤인지" + now +
            "\n· 나누는 법 : 고점과 1% 안이면 고점 부근, 저점과 1% 안이면 저점 부근, 그 사이는 박스 중간. 고점 부근이면서 한 달에 5% 넘게 오르면 과열 주의")


def risk_rule(status):
    """구획 제목 옆 `판정` ? — 오늘 종합이 왜 그렇게 나왔는지와 판정 규칙 (옛 RISK_TIP)."""
    status = status or {}
    names = lambda lt: [n for k, n in STATUS_KEYS.items() if status.get(k) == lt]  # noqa: E731
    overall = status.get("overall")
    now = ""
    if overall == "🔴":
        now = f"\n· 오늘 경계 : {' · '.join(names('🔴'))}에 경계가 켜졌다"
    elif overall == "🟡":
        now = f"\n· 오늘 주의 : {' · '.join(names('🟡'))}에 주의가 켜져 조심할 신호가 여럿"
    elif overall == "🟢":
        c = names("🟡")
        now = "\n· 오늘 정상 : " + (f"주의가 {c[0]} 하나뿐이라 정상" if c else "켜진 위험 신호가 없다")
    return ("다섯 가지 위험 신호를 정상 · 주의 · 경계로 나눠, 시장이 지금 얼마나 불안한지 보는 것" + now +
            "\n· 나누는 법 : 경계가 하나라도 있으면 경계, 주의가 둘 이상이면 주의, 그 밖은 정상"
            "\n· 주의가 켜지는 때 : S&P 500이 평균 가격선 아래로 내려가거나, VIX가 18 이상, 상승 비율 55% 미만, "
            "금리가 일주일에 0.05%p 넘게 오르거나, 지수가 한 달에 4% 이상 오를 때")


def _pos(label):
    """20일 위치 라벨 — 고점·저점은 굵게, 라벨 전체 증감 색 (고점 빨강 · 저점 파랑, 2026-10-12 사용자)."""
    if not label:
        return ""
    col = UP_COLOR if "고점" in label else DOWN_COLOR if "저점" in label else None
    t = _esc(label).replace("고점", "<b>고점</b>").replace("저점", "<b>저점</b>")
    return f'<span style="color:{col};">{t}</span>' if col else t


def _light_pill(light, text=None):
    kind = LIGHT_KIND.get(light, "neutral")
    return dk.pill(text or _light_word(light) or "—", kind).replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 {dk.PILL_GAP + 5}px 0 {dk.PILL_GAP}px;", 1)   # 등급 라벨 오른쪽 +5 (2026-10-13 사용자)


TAB_TOP = 10   # 오늘 · 시장 탭 첫 콘텐츠 위 여백 +10 — margin 은 탭 줄 아래 14 와 겹쳐 사라지므로 padding (2026-10-13 사용자: "오늘, 시장 탭의 콘텐츠 시작 위쪽 여백을 10픽셀 추가")
LEAD_VP = 8   # 머리 결론 18px · 행간 34 의 반쪽 — 구분선 위아래 보이는 14 (2026-10-13 사용자: 카드 없이)


SEO_GRADE = {"Risk-On": "위험 선호", "Neutral": "중립", "Risk-Off": "위험 회피"}   # analyze.regime_score 라벨 → 한국어
SEO_INDICES = (("sp500", "S&P 500"), ("nasdaq", "나스닥"), ("dow", "다우"))


def sec_seo_lead(input_data, analysis):
    """검색 결과 요약 문단 (2026-10-18, 검색 노출) — 본문 맨 앞, 파이썬 값만으로 1~2문장.
    data-lead · data-cards 를 달지 않는다: 홈 카드 · 목록 요약은 data-lead 부터 읽으므로 이 문단은 거기 실리지 않는다.
    날짜는 시계열 기준 거래일(analysis.as_of, 뉴욕). 값이 없는 부분은 문장에서 뺀다."""
    a = analysis or {}
    as_of = a.get("as_of")
    day = ""
    if as_of:
        try:
            _, m, d = str(as_of).split("-")[:3]
            day = f"{int(m)}월 {int(d)}일 "
        except ValueError:
            day = ""
    indices = (input_data.get("market") or {}).get("indices") or {}
    chg = [f"{name} {float(indices[k]['change_pct']):+.2f}%" for k, name in SEO_INDICES
           if (indices.get(k) or {}).get("change_pct") is not None]
    sents = []
    if chg:
        sents.append(f"{day}미국 증시는 " + " · ".join(chg) + "로 마감했습니다.")
    nr = (a.get("normal") or {})
    outs = [sx.INDEX_NAME[k] for k in ("^GSPC", "^IXIC", "^DJI") if (nr.get(k) or {}).get("outside")]
    if nr.get("^GSPC"):   # 점수 대신 평소 범위 (2026-10-18 재설계 — 점수는 앞날을 가르지 못했다)
        sents.append((sx.eun(" · ".join(outs)) + " 평소 하루 움직임의 범위를 벗어났습니다.") if outs else "주요 지수는 모두 평소 하루 움직임의 범위 안이었습니다.")
    k = sx.seo_korea(a)   # 코스피 영향 한 문장 — 검색어 "코스피 영향" (2026-10-18 사용자)
    if k:
        sents.append(k)
    if not sents:
        return ""
    return (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">'
            + dk._tint_inline(_esc(" ".join(sents))) + "</p>")   # 요약 문장의 증감도 색 (가이드라인 3-3-1, 예외 없음) — 문장이라 숫자(와 앞 지수 이름)만 칠한다. dk.tint 는 가운뎃점 덩어리 통째로 칠해 문장 앞머리까지 파랗게 된다


def sec_lead(report, analysis):
    """글 머리(제목 없음, data-lead): 한 줄 결론 + 종합을 한 강조 카드에 (2026-10-12 사용자: 하나의 카드로 통합, 가로 구분선, 16px).
    홈 카드는 '(머리)'로 한 줄 결론을(구분선 아래는 건너뜀), '(종합)'으로 data-insight 문단을 읽는다."""
    one = str(report.get("one_line") or "").strip()
    inner = f'<div style="color:#111;font-weight:700;padding-left:{dk.ALIGN_PX}px;">{_esc(dk.ko(one, TERM_KO))}</div>' if one else dk.muted("한 줄 결론 없음")   # 카드 대신 굵게 (2026-10-13 사용자)
    paras = _paragraphs(report.get("opinion"))
    if paras:
        # 문장마다 한 줄, 문단 사이 빈 줄 하나 (2026-10-16 사용자) — 끝 문단 아래 여백은 두지 않아 카드 여백에 더해지지 않게
        body = "".join(f'<div data-para="1" style="margin:{PARA_GAP if i else 0}px 0 0;">' + "".join(f'<span data-sent="1">{_esc(dk.ko(s, TERM_KO))}</span> ' for s in sents) + "</div>" for i, sents in enumerate(paras))   # PC 한 줄씩 · 모바일 이어 흐름 (테마 CSS)
        inner += (f'<div style="margin:{14 - LEAD_VP}px 0 0;padding-top:{14 - LEAD_VP}px;border-top:1px solid #E2E8F0;">'   # 일반 구분선, 위아래 보이는 14 (2026-10-13 사용자: "구분선은 일반 구분선 컬러로 유지")
                  f'<div data-insight="1" style="font-size:{dk.BODY};color:#111;padding-left:{dk.ALIGN_PX}px;">{body}</div></div>')   # 구분선 아래 18px (2026-10-13 사용자)   # 구분선 아래 종합 문단만 16px (2026-10-12 사용자: "이것만 16포인트")   # 18px · 행간 33 은 바깥에서 물려받는다
    return dk.cards(f'<div style="margin:0 0 8px;padding-top:{TAB_TOP}px;line-height:{dk.LH_BODY};">{inner}</div>')   # 오늘 탭 첫 콘텐츠 위 +10 (2026-10-13 사용자)   # 강조 카드 디자인 삭제 — 배경 · 테두리 · 안쪽 여백 없음 (2026-10-13 사용자)


def sec_regime(analysis, report, prev=None):
    """시장 상태 — 해설 먼저(2026-10-12 사용자: 모든 탭 일괄), 점수 카드(접힘) → 펼치면 어제 대비 + 요소별 막대 C 카드. 점수는 analyze.py 규칙값.
    2026-10-13 사용자: 등급 라벨은 점수 앞, 오른쪽 끝 펼침 화살표, 6개 정보는 펼쳤을 때."""
    regime = (analysis or {}).get("regime") or {}
    comment = _text(report.get("regime_comment"))
    if regime.get("score") is None:
        return dk.muted("오늘은 시장 상태 점수를 계산하지 못했습니다.") + comment
    light = regime.get("light") or "🟡"
    grade = dk.ko(regime.get("label") or "", TERM_KO)
    # 점수 · 등급 설명은 본문 글머리표가 아니라 "점수" 옆 ? 툴팁 (2026-10-12 사용자: "점수 위험 선호 내용은 툴팁으로 제공하고 본문에서 삭제")
    explain = score_tip(regime)   # 뜻 · 오늘 · 나누는 법 (가이드라인 2-6)
    score_card = dk.state_card("점수" + dk.tip_icon(explain), LIGHT_KIND.get(light, "neutral"),   # `안내 ?` (2026-10-13 사용자: 아이콘만 두지 않는다) · 따로 카드, 배경은 등급 라벨 색 (2026-10-12 사용자)
                               _light_pill(light, grade) + f' <span style="font-size:{SCORE_SIZE};">{int(regime["score"])} <span style="color:{dk.SUB};font-weight:400;">/ 100</span></span>', chev=True)   # 라벨이 점수 앞 (2026-10-13 사용자) · 86 / 100 은 20px 굵게 (2026-10-12 사용자)
    rows = []
    if regime.get("score_prev") is not None:
        rows.append(("어제 대비", dk.arrow(regime.get("delta") or 0, 0, ""), _esc(f"어제 {regime['score_prev']}점")))
    else:
        rows.append(("어제 대비", dk.dash(), "어제 점수 없음"))   # 구분명 │ 보조 줄 한 줄 (crow, 2026-10-12 사용자)
    html_rows = [dk.crow(n, v, sb, first=(i == 0)) for i, (n, v, sb) in enumerate(rows)]
    bars = []
    for key, label in REGIME_COMPONENT_LABELS.items():
        c = (regime.get("components") or {}).get(key) or {}
        score, mx = c.get("score"), c.get("max")
        if score is None or not mx:
            continue
        frac = score / mx
        col = LIGHT_COLOR["🟢"] if frac >= 0.7 else LIGHT_COLOR["🟡"] if frac >= 0.45 else LIGHT_COLOR["🔴"]
        p = _get(prev, "regime", "components", key, "score")
        d = "" if p is None else " " + dk.arrow(score - p, 0, "")   # 요소 점수도 어제 대비 (2026-10-13 사용자)
        bars.append((_esc(label), frac, col, f"{int(score)} <span style='color:{dk.SUB};font-weight:400;'>/ {int(mx)}</span>{d}"))
    if bars:   # 막대는 가장 긴 이름(금리 환경) + 14px 뒤에서 시작, 모두 같은 길이 (2026-10-12 사용자)
        w = dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])
        html_rows += [dk.bar_row(n, f, c, v, w) for n, f, c, v in bars]
    return dk.state_fold(score_card, dk.card_of(html_rows)) + comment   # 제목 밑줄 없이 바로 점수 카드, 해설은 아래 (2026-10-13 사용자) · 누르면 6개 정보


def _arrows(last5):
    """최근 5일 방향 ↑↓ — 왼쪽이 5거래일 전, 끝이 오늘. 상승 빨강 · 하락 파랑, 굵게 (2026-10-12 사용자)."""
    colors = {"↑": UP_COLOR, "↓": DOWN_COLOR}
    return "".join(f'<b style="color:{colors.get(a, MUTED)};">{_esc(a)}</b>' for a in last5)


INDEX_SHOWN = 2   # S&P 500 · 나스닥만 보이고 나머지는 펼침 (2026-10-12 사용자) — FOLD_SHOWN 과 같은 값


def sec_indices(indices, analysis, report):
    """주요 지수 — 해설 먼저(2026-10-12 사용자), C 카드(왼쪽 60%): 지수, 값 가격 + 1일 등락, 보조 줄 5일·20일·최근 5일·위치.
    S&P 500 · 나스닥만 보이고 다우존스 · 러셀 2000 · VIX는 펼침 버튼 안."""
    series = (analysis or {}).get("series") or {}
    position = (analysis or {}).get("position") or {}
    rows = []
    for key in ("sp500", "nasdaq", "dow", "russell", "vix"):
        rec = indices.get(key) or {}
        s = series.get(INDEX_SYMBOL[key]) or {}
        label = (position.get(key) or {}).get("position_label")
        value = f'<span style="font-weight:400;">{_esc(_fmt_price(rec.get("price")))}</span> {dk.arrow(rec.get("change_pct"))}'   # 지수 가격 보통 굵기 (2026-10-13 사용자)
        sub = []
        if s.get("ret_5d") is not None:
            sub.append(f"5일 {s['ret_5d']:+.2f}%")   # 덩어리째 증감 색은 crow 의 tint
        if s.get("ret_20d") is not None:
            sub.append(f"20일 {s['ret_20d']:+.2f}%")
        if s.get("last5"):
            sub.append("최근 5일 " + _arrows(s["last5"]))
        if label:
            sub.append(_pos(label))   # 고점·저점 굵게 + 증감 색
        rows.append((_esc(INDEX_LABELS.get(key, key)), value, " · ".join(sub)))
    return _text(report.get("summary")) + dk.ccard(rows, left=60, fold_at=INDEX_SHOWN, noun="지수")   # 펼침 버튼은 같은 카드 안 (2026-10-13 사용자)


def sec_change(analysis, report, prev=None):
    """달라진 것 — 상대강도·추세·VIX C 카드 + 해설. 분석이 없으면 빈 문자열(구획 생략)."""
    if not analysis:
        return ""
    series = analysis.get("series") or {}
    position = analysis.get("position") or {}
    rs = analysis.get("rs") or {}
    vix = analysis.get("vix") or {}
    # 읽는 법은 카드가 아니라 그 내용의 제목(소제목 · 구분명) 옆 ? 툴팁 — 7번째 값 (2026-10-12 사용자: "해당 내용만 툴팁으로 타이틀 옆에")
    prs = (prev or {}).get("rs") or {}
    rows = [("성장주 vs 시장 (나스닥 vs S&P 500 · 5일)", dk.arrow(rs.get("qqq_spy_5d"), 2, "%p"), _vs(rs.get("qqq_spy_5d"), prs.get("qqq_spy_5d")), None, False, True,
             qqq_tip(rs.get("qqq_spy_5d"))),
            ("소형주 vs 시장 (러셀 2000 vs S&P 500 · 5일)", dk.arrow(rs.get("iwm_spy_5d"), 2, "%p"), _vs(rs.get("iwm_spy_5d"), prs.get("iwm_spy_5d")), None, False, True,
             iwm_tip(rs.get("iwm_spy_5d"))),
            ("동일가중 vs 시총가중 (RSP vs SPY · 5일)", dk.arrow(rs.get("rsp_spy_5d"), 2, "%p"), _vs(rs.get("rsp_spy_5d"), prs.get("rsp_spy_5d")), None, False, True,
             rsp_tip(rs.get("rsp_spy_5d")))]   # 어제 대비는 줄 아래 한 줄 (sub_below)
    streak = rs.get("qqq_streak")
    if streak is not None:
        rows.append(("나스닥이 S&P 500을 웃돈 연속 일수", f"{int(streak)}일", _vs(streak, prs.get("qqq_streak"), 0, "일"), None, False, True))
    out = (_text(report.get("change_comment")) + dk.sub_label("상대강도", rs_group_tip(rs))
           + dk.ccard(rows, fold_at=FOLD_SHOWN, noun="항목"))   # 앞 2줄 + 카드 아래 더 보기 (2026-10-13 사용자: 소제목 화살표 대신)
    trows = []
    for key in ("sp500", "nasdaq", "russell"):
        s = series.get(INDEX_SYMBOL[key]) or {}
        p = position.get(key) or {}
        sub = []
        if s.get("up_days_20") is not None:
            sub.append(_esc(f"20일 중 상승 {s['up_days_20']} · 하락 {s['down_days_20']}"))
        if p.get("from_high_pct") is not None:
            sub.append(_esc(f"20일 고점 대비 {p['from_high_pct']:+.2f}% · 저점 대비 {p['from_low_pct']:+.2f}%"))
            sub.append(_vs(p["from_high_pct"], _get(prev, "position", key, "from_high_pct"), word="고점 대비 어제보다"))   # 고점과의 거리 변화 (2026-10-13 사용자: 어제 대비)
        trows.append((_esc(INDEX_LABELS[key]), _pos(p.get("position_label")) or "—", _join(*sub)))
    if vix.get("now") is not None and vix.get("prev_5d") is not None:   # VIX 는 같은 카드 마지막 줄 (2026-10-13 사용자: 더 보기 안으로)
        trows.append(("VIX (5거래일)", f'{vix["prev_5d"]:.2f} → <b>{vix["now"]:.2f}</b> {dk.arrow(vix.get("change_5d") or 0.0, 2, "")}',
                      _vs(vix["now"], _get(prev, "vix", "now"), 2, ""), 35, True, True))   # 값 한 줄 (2026-10-12 사용자), 어제 대비는 줄 아래
    return out + dk.sub_label("20일 위치", position_tip(position.get("sp500"))) + dk.ccard(trows, fold_at=FOLD_SHOWN, noun="항목")


def _up_down(up, down):
    """상승 / 하락 개수 — ▲ 빨강 · ▼ 파랑 (2026-10-12 사용자: 증감 삼각형)."""
    return (f'<span style="color:{UP_COLOR};white-space:nowrap;">▲&nbsp;{up}</span> / '
            f'<span style="color:{DOWN_COLOR};white-space:nowrap;">▼&nbsp;{down}</span>')


def sec_breadth(analysis, prev=None):
    """시장 폭 — 상승 비율 카드(접힘) → 펼치면 어제 대비 · 상승 / 하락 · 동일가중 C 카드. 프록시 모드는 섹터 ETF 상승 개수, 전수 모드는 상승/하락 종목 수.
    2026-10-13 사용자: 점수 카드와 같게 — 라벨이 비율 앞, 오른쪽 끝 펼침 화살표, 설명은 `안내 ?`."""
    b = (analysis or {}).get("breadth") or {}
    if b.get("ratio") is None:
        return ""
    light = (b.get("label") or "")[:1]
    grade = (b.get("label") or "")[1:].strip()
    explain = breadth_tip(b)   # 등급 설명은 본문 글머리표 대신 `안내 ?` (점수 카드와 같게, 2026-10-13 사용자) · 뜻 · 오늘 · 나누는 법 (가이드라인 2-6)
    ratio_card = dk.state_card("상승 비율" + dk.tip_icon(explain), "neutral",   # 신호 색 없음 (2026-10-18 재설계 B5 — 등급이 앞날을 가르지 못했다)
                               dk.pill(grade, "area").replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 {dk.PILL_GAP + 5}px 0 {dk.PILL_GAP}px;", 1) + f' {b["ratio"]:.1f}%' if grade else f'{b["ratio"]:.1f}%', chev=True)   # 따로 카드, 배경은 등급 색 (2026-10-12 사용자) · 라벨이 비율 앞 (2026-10-13 사용자)
    pb = (prev or {}).get("breadth") or {}
    rows = []
    if pb.get("ratio") is not None:
        rows.append(("어제 대비", dk.arrow(round(b["ratio"] - pb["ratio"], 1), 1, "%p"), _esc(f"어제 {pb['ratio']:.1f}%")))
    else:
        rows.append(("어제 대비", dk.dash(), "어제 값 없음"))
    if b.get("mode") == "full":
        rows.append(("상승 / 하락 종목", _up_down(b.get("advancers"), b.get("decliners")), "S&P 500 구성종목"))
        if b.get("new_high_52w") is not None:
            rows.append(("52주 신고가 / 신저가", f'{b["new_high_52w"]} / {b["new_low_52w"]}', ""))
    else:
        rows.append(("섹터 ETF", _up_down(b.get("sectors_up"), b.get("sectors_down")),
                     _join(f"{b.get('sectors_counted')}개 기준", _vs(b.get("sectors_up"), pb.get("sectors_up"), 0, "개", "상승 어제 대비"))))   # 폰에서도 구분명 │ 보조 줄 한 줄 (2026-10-12 사용자) — 상승·하락은 ▲▼ 가 말한다
    if b.get("rsp_spy_1d") is not None:
        rows.append(("동일가중 − 시총가중 (1일)", dk.arrow(b["rsp_spy_1d"], 2, "%p"), _vs(b["rsp_spy_1d"], pb.get("rsp_spy_1d")), None, False, True,
                     rsp_tip(b["rsp_spy_1d"], "오늘 하루")))   # 읽는 법은 구분명 옆 ? (2026-10-12 사용자)
        if b.get("rsp_spy_5d") is not None:
            rows.append(("동일가중 − 시총가중 (5일)", dk.arrow(b["rsp_spy_5d"], 2, "%p"), _vs(b["rsp_spy_5d"], pb.get("rsp_spy_5d")), None, False, True))
    return dk.state_fold(ratio_card, dk.ccard(rows)).replace('<details data-acc="1" style="margin:0 0 8px;">', f'<details data-acc="1" style="margin:0 0 8px;padding-top:{TAB_TOP}px;">', 1)   # 시장 탭 첫 콘텐츠 위 +10 (2026-10-13 사용자)   # 상승 비율 카드를 누르면 펼침 (2026-10-13 사용자)


def sec_sectors(analysis, report):
    """섹터 — 해설 먼저, 주도·약세 줄, 막대 카드: 테마(ETF) · 막대 · 등락률, 보조 줄 5일 순위 대비. 앞 3개만 보이고 나머지는 펼침 (2026-10-12 사용자)."""
    ranked = ((analysis or {}).get("sectors") or {}).get("ranked_1d") or []
    if not ranked:
        return ""
    max_abs = max(abs(r["ret_1d"]) for r in ranked) or 1.0
    bars = []
    for r in ranked:
        col = UP_COLOR if r["ret_1d"] >= 0 else DOWN_COLOR
        d = r.get("rank_change")
        sub = "" if d is None else (f"5일 순위 대비 ▲{d}" if d > 0 else f"5일 순위 대비 ▼{-d}" if d < 0 else "5일 순위와 같음")
        sub = " · ".join(x for x in (r["etf"], sub) if x)   # ETF 코드는 보조 줄로 — 이름 칸을 짧게 해 막대 자리를 둔다
        bars.append((_esc(r["theme"]), abs(r["ret_1d"]) / max_abs, col, dk.arrow(r["ret_1d"]), _esc(sub)))
    w = dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])   # 접힌 줄까지 같은 폭 → 막대 길이 모두 같음
    rows = [dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)]
    by_etf = {r["etf"]: r for r in ranked}
    names = lambda etfs: " · ".join(_esc(by_etf[e]["theme"]) for e in etfs if e in by_etf)  # noqa: E731
    sectors = analysis["sectors"]
    lis = "".join(dk.dot_li(f"<b>{k}</b> : {v}", size=3, lh=dk.LH_EMPH) for k, v in (("주도", names(sectors.get("leaders") or []) or "—"), ("약세", names(sectors.get("laggards") or []) or "—")))
    lead = dk.dcard(f"<ul style='margin:-9px 0;padding:0;list-style:none;font-size:{dk.SMALL};'>{lis}</ul>", "positive")   # 강조 카드 (2026-10-12 사용자)   # 긴 이름 나열은 값 칸이 아니라 라벨 글머리표로 (가이드라인 3-3)
    return _text(report.get("sector_comment")) + lead + _folded(rows, "섹터")


def _bp(bp):
    return "—" if bp is None else f"{int(bp):+d}bp"


MACRO_ROWS = (   # (키, 이름, 단위, 증감 단위, 증감 배수) — 단위는 값에, 이름에서는 뺀다 (2026-10-12 사용자)
    ("us2y", "2년물 금리", "%", "bp", 100),
    ("spread_10_2", "10년 − 2년", "%p", "bp", 100),
    ("fed_funds", "기준금리", "%", "bp", 100),
    ("unemployment_rate", "실업률", "%", "%p", 1),
    ("cpi", "소비자물가", "", "%", None),   # CPI 지수, 증감은 전월 대비 % — 이름을 줄여 `구분명 │ 날짜` 한 줄
    ("vix", "VIX", "", "", 1),
)


def _macro_value(rec, unit, chg_unit, mult):
    """값 + 단위, 뒤에 직전 관측 대비 증감(▲▼ 증감 색). 직전 값이 없으면 값만."""
    if not rec or rec.get("value") is None:
        return dk.dash()
    out = f"{rec['value']:.2f}{unit}"
    prev = rec.get("prev")
    if prev is None:
        return f'<span style="font-weight:400;">{_esc(out)}</span>'   # 증감 아닌 값은 보통 굵기 (2026-10-13 사용자)
    if mult is None:   # 변화율 %
        d = (rec["value"] - prev) / prev * 100 if prev else None
        digits = 1
    else:
        d = (rec["value"] - prev) * mult
        digits = 0 if chg_unit == "bp" else 2
    if d is None:
        return f'<span style="font-weight:400;">{_esc(out)}</span>'
    if digits == 0:
        d = round(d)
    return f'<span style="font-weight:400;">{_esc(out)}</span> {dk.arrow(d, digits, chg_unit)}'


def sec_macro(macro, analysis, report):
    """금리·지표 — 해설 먼저, C 카드: 지표(단위 없음) · 값(단위 + 직전 관측 대비 증감) · 보조 줄 기준일.
    10년물은 1일·5일 변화와 기준일을 줄 아래 한 줄로 (2026-10-12 사용자). 증감은 모두 색."""
    rates = (analysis or {}).get("rates") or {}
    rows = []
    rec10 = macro.get("us10y") or {}
    v10, d10 = rec10.get("value"), rec10.get("date", "")
    if rates.get("us10y") is not None:
        v10, d10 = rates["us10y"], (analysis or {}).get("as_of") or d10
    chg = f"1일 {_bp(rates.get('us10y_change_1d_bp'))} · 5일 {_bp(rates.get('us10y_change_5d_bp'))}" if rates.get("us10y_change_5d_bp") is not None else ""
    rows.append(("10년물 금리", f'<span style="font-weight:400;">{_esc(f"{v10:.2f}%")}</span>' if v10 is not None else dk.dash(), _esc(" · ".join(x for x in (chg, dk.day(d10)) if x)), None, False, True))
    for key, label, unit, chg_unit, mult in MACRO_ROWS:
        if key in ("us2y", "spread_10_2", "fed_funds") and not macro.get(key):
            continue
        rec = macro.get(key) or {}
        rows.append((label, _macro_value(rec, unit, chg_unit, mult), _esc(dk.day(rec.get("date", ""))) if rec else ""))
    if rates.get("growth_label"):
        rows.append(("금리와 성장주", f'<span style="font-weight:400;">{_esc(rates["growth_label"])}</span>', ""))   # 따로 카드를 만들지 않고 같은 카드 안에 (가이드라인 2-1)
    html_rows = [dk.crow(r[0], r[1], r[2], first=(i == 0), sub_below=bool(len(r) > 5 and r[5])) for i, r in enumerate(rows)]
    return _text(report.get("macro_comment")) + _folded(html_rows, "지표")


FOLD_SHOWN = 2   # 카드 줄이 많으면 앞 2줄만 보이고 나머지는 '더 보기' 펼침 (2026-10-12 사용자: "섹터는 2개만, 다른 탭에도 동일하게 2개만")


def _folded(rows_html, noun):
    """줄 목록 → 카드. FOLD_SHOWN 줄이 넘으면 나머지는 펼침 버튼 안의 둘째 카드로 (각 카드 첫 줄은 first=True 로 만들어 둔다)."""
    if len(rows_html) <= FOLD_SHOWN:
        return dk.card_of(rows_html)
    rest = rows_html[FOLD_SHOWN:]
    return dk.card_of(rows_html, fold_at=FOLD_SHOWN, noun=noun)   # 펼침 버튼은 같은 카드 안 (2026-10-13 사용자)


QUOTE_LEFT = 40   # 종목 칸 40% — 값 `$162.57 ▲ 1.25%` 이 한 줄에 들도록 (거래량은 종목 아래 줄)


def _quote_rows(quotes):
    """급등주·관심 종목 — 종목 아래 줄에 거래량, 값(가격 + 등락)은 한 줄 (2026-10-12 사용자). data-pick: 홈 '오늘의 급등주' 카드가 읽는다."""
    rows = []
    for q in quotes or []:
        sym = q.get("symbol") or "-"
        sector = SECTOR_KO.get(q.get("sector") or "", q.get("sector") or "")
        vol = '<span style="white-space:nowrap;">' + _esc("거래량 " + _fmt_volume(q.get("volume"))) + "</span>"   # 라벨과 거래량 사이에서만 줄이 바뀌게
        tag = dk.pill(sector, bare=True) if sector else ""   # 여백 없음 (2026-10-13 사용자)   # 줄 첫머리 라벨 — 왼쪽 0, 오른쪽 4   # 섹터 라벨이 거래량보다 앞 (2026-10-13 사용자: "어느 섹터인지가 더 중요")
        value = (f'<span style="font-weight:400;">{_esc(_fmt_price(q.get("price")))}</span> {dk.arrow(q.get("change_pct"))}'   # 가격은 보통 굵기 (2026-10-13 사용자)
                 + (f'<span style="display:block;line-height:1;margin:6px 0 0;">{tag}</span>' if tag else ""))   # 섹터 라벨은 증감 아래 줄, 오른쪽 정렬, 여백 없음 (2026-10-13 사용자)
        r = dk.crow(dk.ticker_logo(sym) + _esc(sym), value, vol, first=len(rows) == 0,
                    left=QUOTE_LEFT, nowrap=True, sub_block=True)
        chg = q.get("change_pct")
        r = r.replace('<span style="', f'<span data-pick="1" data-sym="{_esc(sym)}" data-price="{_esc(_fmt_price(q.get("price")))}" data-chg="{"" if chg is None else f"{float(chg):+.2f}%"}" style="', 1)
        rows.append(r)
    if not rows:
        return dk.muted("데이터 없음")
    return _folded(rows, "종목")


def _named_reaction(sym, value_html):
    """관련 자산 한 칸 — 이름까지 증감 색 (2026-10-11 사용자: % 만이 아니라 종목도 같이 색). 값이 bp 등 색 없는 경우는 이름도 기본색."""
    name = _esc(SYMBOL_NAMES.get(sym, sym))
    col = UP_COLOR if "▲" in value_html else DOWN_COLOR if "▼" in value_html else None
    if col is None and "<" not in value_html and value_html[:1] in "+-−":   # 금리 bp 처럼 색 없이 온 값도 증감 색 (2026-10-12 사용자)
        col = UP_COLOR if value_html[0] == "+" else DOWN_COLOR
        value_html = f'<span style="color:{col};font-weight:700;">{value_html}</span>'
    return f'<span style="color:{col};">{name}</span> {value_html}' if col else f"{name} {value_html}"


NEWS_REL_SIZE = "15px"   # 뉴스 `관련 자산` 줄 14 → 15 굵게 (2026-10-13 사용자)


def sec_news(input_data, report, analysis):
    """뉴스 — 공용 뉴스 카드. 기사 칸(헤드라인 = 원제 번역 · 요약 줄 · 테마 · 관련 종목)은 모두 공용 처리(news_store, collect_news.process)가 정하고,
    데일리 AI 는 어떤 기사를 실을지(index)만 고른다 (2026-10-25 사용자: 공용 기사에 특별 케이스 없이). 선정 이유 줄은 없앴다 — 요약 줄이 그 몫."""
    series = (analysis or {}).get("series") or {}
    rates = (analysis or {}).get("rates") or {}
    quotes = {q["symbol"]: q for q in input_data.get("gainers", []) + input_data.get("most_active", []) if q.get("symbol")}   # 옛 입력용 (2026-10-18 부터 빈 목록)
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
        theme = news_item.get("theme")
        if theme and theme not in THEME_VOCAB:
            theme = "기타"
        tag = dk.pill(theme, bare=True) if theme else ""
        title = _esc(news_item.get("headline_ko") or news_item.get("title") or "")   # 원제 번역 (홈과 같은 기사 = 같은 헤드라인) — 처리 실패면 영문 원제
        related = [s for s in (news_item.get("related") or []) if isinstance(s, str) and s in known][:4]   # 관련도 2 이상 종목 중 오늘 시세가 있는 것
        subs = []
        if related:
            subs.append(f'<span style="font-size:{NEWS_REL_SIZE};font-weight:700;">관련 자산 : ' + " · ".join(_named_reaction(s, reaction(s)) for s in related) + "</span>")   # 15px 굵게 (2026-10-13 사용자) · 종목 이름도 증감 색 (가이드라인 3-3)
        sub_html = [f'<span style="display:block;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;">{x}</span>' for x in subs]
        # 공용 뉴스 카드 (design_kit.news_item, 2026-10-25 뉴스 형식 통일): 헤드라인(원문 링크) / 요약 줄 / 관련 자산 / [테마]  매체
        # 매체명을 보이는 글자로 — 출처 명시(저작권법 제37조)는 툴팁이 아니라 본문 글자여야 한다 (2026-10-21, 운영지침 D4-3)
        items.append(dk.news_item(title, news_item.get("link"), news_item.get("detail_ko") or "", sub_html, tag, [news_item.get("source") or ""]))   # 요약 줄 = 공용 처리 detail
    # 방송 줄 — 미디어 데일리 재료 중 시장 · 업종 이슈, 방송 여러 곳이 같이 다룬 순 (2026-10-25 사용자). 의견이 섞여 `방송` 라벨 + 채널 · 방송 n곳
    # 시장 이야기의 집은 데일리 (2026-10-30 사용자: 미디어 데일리 글을 접으며) — 상한 없이 전부, 앞 MEDIA_SHOWN 건만 펼치고 나머지는 접기
    media = []
    for r in _media_lines():
        labels = (dk.pill(r["theme"], bare=True) + " " + dk.pill({"positive": "긍정", "negative": "부정"}.get(r["direction"], "중립"),
                                                                  r["direction"] if r["direction"] in ("positive", "negative") else "neutral", bare=True)
                  + (" " + dk.pill("엇갈림", "uncertain", bare=True) if r.get("split") else "")
                  + (" " + dk.pill("예상 밖", "uncertain", bare=True) if r.get("surprise") else ""))   # `방송` 라벨은 뺀다 — 메타의 채널 · 방송 n곳과 중복 (2026-10-26 사용자). 엇갈림 · 예상 밖은 미디어 데일리 순위 글에서 옮겨 옴
        meta = [_kst_hm(r["published_at"]), r["channel"], f"방송 {r['n_channels']}곳" if r["n_channels"] > 1 else ""]
        media.append(dk.news_item(_esc(r["topic"]), r["url"], r["note"], (), labels, meta, ' data-trhelp="skip"'))
    if not items and not media:
        return dk.muted("주요 뉴스 없음")
    out = dk.item_rules(items + media[:MEDIA_SHOWN], sub=True, indent=dk.ALIGN_PX)   # 카드 대신 기사 사이 가로 구분선, 위아래 27 (2026-10-13 사용자)
    if len(media) > MEDIA_SHOWN:
        out += dk.fold(f"방송 {len(media) - MEDIA_SHOWN}건 더 보기", dk.item_rules(media[MEDIA_SHOWN:], sub=True, indent=dk.ALIGN_PX))
    return out


def _overall_text(overall, items):
    """종합 설명 (결론, 이유) — 항목 신호 개수와 판정 규칙대로 왜 이 종합인지. 사실만."""
    names = lambda lt: [label for label, light, _ in items if light == lt]  # noqa: E731
    warn, caution = names("🔴"), names("🟡")
    if overall == "🔴":
        return f"경계 {len(warn)}개 ({' · '.join(warn)})", "경계가 하나라도 있으면 종합은 경계입니다"
    if overall == "🟡":
        return f"주의 {len(caution)}개 ({' · '.join(caution)})", "주의가 둘 이상이라 종합은 주의입니다"
    if caution:
        return f"주의 {len(caution)}개 ({' · '.join(caution)}), 나머지는 정상", "주의가 하나뿐이라 종합은 정상입니다"
    return f"{len(items)}개 항목이 모두 정상입니다", "지금 켜진 위험 신호가 없습니다"


def sec_status(analysis, report, prev=None):
    """주의할 위험요인 (옛 이름 위험 지도) — 위험요인 글, 그 아래 C 카드: 종합 설명 + 항목 5개(신호·근거). 규칙 설명은 제목 옆 ?."""
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
    p = prev or {}
    vs = {   # 근거 값의 어제 대비 (2026-10-13 사용자: 모든 데이터)
        "변동성": _vs(vix.get("now"), _get(p, "vix", "now"), 2, ""),
        "시장 폭": _vs(breadth.get("ratio"), _get(p, "breadth", "ratio"), 1, "%p"),
        "금리 위험": _vs(rates.get("us10y_change_5d_bp"), _get(p, "rates", "us10y_change_5d_bp"), 0, "bp"),
        "과열 위험": _vs(spy.get("ret_20d"), _get(p, "series", "SPY", "ret_20d")),
    }
    pst = p.get("status") or {}
    was = {"추세 유지": pst.get("trend"), "변동성": pst.get("volatility"), "시장 폭": pst.get("breadth"), "금리 위험": pst.get("rates"), "과열 위험": pst.get("overheat")}
    overall = status["overall"]
    head, why = _overall_text(overall, items)
    overall_card = dk.state_card(_esc(head), LIGHT_KIND.get(overall, "neutral"), sub_html=_esc(why), center=True)   # 가운데 정렬 (2026-10-13 사용자)
    pad_old = f"padding:{dk.EMPH_PAD - dk.VP_EMPH}px 14px {dk.EMPH_PAD - dk.VP}px;margin:0 0 8px;"
    overall_card = overall_card.replace(pad_old, f"padding:{dk.EMPH_PAD - dk.VP_EMPH - 12}px 14px {dk.EMPH_PAD - dk.VP - 13}px;margin:40px 0 8px;", 1)   # 높이 −20%(83 → 66: 위아래 패딩 −8 · −8) · 위 여백 20 → 40 (2026-10-14 사용자)
    overall_card = overall_card.replace("color:#374151;margin-top:2px;", "color:#374151;margin-top:1px;", 1)   # 두 문장 사이 보이는 12 → 11 (−10%, 같은 날)   # 높이 약 10% 줄임(위아래 −4 · −5) · 위 여백 +20 (2026-10-13 사용자)   # 종합은 따로 카드, 라벨 없이 설명, 배경은 신호 색 (2026-10-12 사용자)
    rows = []
    for label, light, basis in items:
        changed = f"어제 {_light_word(was[label])}" if was.get(label) and light and was[label] != light else ""   # 신호가 바뀐 날만 어제 신호
        rows.append((_esc(label), _light_pill(light) if light else dk.dash(), _join(_esc(basis), vs.get(label, ""), _esc(changed))))
    risks = [dk.ko(ln, TERM_KO) for ln in str(report.get("risk") or "").splitlines() if ln.strip()]
    risk_ul = dk.dot_ul([dk.dot_li(dk.tint(_esc(t)), size=3, lh=dk.LH_BODY, margin=dk.LI_MARGIN) for t in risks]) if risks else ""   # 강조 카드 삭제 — 본문 글머리표 (2026-10-13 사용자)
    return risk_ul + overall_card + dk.rule_rows(rows)   # 신호 줄은 흰 카드 대신 가로 구분선 (2026-10-13 사용자)   # 글 먼저, 강조 카드 (2026-10-12 사용자), 소제목 없음 — 구획 제목이 '주의할 위험요인'   # 판정 규칙은 제목 옆 ? 툴팁 (가이드라인 2-1 상태 카드 규칙)


def build_body(input_data, report, cover_url=None, analysis=None, output_dir=None):
    """2026-10-18 재설계 (doc/기획/데일리-리포트-기획.md 6절) — 탭 = 독자 질문 묶음.
    오늘(D1 · D2 · D3 · D6) · 한국장(K1 · K2 · K3) · 시장(D4) · 일정(D5). 시장 상태 점수 · 신호등 · 급등주 · 거래 상위 · 위험요인은 뺐다 (5절 B5 · B6).
    홈 카드 CARDS: summary = (머리), insight = (종합) — 머리 카드의 data-insight 그대로."""
    indices = input_data.get("market", {}).get("indices", {})
    prev = _prev_analysis(analysis)   # 어제 대비 (2026-10-13 사용자)
    a = analysis or {}
    parts = [
        dk.WRAP_OPEN,
        sec_seo_lead(input_data, analysis),   # 검색 결과 요약 — 보이는 첫 요소, data-lead 보다 앞 (2026-10-18)
        # S&P 500 그래프가 커버 이미지 자리 (2026-10-18 사용자, 엔비디아처럼). 그래프가 없는 날만 AI 커버
        sec_chart(output_dir) or _cover_image(cover_url),
        sec_lead(report, analysis),
    ]
    today_cards = sx.normal_card(a) + sx.shock_card(a) + sx.market_now_card(a)
    if today_cards:
        parts.append(dk.section("핵심 질문", cards.cards_grid(today_cards), tab=TAB_TODAY))
    parts += [
        dk.section("주요 지수", sec_indices(indices, analysis, report), tab=TAB_TODAY),
        dk.keep_tone(dk.section("뉴스", sec_news(input_data, report, analysis), tab=TAB_TODAY)),   # 뉴스는 헤드라인체 그대로 (2026-10-18 사용자)
    ]
    korea = sx.korea_open_card(a) + sx.korea_pairs_card(a) + sx.fx_card(a)
    if korea:
        parts.append(dk.section(TAB_KOREA, cards.cards_grid(korea), tab=TAB_KOREA))   # 탭 이름과 같은 구획 제목은 테마가 탭 화면에서 숨긴다
    parts.append(kr_news.section(_media_rows()))   # 소식이 없어도 표시 주석은 남긴다 — 미디어 데일리 실행 뒤 kr_news.py 가 이 칸만 채운다 (2026-10-25)
    mega = sx.mega_rows(a)
    if mega:
        parts.append(dk.section("대형주", _folded(mega, "종목"), summary="평소 범위 기준 크게 움직인 순", tab=TAB_MARKET,
                                aside=dk.tip_line([("읽는 법", sx.mega_tip(a))], in_title=True)))
    breadth = sec_breadth(analysis, prev)
    if breadth:
        parts.append(dk.section("시장 폭", breadth, tab=TAB_MARKET))
    change = sec_change(analysis, report, prev)
    if change:
        parts.append(dk.section("달라진 것", change, tab=TAB_MARKET))
    sectors = sec_sectors(analysis, report)
    if sectors:
        parts.append(dk.section("섹터", sectors, summary="1일 등락률", tab=TAB_MARKET))
    parts.append(dk.section("금리·지표", sec_macro(input_data.get("macro", {}), analysis, report), tab=TAB_MARKET))
    if a.get("calendar"):
        parts.append(dk.section(TAB_CAL, cards.cards_grid(sx.macro_cal_card(a) + sx.earnings_cal_card(a)), tab=TAB_CAL))
    parts.append(dk.WRAP_CLOSE)   # 출처 · 면책 꼬리말 없음 — 블로그 공통 푸터가 맡는다 (2026-10-18 사용자: 중복 안내 금지, 가이드라인 6절)
    # ":" 앞뒤 띄우기 (2026-10-11 사용자: 모든 페이지) · 반말 문장 끝은 합니다체 (2026-10-18 사용자: 블로그 기본 문체, 데일리는 재작업 때 일괄 — 지금)
    return dk.formal(dk.fix_colons(dk.align_titles("\n".join(p for p in parts if p))))   # 카드 밖 제목을 좌측 기준선(ALIGN_PX)으로 (2026-10-23 사용자)


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

    body = build_body(input_data, report, cover_url=cover_url, analysis=analysis, output_dir=output_dir)   # 템플릿 대신 코드로 (2026-10-11 디자인 가이드라인)

    body_path = os.path.join(output_dir, "report_body.html")
    preview_path = os.path.join(output_dir, "report.html")

    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW_WRAPPER.replace("__BODY__", body))

    title_path = os.path.join(output_dir, "title.txt")
    title = open(title_path, encoding="utf-8").read().strip() if os.path.exists(title_path) else "미국 증시 리포트"
    mock = dk.write_mock(body, os.path.join(output_dir, "daily_mock.html"), title)   # 테마 입힌 목업 (2026-10-11 사용자: 목업 화면 확인)
    if mock:
        print(f"목업 -> {mock}")
    print(f"HTML 렌더 완료 -> {body_path}")
    print(f"미리보기 완료 -> {preview_path}")
    return body, body_path, preview_path


if __name__ == "__main__":
    # CI 는 작업 폴더에 입력이 있다. 로컬에서 목업만 다시 만들 때는 output/ 의 지난 입력을 쓴다 (python render_html.py)
    base = "" if os.path.exists("report_input.json") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    render(os.path.join(base, "report_input.json"), os.path.join(base, "report.out.json"),
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "output") if base else "output", analysis_path=os.path.join(base, "analysis.json"))