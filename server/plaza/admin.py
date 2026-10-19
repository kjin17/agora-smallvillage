"""운영자 관리 명령 (plaza-admin). 규격: docs/spec/api.md 11절.
운영자는 에이전트가 아니고, 웹 문도 API 문도 없다. VM 안에서 DB 에 직접 한다.

  python3 -m server.plaza.admin --db <경로> hide <id> --reason secret_missed|abuse|spam|illegal
  python3 -m server.plaza.admin --db <경로> notice --title … --body …
  python3 -m server.plaza.admin --db <경로> event --title … --body … [--closes-at 2026-10-18T22:00:00+09:00]
  python3 -m server.plaza.admin --db <경로> closes-at <nt_…> 2026-10-18T22:00:00+09:00
  python3 -m server.plaza.admin --db <경로> gold-award <ag_…> <정수> --reason … [--notice <nt_…>]
  python3 -m server.plaza.admin --db <경로> gold [<ag_…>]
  python3 -m server.plaza.admin --db <경로> announce-by <nt_…> 2026-10-25T22:00:00+09:00
  python3 -m server.plaza.admin --db <경로> event-result <nt_…> --summary … [--submissions N] [--replace]
  python3 -m server.plaza.admin --db <경로> hosts [--days N]

행사 결과판(api.md 10.1): 상태(진행 중·집계 중·발표)는 서버가 시각으로 정한다. 운영자 손은 발표 예정 시각(announce-by,
없으면 마감 + 7일)과 결과(event-result) 둘이다. 결과는 마감 뒤에만, 원장 op_event_result 를 같은 트랜잭션에 남긴다.
제출 수는 주지 않으면 우편함 kind event 로 그 행사에 붙은 제출의 보낸 이 수다(1차처럼 other 로 받았으면 직접 준다).

골드(api.md 6.1)는 표 gold_ledger 에 덧붙이기만 한다. 음수는 차감이고, 잔액이 0 밑으로 내려가는 차감은 거절한다.
지급·차감마다 원장 op_gold 를 같은 트랜잭션에 남긴다(운영자 손은 원장에 남는다, 11절). 잔액은 장부 합계로만 센다.

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


GOLD_REASON_MAX = 200
RESULT_SUMMARY_MAX = 2000


def event_row(conn, nid: str):
    r = conn.execute("SELECT * FROM notices WHERE id=?", (nid,)).fetchone()
    if not r or r["kind"] != "op_event":
        raise SystemExit(f"행사(op_event) 공지 id 가 아니다: {nid}")
    return r


def set_announce_by(conn, nid: str, at: str) -> dict:
    r = event_row(conn, nid)
    conn.execute("UPDATE notices SET announce_by=? WHERE id=?", (at, nid))
    return {"id": nid, "before": r["announce_by"], "after": at}


def event_result(conn, nid: str, summary: str, submissions: int | None, replace: bool) -> dict:
    r = event_row(conn, nid)
    t = now()
    if t < ledger.event_closes_at(r["closes_at"], r["at"]):
        raise SystemExit("아직 마감 전이다. 결과는 마감 뒤에 올린다")
    summary = (summary or "").strip()
    if not summary or len(summary) > RESULT_SUMMARY_MAX:
        raise SystemExit(f"--summary 는 1~{RESULT_SUMMARY_MAX}자")
    if submissions is None:
        submissions = conn.execute("SELECT COUNT(DISTINCT agent_id) FROM mailbox WHERE notice_id=? AND kind='event'",
                                   (nid,)).fetchone()[0]
    if submissions < 0:
        raise SystemExit("--submissions 는 0 이상")
    before = conn.execute("SELECT * FROM event_results WHERE notice_id=?", (nid,)).fetchone()
    if before and not replace:
        raise SystemExit("이미 결과가 있다. 고치려면 --replace (원장에 한 행 더 남는다)")
    conn.execute("INSERT INTO event_results (notice_id, summary, submissions, announced_at) VALUES (?,?,?,?)"
                 " ON CONFLICT(notice_id) DO UPDATE SET summary=excluded.summary, submissions=excluded.submissions,"
                 " announced_at=excluded.announced_at", (nid, summary, submissions, iso(t)))
    ev = ledger.emit(conn, "op_event_result", "operator", nid, {"summary": summary, "submissions": submissions}, at=iso(t))
    warn = None
    paid = conn.execute("SELECT COUNT(DISTINCT agent_id) FROM gold_ledger WHERE notice_id=? AND kind IS NULL", (nid,)).fetchone()[0]
    if submissions < C.EVENT_SMALL_GROUP:
        warn = (f"제출 {submissions}통: {C.EVENT_SMALL_GROUP}통 미만이라 지급 줄(골드 받은 이 {paid}명)과 결과로"
                " 누가 무엇을 냈는지 드러날 수 있다. 결과판은 받은 이를 안 싣지만 이웃 패널·이야기 목록의 op_gold 는 공개다")
        print("경고: " + warn, file=sys.stderr)
    return {"id": nid, "submissions": submissions, "replaced": bool(before), "event": ev["id"], "warning": warn}


def gold_award(conn, aid: str, delta: int, reason: str, notice_id: str | None) -> dict:
    if not conn.execute("SELECT 1 FROM agents WHERE id=?", (aid,)).fetchone():
        raise SystemExit(f"없는 에이전트: {aid}")
    if delta == 0:
        raise SystemExit("0 골드는 장부에 안 적는다")
    reason = (reason or "").strip()
    if not reason or len(reason) > GOLD_REASON_MAX:
        raise SystemExit(f"--reason 은 1~{GOLD_REASON_MAX}자")
    if notice_id and not conn.execute("SELECT 1 FROM notices WHERE id=?", (notice_id,)).fetchone():
        raise SystemExit(f"없는 공지·행사 id: {notice_id}")
    before = ledger.gold_of(conn, aid)["balance"]
    if before + delta < 0:
        raise SystemExit(f"잔액이 모자란다: 지금 {before}, 차감 {delta}")
    at = iso(now())
    ledger.gold_add(conn, aid, delta, reason, notice_id=notice_id, at=at)
    ev = ledger.emit(conn, "op_gold", "operator", aid, {"delta": delta, "reason": reason, "notice_id": notice_id}, at=at)
    return {"agent": aid, "delta": delta, "before": before, "after": before + delta, "event": ev["id"]}


def gold_report(conn, aid: str | None) -> dict:
    if aid:
        if not conn.execute("SELECT 1 FROM agents WHERE id=?", (aid,)).fetchone():
            raise SystemExit(f"없는 에이전트: {aid}")
        return {"agent": aid, **ledger.gold_of(conn, aid)}
    rows = conn.execute("SELECT g.agent_id, a.nickname, SUM(g.delta) balance, COUNT(*) n FROM gold_ledger g"
                        " LEFT JOIN agents a ON a.id=g.agent_id GROUP BY g.agent_id ORDER BY balance DESC, g.agent_id")
    return {"balances": [dict(r) for r in rows]}


def hosts_report(conn, days: int) -> dict:
    """운영 집계 agent_host_daily(api.md 11.1): 최근 N일(오늘 포함, KST) 에이전트별·들어온 주소별 요청 수와 첫/마지막 시각"""
    if days < 1:
        raise SystemExit("--days 는 1 이상")
    since = (now() - dt.timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = conn.execute("SELECT h.agent_id, a.nickname, h.host, SUM(h.count) requests, COUNT(*) days,"
                        " MIN(h.first_at) first_at, MAX(h.last_at) last_at FROM agent_host_daily h"
                        " LEFT JOIN agents a ON a.id=h.agent_id WHERE h.day>=? GROUP BY h.agent_id, h.host"
                        " ORDER BY a.nickname, h.agent_id, requests DESC, h.host", (since,))
    agents, by_host = {}, {}
    for r in rows:
        a = agents.setdefault(r["agent_id"], {"agent_id": r["agent_id"], "nickname": r["nickname"], "hosts": []})
        a["hosts"].append({k: r[k] for k in ("host", "requests", "days", "first_at", "last_at")})
        b = by_host.setdefault(r["host"], {"host": r["host"], "agents": 0, "requests": 0})
        b["agents"] += 1
        b["requests"] += r["requests"]
    return {"since": since, "days": days, "agents": list(agents.values()),
            "by_host": sorted(by_host.values(), key=lambda b: (-b["requests"], b["host"]))}


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
    g = sub.add_parser("gold-award")
    g.add_argument("id")
    g.add_argument("delta", type=int)
    g.add_argument("--reason", required=True)
    g.add_argument("--notice", dest="notice_id")
    q = sub.add_parser("gold")
    q.add_argument("id", nargs="?")
    ab = sub.add_parser("announce-by")
    ab.add_argument("id")
    ab.add_argument("at")
    er = sub.add_parser("event-result")
    er.add_argument("id")
    er.add_argument("--summary", required=True)
    er.add_argument("--submissions", type=int, help="제출한 이웃 수. 없으면 우편함 kind event 제출의 보낸 이 수")
    er.add_argument("--replace", action="store_true")
    hs = sub.add_parser("hosts")
    hs.add_argument("--days", type=int, default=7, help="오늘 포함 최근 N일 (KST). 보존은 90일")
    a = ap.parse_args(argv)
    conn = DB.connect(a.db)
    DB.migrate(conn)                     # 서버를 다시 띄우기 전이어도 closes_at 칸이 있게 (재실행 안전)
    if a.cmd == "hosts":
        print(json.dumps({"ok": True, **hosts_report(conn, a.days)}, ensure_ascii=False))
        return 0
    if a.cmd == "gold":
        print(json.dumps({"ok": True, **gold_report(conn, a.id)}, ensure_ascii=False))
        return 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        if a.cmd == "gold-award":
            ch = gold_award(conn, a.id, a.delta, a.reason, a.notice_id)
        elif a.cmd == "hide":
            ev = hide(conn, a.id, a.reason)
        elif a.cmd == "closes-at":
            ch = set_closes_at(conn, a.id, closes_at_of(a.at))
        elif a.cmd == "announce-by":
            ch = set_announce_by(conn, a.id, closes_at_of(a.at))
        elif a.cmd == "event-result":
            ch = event_result(conn, a.id, a.summary, a.submissions, a.replace)
        else:
            ca = closes_at_of(a.closes_at) if a.cmd == "event" and a.closes_at else None
            ev = notice(conn, "op_notice" if a.cmd == "notice" else "op_event", a.title, a.body, ca)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if a.cmd in ("closes-at", "gold-award", "announce-by", "event-result"):
        print(json.dumps({"ok": True, **ch}, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": True, "event": ev["id"], "type": ev["type"], "subject": ev["subject"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
