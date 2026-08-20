"""리포트 검증

1. 수집 데이터(sanity): 지수/경제지표가 존재해야 한다. 급등주·관심종목은 비어 있어도 되지만 경고.
2. Gemini 출력(구조): 필수 키 존재, 뉴스 index가 수집 뉴스 목록 범위 안인지 확인.
실패하면 프로세스 종료(exit 1) → 게시 단계로 진행하지 않는다.
"""

import json
import os
import sys

REQUIRED_LLM_KEYS = ["summary", "market_mood", "gainers_comment",
                     "attention_comment", "news", "macro_comment",
                     "opinion", "risk"]

REQUIRED_MACRO = ["unemployment_rate", "cpi", "vix"]
REQUIRED_INDICES = ["sp500", "nasdaq", "dow", "russell", "vix"]


def _is_bad(val):
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    return False


def validate(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    with open(output_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    errors = []
    warnings = []

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

    news_size = len(input_data.get("news", []))
    for i, item in enumerate(report.get("news", [])):
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < news_size):
            errors.append(
                f"news[{i}] index({idx}) 유효하지 않음 (유효 범위 0~{news_size - 1})"
            )

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
    validate("report_input.json", "report.out.json")