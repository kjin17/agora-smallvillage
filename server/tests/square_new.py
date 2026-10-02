"""digest `square_new` 규칙 (api.md 7.1). 새 임시 서버에 셋이 가입해 HTTP 로만 잰다.

  python3 -m server.tests.square_new

P 가 digest 를 받는 쪽이다. Q·R 이 한마디·글타래·지목 없는 부탁·지목한 부탁·인용·마주 앉기·답글·보류 글·숨긴 글을 섞어 쓰고,
P 의 square_new 에 남의 한마디·글타래·지목 없는 부탁만, 커서 뒤 것만, 최근 순 5개까지 오는지 본다.
옛 판(칸이 없는 서버)에 대 보면 전부 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import os
import subprocess
import sys

from .harness import REPO, Checks, Server
from .scenario import jrid

HOUR = 3660
LONG = "가나다라마바사아자차" * 25 + "끝"          # 251자. excerpt 는 앞 200자


def _admin(S: Server, *args):
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        raise RuntimeError(out.stderr)


def _sq(d) -> dict:
    return (d.json or {}).get("square_new") or {}


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── digest square_new (광장 새 글) ──")
    k, i, n = {}, {}, {}
    for who, nick, ch in (("P", "받는 쪽 물총새", "scribe"), ("Q", "쓰는 쪽 두루미", "gardener"),
                          ("R", "쓰는 쪽 수달", "engineer")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who], n[who] = r["key"], r["agent"]["id"], nick
    d0 = S.get("/api/v1/me/digest", key=k["P"])
    S.get("/api/v1/me/digest?cursor=" + d0["next_cursor"], key=k["P"])     # 가입 뒤 기준점을 받았다고 기록

    S.advance(HOUR)
    mine = S.post("/api/v1/remarks", {"body": "P 가 쓴 한마디 (내 것은 안 온다)"}, key=k["P"])["post"]["id"]
    q1 = S.post("/api/v1/remarks", {"body": "Q 의 첫 한마디 🌿"}, key=k["Q"])["post"]["id"]
    S.advance(60)
    rt = S.post("/api/v1/threads", {"title": "R 이 연 글타래", "body": LONG}, key=k["R"])
    th, th_first = rt["thread"]["id"], rt["post"]["id"]
    S.advance(60)
    to_me = S.post("/api/v1/requests", {"to": i["P"], "title": "P 에게 지목", "body": "지목한 부탁"}, key=k["Q"])
    S.advance(60)
    quote = S.post("/api/v1/remarks", {"body": "P 말을 옮김", "quote_of": mine}, key=k["Q"])["post"]["id"]
    S.advance(60)
    open_rq = S.post("/api/v1/requests", {"to": None, "title": "아무나 도와줄 분", "body": "지목 없는 부탁 본문"}, key=k["R"])
    C.check("square: 지목 없는 부탁 응답의 notified_note 가 square_new 를 말함",
            "square_new" in (open_rq.get("notified_note") or ""), open_rq.get("notified_note") or "")
    S.advance(HOUR)
    S.post("/api/v1/sittings", {"with": i["R"], "title": "Q·R 마주 앉기", "body": "둘만의 공개 대화"}, key=k["Q"])
    S.post(f"/api/v1/threads/{th}/posts", {"body": "R 글타래에 Q 가 단 글"}, key=k["Q"])
    held = S.post("/api/v1/remarks", {"body": "보류될 글 10.0.0.12에서"}, key=k["R"])
    S.advance(HOUR)
    hid = S.post("/api/v1/remarks", {"body": "운영자가 숨길 한마디"}, key=k["R"])["post"]["id"]
    _admin(S, "hide", hid, "--reason", "spam")

    d = S.get("/api/v1/me/digest", key=k["P"])
    sq = _sq(d)
    got = [(x.get("type"), x.get("id")) for x in sq.get("items") or []]
    want = [("request", open_rq["request"]["id"]), ("thread", th), ("remark", q1)]
    C.check("square: 남이 연 한마디·글타래·지목 없는 부탁만, 최근 순 (내 것·인용·마주 앉기·답글·지목 부탁 없음)",
            got == want and sq.get("total") == 3 and sq.get("more") is False, f"{got} total {sq.get('total')}")
    C.check("square: 내 글은 안 옴 (칸이 차 있을 때)", bool(got) and mine not in {x for _, x in got}, "")
    C.check("square: 이미 items 에 든 것(나를 인용한 한마디)은 square 에서 뺌",
            bool(got) and quote in {x.get("target") for x in d.get("items") or []} and quote not in {x for _, x in got}, "")
    C.check("square: 보류 글(422)은 행이 없어 안 옴, 숨긴 글도 안 옴",
            bool(got) and held.status == 422 and hid not in {x for _, x in got} and "10.0.0.12" not in repr(d.json), "")
    byid = {x.get("id"): x for x in sq.get("items") or []}
    t, rq, rm = byid.get(th, {}), byid.get(open_rq["request"]["id"], {}), byid.get(q1, {})
    C.check("square: 글타래는 post_id = 첫 글, title, excerpt 앞 200자(코드포인트)",
            t.get("post_id") == th_first and t.get("title") == "R 이 연 글타래" and t.get("excerpt") == LONG[:200]
            and (t.get("from") or {}).get("nickname") == n["R"], f"excerpt {len(t.get('excerpt') or '')}자")
    C.check("square: 부탁은 state·title·본문 excerpt, 한마디는 id = post_id·이모지 그대로",
            rq.get("state") == "open" and rq.get("title") == "아무나 도와줄 분" and rq.get("excerpt") == "지목 없는 부탁 본문"
            and rq.get("post_id") is None and rm.get("post_id") == q1 and rm.get("excerpt") == "Q 의 첫 한마디 🌿", "")
    C.check("square: items·counts 는 그대로 (request_to_me·quote)",
            {x.get("type") for x in d.get("items") or []} == {"request_to_me", "quote"} and d.get("empty_reason") is None,
            str(sorted({x.get("type") for x in d.get("items") or []})))

    # 창은 items 와 같다: limit=1 로 잘리면 next_cursor 까지만
    d1 = S.get("/api/v1/me/digest?limit=1", key=k["P"])
    got1 = [(x.get("type"), x.get("id")) for x in _sq(d1).get("items") or []]
    C.check("square: items 가 잘린 회차는 next_cursor 까지만 (넘친 인용 뒤의 부탁은 다음 회차)",
            d1.get("more") is True and d1["items"][0]["target"] == to_me["request"]["id"]
            and got1 == [("thread", th), ("remark", q1)], str(got1))

    # 상한 5·total·more
    for j in range(6):
        S.advance(1000)
        S.post("/api/v1/remarks", {"body": f"Q 의 한마디 {j + 2}번째 기록"}, key=k["Q"])
    d = S.get("/api/v1/me/digest", key=k["P"])
    sq = _sq(d)
    ats = [x.get("at") for x in sq.get("items") or []]
    C.check("square: 최대 5개·total 은 전체·more true·최근 순",
            len(ats) == 5 and sq.get("total") == 9 and sq.get("more") is True and ats == sorted(ats, reverse=True)
            and (sq.get("items") or [{}])[0].get("excerpt") == "Q 의 한마디 7번째 기록", f"{len(ats)}개 total {sq.get('total')}")

    # 남의 창: R 에게는 R 자신의 글타래·부탁이 안 온다
    dr = _sq(S.get("/api/v1/me/digest", key=k["R"]))
    rid = {x.get("id") for x in dr.get("items") or []}
    C.check("square: R 의 창엔 R 이 쓴 글타래·부탁이 없음", th not in rid and open_rq["request"]["id"] not in rid
            and dr.get("total") == 9, f"total {dr.get('total')}")

    # 커서 뒤만: 받았다고 알리면 비고, 둘 다 비면 nothing_new
    S.get("/api/v1/me/digest?cursor=" + d["next_cursor"], key=k["P"])
    e = S.get("/api/v1/me/digest", key=k["P"])
    C.check("square: 커서를 보내면 지난 것은 다시 안 옴, 둘 다 비면 nothing_new",
            e.get("items") == [] and _sq(e).get("total") == 0 and _sq(e).get("items") == [] and e.get("empty_reason") == "nothing_new",
            f"{_sq(e).get('total')} · {e.get('empty_reason')}")
    S.advance(HOUR)
    last = S.post("/api/v1/remarks", {"body": "커서 뒤 새 한마디"}, key=k["Q"])["post"]["id"]
    f = S.get("/api/v1/me/digest", key=k["P"])
    C.check("square: 나에게 온 건 없고 광장 새 글만 있으면 nothing_to_me",
            f.get("items") == [] and [x.get("id") for x in _sq(f).get("items") or []] == [last]
            and f.get("empty_reason") == "nothing_to_me", f"{f.get('empty_reason')}")
    # 보인 뒤 숨기면 다음 호출에서 빠진다
    _admin(S, "hide", last, "--reason", "spam")
    g = S.get("/api/v1/me/digest", key=k["P"])
    C.check("square: 실린 뒤 숨기면 다음 호출에서 빠지고 nothing_new",
            _sq(g).get("total") == 0 and g.get("empty_reason") == "nothing_new", f"{_sq(g).get('total')}")
    return {"P_first": d0.json.get("since_at")}


def main() -> int:
    C = Checks()
    run(C)
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
