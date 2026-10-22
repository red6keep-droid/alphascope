"""리포트 검증

1. 수집 데이터(sanity): 지수/경제지표가 존재해야 한다.
2. Gemini 출력(구조): 필수 키 존재, 뉴스 index가 수집 뉴스 목록 범위 안인지 확인.
실패하면 프로세스 종료(exit 1) → 게시 단계로 진행하지 않는다.
"""

import json
import os
import re
import sys

# 2026-10-18 재설계: 시장 상태 점수 해설(regime_*) · 급등주 · 관심 종목 · 위험요인 칸을 뺐다 (doc/데일리-리포트-기획.md 5절 B5 · B6)
REQUIRED_LLM_KEYS = ["one_line", "summary", "change_comment", "sector_comment", "news",
                     "macro_comment", "opinion", "image_prompt"]

ONE_LINE_MAX_LEN = 80   # 원인 하나 한 문장 (2026-10-18 재설계 — 지수 등락 · 평소 범위는 맨 앞 요약이 말한다)

# 프롬프트 규칙 10 · render_html.THEME_VOCAB 과 같은 목록
THEME_VOCAB = {"금리", "AI/반도체", "실적", "매크로", "에너지", "정책/규제", "지정학", "기타"}

IMAGE_PROMPT_MAX_LEN = 300

REQUIRED_MACRO = ["unemployment_rate", "cpi", "vix"]
# 러셀 2000 은 yfinance 예비(FRED)에 없어 막힌 날 못 채운다 — 빠져도 글은 나가게 경고로 내렸다 (2026-10-21, 운영지침 D6-1)
REQUIRED_INDICES = ["sp500", "nasdaq", "dow", "vix"]
OPTIONAL_INDICES = ["russell"]


def _is_bad(val):
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    return False


def validate(input_path, output_path, analysis_path=None):
    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    with open(output_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    errors = []
    warnings = []

    # 분석은 있으면 좋고 없어도 리포트는 나간다. 있는데 핵심이 비면 렌더가 '—'로 채우니 경고만.
    analysis = {}
    if analysis_path and os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
        if analysis.get("date") != input_data.get("date"):
            warnings.append(f"analysis.json 날짜({analysis.get('date')})가 수집 날짜({input_data.get('date')})와 다릅니다.")
        if not (analysis.get("series") or {}).get("^GSPC"):
            warnings.append("analysis.series에 ^GSPC가 없어 지수 표의 5D/20D가 비게 됩니다.")
        if analysis.get("history_stale"):
            warnings.append(f"시계열에 오늘 바가 없는 것으로 보입니다 (당일가 대비 {analysis.get('history_gap_pct')}%).")
    else:
        warnings.append("analysis.json 없음 — 지수 표 3열, '무엇이 달라졌나' 생략.")

    macro = input_data.get("macro", {})
    for key in REQUIRED_MACRO:
        if _is_bad(macro.get(key)):
            errors.append(f"매크로 데이터 누락: {key}")
    subs = [f"{k}({(v or {}).get('source')}, {(v or {}).get('date')})" for k, v in macro.items() if (v or {}).get("source")]
    if subs:
        warnings.append(f"FRED 대신 예비 값으로 채운 지표: {', '.join(subs)}")

    indices = input_data.get("market", {}).get("indices", {})
    for key in REQUIRED_INDICES:
        rec = indices.get(key) or {}
        if rec.get("price") is None:
            errors.append(f"지수 데이터 누락: {key}")
    for key in OPTIONAL_INDICES:
        if ((indices.get(key) or {}).get("price")) is None:
            warnings.append(f"지수 데이터 누락 (선택): {key} — 표에서 '—' 로 나갑니다.")
    fb = [k for k, v in indices.items() if (v or {}).get("source") == "FRED"]
    if fb:
        warnings.append(f"yfinance 대신 FRED 종가로 채운 지수: {', '.join(fb)} (하루 늦을 수 있음)")

    for key in REQUIRED_LLM_KEYS:
        if key not in report or _is_bad(report.get(key)):
            errors.append(f"Gemini 출력 필수 키 누락: {key}")

    # 점수 · 등급 말투가 남았는지 — 지시문 규칙 9. 게시를 막지는 않는다
    for k in ("one_line", "opinion", "summary"):
        if any(w in str(report.get(k) or "") for w in ("위험 선호", "위험 회피", "Risk-On", "Risk-Off")):
            warnings.append(f"{k} 에 시장 등급 말투가 있습니다 (규칙 9).")
        if any(w in str(report.get(k) or "") for w in ("지지선", "저항선", "저점 시험", "돌파", "급등했", "폭등")):
            warnings.append(f"{k} 에 차트 해석 · 과장 말투가 있습니다 (규칙 9).")

    # 칸끼리 같은 말 되풀이 — 한 줄 결론과 종합이 같은 낱말을 많이 나누면 경고 (2026-10-18 사용자: 홈 카드 요약이 같은 말 반복)
    def _words(t):
        return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", str(t or "")) if len(w) >= 2}
    a_, b_ = _words(report.get("one_line")), _words(report.get("opinion"))
    if a_ and b_ and len(a_ & b_) / max(1, min(len(a_), len(b_))) >= 0.5:
        warnings.append(f"one_line 과 opinion 이 같은 말을 되풀이합니다 (겹치는 낱말 {sorted(a_ & b_)[:8]}).")
    for k in ("one_line", "opinion", "summary"):
        if "평소 범위" in str(report.get(k) or "") or "평소 하루" in str(report.get(k) or ""):
            warnings.append(f"{k} 에 '평소 범위' 이야기가 있습니다 — 맨 앞 요약 · 카드와 겹칩니다.")

    one_line = str(report.get("one_line") or "")
    if len(one_line) > ONE_LINE_MAX_LEN:
        warnings.append(f"one_line {len(one_line)}자 (권장 {ONE_LINE_MAX_LEN}자 이내)")

    image_prompt = str(report.get("image_prompt") or "")
    if image_prompt and len(image_prompt) > IMAGE_PROMPT_MAX_LEN:
        errors.append(
            f"image_prompt 길이 초과: {len(image_prompt)}자 (최대 {IMAGE_PROMPT_MAX_LEN}자)"
        )

    # 뉴스의 theme·related는 렌더가 같은 규칙으로 걸러내므로 여기서는 경고만 남긴다.
    # 어휘 밖 테마는 '기타'로, 모르는 심볼은 빠진다 — 게시를 막을 일은 아니다.
    known_symbols = set(analysis.get("symbols") or [])

    news_size = len(input_data.get("news", []))
    for i, item in enumerate(report.get("news", [])):
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < news_size):
            errors.append(
                f"news[{i}] index({idx}) 유효하지 않음 (유효 범위 0~{news_size - 1})"
            )
        if not str(item.get("title_ko") or "").strip():
            warnings.append(f"news[{i}] title_ko 없음 — 원문(영어) 제목으로 렌더됩니다.")
        theme = item.get("theme")
        if theme is None:
            warnings.append(f"news[{i}] theme 없음 — 태그 없이 렌더됩니다.")
        elif theme not in THEME_VOCAB:
            warnings.append(f"news[{i}] theme '{theme}' 어휘 밖 — '기타'로 표기됩니다.")
        related = item.get("related")
        if related is not None and not isinstance(related, list):
            warnings.append(f"news[{i}] related가 배열이 아님 — 무시됩니다.")
        elif related:
            unknown = [s for s in related if s not in known_symbols]
            if unknown:
                warnings.append(f"news[{i}] related에 목록 밖 심볼 {unknown} — 제외됩니다.")

    if report.get("news"):
        selected = len(report["news"])
        if not (3 <= selected <= 5):
            warnings.append(f"선정 뉴스 수 {selected} (권장: 3~5)")

    for w in warnings:
        print(f"[경고] {w}")

    if errors:
        print("[검증 실패] 아래 항목 때문에 게시를 중단합니다.")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("[검증 통과] 구조/수치 확인 완료")
    return report


if __name__ == "__main__":
    validate("report_input.json", "report.out.json", analysis_path="analysis.json")