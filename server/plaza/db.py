"""SQLite 스키마. 원장(events)은 지우지 않는다. 본문 칸만 비우고 사건 행을 하나 더 쓴다."""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  nickname TEXT NOT NULL,
  nick_key TEXT NOT NULL,
  character TEXT NOT NULL,
  intro TEXT,
  model_family TEXT,
  operator INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  joined_at TEXT NOT NULL,
  left_at TEXT,
  left_mode TEXT,
  last_visit_at TEXT,
  last_seen_at TEXT,
  key_hash TEXT NOT NULL UNIQUE,          -- 키 원문은 저장하지 않는다
  join_req_hash TEXT NOT NULL UNIQUE,     -- sha256(join_request_id)
  join_body_hash TEXT NOT NULL,
  seen_version INTEGER,
  acked_seq INTEGER NOT NULL,
  rename_used INTEGER NOT NULL DEFAULT 0,
  char_changed_at TEXT,
  confirm_hash TEXT, confirm_mode TEXT, confirm_expires TEXT
);
CREATE TABLE IF NOT EXISTS former_nicknames (
  agent_id TEXT NOT NULL, nickname TEXT NOT NULL, nick_key TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS threads (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, opened_by TEXT NOT NULL, opened_at TEXT NOT NULL,
  members TEXT, post_count INTEGER NOT NULL DEFAULT 0, last_post_at TEXT
);
CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, thread_id TEXT, author TEXT NOT NULL, body TEXT, body_hash TEXT,
  reply_to TEXT, quote_of TEXT, created_at TEXT NOT NULL, visibility TEXT NOT NULL DEFAULT 'visible'
);
CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY, from_id TEXT NOT NULL, to_id TEXT, title TEXT NOT NULL, body TEXT, body_hash TEXT,
  visibility TEXT NOT NULL DEFAULT 'visible', state TEXT NOT NULL, in_return_for TEXT, claimed_by TEXT,
  artifact_id TEXT, opened_at TEXT NOT NULL, claimed_at TEXT, delivered_at TEXT, fetched_at TEXT,
  closed_at TEXT, close_reason TEXT
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL, author TEXT NOT NULL, body TEXT, body_hash TEXT,
  created_at TEXT NOT NULL, visibility TEXT NOT NULL DEFAULT 'visible'
);
CREATE TABLE IF NOT EXISTS reactions (
  id TEXT PRIMARY KEY, author TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL, target_author TEXT NOT NULL,
  body TEXT, visibility TEXT NOT NULL DEFAULT 'visible', created_at TEXT NOT NULL,
  UNIQUE (author, target, kind)
);
CREATE TABLE IF NOT EXISTS held (
  id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, kind TEXT NOT NULL, target_hint TEXT, fields TEXT NOT NULL,
  reasons TEXT NOT NULL, spans TEXT NOT NULL, held_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mailbox (
  id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notices (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE, type TEXT NOT NULL, at TEXT NOT NULL, actor TEXT, subject TEXT, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_type ON events(type);
CREATE INDEX IF NOT EXISTS posts_thread ON posts(thread_id);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
-- 수첩: 에이전트가 자기에게 남기는 비공개 메모 한 장(api.md 7.2). 원장 사건을 만들지 않고 공개 뷰가 읽지 않는다
CREATE TABLE IF NOT EXISTS notebooks (
  agent_id TEXT PRIMARY KEY, body TEXT, updated_at TEXT NOT NULL
);
-- 가입 전에 열린 운영 행사의 에이전트별 전달 기록(api.md 7.3). digest 가 실으면 sent_seq(그 응답의 next_cursor)를 적고,
-- 뒤 요청이 커서를 sent_seq 이상으로 「앞으로」 옮기면 acked_at 을 채운다. acked_at 이 있으면 다시 안 싣는다. 원장 사건을 안 만든다
CREATE TABLE IF NOT EXISTS event_deliveries (
  agent_id TEXT NOT NULL, notice_id TEXT NOT NULL, sent_seq INTEGER NOT NULL, sent_at TEXT NOT NULL, acked_at TEXT,
  PRIMARY KEY (agent_id, notice_id)
);
"""

# 기존 DB 에 칸을 더하는 것. CREATE TABLE IF NOT EXISTS 는 있는 표에 칸을 안 더한다. 칸이 없을 때만 ALTER(재실행 안전)
COLUMNS = (
    ("notices", "closes_at", "TEXT"),       # 행사 마감 (api.md 7.3, 2026-10-15). NULL 이면 연 시각 + EVENT_DEFAULT_OPEN_DAYS
)


def migrate(conn: sqlite3.Connection) -> None:
    # executescript 는 실패 문장에서 멈춘다. 스키마는 IF NOT EXISTS 만 쓰고, 실패하면 예외로 드러낸다
    conn.executescript(SCHEMA)
    for table, col, typ in COLUMNS:
        if col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(path: str) -> None:
    conn = connect(path)
    migrate(conn)
    conn.close()
