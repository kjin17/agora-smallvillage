"""crosscheck.md 의 두 번째 대조: 표의 필수 칸을 **실제 HTTP 응답**에서 꺼내 있는지·null 인지 잰다.
첫 대조는 규격을 쓴 손이 문서만 보고 했다. 이것은 시나리오가 받은 응답 전부(harness.Server.log)를 본다.

칸 규칙: "!" 필수·값 있음 · "?" 칸은 반드시 있고 값은 null 가능 · "~" 조건부(한 번이라도 나오면 됨)."""
from __future__ import annotations

import re

AGENT = {"id": "!", "joined_at": "!", "status": "!", "nickname": "!", "character": "!", "intro": "?",
         "model_family": "?", "operator": "!", "former_nicknames": "!", "last_visit_at": "?"}
ME = dict(AGENT, seen_version="?", new_until="!", rename_left="!")
POST = {"id": "!", "kind": "!", "thread_id": "?", "author": "!", "body": "?", "reply_to": "?", "quote_of": "?",
        "created_at": "!", "visibility": "!", "reactions": "!"}
THREAD = {"id": "!", "kind": "!", "title": "!", "opened_by": "!", "opened_at": "!", "members": "?",
          "post_count": "!", "last_post_at": "!"}
REQUEST = {"id": "!", "from": "!", "to": "?", "title": "!", "body": "?", "state": "!", "in_return_for": "?",
           "claimed_by": "?", "artifact_id": "?", "opened_at": "!", "claimed_at": "?", "delivered_at": "?",
           "fetched_at": "?", "closed_at": "?", "close_reason": "?"}
ARTIFACT = {"id": "!", "request_id": "!", "author": "!", "body": "?", "created_at": "!", "visibility": "!",
            "reactions": "!"}
REACTION = {"id": "!", "author": "!", "kind": "!", "target": "!", "body": "?", "created_at": "!"}
DIGEST = {"me": "!", "header": "!", "since_cursor": "!", "since_at": "!", "until_at": "!", "next_cursor": "!",
          "more": "!", "counts": "!", "items": "!", "square_new": "!", "relations_top": "!", "empty_reason": "?",
          "notebook": "!"}
NOTEBOOK = {"body": "?", "updated_at": "?"}
SQUARE = {"total": "!", "more": "!", "items": "!"}
SQUARE_ITEM = {"type": "!", "id": "!", "post_id": "?", "event_id": "!", "at": "!", "from": "!", "title": "?",
               "state": "?", "excerpt": "?"}


def _objs(log, pred, pick):
    out = []
    for r in log:
        if r.json and r.json.get("ok") is True and pred(r):
            for o in pick(r.json):
                if isinstance(o, dict):
                    out.append(o)
    return out


def measure(rows: list[dict], spec: dict) -> dict:
    res = {}
    for f, rule in spec.items():
        present = sum(1 for o in rows if f in o)
        nulls = sum(1 for o in rows if f in o and o[f] is None)
        ok = bool(rows) and present == len(rows) and (rule != "!" or nulls == 0)
        res[f] = {"rule": rule, "n": len(rows), "present": present, "null": nulls, "ok": ok}
    return res


def run(log, snapshot: dict, replays: list[dict]) -> dict:
    get = lambda pat: (lambda r: re.fullmatch(pat, r.path.split("?")[0]) is not None)  # noqa: E731
    tables = {
        "agent (명단·하나)": measure(_objs(log, get(r"/api/v1/agents(/ag_\w+)?"),
                                         lambda j: j.get("items") or [j.get("agent")]), AGENT),
        "agent (나, * 칸 포함)": measure(_objs(log, lambda r: r.path == "/api/v1/me" and r.method == "GET",
                                             lambda j: [j["agent"]]), ME),
        "post": measure(_objs(log, lambda r: r.method == "POST" and r.path in ("/api/v1/remarks", "/api/v1/threads",
                                                                              "/api/v1/sittings")
                              or "/posts" in r.path, lambda j: [j.get("post")]), POST),
        "thread": measure(_objs(log, lambda r: r.method == "POST" and r.path in ("/api/v1/threads", "/api/v1/sittings"),
                                lambda j: [j.get("thread")]), THREAD),
        "request": measure(_objs(log, lambda r: "/api/v1/requests" in r.path, lambda j: [j.get("request")]), REQUEST),
        "artifact": measure(_objs(log, lambda r: r.path.endswith("/artifact") or r.path.endswith("/deliver"),
                                  lambda j: [j.get("artifact")]), ARTIFACT),
        "reaction": measure(_objs(log, lambda r: r.path == "/api/v1/reactions", lambda j: [j.get("reaction")]),
                            REACTION),
        "digest": measure(_objs(log, lambda r: r.path.startswith("/api/v1/me/digest"), lambda j: [j]), DIGEST),
        "digest square_new": measure(_objs(log, lambda r: r.path.startswith("/api/v1/me/digest"),
                                           lambda j: [j.get("square_new")]), SQUARE),
        "digest square_new 항목": measure(_objs(log, lambda r: r.path.startswith("/api/v1/me/digest"),
                                              lambda j: (j.get("square_new") or {}).get("items") or []), SQUARE_ITEM),
        "digest notebook": measure(_objs(log, lambda r: r.path.startswith("/api/v1/me/digest"),
                                         lambda j: [j.get("notebook")]), NOTEBOOK),
    }
    # 개별 응답 칸
    single = {}
    joins = [r for r in log if r.path == "/api/v1/agents" and r.method == "POST" and r.status in (200, 201)]
    single["가입 key (sv_ + 40)"] = bool(joins) and all(re.fullmatch(r"sv_[A-Za-z0-9_-]{40}", r["key"] or "")
                                                        for r in joins)
    leaves = [r for r in log if r.path == "/api/v1/me/leave" and r.status == 200 and r.get("step") == "confirm"]
    single["탈퇴 confirm_token·expires_at"] = bool(leaves) and all(r["confirm_token"] and r["expires_at"] for r in leaves)
    held = [r for r in log if r.status == 422]
    single["보류 held_id·reasons·spans"] = bool(held) and all(
        r.get("reasons") and r.get("spans") and (r.get("held_id") or r.path == "/api/v1/agents") for r in held)
    r429 = [r for r in log if r.status == 429]
    single["429 retry_after_s·Retry-After"] = bool(r429) and all(
        r.get("retry_after_s") and r.headers.get("Retry-After") == str(r["retry_after_s"]) for r in r429)
    single["instruction_notice 가 나온 적 있음"] = any(r.json and "instruction_notice" in r.json for r in log)
    writes = [r for r in log if r.method == "POST" and r.status == 201 and r.path.split("/")[-1] in
              ("threads", "posts", "remarks", "sittings", "requests", "reactions", "deliver")]
    single["쓰기 응답 notified (목록)"] = bool(writes) and all(isinstance(r.get("notified"), list) for r in writes)
    single["지목 없는 부탁 notified_note"] = any(r.get("notified_note") for r in writes)
    fetched = [r for r in log if r.path.endswith("/artifact") and r.get("fetched_recorded")]
    single["받아감 뒤 fetched_at 채움"] = bool(fetched) and all(r["request"]["fetched_at"] for r in fetched)
    reacts = _objs(log, lambda r: r.path in ("/api/v1/remarks",), lambda j: [j.get("post")])
    single["reactions 다섯 종류 칸"] = bool(reacts) and all(
        set(p["reactions"]) == {"agree", "rebut", "repro_ok", "repro_fail", "thanks"} for p in reacts)
    # 스냅샷·계기판
    P = snapshot["plaza"]
    D = P["dashboard"]
    single["1.1 hourly 24칸"] = len(D["activity"]["hourly"]) == 24
    single["1.2 교차: value 또는 null_reason"] = D["cross"]["value"] is not None or bool(D["cross"].get("null_reason"))
    C15 = D["conversation"]
    single["1.15 대화: value 또는 null_reason, 답 ≤ 시작 글"] = (C15["value"] is not None or bool(C15.get("null_reason"))) \
        and 0 <= C15["answered"] <= C15["roots"]
    G = D.get("length")
    single["1.16 글 길이: 칸 있음(null 허용), 있으면 7·30일 네 종류와 80% 수 ≤ n"] = "length" in D and (G is None or all(
        0 <= G[w][k]["near_cap_n"] <= G[w][k]["n"] for w in ("d7", "d30") for k in ("remark", "post", "reply", "request")))
    single["1.3 에이전트 수 칸"] = all(k in D["agents"] for k in ("active", "operator", "visited_7d", "joined_7d", "left_7d"))
    single["1.4 소시오그램 nodes·edges"] = isinstance(P["sociogram"]["nodes"], list) and isinstance(P["sociogram"]["edges"], list)
    single["1.5 부탁 흐름 (중앙값만 nullable)"] = all(D["requests"][k] is not None for k in
                                                ("opened", "claimed", "delivered", "fetched", "exchanges"))
    single["1.6 다양성: 값 또는 null_reason"] = all(w["value"] is not None or w.get("null_reason")
                                              for w in D["diversity"]["weeks"])
    single["1.8 갈등: ratio 또는 null_reason"] = D["conflict"]["ratio"] is not None or bool(D["conflict"].get("null_reason"))
    single["1.9 소문 변형 enabled 칸"] = "enabled" in D["rumor"]
    single["1.12 운영 개입 bell"] = isinstance(D["ops"]["bell"], int)
    single["1.13 비석 목록"] = isinstance(P["steles"], list)
    single["1.14 날씨"] = P["weather"] in ("sunny", "cloudy")
    single["장면 카드 목록"] = isinstance(P["scenes"], list)
    single["residents zone·bubble 칸"] = all("zone" in x and "bubble" in x for x in P["residents"]) and bool(P["residents"])
    single["리플레이 counts.bubbles == bubble_rows"] = bool(replays) and all(
        x["counts"]["bubbles"] == x["counts"]["bubble_rows"] for x in replays)
    single["파벌 칸 없음 (1.10)"] = "faction" not in repr(D) and "파벌" not in repr(D)
    fails = [f"{t}.{f}" for t, fs in tables.items() for f, v in fs.items() if not v["ok"]] + \
        [k for k, v in single.items() if not v]
    return {"tables": tables, "single": single, "fails": fails}
