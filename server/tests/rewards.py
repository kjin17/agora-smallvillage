"""부탁 보상 (api.md 4.1·6.1). 새 임시 서버에서 HTTP 와 plaza-admin 으로만 잰다.

  python3 -m server.tests.rewards

- 걸기: 1~REWARD_MAX 정수만, 잔액보다 많이는 409 insufficient_gold 이고 부탁·장부가 그대로다. 걸면 장부에 맡김(-N) 한 행
- 받아들임(받아가 done 으로 닫음): 산출물 쓴 이에게 넘김(+N) 한 행. 두 번 닫기·다시 정리해도 두 번 안 간다
- 거둠(withdrawn)·기한 지남(산출물 전)·떠남: 돌려줌(+N). 산출물이 온 뒤엔 거둘 수 없고(409 reward_delivered) 기한이 지나면 넘긴다
- 남용: 자기 부탁에 손 들기(own_target), 가입 72시간 안 계정의 손 들기(new_period_reward)
- 경합: 같은 에이전트의 보상 부탁 여럿 + 운영자 차감을 동시에 → 잔액이 0 밑으로 안 간다, 장부 합계가 맞는다
- DB 그물: 장부 고치기·지우기·음수 잔액 행, 같은 부탁의 두 번째 넘김을 DB 가 거절한다
- 공개: 부탁 공개 뷰의 reward 칸, 리플레이 reward_settled 의 data 는 outcome·amount·to 만, 스냅샷 market 의 reward
옛 판(칸이 없는 서버)에 대 보면 정상 경로가 실패해야 한다."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import threading

from .gold import _admin, _gold
from .harness import Checks, Server
from .scenario import jrid


def _db(S: Server, sql: str, args=()):
    c = sqlite3.connect(S.db)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.OperationalError as e:
        return [("오류", str(e))]
    finally:
        c.close()


def _bal(S, k) -> int | None:
    return _gold(S.get("/api/v1/me", key=k)).get("balance")


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _join(S, nick, ch):
    S.advance(3700)                                        # 가입 속도 제한(IP 당 시간 3)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
    return r["key"], r["agent"]["id"]


def _open(S, k, title, reward=..., to=None):
    b = {"to": to, "title": title, "body": f"{title} 본문 {jrid()[:8]}"}
    if reward is not ...:
        b["reward"] = reward
    return S.post("/api/v1/requests", b, key=k)


def _deliver(S, kc, rid):
    S.post(f"/api/v1/requests/{rid}/claim", {}, key=kc)
    return S.post(f"/api/v1/requests/{rid}/deliver", {"body": f"산출물 {jrid()[:8]}"}, key=kc)


def _run(S: Server, C: Checks) -> dict:
    print("── 부탁 보상 ──")
    kA, A = _join(S, "보상 거는 해오라기", "scribe")
    kB, B = _join(S, "일 받는 수달", "gardener")
    kD, D = _join(S, "동시에 거는 두더지", "chef")
    kL, L = _join(S, "떠날 너구리", "knight")
    for aid, n in ((A, 50), (D, 12), (L, 10)):
        _admin(S, "gold-award", aid, str(n), "--reason", "시험 지급")
    S.advance(73 * 3600)                                   # 신규 기간(72시간) 밖으로
    kN, N = _join(S, "갓 온 병아리", "penguin")              # 신규 기간 안

    # ── 걸기: 값 검사 ──
    rows0 = _db(S, "SELECT COUNT(*) FROM gold_ledger")
    rq0 = _db(S, "SELECT COUNT(*) FROM requests")
    for v in (0, 101, "5", True, 5.5, -3):
        r = _open(S, kA, f"틀린 보상 {v!r}", v)
        C.check(f"걸기 거절: reward={v!r} → 400 bad_value", r.status == 400 and r.get("error") == "bad_value"
                and r.get("fields") == ["reward"], repr(r)[:200])
    r = _open(S, kA, "너무 큰 보상", 60)
    C.check("걸기 거절: 잔액 50 에 60 → 409 wrong_state insufficient_gold, balance 50",
            r.status == 409 and r.get("reason") == "insufficient_gold" and r.get("balance") == 50, repr(r)[:200])
    C.check("걸기 거절은 부탁·장부를 안 만든다", _db(S, "SELECT COUNT(*) FROM gold_ledger") == rows0
            and _db(S, "SELECT COUNT(*) FROM requests") == rq0, f"{rows0}/{rq0}")
    r = _open(S, kA, "보상 없는 옛 부탁")
    C.check("보상 칸 없이 연 부탁은 그대로 (reward null)", r.status == 201 and r["request"].get("reward") is None
            and r["request"].get("reward_state") is None, repr(r)[:200])

    # ── 맡김 → 받아들임 → 넘김 ──
    r = _open(S, kA, "지도 정리 부탁", 20)
    rq1 = r.get("request") or {}
    C.check("걸기: 201, reward 20·held·기한(14일)", r.status == 201 and rq1.get("reward") == 20
            and rq1.get("reward_state") == "held" and bool(rq1.get("reward_expires_at")), repr(r)[:300])
    rid1 = rq1.get("id")
    C.check("걸기: 잔액 50 → 30, 장부에 맡김 -20 한 행", _bal(S, kA) == 30 and _db(
        S, "SELECT delta, kind, request_id FROM gold_ledger WHERE request_id=?", (rid1,)) == [(-20, "escrow", rid1)],
        str(_db(S, "SELECT delta, kind, request_id FROM gold_ledger WHERE request_id=?", (rid1,))))
    r = S.post(f"/api/v1/requests/{rid1}/claim", {}, key=kA)
    C.check("남용: 자기 부탁에 손 들기 → 403 own_target", r.status == 403 and r.get("reason") == "own_target", repr(r)[:200])
    r = S.post(f"/api/v1/requests/{rid1}/claim", {}, key=kN)
    C.check("남용: 가입 72시간 안 계정의 손 들기 → 403 new_period_reward", r.status == 403
            and r.get("reason") == "new_period_reward" and bool(r.get("new_until")), repr(r)[:200])
    r = _deliver(S, kB, rid1)
    C.check("넘긴 이웃: 손 들고 산출물", r.status == 201, repr(r)[:200])
    r = S.post(f"/api/v1/requests/{rid1}/close", {"reason": "withdrawn"}, key=kA)
    C.check("산출물이 온 보상 부탁은 거둘 수 없다 → 409 reward_delivered", r.status == 409
            and r.get("reason") == "reward_delivered", repr(r)[:200])
    S.get(f"/api/v1/requests/{rid1}/artifact", key=kA)
    r = S.post(f"/api/v1/requests/{rid1}/close", {"reason": "done"}, key=kA)
    C.check("받아들임(done): 넘김 to=산출물 쓴 이·20", r.status == 200 and r.get("reward_settled") == {
        "outcome": "paid", "amount": 20, "to": B} and (r.get("request") or {}).get("reward_state") == "paid", repr(r)[:300])
    C.check("받아들임: B 잔액 20, A 는 30 그대로", _bal(S, kB) == 20 and _bal(S, kA) == 30, f"{_bal(S, kB)} {_bal(S, kA)}")
    r = S.post(f"/api/v1/requests/{rid1}/close", {"reason": "done"}, key=kA)
    S.advance(15 * 86400)                                  # 기한이 지나도 다시 정리하지 않는다
    S.get("/api/v1/me", key=kA)
    S.advance(-15 * 86400)
    C.check("이중 지급 없음: 두 번째 닫기 409, 기한 뒤에도 넘김 한 행", r.status == 409 and _db(
        S, "SELECT COUNT(*) FROM gold_ledger WHERE request_id=? AND kind='payout'", (rid1,)) == [(1,)] and _bal(S, kB) == 20,
        str(_db(S, "SELECT delta, kind FROM gold_ledger WHERE request_id=?", (rid1,))))

    # ── 거둠: 돌려줌 ──
    r = _open(S, kA, "지목 부탁", 10, to=B)
    rid2 = (r.get("request") or {}).get("id")
    S.post(f"/api/v1/requests/{rid2}/claim", {}, key=kB)
    r = S.post(f"/api/v1/requests/{rid2}/close", {"reason": "withdrawn"}, key=kA)
    C.check("거둠(손 든 뒤, 산출물 전): 돌려줌 10, A 잔액 30 그대로", r.status == 200 and r.get("reward_settled") == {
        "outcome": "refunded", "amount": 10, "to": A} and _bal(S, kA) == 30, repr(r)[:300])

    # ── 기한 지남 ──
    r3 = (_open(S, kA, "기한 지날 부탁(산출물 전)", 7).get("request") or {}).get("id")
    S.post(f"/api/v1/requests/{r3}/claim", {}, key=kB)
    r4 = (_open(S, kA, "기한 지날 부탁(산출물 옴)", 5).get("request") or {}).get("id")
    _deliver(S, kB, r4)
    C.check("기한 전: A 잔액 30-7-5 = 18", _bal(S, kA) == 18, str(_bal(S, kA)))
    S.advance(15 * 86400)
    pub3 = (S.get(f"/public/requests/{r3}.json").json or {}).get("request") or {}
    pub4 = (S.get(f"/public/requests/{r4}.json").json or {}).get("request") or {}
    C.check("기한 지남(산출물 전): 아무 요청이 정리한다 — 닫힘 withdrawn·refunded", pub3.get("state") == "closed"
            and pub3.get("close_reason") == "withdrawn" and pub3.get("reward_state") == "refunded", str(pub3))
    C.check("기한 지남(산출물 옴): 닫힘 done·paid", pub4.get("state") == "closed" and pub4.get("close_reason") == "done"
            and pub4.get("reward_state") == "paid", str(pub4))
    C.check("기한 지남: A 25(돌려받음 7), B 25(넘김 5)", _bal(S, kA) == 25 and _bal(S, kB) == 25, f"{_bal(S, kA)} {_bal(S, kB)}")
    ent = (_gold(S.get("/api/v1/me", key=kB)).get("entries") or [{}])[0]
    C.check("내역 행: kind payout·request_id·사유에 (기한 지남)", ent.get("kind") == "payout" and ent.get("request_id") == r4
            and "기한 지남" in (ent.get("reason") or ""), str(ent))

    # ── 떠남: 돌려줌 ──
    r5 = (_open(S, kL, "떠나기 전 부탁", 10).get("request") or {}).get("id")
    t = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=kL)
    S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": t.get("confirm_token")}, key=kL)
    C.check("떠남: 연 보상 부탁을 닫고 돌려준다(장부 행은 남는다)", _db(
        S, "SELECT reward_state FROM requests WHERE id=?", (r5,)) == [("refunded",)] and _db(
        S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger WHERE agent_id=?", (L,)) == [(10,)],
        str(_db(S, "SELECT delta, kind FROM gold_ledger WHERE agent_id=?", (L,))))

    # ── 경합: D 잔액 12 에 5짜리 다섯을 동시에 + 운영자 -4 ──
    res, adm = [], {}
    def go(i):
        res.append(_open(S, kD, f"동시 부탁 {i}", 5))
    def admin():
        adm["rc"], adm["out"] = _admin(S, "gold-award", D, "-4", "--reason", "경합 차감")
    ths = [threading.Thread(target=go, args=(i,)) for i in range(5)] + [threading.Thread(target=admin)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    ok = sum(1 for r in res if r.status == 201)
    poor = sum(1 for r in res if r.status == 409 and r.get("reason") == "insufficient_gold")
    bal = _bal(S, kD)
    want = 12 - 5 * ok - (4 if adm.get("rc") == 0 else 0)
    C.check("경합: 성공 + 잔액 부족 = 5, 잔액 ≥ 0, 잔액 = 12 - 5×성공 - 차감", ok + poor == 5 and bal is not None
            and bal >= 0 and bal == want and ok in (1, 2), f"성공 {ok} 부족 {poor} 차감rc {adm.get('rc')} 잔액 {bal}")

    # ── DB 그물 ──
    def raw(sql, args=()):
        c = sqlite3.connect(S.db)
        try:
            c.execute(sql, args)
            c.commit()
            return "ok"
        except sqlite3.DatabaseError as e:
            return str(e)
        finally:
            c.close()
    C.check("DB: 장부 행 고치기 거절", "append-only" in raw("UPDATE gold_ledger SET delta=999"), "")
    C.check("DB: 장부 행 지우기 거절", "append-only" in raw("DELETE FROM gold_ledger"), "")
    C.check("DB: 잔액을 0 밑으로 내리는 행 거절", "below zero" in raw(
        "INSERT INTO gold_ledger (agent_id, delta, reason, at) VALUES (?, -1000, 'x', 'x')", (A,)), "")
    C.check("DB: 같은 부탁의 두 번째 넘김(또는 넘김 뒤 돌려줌) 거절", "UNIQUE" in raw(
        "INSERT INTO gold_ledger (agent_id, delta, reason, at, kind, request_id) VALUES (?, 20, 'x', 'x', 'refund', ?)",
        (A, rid1)), "")

    # ── 보존: 운영자 지급 합 = 모든 장부 합 + 아직 맡긴 보상 ──
    awards = _db(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger WHERE kind IS NULL")[0][0]
    total = _db(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger")[0][0]
    held = _db(S, "SELECT COALESCE(SUM(reward),0) FROM requests WHERE reward_state='held'")[0][0]
    neg = _db(S, "SELECT agent_id FROM gold_ledger GROUP BY agent_id HAVING SUM(delta)<0")
    ints = all(isinstance(x, int) for x in (awards, total, held))      # 옛 판: 칸이 없어 오류 행
    C.check("보존: 골드는 운영자 지급 밖에서 생기지 않는다 (지급 = 잔액 합 + 맡김)", ints and awards == total + held and not neg,
            f"지급 {awards} 잔액합 {total} 맡김 {held} 음수 {neg}")

    # ── 공개 ──
    idx = S.get("/public/replay/index.json").json or {}
    evs = []
    for d in idx.get("dates", []):
        evs += [e for e in (S.get(f"/public/replay/{d['date']}.json").json or {}).get("events", [])
                if e.get("type") == "reward_settled"]
    C.check("공개: 리플레이 reward_settled 의 data 는 outcome·amount·to 만",
            len(evs) >= 5 and all(set(e.get("data", {})) == {"outcome", "amount", "to"} for e in evs), json.dumps(evs[:2], ensure_ascii=False)[:300])
    snap = S.get("/public/snapshot.json").json or {}
    mk = [m for m in (snap.get("plaza") or {}).get("market", []) if m.get("reward")]
    C.check("공개: 스냅샷 market 에 reward·reward_state", bool(mk) and all(m.get("reward_state") == "held" for m in mk), str(mk)[:300])
    dg = S.get("/api/v1/me/digest", key=kB).json or {}
    sq = [x for x in (dg.get("square_new") or {}).get("items", []) if x.get("type") == "request"]
    C.check("digest square_new 의 부탁에 reward 칸", bool(sq) and all("reward" in x for x in sq), str(sq)[:300])
    return {"balances": {"A": _bal(S, kA), "B": _bal(S, kB), "D": bal}}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
