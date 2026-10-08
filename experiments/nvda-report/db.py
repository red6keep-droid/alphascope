"""SQLite 스키마와 연결 (기획서 3절).

②단계(분류) 전에 확정해야 하는 것: items.kind · ai_* 컬럼 · daily_state 컬럼군 · quarterly.metric 목록.
여기 적힌 것이 그 확정본이다. 열거형·배열 값은 JSON 문자열, 시각은 UTC ISO-8601("2026-10-07T22:45:00Z").

trump-trend와 다른 점 하나 — 거시 캘린더(FOMC·CPI·NFP·GDP·PCE)를 별도 macro_calendar 테이블에 두지 않고
`calendar` 한 테이블에 kind로 섞어 둔다. "다가오는 것" 섹션이 한 쿼리로 읽기 위해서다.
"""

import json
import os
import sqlite3

import config

SCHEMA = """
-- 수집된 문서 하나 = 행 하나. 공시(form4·8k·10q·10k)와 애널리스트 변경(analyst)은 Gemini를 거치지 않는다.
CREATE TABLE IF NOT EXISTS items (
    item_id          TEXT PRIMARY KEY,   -- {kind}:{source_key}
    kind             TEXT NOT NULL,      -- form4 · 8k · 10q · 10k · analyst · fedreg · court · newsroom · blog · news
    published_at     TEXT NOT NULL,      -- 원문 시각 (UTC)
    title            TEXT,
    summary          TEXT,
    url              TEXT,
    source           TEXT NOT NULL,      -- edgar · yfinance · federalregister · courtlistener · nvidianews · cnbc · googlenews …
    raw_json         TEXT,               -- 소스별 구조화 필드
    collected_at     TEXT NOT NULL,
    prefilter_reason TEXT,               -- no_nvda_keyword · duplicate_of:{item_id} · NULL
    ai_area          TEXT,               -- Earnings · Flows · Regulation · Legal · Product · Demand · Supply · Corporate · Macro · Other
    ai_direction     TEXT,               -- positive · negative · uncertain · neutral
    ai_novelty       TEXT,               -- new · update · repeat
    ai_relevance     INTEGER,            -- 0–3
    ai_fact          TEXT,               -- 한 문장 사실 요약
    ai_entities      TEXT,               -- JSON
    ai_model         TEXT,
    analyzed_at      TEXT,               -- NULL이면 분류 대기 (form4·8k·analyst는 수집 시 채운다 = 분류 불필요)
    is_event         INTEGER DEFAULT 0,  -- 6절 임계값 통과
    reported_on      TEXT                -- 어느 날 리포트의 "오늘 바뀐 것"에 올랐나. NULL이면 아직 안 올랐다
);
CREATE INDEX IF NOT EXISTS idx_items_kind_pub ON items(kind, published_at);
CREATE INDEX IF NOT EXISTS idx_items_pending ON items(analyzed_at, prefilter_reason);
CREATE INDEX IF NOT EXISTS idx_items_reported ON items(reported_on);

-- 거래일 하나 = 행 하나 (상태판 스냅샷). 가격·기술 칸은 일봉에서 과거까지 채우고, 나머지는 수집한 날부터.
CREATE TABLE IF NOT EXISTS daily_state (
    day                         TEXT PRIMARY KEY,
    -- 가격
    close REAL, ret_1d REAL, ret_vs_spy REAL, ret_vs_smh REAL, ret_vs_amd REAL, ret_vs_qqq REAL,
    gap REAL, range_pct REAL,
    -- 거래량
    volume REAL, vol_ratio_20d REAL,
    -- 기술
    ma50 REAL, ma200 REAL, pct_from_52w_high REAL, rsi14 REAL,
    ma_cross TEXT,                      -- golden · death · NULL
    -- 옵션
    iv_atm_30d REAL, iv_rank_60d REAL, implied_move_next_earnings REAL,
    pc_ratio_oi REAL, pc_ratio_vol REAL,
    gex_approx REAL,                    -- 달러 단위 근사. 부호만 쓴다
    gex_flip_strike REAL,               -- 누적 감마가 0을 지나는 행사가 (현재가에 가장 가까운 것)
    max_oi_strike_call REAL, max_oi_strike_put REAL,
    option_expiries TEXT,               -- JSON. 이날 스냅샷에 담긴 만기
    -- 추정치
    eps_est_cq REAL, eps_est_cq_7d_chg_pct REAL,
    rev_est_cq REAL, rev_est_cq_7d_chg_pct REAL,
    revisions_up_30d INTEGER, revisions_down_30d INTEGER,
    eps_est_ny REAL,                    -- 다음 회계연도 EPS 컨센서스 (forward_pe용)
    -- 애널리스트
    rating_counts_json TEXT, pt_mean REAL, pt_high REAL, pt_low REAL, pt_median REAL,
    -- 수급
    smh_shares_out REAL, soxx_shares_out REAL,
    shares_short REAL, short_pct_float REAL, short_asof TEXT, shares_short_prior REAL,
    -- 밸류에이션
    forward_pe REAL,
    -- 뉴스 (②단계)
    news_count INTEGER,
    -- 메타
    collected_at TEXT,
    missing_fields_json TEXT
);

-- 거래일 × 만기 × 행사가. 현재가 ±30% 행사가만, 90일 보관.
CREATE TABLE IF NOT EXISTS option_snapshots (
    day TEXT NOT NULL, expiry TEXT NOT NULL, strike REAL NOT NULL,
    call_oi REAL, put_oi REAL, call_iv REAL, put_iv REAL, call_vol REAL, put_vol REAL,
    call_mid REAL, put_mid REAL,
    PRIMARY KEY (day, expiry, strike)
);

-- 다가오는 것 + 거시. kind: EARNINGS · EARNINGS_PEER · FOMC · CPI · NFP · GDP · PCE · TSMC_REV · EVENT · INDEX · OPEX
CREATE TABLE IF NOT EXISTS calendar (
    day TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL,
    symbol TEXT, source TEXT, confirmed INTEGER DEFAULT 1,
    PRIMARY KEY (day, kind, label)
);

-- 추적 중인 소송·규제 사안 (③단계에서 채운다)
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
    title TEXT, court TEXT, docket_number TEXT, url TEXT,
    role TEXT, category TEXT, status TEXT,
    opened_at TEXT, last_activity_at TEXT, last_activity_summary TEXT,
    watch INTEGER DEFAULT 0
);

-- 보유 논리 점검표 (8절). value는 숫자, value_json은 표 모양 값(기관 상위 10 같은 것).
CREATE TABLE IF NOT EXISTS quarterly (
    fiscal_quarter TEXT NOT NULL, metric TEXT NOT NULL,
    value REAL, value_json TEXT, unit TEXT,
    source TEXT, source_url TEXT, recorded_at TEXT, verified INTEGER DEFAULT 0,
    PRIMARY KEY (fiscal_quarter, metric)
);

-- TSMC 월매출 (④단계)
CREATE TABLE IF NOT EXISTS monthly (
    month TEXT PRIMARY KEY, revenue_twd REAL, yoy_pct REAL, mom_pct REAL, source_url TEXT
);

-- 공시 본문 (④단계 추출용)
CREATE TABLE IF NOT EXISTS filings_text (
    accession TEXT PRIMARY KEY, form TEXT, url TEXT, text TEXT, fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL, day TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, day)
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# 이미 만들어진 DB에 컬럼이 추가될 때. (table, column, decl)
_MIGRATIONS = [
    ("items", "classify_attempts", "INTEGER DEFAULT 0"),   # ②단계: 검증 탈락 횟수
]


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn):
    for table, column, decl in _MIGRATIONS:
        if column not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def dumps(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False, default=str)


def loads(text, default=None):
    if not text:
        return default if default is not None else []
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default if default is not None else []


def upsert(conn, table, row, keys):
    """dict 한 행을 INSERT … ON CONFLICT(keys) DO UPDATE. 값이 None인 칸은 기존 값을 지우지 않는다."""
    cols = list(row)
    sets = ", ".join(f"{c}=COALESCE(excluded.{c}, {table}.{c})" for c in cols if c not in keys)
    sql = (f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)}) "
           f"ON CONFLICT({', '.join(keys)}) DO UPDATE SET {sets}")
    conn.execute(sql, [row[c] for c in cols])


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
