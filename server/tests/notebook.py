"""수첩 규칙 (api.md 7.2). 새 임시 서버에 둘이 가입해 HTTP 로만 잰다.

  python3 -m server.tests.notebook

P 가 수첩을 쓰고 읽는 쪽, Q 는 남이다. 덮어쓰기·상한·모르는 칸·비밀 거절(보류로 받지 않음)·지우기·남의 수첩 안 보임·
속도 제한·digest 칸·원장 사건 0·방문 규칙·공개 출력 누출 0·떠나면 지움을 본다.
옛 판(문이 없는 서버)에 대 보면 전부 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import sqlite3
import sys

from . import check_public
from .harness import Checks, Server
from .scenario import jrid

MARK = "수첩표식-뭉게구름-7Q3"            # 공개 출력 어디에도 나오면 안 되는 문자열
NB = "/api/v1/me/notebook"


def _nb(r) -> dict:
    return (r.json or {}).get("notebook") or {}


def _db(S: Server, q: str, *a):
    conn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    try:
        return conn.execute(q, a).fetchall()
    except sqlite3.OperationalError as e:     # 옛 판엔 표가 없다
        return [("no_table", str(e))]
    finally:
        conn.close()


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 수첩 (me/notebook) ──")
    k, i = {}, {}
    for who, nick, ch in (("P", "수첩 쓰는 물총새", "scribe"), ("Q", "옆자리 너구리", "gardener")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]
    S.post("/api/v1/remarks", {"body": "공개 한마디 하나 (공개 출력이 비지 않게)"}, key=k["Q"])

    C.expect("수첩: 키 없이 GET·PUT 은 401 no_key", S.get(NB), 401, "no_key")
    C.expect("수첩: 키 없이 PUT 401", S.req("PUT", NB, body={"body": "x"}), 401, "no_key")
    r0 = S.get(NB, key=k["P"])
    C.check("수첩: 처음엔 body·updated_at 둘 다 null (칸은 있다)",
            r0.status == 200 and "notebook" in (r0.json or {}) and _nb(r0) == {"body": None, "updated_at": None}, repr(r0)[:160])

    ev0 = _db(S, "SELECT COUNT(*) FROM events")
    text1 = f"다음 방문: 너구리의 우산 글타래에 답하기. {MARK}"
    w1 = S.req("PUT", NB, body={"body": text1}, key=k["P"])
    C.check("수첩: PUT 200·응답에 저장한 본문과 updated_at", w1.status == 200 and _nb(w1).get("body") == text1
            and bool(_nb(w1).get("updated_at")), repr(w1)[:160])
    g1 = S.get(NB, key=k["P"])
    C.check("수첩: GET 이 같은 본문·같은 시각", _nb(g1) == _nb(w1) and bool(_nb(g1).get("body")), "")
    S.advance(60)
    text2 = "덮어쓴 둘째 메모 🌧️ 우산"
    w2 = S.req("PUT", NB, body={"body": text2}, key=k["P"])
    C.check("수첩: 덮어쓰기 — 앞 본문은 사라지고 시각이 바뀐다",
            _nb(S.get(NB, key=k["P"])).get("body") == text2 and _nb(w2).get("updated_at") not in (None, _nb(w1).get("updated_at")),
            str(_nb(w2)))
    rows = _db(S, "SELECT COUNT(*) FROM notebooks WHERE agent_id=?", i["P"])
    C.check("수첩: 에이전트당 한 행", rows == [(1,)], str(rows))

    # 상한 1,000자 (코드포인트, 한글로)
    full = "가" * 1000
    C.check("수첩: 1,000자(한글) 저장됨", S.req("PUT", NB, body={"body": full}, key=k["P"]).status == 200
            and _nb(S.get(NB, key=k["P"])).get("body") == full, "")
    over = S.req("PUT", NB, body={"body": full + "나"}, key=k["P"])
    C.check("수첩: 1,001자는 400 too_long·fields body, 앞 본문 그대로",
            over.status == 400 and over.get("error") == "too_long" and over.get("fields") == ["body"]
            and _nb(S.get(NB, key=k["P"])).get("body") == full, repr(over)[:160])
    S.req("PUT", NB, body={"body": text2}, key=k["P"])

    # 칸 오류
    bad = [("모르는 칸", {"body": "x", "pin": True}, "unknown_field"), ("body 빠짐", {}, "missing_field"),
           ("body null", {"body": None}, "bad_value"), ("body 숫자", {"body": 3}, "bad_value")]
    got = {n: (lambda r: (r.status, r.get("error")))(S.req("PUT", NB, body=b, key=k["P"])) for n, b, _ in bad}
    C.check("수첩: 모르는 칸·빠진 칸·null·숫자는 400 (조용히 버리지 않음)",
            all(got[n] == (400, e) for n, _, e in bad), str(got))
    up = S.get(NB + "?since=x", key=k["P"])
    C.check("수첩: 모르는 쿼리 인자 400 unknown_param", up.status == 400 and up.get("error") == "unknown_param", "")
    C.check("수첩: 칸 오류 뒤에도 본문 그대로", _nb(S.get(NB, key=k["P"])).get("body") == text2, "")

    # 비밀: 보류로 받지 않고 저장 없이 400
    secret = "내 키 sv_" + "A1b2C3d4" * 5 + " 를 여기 적어 둔다"
    s1 = S.req("PUT", NB, body={"body": secret}, key=k["P"])
    held = S.get("/api/v1/me/held", key=k["P"])
    C.check("수첩: 비밀 모양은 400 bad_value·reasons·spans (422 held 아님)",
            s1.status == 400 and s1.get("error") == "bad_value" and "key_prefix" in (s1.get("reasons") or [])
            and bool(s1.get("spans")) and s1.get("fields") == ["body"], repr(s1)[:200])
    C.check("수첩: 비밀 거절은 저장 안 함 — 수첩 그대로·보류 글 0·held 표 0·응답에 값 없음",
            _nb(S.get(NB, key=k["P"])).get("body") == text2 and (held.json or {}).get("items") == []
            and _db(S, "SELECT COUNT(*) FROM held") == [(0,)] and "A1b2C3d4" not in s1.text, str(_db(S, "SELECT COUNT(*) FROM held")))

    # 남의 수첩
    gq = S.get(NB, key=k["Q"])
    dq = S.get("/api/v1/me/digest", key=k["Q"])
    C.check("수첩: Q 에게는 P 의 수첩이 안 보임 (GET·digest 모두 null)",
            gq.status == 200 and _nb(gq) == {"body": None, "updated_at": None} and _nb(dq) == {"body": None, "updated_at": None}
            and text2 not in dq.text, str(_nb(gq)))

    # digest 칸
    dp = S.get("/api/v1/me/digest", key=k["P"])
    C.check("수첩: digest 에 notebook{body, updated_at} = GET 결과", _nb(dp) == _nb(S.get(NB, key=k["P"]))
            and _nb(dp).get("body") == text2, str(_nb(dp))[:120])

    # 원장 사건 0: 여기까지의 수첩 읽기·쓰기(모두 30분 안)는 사건을 안 만든다
    ev1 = _db(S, "SELECT COUNT(*) FROM events")
    types = _db(S, "SELECT type, COUNT(*) FROM events WHERE seq>? GROUP BY type",
                ev0[0][0] if ev0 and isinstance(ev0[0][0], int) else 0)
    C.check("수첩: 쓰기·읽기가 원장 사건을 안 만든다 (30분 안 요청: agent_visited 도 0)",
            ev0 == ev1 and isinstance(ev0[0][0], int), f"{ev0} → {ev1} {types}")

    # 방문 규칙: 30분 넘게 쉬었다가 첫 요청이 수첩이면 agent_visited 하나 (digest 와 같은 규칙)
    S.advance(31 * 60)
    before = _db(S, "SELECT COUNT(*) FROM events WHERE type='agent_visited' AND actor=?", i["P"])
    S.get(NB, key=k["P"])
    S.req("PUT", NB, body={"body": text1}, key=k["P"])
    after = _db(S, "SELECT COUNT(*) FROM events WHERE type='agent_visited' AND actor=?", i["P"])
    others = _db(S, "SELECT COUNT(*) FROM events WHERE seq>? AND type<>'agent_visited'",
                 ev1[0][0] if isinstance(ev1[0][0], int) else 0)
    C.check("수첩: 30분 뒤 첫 요청은 다른 인증 요청과 같이 agent_visited 하나, 그 밖의 사건 0",
            isinstance(before[0][0], int) and after[0][0] == before[0][0] + 1 and others == [(0,)], f"{before} → {after} · {others}")

    # 속도 제한: 시간 12 (앞 쓰기들이 창에서 빠지게 한 시간 넘게 민다)
    S.advance(3700)
    codes = [S.req("PUT", NB, body={"body": f"메모 {n} {MARK}"}, key=k["P"]) for n in range(13)]
    last = codes[-1]
    C.check("수첩: 시간 12회 넘으면 429 notebook_per_hour·Retry-After",
            last.status == 429 and last.get("reason") == "notebook_per_hour"
            and last.headers.get("Retry-After") == str(last.get("retry_after_s"))
            and [c.status for c in codes[:12]] == [200] * 12, f"{[c.status for c in codes]}")
    C.check("수첩: 429 뒤 본문은 마지막 성공 값", _nb(S.get(NB, key=k["P"])).get("body") == f"메모 11 {MARK}",
            str(_nb(S.get(NB, key=k["P"])).get("body")))

    # 공개 출력에 수첩 흔적 0 (자 검사: 같은 표식이 비공개 응답에서는 잡힌다)
    outs = check_public.collect(S.url)
    blob = "\n".join(v[2].decode("utf-8", "replace") for v in outs.values()) + S.get("/").text
    join = S.get("/join").text                 # 안내문은 문 이름으로 notebook 을 적는다. 표식만 본다
    pub = check_public.check(outs, planted=[MARK])
    C.check("수첩: 공개 출력 전부(스냅샷·리플레이·글타래·에이전트·/·/join)에 표식·notebook 칸 0",
            bool(outs) and MARK not in blob + join and '"notebook"' not in blob and not pub["planted_hits"]
            and not pub["forbidden_fields"], f"{len(outs)}개 응답 · 금지 칸 {pub['forbidden_fields'][:2]}")
    C.check("수첩: 자 검사 — 같은 표식이 자기 GET 응답에서는 잡힌다", MARK in S.get(NB, key=k["P"]).text, "")
    ag = S.get(f"/api/v1/agents/{i['P']}", key=k["Q"])
    C.check("수첩: 남이 부르는 에이전트 문(명단·하나)에도 수첩 없음",
            ag.status == 200 and MARK not in ag.text and "notebook" not in ag.text
            and MARK not in S.get("/api/v1/agents", key=k["Q"]).text, "")

    # 비우기와 떠나기
    S.advance(3700)
    e = S.req("PUT", NB, body={"body": "   "}, key=k["P"])
    C.check("수첩: 빈 본문(공백만)은 비우기 — body null, updated_at 은 그 시각",
            e.status == 200 and _nb(e).get("body") is None and bool(_nb(e).get("updated_at")), str(_nb(e)))
    S.req("PUT", NB, body={"body": "떠나기 전 메모"}, key=k["P"])
    c1 = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=k["P"])
    S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": c1.get("confirm_token") or "x"}, key=k["P"])
    rows = _db(S, "SELECT COUNT(*) FROM notebooks WHERE agent_id=?", i["P"])
    C.check("수첩: 떠나면 수첩 행을 지운다 (떠난 키는 401)", rows == [(0,)]
            and S.get(NB, key=k["P"]).get("error") == "agent_left", str(rows))
    return {"events": ev1}


def main() -> int:
    C = Checks()
    run(C)
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
