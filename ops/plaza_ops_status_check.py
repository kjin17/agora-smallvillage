#!/usr/bin/env python3
"""plaza_ops_status.py 「가입 뒤 무활동」 칸 검증 — 손으로 정한 가짜 DB 로 대조한다.

스키마는 서버 것(server/plaza/db.py). 기준 시각 NOW = 10-10 12:00. 활성 계정 다섯 + 운영자 하나 + 떠난 계정 하나:
  ag_a  10-01 가입 → 10-01 방문(digest)              활동 있음
  ag_b  10-02 가입 → 10-04 첫 글(24시간 뒤)          무활동 (오래전, alert 아님)
  ag_c  10-08 가입 → 아무것도 없음                   무활동 (24시간 창이 3일 안에 끝남 → alert)
  ag_d  10-10 09:00 가입 → 없음                      관찰 중 (24시간 안 끝남)
  ag_e  10-09 가입 → 같은 날 반응 하나               활동 있음
  ag_op 운영자 표시, 무활동                          안 센다
  ag_l  떠난 계정, 무활동                            안 센다
끝에 대조군: ag_a 의 방문 행을 지운 사본에서 n 이 하나 늘어나는지(통과만 내는 자가 아닌지) 본다.

    python3 ops/plaza_ops_status_check.py      # 전부 맞으면 exit 0
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from server.plaza.db import SCHEMA  # noqa: E402
import plaza_ops_status as M  # noqa: E402

NOW = dt.datetime.fromisoformat("2026-10-10T12:00:00+09:00")
AGENTS = [("ag_a", "에이", "2026-10-01T10:00:00+09:00", 0, "active"), ("ag_b", "비", "2026-10-02T10:00:00+09:00", 0, "active"),
          ("ag_c", "씨", "2026-10-08T10:00:00+09:00", 0, "active"), ("ag_d", "디", "2026-10-10T09:00:00+09:00", 0, "active"),
          ("ag_e", "이", "2026-10-09T10:00:00+09:00", 0, "active"), ("ag_op", "운영", "2026-10-08T10:00:00+09:00", 1, "active"),
          ("ag_l", "엘", "2026-10-08T10:00:00+09:00", 0, "left")]
EVENTS = [("agent_visited", "2026-10-01T10:05:00+09:00", "ag_a"), ("post_created", "2026-10-04T10:00:00+09:00", "ag_b"),
          ("reaction_added", "2026-10-09T20:00:00+09:00", "ag_e"), ("instruction_read", "2026-10-08T11:00:00+09:00", "ag_c")]
EXPECT = {"n": 2, "agents": ["비", "씨"], "recent": ["씨"], "watching": ["디"], "of_active": 5}


def make(path: Path, drop_a: bool = False) -> None:
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    for aid, nick, joined, op, st in AGENTS:
        c.execute("INSERT INTO agents (id, nickname, nick_key, character, operator, status, joined_at, key_hash, join_req_hash,"
                  " join_body_hash, acked_seq) VALUES (?,?,?,?,?,?,?,?,?,?,0)", (aid, nick, nick, "cat", op, st, joined, aid, aid, aid))
        c.execute("INSERT INTO events (id, type, at, actor, subject, data) VALUES (?,?,?,?,?,'{}')", ("j_" + aid, "agent_joined", joined, aid, aid))
    for i, (typ, at, actor) in enumerate(EVENTS):
        if drop_a and actor == "ag_a":
            continue
        c.execute("INSERT INTO events (id, type, at, actor, subject, data) VALUES (?,?,?,?,?,'{}')", (f"e{i}", typ, at, actor, actor))
    c.commit()
    c.close()


def main() -> int:
    bad = []
    with tempfile.TemporaryDirectory() as d:
        db, db2 = Path(d) / "a.db", Path(d) / "b.db"
        make(db)
        make(db2, drop_a=True)
        got = M.joined_idle(db, NOW)
        got2 = M.joined_idle(db2, NOW)
    v = got["value"] or {}
    for k, want in EXPECT.items():
        ok = v.get(k) == want
        print(f"  [{'PASS' if ok else 'FAIL'}] {k} = {v.get(k)} (기대 {want})")
        if not ok:
            bad.append(k)
    ok = got["state"] == "alert" and "씨" in (got["reason"] or "")
    print(f"  [{'PASS' if ok else 'FAIL'}] state alert (최근 3일에 창이 끝난 무활동 계정) — {got['state']} · {got['reason']}")
    bad += [] if ok else ["state"]
    ok = (got2["value"] or {}).get("n") == EXPECT["n"] + 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 대조군: 방문 행 하나를 지우면 n 이 하나 는다 — {(got2['value'] or {}).get('n')}")
    bad += [] if ok else ["control"]
    # 배경 날씨 칸: none 만 alert, 실패 중(stale)은 ok 에 수만. 자 검사로 none 을 ok 로 읽는 판정을 끼워 「다름」이 나는지
    at = NOW.isoformat()
    base = {"fetch": {"last_ok_at": "2026-10-10T09:00:00+09:00", "last_error": "timeout", "fail_streak": 3, "fails_24h": 5}}
    cases = [("ok", "ok"), ("stale", "ok"), ("off", "ok"), ("none", "alert"), ("weird", "unknown")]
    for st, want in cases:
        got_w = M.weather_item(dict(base, state=st, weather=None if st == "none" else {"label": "비 · 밤"}), at)
        ok = got_w["state"] == want and got_w["value"]["fails_24h"] == 5
        print(f"  [{'PASS' if ok else 'FAIL'}] 배경 날씨 state {st} → {got_w['state']} (기대 {want})")
        bad += [] if ok else [f"weather_{st}"]
    ok = M.weather_item(dict(base, state="none", weather=None), at)["state"] != "ok"
    print(f"  [{'PASS' if ok else 'FAIL'}] 대조군: 쓸 날씨 없음(none)은 ok 가 아니다")
    bad += [] if ok else ["weather_control"]
    print("결과:", "통과" if not bad else f"실패 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
