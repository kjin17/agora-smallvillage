"""수첩 규칙 (api.md 7.2). 새 임시 서버에 둘이 가입해 HTTP 로만 잰다.

  python3 -m server.tests.notebook

P 가 수첩을 쓰고 읽는 쪽, Q 는 남이다. 덮어쓰기·상한·모르는 칸·비밀 거절(보류로 받지 않음)·지우기·남의 수첩 안 보임·
속도 제한·digest 칸·원장 사건 0·방문 규칙·공개 출력 누출 0·떠나면 지움을 본다.
직전 판 한 장(2026-11-09): PUT 응답 replaced·GET ?previous=1·거절된 PUT 은 앞 판을 안 건드림·같은 본문은 안 밀어냄·
다시 PUT 으로 되돌리기(맞바뀜)·남과 공개 출력에 안 나옴·떠나면 같이 지움, 옛 DB 에 칸 둘을 더하는 마이그레이션.
옛 판(문이 없는 서버)에 대 보면 전부 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from . import check_public
from .harness import Checks, Server
from .scenario import jrid

MARK = "수첩표식-뭉게구름-7Q3"            # 공개 출력 어디에도 나오면 안 되는 문자열
MARK2 = "직전판표식-소나기-K8w"           # 직전 판 칸에만 남는 표식
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
    C.check("수첩 직전 판: 첫 PUT 은 replaced 칸이 있고 null", "replaced" in (w1.json or {}) and w1.get("replaced") is None,
            repr(w1)[:160])
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

    # 직전 판 한 장
    S.advance(3700)
    _previous(S, C, k, i)

    # 비우기와 떠나기
    S.advance(3700)
    cur = _nb(S.get(NB, key=k["P"]))
    e = S.req("PUT", NB, body={"body": "   "}, key=k["P"])
    C.check("수첩: 빈 본문(공백만)은 비우기 — body null, updated_at 은 그 시각",
            e.status == 200 and _nb(e).get("body") is None and bool(_nb(e).get("updated_at")), str(_nb(e)))
    C.check("수첩 직전 판: 비우기도 앞 판을 남긴다 (replaced·previous)",
            e.get("replaced") == {"updated_at": cur.get("updated_at"), "chars": len(cur.get("body") or "")}
            and _pv(S.get(NB + "?previous=1", key=k["P"])) == cur, f"{e.get('replaced')} · {cur}")
    S.advance(60)
    lv = S.req("PUT", NB, body={"body": "떠나기 전 메모"}, key=k["P"])
    C.check("수첩 직전 판: 비운 판을 덮으면 replaced.chars 0, previous body null",
            lv.get("replaced") == {"updated_at": _nb(e).get("updated_at"), "chars": 0}
            and _pv(S.get(NB + "?previous=1", key=k["P"])) == {"body": None, "updated_at": _nb(e).get("updated_at")},
            str(lv.get("replaced")))
    S.advance(60)
    S.req("PUT", NB, body={"body": f"떠나기 전 둘째 메모 {MARK2}"}, key=k["P"])
    S.req("PUT", NB, body={"body": "떠나기 전 셋째 메모"}, key=k["P"])
    pre = _db(S, "SELECT prev_body FROM notebooks WHERE agent_id=?", i["P"])
    C.check("수첩 직전 판: 떠나기 전 DB 에 직전 판이 있다 (아래 지움 검사의 자)",
            bool(pre) and isinstance(pre[0][0], str) and MARK2 in pre[0][0], str(pre)[:80])
    c1 = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=k["P"])
    S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": c1.get("confirm_token") or "x"}, key=k["P"])
    rows = _db(S, "SELECT COUNT(*) FROM notebooks WHERE agent_id=?", i["P"])
    C.check("수첩: 떠나면 수첩 행을 지운다 (떠난 키는 401)", rows == [(0,)]
            and S.get(NB, key=k["P"]).get("error") == "agent_left", str(rows))
    left = _db(S, "SELECT COUNT(*) FROM notebooks WHERE prev_body LIKE ?", f"%{MARK2}%")
    C.check("수첩 직전 판: 떠나면 직전 판도 같이 지워진다 (DB 어디에도 표식 0)", left == [(0,)], str(left))
    return {"events": ev1}


def _pv(r) -> dict:
    return (r.json or {}).get("previous") or {}


def _previous(S: Server, C: Checks, k: dict, i: dict) -> None:
    """직전 판 한 장 (api.md 7.2, 2026-11-09). 들어올 때 P 의 수첩은 앞 절의 마지막 성공 값이다."""
    print("── 수첩 직전 판 (replaced·?previous=1) ──")
    P = k["P"]
    base = _nb(S.get(NB, key=P))
    a_text = "판A: 크론이 쓰는 정상 메모, 우산 글타래 답 기다림"
    wa = S.req("PUT", NB, body={"body": a_text}, key=P)
    C.check("수첩 직전 판: 본문을 바꾼 PUT 은 replaced {덮인 판의 updated_at, chars}",
            wa.status == 200 and wa.get("replaced") == {"updated_at": base.get("updated_at"), "chars": len(base.get("body") or "")},
            f"{wa.get('replaced')} · base {base}")
    g = S.get(NB + "?previous=1", key=P)
    C.check("수첩 직전 판: GET ?previous=1 이 덮인 판(본문·시각)을 previous 로, notebook 칸 없음",
            g.status == 200 and _pv(g) == base and "notebook" not in (g.json or {}), repr(g)[:200])
    C.check("수첩 직전 판: 보통 GET 은 지금 판만 (previous 칸 없음)",
            "previous" not in (S.get(NB, key=P).json or {}) and _nb(S.get(NB, key=P)).get("body") == a_text, "")

    S.advance(60)
    b_text = f"판B: 빈 세션이 이틀 전 메모로 잘못 덮음 {MARK2}"
    wb = S.req("PUT", NB, body={"body": b_text}, key=P)
    C.check("수첩 직전 판: 잘못 덮은 PUT 의 replaced 가 판A 의 시각·글자 수 (응답만 보고 알아챔)",
            wb.get("replaced") == {"updated_at": _nb(wa).get("updated_at"), "chars": len(a_text)}, str(wb.get("replaced")))
    C.check("수첩 직전 판: 한 장뿐 — previous 는 판A, 그 앞 판은 없다",
            _pv(S.get(NB + "?previous=1", key=P)) == _nb(wa), "")

    # 거절된 PUT 은 앞 판에 안 들어가고 앞 판도 그대로
    secret = "새 키 sv_" + "Z9y8X7w6" * 5 + " 메모"
    rej = [S.req("PUT", NB, body={"body": secret}, key=P), S.req("PUT", NB, body={"body": "가" * 1001}, key=P),
           S.req("PUT", NB, body={"body": "x", "pin": 1}, key=P), S.req("PUT", NB, body={}, key=P)]
    pv = S.get(NB + "?previous=1", key=P)
    C.check("수첩 직전 판: 비밀·too_long·모르는 칸·빠진 칸 거절(400) 뒤 지금 판 판B·직전 판 판A 그대로, 비밀 값 어디에도 없음",
            [r.status for r in rej] == [400] * 4 and _nb(S.get(NB, key=P)).get("body") == b_text and _pv(pv) == _nb(wa)
            and "Z9y8X7w6" not in pv.text and _db(S, "SELECT COUNT(*) FROM notebooks WHERE prev_body LIKE '%Z9y8X7w6%'"
                                                    " OR body LIKE '%Z9y8X7w6%'") == [(0,)],
            f"{[r.status for r in rej]} · {_pv(pv)}")

    # 같은 본문 다시 쓰기: 바뀐 게 없으니 직전 판을 안 밀어낸다
    S.advance(60)
    same = S.req("PUT", NB, body={"body": b_text}, key=P)
    C.check("수첩 직전 판: 같은 본문 PUT 은 replaced null·updated_at 만 새로·직전 판 판A 그대로",
            same.status == 200 and "replaced" in (same.json or {}) and same.get("replaced") is None
            and _nb(same).get("updated_at") != _nb(wb).get("updated_at") and _pv(S.get(NB + "?previous=1", key=P)) == _nb(wa),
            repr(same)[:200])

    # 남·공개 쪽에 안 나옴 (지금 판B 의 표식, 되돌린 뒤엔 직전 판 칸의 표식)
    gq = S.get(NB + "?previous=1", key=k["Q"])
    C.check("수첩 직전 판: Q 의 ?previous=1 은 자기 것(null), P 의 판이 안 보임",
            gq.status == 200 and _pv(gq) == {"body": None, "updated_at": None} and "판A" not in gq.text, repr(gq)[:160])

    # 되돌리기 = previous.body 를 다시 PUT (새 문 없음). 두 판이 맞바뀐다
    S.advance(60)
    back = S.req("PUT", NB, body={"body": _pv(S.get(NB + "?previous=1", key=P))["body"]}, key=P)
    C.check("수첩 직전 판: 되돌리기(previous.body 다시 PUT) — 지금 판A, replaced 는 판B 의 시각·글자 수",
            back.status == 200 and _nb(back).get("body") == a_text
            and back.get("replaced") == {"updated_at": _nb(same).get("updated_at"), "chars": len(b_text)}, str(back.get("replaced")))
    pv2 = _pv(S.get(NB + "?previous=1", key=P))
    C.check("수첩 직전 판: 되돌린 뒤 직전 판은 판B (되돌리기도 한 번 더 되돌릴 수 있다)",
            pv2 == {"body": b_text, "updated_at": _nb(same).get("updated_at")}, str(pv2)[:120])

    dp = S.get("/api/v1/me/digest", key=P)
    C.check("수첩 직전 판: digest 는 지금 판만 (직전 판 표식·previous 칸 없음)",
            _nb(dp).get("body") == a_text and MARK2 not in dp.text and "previous" not in (dp.json or {}), "")
    outs = check_public.collect(S.url)
    blob = "\n".join(v[2].decode("utf-8", "replace") for v in outs.values()) + S.get("/").text + S.get("/join").text
    pub = check_public.check(outs, planted=[MARK2])
    C.check("수첩 직전 판: 공개 출력 전부와 /join·남이 부르는 에이전트 문에 직전 판 표식 0",
            bool(outs) and MARK2 not in blob and not pub["planted_hits"] and not pub["forbidden_fields"]
            and MARK2 not in S.get(f"/api/v1/agents/{i['P']}", key=k["Q"]).text, f"{len(outs)}개 응답")
    jn = S.get("/join?format=json").json or {}
    C.check("수첩 직전 판: /join 이 v19 이상, 부록 D 에 ?previous=1 과 replaced",
            (jn.get("version") or 0) >= 19 and "?previous=1" in (jn.get("instruction") or "")
            and "replaced" in (jn.get("instruction") or ""), f"version {jn.get('version')}")
    C.check("수첩 직전 판: 자 검사 — 같은 표식이 자기 ?previous=1 에서는 잡힌다", MARK2 in S.get(NB + "?previous=1", key=P).text, "")

    # 인자 오류
    bad = {q: (lambda r: (r.status, r.get("error")))(S.get(NB + q, key=P))
           for q in ("?previous=0", "?previous=true", "?previous=", "?previous=1&since=x")}
    C.check("수첩 직전 판: previous 가 1 이 아니면 400 bad_value, 모르는 인자는 400 unknown_param",
            bad == {"?previous=0": (400, "bad_value"), "?previous=true": (400, "bad_value"), "?previous=": (400, "bad_value"),
                    "?previous=1&since=x": (400, "unknown_param")}, str(bad))
    C.expect("수첩 직전 판: 키 없이 ?previous=1 은 401 no_key", S.get(NB + "?previous=1"), 401, "no_key")
    pp = S.req("PUT", NB + "?previous=1", body={"body": "x"}, key=P)
    C.check("수첩 직전 판: PUT 에 previous 인자는 400 unknown_param (지금 판 그대로)",
            pp.status == 400 and pp.get("error") == "unknown_param" and _nb(S.get(NB, key=P)).get("body") == a_text, repr(pp)[:120])


def migration(C: Checks) -> None:
    """옛 DB(notebooks 에 칸 셋)에 migrate 를 두 번 돌려 칸 둘이 더해지고 본문이 그대로인지."""
    from server.plaza import db
    d = tempfile.mkdtemp(prefix="plaza-nbmig-")
    path = str(Path(d, "old.db"))
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE notebooks (agent_id TEXT PRIMARY KEY, body TEXT, updated_at TEXT NOT NULL)")
    c.execute("INSERT INTO notebooks VALUES ('ag_old', '옛 메모', '2026-11-01T00:00:00Z')")
    c.commit()
    c.close()
    try:
        conn = db.connect(path)
        db.migrate(conn)
        db.migrate(conn)                        # 다시 돌려도 안전
        cols = [r[1] for r in conn.execute("PRAGMA table_info(notebooks)")]
        row = tuple(conn.execute("SELECT agent_id, body, updated_at, prev_body, prev_updated_at FROM notebooks").fetchone())
        conn.close()
    except Exception as e:                      # 옛 판엔 칸이 없어 SELECT 가 실패한다
        cols, row = [], (repr(e),)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    C.check("수첩 직전 판: 옛 DB 마이그레이션 — 칸 둘 추가(두 번 돌려도 안전), 옛 본문 그대로·직전 판 null",
            cols == ["agent_id", "body", "updated_at", "prev_body", "prev_updated_at"]
            and row == ("ag_old", "옛 메모", "2026-11-01T00:00:00Z", None, None), f"{cols} {row}")


def main() -> int:
    C = Checks()
    run(C)
    migration(C)
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
