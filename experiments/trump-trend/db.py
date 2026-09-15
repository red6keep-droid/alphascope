"""SQLite 스키마와 연결.

기획서 3절의 테이블을 그대로 만든다. 열거형·배열 값은 JSON 문자열로 저장한다.
모든 시각은 UTC ISO-8601 문자열("2026-09-15T03:54:14Z").
"""

import json
import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS trump_posts (
    id                      TEXT PRIMARY KEY,
    published_at            TEXT NOT NULL,
    content                 TEXT NOT NULL,
    source                  TEXT NOT NULL,
    source_url              TEXT,
    media_count             INTEGER DEFAULT 0,
    collected_at            TEXT NOT NULL,
    noise_reason            TEXT,
    ai_topic                TEXT,
    ai_subtopic             TEXT,
    ai_target_country       TEXT,   -- JSON array
    ai_target_sector        TEXT,   -- JSON array
    ai_mentioned_companies  TEXT,   -- JSON array
    ai_direction            TEXT,
    ai_intensity            INTEGER,
    ai_market_relevance     INTEGER,
    event_id                TEXT,
    analyzed_at             TEXT,
    ai_model                TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_published ON trump_posts(published_at);
CREATE INDEX IF NOT EXISTS idx_posts_pending ON trump_posts(analyzed_at, noise_reason);
CREATE INDEX IF NOT EXISTS idx_posts_event ON trump_posts(event_id);

CREATE TABLE IF NOT EXISTS trump_events (
    event_id            TEXT PRIMARY KEY,
    topic               TEXT NOT NULL,
    subtopic            TEXT,
    target              TEXT,
    first_post_at       TEXT NOT NULL,
    last_post_at        TEXT NOT NULL,
    post_count          INTEGER NOT NULL,
    event_direction     TEXT NOT NULL,
    event_intensity     INTEGER NOT NULL,
    mapping_rule_id     TEXT,
    mentioned_companies TEXT,   -- JSON array. 본문에 실제 언급된 티커 (신규 등장 판정용)
    affected_companies  TEXT,   -- JSON array. 언급 + 매핑 규칙 산출
    market_session      TEXT,   -- regular / pre / after / closed
    baseline_day        TEXT,   -- 기준 종가의 거래일 (YYYY-MM-DD)
    effective_day       TEXT,   -- 반응을 재는 거래일 D
    confounded_intraday INTEGER DEFAULT 0,
    confounded_daily    INTEGER DEFAULT 0,
    confound_labels     TEXT    -- JSON array
);
CREATE INDEX IF NOT EXISTS idx_events_first ON trump_events(first_post_at);
CREATE INDEX IF NOT EXISTS idx_events_topic ON trump_events(topic, subtopic, target);

CREATE TABLE IF NOT EXISTS event_reactions (
    event_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    baseline_price  REAL,
    ret_close       REAL,
    ret_next_close  REAL,
    ret_5m          REAL,
    ret_15m         REAL,
    ret_60m         REAL,
    abn_close       REAL,
    abn_next_close  REAL,
    abn_5m          REAL,
    abn_15m         REAL,
    abn_60m         REAL,
    PRIMARY KEY (event_id, symbol)
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol  TEXT NOT NULL,
    day     TEXT NOT NULL,   -- YYYY-MM-DD (거래일, 뉴욕 기준)
    open    REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, day)
);

CREATE TABLE IF NOT EXISTS macro_calendar (
    day     TEXT NOT NULL,
    kind    TEXT NOT NULL,   -- FOMC / CPI / NFP / GDP / PCE / EARNINGS
    label   TEXT,
    source  TEXT,
    PRIMARY KEY (day, kind, label)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


# 이미 만들어진 DB에 컬럼이 추가될 때. (table, column, decl)
_MIGRATIONS = [
    ("trump_events", "mentioned_companies", "TEXT"),
]


def _migrate(conn):
    for table, column, decl in _MIGRATIONS:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def dumps(value):
    return json.dumps(value or [], ensure_ascii=False)


def loads(text):
    if not text:
        return []
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return []
