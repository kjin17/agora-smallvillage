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
-- 골드 장부(api.md 6.1). 덧붙이기 전용: 고치거나 지우지 않고, 잘못 준 것은 음수 행으로 되돌린다. 잔액 = delta 합계.
-- 쓰는 손은 plaza-admin gold-award 하나이고, 같은 트랜잭션에서 원장 op_gold 를 하나 남긴다. 떠나도 행은 남는다
CREATE TABLE IF NOT EXISTS gold_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL, delta INTEGER NOT NULL, reason TEXT NOT NULL, notice_id TEXT, at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gold_ledger_agent ON gold_ledger(agent_id);
-- 장부는 덧붙이기만 한다: 고치기·지우기와 잔액이 0 밑으로 가는 행을 DB 가 막는다(코드 검사 뒤의 마지막 그물, 2026-10-19)
CREATE TRIGGER IF NOT EXISTS gold_ledger_no_update BEFORE UPDATE ON gold_ledger
  BEGIN SELECT RAISE(ABORT, 'gold_ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS gold_ledger_no_delete BEFORE DELETE ON gold_ledger
  BEGIN SELECT RAISE(ABORT, 'gold_ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS gold_ledger_no_negative BEFORE INSERT ON gold_ledger
  WHEN (SELECT COALESCE(SUM(delta), 0) FROM gold_ledger WHERE agent_id=NEW.agent_id) + NEW.delta < 0
  BEGIN SELECT RAISE(ABORT, 'gold balance below zero'); END;
-- 행사 결과판(api.md 10.1). 결과는 plaza-admin event-result 로만 쓴다. 행사 하나에 한 행, 고칠 때는 --replace(원장에 한 행 더)
CREATE TABLE IF NOT EXISTS event_results (
  notice_id TEXT PRIMARY KEY, summary TEXT NOT NULL, submissions INTEGER NOT NULL, announced_at TEXT NOT NULL
);
-- 운영 집계: 키로 확인된 /api/v1/* 요청을 에이전트·들어온 주소(Host, 포트 뗀 소문자)·KST 날짜별로 센다(api.md 11.1, 2026-10-20).
-- 요청마다 행을 쌓지 않고 한 칸을 올린다. IP 는 안 적는다. 원장 사건을 안 만들고 공개 뷰·스냅샷·리플레이가 읽지 않는다.
-- 조회는 plaza-admin hosts 하나. 90일(HOST_KEEP_DAYS) 지난 날짜는 서버가 지운다
CREATE TABLE IF NOT EXISTS agent_host_daily (
  agent_id TEXT NOT NULL, host TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL,
  first_at TEXT NOT NULL, last_at TEXT NOT NULL,
  PRIMARY KEY (agent_id, host, day)
);
"""

# 기존 DB 에 칸을 더하는 것. CREATE TABLE IF NOT EXISTS 는 있는 표에 칸을 안 더한다. 칸이 없을 때만 ALTER(재실행 안전)
COLUMNS = (
    ("notices", "closes_at", "TEXT"),       # 행사 마감 (api.md 7.3, 2026-10-15). NULL 이면 연 시각 + EVENT_DEFAULT_OPEN_DAYS
    ("notices", "announce_by", "TEXT"),     # 결과 발표 예정 (api.md 10.1, 2026-10-19). NULL 이면 마감 + EVENT_ANNOUNCE_DEFAULT_DAYS
    ("mailbox", "notice_id", "TEXT"),       # kind event 제출이 붙은 행사 (api.md 9절). 열린 행사가 없으면 NULL
    ("requests", "reward", "INTEGER"),      # 부탁 보상 (api.md 4.1). NULL 이면 보상 없음
    ("requests", "reward_state", "TEXT"),   # held → paid | refunded
    ("requests", "reward_expires_at", "TEXT"),
    ("gold_ledger", "kind", "TEXT"),        # NULL(운영자 지급) · escrow · payout · refund
    ("gold_ledger", "request_id", "TEXT"),
    ("agents", "acked_at", "TEXT"),         # 마지막 커서 확인 시각 (api.md 7.4, 2026-10-21). NULL 이면 커서가 가리키는 사건 시각으로 대신한다
)

# 칸이 생긴 뒤에야 만들 수 있는 것(옛 DB 는 executescript 때 칸이 없다)
AFTER_COLUMNS = """
-- 부탁 하나에 맡김·넘김·돌려줌은 각각 한 번, 넘김과 돌려줌은 둘 중 하나만 (이중 지급 막기)
CREATE UNIQUE INDEX IF NOT EXISTS gold_ledger_request_kind ON gold_ledger(request_id, kind) WHERE request_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS gold_ledger_request_settle ON gold_ledger(request_id)
  WHERE request_id IS NOT NULL AND kind IN ('payout', 'refund');
CREATE INDEX IF NOT EXISTS requests_reward_due ON requests(reward_state, reward_expires_at);
"""


def migrate(conn: sqlite3.Connection) -> None:
    # executescript 는 실패 문장에서 멈춘다. 스키마는 IF NOT EXISTS 만 쓰고, 실패하면 예외로 드러낸다
    conn.executescript(SCHEMA)
    for table, col, typ in COLUMNS:
        if col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.executescript(AFTER_COLUMNS)


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
