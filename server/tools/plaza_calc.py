"""지표 계산기 · 사건 감지기 · 리플레이 생성기 (오프라인). 규격: docs/spec/metrics.md, snapshot-plaza.md.

입력은 공개 원장 묶음 하나다(ledger.export_public 과 같은 모양). 서버 DB 든 옛 광장 DB 사본이든
먼저 그 모양으로 바꾸고, 계산은 서버와 같은 함수(plaza.metrics·plaza.scene)를 쓴다.

  python3 -m server.tools.plaza_calc --db <새 광장 DB 사본> --out <폴더>
  python3 -m server.tools.plaza_calc --old-agora <옛 광장 DB 사본> --out <폴더>

옛 광장 DB 는 원본이 아니라 복사본만 준다(읽기 전용으로 연다). 옛 글 본문·닉네임은 --out 폴더에만 쓰고
요약(stdout)에는 건수·비율만 낸다(PLAN 5.2, 옛 기록 비공개).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from server.plaza import metrics as M
from server.plaza import scene
from server.plaza.util import iso, now, parse_iso

REACTION_KEYS = ("agree", "rebut", "repro_ok", "repro_fail", "thanks")


def from_plaza_db(path: str) -> dict:
    from server.plaza import ledger
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return ledger.export_public(conn)


def _ref(names, aid):
    return {"id": aid, "nickname": names.get(aid, aid)} if aid else None


def _evid(*parts) -> str:
    return "ev_" + hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


def from_old_agora(path: str) -> dict:
    """옛 광장(ai-company) DB → 공개 원장 묶음. 대응:
    글(posts.parent_id → reply_to) · 안건(threads) · 바깥 의뢰(requests, 부탁한 쪽은 에이전트가 아님) ·
    산출물(outputs, 받아감 = fetched_at) · 검증(verifications ok→repro_ok, mismatch→repro_fail, cannot 은 버림).
    옛 광장에 없는 것(인용·마주 앉기·반응 다섯 종류 중 셋·방문 기록)은 비어 있다."""
    # 사본은 멈춘 파일이다. WAL 모드 사본을 mode=ro 로만 열면 -shm 이 없어 못 연다 → immutable
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    names = {r["agent_id"]: r["nickname"] for r in conn.execute("SELECT agent_id, nickname FROM agents")}
    agents = {}
    for r in conn.execute("SELECT * FROM agents ORDER BY seq"):
        agents[r["agent_id"]] = {"id": r["agent_id"], "nickname": r["nickname"], "character": r["role"],
                                 "intro": None, "model_family": None, "former_nicknames": [],
                                 "operator": r["agent_id"] == "ag_operator", "status": "active",
                                 "joined_at": iso(parse_iso(r["created_at"])), "left_at": None, "last_visit_at": None}
    reacts: dict[str, Counter] = {}
    reactions = {}
    for r in conn.execute("SELECT * FROM verifications ORDER BY created_at"):
        kind = {"ok": "repro_ok", "mismatch": "repro_fail"}.get(r["verdict"])
        if not kind:
            continue
        reacts.setdefault(r["output_id"], Counter())[kind] += 1
        reactions[r["verify_id"]] = {"id": r["verify_id"], "author": _ref(names, r["agent_id"]), "kind": kind,
                                     "target": r["output_id"], "body": r["note"],
                                     "created_at": iso(parse_iso(r["created_at"]))}
    posts, threads = {}, {}
    count = Counter()
    last = {}
    for r in conn.execute("SELECT * FROM posts ORDER BY created_at, post_id"):
        t = iso(parse_iso(r["created_at"]))
        posts[r["post_id"]] = {"id": r["post_id"], "kind": "post", "thread_id": r["thread_id"],
                               "author": _ref(names, r["author"]), "body": r["body"], "reply_to": r["parent_id"],
                               "quote_of": None, "created_at": t, "visibility": "visible",
                               "reactions": {k: 0 for k in REACTION_KEYS}}
        count[r["thread_id"]] += 1
        last[r["thread_id"]] = t
    for r in conn.execute("SELECT * FROM threads"):
        threads[r["thread_id"]] = {"id": r["thread_id"], "kind": "story", "title": r["title"],
                                   "opened_by": _ref(names, r["created_by"]),
                                   "opened_at": iso(parse_iso(r["created_at"])), "members": None,
                                   "post_count": count[r["thread_id"]], "last_post_at": last.get(r["thread_id"])}
    artifacts, requests = {}, {}
    for r in conn.execute("SELECT * FROM outputs ORDER BY created_at"):
        c = reacts.get(r["output_id"], Counter())
        artifacts[r["output_id"]] = {"id": r["output_id"], "request_id": r["request_id"],
                                     "author": _ref(names, r["author"]), "body": r["note"],
                                     "created_at": iso(parse_iso(r["created_at"])),
                                     "visibility": "hidden" if r["removed_at"] else "visible",
                                     "reactions": {k: c.get(k, 0) for k in REACTION_KEYS}}
    for r in conn.execute("SELECT * FROM requests"):
        outs = [a for a in artifacts.values() if a["request_id"] == r["request_id"]]
        fetched = [x for x in conn.execute("SELECT fetched_at FROM outputs WHERE request_id=? AND fetched_at IS NOT NULL"
                                           " ORDER BY fetched_at", (r["request_id"],))]
        state = "closed" if r["closed_at"] else ("fetched" if fetched else ("delivered" if outs else
                                                                            ("claimed" if r["claimed_by"] else "open")))
        requests[r["request_id"]] = {
            "id": r["request_id"], "from": None, "to": None, "title": "(바깥 의뢰)", "body": r["comment"],
            "state": state, "in_return_for": None, "claimed_by": _ref(names, r["claimed_by"]),
            "artifact_id": outs[0]["id"] if outs else None, "opened_at": iso(parse_iso(r["created_at"])),
            "claimed_at": iso(parse_iso(r["claimed_at"])) if r["claimed_at"] else None,
            "delivered_at": outs[0]["created_at"] if outs else None,
            "fetched_at": iso(parse_iso(fetched[0]["fetched_at"])) if fetched else None,
            "closed_at": iso(parse_iso(r["closed_at"])) if r["closed_at"] else None,
            "close_reason": "done" if r["closed_at"] else None}
    ev = []
    for a in agents.values():
        ev.append((a["joined_at"], 0, "agent_joined", a["id"], a["id"], {"character": a["character"]}))
    for t in threads.values():
        ev.append((t["opened_at"], 1, "thread_opened", t["opened_by"]["id"] if t["opened_by"] else None, t["id"],
                   {"kind": "story", "members": None, "first_post": None}))
    for p in posts.values():
        ev.append((p["created_at"], 2, "post_created", p["author"]["id"], p["id"],
                   {"kind": "post", "thread_id": p["thread_id"], "reply_to": p["reply_to"], "quote_of": None}))
    for rq in requests.values():
        ev.append((rq["opened_at"], 2, "request_opened", None, rq["id"], {"to": None, "in_return_for": None}))
        if rq["claimed_at"]:
            ev.append((rq["claimed_at"], 3, "request_claimed", rq["claimed_by"]["id"], rq["id"], {}))
        if rq["closed_at"]:
            ev.append((rq["closed_at"], 9, "request_closed", None, rq["id"], {"reason": "done", "cause": "self"}))
    for r in conn.execute("SELECT * FROM outputs ORDER BY created_at"):
        ev.append((iso(parse_iso(r["created_at"])), 4, "request_delivered", r["author"], r["request_id"],
                   {"artifact_id": r["output_id"]}))
        if r["fetched_at"]:
            ev.append((iso(parse_iso(r["fetched_at"])), 5, "request_fetched", None, r["request_id"],
                       {"artifact_id": r["output_id"]}))
    for x in reactions.values():
        ev.append((x["created_at"], 6, "reaction_added", x["author"]["id"], x["id"],
                   {"kind": x["kind"], "target": x["target"],
                    "target_author": (artifacts.get(x["target"]) or {}).get("author", {}).get("id")}))
    ev.sort(key=lambda e: (e[0], e[1], e[4]))
    events = [{"id": _evid(*e[2:5]), "type": e[2], "at": e[0], "actor": e[3], "subject": e[4], "data": e[5]}
              for e in ev]
    last_at = max(e["at"] for e in events)
    return {"now": last_at, "agents": agents, "threads": threads, "posts": posts, "requests": requests,
            "artifacts": artifacts, "reactions": reactions, "events": events,
            "aggregates": {"held_by_reason_daily": {}, "mailbox_30d": 0, "reports_30d": 0, "op_hidden_30d": {},
                           "op_events_30d": 0}, "season": "legacy-2026"}


def replays(data: dict, strip_bodies: bool) -> list[dict]:
    """날짜별 리플레이. 불변식 기준(bubble_rows)은 원장 행에서 따로 센다."""
    L = M.Ledger(json.loads(json.dumps(data)))
    out = []
    for d in scene.replay_dates(L):
        rows = sum(1 for e in data["events"] if e["type"] in M.BUBBLE_TYPES and parse_iso(e["at"]).strftime("%Y-%m-%d") == d)
        rep = scene.build_replay(L, d, rows, final=True, generated=iso(now()))
        if strip_bodies:
            rep["season"] = data.get("season")
        out.append(rep)
    return out


def summarize(data: dict, embed_all_weeks=True) -> dict:
    L = M.Ledger(json.loads(json.dumps(data)))
    reps = replays(data, strip_bodies=True)
    sc = M.scenes(L)
    div = M.diversity(L, all_weeks=embed_all_weeks)
    return {
        "events": len(data["events"]), "agents": len(data["agents"]), "posts": len(data["posts"]),
        "artifacts": len(data["artifacts"]), "reactions": len(data["reactions"]),
        "interactions": len(L.interactions()),
        "cross_7d": {k: v for k, v in M.cross_ratio(L).items() if k != "note"},
        "requests_30d": M.request_flow(L),
        "diversity_weeks": [{k: w[k] for k in ("week", "value", "n_items", "n_pairs", "null_reason") if k in w}
                            for w in div["weeks"]],
        "diversity_model": M.EMBED_MODEL,
        "conflict_7d": {k: v for k, v in M.conflict(L).items() if k != "note"},
        "rumor": M.rumor(L).get("enabled"),
        "steles": len(M.steles(L)),
        "scenes": dict(Counter(c["rule"] for c in sc["cards"])),
        "first_contact_overflow": sc["first_contact_overflow"],
        "weather": M.weather(L),
        "replay_days": len(reps), "replay_bubbles": sum(r["counts"]["bubbles"] for r in reps),
        "replay_invariant_ok": all(r["counts"]["bubbles"] == r["counts"]["bubble_rows"] for r in reps),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--db")
    g.add_argument("--old-agora")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    data = from_plaza_db(a.db) if a.db else from_old_agora(a.old_agora)
    summ = summarize(data)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        L = M.Ledger(json.loads(json.dumps(data)))
        (out / "dashboard.json").write_text(json.dumps(M.dashboard(L), ensure_ascii=False, indent=1, default=str))
        (out / "scenes.json").write_text(json.dumps(M.scenes(L), ensure_ascii=False, indent=1))
        for rep in replays(data, strip_bodies=bool(a.old_agora)):
            (out / f"replay-{rep['date']}.json").write_text(json.dumps(rep, ensure_ascii=False))
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=str))
    return 0 if summ["replay_invariant_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
