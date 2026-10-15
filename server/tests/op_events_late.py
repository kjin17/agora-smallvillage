"""digest `events` — 가입 전에 열린, 아직 마감 전인 운영 행사 (api.md 7.3, 2026-10-15). 새 임시 서버에서 HTTP 로 잰다.

  python3 -m server.tests.op_events_late

A·B·C 가 가입하고 행사 E1(--closes-at 지금+3일)이 열린 뒤 L·M·N 이 가입한다(실제 사고: 행사를 연 뒤 들어온 셋이
첫 digest 를 읽고도 행사를 못 받았다).
- 늦게 온 L: 한 번 받고, 그 응답의 next_cursor 를 보내면(앞으로 옮기면) 다음엔 없다. 커서 없이 불러도 없다
- 응답 유실 M: 커서를 안 보내면(받았다고 안 하면) 다시 받는다. 커서를 보내면 그 뒤엔 없다
- 커서로 이미 받은 A: 다시 안 온다(전달 기록도 안 생긴다). 아직 안 읽은 B: 커서 경로로 한 번만
- 마감 뒤: 커서 경로(C)로도, 늦은 경로(N)로도 안 온다
- --closes-at 없는 행사 E2 는 연 시각 + 7일이 마감: 6일 뒤 늦게 온 이는 받고, 7일+1시간 뒤엔 안 받는다
- plaza-admin: 지난 마감 거부, closes-at 으로 이미 연 행사의 마감 고침(행사 아닌 id 거부), closes_at 칸 없는 옛 DB 이전
옛 판(전달 기록·마감이 없는 서버)에 대 보면 L·M 이 받는 판정과 마감 판정이 실패해야 한다."""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import tempfile
from pathlib import Path

from .harness import REPO, Checks, Server
from .op_events import _admin, _ev, _ids
from .scenario import jrid

KST = dt.timezone(dt.timedelta(hours=9))
CHARS = ("merchant", "philosopher", "scholar", "messenger", "robot", "gardener", "scribe", "watchman", "chef")
HOUR = 3660           # 방문 간격(30분)을 넘겨 새 방문 사건이 원장에 남게 한다 — 운영의 「다음 방문」과 같은 모양


def _now(S: Server) -> dt.datetime:
    return dt.datetime.now(KST).replace(microsecond=0) + dt.timedelta(seconds=S.offset)


def _db(S: Server, sql: str, args=()) -> list:
    conn = sqlite3.connect(str(S.db), timeout=10)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _admin_err(S: Server, *args) -> str:
    try:
        _admin(S, *args)
    except RuntimeError as e:
        return str(e)
    return ""


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        out = _run(S, C)
    finally:
        S.stop()
    migrate(C)
    return out


def _run(S: Server, C: Checks) -> dict:
    print("── digest events: 가입 전에 열린 마감 전 행사 ──")
    k, i = {}, {}

    chars = iter(CHARS)

    def join(who, nick, _ch=None):
        S.advance(HOUR)                                             # 같은 IP 가입 시간 3회 상한 밖으로
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": next(chars),
                                      "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]

    def dg(who, cursor=None):
        return S.get("/api/v1/me/digest" + (f"?cursor={cursor}" if cursor else ""), key=k[who])

    for who, nick in (("A", "먼저 읽은 장터"), ("B", "아직 안 읽은 먹줄"), ("C", "늦게 읽는 다림추")):
        join(who, nick, "gardener")
    S.advance(60)
    closes = (_now(S) + dt.timedelta(days=3)).isoformat()
    e1 = _admin(S, "event", "--title", "같은 이웃일까", "--body", "마감은 사흘 뒤", "--closes-at", closes)
    nid = e1["subject"]
    C.check("admin: --closes-at 이 notices.closes_at 에 저장된다",
            _db(S, "SELECT closes_at FROM notices WHERE id=?", (nid,)) == [(closes,)],
            str(_db(S, "SELECT closes_at FROM notices WHERE id=?", (nid,))))
    S.advance(60)
    a1 = dg("A")
    C.check("A(가입 후 열린 행사): 커서 창으로 한 번, closes_at 이 실린다",
            _ids(a1) == [nid] and (_ev(a1) or [{}])[0].get("closes_at") == closes, str(_ev(a1))[:300])
    dg("A", a1["next_cursor"])

    S.advance(60)
    for who, nick in (("L", "이음표"), ("M", "영점의시인"), ("N", "노이즈필터")):
        join(who, nick, "scribe")
        S.advance(60)

    # ── 늦게 온 L: 한 번, 커서를 보내면 끝 ──
    S.advance(HOUR)
    l1 = dg("L")
    C.check("L(가입 전에 열린 마감 전 행사): 첫 digest 에 한 번 온다", _ids(l1) == [nid], str(_ids(l1)))
    C.check("L: 실린 행사에 closes_at·전문", (_ev(l1) or [{}])[0].get("closes_at") == closes
            and (_ev(l1) or [{}])[0].get("body") == "마감은 사흘 뒤", str(_ev(l1))[:300])
    C.check("L: items 가 비고 행사만 있으면 empty_reason nothing_to_me",
            (l1.json or {}).get("empty_reason") == "nothing_to_me", str((l1.json or {}).get("empty_reason")))
    l2 = dg("L", l1["next_cursor"])
    C.check("L: 그 응답의 next_cursor 를 보낸 두 번째 digest 엔 없다", l2.status == 200 and _ev(l2) == [], str(_ids(l2)))
    l3 = dg("L")
    C.check("L: 확정 뒤엔 커서 없이 불러도 없다", _ev(l3) == [], str(_ids(l3)))
    acked = _db(S, "SELECT acked_at IS NOT NULL FROM event_deliveries WHERE agent_id=? AND notice_id=?", (i["L"], nid))
    C.check("L: 전달 기록이 확정(acked_at)으로 남는다", acked == [(1,)], str(acked))

    # ── 응답 유실 M: 커서를 안 보내면 다시 온다 ──
    m1 = dg("M")
    C.check("M: 첫 digest 에 한 번 온다", _ids(m1) == [nid], str(_ids(m1)))
    C.check("M: 확정 전 전달 기록은 대기(acked_at NULL)",
            _db(S, "SELECT acked_at FROM event_deliveries WHERE agent_id=?", (i["M"],)) == [(None,)],
            str(_db(S, "SELECT acked_at FROM event_deliveries WHERE agent_id=?", (i["M"],))))
    S.advance(60)
    m2 = dg("M")                                                    # m1 응답을 잃었다고 보고 커서 없이 다시
    C.check("M: 커서를 안 보내면(응답 유실) 같은 행사를 다시 받는다", _ids(m2) == [nid], str(_ids(m2)))
    m3 = dg("M", m1["next_cursor"])                                 # 늦게라도 첫 응답의 커서를 보내면 확정
    m4 = dg("M")
    C.check("M: 실은 응답의 커서를 보내면 확정되고 그 뒤엔 없다", _ev(m3) == [] and _ev(m4) == [], f"{_ids(m3)} {_ids(m4)}")

    # ── 기존 멤버: 커서로 받은 A 는 다시 안, 안 읽은 B 는 커서 경로로 한 번 ──
    a2 = dg("A")
    C.check("A(커서로 이미 받음): 다시 안 온다", _ev(a2) == [], str(_ids(a2)))
    b1 = dg("B")
    C.check("B(안 읽은 기존 멤버): 커서 경로로 한 번", _ids(b1) == [nid], str(_ids(b1)))
    b2 = dg("B", b1["next_cursor"])
    C.check("B: 커서를 보내면 다음엔 없다(중복 없음)", _ev(b2) == [], str(_ids(b2)))
    rows = _db(S, "SELECT agent_id FROM event_deliveries WHERE agent_id IN (?,?)", (i["A"], i["B"]))
    C.check("A·B: 가입 후 행사엔 전달 기록이 안 생긴다(두 길이 안 겹친다)", rows == [], str(rows))

    # ── 마감 뒤: 어느 길로도 안 온다 ──
    S.advance(3 * 24 * 3600)
    c1 = dg("C")
    C.check("C(커서 경로, 마감 뒤에야 읽음): 마감 지난 행사는 안 온다", nid not in _ids(c1), str(_ids(c1)))
    n1 = dg("N")
    C.check("N(늦게 온, 마감 뒤에야 읽음): 마감 지난 행사는 안 온다", nid not in _ids(n1), str(_ids(n1)))
    for who, d in (("C", c1), ("N", n1)):
        dg(who, d["next_cursor"])

    # ── --closes-at 없는 행사: 연 시각 + 7일 ──
    S.advance(5 * 24 * 3600)                                        # E1 로부터 8일 넘게 — 주 1회 상한 밖
    e2 = _admin(S, "event", "--title", "마감 안 적은 행사", "--body", "기본 마감")
    nid2 = e2["subject"]
    opened = _db(S, "SELECT at, closes_at FROM notices WHERE id=?", (nid2,))[0]
    C.check("admin: --closes-at 없이 열면 closes_at 은 비어 있다(기본값을 써 넣지 않는다)", opened[1] is None, str(opened))
    S.advance(60)
    join("P", "엿새 뒤 온 이", "scribe")
    join("R", "이레 뒤 온 이", "scribe")
    S.advance(6 * 24 * 3600)
    p1 = dg("P")
    want = (dt.datetime.fromisoformat(opened[0]) + dt.timedelta(days=7)).isoformat()
    C.check("기본 마감: 6일 뒤 읽으면 아직 온다, closes_at = 연 시각 + 7일",
            _ids(p1) == [nid2] and (_ev(p1) or [{}])[0].get("closes_at") == want, str(_ev(p1))[:300])
    S.advance(24 * 3600 + HOUR)
    r1 = dg("R")
    C.check("기본 마감: 7일+1시간 뒤엔 안 온다", nid2 not in _ids(r1), str(_ids(r1)))

    # ── plaza-admin ──
    past = (_now(S) - dt.timedelta(hours=1)).isoformat()
    C.check("admin: 지난 마감은 거부", "마감이 이미 지났다" in _admin_err(S, "closes-at", nid2, past), past)
    C.check("admin: 형식이 틀린 마감은 거부", "ISO8601" in _admin_err(S, "closes-at", nid2, "다음주"), "")
    fut = (_now(S) + dt.timedelta(days=2)).isoformat()
    ch = _admin(S, "closes-at", nid2, fut)
    C.check("admin closes-at: 이미 연 행사의 마감을 고치고 전후 값을 낸다",
            ch.get("before") is None and ch.get("after") == fut
            and _db(S, "SELECT closes_at FROM notices WHERE id=?", (nid2,)) == [(fut,)], str(ch))
    r2 = dg("R")
    C.check("admin closes-at: 마감을 늘리면 늦게 온 R 도 받는다", _ids(r2) == [nid2], str(_ids(r2)))
    notice = _admin(S, "notice", "--title", "공지", "--body", "행사 아님")
    C.check("admin closes-at: 행사가 아닌 공지 id 는 거부",
            "행사(op_event)" in _admin_err(S, "closes-at", notice["subject"], fut), "")
    return {"e1": nid, "e2": nid2}


OLD_NOTICES = "CREATE TABLE notices (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL)"


def migrate(C: Checks) -> None:
    """closes_at 칸이 없는 옛 DB(운영판 a3999af 와 같은 모양)에 DB.init 이 칸과 전달 기록 표를 더하고 행을 지키는지. 두 번 돌려도 안전."""
    sys.path.insert(0, str(REPO))
    from server.plaza import db as DB
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "old.db")
        conn = sqlite3.connect(p)
        conn.execute(OLD_NOTICES)
        conn.execute("INSERT INTO notices VALUES ('nt_old','op_event','옛 행사','본문','2026-10-15T21:56:00+09:00')")
        conn.commit()
        conn.close()
        DB.init(p)
        DB.init(p)
        conn = sqlite3.connect(p)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(notices)")]
        row = conn.execute("SELECT id, title, closes_at FROM notices").fetchall()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
    C.check("이전: 옛 notices 에 closes_at 칸이 붙고 행은 그대로(NULL), 두 번 돌려도 안전",
            cols[-1] == "closes_at" and cols.count("closes_at") == 1 and row == [("nt_old", "옛 행사", None)], f"{cols} {row}")
    C.check("이전: event_deliveries 표가 생긴다", "event_deliveries" in tables, str(sorted(tables)))


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
