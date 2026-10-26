"""이웃끼리 골드 건네기 (api.md 6.2, 2026-10-26, 인스트럭션 v17). 새 임시 서버에서 HTTP 와 plaza-admin 으로만 잰다.

  python3 -m server.tests.gold_give.check

기대값은 서버 응답을 믿지 않고 DB(gold_ledger·gold_gives·events)에서 따로 센다.
- 칸: amount 1~GIVE_MAX(10) 정수만, give_request_id 필수(16~64자), 자기 자신·떠난 이웃·없는 이웃·남의 글 quote_of 는 400,
  이유 81자는 too_long. 거절은 장부·건넴·원장을 하나도 안 만든다
- 잔액: 잔액 0 계정은 409 insufficient_gold(balance 0), 잔액과 같은 양은 되고(0 까지) 그 뒤 1 은 409
- 한 건 = 장부 두 행(give_out -N·give_in +N, 같은 give_id)과 원장 gold_given 하나, 받은 이에게 notified why gold
- 재시도: 같은 id·같은 본문은 200 replayed(행 안 늘고 하루 상한에도 안 셈), 같은 id·다른 본문은 409 give_conflict
- 하루 상한(굴러가는 24시간): 횟수 3(gold_gives_per_day), 양 20(gold_given_per_day), 429 + Retry-After, 24시간 뒤 다시 된다
- 거르기: 이유에 비밀 모양 → 422 held(골드 그대로), 신규 기간 링크 → link_not_yet
- 경합: 잔액 5 에 3골드 건네기 셋을 동시에 → 하나만 되고 잔액이 0 밑으로 안 간다
- 불변식: 장부 합 + 노점 맡김 = 운영 지급 합(골드가 새로 생기지 않는다), 음수 잔액 없음, 건넴마다 두 행 합 0
- DB 그물: 같은 건넴의 두 번째 give_in 행을 DB 가 거절한다
- 공개: /public/agents 의 내역(give_out 엔 to, give_in 엔 from, 이유), 리플레이 gold_given 의 data 는 to·amount·quote_of 만,
  스냅샷 gold_moves 의 give 줄(보낸 이 → 받은 이)·given 합 = DB, check_public 통과. 자 검사: 모르는 칸을 넣은 사본은 잡힌다
- digest: 받은 이 items 에 type gold(「N골드 · 이유」), counts.gold
- 떠나기 erase_posts: 이유 글은 지워지고(null) 장부 행은 남는다
- 인스트럭션: /join 이 v17, 부록 D 에 POST /api/v1/gold/give, 한 화면 상한 안
옛 판(73bc9b0)에 대면 문이 없어 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import json
import secrets
import sqlite3
import sys
import threading

from .. import check_public
from ..gold import _admin, _gold
from ..harness import Checks, Server
from ..scenario import jrid


def _db(S: Server, sql: str, args=()):
    c = sqlite3.connect(S.db)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error as e:                       # 옛 판: 표·칸이 없다. 그물(트리거·색인)의 거절도 여기로
        return [("오류", str(e))]
    finally:
        c.close()


def _one(S, sql, args=()):
    r = _db(S, sql, args)
    return r[0][0] if r and r[0] and r[0][0] != "오류" else None


def gid() -> str:
    return secrets.token_urlsafe(18)


def _join(S, nick, ch):
    S.advance(3700)                                        # 가입 속도 제한(IP 당 시간 3)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
    return r["key"], r["agent"]["id"]


def _bal(S, k):
    return _gold(S.get("/api/v1/me", key=k)).get("balance")


def _counts(S):
    return (_one(S, "SELECT COUNT(*) FROM gold_ledger"), _one(S, "SELECT COUNT(*) FROM gold_gives"),
            _one(S, "SELECT COUNT(*) FROM events WHERE type='gold_given'"))


def run(C: Checks, screen: bool = False) -> dict:
    """run_stage2 는 HTTP 판정만(screen=False). 단독 실행은 관전 화면 골드 장부 팝업까지(playwright)"""
    S = Server().start()
    try:
        out = _run(S, C)
        if screen:
            screen_checks(C, S)
        return out
    finally:
        S.stop()


GOLD_POP = """() => { const b = document.getElementById('pzSpotBody'), st = b.querySelector('.pz-spotstat'),
  r = b.querySelector('[data-list=gold-replay]'), g = b.querySelector('[data-list=gold]');
  return {stat: st ? {...st.dataset, text: st.textContent} : null, replay: r ? r.innerText : null,
          moves: g ? [...g.querySelectorAll(':scope > .pz-si')].map((l) => l.dataset.kind) : null, text: b.innerText}; }"""


def screen_checks(C: Checks, S: Server):
    """골드 장부 팝업: 건넴 줄(지금 7일), 원장 행은 리플레이 시각까지만(snapshot-plaza.md 4절)"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        C.check("화면: playwright 없음 — 건너뛰지 않고 실패로 적는다", False, "pip install playwright")
        return
    at = _one(S, "SELECT at FROM gold_gives WHERE reason='다음 날 답례'")
    import datetime as dt
    t = dt.datetime.fromisoformat(at)
    errs = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))

        def pop():
            pg.evaluate("Plaza.closeSpot()")
            pg.evaluate("Plaza.openSpot('gold')")
            pg.wait_for_function("() => Plaza.spot().ready", timeout=20000)
            return pg.evaluate(GOLD_POP)
        pg.goto(S.url + "/?mode=now&motion=0")
        pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
        now = pop()
        C.check("화면(지금): 골드 장부 줄에 건넴(kind give), 첫 줄에 「이웃끼리 건넨 골드」, 끝줄 「새 골드는 행사 지급으로만」",
                "give" in (now["moves"] or []) and "이웃끼리 건넨 골드" in ((now["stat"] or {}).get("text") or "")
                and "새 골드는 행사 지급으로만 생겨요" in now["text"], str(now["moves"]) + " " + str((now["stat"] or {}).get("text")))
        pg.goto(S.url + f"/?view=replay&motion=0&autopause=0&date={at[:10]}")
        pg.wait_for_function("() => window.Plaza && Plaza.stats().mode === 'replay' && Plaza.stats().date", timeout=30000)
        if pg.evaluate("Plaza.stats().playing"):
            pg.click("[data-rp=play]")
        res = {}
        for name, when in (("앞", t - dt.timedelta(seconds=2)), ("뒤", t + dt.timedelta(seconds=2))):
            pg.evaluate("(iso) => Plaza.seek(iso)", when.isoformat(timespec="seconds"))
            pg.wait_for_timeout(300)
            res[name] = pop()["replay"] or ""
        C.check("화면(리플레이): 원장 행은 리플레이 시각까지만 — 건넴 시각 2초 앞엔 「골드 2 건넴」 없고 2초 뒤엔 있다",
                "골드 2 건넴" not in res["앞"] and "골드 2 건넴" in res["뒤"], f"앞 {res['앞'][:120]!r} / 뒤 {res['뒤'][:120]!r}")
        br.close()
    C.check("화면: 페이지 오류 0", not errs, str(errs[:2]))


def _run(S: Server, C: Checks) -> dict:
    print("── 골드 건네기 ──")
    kA, A = _join(S, "고마움 건네는 해달", "scribe")
    kB, B = _join(S, "좋은 질문 하는 오소리", "gardener")
    kD, D = _join(S, "동시에 건네는 두더지", "chef")
    kL, L = _join(S, "떠날 너구리", "knight")
    kX, X = _join(S, "먼저 떠난 수리부엉이", "penguin")
    kE, E = _join(S, "있는 만큼 건네는 고슴도치", "cat")
    for aid, n in ((A, 50), (D, 5), (L, 4), (E, 4)):
        _admin(S, "gold-award", aid, str(n), "--reason", "시험 행사 지급")
    q = S.post("/api/v1/remarks", {"body": "광장 골드는 어디에 쓰면 좋을까요? 써 본 이웃 이야기가 궁금해요"}, key=kB)
    qB = (q.json or {}).get("post", {}).get("id")
    qA = ((S.post("/api/v1/remarks", {"body": "해달이 남기는 첫 한마디, 골드 장부를 살펴보는 중"}, key=kA).json or {})
          .get("post", {}).get("id"))
    r = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=kX)
    S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": (r.json or {}).get("confirm_token")}, key=kX)
    S.advance(73 * 3600)                                   # 신규 기간(72시간) 밖으로
    kN, N = _join(S, "갓 온 병아리", "puppy")                 # 신규 기간 안
    _admin(S, "gold-award", N, "3", "--reason", "시험 행사 지급")

    def give(k, to, amount, rid=None, **kw):
        b = {"to": to, "amount": amount, "give_request_id": rid or gid(), **kw}
        return S.post("/api/v1/gold/give", b, key=k)

    # ── 칸 검사: 거절은 아무것도 안 만든다 ──
    c0 = _counts(S)
    for v in (0, 11, "5", True, 5.5, -3, None):
        r = give(kA, B, v)
        C.check(f"칸: amount={v!r} → 400 bad_value", r.status == 400 and r.get("error") == "bad_value"
                and r.get("fields") == ["amount"], repr(r)[:200])
    r = S.post("/api/v1/gold/give", {"to": B, "amount": 1}, key=kA)
    C.check("칸: give_request_id 빠짐 → 400 missing_field", r.status == 400 and r.get("error") == "missing_field"
            and r.get("fields") == ["give_request_id"], repr(r)[:200])
    r = give(kA, B, 1, rid="짧은id")
    C.check("칸: give_request_id 모양 틀림 → 400 bad_value", r.status == 400 and r.get("fields") == ["give_request_id"], repr(r)[:200])
    r = give(kA, B, 1, memo="x")
    C.check("칸: 모르는 칸 → 400 unknown_field", r.status == 400 and r.get("error") == "unknown_field", repr(r)[:200])
    for to, why in ((A, "자기 자신"), (X, "떠난 이웃"), ("ag_0000000000000000", "없는 이웃"), ("po_1", "에이전트 id 아님")):
        r = give(kA, to, 1)
        C.check(f"받는 이: {why} → 400 bad_value fields to", r.status == 400 and r.get("error") == "bad_value"
                and r.get("fields") == ["to"], repr(r)[:200])
    r = give(kA, B, 1, reason="가" * 81)
    C.check("칸: 이유 81자 → 400 too_long", r.status == 400 and r.get("error") == "too_long", repr(r)[:200])
    for qo, why in (("po_nothere", "없는 글"), (qA, "받는 이가 쓰지 않은 글")):
        r = give(kA, B, 1, quote_of=qo)
        C.check(f"quote_of: {why} → 400 bad_value", r.status == 400 and r.get("fields") == ["quote_of"], repr(r)[:200])
    r = give(kB, A, 1)
    C.check("잔액 0 계정: 409 wrong_state insufficient_gold, balance 0", r.status == 409 and r.get("error") == "wrong_state"
            and r.get("reason") == "insufficient_gold" and r.get("balance") == 0, repr(r)[:200])
    C.check("거절은 장부·건넴·원장을 안 만든다", _counts(S) == c0 and None not in c0, f"{c0} → {_counts(S)}")

    # ── 한 건 ──
    rid1 = gid()
    r = give(kA, B, 7, rid=rid1, reason="좋은 질문 고마워요", quote_of=qB)
    g1 = (r.json or {}).get("give") or {}
    C.check("건네기: 201, give{id gv_, from A, to B, amount 7, 이유, quote_of}, balance 43", r.status == 201
            and str(g1.get("id", "")).startswith("gv_") and (g1.get("from") or {}).get("id") == A
            and (g1.get("to") or {}).get("id") == B and g1.get("amount") == 7 and g1.get("reason") == "좋은 질문 고마워요"
            and g1.get("quote_of") == qB and r.get("balance") == 43 and r.get("replayed") is False, repr(r)[:400])
    C.check("알림: 받은 이에게 why gold", r.get("notified") == [{"id": B, "nickname": "좋은 질문 하는 오소리", "why": "gold"}],
            str(r.get("notified")))
    rows = _db(S, "SELECT agent_id, delta, kind, counterparty FROM gold_ledger WHERE give_id=? ORDER BY id", (g1.get("id"),))
    C.check("장부: 같은 give_id 두 행 (A give_out -7 → B, B give_in +7 ← A)",
            rows == [(A, -7, "give_out", B), (B, 7, "give_in", A)], str(rows))
    C.check("원장: gold_given 한 행 (actor A, subject 건넴 id)",
            _db(S, "SELECT actor, subject FROM events WHERE type='gold_given'") == [(A, g1.get("id"))],
            str(_db(S, "SELECT actor, subject, data FROM events WHERE type='gold_given'")))
    C.check("잔액: A 43, B 7 (GET /api/v1/me)", _bal(S, kA) == 43 and _bal(S, kB) == 7, f"{_bal(S, kA)} {_bal(S, kB)}")

    # ── 재시도 ──
    c1 = _counts(S)
    r = give(kA, B, 7, rid=rid1, reason="좋은 질문 고마워요", quote_of=qB)
    C.check("재시도(같은 id·같은 본문): 200 replayed, 같은 건넴 id, 행 안 늚", r.status == 200 and r.get("replayed") is True
            and ((r.json or {}).get("give") or {}).get("id") == g1.get("id") and _counts(S) == c1, repr(r)[:300])
    r = give(kA, B, 8, rid=rid1)
    C.check("재시도(같은 id·다른 본문): 409 wrong_state give_conflict", r.status == 409 and r.get("reason") == "give_conflict"
            and r.get("give_id") == g1.get("id") and _counts(S) == c1, repr(r)[:300])

    # ── 하루 상한 ──
    r2 = give(kA, B, 10)                                   # 2번째, 합 17 (경계: 한 번 상한 10 은 된다)
    r3 = give(kA, B, 4)                                    # 합 21 > 20
    C.check("하루 양 상한: 7+10 뒤 4 → 429 gold_given_per_day limit 20, Retry-After", r2.status == 201 and r3.status == 429
            and r3.get("reason") == "gold_given_per_day" and r3.get("limit") == 20 and r3.headers.get("Retry-After")
            and (r3.get("used") or {}).get("amount") == 17, f"{r2.status} {repr(r3)[:300]}")
    r3 = give(kA, B, 3)                                    # 합 20 (경계: 상한과 같으면 된다)
    r4 = give(kA, B, 1)                                    # 4번째
    C.check("하루 횟수 상한: 세 번(합 20) 뒤 네 번째 → 429 gold_gives_per_day limit 3", r3.status == 201 and r4.status == 429
            and r4.get("reason") == "gold_gives_per_day" and r4.get("limit") == 3 and r4.get("window_s") == 86400,
            f"{r3.status} {repr(r4)[:300]}")
    r = give(kA, B, 7, rid=rid1, reason="좋은 질문 고마워요", quote_of=qB)
    C.check("재시도는 하루 상한에 안 막힌다(같은 결과)", r.status == 200 and r.get("replayed") is True, repr(r)[:200])
    S.advance(86401)
    r = give(kA, B, 2, reason="다음 날 답례")
    C.check("24시간 지나면 다시 된다", r.status == 201, repr(r)[:200])

    # ── 잔액 경계: 잔액과 같은 양까지 ──
    r = give(kE, B, 4, reason="있는 만큼")
    r5 = give(kE, B, 1)
    C.check("잔액 경계: 잔액 4 에 4 → 201 balance 0, 그 뒤 1 → 409 insufficient_gold balance 0",
            r.status == 201 and r.get("balance") == 0 and _bal(S, kE) == 0 and r5.status == 409
            and r5.get("reason") == "insufficient_gold" and r5.get("balance") == 0, f"{repr(r)[:200]} / {repr(r5)[:200]}")

    # ── 거르기 ──
    c2 = _counts(S)
    r = give(kA, B, 1, reason="키 sk-ant-api03-" + "x" * 40)
    C.check("이유에 비밀 모양 → 422 held, 골드 그대로", r.status == 422 and r.get("error") == "held" and _counts(S) == c2,
            repr(r)[:200])
    r = give(kN, B, 1, reason="고마워요 https://example.com")
    C.check("신규 기간 이유에 링크 → 400 link_not_yet", r.status == 400 and r.get("error") == "link_not_yet"
            and _counts(S) == c2, repr(r)[:200])
    r = give(kN, B, 1, reason="첫날이지만 고마워서")
    C.check("신규 기간 계정도 받은 골드는 건넨다(행사 지급 3 → 2)", r.status == 201 and r.get("balance") == 2, repr(r)[:200])

    # ── 경합 ──
    outs = []

    def fire():
        outs.append(give(kD, B, 3).status)
    th = [threading.Thread(target=fire) for _ in range(3)]
    [t.start() for t in th]
    [t.join() for t in th]
    C.check("경합: 잔액 5 에 3골드 셋 동시 → 201 하나·409 둘, D 잔액 2", sorted(outs) == [201, 409, 409] and _bal(S, kD) == 2,
            f"{sorted(outs)} 잔액 {_bal(S, kD)}")

    # ── DB 그물 ──
    gx = _one(S, "SELECT id FROM gold_gives ORDER BY at LIMIT 1")
    err = _db(S, "INSERT INTO gold_ledger (agent_id, delta, reason, at, kind, give_id, counterparty) VALUES (?,?,?,?,?,?,?)",
              (B, 7, "받음", "2026-10-26T00:00:00+09:00", "give_in", gx, A))
    C.check("DB 그물: 같은 건넴의 두 번째 give_in 행 거절", bool(gx) and bool(err) and err[0][0] == "오류" and "UNIQUE" in str(err),
            str(err)[:200])
    err = _db(
        S, "INSERT INTO gold_ledger (agent_id, delta, reason, at, kind, give_id, counterparty) VALUES (?,?,?,?,?,?,?)",
        (D, -100, "건넴", "2026-10-26T00:00:00+09:00", "give_out", "gv_fake", B))
    C.check("DB 그물: 잔액이 0 밑이 되는 give_out 행 거절(트리거 문구로)", bool(err) and err[0][0] == "오류"
            and "below zero" in str(err), str(err)[:200])

    # ── 떠나기 erase_posts: 이유 글만 지워진다 ──
    r = give(kL, B, 4, reason="떠나기 전에 남기는 고마움")
    gL = ((r.json or {}).get("give") or {}).get("id")
    r = S.post("/api/v1/me/leave", {"mode": "erase_posts"}, key=kL)
    S.post("/api/v1/me/leave", {"mode": "erase_posts", "confirm_token": (r.json or {}).get("confirm_token")}, key=kL)
    entB = (S.get(f"/public/agents/{B}.json").json or {}).get("gold", {}).get("entries", [])
    eL = next((e for e in entB if e.get("give_id") == gL), {})
    C.check("떠나기 erase_posts: 받은 이 내역의 그 줄은 남고(양 4, from 떠난 이) 이유는 null", bool(gL) and eL.get("delta") == 4
            and (eL.get("from") or {}).get("id") == L and eL.get("reason") is None
            and _one(S, "SELECT COUNT(*) FROM gold_ledger WHERE give_id=?", (gL,)) == 2, str(eL))

    # ── 불변식 ──
    awards = _one(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger WHERE kind IS NULL")
    total = _one(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger")
    held = _one(S, "SELECT COALESCE(SUM(reward),0) FROM requests WHERE reward_state='held'")
    neg = _db(S, "SELECT agent_id FROM gold_ledger GROUP BY agent_id HAVING SUM(delta)<0")
    pair = _db(S, "SELECT give_id FROM gold_ledger WHERE give_id IS NOT NULL GROUP BY give_id HAVING SUM(delta)<>0 OR COUNT(*)<>2")
    n_give = _one(S, "SELECT COUNT(*) FROM gold_gives")
    C.check("불변식: 장부 합 + 맡김 = 운영 지급 합(새 골드 없음), 음수 잔액 없음, 건넴마다 두 행 합 0",
            None not in (awards, total, held) and awards == total + held and not neg and not pair and (n_give or 0) >= 8,
            f"지급 {awards} 장부합 {total} 맡김 {held} 음수 {neg} 짝 어긋남 {pair} 건넴 {n_give}")

    # ── 공개 ──
    entA = (S.get(f"/public/agents/{A}.json").json or {}).get("gold", {}).get("entries", [])
    out = next((e for e in entA if e.get("give_id") == g1.get("id")), {})
    inn = next((e for e in entB if e.get("give_id") == g1.get("id")), {})
    C.check("공개 내역: A 의 give_out(-7, to B, 이유), B 의 give_in(+7, from A, 이유)", out.get("kind") == "give_out"
            and out.get("delta") == -7 and (out.get("to") or {}).get("id") == B and out.get("from") is None
            and inn.get("kind") == "give_in" and inn.get("delta") == 7 and (inn.get("from") or {}).get("id") == A
            and inn.get("reason") == "좋은 질문 고마워요", f"{out} / {inn}")
    me = S.get("/api/v1/me", key=kB).json or {}
    C.check("API 내역 = 공개 내역 (GET /api/v1/me 의 gold)", (me.get("gold") or {}).get("entries") == entB, "")
    evs = []
    for d in (S.get("/public/replay/index.json").json or {}).get("dates", []):
        evs += [e for e in (S.get(f"/public/replay/{d['date']}.json").json or {}).get("events", []) if e.get("type") == "gold_given"]
    C.check("리플레이: gold_given 의 data 는 to·amount·quote_of 만, 행 수 = gold_gives 행 수",
            len(evs) == n_give and all(set(e.get("data", {})) == {"to", "amount", "quote_of"} for e in evs),
            f"{len(evs)}/{n_give} " + json.dumps(evs[:1], ensure_ascii=False)[:200])
    snap = S.get("/public/snapshot.json").json or {}
    gm = (snap.get("plaza") or {}).get("gold_moves") or {}
    gives = [x for x in gm.get("rows", []) if x.get("kind") == "give"]
    want_given = _one(S, "SELECT COALESCE(SUM(-delta),0) FROM gold_ledger WHERE kind='give_out'")
    C.check("스냅샷 gold_moves: give 줄 = 보낸 이 → 받은 이, given = DB 건넨 합(7일 안 전부)", bool(gives)
            and all(x.get("from") and x.get("to") and x.get("delta", 0) > 0 for x in gives) and gm.get("given") == want_given,
            f"given {gm.get('given')} DB {want_given} 줄 {len(gives)}")
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    W = check_public.Walker(wl, et)
    W.walk(check_public.SNAPSHOT, snap)
    W.walk(check_public.shape_for(f"/public/agents/{B}.json"), S.get(f"/public/agents/{B}.json").json or {})
    W.walk(["replay_event"], evs)
    C.check("check_public: 스냅샷·이웃 장부·리플레이 gold_given 통과 (규격 표에 give_id·gold_given)",
            not W.bad and "give_id" in wl.get("gold", set()) and "gold_given" in et, str(W.bad[:4]))
    probe = json.loads(json.dumps(snap))
    for x in probe["plaza"].get("gold_moves", {}).get("rows", []):
        x["give_request_id"] = "새면안됨"
    W2 = check_public.Walker(wl, et)
    W2.walk(check_public.SNAPSHOT, probe)
    C.check("자 검사: 줄에 재시도 id 를 넣은 사본은 check_public 이 잡는다", any("give_request_id" in b for b in W2.bad), str(W2.bad[:2]))
    raw = json.dumps([snap, entA, entB, evs], ensure_ascii=False)
    C.check("공개 출력 어디에도 give_request_id·sig 칸이 없다", "give_request_id" not in raw and rid1 not in raw and '"sig"' not in raw, "")

    # ── digest ──
    dg = S.get("/api/v1/me/digest", key=kB).json or {}
    its = [x for x in dg.get("items", []) if x.get("type") == "gold"]
    C.check("digest: 받은 이 items 에 type gold(「7골드 · 이유」, from A), counts.gold = 그 수", bool(its)
            and any(x.get("excerpt") == "7골드 · 좋은 질문 고마워요" and (x.get("from") or {}).get("id") == A for x in its)
            and (dg.get("counts") or {}).get("gold") == len(its), json.dumps(its[:2], ensure_ascii=False)[:300])

    # ── 인스트럭션 ──
    jn = S.get("/join?format=json", key=kA).json or {}
    me = S.get("/api/v1/me", key=kA).json or {}
    C.check("/join 이 v17, 부록 D 에 POST /api/v1/gold/give", jn.get("version") == 17 and "/api/v1/gold/give" in (jn.get("instruction") or ""),
            f"version {jn.get('version')}")
    C.check("/api/v1/me: 판 17 을 읽은 뒤 instruction_notice 없음, seen_version 17",
            "instruction_notice" not in me and (me.get("agent") or {}).get("seen_version") == 17, str(me.get("instruction_notice"))[:200])
    return {"gives": n_give, "given": want_given, "supply": total}


if __name__ == "__main__":
    C = Checks()
    run(C, screen="--no-screen" not in sys.argv)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
