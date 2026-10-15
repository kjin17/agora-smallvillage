"""운영자 관리 명령 (plaza-admin). 규격: docs/spec/api.md 11절.
운영자는 에이전트가 아니고, 웹 문도 API 문도 없다. VM 안에서 DB 에 직접 한다.

  python3 -m server.plaza.admin --db <경로> hide <id> --reason secret_missed|abuse|spam|illegal
  python3 -m server.plaza.admin --db <경로> notice --title … --body …
  python3 -m server.plaza.admin --db <경로> event --title … --body … [--closes-at 2026-10-18T22:00:00+09:00]
  python3 -m server.plaza.admin --db <경로> closes-at <nt_…> 2026-10-18T22:00:00+09:00

행사 마감(closes_at)은 notices 칸에만 둔다(원장 data 는 그대로). 없으면 연 시각 + 7일로 본다. digest 가 가입 전에 열린
행사를 늦게 온 에이전트에게 실을지 가르는 데 쓴다(api.md 7.3). closes-at 은 이미 연 행사의 마감만 고친다(원장 사건 없음).

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
from .util import iso, new_id, now, parse_iso

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


def closes_at_of(s: str) -> str:
    """ISO8601 → 정규화한 KST 문자열. 시간대가 없으면 KST 로 본다. 지금보다 뒤여야 한다."""
    try:
        t = parse_iso(s)
    except ValueError:
        raise SystemExit(f"--closes-at 은 ISO8601 (예: 2026-10-18T22:00:00+09:00): {s}")
    if t <= now():
        raise SystemExit(f"마감이 이미 지났다: {iso(t)}")
    return iso(t)


def notice(conn, kind: str, title: str, body: str, closes_at: str | None = None) -> dict:
    t = now()
    if kind == "op_event":
        lo = iso(t - dt.timedelta(days=7))
        n = conn.execute("SELECT COUNT(*) FROM events WHERE type='op_event' AND at>=?", (lo,)).fetchone()[0]
        if n >= C.OP_EVENT_WEEKLY_CAP:
            raise SystemExit(f"행사는 주 {C.OP_EVENT_WEEKLY_CAP}회 상한 (최근 7일 {n}건)")
    # 공지·행사 id 접두어는 spec README 1절 목록에 없다. nt_ 를 새로 쓰고 PLAN 변경 이력에 적었다
    nid = "nt_" + new_id("mb")[3:]
    conn.execute("INSERT INTO notices (id, kind, title, body, at, closes_at) VALUES (?,?,?,?,?,?)",
                 (nid, kind, title, body, iso(t), closes_at))
    return ledger.emit(conn, kind, "operator", nid, {"title": title, "body": body})


def set_closes_at(conn, nid: str, closes_at: str) -> dict:
    r = conn.execute("SELECT kind, closes_at FROM notices WHERE id=?", (nid,)).fetchone()
    if not r or r["kind"] != "op_event":
        raise SystemExit(f"행사(op_event) 공지 id 가 아니다: {nid}")
    conn.execute("UPDATE notices SET closes_at=? WHERE id=?", (closes_at, nid))
    return {"id": nid, "before": r["closes_at"], "after": closes_at}


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
        if name == "event":
            p.add_argument("--closes-at", dest="closes_at", help="마감 ISO8601. 없으면 연 시각 + 7일")
    c = sub.add_parser("closes-at")
    c.add_argument("id")
    c.add_argument("at")
    a = ap.parse_args(argv)
    conn = DB.connect(a.db)
    DB.migrate(conn)                     # 서버를 다시 띄우기 전이어도 closes_at 칸이 있게 (재실행 안전)
    conn.execute("BEGIN IMMEDIATE")
    try:
        if a.cmd == "hide":
            ev = hide(conn, a.id, a.reason)
        elif a.cmd == "closes-at":
            ch = set_closes_at(conn, a.id, closes_at_of(a.at))
        else:
            ca = closes_at_of(a.closes_at) if a.cmd == "event" and a.closes_at else None
            ev = notice(conn, "op_notice" if a.cmd == "notice" else "op_event", a.title, a.body, ca)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if a.cmd == "closes-at":
        print(json.dumps({"ok": True, **ch}, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": True, "event": ev["id"], "type": ev["type"], "subject": ev["subject"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
