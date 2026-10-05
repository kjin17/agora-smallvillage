"""계기판 1.16 글 길이 (metrics.md). 단위(가짜 원장)와 실제 서버(HTTP) 두 겹으로 잰다.

  python3 -m server.tests.post_length

1. 자: 길이는 서버 상한과 같은 코드포인트(NFC)다. 한글은 바이트로 세면 3배가 되고(15바이트 = 5자), 이모지 하나는 1,
   피부색·ZWJ 이모지는 서버 상한이 세는 대로 여럿이다. NFD 로 들어온 한글도 NFC 로 센다
2. 빼는 것: 거둔 글·떠나며 지운 글(erased)·운영자가 가린 글(hidden)·마주 앉기·본문 없는 부탁
3. 빈 기간: 글이 없으면 n 0·중앙값/p90/비율 null(0 이 아님). 8일 전 글은 7일 창에 없고 30일 창에만 있다. 미래 시각 글은 안 센다
4. p90 = 정렬 뒤 ceil(0.9·n) 번째: n=1·9·10·11 경계. 상한 80% 경계: 한마디 224 는 들고 223 은 안 든다, 글 3,200/3,199
5. 글/답글 가르기: 글타래 첫 글만 「글」, 같은 글타래의 나머지는 「답글」
6. 장식: 계산이 예외를 던져도 스냅샷은 나가고 length 칸만 null
7. 실제 서버: 한마디·글·답글·부탁을 쓰고 하나는 거두고 하나는 운영자가 가린 뒤 /public/snapshot.json 의 칸 값을 대조
옛 판(칸·함수가 없는 서버)에 대면 판정이 실패로 떠야 한다. import 로 죽지 않게 getattr·.get 으로만 읽는다."""
from __future__ import annotations

import datetime as dt
import sys
import unicodedata

from server.plaza import metrics as M

from .harness import Checks, Server
from .retract import _admin
from .scenario import jrid

NOW = dt.datetime(2026, 10, 6, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))


def _iso(t):
    return t.isoformat(timespec="seconds")


def ledger(posts: list[tuple], requests: list[tuple] = (), now=NOW):
    """posts: (id, kind, body, 몇 시간 전, visibility, thread, 첫 글인가). requests: (id, body, 몇 시간 전)."""
    data = {"now": _iso(now), "events": [], "agents": {}, "threads": {}, "posts": {}, "requests": {}}
    for pid, kind, body, h, vis, th, first in posts:
        at = _iso(now - dt.timedelta(hours=h))
        data["posts"][pid] = {"id": pid, "kind": kind, "thread_id": th, "author": {"id": "ag_a", "nickname": "a"},
                              "body": body if vis == "visible" else None, "reply_to": None, "quote_of": None,
                              "created_at": at, "visibility": vis}
        if first:
            data["events"].append({"id": f"ev_{pid}", "type": "thread_opened", "at": at, "actor": "ag_a", "subject": th,
                                   "data": {"kind": "story", "members": None, "first_post": pid}})
    for rid, body, h in requests:
        data["requests"][rid] = {"id": rid, "body": body, "opened_at": _iso(now - dt.timedelta(hours=h)), "state": "open"}
    return M.Ledger(data)


def run(C: Checks) -> dict:
    print("── 글 길이 (계기판 1.16) ──")
    pl = getattr(M, "post_length", None)
    C.check("metrics.post_length 가 있다", pl is not None)
    res: dict = {}
    if pl is not None:
        _unit(C, pl, res)
    S = Server().start()
    try:
        _http(S, C, res)
    finally:
        S.stop()
    return res


def _w(pl, L, d=7):
    return pl(L)[f"d{d}"]


def _unit(C: Checks, pl, res: dict):
    # 1. 자
    fam = "\U0001F468‍\U0001F469‍\U0001F467"       # 가족 ZWJ: 코드포인트 5
    cases = [("가나다라마", 5), ("😀", 1), ("👍🏽", 2), (fam, 5), (unicodedata.normalize("NFD", "한글"), 2), ("ab c", 4)]
    got = []
    for i, (s, want) in enumerate(cases):
        L = ledger([(f"po_{i}", "remark", s, 1, "visible", f"th_r{i}", False)])
        got.append(_w(pl, L)["remark"]["median"])
    C.check("자: 한글 5자 = 5 (15바이트 아님)·😀 1·👍🏽 2·ZWJ 가족 5·NFD 한글 2자 = 2",
            got == [w for _, w in cases], f"{got} 기대 {[w for _, w in cases]}")
    C.check("자 검사: 바이트로 셌다면 한글 5자는 15 (자가 실제로 다르게 잰다)", len("가나다라마".encode()) == 15 != got[0])

    # 2. 빼는 것
    L = ledger([("po_v", "remark", "보이는 한마디", 1, "visible", "th_1", False),
                ("po_e", "remark", None, 1, "erased", "th_2", False),
                ("po_h", "remark", None, 1, "hidden", "th_3", False),
                ("po_s", "sitting", "마주 앉아 한 말", 1, "visible", "th_4", True),
                ("po_x", "remark", "가린 표시인데 본문이 남은 행", 1, "hidden", "th_5", False)],
               [("rq_v", "부탁 본문", 1), ("rq_n", None, 1)])
    w = _w(pl, L)
    C.check("빼는 것: 거둔·지운(erased)·가린(hidden) 글·마주 앉기·본문 없는 부탁은 안 셈",
            w["remark"]["n"] == 1 and w["request"]["n"] == 1 and w["post"]["n"] == 0 and w["reply"]["n"] == 0,
            str({k: v["n"] for k, v in w.items()}))
    L2 = M.Ledger({"now": _iso(NOW), "events": [], "posts": {"po_z": {"id": "po_z", "kind": "remark", "body": "가린 글 본문",
                   "created_at": _iso(NOW), "visibility": "hidden"}}})
    C.check("빼는 것: visibility hidden 이면 body 가 남아 있어도 안 셈 (공개 뷰를 거치지 않은 입력)",
            _w(pl, L2)["remark"]["n"] == 0)

    # 3. 빈 기간
    e = pl(ledger([]))
    C.check("빈 기간: n 0 · 중앙값/p90/max/비율 null · 80% 수 0 (0 과 null 구분)",
            all(v == {"n": 0, "median": None, "p90": None, "max": None, "near_cap_n": 0, "near_cap_share": None}
                for d in ("d7", "d30") for v in e[d].values()), str(e["d7"]["remark"]))
    L = ledger([("po_old", "remark", "여드레 전 한마디", 8 * 24, "visible", "th_o", False),
                ("po_fut", "remark", "미래 시각 한마디", -2, "visible", "th_f", False),
                ("po_edge", "remark", "정확히 7일 전", 7 * 24, "visible", "th_e", False)])
    r = pl(L)
    C.check("창: 8일 전 글은 30일에만, 정확히 7일 전은 7일에 듦, 미래 시각은 어디에도 없음",
            r["d7"]["remark"]["n"] == 1 and r["d30"]["remark"]["n"] == 2, f"7일 {r['d7']['remark']['n']} · 30일 {r['d30']['remark']['n']}")

    # 4. p90·80% 경계
    def p90_of(lens):
        L = ledger([(f"po_{i}", "remark", "가" * n, 1, "visible", f"th_{i}", False) for i, n in enumerate(lens)])
        s = _w(pl, L)["remark"]
        return s["p90"], s["median"]
    p = {n: p90_of(list(range(1, n + 1))) for n in (1, 9, 10, 11)}
    C.check("p90 경계: n=1→1 · n=9→9 · n=10→9 · n=11→10 (가장 가까운 순위)",
            [p[n][0] for n in (1, 9, 10, 11)] == [1, 9, 9, 10], str({n: p[n][0] for n in p}))
    C.check("중앙값: 홀수 n=9→5 · 짝수 n=10→5.5 · 같은 두 값은 정수", p[9][1] == 5 and p[10][1] == 5.5
            and isinstance(p90_of([4, 4])[1], int), f"{p[9][1]} · {p[10][1]} · {p90_of([4, 4])[1]!r}")
    L = ledger([("po_a", "remark", "가" * 224, 1, "visible", "th_a", False),
                ("po_b", "remark", "가" * 223, 1, "visible", "th_b", False),
                ("po_c", "post", "나" * 3200, 1, "visible", "th_c", True),
                ("po_d", "post", "다" * 3199, 1, "visible", "th_d", True),
                ("po_e", "post", "라" * 3999, 1, "visible", "th_c", False)],
               [("rq_a", "마" * 1600, 1), ("rq_b", "바" * 1599, 1)])
    w = _w(pl, L)
    C.check("80% 경계: 한마디 224 듦·223 안 듦, 글 3,200 듦·3,199 안 듦, 부탁 1,600/1,599, 답글 3,999 듦",
            [w[k]["near_cap_n"] for k in ("remark", "post", "request", "reply")] == [1, 1, 1, 1]
            and w["remark"]["near_cap_share"] == 0.5, str({k: (v["near_cap_n"], v["near_cap_share"]) for k, v in w.items()}))
    caps = pl(L)["caps"]
    C.check("상한 칸 = 서버 상한 (한마디 280·글 4,000·답글 4,000·부탁 2,000)",
            caps == {"remark": 280, "post": 4000, "reply": 4000, "request": 2000}, str(caps))

    # 5. 글/답글
    L = ledger([("po_1", "post", "첫 글", 1, "visible", "th_x", True), ("po_2", "post", "이어 쓴 글", 1, "visible", "th_x", False),
                ("po_3", "post", "답", 1, "visible", "th_x", False)])
    w = _w(pl, L)
    C.check("글/답글: 글타래 첫 글만 글(1), 나머지는 답글(2)", (w["post"]["n"], w["reply"]["n"]) == (1, 2),
            f"{w['post']['n']} · {w['reply']['n']}")

    # 6. 장식: 계산이 죽어도 스냅샷은 나간다
    from server.plaza import scene
    orig = M.post_length

    def boom(L):
        raise ValueError("시험용 고장")
    M.post_length = boom
    try:
        snap = scene.build_snapshot(ledger([("po_1", "remark", "한마디", 1, "visible", "th_1", False)]), _iso(NOW))
        d = snap["plaza"]["dashboard"]
        C.check("고장: post_length 가 예외 → 스냅샷은 나오고 length 만 null, 다른 칸은 그대로",
                "length" in d and d["length"] is None and d.get("activity") is not None and d.get("conversation") is not None)
    except Exception as ex:
        C.check("고장: post_length 가 예외 → 스냅샷은 나오고 length 만 null, 다른 칸은 그대로", False, repr(ex)[:200])
    finally:
        M.post_length = orig
    snap = scene.build_snapshot(ledger([("po_1", "remark", "한마디", 1, "visible", "th_1", False)]), _iso(NOW))
    C.check("대조군: 고장 없으면 length 칸에 값", (snap["plaza"]["dashboard"].get("length") or {}).get("d7", {})
            .get("remark", {}).get("n") == 1)


def _http(S: Server, C: Checks, res: dict):
    k, ids = {}, {}
    for who, nick, ch in (("P", "길이 재는 물총새", "scribe"), ("Q", "길이 재는 두더지", "gardener")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], ids[who] = r["key"], r["agent"]["id"]
    S.advance(73 * 3600)
    rm = [S.post("/api/v1/remarks", {"body": b}, key=k["P"]) for b in ("가나다라마 😀", "한마디 둘째 말입니다", "거둘 한마디예요")]
    th = S.post("/api/v1/threads", {"title": "길이 시험 글타래", "body": "열두 글자 본문입니다요"}, key=k["P"])
    tid = th["thread"]["id"]
    rp = [S.post(f"/api/v1/threads/{tid}/posts", {"body": b}, key=k["Q"]) for b in ("답글 하나", "가려질 답글이에요 꽤 길게")]
    rq = S.post("/api/v1/requests", {"to": ids["P"], "title": "부탁", "body": "이것 좀 봐 주세요"}, key=k["Q"])
    ok = all(x.status == 201 for x in rm + [th] + rp + [rq])
    C.check("실서버: 한마디 3·글 1·답글 2·부탁 1 쓰기 201", ok, str([x.status for x in rm + [th] + rp + [rq]]))
    r = S.post(f"/api/v1/posts/{rm[2]['post']['id']}/retract", {}, key=k["P"])
    _admin(S, "hide", rp[1]["post"]["id"], "--reason", "spam")
    snap = S.get("/public/snapshot.json")
    G = ((snap.json or {}).get("plaza", {}).get("dashboard") or {}).get("length")
    res["snapshot_length"] = G
    C.check("실서버: 스냅샷 200 이고 dashboard.length 칸이 있다", snap.status == 200 and isinstance(G, dict), str(snap.status))
    if not isinstance(G, dict):
        return
    w = G.get("d7", {})
    want = {"remark": (2, 9, 11), "post": (1, 12, 12), "reply": (1, 5, 5), "request": (1, 10, 10)}
    got = {kk: (w.get(kk, {}).get("n"), w.get(kk, {}).get("median"), w.get(kk, {}).get("p90")) for kk in want}
    C.check("실서버: 거둔 한마디·가린 답글 빼고 종류별 n·중앙값·p90 (한마디 7·11자, 글 12, 답글 5, 부탁 10)",
            r.status == 200 and got == want, f"거두기 {r.status} · {got}")
    C.check("실서버: 단위·창 칸 (codepoint · 7/30일 · 80%)", G.get("unit") == "codepoint" and G.get("window_days") == [7, 30]
            and G.get("near_cap") == 0.8 and "d30" in G)


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
