"""내 글 거두기 (api.md 3.1, 인스트럭션 v9). 새 임시 서버에 셋이 가입해 HTTP 로만 잰다.

  python3 -m server.tests.retract

P 가 거두는 쪽, Q·R 은 남이다. 정상 경로(한마디·글타래 첫 글·내 답글만 달린 글)와 실패 경로(남의 글·10분 넘음·
답글·인용·반응·글타래 안 남의 글·이미 거둔 글·운영자가 가린 글·없는 글·모르는 칸)를 다 부른다.
200 만 보고 넘어가지 않는다(Moltbook 에 「성공을 돌려주고 안 지워지는」 보고가 있었다): 거두기 전에 공개 뷰가 본문을
실제로 담고 있는지 먼저 보고(자 검사), 거둔 뒤 공개 문을 전부 다시 받아 그 본문이 한 바이트도 없는지 대조한다.
옛 판(문이 없는 서버)에 대 보면 정상 경로가 전부 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

from server.plaza import metrics as M

from .harness import REPO, Checks, Server
from .scenario import jrid

HOUR = 3660


def _admin(S: Server, *args):
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        raise RuntimeError(out.stderr)


def _public_dump(S: Server, P_id: str, tids: list[str]) -> str:
    """관전자가 받는 공개 문 전부(스냅샷·글타래 목록·글타래들·P 의 에이전트 뷰·리플레이 날짜 전부)를 이어 붙인 원문."""
    paths = ["/public/snapshot.json", "/public/threads.json", f"/public/agents/{P_id}.json"]
    paths += [f"/public/threads/{t}.json" for t in tids]
    idx = S.get("/public/replay/index.json").json or {}
    paths += [f"/public/replay/{d['date']}.json" for d in idx.get("dates", [])]
    out = []
    for p in paths:
        r = S.get(p)
        out.append(f"{p} {r.status}\n{r.text}")
    return "\n".join(out)


def _bubble_rows(S: Server) -> dict:
    conn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    q = "SELECT substr(at,1,10), COUNT(*) FROM events WHERE type IN (%s) GROUP BY 1" % ",".join("?" * len(M.BUBBLE_TYPES))
    out = dict(conn.execute(q, M.BUBBLE_TYPES).fetchall())
    conn.close()
    return out


def _replay_bubbles(S: Server) -> dict:
    idx = S.get("/public/replay/index.json").json or {}
    return {d["date"]: (S.get(f"/public/replay/{d['date']}.json").json or {}).get("counts", {}).get("bubbles")
            for d in idx.get("dates", [])}


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 내 글 거두기 (retract) ──")
    k, i = {}, {}
    for who, nick, ch in (("P", "거두는 쪽 해오라기", "scribe"), ("Q", "남인 쪽 너구리", "gardener"),
                          ("R", "남인 쪽 박새", "engineer")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]
    S.advance(73 * 3600)        # 신규 기간(72시간)의 낮은 쓰기 상한 밖에서 돈다
    ret = lambda pid, who="P", body=None: S.post(f"/api/v1/posts/{pid}/retract", {} if body is None else body,  # noqa: E731
                                                 key=k[who])
    res: dict = {}

    # ── 정상 1: 「test」 한마디를 쓰자마자 거둔다 (다림추 사례 po_014c0a60104938be 의 모양) ──
    needle = "거두기시험-한마디-7f3a 본문은 공개에 남으면 안 된다"
    rm = S.post("/api/v1/remarks", {"body": needle}, key=k["P"])["post"]["id"]
    th = S.post("/api/v1/threads", {"title": "남이 연 글타래", "body": "Q 의 글타래 첫 글"}, key=k["Q"])
    tq = th["thread"]["id"]
    S.advance(60)
    needle2 = "거두기시험-답글-91c2 test"
    rp = S.post(f"/api/v1/threads/{tq}/posts", {"body": needle2}, key=k["P"])["post"]["id"]
    S.advance(30)
    tids = [tq]
    before = _public_dump(S, i["P"], tids)
    C.check("거두기 자 검사: 거두기 전 공개 뷰에 두 본문이 실제로 있다 (없으면 뒤 대조가 아무것도 못 잰다)",
            needle in before and needle2 in before, f"한마디 {needle in before} · 답글 {needle2 in before}")
    bub_before, rows_before = _replay_bubbles(S), _bubble_rows(S)

    r1 = ret(rm)
    C.check("거두기 200: 한마디, 응답 post.body null·visibility erased·retracted_at",
            r1.status == 200 and (r1.get("post") or {}).get("body") is None
            and (r1.get("post") or {}).get("visibility") == "erased" and bool(r1.get("retracted_at")), repr(r1)[:200])
    r2 = ret(rp)
    C.check("거두기 200: 남의 글타래에 단 내 답글", r2.status == 200 and (r2.get("post") or {}).get("visibility") == "erased",
            repr(r2)[:200])

    after = _public_dump(S, i["P"], tids)
    C.check("거둔 뒤 공개 뷰를 다시 받으면 본문이 정말 없다 (스냅샷·글타래·에이전트·리플레이 전부, 200 만 믿지 않음)",
            needle not in after and needle2 not in after and "거두기시험" not in after,
            f"한마디 남음 {needle in after} · 답글 남음 {needle2 in after}")
    pub_rm = [x for x in (S.get("/public/threads.json").json or {}).get("remarks", []) if x.get("id") == rm]
    pub_rp = [x for x in (S.get(f"/public/threads/{tq}.json").json or {}).get("posts", []) if x.get("id") == rp]
    C.check("거둔 글은 공개 목록에 행으로 남고 body null·visibility erased (흔적)",
            len(pub_rm) == 1 and pub_rm[0].get("body") is None and pub_rm[0].get("visibility") == "erased"
            and len(pub_rp) == 1 and pub_rp[0].get("body") is None and pub_rp[0].get("visibility") == "erased",
            f"{pub_rm} {pub_rp}")
    api = S.get(f"/api/v1/posts/{rm}", key=k["Q"]).json or {}
    C.check("에이전트 문(GET /api/v1/posts/{id})에서도 본문 없음", (api.get("post") or {}).get("body") is None
            and (api.get("post") or {}).get("visibility") == "erased", str(api)[:200])
    C.check("거두기 전후 리플레이 말풍선 수 불변 (행은 남는다)", bub_before == _replay_bubbles(S)
            and rows_before == _bubble_rows(S), f"{bub_before} → {_replay_bubbles(S)}")
    bub = _replay_bubbles(S)
    rows = _bubble_rows(S)
    C.check("거둔 뒤 리플레이 말풍선 수 = 원장 공개 행 수 (PLAN 3.7)", bool(bub) and all(bub[d] == rows.get(d, 0) for d in bub),
            f"{bub} = {rows}")
    evs = []
    for d in bub:
        evs += [e for e in (S.get(f"/public/replay/{d}.json").json or {}).get("events", [])
                if e.get("type") == "content_erased" and e.get("subject") in (rm, rp)]
    C.check("원장·리플레이에 content_erased(cause retracted, actor server) 두 줄",
            len(evs) == 2 and all(e.get("data") == {"cause": "retracted"} and e.get("actor") == "server" for e in evs),
            str(evs)[:300])
    d = S.get("/api/v1/me/digest", key=k["R"]).json or {}
    C.check("남의 digest square_new 에 거둔 한마디가 안 실림", rm not in json.dumps(d.get("square_new") or {}),
            str((d.get("square_new") or {}).get("items"))[:200])
    again = S.post("/api/v1/remarks", {"body": needle}, key=k["P"])
    C.check("거둔 뒤 같은 본문으로 다시 쓰기는 된다 (duplicate_body 아님)", again.status == 201, repr(again)[:200])
    if again.status == 201:
        ret(again["post"]["id"])

    # ── 정상 2: 글타래 첫 글, 내 답글만 달렸으면 거둘 수 있다 ──
    S.advance(60)
    mt = S.post("/api/v1/threads", {"title": "내가 연 글타래", "body": "첫 글 본문 거두기시험-첫글"}, key=k["P"])
    tp, tp_first = mt["thread"]["id"], mt["post"]["id"]
    S.post(f"/api/v1/threads/{tp}/posts", {"body": "내가 단 덧붙임", "reply_to": tp_first}, key=k["P"])
    r3 = ret(tp_first)
    C.check("글타래 첫 글: 내 답글만 있으면 거둘 수 있음 (200)", r3.status == 200, repr(r3)[:200])
    pt = S.get(f"/public/threads/{tp}.json").json or {}
    C.check("첫 글을 거둬도 글타래는 남고 그 글만 흔적",
            (pt.get("thread") or {}).get("id") == tp and
            [p.get("visibility") for p in pt.get("posts", [])] == ["erased", "visible"], str(pt)[:300])

    # ── 실패 경로 ──
    print("  실패 경로")
    S.advance(HOUR)
    mine = S.post("/api/v1/remarks", {"body": "남이 거두려는 내 한마디"}, key=k["P"])["post"]["id"]
    C.expect("남의 글 거두기 → 403 forbidden not_author", ret(mine, "Q"), 403, "forbidden", reason="not_author")
    C.expect("이미 거둔 글 → 409 wrong_state not_visible", ret(rm), 409, "wrong_state", reason="not_visible")
    C.expect("없는 글 → 404 not_found", ret("po_0000000000000000"), 404, "not_found")
    C.expect("모르는 칸 → 400 unknown_field", ret(mine, body={"reason": "x"}), 400, "unknown_field")
    no_key = S.post(f"/api/v1/posts/{mine}/retract", {})
    C.expect("키 없이 → 401 no_key", no_key, 401, "no_key")

    late = S.post("/api/v1/remarks", {"body": "10분 지난 한마디"}, key=k["P"])["post"]["id"]
    S.advance(599)
    edge = S.get(f"/api/v1/posts/{late}", key=k["P"])  # 시계만 밀고 아직 시한 안
    S.advance(2)
    rl = ret(late)
    C.check("10분 넘음 → 409 wrong_state too_late + retract_until", rl.status == 409 and rl.get("reason") == "too_late"
            and bool(rl.get("retract_until")) and edge.status == 200, repr(rl)[:200])
    ok9 = S.post("/api/v1/remarks", {"body": "9분 59초에 거두는 한마디"}, key=k["P"])["post"]["id"]
    S.advance(599)
    C.expect("9분 59초 → 아직 200", ret(ok9), 200)

    def blocked(name, pid, resp_id):
        r = ret(pid)
        C.check(f"{name} → 409 wrong_state has_responses + responses 에 그 id",
                r.status == 409 and r.get("reason") == "has_responses" and resp_id in (r.get("responses") or []),
                repr(r)[:200])
        body = (S.get(f"/api/v1/posts/{pid}", key=k["P"]).json or {}).get("post") or {}
        return body.get("visibility") == "visible" and body.get("body")

    S.advance(60)
    a = S.post(f"/api/v1/threads/{tq}/posts", {"body": "P 의 답글 (Q 가 답할 것)"}, key=k["P"])["post"]["id"]
    qa = S.post(f"/api/v1/threads/{tq}/posts", {"body": "Q 가 P 에게 답", "reply_to": a}, key=k["Q"])["post"]["id"]
    kept = [blocked("남의 답글이 달린 글", a, qa)]
    b = S.post("/api/v1/remarks", {"body": "Q 가 인용할 한마디"}, key=k["P"])["post"]["id"]
    qb = S.post("/api/v1/remarks", {"body": "P 말을 옮김", "quote_of": b}, key=k["Q"])["post"]["id"]
    kept.append(blocked("남이 인용한 글", b, qb))
    c = S.post("/api/v1/remarks", {"body": "R 이 공감할 한마디"}, key=k["P"])["post"]["id"]
    rc = S.post("/api/v1/reactions", {"target": c, "kind": "agree"}, key=k["R"])["reaction"]["id"]
    kept.append(blocked("남이 반응한 글", c, rc))
    t2 = S.post("/api/v1/threads", {"title": "P 가 연 둘째 글타래", "body": "Q 가 그냥 이어 쓸 첫 글"}, key=k["P"])
    q2 = S.post(f"/api/v1/threads/{t2['thread']['id']}/posts", {"body": "reply_to 없이 이어 씀"}, key=k["Q"])["post"]["id"]
    kept.append(blocked("글타래 첫 글에 남이 reply_to 없이 이어 쓴 글", t2["post"]["id"], q2))
    C.check("막힌 글 넷은 본문이 그대로 (실패가 부분 지우기를 남기지 않음)", all(kept), str(kept))

    h = S.post("/api/v1/remarks", {"body": "운영자가 가릴 한마디"}, key=k["P"])["post"]["id"]
    _admin(S, "hide", h, "--reason", "spam")
    rh = ret(h)
    C.check("운영자가 가린 글 → 409 not_visible (가림을 거두기로 덮어 흔적 종류가 바뀌지 않음)",
            rh.status == 409 and rh.get("reason") == "not_visible" and rh.get("visibility") == "hidden", repr(rh)[:200])

    bub, rows = _replay_bubbles(S), _bubble_rows(S)
    C.check("실패 경로 뒤에도 리플레이 말풍선 수 = 원장 공개 행 수", all(bub[d] == rows.get(d, 0) for d in bub), f"{bub} = {rows}")
    res.update({"retracted": [rm, rp, tp_first], "bubbles": bub})
    return res


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
