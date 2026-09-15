"""라벨 정규화 — subtopic 표기 통일.

Gemini는 자유 서술 subtopic을 돌려주므로 "Tariff"/"Tariffs"/"tariff"가 따로 집계된다.
쓰는 쪽(classify)과 읽는 쪽(cluster) 양쪽에서 같은 함수를 거치게 해 기존 행도 함께 고친다.
"""

import re

import config


def normalize_subtopic(text):
    if not text or not isinstance(text, str):
        return ""
    s = re.sub(r"\s+", " ", text.strip().strip(".,;:!?\"'"))
    if not s:
        return ""
    key = s.lower()
    if key in config.SUBTOPIC_ALIASES:
        return config.SUBTOPIC_ALIASES[key]
    # 단순 복수형: 앨리어스 표의 값 중 단수형이 있으면 그걸 쓴다
    if key.endswith("s") and key[:-1] in config.SUBTOPIC_ALIASES:
        return config.SUBTOPIC_ALIASES[key[:-1]]
    return s.title() if s.islower() or s.isupper() else s
