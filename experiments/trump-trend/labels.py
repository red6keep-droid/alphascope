"""라벨 정규화 — subtopic 표기 통일 + 결정적 보정 규칙.

Gemini는 자유 서술 subtopic을 돌려주므로 "Tariff"/"Tariffs"/"tariff"가 따로 집계된다.
쓰는 쪽(classify)과 읽는 쪽(cluster) 양쪽에서 같은 함수를 거치게 해 기존 행도 함께 고친다.

2026-10-07 추가 — 10월 7일 게시 글 검토에서 나온 라벨 오류를 규칙으로 막는다 (README "검증 기록").
  normalize_subtopic : " Rules"/" Standards"/" Policy" 같은 꼬리말을 떼고 동의어 표로 합친다.
                       "Fuel Economy Rules"와 "Fuel Economy Standards"가 다른 주제로 집계되던 문제.
  adjust             : 본문을 보고 Gemini 라벨을 결정적으로 보정한다. 두 가지뿐이다.
                       ① 기사 제목 + 링크만 올린 글은 강도 상한 (남의 헤드라인은 본인의 발표가 아니다)
                       ② 감사 인사로 시작하는 글은 관련성 상한 (정책 조치가 없다)
  reapply            : DB 전체 행에 위 둘을 다시 적용한다. 멱등이라 매 실행 돌려도 된다.
"""

import re

import config

_URL_RE = re.compile(r"https?://\S+")


def normalize_subtopic(text):
    if not text or not isinstance(text, str):
        return ""
    s = re.sub(r"\s+", " ", text.strip().strip(".,;:!?\"'"))
    if not s:
        return ""
    key = s.lower()
    # 꼬리말 제거: "Fuel Economy Rules" → "Fuel Economy", "AI Regulation" → "AI"
    for suffix in config.SUBTOPIC_STRIP_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            key = key[: -len(suffix)].rstrip()
            s = s[: len(key)].rstrip()
            break
    if key in config.SUBTOPIC_ALIASES:
        return config.SUBTOPIC_ALIASES[key]
    # 단순 복수형: 앨리어스 표의 값 중 단수형이 있으면 그걸 쓴다
    if key.endswith("s") and key[:-1] in config.SUBTOPIC_ALIASES:
        return config.SUBTOPIC_ALIASES[key[:-1]]
    return s.title() if s.islower() or s.isupper() else s


def is_link_post(text):
    """기사 제목 + URL만 올린 글. URL을 빼면 짧고, URL이 있다."""
    if not text or not _URL_RE.search(text):
        return False
    words = _URL_RE.sub("", text).split()
    return len(words) <= config.LINK_POST_MAX_WORDS


def is_gratitude_post(text):
    lowered = (text or "").lstrip().lower()
    return lowered.startswith(config.GRATITUDE_PREFIXES)


def adjust(labels, text):
    """labels: ai_intensity · ai_market_relevance · ai_subtopic 를 가진 dict (원본은 바꾸지 않는다).
    → (보정된 dict, 적용된 규칙 이름 리스트)"""
    out = dict(labels)
    reasons = []
    out["ai_subtopic"] = normalize_subtopic(out.get("ai_subtopic"))
    if out["ai_subtopic"] != (labels.get("ai_subtopic") or ""):
        reasons.append("subtopic")
    if is_link_post(text) and (out.get("ai_intensity") or 0) > config.LINK_POST_MAX_INTENSITY:
        out["ai_intensity"] = config.LINK_POST_MAX_INTENSITY
        reasons.append("link_intensity_cap")
    if is_gratitude_post(text) and (out.get("ai_market_relevance") or 0) > config.GRATITUDE_MAX_RELEVANCE:
        out["ai_market_relevance"] = config.GRATITUDE_MAX_RELEVANCE
        reasons.append("gratitude_relevance_cap")
    return out, reasons


def reapply(conn):
    """분류된 전체 행에 adjust를 다시 적용한다. 규칙을 바꾼 뒤에도 과거 행이 같은 기준을 따르게."""
    import prefilter  # 순환 import 방지 — prefilter는 config만 본다

    rows = conn.execute(
        "SELECT id, content, ai_subtopic, ai_intensity, ai_market_relevance FROM trump_posts "
        "WHERE analyzed_at IS NOT NULL"
    ).fetchall()
    changes = []
    counts = {}
    for r in rows:
        new, reasons = adjust(dict(r), prefilter.clean_text(r["content"]))
        if reasons:
            changes.append((new["ai_subtopic"], new["ai_intensity"], new["ai_market_relevance"], r["id"]))
            for k in reasons:
                counts[k] = counts.get(k, 0) + 1
    conn.executemany(
        "UPDATE trump_posts SET ai_subtopic = ?, ai_intensity = ?, ai_market_relevance = ? WHERE id = ?",
        changes,
    )
    conn.commit()
    detail = " · ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "변경 없음"
    print(f"[labels] 보정 규칙 재적용 — {len(rows):,}행 중 {len(changes):,}행 변경 ({detail})")
    return len(changes)
