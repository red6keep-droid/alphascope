-- Newfact 토론 — D1 표 (2026-11-22, 기획 alphascope-docs doc/기획/댓글-토론방-기획.md 3-4절)
-- 적용:  npx wrangler d1 execute newfact-board --remote --file schema.sql   (로컬 시험은 --local)
-- 색인이 붙은 칸을 쓰면 D1 쓰기 줄이 하나씩 더 세어진다 → 색인은 읽기에 꼭 필요한 것만.

-- 글 · 답글. 별명은 여기 두지 않고 파일 만들 때 users 와 맞춰 붙인다(별명을 바꾸면 지난 글도 새 별명)
CREATE TABLE IF NOT EXISTS items (
  id        TEXT PRIMARY KEY,
  key       TEXT NOT NULL,              -- 자리 열쇠(stock-NVDA · p-… · post-… · market-kr · market-us · kr-report)
  kind      TEXT NOT NULL,              -- post | reply
  parent    TEXT,                       -- 답글이면 글 id
  seq       INTEGER,                    -- 글만: 그 자리 안 번호(1, 2, 3…) — 50개 묶음 파일 번호 = (seq-1)/50
  uid       TEXT NOT NULL,
  title     TEXT,                       -- 글만
  text      TEXT NOT NULL,
  sym       TEXT,                       -- 붙인 종목 코드
  where_url TEXT,                       -- 쓴 날 글 주소(자리 댓글 꼬리표 · 그 날 글로 가기)
  where_label TEXT,                     -- 꼬리표 글자 `11.18 증시 시황`
  created   INTEGER NOT NULL,           -- ms
  up        INTEGER NOT NULL DEFAULT 0,
  down      INTEGER NOT NULL DEFAULT 0,
  replies   INTEGER NOT NULL DEFAULT 0,
  hidden    INTEGER NOT NULL DEFAULT 0, -- 신고 3명 · 운영자
  deleted   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_key_seq ON items (key, seq) WHERE kind = 'post';
CREATE INDEX IF NOT EXISTS items_parent ON items (parent) WHERE kind = 'reply';
CREATE INDEX IF NOT EXISTS items_uid ON items (uid, created);
CREATE INDEX IF NOT EXISTS items_created ON items (created);   -- 댓글 봇 `새 글` 질의

-- 자리마다 글 수 · 마지막 번호 — 쓸 때마다 세면(COUNT) 글이 쌓일수록 읽기 줄이 늘어서 칸으로 둔다
CREATE TABLE IF NOT EXISTS places (
  key      TEXT PRIMARY KEY,
  posts    INTEGER NOT NULL DEFAULT 0,
  last_seq INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reacts (
  item    TEXT NOT NULL,
  uid     TEXT NOT NULL,
  v       TEXT NOT NULL,                -- up | down
  created INTEGER NOT NULL,
  PRIMARY KEY (item, uid)
);
CREATE INDEX IF NOT EXISTS reacts_uid ON reacts (uid);

CREATE TABLE IF NOT EXISTS reports (
  item    TEXT NOT NULL,
  uid     TEXT NOT NULL,
  why     TEXT NOT NULL,
  created INTEGER NOT NULL,
  PRIMARY KEY (item, uid)
);

CREATE TABLE IF NOT EXISTS users (
  uid     TEXT PRIMARY KEY,
  nick    TEXT,
  intro   TEXT NOT NULL DEFAULT '',
  nick_at INTEGER,                      -- 별명 바꾼 때(30일에 한 번)
  day     INTEGER NOT NULL DEFAULT 0,   -- 한국 날짜 번호
  n       INTEGER NOT NULL DEFAULT 0,   -- 그날 글 · 답글 수(30)
  rday    INTEGER NOT NULL DEFAULT 0,
  rn      INTEGER NOT NULL DEFAULT 0,   -- 그날 좋아요 · 싫어요 수(30)
  last    INTEGER NOT NULL DEFAULT 0,   -- 마지막 글 ms(20초 간격)
  banned  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nicks (
  nick TEXT PRIMARY KEY,                -- 대소문자 구분 없이 겹침 금지 → 소문자로 저장
  uid  TEXT NOT NULL
);
