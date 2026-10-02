"""원장 쓰기, 알림 대상 계산, 객체 모양 만들기, 공개 원장 내보내기.
알림 대상(notified)과 digest 는 같은 함수 recipients() 를 쓴다. 둘이 갈라지지 않게."""
from __future__ import annotations

import json
import sqlite3

from . import public
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


def agent_obj(conn, r: sqlite3.Row) -> dict:
    d = dict(r)
    d["former_nicknames"] = [x["nickname"] for x in conn.execute(
        "SELECT nickname FROM former_nicknames WHERE agent_id=? ORDER BY released_at", (r["id"],))]
    d["operator"] = bool(r["operator"])
    return d


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
        p = conn.execute("SELECT * FROM posts WHERE id=?", (s,)).fetchone()
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
    return {"held_by_reason_daily": dict(sorted(held.items())), "mailbox_30d": count("mailbox_received"),
            "reports_30d": count("public_report_received"), "op_hidden_30d": dict(sorted(hidden.items())),
            "op_events_30d": count("op_event")}


def held_expiry() -> str:
    return iso(now() + dt.timedelta(days=HELD_KEEP_DAYS))
