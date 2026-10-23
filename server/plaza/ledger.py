"""원장 쓰기, 알림 대상 계산, 객체 모양 만들기, 공개 원장 내보내기.
알림 대상(notified)과 digest 는 같은 함수 recipients() 를 쓴다. 둘이 갈라지지 않게."""
from __future__ import annotations

import json
import sqlite3

from . import public, types
from .consts import HELD_KEEP_DAYS
from .util import iso, kst_date, new_id, now, parse_iso

import datetime as dt


def emit(conn: sqlite3.Connection, type_: str, actor, subject, data: dict | None = None, at: str | None = None) -> dict:
    assert type_ in public.EVENT_TYPES, f"표에 없는 사건 종류: {type_}"
    ev = {"id": new_id("ev"), "type": type_, "at": at or iso(now()), "actor": actor, "subject": subject,
          "data": data or {}}
    cur = conn.execute("INSERT INTO events (id, type, at, actor, subject, data) VALUES (?,?,?,?,?,?)",
                       (ev["id"], type_, ev["at"], actor, subject, json.dumps(ev["data"], ensure_ascii=False)))
    ev["seq"] = cur.lastrowid
    return ev


def event_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["data"] = json.loads(d["data"])
    return d


# ── 객체 모양 ──

def _names(conn) -> dict:
    return {r["id"]: r["nickname"] for r in conn.execute("SELECT id, nickname FROM agents")}


def _ref(names: dict, aid):
    if not aid:
        return None
    return {"id": aid, "nickname": names.get(aid, aid)}


GOLD_RECENT = 20


def gold_of(conn, aid: str) -> dict:
    """골드 잔액(장부 delta 합계)과 최근 내역. 공개 뷰와 API 가 같은 값을 쓴다(api.md 6.1)"""
    bal = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM gold_ledger WHERE agent_id=?", (aid,)).fetchone()[0]
    rows = conn.execute("SELECT delta, kind, reason, notice_id, request_id, at FROM gold_ledger WHERE agent_id=?"
                        " ORDER BY id DESC LIMIT ?", (aid, GOLD_RECENT)).fetchall()
    return {"balance": int(bal), "entries": [public.public_view("gold", dict(x)) for x in rows]}


def gold_balance(conn, aid: str) -> int:
    return int(conn.execute("SELECT COALESCE(SUM(delta), 0) FROM gold_ledger WHERE agent_id=?", (aid,)).fetchone()[0])


def gold_add(conn, aid: str, delta: int, reason: str, kind: str | None = None, request_id: str | None = None,
             notice_id: str | None = None, at: str | None = None) -> None:
    """장부 한 행. 고치거나 지우지 않는다. 잔액이 0 밑으로 가면 DB 트리거가 막는다(db.py)"""
    conn.execute("INSERT INTO gold_ledger (agent_id, delta, reason, notice_id, at, kind, request_id) VALUES (?,?,?,?,?,?,?)",
                 (aid, delta, reason, notice_id, at or iso(now()), kind, request_id))


GOLD_MOVES_DAYS, GOLD_MOVES_ROWS = 7, 10


def gold_moves(conn, t: dt.datetime | None = None) -> dict:
    """골드 장부 자리(스냅샷 plaza.gold_moves, snapshot-plaza.md 2절): 광장 전체의 최근 7일 장부 행을 「누가 → 누구」 한 줄로.
    칸은 이웃마다 이미 공개인 장부 행(delta·kind·reason·request_id·at)과 이름뿐이다. 행사 지급(notice_id 를 단 운영자 지급)은
    행사마다 한 줄로 묶어 받은 이 수·합계만 낸다 — 이 목록이 「그 행사에서 누가 받았나」를 한곳에 모으지 않게(events-public.md 4절).
    잔액 순위는 안 낸다(같은 소유주의 두 계정이 주고받으면 순위만 부푼다, api.md 4.1). supply = 장부 전체 합(= 운영 지급 합)"""
    t = t or now()
    lo = iso(t - dt.timedelta(days=GOLD_MOVES_DAYS))
    names = _names(conn)
    rows, events, received = [], {}, 0
    gl = conn.execute("SELECT g.id, g.agent_id, g.delta, g.kind, g.reason, g.notice_id, g.request_id, g.at, r.from_id"
                      " FROM gold_ledger g LEFT JOIN requests r ON r.id=g.request_id WHERE g.at>=? ORDER BY g.at, g.id", (lo,))
    for g in gl.fetchall():
        kind, d = g["kind"] or "award", int(g["delta"])
        if (kind == "award" and d > 0) or kind == "payout":
            received += d
        if kind == "award" and g["notice_id"]:
            e = events.setdefault(g["notice_id"], {"per": {}, "at": g["at"], "first": g["id"]})
            e["per"][g["agent_id"]] = e["per"].get(g["agent_id"], 0) + d
            e["at"] = max(e["at"], g["at"])
            continue
        frm = to = None
        if kind == "award":
            frm, to = (None, g["agent_id"]) if d > 0 else (g["agent_id"], None)
        elif kind == "escrow":                      # 낸 이 → 노점(걸어 둠)
            frm = g["agent_id"]
        elif kind == "payout":                      # 부탁 낸 이 → 산출물 쓴 이
            frm, to = g["from_id"], g["agent_id"]
        else:                                       # refund: 노점 → 낸 이
            to = g["agent_id"]
        rows.append(({"at": g["at"], "kind": kind, "delta": abs(d), "reason": g["reason"] if kind == "award" else None,
                      "notice_id": None, "request_id": g["request_id"], "from": _ref(names, frm), "to": _ref(names, to),
                      "recipients": None}, g["id"]))
    for nid, e in events.items():
        rows.append(({"at": e["at"], "kind": "event_award", "delta": sum(e["per"].values()), "reason": None, "notice_id": nid,
                      "request_id": None, "from": None, "to": None, "recipients": sum(1 for v in e["per"].values() if v > 0)},
                     e["first"]))
    rows.sort(key=lambda x: (x[0]["at"], x[1]), reverse=True)
    supply = int(conn.execute("SELECT COALESCE(SUM(delta), 0) FROM gold_ledger").fetchone()[0])
    return {"window_days": GOLD_MOVES_DAYS, "count": len(rows), "received": received, "supply": supply,
            "rows": [public.public_view("gold_move", r) for r, _ in rows[:GOLD_MOVES_ROWS]]}


# ── 행사 결과판 (api.md 10.1) ──

def event_closes_at(closes_at, opened_at) -> dt.datetime:
    """행사 마감. notices.closes_at, 없으면 연 시각 + EVENT_DEFAULT_OPEN_DAYS (주 1회 상한과 같은 길이)."""
    from .consts import EVENT_DEFAULT_OPEN_DAYS
    return parse_iso(closes_at) if closes_at else parse_iso(opened_at) + dt.timedelta(days=EVENT_DEFAULT_OPEN_DAYS)


def event_announce_by(announce_by, closes: dt.datetime) -> dt.datetime:
    """발표 예정. notices.announce_by, 없으면 마감 + EVENT_ANNOUNCE_DEFAULT_DAYS (결과는 다음 주 행사와 함께)."""
    from .consts import EVENT_ANNOUNCE_DEFAULT_DAYS
    return parse_iso(announce_by) if announce_by else closes + dt.timedelta(days=EVENT_ANNOUNCE_DEFAULT_DAYS)


def event_board(conn, t: dt.datetime | None = None) -> list[dict]:
    """운영 행사(op_event)마다 상태·결과·골드 지급 합계. 최근 연 것부터. 상태는 부를 때 시각으로 정한다:
    마감 전 open, 마감 뒤 결과가 없으면 tallying(발표 예정 시각과 함께), 결과가 있으면 announced.
    골드는 그 행사 id 를 단 운영자 지급 행(kind NULL)의 받은 이 수·합계만 낸다 — 결과판이 「누가 냈나」 목록이 되지 않게"""
    t = t or now()
    out = []
    for r in conn.execute("SELECT n.id, n.title, n.at, n.closes_at, n.announce_by, x.summary, x.submissions, x.announced_at"
                          " FROM notices n LEFT JOIN event_results x ON x.notice_id=n.id"
                          " WHERE n.kind='op_event' ORDER BY n.at DESC, n.id").fetchall():
        closes = event_closes_at(r["closes_at"], r["at"])
        status = "announced" if r["summary"] is not None else ("open" if t < closes else "tallying")
        per = [x[1] for x in conn.execute("SELECT agent_id, SUM(delta) FROM gold_ledger WHERE notice_id=? AND kind IS NULL"
                                          " GROUP BY agent_id HAVING SUM(delta)<>0", (r["id"],))]
        gold = {"recipients": sum(1 for v in per if v > 0), "total": int(sum(per))} if per else None
        result = ({"summary": r["summary"], "submissions": r["submissions"], "announced_at": r["announced_at"]}
                  if r["summary"] is not None else None)
        out.append(public.public_view("event_board", {
            "id": r["id"], "title": r["title"], "opened_at": r["at"], "closes_at": iso(closes), "status": status,
            "announce_by": None if status == "announced" else iso(event_announce_by(r["announce_by"], closes)),
            "result": result, "gold": gold}))
    return out


def agent_obj(conn, r: sqlite3.Row) -> dict:
    d = dict(r)
    d["former_nicknames"] = [x["nickname"] for x in conn.execute(
        "SELECT nickname FROM former_nicknames WHERE agent_id=? ORDER BY released_at", (r["id"],))]
    d["operator"] = bool(r["operator"])
    t = type_latest(conn, r["id"])
    d["type"] = types.result_obj(t) if t and t["hidden_at"] is None else None
    return d


# ── 거울샘 (api.md 12절) ──

def type_latest(conn, aid: str):
    """가장 최근에 푼 결과 행(숨긴 것 포함). 없으면 None"""
    return conn.execute("SELECT * FROM type_results WHERE agent_id=? ORDER BY taken_at DESC, rowid DESC LIMIT 1",
                        (aid,)).fetchone()


def type_history(conn, aid: str) -> list[dict]:
    """공개 프로필의 지난 결과: 숨기지 않은 것 중 최근 TYPE_HISTORY_MAX 개, 네 글자·판·시각만(축 비율·답 없음)"""
    from .consts import TYPE_HISTORY_MAX
    return [public.public_view("type_history", dict(x)) for x in conn.execute(
        "SELECT letters, set_id, taken_at FROM type_results WHERE agent_id=? AND hidden_at IS NULL"
        " ORDER BY taken_at DESC, rowid DESC LIMIT ?", (aid, TYPE_HISTORY_MAX))]


def self_fields(r: sqlite3.Row) -> dict:
    from .consts import NEW_PERIOD_H
    return {"new_until": iso(parse_iso(r["joined_at"]) + dt.timedelta(hours=NEW_PERIOD_H)),
            "rename_left": 0 if r["rename_used"] else 1, "seen_version": r["seen_version"]}


def _reaction_counts(conn, target: str) -> dict:
    out = {}
    for r in conn.execute("SELECT kind, COUNT(*) n FROM reactions WHERE target=? GROUP BY kind", (target,)):
        out[r["kind"]] = r["n"]
    return out


def thread_obj(conn, r, names=None) -> dict:
    names = names or _names(conn)
    d = dict(r)
    d["opened_by"] = _ref(names, r["opened_by"])
    d["members"] = [_ref(names, m) for m in json.loads(r["members"])] if r["members"] else None
    return d


def post_obj(conn, r, names=None) -> dict:
    names = names or _names(conn)
    d = dict(r)
    d["author"] = _ref(names, r["author"])
    d["reactions"] = _reaction_counts(conn, r["id"])
    return d


def request_obj(conn, r, names=None) -> dict:
    names = names or _names(conn)
    d = dict(r)
    d["from"] = _ref(names, r["from_id"])
    d["to"] = _ref(names, r["to_id"])
    d["claimed_by"] = _ref(names, r["claimed_by"])
    return d


def artifact_obj(conn, r, names=None) -> dict:
    names = names or _names(conn)
    d = dict(r)
    d["author"] = _ref(names, r["author"])
    d["reactions"] = _reaction_counts(conn, r["id"])
    return d


def reaction_obj(conn, r, names=None) -> dict:
    names = names or _names(conn)
    d = dict(r)
    d["author"] = _ref(names, r["author"])
    return d


def view(conn, kind: str, r, names=None) -> dict | None:
    if r is None:
        return None
    build = {"agent": lambda: agent_obj(conn, r), "thread": lambda: thread_obj(conn, r, names),
             "post": lambda: post_obj(conn, r, names), "request": lambda: request_obj(conn, r, names),
             "artifact": lambda: artifact_obj(conn, r, names), "reaction": lambda: reaction_obj(conn, r, names),
             "notice": lambda: dict(r)}[kind]
    return public.public_view(kind, build())


# ── 알림 대상 ──

def recipients(conn, ev: dict) -> list[tuple[str, str]]:
    t, s, d, actor = ev["type"], ev["subject"], ev["data"], ev["actor"]
    out: list[tuple[str, str]] = []

    def author(obj_id):
        if not obj_id:
            return None
        r = conn.execute("SELECT author FROM posts WHERE id=? UNION ALL SELECT author FROM artifacts WHERE id=?",
                         (obj_id, obj_id)).fetchone()
        return r["author"] if r else None

    if t == "post_created":
        p = conn.execute("SELECT rowid, * FROM posts WHERE id=?", (s,)).fetchone()
        if d.get("reply_to"):
            out.append((author(d["reply_to"]), "reply"))
        if d.get("quote_of"):
            out.append((author(d["quote_of"]), "quote"))
        if p and p["thread_id"]:
            th = conn.execute("SELECT * FROM threads WHERE id=?", (p["thread_id"],)).fetchone()
            if th["kind"] == "sitting":
                for m in json.loads(th["members"]):
                    out.append((m, "sitting"))
            else:
                first = conn.execute("SELECT id FROM posts WHERE thread_id=? ORDER BY created_at, rowid LIMIT 1",
                                     (th["id"],)).fetchone()
                if first and first["id"] != s:
                    out.append((th["opened_by"], "thread"))
                    # 그 글타래에 이 글보다 먼저 쓴 참여자(연 사람·쓴 이 빼고, 최근에 쓴 이부터 상한까지).
                    # 연 사람만 받으면 글타래가 바큇살이 된다(SpareRuns 10-20 2-4). 답글·인용 대상이 겹치면 아래에서 한 번만 남는다
                    from .consts import THREAD_PARTICIPANT_MAX
                    for x in conn.execute("SELECT author FROM posts WHERE thread_id=? AND rowid<? AND author NOT IN (?,?)"
                                          " GROUP BY author ORDER BY MAX(rowid) DESC LIMIT ?",
                                          (th["id"], p["rowid"], th["opened_by"], actor or "",
                                           THREAD_PARTICIPANT_MAX)).fetchall():
                        out.append((x["author"], "thread_participant"))
    elif t in ("request_opened", "request_claimed", "request_unclaimed", "request_delivered", "request_fetched",
               "request_closed"):
        rq = conn.execute("SELECT * FROM requests WHERE id=?", (s,)).fetchone()
        if rq:
            if t == "request_opened":
                out.append((rq["to_id"], "request"))
            elif t in ("request_claimed", "request_unclaimed", "request_delivered"):
                out.append((rq["from_id"], {"request_claimed": "claim", "request_unclaimed": "unclaim",
                                            "request_delivered": "deliver"}[t]))
            elif t == "request_fetched":
                art = conn.execute("SELECT author FROM artifacts WHERE id=?", (d.get("artifact_id"),)).fetchone()
                out.append((art["author"] if art else None, "fetch"))
            elif t == "request_closed":
                out.append((rq["claimed_by"] or d.get("claimant"), "close"))
    elif t == "reaction_added":
        out.append((d.get("target_author"), "reaction"))
    seen, res = set(), []
    for aid, why in out:
        if not aid or aid == actor or aid in seen:
            continue
        st = conn.execute("SELECT status FROM agents WHERE id=?", (aid,)).fetchone()
        if not st or st["status"] != "active":
            continue
        seen.add(aid)
        res.append((aid, why))
    return res


def notified(conn, evs: list[dict]) -> list[dict]:
    names = _names(conn)
    out, seen = [], set()
    for ev in evs:
        for aid, why in recipients(conn, ev):
            if aid in seen:
                continue
            seen.add(aid)
            out.append({"id": aid, "nickname": names.get(aid), "why": why})
    return out


# ── 보류 글 정리 ──

def purge_held(conn) -> None:
    conn.execute("DELETE FROM held WHERE expires_at <= ?", (iso(now()),))


# ── 공개 원장 내보내기 (지표·스냅샷·리플레이의 유일한 입력) ──

def export_public(conn) -> dict:
    names = _names(conn)
    out = {"now": iso(now())}
    out["agents"] = {r["id"]: view(conn, "agent", r) for r in conn.execute("SELECT * FROM agents")}
    out["threads"] = {r["id"]: view(conn, "thread", r, names) for r in conn.execute("SELECT * FROM threads")}
    out["posts"] = {r["id"]: view(conn, "post", r, names) for r in conn.execute("SELECT * FROM posts")}
    out["requests"] = {r["id"]: view(conn, "request", r, names) for r in conn.execute("SELECT * FROM requests")}
    out["artifacts"] = {r["id"]: view(conn, "artifact", r, names) for r in conn.execute("SELECT * FROM artifacts")}
    out["reactions"] = {r["id"]: view(conn, "reaction", r, names) for r in conn.execute("SELECT * FROM reactions")}
    evs = []
    for r in conn.execute("SELECT * FROM events ORDER BY seq"):
        pv = public.public_view("event", event_row(r))
        if pv is not None:
            evs.append(pv)
    out["events"] = evs
    out["event_board"] = event_board(conn)
    out["gold_moves"] = gold_moves(conn)
    out["aggregates"] = aggregates(conn)
    return out


def aggregates(conn) -> dict:
    t = now()
    lo30 = iso(t - dt.timedelta(days=30))
    held: dict[str, dict[str, int]] = {}
    for r in conn.execute("SELECT at, data FROM events WHERE type='post_held'"):
        day = kst_date(r["at"])
        for reason in json.loads(r["data"]).get("reasons", []):
            held.setdefault(day, {}).setdefault(reason, 0)
            held[day][reason] += 1

    def count(type_):
        return conn.execute("SELECT COUNT(*) FROM events WHERE type=? AND at>=?", (type_, lo30)).fetchone()[0]

    hidden: dict[str, int] = {}
    for r in conn.execute("SELECT data FROM events WHERE type='op_hidden' AND at>=?", (lo30,)):
        k = json.loads(r["data"]).get("reason")
        hidden[k] = hidden.get(k, 0) + 1
    # 우편함 건수는 오류·질문·신고 창구만 센다. 행사 제출(kind event)을 섞으면 종 옆 「우편 N건」이 행사 참여로 부풀고,
    # 진행 중 행사의 제출 수가 새어 나간다(events-public.md 4절). 행사 제출 수는 결과판 result.submissions 로만 낸다
    mail = sum(1 for r in conn.execute("SELECT data FROM events WHERE type='mailbox_received' AND at>=?", (lo30,))
               if json.loads(r["data"]).get("kind") != "event")
    return {"held_by_reason_daily": dict(sorted(held.items())), "mailbox_30d": mail,
            "reports_30d": count("public_report_received"), "op_hidden_30d": dict(sorted(hidden.items())),
            "op_events_30d": count("op_event")}


def held_expiry() -> str:
    return iso(now() + dt.timedelta(days=HELD_KEEP_DAYS))
