"""SQLite 스키마와 연결. 모든 시각은 UTC ISO-8601 ("2026-10-19T03:54:14Z").

statements 한 행 = 수집된 글 하나 (1차: 본인 글 · 기관 발표 · 매매 공시 / 2차: 기사 제목).
인용 추출 · 분류 열은 3 · 4단계에서 붙인다 (기획 6절).
"""

import datetime
import json
import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS statements (
    id            TEXT PRIMARY KEY,      -- {collector}:{hash}
    speaker       TEXT NOT NULL,         -- config.PEOPLE 키
    sub_speaker   TEXT,                  -- 연준 연설자 성(waller 등), ARK 펀드 묶음 등
    source_kind   TEXT NOT NULL,         -- primary | secondary
    attribution   TEXT NOT NULL,         -- self | office | trade | report
    collector     TEXT NOT NULL,
    publisher     TEXT,
    published_at  TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT,                  -- 1차만. 2차는 기사 본문을 저장하지 않는다
    url           TEXT,
    collected_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_st_published ON statements(published_at);
CREATE INDEX IF NOT EXISTS idx_st_speaker ON statements(speaker, published_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_st_url ON statements(speaker, url);
"""

# 나중에 붙은 열 (로컬 DB 는 connect 때 ALTER). 인용 추출 열(3단계)은 2차 항목에만 채운다
EXTRA_COLUMNS = {
    "ext_id": "TEXT",             # 소스 쪽 id — Truth Social 게시물 id (trump-trend 분류를 그대로 쓴다, 4단계)
    "prefilter_reason": "TEXT",   # no_name · no_speech — LLM 전에 버린 이유. NULL = 통과
    "group_id": "TEXT",           # 같은 발언 묶음 = 대표 항목 id (대표 자신 포함)
    "group_size": "INTEGER",      # 대표 행에만: 묶음의 매체 수
    "is_statement": "INTEGER",    # 1 = 그 인물이 직접 한 새 발언 · 행동, 0 = 해설 · 남의 말 · 오래된 말
    "quote": "TEXT",              # 발언 한 문장 (영어, 기사 제목에서 옮김)
    "dup_of_primary": "TEXT",     # 같은 발언의 1차 항목 id — 있으면 2차는 카드에 쓰지 않는다
    "extract_model": "TEXT",
    "extracted_at": "TEXT",
    # 4단계 분류 (classify.py) — trump-trend 와 같은 8칸. 배열은 JSON 문자열
    "noise_reason": "TEXT",
    "ai_topic": "TEXT", "ai_subtopic": "TEXT", "ai_target_country": "TEXT", "ai_target_sector": "TEXT",
    "ai_mentioned_companies": "TEXT", "ai_direction": "TEXT", "ai_intensity": "INTEGER", "ai_market_relevance": "INTEGER",
    "analyzed_at": "TEXT", "ai_model": "TEXT",
    "ai_issue": "TEXT",           # 이슈 코드 (experiments/issue_codes.py, 2026-10-21) — 옛 행은 NULL, 주제 대응표로 채울 수 있다
}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path=config.DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(statements)")}
    for col, typ in EXTRA_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE statements ADD COLUMN {col} {typ}")
    return conn


def dumps(v):
    return json.dumps(v, ensure_ascii=False)
