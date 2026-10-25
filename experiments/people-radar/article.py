"""보도 발언의 기사 첫 문단 — 카드 요약이 제목을 되풀이하지 않게 (2026-10-25 사용자: "제목과 요약이 같은 말이다, 더 자세히").

2차(보도) 신호는 지금까지 기사 제목 한 줄만 서술 모델에 갔다 → 요약이 제목을 다시 쓴 문장이 됐다.
여기서 Google News 주소를 원래 기사 주소로 풀고(batchexecute), 기사의 설명(meta description) + 첫 문단 몇 개를 짧게 가져온다.
- 서술 모델 입력으로만 쓴다. 기사 문장을 화면에 옮기지 않는다 — 모델이 우리 말로 사실만 요약한다 (운영지침 4-3 · D3-1f)
- 저장: data/article_cache.json (주소 → {real, lead}) — 같은 기사를 다시 받지 않는다. 깃에 안 들어간다(data/)
- 유료 · 차단 · 자바스크립트 기사는 빈 값 → 요약은 제목만으로(또는 생략)
본체는 experiments/article_lead.py (공용 — 종목 페이지 기사 요약도 쓴다, 2026-10-25). 여기는 캐시 위치만 정한다.
"""

import os
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import article_lead  # noqa: E402

CACHE_PATH = os.path.join(config.DATA_DIR, "article_cache.json")
decode_gnews = article_lead.decode_gnews
lead_text = article_lead.lead_text


def leads(urls):
    """주소 목록 → {주소: 첫 문단} (캐시 data/article_cache.json)."""
    return article_lead.leads(urls, CACHE_PATH)
