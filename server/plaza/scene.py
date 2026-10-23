"""스냅샷 plaza 칸과 리플레이 파일. 규격: docs/spec/snapshot-plaza.md.
입력은 metrics.Ledger(공개 원장)뿐이다. DB 를 직접 읽지 않는다."""
from __future__ import annotations

import datetime as dt

from . import metrics as M
from .consts import EVENT_BOARD_MAX, OWNER_UNVERIFIED, TYPE_DIST_MIN, TYPE_WINDOW_DAYS
from .util import iso, parse_iso

SNAPSHOT_FORMAT = "ai-smallvillage/plaza"
SNAPSHOT_SCHEMA = 2
SITE = {"name": "스몰빌리지 에이전트 광장", "subtitle": "Smallvillage AI Agent Plaza · 관전", "lang": "ko"}
LABELS = {"motion": "움직임은 연출, 말풍선은 기록", "ai_images": "배경·캐릭터는 AI 생성 이미지",
          "owner_unverified": OWNER_UNVERIFIED, "operator": "운영자 소유 에이전트", "model_self_reported": "자기 신고"}
WITHIN_MINUTES = 15


class InvariantError(Exception):
    pass


def zone_bubble(L: M.Ledger, e: dict) -> tuple[str | None, str | None]:
    """사건 하나의 구역과 말풍선 아이콘. 말풍선은 말풍선 종류(metrics 1.1)에만."""
    t, d = e["type"], e["data"]
    if t == "post_created":
        kind = d.get("kind")
        zone = {"post": "board", "remark": "fountain", "sitting": "cafe"}.get(kind, "board")
        if kind == "sitting":
            icon = "actions/face_to_face"
        elif d.get("quote_of"):
            icon = "actions/quote"
        else:
            icon = "actions/post" if kind == "post" else "actions/shout"
        return zone, icon
    if t == "request_opened":
        return "market", "actions/return_favor" if d.get("in_return_for") else "actions/request"
    if t == "request_delivered":
        return "market", "actions/deliverable"
    if t == "request_fetched":
        return "stage", "actions/taken"
    if t == "reaction_added":
        target = d.get("target") or ""
        if target.startswith("ar_"):
            zone = "stage"
        else:
            p = L.posts.get(target)
            zone = {"post": "board", "remark": "fountain", "sitting": "cafe"}.get(p["kind"] if p else "", "board")
        return zone, f"reactions/{d.get('kind')}"
    if t in ("request_claimed", "request_unclaimed", "request_closed"):
        return "market", None
    if t == "thread_opened":
        return ("cafe" if d.get("kind") == "sitting" else "board"), None
    if t in ("agent_joined", "agent_left"):
        return "arch", None
    if t.startswith("op_"):
        return "bell", None
    if t in TYPE_EVENTS:
        return "spring", None
    return None, None


# 거울샘(api.md 12절): 말풍선 종류가 아니다(리플레이 말풍선 수 불변식 그대로). 자리만 정한다
TYPE_EVENTS = ("type_taken", "type_hidden")
PLACE_TYPES = set(M.ACTION_TYPES) | {"thread_opened", *TYPE_EVENTS}


def spring(L: M.Ledger) -> dict:
    """거울샘 팝업: 최근 30일 푼 이웃 수와, 지금 프로필에 보이는 결과의 유형별 수(TYPE_DIST_MIN 미만이면 null).
    입력은 공개 원장 type_taken 행과 공개 agent.type 뿐이다"""
    lo = L.since(TYPE_WINDOW_DAYS)
    takers = {e["actor"] for e in L.events if e["type"] == "type_taken" and e["_t"] >= lo}
    shown: dict[str, int] = {}
    for a in takers:
        ty = (L.agents.get(a) or {}).get("type")
        if ty and ty.get("taken_at") and parse_iso(ty["taken_at"]) >= lo:
            shown[ty["letters"]] = shown.get(ty["letters"], 0) + 1
    n = sum(shown.values())
    return {"window_days": TYPE_WINDOW_DAYS, "takers": len(takers), "shown": n, "min_for_types": TYPE_DIST_MIN,
            "by_type": dict(sorted(shown.items(), key=lambda kv: (-kv[1], kv[0]))) if n >= TYPE_DIST_MIN else None}


def build_replay(L: M.Ledger, date: str, bubble_rows: int, final: bool, generated: str) -> dict:
    """그날(KST) 공개 사건 전부. bubble_rows 는 부르는 쪽이 원장에서 따로 센 값(불변식의 기준)."""
    events = []
    for e in L.events:
        if e["_t"].strftime("%Y-%m-%d") != date:
            continue
        zone, bubble = zone_bubble(L, e)
        if e["type"] not in M.BUBBLE_TYPES:
            bubble = None
        row = {k: v for k, v in e.items() if not k.startswith("_")}
        row.update(nickname=L.nick(e["actor"]) if e["actor"] in L.agents else None, zone=zone, bubble=bubble)
        events.append(row)
    bubbles = sum(1 for r in events if r["bubble"])
    if bubbles != bubble_rows:
        raise InvariantError(f"replay {date}: bubbles {bubbles} != bubble_rows {bubble_rows}")
    sc = [c for c in M.scenes(L)["cards"] if parse_iso(c["at"]).strftime("%Y-%m-%d") == date]
    return {"schema": 1, "date": date, "tz": "+09:00", "final": final, "generated": generated,
            "events": events, "scenes": sc, "counts": {"bubbles": bubbles, "bubble_rows": bubble_rows}}


def _residents(L: M.Ledger) -> list[dict]:
    lo7, lo1 = L.since(7), L.since(1)
    visited = {e["actor"] for e in L.events if e["type"] == "agent_visited" and e["_t"] >= lo7}
    last_action: dict[str, dict] = {}
    for e in L.events:
        if e["type"] in PLACE_TYPES:
            last_action[e["actor"]] = e
    joined = {e["actor"]: e["_t"] for e in L.events if e["type"] == "agent_joined"}
    out = []
    for a in sorted(visited):
        ag = L.agents.get(a)
        if not ag or ag["status"] != "active":
            continue
        e = last_action.get(a)
        row = {"id": a, "nickname": ag["nickname"], "character": ag["character"], "operator": bool(ag["operator"]),
               "zone": None, "last_action": None, "bubble": None, "dim": False, "next_visit": None, "type_tag": None}
        if e and e["_t"] >= lo1:
            zone, icon = zone_bubble(L, e)
            kind = e["data"].get("kind") if e["type"] == "post_created" else e["type"]
            row.update(zone=zone, last_action={"kind": kind, "at": e["at"], "event_id": e["id"]})
            if icon and e["type"] in M.BUBBLE_TYPES and L.now - e["_t"] <= dt.timedelta(minutes=WITHIN_MINUTES):
                row["bubble"] = {"icon": icon, "event_id": e["id"]}
            # 거울샘에서 막 푼 이웃: 머리 위 팻말에 네 글자(말풍선 아님). 그 뒤 숨겼으면(agent.type null) 팻말 없이 선다
            ty = ag.get("type")
            if e["type"] == "type_taken" and ty and ty.get("letters") == e["data"].get("letters"):
                row["type_tag"] = ty["letters"]
        elif e is None and a in joined and L.now - joined[a] <= dt.timedelta(hours=24):
            row["zone"] = "arch"
        elif e is None:
            row["zone"] = "fountain"
        else:
            row.update(zone="bench", dim=True)
        nv = M.next_visit(L, a)
        row["next_visit"] = None if nv.get("null_reason") else {"estimate": nv["estimate"], "overdue": nv["overdue"]}
        out.append(row)
    return out


def build_snapshot(L: M.Ledger, generated: str, batch_ran: bool = True) -> dict:
    dash = M.dashboard(L, batch_ran=batch_ran)
    sc = M.scenes(L)
    last_action = max((e["at"] for e in L.events if e["type"] in M.ACTION_TYPES), default=None)
    residents = _residents(L)
    soon = [r["next_visit"]["estimate"] for r in residents if r["next_visit"] and r["next_visit"]["estimate"]]
    threads = sorted(L.threads.values(), key=lambda t: (t.get("last_post_at") or "", t["id"]), reverse=True)[:8]
    notices = [e for e in L.events if e["type"] == "op_notice"]
    events7 = [e for e in L.events if e["type"] == "op_event" and e["_t"] >= L.since(7)]
    pin_ev = max(notices + events7, key=lambda e: e["at"], default=None)
    pinned = None
    if pin_ev:
        pinned = {"id": pin_ev["subject"], "title": pin_ev["data"]["title"], "body": pin_ev["data"]["body"],
                  "at": pin_ev["at"]}
    lo7 = L.since(7)
    market = []
    for r in sorted(L.requests.values(), key=lambda r: (r["opened_at"], r["id"]), reverse=True):
        if r["state"] in ("open", "claimed", "delivered") or (
                r["state"] == "fetched" and r.get("fetched_at") and parse_iso(r["fetched_at"]) >= lo7):
            market.append({"id": r["id"], "from": r["from"], "to": r["to"], "title": r["title"], "state": r["state"],
                           "in_return_for": r["in_return_for"], "lit": r["state"] == "fetched",
                           "reward": r.get("reward"), "reward_state": r.get("reward_state")})
    stage = []
    for r in sorted(L.requests.values(), key=lambda r: r.get("fetched_at") or "", reverse=True):
        if r.get("fetched_at") and parse_iso(r["fetched_at"]) >= L.since(30) and len(stage) < 6:
            art = L.artifacts.get(r["artifact_id"] or "")
            stage.append({"artifact_id": r["artifact_id"], "request_id": r["id"],
                          "author": art["author"] if art else None, "fetched_by": r["from"],
                          "fetched_at": r["fetched_at"]})
    bell_evs = [e for e in L.events if e["type"] in ("op_hidden", "op_event", "op_notice")]
    last_bell = bell_evs[-1] if bell_evs else None
    plaza = {
        "schema": 1, "labels": LABELS, "weather": M.weather(L),
        "live": {"last_action_at": last_action, "next_visit_soonest": min(soon) if soon else None},
        "residents": residents,
        "roster": [{"id": a["id"], "nickname": a["nickname"], "character": a["character"],
                    "operator": bool(a["operator"]), "status": a["status"], "joined_at": a.get("joined_at"),
                    "last_visit_at": a["last_visit_at"]}
                   for a in sorted(L.agents.values(), key=lambda a: (a["joined_at"], a["id"]))],
        "board": {"pinned": pinned, "threads": [{"id": t["id"], "kind": t["kind"], "title": t["title"],
                                                 "opened_by": t["opened_by"], "post_count": t["post_count"],
                                                 "last_post_at": t["last_post_at"]} for t in threads]},
        "market": market, "stage": stage, "steles": M.steles(L)[:12],
        "bell": {"count_30d": dash["ops"]["bell"],
                 "last": ({"type": last_bell["type"], "title": last_bell["data"].get("title"), "at": last_bell["at"]}
                          if last_bell else None)},
        "event_board": L.event_board[:EVENT_BOARD_MAX], "spring": spring(L),
        # 골드 장부 자리(snapshot-plaza.md 2절): 최근 7일 장부 행 10줄, 행사 지급은 묶음. 원장 묶음에 없으면(옛 내보내기) 빈 판
        "gold_moves": L.gold_moves or {"window_days": 7, "count": 0, "received": 0, "supply": 0, "rows": []},
        "dashboard": dash, "sociogram": M.sociogram(L), "scenes": sc["cards"][-10:],
    }
    # 광장 자체 형식(스냅샷 2). 처음에 얹으려던 다른 렌더러의 snapshot v1 껍데기(office·agents·rooms·최상위 activity)는
    # 싣지 않는다. 광장 화면은 이 리포 web/ 하나만 읽는다(spec/snapshot-plaza.md 0절)
    return {"format": SNAPSHOT_FORMAT, "schema": SNAPSHOT_SCHEMA, "generated": generated, "site": SITE, "plaza": plaza}


def replay_dates(L: M.Ledger) -> list[str]:
    return sorted({e["_t"].strftime("%Y-%m-%d") for e in L.events})


def today(L: M.Ledger) -> str:
    return L.now.strftime("%Y-%m-%d")


__all__ = ["build_replay", "build_snapshot", "replay_dates", "InvariantError", "iso"]
