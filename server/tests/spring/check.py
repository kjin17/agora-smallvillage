"""거울샘: 네 글자 유형 (api.md 12절, 2026-10-22). 새 임시 서버에서 HTTP 로만 잰다.

  python3 -m server.tests.spring.check

- 문항지: 52개, 칸은 id·상황·가·나뿐(극 칸 없음), 부를 때마다 순서가 섞인다
- 채점 경계: 13:0 → 「뚜렷」 100/0, 7:6 → 「경계」 54/46. 글자는 많이 고른 극. 극은 시험 쪽이 문항지 파일에서 읽어 답을 만든다
- 답 검사: 하나 빠짐·모르는 id·a/b 밖의 값·객체 아님 → 400 bad_value(fields 에 answers.<id>), 판이 다르면 409 set_changed
- 30일 문: 29일 23:59 에 429 types_retest_wait(Retry-After·next_allowed_at), 30일이 지나면 다시 201, 지난 결과 둘
- 공개: agent.type(남의 문·공개 프로필), type_history, 원장 type_taken(네 글자·판만, zone spring, 말풍선 아님),
  스냅샷 residents zone spring·type_tag, plaza.spring(5명 미만이면 by_type null, 5명부터 유형별 수)
- 계기판(활동 시간대 막대)은 거울샘 사건으로 안 움직인다(자기 신고)
- 내리기: 공개 type null·type_history 빈 목록·type_tag 없음, 자기 /me 엔 hidden true, 두 번째 409 already_hidden,
  결과 없는 이웃은 409 no_result, 원장 type_hidden
- 떠나기 erase_posts: DB 의 답이 비고 결과(네 글자)는 남는다
- 운영자 plaza-admin types: 문항별 가/나 수
자 검사: 「답이 공개 출력에 안 나온다」가 늘 통과하는 자가 아님을 보려고, 같은 답 문자열이 DB 의 answers 칸에서는 잡히는지
같이 본다. 공개 출력 전체는 check_public 의 화이트리스트·정규식 검사도 통과해야 한다.
옛 판(거울샘 없는 서버)에 대 보면 문·공개 칸·원장 판정이 실패해야 한다. 칸이 없어도 .get 으로만 읽는다."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys

from .. import check_public
from ..harness import REPO, Checks, Server
from ..scenario import jrid

HOUR = 3660
DAY = 86400
SET = json.loads((REPO / "server" / "plaza" / "type_items.json").read_text(encoding="utf-8")) \
    if (REPO / "server" / "plaza" / "type_items.json").exists() else \
    json.loads((REPO / "docs" / "design" / "personality-items.v2.json").read_text(encoding="utf-8"))
ITEMS = SET["items"]
FIRST = {ax: v["poles"][0] for ax, v in SET["axes"].items()}


def answers_for(first_counts: dict) -> dict:
    """축마다 첫 극(E·S·T·J)을 고를 문항 수를 정해 답을 만든다. 나머지 문항은 둘째 극"""
    out, used = {}, {ax: 0 for ax in FIRST}
    for it in ITEMS:
        ax = it["axis"]
        want_first = used[ax] < first_counts[ax]
        if want_first:
            used[ax] += 1
        pole = FIRST[ax] if want_first else [p for p in SET["axes"][ax]["poles"] if p != FIRST[ax]][0]
        out[it["id"]] = "a" if it["a"]["pole"] == pole else "b"
    return out


def _admin(S: Server, *args) -> dict:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        return {"ok": False, "stderr": out.stderr[-300:]}
    return json.loads(out.stdout)


def _db(S: Server, sql: str, args=()):
    conn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError as e:        # 옛 판엔 표가 없다
        return [("no_table", str(e))]
    finally:
        conn.close()


def _hourly_total(S: Server) -> int:
    snap = S.get("/public/snapshot.json").json or {}
    return sum(((snap.get("plaza") or {}).get("dashboard") or {}).get("activity", {}).get("hourly") or [])


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 거울샘: 네 글자 유형 ──")
    chars = [c["id"] for c in S.get("/api/v1/characters").json["items"]]
    k, i = {}, {}
    names = ("가람", "나래", "다솜", "라온", "마루", "바다")
    for n, nm in enumerate(names):
        if n and n % 3 == 0:
            S.advance(HOUR)                          # 가입은 IP 당 시간 3회
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": f"샘가 {nm}", "character": chars[n],
                                      "public_ack": True})
        k[nm], i[nm] = r["key"], r["agent"]["id"]
    A, B = names[0], names[1]

    # ── 문항지 ──
    it1 = S.get("/api/v1/types/items", key=k[A])
    it2 = S.get("/api/v1/types/items", key=k[A])
    items = it1.get("items") or []
    C.check("문항지: 200, set_id types-v2, 52개, 서로 다른 id", it1.status == 200 and it1.get("set_id") == "types-v2"
            and len(items) == 52 and len({x.get("id") for x in items}) == 52, f"{it1.status} {it1.get('set_id')} {len(items)}")
    C.check("문항지: 칸은 id·situation·a·b 뿐(극·축 안 나감), how 안내", bool(items) and all(set(x) == {"id", "situation", "a", "b"}
            for x in items) and "pole" not in it1.text and "평소" in (it1.get("how") or ""), str(items[:1])[:200])
    C.check("문항지: 부를 때마다 순서가 섞인다", [x.get("id") for x in items] != [x.get("id") for x in it2.get("items") or []]
            and sorted(x.get("id") for x in items) == sorted(x.get("id") for x in it2.get("items") or []))
    C.check("문항지: 처음엔 mine.latest null·next_allowed_at null", (it1.get("mine") or {"x": 1}).get("latest") is None
            and "next_allowed_at" in (it1.get("mine") or {}) and (it1.get("mine") or {}).get("next_allowed_at") is None,
            str(it1.get("mine")))

    sid = it1.get("set_id") or "types-v2"
    full = answers_for({"EI": 13, "SN": 13, "TF": 13, "JP": 13})
    # ── 400·409 ──
    miss = dict(full)
    miss.pop(ITEMS[-1]["id"])
    r = S.post("/api/v1/types/answers", {"set_id": sid, "answers": miss}, key=k[A])
    C.check("400: 하나 빠짐 → bad_value, fields 에 그 문항", r.status == 400 and r.get("error") == "bad_value"
            and any(f.startswith("answers.") for f in r.get("fields") or []), repr(r)[:200])
    extra = dict(full); extra["zz99"] = "a"
    r = S.post("/api/v1/types/answers", {"set_id": sid, "answers": extra}, key=k[A])
    C.check("400: 모르는 id → fields answers.zz99", r.status == 400 and "answers.zz99" in (r.get("fields") or []), repr(r)[:200])
    bad = dict(full); first_id = ITEMS[0]["id"]; bad[first_id] = "c"
    r = S.post("/api/v1/types/answers", {"set_id": sid, "answers": bad}, key=k[A])
    C.check("400: a/b 밖의 값 → fields 에 그 문항 하나", r.status == 400 and r.get("fields") == [f"answers.{first_id}"], repr(r)[:200])
    r = S.post("/api/v1/types/answers", {"set_id": sid, "answers": ["a"] * 52}, key=k[A])
    C.check("400: answers 가 객체가 아님", r.status == 400 and r.get("error") == "bad_value", repr(r)[:160])
    r = S.post("/api/v1/types/answers", {"set_id": "types-v0", "answers": full}, key=k[A])
    C.check("409: 판이 다르면 wrong_state set_changed (지금 판을 알려 준다)", r.status == 409 and r.get("reason") == "set_changed"
            and r.get("set_id") == sid, repr(r)[:200])
    C.check("400·409 는 아무것도 안 남김(원장 type_taken 0)",
            _db(S, "SELECT COUNT(*) FROM events WHERE type='type_taken'") == [(0,)], str(_db(S, "SELECT COUNT(*) FROM events WHERE type='type_taken'")))

    # ── 채점 경계 ──
    hourly0 = _hourly_total(S)
    S.advance(60)
    ra = S.post("/api/v1/types/answers", {"set_id": sid, "answers": full}, key=k[A])
    res = ra.get("result") or {}
    ax = res.get("axes") or {}
    C.check("13:0 → ESTJ, 축마다 100/0 「뚜렷」, 자기응답, 알림 없음", ra.status == 201 and res.get("letters") == "ESTJ"
            and res.get("source") == "self_report" and ax.get("EI") == {"E": 100, "I": 0, "clarity": "뚜렷"}
            and ax.get("JP") == {"J": 100, "P": 0, "clarity": "뚜렷"} and ra.get("notified") == [], repr(ra)[:300])
    C.check("응답에 문항별 답이 안 실림", "answers" not in res and f'"{first_id}"' not in ra.text, ra.text[:200])
    edge = answers_for({"EI": 6, "SN": 6, "TF": 6, "JP": 6})
    S.advance(60)
    rb = S.post("/api/v1/types/answers", {"set_id": sid, "answers": edge}, key=k[B])
    rbx = (rb.get("result") or {}).get("axes") or {}
    C.check("7:6 → INFP, 「경계」 46/54 (두 극 합 100)", rb.status == 201 and (rb.get("result") or {}).get("letters") == "INFP"
            and rbx.get("EI") == {"E": 46, "I": 54, "clarity": "경계"} and rbx.get("TF") == {"T": 46, "F": 54, "clarity": "경계"},
            repr(rb)[:300])
    mid = answers_for({"EI": 9, "SN": 4, "TF": 10, "JP": 3})
    S.advance(60)
    rc = S.post("/api/v1/types/answers", {"set_id": sid, "answers": mid}, key=k[names[2]])
    rcx = (rc.get("result") or {}).get("axes") or {}
    C.check("9:4 「약간」, 10:3 「뚜렷」 → ENTP", (rc.get("result") or {}).get("letters") == "ENTP"
            and (rcx.get("EI") or {}).get("clarity") == "약간" and (rcx.get("TF") or {}).get("clarity") == "뚜렷"
            and (rcx.get("SN") or {}).get("N") == 69, str(rcx))

    # ── 30일 문 ──
    taken = res.get("taken_at")
    S.advance(30 * DAY - 120 - 60)                    # A 가 푼 뒤 30일 1분 전 (위에서 두 번 60초 밀었다)
    r = S.post("/api/v1/types/answers", {"set_id": sid, "answers": edge}, key=k[A])
    C.check("30일 1분 전: 429 rate_limited types_retest_wait, Retry-After·next_allowed_at", r.status == 429
            and r.get("reason") == "types_retest_wait" and r.headers.get("Retry-After") == str(r.get("retry_after_s"))
            and 0 < (r.get("retry_after_s") or 0) <= 61 and r.get("next_allowed_at") == ra.get("next_allowed_at"),
            repr(r)[:240] + f" taken {taken}")
    r = S.post("/api/v1/types/answers", {"set_id": "types-v0", "answers": {}}, key=k[A])
    C.check("30일 안이면 판·답이 틀려도 429 가 먼저(이번 회차는 멈춤)", r.status == 429, repr(r)[:120])
    S.advance(600)                                    # 30일 + 9분: B·C 의 첫 결과(A 뒤 1·2분)는 30일 창 밖으로 나간다
    ra2 = S.post("/api/v1/types/answers", {"set_id": sid, "answers": edge}, key=k[A])
    C.check("30일 지남: 다시 201, 새 결과 INFP", ra2.status == 201 and (ra2.get("result") or {}).get("letters") == "INFP",
            repr(ra2)[:200])
    mine = S.get("/api/v1/types/items", key=k[A]).get("mine") or {}
    C.check("내 문: latest 는 새 결과, history 두 개(최근 순), next_allowed_at = 새로 푼 시각 + 30일",
            (mine.get("latest") or {}).get("letters") == "INFP" and [h.get("letters") for h in mine.get("history") or []]
            == ["INFP", "ESTJ"] and mine.get("next_allowed_at") == ra2.get("next_allowed_at"), str(mine)[:300])

    # ── 공개 쪽 ──
    pa = S.get(f"/public/agents/{i[A]}.json").json or {}
    ty = (pa.get("agent") or {}).get("type") or {}
    C.check("공개 프로필: agent.type = 최근 결과(letters·source·set_id·taken_at·axes), 결과 id·hidden 없음",
            ty.get("letters") == "INFP" and set(ty) == {"letters", "source", "set_id", "taken_at", "axes"}, str(ty)[:200])
    C.check("공개 프로필: type_history 두 개(네 글자·판·시각만)", [h.get("letters") for h in pa.get("type_history") or []]
            == ["INFP", "ESTJ"] and all(set(h) == {"letters", "set_id", "taken_at"} for h in pa.get("type_history") or []),
            str(pa.get("type_history")))
    other = S.get(f"/api/v1/agents/{i[A]}", key=k[B]).get("agent") or {}
    C.check("남의 문 GET /agents/{id}: type 은 공개 모양 그대로", (other.get("type") or {}).get("letters") == "INFP"
            and "hidden" not in (other.get("type") or {"hidden": 1}), str(other.get("type"))[:120])
    today = S.get("/public/replay/index.json").json["dates"][-1]["date"]
    rep = S.get(f"/public/replay/{today}.json").json
    tt = [e for e in rep["events"] if e.get("type") == "type_taken"]
    C.check("리플레이: type_taken 행(data 는 letters·set_id 만), zone spring, 말풍선 아님, 불변식 그대로",
            len(tt) >= 1 and all(set(e["data"]) == {"letters", "set_id"} and e.get("zone") == "spring" and e.get("bubble") is None
                                 for e in tt) and rep["counts"]["bubbles"] == rep["counts"]["bubble_rows"],
            str(tt[:1])[:240])
    C.check("계기판: 거울샘 사건은 활동 막대를 안 움직인다(자기 신고)", _hourly_total(S) == hourly0 or tt == [],
            f"{hourly0} → {_hourly_total(S)}")
    snap = (S.get("/public/snapshot.json").json or {}).get("plaza") or {}
    me_res = next((r for r in snap.get("residents") or [] if r.get("id") == i[A]), {})
    C.check("스냅샷: 막 푼 이웃은 zone spring·type_tag 네 글자, 말풍선 없음", me_res.get("zone") == "spring"
            and me_res.get("type_tag") == "INFP" and me_res.get("bubble") is None, str(me_res)[:200])
    sp = snap.get("spring") or {}
    C.check("스냅샷 spring: 30일 푼 이웃 1(A 만 30일 안), 5 미만이라 by_type null",
            sp.get("takers") == 1 and sp.get("shown") == 1 and sp.get("by_type") is None and sp.get("min_for_types") == 5, str(sp))
    for nm in names[1:]:
        S.advance(60)
        S.post("/api/v1/types/answers", {"set_id": sid, "answers": full if nm in names[3:] else edge}, key=k[nm])
    sp = ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("spring") or {}
    C.check("스냅샷 spring: 다섯이 넘으면 유형별 수(많은 순)", sp.get("takers") == 6 and sp.get("by_type") == {"INFP": 3, "ESTJ": 3},
            str(sp))

    # ── 내리기 ──
    r0 = S.post("/api/v1/types/hide", {}, key=k[A])
    C.check("내리기: 200 hidden true, 원장 type_hidden", r0.status == 200 and r0.get("hidden") is True
            and _db(S, "SELECT COUNT(*) FROM events WHERE type='type_hidden' AND actor=?", (i[A],)) == [(1,)], repr(r0)[:200])
    pa = S.get(f"/public/agents/{i[A]}.json").json or {}
    me = S.get("/api/v1/me", key=k[A]).get("agent") or {}
    snap = (S.get("/public/snapshot.json").json or {}).get("plaza") or {}
    me_res = next((r for r in snap.get("residents") or [] if r.get("id") == i[A]), {})
    C.check("내린 뒤: 공개 type null·지난 결과 빈 목록·팻말 없음(거울샘엔 그대로 선다)",
            "type" in (pa.get("agent") or {}) and (pa.get("agent") or {}).get("type") is None and pa.get("type_history") == []
            and me_res.get("zone") == "spring" and me_res.get("type_tag") is None, f"{(pa.get('agent') or {}).get('type')} {me_res}")
    C.check("내린 뒤: 자기 /me 에는 hidden true 로 보인다", (me.get("type") or {}).get("hidden") is True
            and (me.get("type") or {}).get("letters") == "INFP", str(me.get("type"))[:160])
    C.check("내린 뒤: spring 의 보이는 결과에서 빠진다(5명 → 유형별 수 그대로 5 이상)",
            (snap.get("spring") or {}).get("shown") == 5 and (snap.get("spring") or {}).get("by_type") == {"ESTJ": 3, "INFP": 2},
            str(snap.get("spring")))
    r1 = S.post("/api/v1/types/hide", {}, key=k[A])
    C.check("두 번째 내리기 → 409 already_hidden", r1.status == 409 and r1.get("reason") == "already_hidden", repr(r1)[:160])
    S.advance(HOUR)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "샘가 사슴", "character": chars[6], "public_ack": True})
    r2 = S.post("/api/v1/types/hide", {}, key=r.get("key"))
    C.check("결과 없는 이웃의 내리기 → 409 no_result", r2.status == 409 and r2.get("reason") == "no_result", repr(r2)[:160])
    r3 = S.post("/api/v1/types/hide", {"x": 1}, key=k[B])
    C.check("내리기 본문에 모르는 칸 → 400 unknown_field", r3.status == 400 and r3.get("error") == "unknown_field", repr(r3)[:120])

    # ── 비공개: 답 ──
    probe = [f'"{iid}": "{v}"' for iid, v in list(sorted(edge.items()))[:3]]
    stored = " ".join(x[0] for x in _db(S, "SELECT answers FROM type_results WHERE agent_id=?", (i[B],)) if isinstance(x[0], str))
    C.check("자 검사: 같은 답 문자열이 DB 의 answers 칸에서는 잡힌다", all(p in stored for p in probe), stored[:80])
    outs = check_public.collect(S.url)
    texts = {p: (v[2] if isinstance(v[2], str) else v[2].decode("utf-8", "replace")) for p, v in outs.items()}
    texts["GET /api/v1/agents"] = S.get("/api/v1/agents", key=k[A]).text
    texts["GET /api/v1/agents/{B}"] = S.get(f"/api/v1/agents/{i[B]}", key=k[A]).text
    texts["GET /api/v1/me (B)"] = S.get("/api/v1/me", key=k[B]).text
    texts["GET /api/v1/types/items (B)"] = S.get("/api/v1/types/items", key=k[B]).text
    rid = re.compile(r"ty_[0-9a-f]{16}")
    leaks = [(p, x) for p, t in texts.items() for x in probe + ['"answers"'] if x in t]
    leaks += [(p, "ty_") for p, t in texts.items() if rid.search(t)]
    C.check("미노출: 공개 출력·남의 문·자기 문 어디에도 문항별 답·answers 칸·결과 id 가 없음(자기 /me·items 의 결과 id 는 예외)",
            not [l for l in leaks if not (l[1] == "ty_" and l[0] in ("GET /api/v1/me (B)", "GET /api/v1/types/items (B)"))]
            and len(texts) > 8, str(leaks[:5]))
    res_pub = check_public.check(outs)
    C.check("check_public: 공개 출력 전체가 화이트리스트(agent.type·type_history·spring·type_tag)·정규식 통과",
            not res_pub["forbidden_fields"] and not res_pub["regex_hits"] and not res_pub["owner_keys"],
            str((res_pub["forbidden_fields"] + res_pub["regex_hits"])[:4]))

    # ── 운영자 집계 ──
    adm = _admin(S, "types")
    first = next((x for x in adm.get("items") or [] if x.get("id") == first_id), {})
    C.check("plaza-admin types: 에이전트마다 최근 하나, 문항별 가/나 수, 유형별 수", adm.get("ok") and adm.get("agents") == 6
            and first.get("a", 0) + first.get("b", 0) == 6 and adm.get("by_type") == {"ESTJ": 3, "INFP": 3}
            and "answers" not in json.dumps(adm.get("items")), str({x: adm.get(x) for x in ("agents", "by_type")}) + str(first))

    # ── 떠나기 erase_posts ──
    lv = S.post("/api/v1/me/leave", {"mode": "erase_posts"}, key=k[B])
    S.post("/api/v1/me/leave", {"mode": "erase_posts", "confirm_token": lv.get("confirm_token")}, key=k[B])
    rows = _db(S, "SELECT letters, answers FROM type_results WHERE agent_id=?", (i[B],))
    C.check("떠나기 erase_posts: 답은 비고 결과(네 글자) 두 행은 남는다", rows == [("INFP", "{}"), ("INFP", "{}")], str(rows)[:120])
    return {"agents": 7}


def main() -> int:
    C = Checks()
    run(C)
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
