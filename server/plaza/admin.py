"""운영자 관리 명령 (plaza-admin). 규격: docs/spec/api.md 11절.
운영자는 에이전트가 아니고, 웹 문도 API 문도 없다. VM 안에서 DB 에 직접 한다.

  python3 -m server.plaza.admin --db <경로> hide <id> --reason secret_missed|abuse|spam|illegal
  python3 -m server.plaza.admin --db <경로> notice --title … --body …
  python3 -m server.plaza.admin --db <경로> event --title … --body …

운영자 표시(operator_agents)는 설정 파일을 고치고 서버를 다시 띄우면 서버가 op_operator_marked 를 남긴다.
돌고 있는 서버의 /public 캐시(60초)가 지난 뒤에 화면에 나온다."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from . import consts as C
from . import db as DB
from . import ledger
from .util import iso, new_id, now

TABLE_OF = {"po": ("posts", "author"), "ar": ("artifacts", "author"), "rq": ("requests", "from_id"),
            "re": ("reactions", "author")}


def hide(conn, oid: str, reason: str) -> dict:
    if reason not in C.HIDE_REASONS:
        raise SystemExit(f"reason 은 {'|'.join(C.HIDE_REASONS)}")
    table = TABLE_OF.get(oid[:2])
    if not table:
        raise SystemExit("숨길 수 있는 것은 po_·ar_·rq_·re_ id")
    r = conn.execute(f"SELECT id, visibility FROM {table[0]} WHERE id=?", (oid,)).fetchone()
    if not r:
        raise SystemExit(f"없는 id: {oid}")
    if r["visibility"] == "hidden":
        raise SystemExit("이미 숨김")
    conn.execute(f"UPDATE {table[0]} SET body=NULL, visibility='hidden' WHERE id=?", (oid,))
    return ledger.emit(conn, "op_hidden", "operator", oid, {"reason": reason})


def notice(conn, kind: str, title: str, body: str) -> dict:
    t = now()
    if kind == "op_event":
        lo = iso(t - dt.timedelta(days=7))
        n = conn.execute("SELECT COUNT(*) FROM events WHERE type='op_event' AND at>=?", (lo,)).fetchone()[0]
        if n >= C.OP_EVENT_WEEKLY_CAP:
            raise SystemExit(f"행사는 주 {C.OP_EVENT_WEEKLY_CAP}회 상한 (최근 7일 {n}건)")
    # 공지·행사 id 접두어는 spec README 1절 목록에 없다. nt_ 를 새로 쓰고 PLAN 변경 이력에 적었다
    nid = "nt_" + new_id("mb")[3:]
    conn.execute("INSERT INTO notices VALUES (?,?,?,?,?)", (nid, kind, title, body, iso(t)))
    return ledger.emit(conn, kind, "operator", nid, {"title": title, "body": body})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plaza-admin")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hide")
    h.add_argument("id")
    h.add_argument("--reason", required=True)
    for name in ("notice", "event"):
        p = sub.add_parser(name)
        p.add_argument("--title", required=True)
        p.add_argument("--body", required=True)
    a = ap.parse_args(argv)
    conn = DB.connect(a.db)
    conn.execute("BEGIN IMMEDIATE")
    try:
        if a.cmd == "hide":
            ev = hide(conn, a.id, a.reason)
        else:
            ev = notice(conn, "op_notice" if a.cmd == "notice" else "op_event", a.title, a.body)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    print(json.dumps({"ok": True, "event": ev["id"], "type": ev["type"], "subject": ev["subject"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
