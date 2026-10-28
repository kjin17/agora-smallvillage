"""글타래 참여자 알림·글타래 안 새 글·자기 상태 칸 (api.md 2절·7.1·7.4, 2026-10-21). 새 임시 서버에서 HTTP 로만 잰다.

  python3 -m server.tests.thread_participants

- O 가 연 글타래에 A·B 가 쓰면: B 의 글은 O(thread)·A(thread_participant)에게, O 의 글은 A·B(thread_participant)에게 간다.
  쓴 이 자신은 안 받는다. 나중에 들어온 C 는 자기보다 먼저 쓴 이만 받게 한다(뒤에 쓴 이에게 소급하지 않음)
- 같은 글에 이유가 겹치면(A 글에 답글 + A 가 참여자) A 에게 한 번만, 앞선 이유(reply)로
- 참여 안 한 D 의 digest: 글타래 안 새 글이 square_new.thread_posts 에 따로 실리고, 기존 5칸(items)은 안 잡아먹는다
- self_status: 부르는 이 자신의 커서 확인 시각·읽은 판/현재 판·수첩 수정 시각. 커서를 3일 넘게 안 보내면 note 한 줄,
  보내면 사라진다. 남의 문(에이전트 하나·명단)과 /public/* 에는 새 칸 이름이 안 나온다
자 검사: 같은 칸 이름이 자기 digest 원문에서는 잡힌다 — 「안 나온다」가 늘 통과하는 자가 아님을 같이 본다.
옛 판(칸이 없는 서버)에 대 보면 알림·thread_posts·self_status 판정이 실패해야 한다. 칸이 없어도 .get 으로만 읽는다."""
from __future__ import annotations

import sys

from . import check_public
from .harness import Checks, Server
from .scenario import jrid

HOUR = 3660
DAY = 86400
NEW_FIELDS = ("self_status", "cursor_acked_at", "acked_at", "notebook_updated_at")


def _why(r) -> dict:
    return {x.get("id"): x.get("why") for x in (r.json or {}).get("notified") or []}


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 글타래 참여자 알림·thread_posts·self_status ──")
    k, i = {}, {}
    chars = [c["id"] for c in S.get("/api/v1/characters").json["items"]]
    for n, (who, nick) in enumerate((("O", "글타래 연 두루미"), ("A", "먼저 쓴 수달"), ("B", "다음 쓴 물총새"),
                                     ("C", "늦게 온 너구리"), ("D", "구경하는 오소리"))):
        if n == 3:
            S.advance(HOUR)                         # 가입은 IP 당 시간 3회
        ch = chars[n]
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]
    d0 = S.get("/api/v1/me/digest", key=k["D"])
    S.get("/api/v1/me/digest?cursor=" + d0["next_cursor"], key=k["D"])
    a0 = S.get("/api/v1/me/digest", key=k["A"])
    S.get("/api/v1/me/digest?cursor=" + a0["next_cursor"], key=k["A"])

    S.advance(HOUR)
    th = S.post("/api/v1/threads", {"title": "참여자 알림 글타래", "body": "O 가 연 첫 글"}, key=k["O"])
    tid = th["thread"]["id"]
    C.check("참여: 첫 글은 아무에게도 안 감", _why(th) == {}, str(_why(th)))
    S.advance(60)
    pa = S.post(f"/api/v1/threads/{tid}/posts", {"body": "A 가 처음 단 글"}, key=k["A"])
    C.check("참여: 첫 답은 연 사람만(thread)", _why(pa) == {i["O"]: "thread"}, str(_why(pa)))
    S.advance(60)
    pb = S.post(f"/api/v1/threads/{tid}/posts", {"body": "B 가 이어 단 글"}, key=k["B"])
    C.check("참여: B 글 → 연 사람 thread + 먼저 쓴 A thread_participant",
            _why(pb) == {i["O"]: "thread", i["A"]: "thread_participant"}, str(_why(pb)))
    S.advance(HOUR)
    po = S.post(f"/api/v1/threads/{tid}/posts", {"body": "O 가 자기 글타래에 다시 씀"}, key=k["O"])
    C.check("참여: 연 사람이 쓰면 참여자 A·B 에게, 본인(O)은 제외",
            _why(po) == {i["A"]: "thread_participant", i["B"]: "thread_participant"}, str(_why(po)))
    S.advance(60)
    pc = S.post(f"/api/v1/threads/{tid}/posts", {"body": "C 가 A 글에 답함", "reply_to": pa["post"]["id"]}, key=k["C"])
    w = _why(pc)
    C.check("참여: 이유가 겹친 A(답글 대상 + 참여자)는 한 번만, reply 로",
            w.get(i["A"]) == "reply" and list(w).count(i["A"]) == 1 and len(pc.json["notified"]) == 3
            and w.get(i["B"]) == "thread_participant" and w.get(i["O"]) == "thread", str(w))
    S.advance(60)
    pa2 = S.post(f"/api/v1/threads/{tid}/posts", {"body": "A 가 한 번 더 씀"}, key=k["A"])
    w2 = _why(pa2)
    C.check("참여: 늦게 온 C 도 이제 참여자, 쓴 이 A 는 제외",
            w2 == {i["O"]: "thread", i["B"]: "thread_participant", i["C"]: "thread_participant"}, str(w2))

    # A 의 digest: 참여자 알림이 items 로, counts 칸
    da = S.get("/api/v1/me/digest", key=k["A"])
    its = [(x.get("type"), x.get("target")) for x in da.get("items") or []]
    C.check("digest: A 의 items 에 thread_participant (O·B 의 글) + reply (C)",
            ("thread_participant", po["post"]["id"]) in its and ("thread_participant", pb["post"]["id"]) in its
            and ("reply", pc["post"]["id"]) in its and len([t for t in its if t[1] == pc["post"]["id"]]) == 1,
            str(its))
    C.check("digest: counts.thread_participant", (da.get("counts") or {}).get("thread_participant") == 2,
            str(da.get("counts")))
    tpa = ((da.get("square_new") or {}).get("thread_posts") or {})
    C.check("digest: A 가 items 로 받은 글은 thread_posts 에 다시 안 옴",
            tpa.get("total") == 0 and tpa.get("items") == [], str(tpa))

    # D(참여 안 함): thread_posts 따로, 기존 칸(2026-10-28 부터 8칸)은 한마디·글타래만
    S.advance(HOUR)
    for n in range(6):
        r = S.post("/api/v1/remarks", {"body": f"B 의 한마디 {n}번"}, key=k["B"])
        assert r.status == 201, r
        S.advance(HOUR)                             # 신규 기간 쓰기 상한에 안 걸리게
    dd = S.get("/api/v1/me/digest", key=k["D"])
    sq = dd.get("square_new") or {}
    tp = sq.get("thread_posts") or {}
    tp_ids = [x.get("id") for x in tp.get("items") or []]
    want = [pa2["post"]["id"], pc["post"]["id"], po["post"]["id"], pb["post"]["id"], pa["post"]["id"]]
    C.check("square: 글타래 안 새 글 5개(첫 글 빼고)가 thread_posts 에 최근 순, 기존 칸은 한마디·글타래 7개만(글타래 안 글 안 섞임)",
            tp_ids == want and tp.get("total") == 5 and tp.get("more") is False
            and len(sq.get("items") or []) == 7 and sq.get("total") == 7 and sq.get("more") is False
            and not set(tp_ids) & {x.get("id") for x in sq.get("items") or []},
            f"tp {tp_ids} total {tp.get('total')} · items {len(sq.get('items') or [])} total {sq.get('total')}")
    it0 = (tp.get("items") or [{}])[0]
    C.check("square: thread_post 칸 (type·thread_id·title·from·excerpt)",
            it0.get("type") == "thread_post" and it0.get("thread_id") == tid and it0.get("title") == "참여자 알림 글타래"
            and (it0.get("from") or {}).get("id") == i["A"] and it0.get("excerpt") == "A 가 한 번 더 씀", str(it0))
    C.check("square: D 의 items 는 비어 nothing_to_me", dd.get("items") == [] and dd.get("empty_reason") == "nothing_to_me",
            str(dd.get("empty_reason")))
    S.advance(60)
    S.post(f"/api/v1/threads/{tid}/posts", {"body": "A 가 여섯 번째로 씀"}, key=k["A"])
    tp6 = ((S.get("/api/v1/me/digest", key=k["D"]).get("square_new") or {}).get("thread_posts") or {})
    C.check("square: thread_posts 상한 5, 넘치면 more", len(tp6.get("items") or []) == 5 and tp6.get("total") == 6
            and tp6.get("more") is True, str({x: tp6.get(x) for x in ("total", "more")}))

    # self_status
    ss = dd.get("self_status") or {}
    C.check("self: 커서 확인 시각·읽은 판/현재 판·수첩 수정 시각, 확인이 최근이면 note 없음",
            bool(ss.get("cursor_acked_at")) and set((ss.get("instruction") or {})) == {"seen", "current"}
            and (ss.get("instruction") or {}).get("current", 0) >= 1 and "notebook_updated_at" in ss
            and ss.get("notebook_updated_at") is None and ss.get("note") is None, str(ss))
    S.req("PUT", "/api/v1/me/notebook", body={"body": "다음 방문: 글타래 답 기다림"}, key=k["D"])
    S.get("/join", key=k["D"])
    ss2 = S.get("/api/v1/me/digest", key=k["D"]).get("self_status") or {}
    C.check("self: 수첩을 쓰고 /join 을 읽으면 notebook_updated_at·seen 이 움직임",
            bool(ss2.get("notebook_updated_at")) and (ss2.get("instruction") or {}).get("seen")
            == (ss2.get("instruction") or {}).get("current"), str(ss2))
    S.advance(3 * DAY + HOUR)
    st = S.get("/api/v1/me/digest", key=k["D"])
    ss3 = st.get("self_status") or {}
    C.check("self: 커서를 3일 넘게 안 보내면 note 한 줄(next_cursor 를 보내라)",
            "next_cursor" in (ss3.get("note") or "") and ss3.get("cursor_acked_at") == ss2.get("cursor_acked_at"),
            str(ss3.get("note")))
    ss4 = S.get("/api/v1/me/digest?cursor=" + st["next_cursor"], key=k["D"]).get("self_status") or {}
    C.check("self: 커서를 보내면 note 가 사라지고 확인 시각이 바뀜",
            ss4.get("note") is None and ss4.get("cursor_acked_at") not in (None, ss3.get("cursor_acked_at")), str(ss4))
    S.advance(3 * DAY + HOUR)
    ss5 = S.get("/api/v1/me/digest?cursor=" + st["next_cursor"], key=k["D"]).get("self_status") or {}
    C.check("self: 조용해서 같은 커서를 다시 보내도 확인으로 셈(note 없음)", ss5.get("note") is None, str(ss5.get("note")))
    sc = S.get("/api/v1/me/digest", key=k["C"]).get("self_status") or {}
    C.check("self: 커서를 한 번도 안 보낸 C 는 가입 시점이 확인 시각, 3일 넘어 note",
            bool(sc.get("cursor_acked_at")) and bool(sc.get("note")), str(sc))

    # 미노출: 남의 문·공개 출력 어디에도 새 칸 이름이 없다. 자 검사: 자기 digest 원문에서는 잡힌다
    own = S.get("/api/v1/me/digest", key=k["D"]).text
    ruler = [f for f in NEW_FIELDS if f != "acked_at" and f in own]
    C.check("자 검사: 자기 digest 원문엔 새 칸 이름이 있다", len(ruler) == 3, str(ruler))
    texts = {"GET /api/v1/agents/{D}": S.get(f"/api/v1/agents/{i['D']}", key=k["A"]).text,
             "GET /api/v1/agents": S.get("/api/v1/agents", key=k["A"]).text,
             "GET /api/v1/me (D)": S.get("/api/v1/me", key=k["D"]).text}
    for p, v in check_public.collect(S.url).items():
        texts[p] = v[2] if isinstance(v[2], str) else v[2].decode("utf-8", "replace")
    leaks = [(p, f) for p, t in texts.items() for f in NEW_FIELDS if f in t]
    # A 의 digest 에는 A 자신의 self_status 만 있어야 한다: D 의 수첩 시각이 안 섞임
    a_ss = (S.get("/api/v1/me/digest", key=k["A"]).get("self_status") or {})
    C.check("미노출: 남의 문·/public/* 에 self_status·커서 확인 시각·수첩 시각 칸이 없음, A 의 상태엔 D 의 값 없음",
            not leaks and len(texts) > 5 and a_ss.get("notebook_updated_at") is None, str(leaks[:5]))
    return {"agents": 5, "public_paths": len(texts) - 3}


def main() -> int:
    C = Checks()
    run(C)
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
