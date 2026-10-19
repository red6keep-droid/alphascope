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


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path=config.DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def dumps(v):
    return json.dumps(v, ensure_ascii=False)
