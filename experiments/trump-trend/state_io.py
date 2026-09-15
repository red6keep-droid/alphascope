"""GitHub Actions용 상태 내보내기·불러오기.

런너는 매번 빈 환경이다. 다시 만들 수 없는 것은 Gemini 분류 결과뿐이므로
(게시물은 archive에서, 가격·캘린더는 API에서, 이벤트·반응은 재계산) 그것만 JSONL로 남긴다.

    classifications.jsonl   한 줄 = 분류된 게시물 하나 (id + ai_* + analyzed_at + ai_model)

불러오기는 collect_posts 뒤에 돈다 — 행이 있어야 UPDATE 할 수 있다.
archive에서 사라진 게시물(삭제)의 분류는 DB에 못 붙지만, 내보낼 때 다시 이어 붙여 잃지 않는다.
"""

import json
import os

AI_FIELDS = [
    "ai_topic", "ai_subtopic", "ai_target_country", "ai_target_sector",
    "ai_mentioned_companies", "ai_direction", "ai_intensity", "ai_market_relevance",
    "analyzed_at", "ai_model",
]

_carry = []   # import 때 DB에 없던 행 — export 때 그대로 다시 쓴다


def import_state(conn, path):
    global _carry
    _carry = []
    if not path or not os.path.exists(path):
        print(f"[state] 불러올 파일 없음: {path} (첫 실행이면 정상)")
        return 0
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    existing = {r["id"] for r in conn.execute("SELECT id FROM trump_posts")}
    applied = []
    for r in rows:
        if r.get("id") in existing:
            applied.append(r)
        else:
            _carry.append(r)
    conn.executemany(
        """UPDATE trump_posts SET
             ai_topic=:ai_topic, ai_subtopic=:ai_subtopic,
             ai_target_country=:ai_target_country, ai_target_sector=:ai_target_sector,
             ai_mentioned_companies=:ai_mentioned_companies, ai_direction=:ai_direction,
             ai_intensity=:ai_intensity, ai_market_relevance=:ai_market_relevance,
             analyzed_at=:analyzed_at, ai_model=:ai_model
           WHERE id=:id AND analyzed_at IS NULL""",
        applied,
    )
    conn.commit()
    print(f"[state] 분류 결과 {len(rows):,}행 중 {len(applied):,}행 적용 · DB에 없는 게시물 {len(_carry):,}행은 보존")
    return len(applied)


def export_state(conn, path):
    rows = [dict(r) for r in conn.execute(
        f"SELECT id, {', '.join(AI_FIELDS)} FROM trump_posts WHERE analyzed_at IS NOT NULL ORDER BY id")]
    ids = {r["id"] for r in rows}
    rows += [r for r in _carry if r.get("id") not in ids]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[state] 분류 결과 {len(rows):,}행 → {path}")
    return len(rows)
