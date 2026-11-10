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
import people_section  # noqa: E402  — 인물 발언 구획 (2026-11-07 사용자, 목업)

dk.TIP_SRC = "Yahoo Finance"   # 툴팁 기본 데이터 출처. 금리 · 경제 일정이 들어간 툴팁만 with_src (2026-10-20 사용자)
import cards  # noqa: E402  — 질문 카드 · 막대 그래프 (2026-10-18 재설계)
import sections as sx  # noqa: E402  — 독자 질문 D1 ~ D6 · K1 ~ K3 구획 (doc/기획/데일리-리포트-기획.md 6절)
import market as mk  # noqa: E402  — 시장 탭 질문 카드 8개 (2026-11-07 사용자: 시장 탭도 질문 · 답 형태로)
import datetime  # noqa: E402
import media_feed  # noqa: E402  — 방송 줄 (미디어 데일리 재료의 시장 · 업종 이슈, 2026-10-25 사용자)
import kr_news  # noqa: E402  — 한국장 탭 `한국장에 영향을 줄 만한 소식` (미디어 데일리 뒤에 이 칸만 갱신)
import news_pick  # noqa: E402  — 뉴스 묶기 · 꼭 볼 뉴스 · 팝업 재료 (2026-11-05 batch 8)

MEDIA_SHOWN = 5    # 뉴스 구획 끝의 방송 줄 — 앞 5건만 펼쳐 두고 나머지는 `방송 n건 더 보기` 접기 (2026-10-30 사용자: 상한 없이 다 싣는다. 옛 MEDIA_MAX=3 은 미디어 데일리가 나머지를 들던 때 숫자)
MEDIA_HOURS = 48   # 글을 만드는 시각 기준 최근 48시간 영상 (2026-10-30 사용자, 옛 24)
NEW_LEAD = dk.NEW_PILL.replace("margin-left:4px;", "margin-right:5px;").replace("vertical-align:middle;", "vertical-align:middle;position:relative;top:-2px;")   # 제목 글자와 세로 가운데 (2026-11-07 사용자 P347: 아래로 치우침)   # 새 뉴스 N 은 제목 앞에 (2026-11-05 사용자)
STORY_SHOWN = 5    # `여러 방송이 같이 다룬 뉴스는?` 카드에 보이는 묶음 수 (2026-11-05 batch 8 ③)
CHART_MAIN = getattr(dk, "CHART_MAIN", "#F5B971")   # 우리 그래프 기본색(주황 · 사용자가 노랑이라 부르는 색) · 비교 대상 회색 — 가이드라인 8-0 (⑨)
CHART_CMP = getattr(dk, "CHART_CMP", "#CBD5E1")
_media_cache = None
_rows_cache = None


def _media_rows():
    global _rows_cache
    if _rows_cache is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        _rows_cache = media_feed.rows(media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=8))   # 목록 48시간 + 한국장 방향 막대 `최근 7일` (P143) — edition 여드레
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
THEME_VOCAB = ["금리", "AI/반도체", "실적", "거시경제", "에너지", "정책/규제", "지정학", "기타"]   # `매크로` → `거시경제` (2026-11-05 사용자 batch 9 ⑦: 영어 그대로는 어렵다 — 공용 어휘 news_store.THEME · media_feed.THEME 도 같이)

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
TAB_KOREA, TAB_CAL, TAB_NEWS, TAB_PEOPLE = "한국장", "일정", "뉴스", "인물 발언"   # 인물 발언 = 뉴스 옆 탭 (2026-11-07 사용자 P365)   # 2026-10-18 재설계: 오늘 · 한국장 · 시장 · 일정 (종목 · 뉴스 · 위험 탭은 없앰 — 기획 6절)

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
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{ZOOM_ICON}</span></a>'
            + dk.tv_chart_fold("AMEX:SPY", "America/New_York", "SPY"))   # 장중 차트 접힘 줄 — 종목 페이지 · 한국 증시 리포트와 같은 자리 · 같은 버튼, 미국 정규장에만 보임 (2026-11-07 사용자). S&P 500 지수 대신 따라가는 ETF(SPY) — 무료 위젯이 지수 자료를 막는 경우가 있다


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


def _text_flow(text):
    """한 문단으로 이어 쓰기 — 문단 · 문장 나눔 없이 PC · 모바일 같게, 줄바꿈은 띄어쓰기에서만 (2026-11-07 사용자 P391: 오늘 탭 지수 해설).
    data-sent 를 달지 않는다(테마 CSS 가 PC 에서 문장마다 줄을 바꾸는 표시)."""
    sents = [x for p in _paragraphs(text) for x in p]
    if not sents:
        return ""
    return (f'<div style="margin:0 0 6px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;">'
            + " ".join(dk.tint(_esc(dk.ko(x, TERM_KO))) for x in sents) + "</div>")


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
# 툴팁 글은 뜻 · 오늘(+ 참고) — 기록상 줄은 2026-11-01 폐지 (디자인-가이드라인.md 2-6, 2026-10-18 사용자: "툴팁은 어려운 용어를 쉽게 전달하는 것인데 숫자만 나열돼 있다").
# 오늘 값을 읽어 줘야 하므로 툴팁은 상수가 아니라 데이터를 받는 함수. 이 리포트의 지표는 아직 우리 검증 결과가 없어 `기록상` 줄은 두지 않는다.
# 등급 경계는 analyze.py 와 같아야 한다 — 시장 상태 70 · 45 (REGIME_RISK_ON · OFF), 상승 비율 65 · 45 (breadth_proxy), 위험 신호는 status_board.
REGIME_GRADE_NOW = {   # 점수 카드 툴팁의 오늘 줄 — 등급의 뜻 (옛 GRADE_MEANING, 2026-10-12 사용자)
    "위험 선호": "위험 선호 구간. 투자자들이 위험을 감수하고 주식 쪽으로 움직이기 쉬운 환경",
    "중립": "중립 구간. 위험 선호와 위험 회피 어느 쪽으로도 크게 기울지 않았다",
    "위험 회피": "위험 회피 구간. 투자자들이 위험을 피해 안전한 자산 쪽으로 움직이기 쉬운 환경",
}
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


def _light_pill(light, text=None):
    kind = LIGHT_KIND.get(light, "neutral")
    return dk.pill(text or _light_word(light) or "—", kind).replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 {dk.PILL_GAP + 5}px 0 {dk.PILL_GAP}px;", 1)   # 등급 라벨 오른쪽 +5 (2026-10-13 사용자)




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
    html = dk.bold_pct(dk._tint_inline(_esc(" ".join(sents))))   # 증감 숫자 굵게 (2026-11-07 사용자 P390)
    html = re.sub(r"(평소의 [0-9.]+배)", r'<span style="font-weight:700;">\1</span>', html)   # 배수 굵게 — `범위를 벗어났습니다` 는 굵게 하지 않는다 (같은 날 사용자 정정)
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">' + html + "</p>"   # 요약 문장의 증감도 색 (가이드라인 3-3-1, 예외 없음) — 문장이라 숫자(와 앞 지수 이름)만 칠한다. dk.tint 는 가운뎃점 덩어리 통째로 칠해 문장 앞머리까지 파랗게 된다


def sec_lead(report, analysis):
    """글 머리(제목 없음, data-lead): 한 줄 결론 + 종합을 한 강조 카드에 (2026-10-12 사용자: 하나의 카드로 통합, 가로 구분선, 16px).
    홈 카드는 '(머리)'로 한 줄 결론을 읽는다."""
    one = str(report.get("one_line") or "").strip()
    inner = f'<div style="color:#111;font-weight:700;padding-left:{dk.ALIGN_PX}px;">{_esc(dk.ko(one, TERM_KO))}</div>' if one else dk.muted("한 줄 결론 없음")   # 카드 대신 굵게 (2026-10-13 사용자)
    # 구분선 아래 종합(Gemini opinion, data-insight)은 뺐다 — `최근 며칠 · 몇 주와 비교` 는 시장 탭 `지금 시장 흐름은?` 과 겹친다 (2026-11-07 사용자). 홈 카드는 10-20부터 한 줄만 읽는다
    return dk.cards(f'<div style="margin:16px 0 8px;line-height:{dk.LH_BODY};">{inner}</div>')   # 지수 표 아래로 옮김 — 위 여백 16 (2026-11-07 사용자 순서: 그래프 → 지수 표 → 한 줄 결론)   # 오늘 탭 첫 콘텐츠 위 +10 (2026-10-13 사용자)   # 강조 카드 디자인 삭제 — 배경 · 테두리 · 안쪽 여백 없음 (2026-10-13 사용자)


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


INDEX_SHOWN = 1   # S&P 500 만 보이고 나머지는 펼침 (2026-11-07 사용자, 옛 2 = S&P 500 · 나스닥)


IDX_CELL_W = 190     # 칸 폭 — `5일 -3.37% · 20일 -10.18%` 한 줄이 들어가는 폭(Chrome 360px 실측). 360px 화면에서 둘째 칸(나스닥)이 화면 끝에 잘려 넘겨 보기가 있다는 게 보인다
IDX_PAD_R = 20      # 칸 오른쪽 여백(내용 ~ 구분선) — 왼쪽 12 보다 넓게 (2026-11-08 사용자 P416). 칸은 내용만큼 넓어진다(옛 고정 190 에 러셀 2000 이 넘쳤다)
IDX_BLEED = 14       # 글 좌우 여백(폰) — 넘겨 보기 줄은 오른쪽 화면 끝까지 (2026-11-08 사용자 P408: "화면 밖으로 걸쳐지게")


def _idx_cell(key, rec, s):
    """지수 한 칸 — 이름(괄호 작게) · `가격 ▲ 등락` 한 줄 · 아래 작은 회색 `5일 · 20일` 한 줄 · 최근 5일 (2026-11-08 사용자 P399 · P408)."""
    sub = []
    if s.get("ret_5d") is not None:
        sub.append(f"5일 {s['ret_5d']:+.2f}%")
    if s.get("ret_20d") is not None:
        sub.append(f"20일 {s['ret_20d']:+.2f}%")
    lines = []
    if sub:
        lines.append(dk.tint(" · ".join(sub)))   # 덩어리마다 증감 색
    if s.get("last5"):
        lines.append("최근 5일 " + _arrows(s["last5"]))
    sub_html = "".join(f'<span style="display:block;white-space:nowrap;">{x}</span>' for x in lines)
    bg = "#fff"   # 칸 배경 흰색 — 방향 색 배경 없앰 (2026-11-08 사용자, 옛 CARD_DIR 방향 배경)
    return (f'<span data-idx-cell="1" style="display:block;flex:0 0 auto;min-width:{IDX_CELL_W}px;box-sizing:border-box;background:{bg};padding:{14 - dk.VP}px {IDX_PAD_R}px {14 - dk.VP}px 12px;">'
            f'<span style="display:block;font-weight:700;color:#111;font-size:{dk.NAME};line-height:{dk.LH_CARD};white-space:nowrap;">{dk.paren(_esc(INDEX_LABELS.get(key, key)))}</span>'
            f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{dk.NAME};color:#111;">{_esc(_fmt_price(rec.get("price")))}</span> '
            f'<span style="font-size:{dk.CHG_SIZE};">{dk.small_chg(dk.arrow(rec.get("change_pct")))}</span></span>'
            f'<span style="display:block;margin-top:6px;font-size:13px;line-height:19px;color:{dk.SUB};">{sub_html}</span></span>')


def sec_indices(indices, analysis, report, with_text=True):
    """주요 지수 — 칸 4개(S&P 500 · 나스닥 · 다우존스 · 러셀 2000)를 가로로 넘겨 보는 줄 (2026-11-08 사용자 P408, 옛 P399 2열 + `지수 2개 더 보기`).
    순서 = 탭 줄처럼 왼쪽부터, 넘기면 오른쪽 칸이 나온다. 줄은 오른쪽 화면 끝까지 걸쳐 둘째 칸이 잘려 보인다 — 넘겨 보기가 있다는 표시.
    칸 = 이름 · 가격 ▲ 등락 · 5일 · 20일 · 최근 5일. VIX 줄 · 20일 위치는 뺐다 — 분위기 카드가 말한다 (2026-11-07 사용자: 오늘 = 그날 기록만)."""
    series = (analysis or {}).get("series") or {}
    cells, themes = [], []
    for key in ("sp500", "nasdaq", "dow", "russell"):
        rec = indices.get(key) or {}
        if rec.get("price") is None and rec.get("change_pct") is None:
            continue
        cells.append(_idx_cell(key, rec, series.get(INDEX_SYMBOL[key]) or {}))
        themes.append("neutral")   # 테두리 · 구분선도 회색 하나로 — 흰 카드 (2026-11-08 사용자, 옛 칸마다 방향 색)
    if not cells:
        return _text(report.get("summary")) if with_text else ""
    # 가로로 긴 흰 카드 한 장 안에 칸 4개 · 칸 사이 세로 구분선만 (2026-11-08 사용자 P414, 옛 P408 칸마다 카드). 카드는 화면 오른쪽 밖으로 잘린다
    # 칸마다 강조 카드 모양 — 바깥선 = 그 방향 카드 테두리, 칸 사이 = 연한 구분선 (2026-11-08 사용자: 옛 회색 #E2E8F0 바깥선 · 구분선, 한국과 같게)
    row = (f'<div data-cards="1" data-idx-scroll="1" style="overflow-x:auto;margin:0 -{IDX_BLEED}px 8px 0;padding:0 {IDX_BLEED}px 0 0;'
           f'-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
           f'<span style="display:flex;width:max-content;border-radius:8px;overflow:hidden;">{dk.dir_cells(cells, themes)}</span></div>')
    return (_text(report.get("summary")) if with_text else "") + row


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


def _meter(n, total):
    """방송 n곳 / 전체 — 작은 네모 칸 (2026-11-05 batch 8 ③: "13곳 중 8곳"이 한눈에)."""
    return dk.channel_meter(n, total)   # 공용으로 옮김 (2026-11-07 P338)


def _kst(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        t = t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)
        return t.astimezone(media_feed.KST).strftime("%m.%d %H:%M")   # 모든 리포트 같은 `01.05 07:07` — 옛 lstrip("0") 은 `1.05` (2026-11-07 0-6)
    except ValueError:
        return ""


def _pop_lines(g, built):
    """팝업 글 줄 — 기사 = news_summary 다섯 줄, 방송 = 수집기 lines(batch 9 ⑧). 둘 다 없으면 요약 줄 하나."""
    rep = g["rep"]
    lines = built["lines"].get(rep["id"]) if rep["kind"] == "article" else (rep.get("lines") or [])
    return [ln for ln in (lines or []) if ln] or ([rep["detail"]] if rep.get("detail") else [])


def _has_pop(g, built):
    """두 줄 이상 있을 때만 팝업 (batch 9 ④: 한 줄 팝업은 의미 없다 — 목록 보조 글씨로)."""
    return len(_pop_lines(g, built)) >= 2


def _story_dir(g):
    """묶음의 방향 하나 — 막대(긍정 · 부정 · 불확실 · 중립)와 같은 네 단어 (2026-11-07 사용자 P335).
    긍정 · 부정이 같이 있거나, 그 둘 없이 불확실이 있으면 `불확실` · 한쪽만 있으면 그쪽 · 아무 방향도 없으면 `중립`."""
    ds = [x.get("market_dir") for x in g["items"]]
    pn = {d for d in ds if d in ("positive", "negative")}
    if len(pn) > 1 or (not pn and "uncertain" in ds):
        return "uncertain"
    return pn.pop() if pn else "neutral"


def _dir_pill(g):
    d = _story_dir(g)
    return dk.pill(dk.DIR_KO[d], d, bare=True)


def _story_row(g, built, first):
    """주요 뉴스 한 줄 (2026-11-05 사용자: `여러 방송이 같이 다룬 뉴스` 5줄과 주요 뉴스 5건이 같아 하나로) — 대표 기사 제목 · 보조 한 줄 · 사건 이름 + `n곳 / 전체` 칸 막대 · 시각 · 매체."""
    n_ch = built["n_channels_all"]
    rep = g["rep"]
    lines = _pop_lines(g, built)
    sub = lines[0] if lines else ""
    attrs = (f' data-news-pop="{_esc(g["id"])}"' if _has_pop(g, built) else "") + ' data-trhelp="skip"'
    head = dk.keep_tone(f'<a href="{_esc(rep.get("url") or "#")}" target="_blank" rel="noopener"{attrs} style="color:#111;font-weight:700;text-decoration:none;font-size:{dk.NEWS_TITLE_FS};line-height:{dk.NEWS_TITLE_LH};display:block;">'
                        f'{NEW_LEAD if g.get("new") else ""}{_esc(rep["text"])}</a>')   # 헤드라인은 합니다체로 바꾸지 않는다 (공용 카드와 같게)
    meta = f'<span style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{_kst(rep["published_at"])} · {_esc(rep["source"])}</span>'   # 메타 = `시각 · 매체` (0-6)
    count = (f'<span style="display:inline-flex;align-items:center;gap:6px;">{_meter(g["n_channels"], n_ch)}'
             f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#374151;"><b style="color:#111;">{g["n_channels"]}곳</b> / {n_ch}곳</span></span>') if g["n_channels"] >= 2 else ""
    return (head + (dk.keep_tone(f'<span style="{dk.NEWS_SUM}">{dk.speaker_html(sub, tail=False)}</span>') if sub else "")   # 목록 줄은 발언자 없이 — 팝업에서만 (P364)
            + f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 0;line-height:1;">'
            + dk.pill_row(dk.pill(g["theme"], bare=True) + " " + _dir_pill(g)) + "</span>"   # 분야 · 방향 (P335 · P336)
            + f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 1px;line-height:1;">{count}{meta}</span>')   # 다음 줄 = 곳 수 막대 + 시각 · 매체 (2026-11-07 사용자 P348)


def _sub_title(t, note, tip_html="", line=False):
    """뉴스 안 소제목. line=True: 안내 글 대신 아래 가로 구분선 (2026-11-05 사용자: `여러 방송이 같이 다룬 뉴스`) — 첫 줄 위 구분선은 이 선이 대신한다."""
    rule = f"padding-bottom:8px;border-bottom:1px solid #E2E8F0;margin:24px 0 0;" if line else "margin:24px 0 2px;"
    return (f'<h3 style="display:flex;align-items:center;flex-wrap:wrap;gap:2px 6px;font-size:{dk.NEWS_TITLE_FS};line-height:26px;font-weight:700;color:#111;{rule}padding-left:{dk.ALIGN_PX}px;position:relative;">'
            f'{_esc(t)}{tip_html}' + (f'<span style="font-weight:400;color:{dk.SUB};font-size:{dk.TINY};">{_esc(note)}</span>' if note else "") + "</h3>")


def _news_pop_body(g, built):
    """팝업 글 (숨긴 div, 테마 JS 가 화면 가운데 창에 옮긴다): 요약 줄 → 관련 종목 → 작은 `원문 보기`. 머리 줄 · `같은 뉴스` 칸 삭제 (2026-11-07 사용자 P352 · P354) — 공용 dk.news_pop_body."""
    rep = g["rep"]
    sx = built["stocks"]
    related, seen = [], set()
    for s in [t for x in g["items"] for t in (x.get("related") or [])]:
        if s in seen or len(related) >= 6:
            continue
        v = (built["series"].get(s) or {}).get("ret_1d")
        if v is None and s in sx and sx[s].get("cp") is not None:
            v = sx[s]["cp"]
        if v is None:
            continue
        seen.add(s)
        related.append(((built.get("names") or {}).get(s) or SYMBOL_NAMES.get(s) or (sx.get(s) or {}).get("name") or s, v))   # names = 한국 리포트 종목 이름 (M82)
    kind = "기사" if rep["kind"] == "article" else "방송"
    return dk.news_pop_body(g["id"], rep["text"], _pop_lines(g, built), source=rep["source"], kind=kind, url=rep.get("url"), related=related)


def _story_item(g, built, reaction, known, compact=False):
    """목록 한 줄 = 묶음의 대표 (공용 뉴스 카드) — 두 줄 이상 있으면 팝업, 아니면 원문 링크 + 보조 글씨 한 줄 (batch 9 ④). 라벨 = 분야 · `n곳` · N."""
    rep = g["rep"]
    related = [s for x in g["items"] for s in (x.get("related") or []) if s in known][:4]
    subs = []
    if related and not compact:
        subs.append(f'<span style="display:block;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;"><span style="font-size:{NEWS_REL_SIZE};font-weight:700;">관련 자산 : '
                    + " · ".join(_named_reaction(s, reaction(s)) for s in dict.fromkeys(related)) + "</span></span>")
    labels = dk.pill(g["theme"], bare=True) + " " + _dir_pill(g)
    count = dk.channel_count(g["n_channels"], built["n_channels_all"]) if g["n_channels"] >= 2 else ""   # 곳 수 막대 — 라벨 다음 줄, 시각 · 매체 앞 (P338 · P348)
    meta = [_kst(rep["published_at"]), rep["source"]]   # `시각 · 매체` — 종목 페이지와 같게 (2026-11-07 0-6, 옛 ` 기사` · ` 방송` 꼬리)
    head = (NEW_LEAD if g.get("new") else "") + _esc(rep["text"])
    pop = _has_pop(g, built)
    lines = _pop_lines(g, built)
    detail = "" if (compact and pop) else (lines[0] if lines else "")   # 팝업 없는 줄은 보조 글씨 한 줄 (④), 주요 뉴스는 늘 보조 줄
    attrs = (f' data-news-pop="{_esc(g["id"])}"' if pop else "") + ' data-trhelp="skip"'
    return dk.news_item(head, rep.get("url") or "#", detail, subs, labels, meta, attrs, count_html=count)


def news_tip():
    """구획 제목 `뉴스` 옆 읽는 법 ? (2026-11-05 사용자: 툴팁은 뉴스 타이틀 옆에)."""
    return ("주요 뉴스 = 우리 데이터로 매긴 점수 순 5건입니다. AI 가 고르지 않습니다.\n· 다룬 방송 수 = 두 곳 이상이면 한 곳마다 2점\n· 관련 자산의 그날 움직임 = 1% 마다 1점 (4점까지)\n"
            "· 예상 밖 표시 = 2점\n· 시장에 좋거나 나쁜 방향이 있는 뉴스 = 1점\n· 최근 12시간 안 = 1점\n"
            "분야 칩을 누르면 그 분야 뉴스가 최신 순으로 나옵니다. 같은 사건을 다룬 기사 · 방송은 한 줄로 묶고 몇 곳이 다뤘는지(n곳) 적습니다.\n"
            "줄을 누르면 요약이 뜹니다. 요약이 두 줄이 안 되는 뉴스는 싣지 않습니다. N = 지난 글 뒤에 새로 나온 뉴스.")


def sec_news(input_data, report, analysis):
    """뉴스 (2026-11-05 batch 8 · 9 재설계) — 방향 막대 / `여러 방송이 같이 다룬 뉴스` 5줄 / `뉴스`(칩: 주요 뉴스 먼저 · 분야).
    기사(CNBC 48시간) · 유튜브 방송 주제(48시간)를 news_stories 가 같은 사건끼리 묶고(news_pick.build), 같은 뉴스는 한 줄 + `n곳`. 두 줄 이상 있는 줄은 팝업(요약 · 원문 작은 링크).
    옛 `방송 n건 더 보기`(111건) 는 없앴다 — 독자가 볼 수 없는 목록이었다 (사용자)."""
    series = (analysis or {}).get("series") or {}
    rates = (analysis or {}).get("rates") or {}
    quotes = {q["symbol"]: q for q in input_data.get("gainers", []) + input_data.get("most_active", []) if q.get("symbol")}
    known = set(series) | set(quotes)

    def reaction(sym):
        if sym == "^TNX" and rates.get("us10y_change_1d_bp") is not None:
            return dk.arrow(rates["us10y_change_1d_bp"] / 100, 2, "%p")   # bp 는 약어 금지(가이드라인 11절) — %p 로 (2026-11-07)
        if sym in series:
            return dk.arrow(series[sym].get("ret_1d"))
        return dk.arrow(quotes[sym].get("change_pct"))

    media = _media_lines()
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=MEDIA_HOURS)).strftime("%Y-%m-%dT%H:%M")
    built = news_pick.build(input_data, analysis, media, all_channels={r["channel"] for r in _media_rows() if str(r["published_at"])[:16] >= cut})
    if not built["stories"]:
        return dk.muted("주요 뉴스 없음")
    dirs = {}
    for n in input_data.get("news") or []:
        if n.get("market_dir"):
            dirs[n["market_dir"]] = dirs.get(n["market_dir"], 0) + 1
    for k, v in media_feed.direction_counts(media).items():
        dirs[k] = dirs.get(k, 0) + v
    week = dict(dirs)   # 최근 7일 = 오늘 기사(CNBC 는 48시간만 받는다) + 방송 이슈 7일 (2026-11-07 사용자: 종목 페이지처럼 오늘 · 최근 7일 막대 두 개)
    since7 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
    for k, v in media_feed.direction_counts(media_feed.market_top(media_feed.issues(_media_rows(), since7), None)).items():
        week[k] = week.get(k, 0) - media_feed.direction_counts(media).get(k, 0) + v
    return news_tab(built, dirs, week, reaction, known)


def news_tab(built, dirs, week, reaction=None, known=()):
    """뉴스 탭 내용 — 분야 칩 · 방향 막대 · 주요 뉴스 · 칩별 목록 · 팝업. 미국 증시 · 한국 증시 리포트 공용 (2026-11-07 사용자 M82: 한국 뉴스 탭을 미국과 같게)."""
    reaction = reaction or (lambda s: "")
    bars = dk.direction_bars(dirs, week)   # 뉴스 방향 막대 오늘 · 최근 7일 (P143 의 `오늘` 만 → 둘, 2026-11-07) — 분야 탭 아래 (P334)
    out = ""
    # `유튜브 방송이 많이 다룬 분야는?` 카드 · `여러 방송이 같이 다룬 뉴스` 5줄은 뺐다 — 분야 칩이 많은 순이고 주요 뉴스 5건과 같았다 (2026-11-05 사용자). 막대 바로 아래 칩
    picks, rest = built["picks"], built["rest"]
    pops = []
    if picks or rest:
        chips = [("주요 뉴스", len(picks))] + news_pick.tab_order(picks, rest)   # 탭 = 8개 묶음(P357) · 순서 = 그날 주요 뉴스 순 → 건수 순(P358). `전체` 없음 (batch 9 ①)
        # 분야 탭 = 홈 `테마 종목` 묶음 탭 모양 (2026-11-07 사용자 P332): 하나로 이은 둥근 박스 · 메뉴 사이 세로 구분선 · 선택 = 굵은 검정 + 1px 검정 외곽선(테마 CSS).
        # 박스 테두리는 버튼들이 나눠 가진다(위 · 아래 + 첫 버튼 왼쪽 · 끝 버튼 오른쪽) — 가로로 밀면 박스째 움직인다 (P333). 위치 = 뉴스 탭 맨 위, 방향 막대는 그 아래 (P334)
        last = len(chips) - 1
        def chip_css(i):
            return (f"flex:1 0 auto;padding:6px 14px;margin:0;background:#fff;color:#4B5563;font:inherit;font-size:{dk.TINY};line-height:{dk.LH_TINY};cursor:pointer;white-space:nowrap;"
                    f"border:1px solid #E2E8F0;{'border-left:0;' if i else ''}border-radius:{'7px' if i == 0 else '0'} {'7px' if i == last else '0'} {'7px' if i == last else '0'} {'7px' if i == 0 else '0'};")
        out += (f'<div data-news-chips="1" style="display:flex;overflow-x:auto;margin:0 0 12px;padding:0;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
                + "".join(f'<button type="button" data-chip="{_esc(k)}" aria-pressed="{"true" if i == 0 else "false"}" style="{chip_css(i)}">{_esc(k)} <span style="color:{dk.SUB};">{n}</span></button>'
                          for i, (k, n) in enumerate(chips)) + "</div>")
        out += bars
        lis = []
        for i, g in enumerate(picks + rest):
            is_pick = i < len(picks)
            item = _story_row(g, built, i == 0) if is_pick else _story_item(g, built, reaction, known, compact=True)   # 주요 뉴스 = 사건 이름 + n곳 막대 줄
            pick_attr = ' data-pick="1"' if is_pick else " hidden"
            pick_attr += (f' data-news-pop="{_esc(g["id"])}"' if _has_pop(g, built) else f' data-row-link="1" data-href="{_esc(g["rep"].get("url") or "#")}"')   # 구분선 안 아무 데나 눌러도 팝업 · 원문 (2026-11-05 사용자, 가이드라인 10-9 줄 전체 링크)
            lis.append(f'<li data-theme="{_esc(news_pick.tab_of(g["theme"]))}"{pick_attr} style="margin:0;padding:{dk.RULE_GAP - dk.NEWS_VP}px {dk.ALIGN_PX}px {dk.RULE_GAP - dk.NEWS_VP}px;'
                       f'line-height:{dk.LH_BODY};box-shadow:inset 0 1px 0 #E2E8F0;">{item}</li>')   # 첫 줄 구분선은 테마 JS 가 지운다. 주요 뉴스 외는 숨김 — 칩이 켠다
            if _has_pop(g, built):
                pops.append(_news_pop_body(g, built))
        out += f'<ul data-news-list="1" data-shown="{news_pick.LIST_SHOWN}" style="margin:0 0 8px;padding:0;list-style:none;font-size:{dk.SMALL};">{"".join(lis)}</ul>'
        out += (f'<button type="button" data-news-more="1" style="{dk.FOLD_BTN}width:100%;margin:0 0 8px;display:none;">'
                f'<span>뉴스 더 보기</span> {dk.ACC_CHEV}</button>')   # 글자 · 보임은 테마 JS (분야 칩마다 LIST_SHOWN 넘는 만큼)
    else:
        out += bars
    out += "".join(pops)
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


KR_REPORT_URL = f"{mk.BLOG}/search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"   # 한국 증시 리포트 라벨 목록 (kr-stocks universe_kr.REPORT_URL 과 같다)
RELATED_LINKS = [("미국 시가총액 상위 10개 종목 주가", mk.US_LIST_URL), ("한국 증시 리포트", KR_REPORT_URL),
                 ("한국 시가총액 상위 10개 종목 주가", f"{mk.BLOG}/p/kr-market-cap-top10.html"),
                 ("주요 인물 발언 전체 보기", people_section.ALL_URL)]   # 함께 보는 페이지 (2026-11-08 사용자: 미국 증시 리포트에도, 인물 발언 전체 보기 포함)


def build_body(input_data, report, cover_url=None, analysis=None, output_dir=None):
    """2026-10-18 재설계 (doc/기획/데일리-리포트-기획.md 6절) — 탭 = 독자 질문 묶음.
    오늘(D1 · D2 · D3 · D6 + 옛 시장 탭 카드 8개, 2026-11-07 시장 탭 없앰) · 뉴스 · 인물 발언 · 한국장(K1 · K2 · K3) · 일정(D5). 시장 상태 점수 · 신호등 · 급등주 · 거래 상위 · 위험요인은 뺐다 (5절 B5 · B6).
    홈 카드 CARDS: summary = (머리), insight = (종합) — 머리 카드의 data-insight 그대로."""
    indices = input_data.get("market", {}).get("indices", {})
    prev = _prev_analysis(analysis)   # 어제 대비 (2026-10-13 사용자)
    a = analysis or {}
    parts = [
        dk.WRAP_OPEN,
        sec_seo_lead(input_data, analysis),   # 검색 결과 요약 — 보이는 첫 요소, data-lead 보다 앞 (2026-10-18)
        # S&P 500 그래프가 커버 이미지 자리 (2026-10-18 사용자, 엔비디아처럼). 그래프가 없는 날만 AI 커버
        sec_chart(output_dir) or _cover_image(cover_url),
        # 오늘 탭 머리 = 탭 줄 바로 아래 (2026-11-07 사용자: 한국 증시 리포트처럼, 구획 제목 · 그래프 제목 없이)
        #   시가 갭 · 장중 · 하루 막대 → 지수 표(S&P 500 + 지수 3개 더 보기) → 한 줄 결론(data-lead) → 지수 해설 문장. 테마는 첫 data-cards 부터 첫 h2 까지를 첫 탭에 넣는다
        sec_indices(indices, analysis, report, with_text=False),   # 넘겨 보기 지수 줄 = 오늘 탭 바로 아래, 그래프 위 (2026-11-08 사용자)
        sx.split_chart(a),
        sec_lead(report, analysis),
        _text_flow(report.get("summary")),   # 한 문단 이어 쓰기 (P391)
    ]
    # 오늘 탭 = 옛 시장 탭 카드까지 한 곳에 (2026-11-07 사용자: "시장 탭을 오늘 탭으로 다 옮기자" — 시장 탭은 없앰). 맨 첫 카드만 펼침
    # 세 덩어리 (같은 날 P384): ① 주요 지수 = 같은 지수를 근거로 쓰는 것(지수 값 → 평소와 달랐나 → 충격 → 흐름 → 기술주 · 소형주)
    #   ② 종목 · 업종 = 무엇이 움직였나(대형주 10개 → 업종 → 테마 → 고르게) ③ 시장 바탕(긴장 → 금리 → 경제)
    grid = lambda h: cards.cards_grid(h) if h else ""  # noqa: E731
    idx_cards = sx.shock_card(a) + mk.index_cards(a, prev)   # `오늘 움직임은 평소와 달랐나?` 는 `미국 증시 분위기는?` 안으로 (2026-11-07 사용자)   # 오늘 탭 카드는 모두 닫힌 채로 (2026-11-07 사용자, 옛 P216 첫 카드 펼침)
    parts.append(dk.section(TAB_TODAY, grid(idx_cards), tab=TAB_TODAY))   # 탭 이름과 같은 제목은 테마가 숨긴다 — `주요 지수` 제목 삭제 (2026-11-07 사용자), 지수 표 · 그래프는 탭 머리로
    move = mk.move_cards(a, prev)
    if move:
        parts.append(dk.section("종목 · 업종", grid(move), tab=TAB_TODAY))
    base = mk.base_cards(a, input_data.get("macro") or {}, input_data.get("cftc"))
    if base:
        parts.append(dk.section("시장 환경", grid(base), tab=TAB_TODAY))   # 옛 `시장 바탕` (2026-11-08 사용자 P404)
    parts += [
        # 뉴스 = 오늘 옆 탭 (2026-11-07 사용자: 오늘 탭이 너무 길다). 탭 이름과 같은 제목 `뉴스` 는 테마가 숨긴다. 읽는 법 툴팁 삭제 (같은 날)
        dk.keep_tone(dk.section("뉴스", sec_news(input_data, report, analysis), tab=TAB_NEWS)),   # 뉴스는 헤드라인체 그대로 (2026-10-18 사용자)
    ]
    people = people_section.for_market()   # 뉴스 탭 맨 아래 — 최근 24시간 시장 관련도 높은 인물 발언 3줄 (2026-11-07 사용자). 없으면 뺀다
    if people:
        parts.append(dk.keep_tone(dk.section(TAB_PEOPLE, people_section.summary_card(cards.question_card) + people, tab=TAB_PEOPLE)))   # 맨 위 질문 카드 3개 (P380, 옛 요약 상자 P376)   # `최근 24시간` 뺌 — 줄마다 시각 (P369)
    k_open = sx.korea_open_card(a)   # 한국장 탭 첫 카드는 펼친 채로 (2026-11-08 사용자) — 연결 카드가 없는 날(평소)은 `연결된 국내 종목은?` 이 첫 카드
    korea = k_open + sx.korea_pairs_card(a, opened=not k_open) + sx.fx_card(a)
    if korea:
        parts.append(dk.section(TAB_KOREA, cards.cards_grid(korea), tab=TAB_KOREA))   # 탭 이름과 같은 구획 제목은 테마가 탭 화면에서 숨긴다
    parts.append(kr_news.section(_media_rows()))   # 소식이 없어도 표시 주석은 남긴다 — 미디어 데일리 실행 뒤 kr_news.py 가 이 칸만 채운다 (2026-10-25)
    if a.get("calendar"):
        parts.append(dk.section(TAB_CAL, cards.cards_grid(sx.macro_cal_card(a) + sx.earnings_cal_card(a)), tab=TAB_CAL))
    parts.append(dk.related_buttons(RELATED_LINKS))   # 함께 보는 페이지 — 한국 증시 리포트와 같은 블록 · 주요 인물 발언 전체 보기 포함 (2026-11-08 사용자)
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