"""리포트 검증

1. 수집 데이터(sanity): 지수/경제지표가 존재해야 한다. 급등주·관심종목은 비어 있어도 되지만 경고.
2. Gemini 출력(구조): 필수 키 존재, 뉴스 index가 수집 뉴스 목록 범위 안인지 확인.
실패하면 프로세스 종료(exit 1) → 게시 단계로 진행하지 않는다.
"""

import json
import os
import sys

REQUIRED_LLM_KEYS = ["one_line", "regime_echo", "regime_comment", "summary", "change_comment",
                     "sector_comment", "gainers_comment", "attention_comment", "news",
                     "macro_comment", "opinion", "risk", "image_prompt"]

ONE_LINE_MAX_LEN = 120
REGIME_LABELS = {"Risk-On", "Neutral", "Risk-Off"}

# 프롬프트 규칙 10 · render_html.THEME_VOCAB 과 같은 목록
THEME_VOCAB = {"금리", "AI/반도체", "실적", "매크로", "에너지", "정책/규제", "지정학", "기타"}

IMAGE_PROMPT_MAX_LEN = 300

REQUIRED_MACRO = ["unemployment_rate", "cpi", "vix"]
REQUIRED_INDICES = ["sp500", "nasdaq", "dow", "russell", "vix"]


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

    indices = input_data.get("market", {}).get("indices", {})
    for key in REQUIRED_INDICES:
        rec = indices.get(key) or {}
        if rec.get("price") is None:
            errors.append(f"지수 데이터 누락: {key}")

    for section in ("gainers", "most_active"):
        if not input_data.get(section):
            warnings.append(f"{section} 목록이 비어 있어 '데이터 없음'으로 표기됩니다.")

    for key in REQUIRED_LLM_KEYS:
        if key not in report or _is_bad(report.get(key)):
            errors.append(f"Gemini 출력 필수 키 누락: {key}")

    # regime_echo — Gemini가 등급을 반대로 읽었는지 기계적으로 잡는 유일한 장치.
    # 파이썬이 만든 라벨과 글자 그대로 같아야 한다. 분석이 없는 날은 "데이터 없음"이어야 한다.
    echo = str(report.get("regime_echo") or "").strip()
    label = (analysis.get("regime") or {}).get("label")
    if label:
        if echo != label:
            errors.append(f"regime_echo '{echo}' ≠ 계산된 등급 '{label}' — Gemini가 시장 상태를 다르게 읽었습니다.")
        score = (analysis.get("regime") or {}).get("score")
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            errors.append(f"regime.score({score})가 0~100 밖입니다.")
    elif echo and echo in REGIME_LABELS:
        warnings.append(f"분석이 없는데 regime_echo가 '{echo}' — 렌더는 '데이터 없음'으로 나가지만 해설이 등급을 언급할 수 있습니다.")

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
    known_symbols |= {q["symbol"] for q in input_data.get("gainers", []) + input_data.get("most_active", [])
                      if q.get("symbol")}

    news_size = len(input_data.get("news", []))
    for i, item in enumerate(report.get("news", [])):
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < news_size):
            errors.append(
                f"news[{i}] index({idx}) 유효하지 않음 (유효 범위 0~{news_size - 1})"
            )
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