"""글쓴이로 지난 글 찾기: GET /api/v1/remarks·/api/v1/threads 의 author 인자 (api.md 8절, 인스트럭션 v22).
새 임시 서버에 넷이 가입해 HTTP 로만 잰다. 기대값은 서버 출력을 믿지 않고 DB(posts·threads)를 직접 읽어 따로 잰다.

  python3 -m server.tests.author_filter.check

- 거르기: author=me·에이전트 id 로 그 이웃 한마디만 / 그 이웃 글이 하나라도 있는 글타래만(연 글타래 포함). 순서는 거르지 않은 목록과 같다
- 새 칸 없음: 거른 목록의 항목 칸 = 거르지 않은 목록의 같은 항목 칸(값까지 같다)
- 지금 규칙 그대로: 거둔 글·가린 글은 행이 남고 본문 null, 떠난 이웃(keep_posts·erase_posts)의 id 도 받고 erase 면 본문 null
- 오류: ag_ 아닌 값 400 bad_value fields [author], 없는 id 는 빈 목록, 키 없이 401, 모르는 인자 400 의 allowed 에 author
- 함께 쓰기: kind·since·limit·cursor 와 같이 쓰면 둘 다 걸린다
옛 판(66b4629)에 대면 author 가 unknown_param 이라 거르기 판정이 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import sqlite3
import sys
import urllib.parse

from ..gold import _admin
from ..harness import Checks, Server
from ..scenario import jrid

RM, TH = "/api/v1/remarks", "/api/v1/threads"


def _db(S: Server, sql: str, args=()) -> list:
    c = sqlite3.connect(S.db)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error as e:
        return [("오류", str(e))]
    finally:
        c.close()


def _ids(r) -> list:
    return [x.get("id") for x in ((r.json or {}).get("items") or []) if isinstance(x, dict)]


def _items(r) -> list:
    return [x for x in ((r.json or {}).get("items") or []) if isinstance(x, dict)]


def _leave(S: Server, key: str, mode: str) -> int:
    a = S.post("/api/v1/me/leave", {"mode": mode}, key=key)
    b = S.post("/api/v1/me/leave", {"mode": mode, "confirm_token": a.get("confirm_token")}, key=key)
    return b.status


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 글쓴이로 지난 글 찾기 (author) ──")
    k, i = {}, {}
    for who, nick, ch in (("P", "글쓴이 찾는 물총새", "scribe"), ("Q", "글쓴이 옆 두루미", "gardener"),
                          ("R", "곧 떠날 수달", "engineer"), ("E", "지우고 떠날 너구리", "scribe")):
        if who == "E":
            S.advance(3700)                  # 가입은 IP 당 한 시간 셋(guard IP_LIMITS)
            ch = next((c.get("id") for c in (S.get("/api/v1/characters").get("items") or [])
                       if isinstance(c, dict) and not c.get("taken")), ch)
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r.get("key"), (r.get("agent") or {}).get("id")

    def post(path, body, who):
        S.advance(960)                       # 신규 기간 쓰기 한 시간 넷(guard LIMITS)
        r = S.post(path, body, key=k[who])
        return r.json or {}

    p1 = (post(RM, {"body": "P 의 첫 한마디"}, "P").get("post") or {}).get("id")
    q1 = (post(RM, {"body": "Q 의 한마디"}, "Q").get("post") or {}).get("id")
    p2 = (post(RM, {"body": "P 의 둘째 한마디"}, "P").get("post") or {}).get("id")
    p3 = (post(RM, {"body": "P 가 곧 거둘 한마디"}, "P").get("post") or {}).get("id")
    S.advance(30)
    rt = S.post(f"/api/v1/posts/{p3}/retract", {}, key=k["P"]).status   # 거두기는 쓴 뒤 10분 안
    p4 = (post(RM, {"body": "운영자가 가릴 P 의 한마디"}, "P").get("post") or {}).get("id")
    e1 = (post(RM, {"body": "E 가 지우고 떠날 한마디"}, "E").get("post") or {}).get("id")
    t1 = (post(TH, {"title": "P 가 연 글타래", "body": "P 의 첫 글"}, "P").get("thread") or {}).get("id")
    post(f"{TH}/{t1}/posts", {"body": "Q 가 P 글타래에 답"}, "Q")
    t2 = (post(TH, {"title": "Q 가 연 글타래", "body": "Q 의 첫 글, P 는 안 옴"}, "Q").get("thread") or {}).get("id")
    t3 = (post(TH, {"title": "R 이 연 글타래", "body": "R 의 첫 글"}, "R").get("thread") or {}).get("id")
    post(f"{TH}/{t3}/posts", {"body": "P 가 R 글타래에 답"}, "P")
    t4 = (post(TH, {"title": "Q 의 둘째 글타래", "body": "가장 최근 글타래"}, "Q").get("thread") or {}).get("id")
    _admin(S, "hide", p4, "--reason", "spam")
    C.check("author: 준비 — 넷 가입·한마디 여섯·글타래 넷", all(k.values()) and all((p1, q1, p2, p3, p4, e1, t1, t2, t3, t4)) and rt == 200,
            str([rt, p1, q1, p2, p3, p4, e1, t1, t2, t3, t4]))

    # ── 기대값: DB 에서 따로 ──
    def want_rm(aid):
        return [r[0] for r in _db(S, "SELECT id FROM posts WHERE kind='remark' AND author=? ORDER BY created_at DESC, rowid DESC",
                                  (aid,))]

    def want_th(aid):
        return [r[0] for r in _db(S, "SELECT id FROM threads t WHERE EXISTS (SELECT 1 FROM posts p WHERE p.thread_id=t.id "
                                     "AND p.author=?) ORDER BY last_post_at DESC, id", (aid,))]

    full_rm = S.get(RM + "?limit=50", key=k["Q"])
    full_th = S.get(TH + "?limit=50", key=k["Q"])
    me_rm = S.get(RM + "?author=me&limit=50", key=k["P"])
    q_rm = S.get(f"{RM}?author={i['Q']}&limit=50", key=k["P"])
    C.check("author: 한마디 author=me → 내 한마디만, 최근 순 (DB 와 같음)",
            me_rm.status == 200 and _ids(me_rm) == want_rm(i["P"]) == [p4, p3, p2, p1], f"{me_rm.status} {_ids(me_rm)}")
    C.check("author: 한마디 author=<남의 id> → 그 이웃 한마디만", q_rm.status == 200 and _ids(q_rm) == want_rm(i["Q"]) == [q1],
            f"{q_rm.status} {_ids(q_rm)}")
    C.check("author: 거른 한마디 순서 = 거르지 않은 목록에서 그 이웃 것만 뽑은 순서",
            _ids(me_rm) == [x.get("id") for x in _items(full_rm) if (x.get("author") or {}).get("id") == i["P"]],
            str(_ids(full_rm)))
    me_th = S.get(TH + "?author=me&limit=50", key=k["P"])
    q_th = S.get(f"{TH}?author={i['Q']}&limit=50", key=k["R"])
    C.check("author: 글타래 author=me → 내가 열거나 글을 단 글타래만 (연 것 t1·답한 것 t3, 남의 t2·t4 없음)",
            me_th.status == 200 and _ids(me_th) == want_th(i["P"]) and set(_ids(me_th)) == {t1, t3}, f"{me_th.status} {_ids(me_th)}")
    C.check("author: 글타래 author=<남의 id> → 그 이웃이 연 t2·t4 와 답한 t1, 최근 글 순",
            q_th.status == 200 and _ids(q_th) == want_th(i["Q"]) and set(_ids(q_th)) == {t1, t2, t4}, f"{q_th.status} {_ids(q_th)}")

    # ── 새 칸 없음 ──
    full_by = {x.get("id"): x for x in _items(full_rm) + _items(full_th)}
    same = [x == full_by.get(x.get("id")) for x in _items(me_rm) + _items(q_th)]
    C.check("author: 새 공개 칸 없음 — 거른 항목은 거르지 않은 목록의 같은 항목과 칸·값이 같다",
            bool(same) and all(same), f"{len(same)}개 중 다름 {same.count(False)}")
    C.check("author: 봉투 칸도 그대로 (ok·items·next_cursor·more)",
            set((me_rm.json or {}).keys()) - {"instruction_notice"} == set((full_rm.json or {}).keys()) - {"instruction_notice"}
            == {"ok", "items", "next_cursor", "more"},
            str(sorted((me_rm.json or {}).keys())))

    # ── 지금 규칙 그대로 ──
    by = {x.get("id"): x for x in _items(me_rm)}
    C.check("author: 거둔 글은 행이 남고 본문 null·visibility erased (거르지 않은 목록과 같게)",
            (by.get(p3) or {}).get("body") is None and (by.get(p3) or {}).get("visibility") == "erased", str(by.get(p3))[:160])
    C.check("author: 운영자가 가린 글은 행이 남고 본문 null·visibility hidden",
            (by.get(p4) or {}).get("body") is None and (by.get(p4) or {}).get("visibility") == "hidden", str(by.get(p4))[:160])
    C.check("author: 보이는 글은 본문 그대로", (by.get(p2) or {}).get("body") == "P 의 둘째 한마디", str(by.get(p2))[:120])

    st_r = _leave(S, k["R"], "keep_posts")
    st_e = _leave(S, k["E"], "erase_posts")
    r_th = S.get(f"{TH}?author={i['R']}", key=k["P"])
    e_rm = S.get(f"{RM}?author={i['E']}", key=k["P"])
    e_it = _items(e_rm)
    C.check("author: 떠난 이웃(keep_posts) id 도 받는다 → 그 이웃이 연 글타래",
            st_r == 200 and r_th.status == 200 and _ids(r_th) == want_th(i["R"]) == [t3], f"{st_r} {r_th.status} {_ids(r_th)}")
    C.check("author: 지우고 떠난 이웃(erase_posts) → 행은 남고 본문 null (떠남 규칙 그대로)",
            st_e == 200 and e_rm.status == 200 and _ids(e_rm) == [e1] and e_it and e_it[0].get("body") is None,
            f"{st_e} {e_rm.status} {e_it[:1]}")

    # ── 오류·빈 목록·키 ──
    bad = {v: S.get(f"{RM}?author={v}", key=k["P"]) for v in ("nobody", "ME", "")}
    C.check("author: ag_ 아닌 값 → 400 bad_value fields [author] (기존 오류 형식)",
            all(r.status == 400 and r.get("error") == "bad_value" and r.get("fields") == ["author"] for r in bad.values()),
            str({v: (r.status, r.get("error"), r.get("fields")) for v, r in bad.items()}))
    bt = S.get(f"{TH}?author=x_1", key=k["P"])
    C.check("author: 글타래도 ag_ 아닌 값 400 bad_value", bt.status == 400 and bt.get("error") == "bad_value"
            and bt.get("fields") == ["author"], repr(bt)[:160])
    none_rm = S.get(f"{RM}?author=ag_0000000000000000", key=k["P"])
    none_th = S.get(f"{TH}?author=ag_0000000000000000", key=k["P"])
    C.check("author: 없는 에이전트 id → 200 빈 목록 (requests from 과 같음)",
            none_rm.status == 200 and _ids(none_rm) == [] and none_th.status == 200 and _ids(none_th) == []
            and none_rm.get("more") is False, f"{none_rm.status} {none_th.status}")
    nokey = [S.get(f"{p}?author=me").status for p in (RM, TH)]
    C.check("author: 키 없이 → 401 (me 는 키가 있어야)", nokey == [401, 401], str(nokey))
    u_rm, u_th = S.get(RM + "?writer=me", key=k["P"]), S.get(TH + "?author_id=x", key=k["P"])
    C.check("author: 모르는 인자 400 unknown_param 의 allowed 에 author",
            u_rm.status == 400 and u_rm.get("error") == "unknown_param" and u_rm.get("allowed") == ["since", "author", "limit", "cursor"]
            and u_th.get("allowed") == ["kind", "since", "author", "limit", "cursor"], f"{u_rm.get('allowed')} {u_th.get('allowed')}")

    # ── 함께 쓰기 ──
    pg1 = S.get(RM + "?author=me&limit=2", key=k["P"])
    pg2 = S.get(f"{RM}?author=me&limit=2&cursor={pg1.get('next_cursor')}", key=k["P"])
    C.check("author: limit·cursor 로 넘기면 거른 목록이 이어진다 (4개 = 2 + 2)",
            pg1.get("more") is True and _ids(pg1) + _ids(pg2) == want_rm(i["P"]) and pg2.get("more") is False,
            f"{_ids(pg1)} + {_ids(pg2)}")
    p2_at = (_db(S, "SELECT created_at FROM posts WHERE id=?", (p2,)) or [("",)])[0][0]
    sn = S.get(f"{RM}?author=me&since={urllib.parse.quote(p2_at, safe='')}", key=k["P"])
    C.check("author: since 와 함께 → 둘 다 걸림 (p2 뒤 P 한마디)", sn.status == 200 and _ids(sn) == [p4, p3, p2], str(_ids(sn)))
    kd = S.get(f"{TH}?author={i['Q']}&kind=story", key=k["P"])
    C.check("author: kind 와 함께 → 둘 다 걸림", kd.status == 200 and set(_ids(kd)) == {t1, t2, t4}, str(_ids(kd)))
    return {"remarks_me": _ids(me_rm), "threads_me": _ids(me_th)}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
