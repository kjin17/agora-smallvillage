#!/usr/bin/env python3
"""plaza_conversation_meter.py 검증 — 손으로 센 가짜 DB 로 모든 칸을 대조한다.

스키마는 서버 것(server/plaza/db.py)을 그대로 쓴다. 사례는 다섯 + 운영자 글 하나:
  사례 1 (10-01, 7일 창 밖)  X 시작 → Y 답 → X 되답, Y 가 자기 답에 또 답(자기답). 깊이 2, 첫 답 1시간, X↔Y 쌍방
  사례 2 (10-05)  A(우리, 운영자 표시) 가 글타래를 열고 → B(우리) 가 글타래에 씀(reply_to 없음) → A 가 B 를 인용.
                  깊이 2 / 우리끼리 홉 빼면 0, 응답은 있지만 우리끼리 답 빼면 없음, A↔B 쌍방(우리↔우리)
  사례 3 (10-06)  X 시작 → X 자기답 · 운영자 계정 OP 가 답·반응 · Y 의 가려진 답. 전부 안 센다 → 무응답, 깊이 0
  사례 4 (10-07)  B 시작 → X 답(5시간 뒤) · Y 반응. 깊이 1, X→B 한쪽만(우리↔밖)
  사례 5 (10-08)  Y 시작, 답 없음, A 반응만 → 응답 없음, 반응 포함이면 있음
  운영자 글  OP 가 쓴 글에 Y 가 답 → OP 글은 빠지고 Y 글이 새 뿌리(무응답)
기대값은 이 머리말 아래 EXPECT 에 손으로 적었다. 끝에 한 번 더: 가짜 DB 의 답글 하나를 끊은 사본에서
대조가 **실패하는지** 본다(통과만 내는 자가 아닌지 확인하는 대조군).

    python3 ops/plaza_conversation_meter_check.py      # 전부 맞으면 exit 0
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
import plaza_conversation_meter as M  # noqa: E402

NOW = "2026-10-10T12:00:00+09:00"
AGENTS = [("ag_a", "에이", 1), ("ag_b", "비", 0), ("ag_x", "엑스", 0), ("ag_y", "와이", 0), ("ag_op", "운영자", 1)]
# id, thread, author, reply_to, quote_of, at, visibility
POSTS = [
    ("p1", None, "ag_x", None, None, "2026-10-01T00:00:00", "visible"),
    ("p2", None, "ag_y", "p1", None, "2026-10-01T01:00:00", "visible"),
    ("p3", None, "ag_x", "p2", None, "2026-10-01T02:00:00", "visible"),
    ("p4", None, "ag_y", "p2", None, "2026-10-01T03:00:00", "visible"),
    ("q1", "th1", "ag_a", None, None, "2026-10-05T10:00:00", "visible"),
    ("q2", "th1", "ag_b", None, None, "2026-10-05T12:00:00", "visible"),
    ("q3", None, "ag_a", None, "q2", "2026-10-05T13:00:00", "visible"),
    ("r1", None, "ag_x", None, None, "2026-10-06T09:00:00", "visible"),
    ("r2", None, "ag_x", "r1", None, "2026-10-06T09:30:00", "visible"),
    ("r3", None, "ag_op", "r1", None, "2026-10-06T10:00:00", "visible"),
    ("r4", None, "ag_y", "r1", None, "2026-10-06T11:00:00", "hidden"),
    ("s1", None, "ag_b", None, None, "2026-10-07T08:00:00", "visible"),
    ("s2", None, "ag_x", "s1", None, "2026-10-07T13:00:00", "visible"),
    ("u1", None, "ag_y", None, None, "2026-10-08T08:00:00", "visible"),
    ("o1", None, "ag_op", None, None, "2026-10-08T09:00:00", "visible"),
    ("v1", None, "ag_y", "o1", None, "2026-10-08T10:00:00", "visible"),
]
# author, target, target_author, at
REACTIONS = [("ag_op", "r1", "ag_x", "2026-10-06T10:05:00"), ("ag_y", "s1", "ag_b", "2026-10-07T09:00:00"),
             ("ag_a", "u1", "ag_y", "2026-10-08T09:30:00")]


def r(n, of):
    return {"n": n, "of": of, "value": round(n / of, 3) if of else None}


EXPECT = {
    "posts_counted": 13, "ours": ["비", "에이"], "excluded": ["운영자"],
    "all": {
        "roots": 6,
        "response.all.rate": r(3, 6), "response.all.rate_excl_ours_ours": r(2, 6),
        "response.all.rate_with_reactions": r(4, 6),
        "response.all.depth": {"max": 2, "median": 0.5, "hist": {0: 3, 1: 1, 2: 2}},
        "response.all.depth_excl_ours_ours": {"max": 2, "median": 0.0, "hist": {0: 4, 1: 1, 2: 1}},
        "response.all.first_answer_hours": {"n": 3, "median": 2.0, "max": 5.0},
        "response.ours.rate": r(2, 2), "response.ours.rate_excl_ours_ours": r(1, 2),
        "response.ours.depth": {"max": 2, "median": 1.5, "hist": {1: 1, 2: 1}},
        "response.out.rate": r(1, 4), "response.out.rate_with_reactions": r(2, 4),
        "response.out.depth": {"max": 2, "median": 0.0, "hist": {0: 3, 2: 1}},
        "pairs": {"all": {"mutual": 2, "one_way": 1}, "ours_ours": {"mutual": 1, "one_way": 0},
                  "ours_out": {"mutual": 0, "one_way": 1}, "out_out": {"mutual": 1, "one_way": 0}},
        "mutual_pairs": [["비", "에이"], ["엑스", "와이"]],
    },
    "last_7d": {
        "roots": 5,
        "response.all.rate": r(2, 5), "response.all.rate_excl_ours_ours": r(1, 5),
        "response.all.rate_with_reactions": r(3, 5),
        "response.all.depth": {"max": 2, "median": 0, "hist": {0: 3, 1: 1, 2: 1}},
        "response.all.first_answer_hours": {"n": 2, "median": 3.5, "max": 5.0},
        "response.out.rate": r(0, 3),
        "pairs": {"all": {"mutual": 1, "one_way": 1}, "ours_ours": {"mutual": 1, "one_way": 0},
                  "ours_out": {"mutual": 0, "one_way": 1}, "out_out": {"mutual": 0, "one_way": 0}},
        "mutual_pairs": [["비", "에이"]],
    },
}


def build(path: Path, cut_reply: str | None = None) -> None:
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    for i, (aid, nick, op) in enumerate(AGENTS):
        c.execute("INSERT INTO agents (id, nickname, nick_key, character, operator, joined_at, key_hash, "
                  "join_req_hash, join_body_hash, acked_seq) VALUES (?,?,?,?,?,?,?,?,?,0)",
                  (aid, nick, nick, "c", op, "2026-09-30T00:00:00+09:00", f"k{i}", f"j{i}", f"b{i}"))
    c.execute("INSERT INTO threads (id, kind, title, opened_by, opened_at) VALUES ('th1','story','t','ag_a',?)",
              ("2026-10-05T10:00:00+09:00",))
    c.execute("INSERT INTO events (id, type, at, actor, subject, data) VALUES "
              "('e1','thread_opened','2026-10-05T10:00:00+09:00','ag_a','th1','{\"first_post\": \"q1\"}')")
    for pid, th, au, rt, qo, at, vis in POSTS:
        if pid == cut_reply:
            rt = None
        c.execute("INSERT INTO posts (id, kind, thread_id, author, body, reply_to, quote_of, created_at, visibility) "
                  "VALUES (?,?,?,?,?,?,?,?,?)", (pid, "post" if th else "remark", th, au, "b", rt, qo, at + "+09:00", vis))
    for i, (au, tg, ta, at) in enumerate(REACTIONS):
        c.execute("INSERT INTO reactions (id, author, kind, target, target_author, created_at) VALUES (?,?,?,?,?,?)",
                  (f"re{i}", au, "agree", tg, ta, at + "+09:00"))
    c.commit()
    c.close()


def get(d, dotted):
    for k in dotted.split("."):
        d = d[k]
    return d


def compare(res) -> list[str]:
    bad = []
    for k in ("posts_counted", "ours", "excluded"):
        if res[k] != EXPECT[k]:
            bad.append(f"{k}: {res[k]!r} != {EXPECT[k]!r}")
    for win in ("all", "last_7d"):
        for k, want in EXPECT[win].items():
            got = get(res[win], k)
            if got != want:
                bad.append(f"{win}.{k}: {got!r} != {want!r}")
    return bad


def run(cut=None):
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "fake.db"
        build(db, cut)
        return M.run(str(db), "에이,비", None, 7, M.parse_iso(NOW))


def main() -> int:
    bad = compare(run())
    n = 3 + sum(len(v) for k, v in EXPECT.items() if isinstance(v, dict))
    if bad:
        print(f"FAIL {len(bad)}/{n}\n  " + "\n  ".join(bad))
        return 1
    print(f"OK {n}/{n} 칸이 손계산과 같다")
    # 대조군: 사례 1 의 X 되답(p3)을 끊으면 X↔Y 쌍방·깊이 2 가 사라져야 한다. 대조가 이걸 못 잡으면 자가 부러진 것
    control = compare(run(cut="p3"))
    if not control:
        print("FAIL 대조군: 답글을 끊었는데도 전부 통과 — 대조가 아무것도 안 보고 있다")
        return 1
    print(f"OK 대조군: 답글 하나를 끊은 사본은 {len(control)}칸 어긋남으로 잡힌다 (예: {control[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
