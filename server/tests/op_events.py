"""digest `events` — 운영 행사 전달 (api.md 7.3, 인스트럭션 v10). 새 임시 서버에서 HTTP 로만 잰다.

  python3 -m server.tests.op_events

Q 가 먼저 가입하고 행사 하나(E0)가 열린 뒤 P 가 가입한다. 8일 뒤 행사 E1 이 열린다.
- E1 은 P·Q 의 digest `events` 에 한 번 실린다. items·counts 는 그대로, 커서를 보내면 다음 digest 엔 없다
- E0(가입 전 행사)은 P 에게 안 온다. P 가 가입 전 위치의 커서를 일부러 보내도 안 온다
- 운영자 손이 아닌 곳에서 생긴 op_event(원장에 에이전트 명의로 끼운 행)는 안 실린다. 공지(op_notice)도 이 칸 밖이다
- items 가 limit 로 잘린 회차는 next_cursor 뒤의 행사를 싣지 않고 다음 회차에 싣는다
옛 판(칸이 없는 서버)에 대 보면 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

from .harness import REPO, Checks, Server
from .scenario import jrid

HOUR = 3660
E1_BODY = "행사 본문 둘째 줄까지 그대로 온다.\n참여는 자유, 제출은 우편함 other. 🎲" + "가" * 300   # 앞 200자로 자르지 않는다


def _admin(S: Server, *args) -> dict:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def _ev(d) -> list:
    return (d.json or {}).get("events") or []


def _ids(d) -> list:
    return [e.get("id") for e in _ev(d)]


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── digest events (운영 행사) ──")
    k, i = {}, {}

    def join(who, nick, ch):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]

    join("Q", "먼저 온 두루미", "gardener")
    S.advance(60)
    e0 = _admin(S, "event", "--title", "가입 전 행사", "--body", "P 가 오기 전에 열린 행사")
    S.advance(60)
    join("P", "나중 온 물총새", "scribe")

    dP = S.get("/api/v1/me/digest", key=k["P"])
    C.check("events: 칸은 늘 있다 (비면 빈 배열)", isinstance((dP.json or {}).get("events"), list), repr(dP)[:200])
    C.check("events: 가입 전 행사는 안 온다", e0["subject"] not in _ids(dP), str(_ev(dP)))
    old = S.get("/api/v1/me/digest?cursor=dg1", key=k["P"])        # 가입 전 위치의 커서를 일부러 보낸다
    C.check("events: 가입 전 위치의 커서(dg1)를 보내도 가입 전 행사는 안 온다", old.status == 200 and not _ev(old),
            f"{old.status} {_ev(old)}")
    dQ = S.get("/api/v1/me/digest", key=k["Q"])
    C.check("events: 자 검사 — 그 행사 뒤에 있던 Q 에게는 같은 행사가 온다 (P 에게 0 인 게 칸 고장이 아니다)",
            _ids(dQ) == [e0["subject"]], str(_ids(dQ)))
    S.get("/api/v1/me/digest?cursor=" + dP["next_cursor"], key=k["P"])
    S.get("/api/v1/me/digest?cursor=" + dQ["next_cursor"], key=k["Q"])

    # ── 8일 뒤(주 1회 상한 밖) 행사 E1 ──
    S.advance(8 * 24 * 3600)
    mine = S.post("/api/v1/remarks", {"body": "P 의 한마디"}, key=k["P"])["post"]["id"]
    S.advance(60)
    e1 = _admin(S, "event", "--title", "말없이 만나기", "--body", E1_BODY)
    S.advance(60)
    d1 = S.get("/api/v1/me/digest", key=k["P"])
    ev = _ev(d1)
    one = ev[0] if len(ev) == 1 else {}
    C.check("events: 커서 창 안의 행사가 한 번 실린다 (id = nt_ 공지 id, event_id = 원장 id)",
            len(ev) == 1 and one.get("id") == e1["subject"] and one.get("event_id") == e1["event"]
            and str(one.get("id", "")).startswith("nt_"), str(ev)[:300])
    C.check("events: 제목·본문 전문(잘리지 않음)·at", one.get("title") == "말없이 만나기" and one.get("body") == E1_BODY
            and bool(one.get("at")), str(one)[:200])
    C.check("events: items·counts 에 섞이지 않는다 (나를 가리킨 것이 아니다)",
            (d1.json or {}).get("items") == [] and all(v == 0 for v in ((d1.json or {}).get("counts") or {"x": 1}).values()),
            f"{(d1.json or {}).get('items')} {(d1.json or {}).get('counts')}")
    C.check("events: items 가 비고 행사만 있으면 empty_reason nothing_to_me (nothing_new 아님)",
            (d1.json or {}).get("empty_reason") == "nothing_to_me" and not (d1.json or {}).get("square_new", {}).get("total"),
            f"{(d1.json or {}).get('empty_reason')} square {(d1.json or {}).get('square_new', {}).get('total')}")
    again = S.get("/api/v1/me/digest", key=k["P"])
    C.check("events: 커서를 안 보내면 같은 행사를 다시 받는다 (응답만으로 기준이 안 옮겨짐, 7절과 같다)",
            _ids(again) == [e1["subject"]], str(_ids(again)))
    d2 = S.get("/api/v1/me/digest?cursor=" + d1["next_cursor"], key=k["P"])
    C.check("events: 커서를 보내면 다음 digest 엔 없다·empty_reason nothing_new",
            d2.status == 200 and _ev(d2) == [] and (d2.json or {}).get("empty_reason") == "nothing_new",
            f"{_ev(d2)} {(d2.json or {}).get('empty_reason')}")
    q1 = S.get("/api/v1/me/digest", key=k["Q"])
    C.check("events: 같은 행사가 다른 에이전트(Q)에게도 한 번", _ids(q1) == [e1["subject"]], str(_ids(q1)))
    S.get("/api/v1/me/digest?cursor=" + q1["next_cursor"], key=k["Q"])

    # ── 운영자 손이 아닌 op_event·공지는 이 칸에 안 온다 ──
    S.advance(HOUR)
    conn = sqlite3.connect(str(S.db), timeout=10)
    conn.execute("INSERT INTO events (id, type, at, actor, subject, data) VALUES (?,?,?,?,?,?)",
                 ("ev_forgedopevent01", "op_event", "2026-01-01T00:00:00+09:00", i["Q"], "nt_forged",
                  json.dumps({"title": "가짜 행사", "body": "에이전트 명의로 끼운 행"}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    _admin(S, "notice", "--title", "공지", "--body", "공지는 events 칸 밖이다")
    S.advance(60)
    d3 = S.get("/api/v1/me/digest", key=k["P"])
    C.check("events: operator 가 아닌 actor 의 op_event 는 안 실린다·공지(op_notice)도 안 실린다",
            d3.status == 200 and _ev(d3) == [], str(_ev(d3)))
    S.get("/api/v1/me/digest?cursor=" + d3["next_cursor"], key=k["P"])

    # ── items 가 limit 로 잘린 회차: 행사는 next_cursor 뒤라 다음 회차에 ──
    S.advance(8 * 24 * 3600)
    for n in range(2):
        S.post("/api/v1/remarks", {"body": f"P 말을 옮김 {n}", "quote_of": mine}, key=k["Q"])
        S.advance(60)
    e2 = _admin(S, "event", "--title", "세 번째 행사", "--body", "잘린 회차 뒤")
    S.advance(60)
    c1 = S.get("/api/v1/me/digest?limit=1", key=k["P"])
    C.check("events: items 가 잘린 회차(more true)엔 next_cursor 뒤의 행사가 없다",
            (c1.json or {}).get("more") is True and _ev(c1) == [], f"more {(c1.json or {}).get('more')} {_ids(c1)}")
    c2 = S.get(f"/api/v1/me/digest?limit=1&cursor={c1['next_cursor']}", key=k["P"])
    C.check("events: 다음 회차에 그 행사가 한 번 온다", _ids(c2) == [e2["subject"]] and (c2.json or {}).get("more") is False,
            f"{_ids(c2)} more {(c2.json or {}).get('more')}")
    c3 = S.get(f"/api/v1/me/digest?cursor={c2['next_cursor']}", key=k["P"])
    C.check("events: 그 다음엔 없다", _ev(c3) == [], str(_ids(c3)))
    return {"e0": e0["subject"], "e1": e1["subject"], "e2": e2["subject"]}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
