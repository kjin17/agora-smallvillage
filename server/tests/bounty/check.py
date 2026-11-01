"""물음 우물 현상금 (api.md 6.3, 2026-11-01, 인스트럭션 v18). 새 임시 서버에서 HTTP 와 plaza-admin 으로만 잰다.

  python3 -m server.tests.bounty.check

기대값은 서버 응답을 믿지 않고 DB(gold_ledger·bounties·events)에서 따로 센다.
- 흐름: 걸기(맡김 -N) → 답 → 고르기(답한 이 +(N−B), B 는 장부 행 없이 사라짐), 알림은 받은 이 하나(why bounty), 걸기엔 알림 없음.
  N=2~10 전 칸의 B·P 가 설계안 3절 표(30% 올림)와 같다
- 불변식: 매 단계 「장부 합 + 맡김(부탁·현상금) + 사라진 골드 = 운영 지급 합」, 음수 잔액 0
- 기한(크론 없이 다음 요청에서): 답 0 → 돌려받음, 답 있는데 안 고름 → 전부 사라짐, 고른 뒤 → 그대로. 아무 문 하나로 정리된다
- 동시: 같은 현상금에 고르기 둘·거두기 하나 → 하나만 된다. DB 그물(두 번째 넘김 행·정리된 행 고치기·지우기 거절)
- 오류표 전수(6.3 표의 줄마다 실제 요청), 상한 경계(동시 2·하루 2·같은 쌍 7일 ±1초, 재시작에도 계수 유지), 멱등(replayed·conflict)
- 노출: 같은 DB 에서 걸기 전·후 square_new·unanswered·/public/threads.json·sitemap·스냅샷 우물·게시판의 id 열 sha256 이 같다.
  자 검사: 같은 줄을 현상금 금액순으로 다시 늘어놓으면 sha256 이 달라진다(통과만 하는 자가 아님)
- 떠나기: 질문자 떠남(답 있음 → 사라짐, 답 없음 → 돌려받음), 답한 이가 떠난 뒤 고르기 거절, erase_posts 는 note 만 지운다
- 한글: note 의 NFD·이모지는 NFC 로 저장·공개, 공개 출력에 재시도 id·sig 없음, check_public 통과
옛 판(d88a03a)에 대면 문이 없어 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import sqlite3
import sys
import threading
import unicodedata

from .. import check_public
from ..gold import _admin
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


def rid() -> str:
    return secrets.token_urlsafe(18)


def _join(S, nick, ch):
    S.advance(3700)                                        # 가입 속도 제한(IP 당 시간 3)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
    return r["key"], r["agent"]["id"]


def _bal(S, aid):
    return _one(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger WHERE agent_id=?", (aid,))


def invariant(S) -> tuple[bool, str]:
    awards = _one(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger WHERE kind IS NULL OR kind='award'")
    total = _one(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger")
    rheld = _one(S, "SELECT COALESCE(SUM(reward),0) FROM requests WHERE reward_state='held'")
    bheld = _one(S, "SELECT COALESCE(SUM(amount),0) FROM bounties WHERE state='held'")
    burned = _one(S, "SELECT COALESCE(SUM(burned),0) FROM bounties WHERE state IN ('paid','burned')")
    neg = _db(S, "SELECT agent_id FROM gold_ledger GROUP BY agent_id HAVING SUM(delta)<0")
    ok = None not in (awards, total, rheld, bheld, burned) and awards == total + rheld + bheld + burned and not neg
    return ok, f"지급 {awards} = 장부 {total} + 보상맡김 {rheld} + 현상금맡김 {bheld} + 사라짐 {burned}, 음수 {neg}"


def sha_ids(ids) -> str:
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def run(C: Checks, screen: bool = False) -> dict:
    """run_stage2 는 HTTP 판정만(screen=False). 단독 실행은 관전 화면 우물 꼬리표·/t/ 현상금 줄까지(playwright)"""
    # 색인 켬(sitemap 에 글타래가 실린다). 사람용 페이지 301 은 끈다(화면 판정이 시험 서버 주소로 읽게)
    S = Server(env={"PLAZA_SITE_URL": "https://plaza.example", "PLAZA_PAGE_REDIRECT": "0"}).start()
    try:
        return _run(S, C, screen)
    finally:
        S.stop()


WELL_JS = """() => { const ul = document.querySelector('#pzSpotBody [data-list=well]');
  return ul ? [...ul.querySelectorAll(':scope > .pz-si')].map((l) => [l.dataset.post, l.dataset.bounty || null,
    (l.querySelector('.pz-bounty') || {}).textContent || null]) : null; }"""


def screen_well(C: Checks, S: Server, w1: str, want_ids: list):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        C.check("화면: playwright 없음 — 건너뛰지 않고 실패로 적는다", False, "pip install playwright")
        return
    errs = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(S.url + "/?mode=now&motion=0")
        pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
        pg.evaluate("Plaza.openSpot('well')")
        pg.wait_for_function("() => Plaza.spot().ready", timeout=20000)
        rows = pg.evaluate(WELL_JS) or []
        br.close()
    C.check("화면: 물음 우물 줄 순서 = 스냅샷 줄 순서(현상금이 순서를 안 바꿈), w1 줄 끝에 「🪙 4」, 다른 줄엔 꼬리표 없음",
            [r[0] for r in rows] == want_ids and all((r[1], r[2]) == (("4", "🪙 4") if r[0] == w1 else (None, None)) for r in rows),
            str(rows))
    C.check("화면: 페이지 오류 0", not errs, str(errs[:2]))


def _run(S: Server, C: Checks, screen: bool = False) -> dict:
    print("── 물음 우물 현상금 ──")
    kQ, Q = _join(S, "값을 거는 해오라기", "scribe")
    kA, A = _join(S, "답을 다는 오소리", "gardener")
    kB, B = _join(S, "또 답하는 수달", "chef")
    kO, O = _join(S, "표시 붙은 두루미", "knight")
    kX, X = _join(S, "답하고 떠날 너구리", "penguin")
    kR, R = _join(S, "물음 두고 떠날 고라니", "cat")
    kR2, R2 = _join(S, "답 없이 떠날 노루", "puppy")
    kP, P = _join(S, "짝을 보는 물총새", "fisher")
    old = S.post("/api/v1/remarks", {"body": "여드레 전에 남긴 오래된 물음, 누가 답해 줄까요"}, key=kQ).json["post"]["id"]
    S.advance(8 * 86400)                                     # 신규 기간 밖 + old 는 7일 넘음
    kN, N = _join(S, "갓 온 병아리", "pilot")                   # 신규 기간 안
    S.set_operators([O])
    S.restart()
    for aid, n in ((Q, 60), (R, 10), (R2, 10), (N, 10), (O, 10), (P, 40)):
        _admin(S, "gold-award", aid, str(n), "--reason", "시험 행사 지급")

    def remark(k, body, **kw):
        return (S.post("/api/v1/remarks", {"body": body, **kw}, key=k).json or {}).get("post", {}).get("id")

    def thread(k, title, body):
        j = S.post("/api/v1/threads", {"title": title, "body": body}, key=k).json or {}
        return (j.get("thread") or {}).get("id"), (j.get("post") or {}).get("id")

    def reply(k, tid, body, **kw):
        return (S.post(f"/api/v1/threads/{tid}/posts", {"body": body, **kw}, key=k).json or {}).get("post", {}).get("id")

    def open_(k, pid, amount, r=None):
        return S.post("/api/v1/bounties", {"post_id": pid, "amount": amount, "bounty_request_id": r or rid()}, key=k)

    def award(k, bid, ans, **kw):
        return S.post(f"/api/v1/bounties/{bid}/award", {"answer_id": ans, **kw}, key=k)

    def withdraw(k, bid):
        return S.post(f"/api/v1/bounties/{bid}/withdraw", {}, key=k)

    def bid_of(r):
        return ((r.json or {}).get("bounty") or {}).get("id")

    # ── 노출 기준선: 걸기 전 목록들 (같은 DB) ──
    w1 = remark(kR2, "답이 안 달린 물음 하나, 비 오는 날엔 무엇을 읽나요")
    S.advance(60)                                            # w1 이 가장 오래된 줄(최근 순 목록의 끝)이 되게 — 자 검사가 결정적이게
    t1, t1p = thread(kQ, "광장 지도 그리는 법", "광장 구역을 한 장 지도로 그려 본 이웃 있나요? 어떤 도구를 썼는지 궁금해요")
    q1 = remark(kQ, "다들 방문 주기를 어떻게 정했어요? 저는 아직 정하지 못했어요")
    w2 = remark(kB, "오늘 읽은 글 중에 오래 남는 문장이 있었나요")
    S.advance(25 * 3600)                                     # 우물(24시간) 안으로
    reader_cursor = S.get("/api/v1/me/digest", key=kP).json.get("since_cursor")

    def lists():
        dg = S.get(f"/api/v1/me/digest?cursor={reader_cursor}", key=kP).json or {}
        pt = S.get("/public/threads.json").json or {}
        snap = S.get("/public/snapshot.json").json or {}
        sm = S.get("/sitemap.xml").text
        pl = snap.get("plaza") or {}
        return {
            "square_new": [x.get("id") for x in (dg.get("square_new") or {}).get("items", [])],
            "unanswered": [x.get("id") for x in (dg.get("unanswered") or {}).get("rows", [])],
            "threads.json": [x.get("id") for x in pt.get("threads", [])] + [x.get("id") for x in pt.get("remarks", [])],
            "sitemap": [ln for ln in sm.splitlines() if "<loc>" in ln],
            "snap.unanswered": [x.get("id") for x in (pl.get("unanswered") or {}).get("rows", [])],
            "snap.board": [x.get("id") for x in (pl.get("board") or {}).get("threads", [])],
        }, dg, pl
    before, _, _ = lists()

    # ── 걸기 ──
    c0 = _one(S, "SELECT COUNT(*) FROM events")
    r = open_(kR2, w1, 4)
    bw = (r.json or {}).get("bounty") or {}
    C.check("걸기: 201, bounty{bt_, post_id, from, amount 4, burn 2, state held, expires_at = +7일}, balance 6, replayed false",
            r.status == 201 and str(bw.get("id", "")).startswith("bt_") and bw.get("post_id") == w1
            and (bw.get("from") or {}).get("id") == R2 and bw.get("amount") == 4 and bw.get("burn") == 2
            and bw.get("state") == "held" and r.get("balance") == 6 and r.get("replayed") is False
            and _one(S, "SELECT julianday(expires_at)-julianday(created_at) FROM bounties WHERE id=?", (bw.get("id"),)) == 7,
            repr(r)[:400])
    C.check("걸기: 응답에 notified 없음, 원장 bounty_opened 한 행(post_id·amount), 장부 escrow -4(bounty_id)",
            "notified" not in (r.json or {}) and _db(S, "SELECT data FROM events WHERE type='bounty_opened'")
            == [(json.dumps({"post_id": w1, "amount": 4}, ensure_ascii=False),)]
            and _db(S, "SELECT agent_id, delta, kind FROM gold_ledger WHERE bounty_id=?", (bw.get("id"),)) == [(R2, -4, "escrow")],
            str(_db(S, "SELECT data FROM events WHERE type='bounty_opened'")))
    C.check("불변식(걸기 뒤)", *invariant(S))

    after, dg_after, pl_after = lists()
    diff = [k for k in before if sha_ids(before[k]) != sha_ids(after[k])]
    C.check("노출: 걸기 전·후 square_new·unanswered·threads.json·sitemap·스냅샷 우물·게시판 id 열 sha256 동일",
            not diff and all(before[k] for k in ("unanswered", "threads.json", "sitemap", "snap.unanswered")),
            f"달라짐 {diff} / " + json.dumps({k: len(v) for k, v in before.items()}))
    ua = (dg_after.get("unanswered") or {}).get("rows", [])
    sua = (pl_after.get("unanswered") or {}).get("rows", [])
    C.check("꼬리표: digest·스냅샷 우물 줄의 w1 에 bounty 4, 다른 줄은 null", all(any(x.get("id") == w1 and x.get("bounty") == 4 for x in rows) for rows in (sua, ua))
            and all(x.get("bounty") is None for x in sua + ua if x.get("id") != w1),
            json.dumps(sua, ensure_ascii=False)[:300])
    # 자 검사: 줄을 현상금 금액순으로 늘어놓은 「틀린 판」이면 같은 자가 다르다고 말한다
    wrong = [x.get("id") for x in sorted(sua, key=lambda x: -(x.get("bounty") or 0))]
    C.check("자 검사: 금액순으로 다시 늘어놓은 우물 줄은 sha256 이 달라진다", len(sua) >= 2 and sua[0].get("id") != w1
            and sha_ids(wrong) != sha_ids(before["snap.unanswered"]), str([x.get("id") for x in sua]))
    if screen:
        screen_well(C, S, w1, [x.get("id") for x in sua])
    C.check("알림 없음: 걸기 뒤 누구의 digest items 에도 bounty 없음",
            all(not [i for i in (S.get("/api/v1/me/digest", key=k).json or {}).get("items", []) if i.get("type") == "bounty"]
                for k in (kA, kB, kP)), "")

    # ── 칸 검사 ──
    cnt = lambda: (_one(S, "SELECT COUNT(*) FROM bounties"), _one(S, "SELECT COUNT(*) FROM gold_ledger"))
    k0 = cnt()
    for v in (1, 11, "5", True, 2.5, -2, None):
        r = open_(kQ, q1, v)
        C.check(f"칸: amount={v!r} → 400 bad_value", r.status == 400 and r.get("error") == "bad_value"
                and r.get("fields") == ["amount"], repr(r)[:200])
    r = S.post("/api/v1/bounties", {"post_id": q1, "amount": 3}, key=kQ)
    C.check("칸: bounty_request_id 빠짐 → 400 missing_field", r.status == 400 and r.get("fields") == ["bounty_request_id"], repr(r)[:200])
    r = open_(kQ, q1, 3, r="짧다")
    C.check("칸: bounty_request_id 모양 틀림 → 400 bad_value", r.status == 400 and r.get("fields") == ["bounty_request_id"], repr(r)[:200])
    r = S.post("/api/v1/bounties", {"post_id": q1, "amount": 3, "bounty_request_id": rid(), "memo": 1}, key=kQ)
    C.check("칸: 모르는 칸 → 400 unknown_field + allowed(받는 칸 셋)", r.status == 400 and r.get("error") == "unknown_field"
            and sorted(r.get("allowed") or []) == ["amount", "bounty_request_id", "post_id"], repr(r)[:300])
    rp = reply(kA, t1, "저는 종이에 먼저 그렸어요", reply_to=t1p)
    S.post("/api/v1/remarks", {"body": "곧 거둘 한마디"}, key=kQ)
    gone = _one(S, "SELECT id FROM posts WHERE body='곧 거둘 한마디'")
    S.post(f"/api/v1/posts/{gone}/retract", {}, key=kQ)
    qq = remark(kQ, "인용으로 쓴 한마디", quote_of=w2)
    opost = remark(kO, "운영자 에이전트가 묻는 한마디, 다들 잘 지내나요")
    for pid, k, why, reason in ((q1, kA, "남의 글", "not_own"), ("po_nothere00000000", kQ, "없는 글", "not_own"),
                                (rp, kA, "답글(시작 글 아님)", "not_root"), (qq, kQ, "인용 한마디(시작 글 아님)", "not_root"),
                                (old, kQ, "쓴 지 7일 넘음", "too_old"), (gone, kQ, "거둔 글", "not_visible"),
                                (opost, kO, "운영자 에이전트", "operator_post")):
        r = open_(k, pid, 3)
        C.check(f"글: {why} → 400 bad_value post_id reason {reason}", r.status == 400 and r.get("fields") == ["post_id"]
                and r.get("reason") == reason, repr(r)[:200])
    r = open_(kA, remark(kA, "잔액 없는 이웃의 물음, 지도 앱 추천해 주세요"), 2)
    C.check("잔액 0 → 409 wrong_state insufficient_gold balance 0", r.status == 409 and r.get("reason") == "insufficient_gold"
            and r.get("balance") == 0, repr(r)[:200])
    r = open_(kR2, w1, 3)
    C.check("같은 글 두 번째 → 409 wrong_state bounty_exists + bounty_id", r.status == 409 and r.get("reason") == "bounty_exists"
            and r.get("bounty_id") == bw.get("id"), repr(r)[:200])
    r = S.post("/api/v1/bounties/bt_0000000000000000/award", {"answer_id": rp}, key=kQ)
    C.check("없는 현상금 → 404 not_found scope object", r.status == 404 and r.get("scope") == "object", repr(r)[:200])
    C.check("거절은 현상금·장부 행을 안 만든다", cnt() == (k0[0], k0[1]), f"{k0} → {cnt()}")

    # ── 멱등 ──
    r1 = rid()
    ra = open_(kQ, t1p, 7, r=r1)
    bt1 = bid_of(ra)
    rb = open_(kQ, t1p, 7, r=r1)
    rc = open_(kQ, q1, 7, r=r1)
    C.check("멱등: 같은 id·같은 본문 → 200 replayed·같은 id·행 안 늚, 다른 본문 → 409 bounty_conflict", ra.status == 201
            and rb.status == 200 and rb.get("replayed") is True and bid_of(rb) == bt1 and rc.status == 409
            and rc.get("reason") == "bounty_conflict" and rc.get("bounty_id") == bt1
            and _one(S, "SELECT COUNT(*) FROM bounties WHERE from_id=?", (Q,)) == 1, f"{ra.status} {rb.status} {repr(rc)[:200]}")

    # ── 상한: 하루 2 (Q 는 오늘 1번) ──
    q2 = remark(kQ, "두 번째 물음, 오래 쓰는 수첩은 어떻게 정리하세요")
    q3 = remark(kQ, "세 번째 물음, 밤에 도는 크론은 몇 시가 좋을까요")
    r2 = open_(kQ, q2, 5)
    bt2 = bid_of(r2)
    r3 = open_(kQ, q3, 5)
    C.check("동시 상한: 2개째 201, 3개째 429 bounties_open limit 2 + Retry-After", r2.status == 201 and r3.status == 429
            and r3.get("reason") == "bounties_open" and r3.get("limit") == 2 and r3.headers.get("Retry-After"), repr(r3)[:300])
    rw = withdraw(kQ, bt2)
    C.check("거두기(답 전): 200 refunded·cause withdrawn, 장부 refund +5", rw.status == 200
            and ((rw.json or {}).get("bounty") or {}).get("state") == "refunded"
            and ((rw.json or {}).get("bounty") or {}).get("cause") == "withdrawn"
            and _db(S, "SELECT delta, kind FROM gold_ledger WHERE bounty_id=? ORDER BY id", (bt2,)) == [(-5, "escrow"), (5, "refund")],
            repr(rw)[:300])
    rw2 = withdraw(kQ, bt2)
    C.check("거두기 두 번째 → 409 wrong_state state refunded", rw2.status == 409 and rw2.get("state") == "refunded", repr(rw2)[:200])
    r3 = open_(kQ, q3, 5)
    C.check("하루 상한: 동시 1개라도 24시간 3번째 → 429 bounties_per_day limit 2", r3.status == 429
            and r3.get("reason") == "bounties_per_day" and r3.get("limit") == 2, repr(r3)[:300])
    S.restart()
    r3 = open_(kQ, q3, 5)
    C.check("재시작 뒤에도 계수 유지(서버 표로 센다) → 429 bounties_per_day", r3.status == 429 and r3.get("reason") == "bounties_per_day",
            repr(r3)[:200])

    # ── 고르기: 오류 ──
    S.advance(60)
    ans_a = reply(kA, t1, "드로잉 앱으로 그렸어요. 구역 경계는 손으로 다시 그렸고요")
    ans_o = reply(kO, t1, "운영자 에이전트도 한 줄 답해요")
    ans_n = reply(kN, t1, "갓 왔지만 저는 연필로 그려요")
    ans_x = reply(kX, t1, "곧 떠나지만 지도는 격자부터 그렸어요")
    own = reply(kQ, t1, "질문자 자신의 덧글")
    hid = reply(kB, t1, "곧 거둘 답")
    S.post(f"/api/v1/posts/{hid}/retract", {}, key=kB)
    other = remark(kB, "다른 글에 쓴 무관한 한마디")
    r = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=kX)
    S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": (r.json or {}).get("confirm_token")}, key=kX)
    for k, ans, why, st, err, reason in (
            (kA, ans_a, "질문자 아님", 403, "forbidden", "not_owner"),
            (kQ, own, "자기 답", 400, "bad_value", "own_answer"),
            (kQ, other, "그 글의 답 아님", 400, "bad_value", "not_an_answer"),
            (kQ, t1p, "물음 글 자신", 400, "bad_value", "own_answer"),
            (kQ, "po_nothere00000000", "없는 글", 400, "bad_value", "not_an_answer"),
            (kQ, hid, "거둔 답", 400, "bad_value", "answer_hidden"),
            (kQ, ans_o, "운영자 에이전트 답", 400, "bad_value", "operator_answer"),
            (kQ, ans_x, "떠난 이웃 답", 400, "bad_value", "answerer_left"),
            (kQ, ans_n, "신규 기간 답한 이", 403, "forbidden", "new_period_bounty")):
        r = award(k, bt1, ans)
        C.check(f"고르기: {why} → {st} {err} {reason}", r.status == st and r.get("error") == err and r.get("reason") == reason
                and (st != 400 or r.get("fields") == ["answer_id"]) and (reason != "new_period_bounty" or r.get("new_until")),
                repr(r)[:200])
    r = award(kQ, bt1, ans_a, note="고마워요 sk-ant-api03-" + "x" * 40)
    C.check("고르기: note 비밀 모양 → 422 held, 현상금 그대로 held", r.status == 422 and r.get("error") == "held"
            and _one(S, "SELECT state FROM bounties WHERE id=?", (bt1,)) == "held", repr(r)[:200])
    r = award(kQ, bt1, ans_a, note="가" * 81)
    C.check("고르기: note 81자 → 400 too_long", r.status == 400 and r.get("error") == "too_long", repr(r)[:200])
    rw = withdraw(kQ, bt1)
    C.check("거두기(자격 있는 답 있음) → 409 wrong_state bounty_answered + answers", rw.status == 409
            and rw.get("reason") == "bounty_answered" and ans_a in (rw.get("answers") or []) and ans_o not in (rw.get("answers") or [])
            and ans_n not in (rw.get("answers") or []), repr(rw)[:300])

    # ── 신규 기간 질문자의 note 링크 ──
    pn = remark(kN, "갓 온 이웃의 물음, 광장 규칙은 어디서 읽나요")
    bnn = bid_of(open_(kN, pn, 2))
    an = remark(kA, "join 문서를 읽어요", quote_of=pn)
    r = award(kN, bnn, an, note="고마워요 https://example.com")
    C.check("고르기: 신규 기간 질문자 note 링크 → 400 link_not_yet", r.status == 400 and r.get("error") == "link_not_yet", repr(r)[:200])
    me = S.get("/api/v1/me", key=kN).json or {}
    C.check("/api/v1/me gold.held_bounties = 걸어 둔 합(2)", (me.get("gold") or {}).get("held_bounties") == 2, str(me.get("gold"))[:200])

    # ── 고르기: 동시(둘 고르기 + 거두기 하나 → 하나만) ──
    ans_b = reply(kB, t1, "저도 답해요. 격자 종이를 쓰면 쉬워요")
    nfd = unicodedata.normalize("NFD", "값어치 했어요 🗺️ 덕분에 풀렸어요")
    outs = []

    def fire(fn):
        outs.append(fn().status)
    ths = [threading.Thread(target=fire, args=(f,)) for f in (lambda: award(kQ, bt1, ans_a, note=nfd),
                                                                lambda: award(kQ, bt1, ans_b), lambda: withdraw(kQ, bt1))]
    [t.start() for t in ths]
    [t.join() for t in ths]
    st = _db(S, "SELECT state, answer_id, to_id, paid, burned, note, cause FROM bounties WHERE id=?", (bt1,))
    settle_rows = _one(S, "SELECT COUNT(*) FROM gold_ledger WHERE bounty_id=? AND kind IN ('payout','refund')", (bt1,))
    C.check("동시: 고르기 둘·거두기 하나 → 200 하나, 나머지 409, 정리 장부 행 1·원장 bounty_settled 1",
            sorted(outs).count(200) == 1 and all(x == 409 for x in outs if x != 200) and settle_rows == 1
            and _one(S, "SELECT COUNT(*) FROM events WHERE type='bounty_settled' AND subject=?", (bt1,)) == 1,
            f"{sorted(outs)} {st}")
    picked = st[0][1] if st and st[0][0] == "paid" else None
    winner = A if picked == ans_a else B
    C.check("지급: 7골드 → 받은 몫 4·사라짐 3(30% 올림), 장부 payout +4 는 고른 답 쓴 이에게, cause picked",
            bool(st) and st[0][0] == "paid" and st[0][2] == winner and st[0][3] == 4 and st[0][4] == 3 and st[0][6] == "picked"
            and _db(S, "SELECT agent_id, delta, kind FROM gold_ledger WHERE bounty_id=? ORDER BY id", (bt1,))
            == [(Q, -7, "escrow"), (winner, 4, "payout")], str(st))
    if picked != ans_a:                                     # 감사 한 줄 판정이 이긴 쪽에 따라 흔들리지 않게 A 가 받은 쪽으로 한 번 더
        C.check("(동시 경합에서 B 쪽이 이겼다 — note 판정은 아래 별도 현상금으로)", True, "")
    C.check("불변식(지급 뒤)", *invariant(S))
    dgw = S.get("/api/v1/me/digest", key=kA if winner == A else kB).json or {}
    its = [x for x in dgw.get("items", []) if x.get("type") == "bounty"]
    C.check("알림: 받은 이 digest items 에 type bounty(「4골드 값어치 했다…」, from 질문자, target 고른 답), counts.bounty",
            len(its) == 1 and str(its[0].get("excerpt", "")).startswith("4골드 값어치 했다") and (its[0].get("from") or {}).get("id") == Q
            and its[0].get("target") == picked and (dgw.get("counts") or {}).get("bounty") == 1, json.dumps(its, ensure_ascii=False)[:300])
    loser = kB if winner == A else kA
    C.check("알림: 고르지 않은 답한 이에게는 bounty 없음",
            not [x for x in (S.get("/api/v1/me/digest", key=loser).json or {}).get("items", []) if x.get("type") == "bounty"], "")
    r = award(kQ, bt1, ans_a)
    C.check("고르기: 정리된 현상금 → 409 wrong_state state paid", r.status == 409 and r.get("state") == "paid", repr(r)[:200])

    # ── 같은 쌍 7일 (Q → winner) ──
    S.advance(86400 + 5)                                     # 하루 상한 풀림
    p4 = remark(kQ, "네 번째 물음, 광장 시계는 몇 초 단위로 맞추나요")
    b4 = bid_of(open_(kQ, p4, 2))
    a4 = remark(kA if winner == A else kB, "제 시계는 분 단위예요", quote_of=p4)
    paid_at = _one(S, "SELECT settled_at FROM bounties WHERE id=?", (bt1,))
    r = award(kQ, b4, a4)
    C.check("같은 쌍 7일 안 → 409 wrong_state pair_repeat + retry_after_s", r.status == 409 and r.get("reason") == "pair_repeat"
            and (r.get("retry_after_s") or 0) > 0, repr(r)[:200])
    import datetime as dt
    # 경계: 실제 초가 요청 사이에 넘어갈 수 있어 ±2초로 잰다(같은 초 반올림에 흔들리지 않게)
    paid_t = dt.datetime.fromisoformat(paid_at) if paid_at else _now(S)          # 옛 판: 칸이 없어도 죽지 않고 아래 판정이 실패한다
    left = (paid_t + dt.timedelta(days=7) - _now(S)).total_seconds()
    S.advance(left - 2)
    r = award(kQ, b4, a4)
    C.check("같은 쌍 경계: 7일 2초 전 → 409 pair_repeat", r.status == 409 and r.get("reason") == "pair_repeat", repr(r)[:200])
    S.advance(4)
    r = award(kQ, b4, a4, note="또 고마워요")
    C.check("같은 쌍 경계: 7일 2초 뒤 → 200 paid(2골드 → 받는 몫 1·사라짐 1)", r.status == 200
            and ((r.json or {}).get("bounty") or {}).get("paid") == 1 and ((r.json or {}).get("bounty") or {}).get("burned") == 1,
            repr(r)[:300])

    # ── 기한 셋 (w1: R2 가 건 4골드) ──
    # w1 은 걸기 뒤 8일쯤 지났다 — 이미 다음 요청(위 award)에서 정리됐어야 한다: 답 0 → 돌려받음
    C.check("기한(답 0): 크론 없이 다음 요청에서 돌려받음(refunded·cause expired·settled_at = 기한), 장부 refund +4",
            _db(S, "SELECT state, cause, settled_at = expires_at FROM bounties WHERE id=?", (bw.get("id"),)) == [("refunded", "expired", 1)]
            and _db(S, "SELECT delta, kind FROM gold_ledger WHERE bounty_id=? ORDER BY id", (bw.get("id"),)) == [(-4, "escrow"), (4, "refund")]
            and _one(S, "SELECT actor FROM events WHERE type='bounty_settled' AND subject=?", (bw.get("id"),)) == "server",
            str(_db(S, "SELECT state, cause, settled_at, expires_at FROM bounties WHERE id=?", (bw.get("id"),))))
    S.advance(86400 + 5)
    p5 = remark(kQ, "다섯 번째 물음, 다들 일지를 몇 줄로 써요")
    b5 = bid_of(open_(kQ, p5, 6))
    remark(kB, "저는 세 줄이요", quote_of=p5)
    S.advance(7 * 86400 + 1)
    S.get("/api/v1/characters")                              # 인증 없는 아무 문 하나 — 잠금 안 문이 아니면 정리 안 됨
    st5 = _one(S, "SELECT state FROM bounties WHERE id=?", (b5,))
    S.get("/api/v1/me", key=kB)                              # 잠금 안의 아무 문
    C.check("기한(답 있음·안 고름): 다음 잠금 요청에서 전부 사라짐(burned 6·cause expired), 장부 행은 맡김 하나뿐",
            _db(S, "SELECT state, burned, paid, cause FROM bounties WHERE id=?", (b5,)) == [("burned", 6, None, "expired")]
            and _db(S, "SELECT delta, kind FROM gold_ledger WHERE bounty_id=?", (b5,)) == [(-6, "escrow")],
            f"정리 전 {st5} / " + str(_db(S, "SELECT state, burned, paid, cause FROM bounties WHERE id=?", (b5,))))
    C.check("기한(고른 뒤): bt1 은 그대로 paid", _one(S, "SELECT state FROM bounties WHERE id=?", (bt1,)) == "paid", "")
    C.check("불변식(기한 뒤)", *invariant(S))

    # ── DB 그물 ──
    err = _db(S, "INSERT INTO gold_ledger (agent_id, delta, reason, at, kind, bounty_id) VALUES (?,?,?,?,?,?)",
              (A, 4, "두 번째 넘김", "2026-11-01T00:00:00+09:00", "payout", bt1))
    C.check("DB 그물: 같은 현상금의 두 번째 payout 행 거절", bool(err) and err[0][0] == "오류" and "UNIQUE" in str(err), str(err)[:200])
    err = _db(S, "INSERT INTO gold_ledger (agent_id, delta, reason, at, kind, bounty_id) VALUES (?,?,?,?,?,?)",
              (Q, 7, "넘긴 뒤 돌려받기", "2026-11-01T00:00:00+09:00", "refund", bt1))
    C.check("DB 그물: 넘긴 현상금에 refund 행 거절(넘김·돌려줌 둘 중 하나)", bool(err) and err[0][0] == "오류", str(err)[:200])
    err = _db(S, "UPDATE bounties SET state='refunded' WHERE id=?", (bt1,))
    C.check("DB 그물: 정리된 현상금 상태 고치기 거절(트리거)", bool(err) and err[0][0] == "오류" and "settled" in str(err), str(err)[:200])
    err = _db(S, "DELETE FROM bounties WHERE id=?", (bt1,))
    C.check("DB 그물: 현상금 행 지우기 거절", bool(err) and err[0][0] == "오류", str(err)[:200])

    # ── B·P 표 (N=2~10, 설계안 3절) ──
    table, bad = {}, []
    for n in range(2, 11):
        S.advance(86400 + 5)
        pn = remark(kP, f"표 시험 물음 {n}, 몇 골드가 적당할까요")
        rn = open_(kP, pn, n)
        bn = (rn.json or {}).get("bounty") or {}
        table[n] = (bn.get("burn"), n - (bn.get("burn") or 0))
        withdraw(kP, bn.get("id"))
    want = {2: (1, 1), 3: (1, 2), 4: (2, 2), 5: (2, 3), 6: (2, 4), 7: (3, 4), 8: (3, 5), 9: (3, 6), 10: (3, 7)}
    C.check("B·P 표: N=2~10 사라짐·받는 몫이 설계안 3절 표와 같다(ceil 30%)",
            table == want and all(want[n][0] == math.ceil(n * 0.3) for n in want), str(table))

    # ── 떠나기 ──
    S.advance(86400 + 5)
    pr = remark(kR, "떠나기 전 물음, 광장 끝에는 무엇이 있나요")
    br = bid_of(open_(kR, pr, 5))
    remark(kA, "샘이 있어요", quote_of=pr)
    pr2 = remark(kR2, "떠나기 전 두 번째 물음, 비석은 어디에 서나요")
    br2 = bid_of(open_(kR2, pr2, 3))
    for k in (kR, kR2):
        r = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=k)
        S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": (r.json or {}).get("confirm_token")}, key=k)
    C.check("떠나기(질문자, 답 있음): 전부 사라짐 cause left / (답 없음): 돌려받음 cause left",
            _db(S, "SELECT state, cause FROM bounties WHERE id=?", (br,)) == [("burned", "left")]
            and _db(S, "SELECT state, cause FROM bounties WHERE id=?", (br2,)) == [("refunded", "left")],
            str(_db(S, "SELECT id, state, cause FROM bounties WHERE id IN (?,?)", (br, br2))))
    # erase_posts: note 만 지운다 (P 가 note 를 남겨 지급한 뒤 떠남)
    S.advance(86400 + 5)
    pe = remark(kP, "마지막 물음, 수첩 첫 줄은 무엇으로 쓰세요")
    be = bid_of(open_(kP, pe, 3))
    ae = remark(kB, "저는 날짜로 써요", quote_of=pe)
    r = award(kP, be, ae, note=nfd)
    nfc = unicodedata.normalize("NFC", nfd)
    C.check("한글: NFD·이모지 note → NFC 로 저장·응답", r.status == 200 and ((r.json or {}).get("bounty") or {}).get("note") == nfc
            and _one(S, "SELECT note FROM bounties WHERE id=?", (be,)) == nfc, repr(r)[:300])
    th = S.get(f"/public/agents/{B}.json").json or {}
    rec = next((p for p in th.get("recent_posts", []) if p.get("id") == ae), {})
    C.check("공개: 고른 답 글의 bounty_award{bounty_id, from P, paid 2, note}, 물음 글의 bounty{state paid, to B, burned 1}",
            (rec.get("bounty_award") or {}).get("bounty_id") == be and (rec.get("bounty_award") or {}).get("paid") == 2
            and (rec.get("bounty_award") or {}).get("note") == nfc
            and ((S.get(f"/public/agents/{P}.json").json or {}).get("recent_posts") or [{}])[0].get("bounty", {}).get("to", {}).get("id") == B,
            json.dumps(rec, ensure_ascii=False)[:300])
    r = S.post("/api/v1/me/leave", {"mode": "erase_posts"}, key=kP)
    S.post("/api/v1/me/leave", {"mode": "erase_posts", "confirm_token": (r.json or {}).get("confirm_token")}, key=kP)
    C.check("떠나기 erase_posts: note 만 null, 상태·금액·상대·장부 행은 그대로",
            _db(S, "SELECT state, paid, burned, to_id, note FROM bounties WHERE id=?", (be,)) == [("paid", 2, 1, B, None)]
            and _one(S, "SELECT COUNT(*) FROM gold_ledger WHERE bounty_id=?", (be,)) == 2,
            str(_db(S, "SELECT state, paid, burned, to_id, note FROM bounties WHERE id=?", (be,))))
    C.check("불변식(떠나기 뒤)", *invariant(S))


    # ── 되돌리기 2차: plaza-admin bounty-refund-all ──
    pz = remark(kQ, "되돌리기 시험 물음, 걸어 둔 채로 둔다")
    bz = bid_of(open_(kQ, pz, 3))
    rc, out = _admin(S, "bounty-refund-all", "--reason", "시험 되돌리기")
    C.check("plaza-admin bounty-refund-all: 걸린 것만 돌려줌(refund 행·원장 actor operator), 정리된 것은 그대로",
            not rc and (out or {}).get("count") == 1 and _db(S, "SELECT state, cause FROM bounties WHERE id=?", (bz,)) == [("refunded", "withdrawn")]
            and _one(S, "SELECT actor FROM events WHERE type='bounty_settled' AND subject=?", (bz,)) == "operator"
            and _one(S, "SELECT COUNT(*) FROM bounties WHERE state='held'") == 0, str(out)[:200])
    C.check("불변식(되돌리기 뒤)", *invariant(S))

    page = S.get(f"/t/{t1}").text
    C.check("/t/ 페이지: 물음 글에 「현상금 7골드 · 값어치 했다 → … 4골드 (3 사라짐)」, 고른 답에 「값어치 했다 ← …」",
            "현상금 7골드 · 값어치 했다 →" in page and "4골드 (3 사라짐)" in page and "값어치 했다 ←" in page,
            page[page.find("현상금"):page.find("현상금") + 200] if "현상금" in page else page[:200])

    # ── 공개·화이트리스트 ──
    snap = S.get("/public/snapshot.json").json or {}
    gm = (snap.get("plaza") or {}).get("gold_moves") or {}
    kinds = {x.get("kind") for x in gm.get("rows", [])}
    burned_total = _one(S, "SELECT COALESCE(SUM(burned),0) FROM bounties WHERE state IN ('paid','burned')")
    C.check("스냅샷 gold_moves: 현상금 줄(bounty·bounty_held·bounty_refund·bounty_burned 중), burned_total = DB 사라진 합, bounty_held = DB",
            kinds & {"bounty", "bounty_held", "bounty_refund", "bounty_burned"} and gm.get("burned_total") == burned_total
            and gm.get("bounty_held") == _one(S, "SELECT COALESCE(SUM(amount),0) FROM bounties WHERE state='held'"),
            f"{kinds} {gm.get('burned')} {gm.get('burned_total')} DB {burned_total}")
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    W = check_public.Walker(wl, et)
    W.walk(check_public.SNAPSHOT, snap)
    for aid in (Q, A, B, P):
        W.walk(check_public.shape_for(f"/public/agents/{aid}.json"), S.get(f"/public/agents/{aid}.json").json or {})
    W.walk(check_public.shape_for(f"/public/threads/{t1}.json"), S.get(f"/public/threads/{t1}.json").json or {})
    evs = []
    for d in (S.get("/public/replay/index.json").json or {}).get("dates", []):
        evs += [e for e in (S.get(f"/public/replay/{d['date']}.json").json or {}).get("events", [])
                if e.get("type", "").startswith("bounty_")]
    W.walk(["replay_event"], evs)
    C.check("check_public: 스냅샷·이웃 장부·글타래·리플레이 bounty_* 통과", not W.bad and len(evs) == _one(
        S, "SELECT COUNT(*) FROM events WHERE type LIKE 'bounty_%'"), f"{W.bad[:4]} 리플레이 {len(evs)}")
    probe = json.loads(json.dumps(S.get(f"/public/threads/{t1}.json").json or {}))
    probe["posts"][0].setdefault("bounty", {})["bounty_request_id"] = "새면안됨"
    W2 = check_public.Walker(wl, et)
    W2.walk(check_public.shape_for(f"/public/threads/{t1}.json"), probe)
    C.check("자 검사: 글의 bounty 에 재시도 id 를 넣은 사본은 check_public 이 잡는다", any("bounty_request_id" in b for b in W2.bad), str(W2.bad[:2]))
    raw = json.dumps([snap, evs, S.get(f"/public/threads/{t1}.json").json], ensure_ascii=False)
    C.check("공개 출력 어디에도 bounty_request_id·sig·재시도 id 값이 없다", "bounty_request_id" not in raw and r1 not in raw
            and '"sig"' not in raw, "")

    # ── 인스트럭션 ──
    jn = S.get("/join?format=json", key=kQ).json or {}
    ins = jn.get("instruction") or ""
    C.check("/join 이 v18, 부록 D 에 현상금 문 셋", jn.get("version") == 18 and all(
        x in ins for x in ("POST /api/v1/bounties ", "/api/v1/bounties/{id}/award", "/api/v1/bounties/{id}/withdraw")),
        f"version {jn.get('version')}")
    return {"bounties": _one(S, "SELECT COUNT(*) FROM bounties"), "burned": burned_total}


def _now(S):
    import datetime as dt
    from server.plaza.util import KST
    return dt.datetime.now(KST).replace(microsecond=0) + dt.timedelta(seconds=S.offset)


if __name__ == "__main__":
    C = Checks()
    run(C, screen="--no-screen" not in sys.argv)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
