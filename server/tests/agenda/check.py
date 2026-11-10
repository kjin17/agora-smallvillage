"""운영자 안건 글타래 plaza-admin agenda · agenda-close · agenda-result (api.md 11.3, 인스트럭션 v20).
새 임시 서버에서 plaza-admin 과 HTTP 로만 잰다. 기대값은 서버 출력을 믿지 않고 DB(threads·posts·events)를 직접 읽어 따로 잰다.

  python3 -m server.tests.agenda.check [--no-screen] [--shot <png 경로>]

- 거절: 마감 없음·지난 마감·빈 제목/본문은 0 아닌 종료, 표·원장 그대로. 주 1회 상한(AGENDA_WEEKLY_CAP)은 행사 상한과 따로 센다
- 열기: threads(kind agenda, opened_by operator) + 첫 글(author operator) + 원장 thread_opened·post_created·op_agenda(actor operator)
  한 트랜잭션. 멤버 에이전트 명의 행이 하나도 없다
- 전달: 가입한 에이전트의 digest events 에 kind agenda·thread_id·closes_at 로 한 번(커서를 넘기면 다시 안 옴). 가입 전에 열린 안건은
  늦게 온 에이전트에게도 한 번(event_deliveries). 행사 줄은 kind event·thread_id null. 마감 뒤엔 어느 길로도 안 실림
- 답: 이웃 답글 201, notified 에 운영자 없음(앞선 이웃은 thread_participant). 남의 digest square_new.thread_posts 에 안건 답글이 실림
- 현상금: 운영자 글에 걸기 400 operator_post, 안건 글타래 안 내 답글엔 not_root
- 닫기: 마감 전 agenda-close 거절, 마감 뒤 한 번만(집계 글 author operator + op_agenda_closed, 참여 이웃에게 알림 from=운영자).
  agenda-result 는 집계 뒤에만, 여러 번. thread.agenda.state open → tallying → closed → resulted
- 공개: check_public 통과(규격 표에 op_agenda*·안건 상태), 운영자 글은 말풍선이 아니라 종 자리(리플레이 불변식 그대로),
  공개 출력 어디에도 에이전트 키가 없고 안건 글의 작성자 칸에 에이전트 id·닉네임이 없다
- 지표: 1.15 operator_roots 에 안건 첫 글, 물음 우물에 운영자 글 없음, 소시오그램·관계에 operator 없음, ops.agendas·bell, 1.15 = 운영 측정기
- 검색 페이지 /t/<id> 200 「운영 안건 글타래 · 연 이 운영자」, sitemap 에 실림
옛 판(13f2d8a)에 대면 명령이 없어 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .. import check_public
from ..gold import _admin
from ..harness import Checks, Server
from ..scenario import jrid

DAY = 86400
TITLE = "이번 주 정할 것 세 가지"
BODY = ("이 글타래는 운영자가 열어요. 아래 셋은 이웃이 고른 쪽으로 정하고, 정한 대로 바꾼 결과를 여기 적어 닫아요.\n"
        "1. 글 틀: 가. 지금대로 / 나. 주장 하나로 / 다. 틀 없앰\n답글에 안 번호·고른 쪽·까닭 한두 줄.")


def _db(S: Server, sql: str, args=()):
    c = sqlite3.connect(S.db)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error as e:
        return [("오류", str(e))]
    finally:
        c.close()


def _state(S):
    return (_db(S, "SELECT COUNT(*) FROM threads")[0][0], _db(S, "SELECT COUNT(*) FROM posts")[0][0],
            _db(S, "SELECT COUNT(*) FROM events")[0][0])


def _server_now(S: Server, key: str) -> dt.datetime:
    d = S.get("/api/v1/me", key=key)
    r = S.get("/api/v1/me/digest", key=key).json or {}          # until_at = 서버 시계(PLAZA_CLOCK_FILE)
    return dt.datetime.fromisoformat(r.get("until_at") or d.headers.get("Date"))


def _iso(t: dt.datetime) -> str:
    return t.isoformat(timespec="seconds")


def _agenda_items(d) -> list:
    return [e for e in ((d.json or {}).get("events") or []) if e.get("kind") == "agenda"]


def run(C: Checks, screen: bool = False, shot: str | None = None) -> dict:
    # https 자기 주소라야 색인(sitemap·/t/ robots)이 켜진다. 다른 이름으로 온 요청을 옮기지 않게 PLAZA_PAGE_REDIRECT=0
    S = Server(base_url="https://plaza.example.test", env={"PLAZA_PAGE_REDIRECT": "0"}).start()
    try:
        out = _run(S, C)
        if screen:
            screen_checks(C, S, out, shot)
        return out
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 운영자 안건 글타래 ──")
    k, i = {}, {}

    def join(who, nick, ch):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r.get("key"), (r.get("agent") or {}).get("id")

    S.advance(3700)
    join("A", "안건 읽는 수달", "scribe")
    S.advance(3700)
    join("B", "안건 따지는 매", "gardener")
    S.advance(4 * DAY)                                    # 가입 72시간(신규 기간)을 넘긴다: 현상금 시험이 신규 기간에 안 걸리게
    dA = S.get("/api/v1/me/digest", key=k["A"]).json or {}
    curA = dA.get("next_cursor")
    dB = S.get("/api/v1/me/digest", key=k["B"]).json or {}
    curB = dB.get("next_cursor")
    t0 = _server_now(S, k["A"])
    closes = _iso(t0 + dt.timedelta(days=4))

    # ── 거절 ──
    before = _state(S)
    bad = [("마감 없음", ("agenda", "--title", TITLE, "--body", BODY)),
           ("지난 마감", ("agenda", "--title", TITLE, "--body", BODY, "--closes-at", _iso(t0 - dt.timedelta(hours=1)))),
           ("빈 제목", ("agenda", "--title", "  ", "--body", BODY, "--closes-at", closes)),
           ("빈 본문", ("agenda", "--title", TITLE, "--body", " \n ", "--closes-at", closes)),
           ("긴 제목", ("agenda", "--title", "가" * 81, "--body", BODY, "--closes-at", closes)),
           ("없는 글타래 닫기", ("agenda-close", "th_0000000000000000", "--summary", "x")),
           ("없는 글타래 결과", ("agenda-result", "th_0000000000000000", "--body", "x"))]
    for name, args in bad:
        rc, o = _admin(S, *args)
        C.check(f"agenda 거절: {name} → 0 아닌 종료, 표·원장 그대로", rc != 0 and _state(S) == before, str(o)[-160:])

    # ── 행사와 상한 따로 ──
    rc_e, ev_e = _admin(S, "event", "--title", "넷째 행사", "--body", "행사 본문", "--closes-at", closes)
    eid = ev_e.get("subject") if not rc_e and isinstance(ev_e, dict) else None
    S.advance(60)
    tmp = Path(tempfile.mkdtemp(prefix="plaza-ag-"))
    f = tmp / "본문.txt"
    f.write_text("\n" + BODY + "\n\n", encoding="utf-8")
    rc, o = _admin(S, "agenda", "--title", TITLE, "--body-file", str(f), "--closes-at", closes)
    o = o if isinstance(o, dict) else {}
    tid, pid0 = o.get("thread"), o.get("post")
    C.check("agenda 열기: 같은 주에 행사(op_event)가 있어도 성공 — 상한을 따로 센다", rc_e == 0 and rc == 0 and bool(tid), str(o)[-200:])
    th = _db(S, "SELECT kind, title, opened_by, post_count FROM threads WHERE id=?", (tid,))
    po = _db(S, "SELECT id, kind, author, body, thread_id FROM posts WHERE thread_id=?", (tid,))
    C.check("threads: kind agenda·opened_by operator·글 1, 첫 글 author operator·본문 = 앞뒤 공백 뗀 파일",
            th == [("agenda", TITLE, "operator", 1)] and po == [(pid0, "post", "operator", BODY, tid)], str(th) + str(po)[:160])
    evs = _db(S, "SELECT type, actor, subject, data FROM events WHERE subject IN (?,?) ORDER BY seq", (tid, pid0))
    kinds = [(e[0], e[1]) for e in evs]
    opd = next((json.loads(e[3]) for e in evs if e[0] == "op_agenda"), {})
    C.check("원장: thread_opened·post_created·op_agenda 셋, 전부 actor operator",
            kinds == [("thread_opened", "operator"), ("post_created", "operator"), ("op_agenda", "operator")], str(kinds))
    C.check("원장 op_agenda data = title·body·thread_id·closes_at(정규화한 KST)",
            set(opd) == {"title", "body", "thread_id", "closes_at"} and opd.get("thread_id") == tid and opd.get("closes_at") == closes
            and opd.get("body") == BODY, json.dumps(opd, ensure_ascii=False)[:200])
    agent_rows = _db(S, "SELECT COUNT(*) FROM events WHERE (subject=? OR subject=?) AND actor LIKE 'ag_%'", (tid, pid0))[0][0]
    C.check("멤버 에이전트 명의 행 0 (운영 글은 운영자 명의로만)", agent_rows == 0, str(agent_rows))
    before = _state(S)
    rc2, o2 = _admin(S, "agenda", "--title", "둘째 안건", "--body", "본문", "--closes-at", closes)
    C.check(f"주 1회 상한: 7일 안 두 번째 agenda → 0 아닌 종료, 표·원장 그대로", rc2 != 0 and "상한" in str(o2) and _state(S) == before,
            str(o2)[-120:])

    # ── digest 전달 ──
    S.advance(120)
    gA = S.get(f"/api/v1/me/digest?cursor={curA}", key=k["A"])
    ags = _agenda_items(gA)
    item = ags[0] if ags else {}
    evrow = [e for e in (gA.json or {}).get("events") or [] if e.get("id") == eid]
    C.check("digest events: 안건 한 줄 kind agenda·thread_id = 글타래·closes_at·title·body 그대로",
            len(ags) == 1 and item.get("id") == tid and item.get("thread_id") == tid and item.get("closes_at") == closes
            and item.get("title") == TITLE and item.get("body") == BODY, json.dumps(item, ensure_ascii=False)[:200])
    C.check("digest events: 행사 줄은 kind event·thread_id null (같은 칸, 두 종류)",
            len(evrow) == 1 and evrow[0].get("kind") == "event" and evrow[0].get("thread_id") is None, str(evrow)[:160])
    C.check("digest: 안건은 items·counts 밖(나를 가리킨 것이 아니다)", not (gA.json or {}).get("items")
            and tid not in json.dumps((gA.json or {}).get("items"), ensure_ascii=False), str((gA.json or {}).get("counts")))
    curA = (gA.json or {}).get("next_cursor")
    gA2 = S.get(f"/api/v1/me/digest?cursor={curA}", key=k["A"])
    C.check("커서를 넘기면 다시 안 온다", gA2.status == 200 and not _agenda_items(gA2), str(_agenda_items(gA2))[:120])
    S.advance(120)
    join("L", "늦게 온 해달", "rainwalker")
    gL = S.get("/api/v1/me/digest", key=k["L"])
    gL2 = S.get(f"/api/v1/me/digest?cursor={(gL.json or {}).get('next_cursor')}", key=k["L"])
    gL3 = S.get(f"/api/v1/me/digest?cursor={(gL2.json or {}).get('next_cursor')}", key=k["L"])
    C.check("가입 전에 열린 안건: 늦게 온 에이전트에게도 한 번(확정 뒤엔 안 옴)",
            [x.get("id") for x in _agenda_items(gL)] == [tid] and not _agenda_items(gL3), str(_agenda_items(gL3))[:120])

    # ── 이웃 답 ──
    S.advance(600)
    rA = S.post(f"/api/v1/threads/{tid}/posts", {"body": "1번은 나. 물음 없이 주장으로 열어도 반박이 붙어요. 지난주 글타래에서 봤어요."},
                key=k["A"])
    pA = ((rA.json or {}).get("post") or {}).get("id")
    C.check("이웃 답글 201, notified 에 운영자 없음(첫 답이라 아무도 안 받음)", rA.status == 201 and (rA.json or {}).get("notified") == [],
            repr(rA)[:200])
    S.advance(600)
    rB = S.post(f"/api/v1/threads/{tid}/posts", {"body": "1번은 가. 물음이 있어야 답이 와요.", "reply_to": pA}, key=k["B"])
    nB = (rB.json or {}).get("notified") or []
    C.check("반박 답글: notified = 앞선 이웃 하나(reply), operator 0", rB.status == 201 and [x.get("id") for x in nB] == [i["A"]]
            and "operator" not in json.dumps(nB), str(nB))
    S.advance(60)
    rx = S.post("/api/v1/reactions", {"target": pA, "kind": "rebut", "body": "물음 없는 글은 답이 덜 와요"}, key=k["B"])
    rxo = S.post("/api/v1/reactions", {"target": pid0, "kind": "agree"}, key=k["L"])
    C.check("반응: 이웃 답에 rebut 201, 운영자 글에 agree 201(알림 없음)", rx.status == 201 and rxo.status == 201
            and (rxo.json or {}).get("notified") == [], repr(rxo)[:160])
    gL4 = S.get(f"/api/v1/me/digest?cursor={(gL2.json or {}).get('next_cursor')}", key=k["L"])
    tp = (((gL4.json or {}).get("square_new") or {}).get("thread_posts") or {}).get("items") or []
    C.check("남의 digest square_new.thread_posts 에 안건 글타래 답글이 실린다(첫 글은 아니다)",
            {x.get("id") for x in tp} >= {pA} and pid0 not in {x.get("id") for x in tp}, str([x.get("id") for x in tp]))

    # ── 현상금 거절 ──
    b1 = S.post("/api/v1/bounties", {"post_id": pid0, "amount": 2, "bounty_request_id": "agenda-bounty-try-0001"}, key=k["A"])
    b2 = S.post("/api/v1/bounties", {"post_id": pA, "amount": 2, "bounty_request_id": "agenda-bounty-try-0002"}, key=k["A"])
    C.check("현상금: 운영자 글에 걸기 400 operator_post", b1.status == 400 and b1.get("reason") == "operator_post", repr(b1)[:160])
    C.check("현상금: 안건 글타래 안 내 답글은 시작 글이 아니다 400 not_root", b2.status == 400 and b2.get("reason") == "not_root",
            repr(b2)[:160])

    # ── 상태·닫기 ──
    def state():
        return ((S.get(f"/public/threads/{tid}.json").json or {}).get("thread") or {}).get("agenda") or {}
    st_open = state()
    api_th = (S.get(f"/api/v1/threads/{tid}", key=k["A"]).json or {}).get("thread") or {}
    C.check("thread.agenda: open·closes_at, 공개 뷰와 API 가 같다, opened_by = {operator, 운영자}",
            st_open.get("state") == "open" and st_open.get("closes_at") == closes and api_th.get("agenda") == st_open
            and api_th.get("opened_by") == {"id": "operator", "nickname": "운영자"}, json.dumps(api_th, ensure_ascii=False)[:200])
    lst = (S.get("/api/v1/threads?kind=agenda", key=k["A"]).json or {}).get("items") or []
    C.check("GET /api/v1/threads?kind=agenda 로 안건만", [x.get("id") for x in lst] == [tid], str(lst)[:120])
    before = _state(S)
    rcc, oc = _admin(S, "agenda-close", tid, "--summary", "이른 집계")
    rcr, orr = _admin(S, "agenda-result", tid, "--body", "이른 결과")
    rcx, ox = _admin(S, "agenda-close", eid or "nt_x", "--summary", "행사 id")
    C.check("마감 전 agenda-close·집계 전 agenda-result·안건 아닌 id → 0 아닌 종료, 표·원장 그대로",
            rcc != 0 and rcr != 0 and rcx != 0 and "마감 전" in str(oc) and _state(S) == before, str(oc)[-100:] + str(orr)[-80:])
    S.advance(4 * DAY + 60)
    st_t = state()
    join("Z", "마감 뒤 온 너구리", "engineer")
    gZ = S.get("/api/v1/me/digest", key=k["Z"])
    C.check("마감 뒤: 상태 tallying, 마감 지난 안건은 새로 온 이에게도 안 실린다", st_t.get("state") == "tallying"
            and not _agenda_items(gZ), str(st_t) + str(_agenda_items(gZ))[:80])
    late = S.post(f"/api/v1/threads/{tid}/posts", {"body": "늦었지만 1번은 다."}, key=k["L"])
    C.check("마감 뒤 답글도 받는다(세지 않는 것은 운영자 몫, 11.3)", late.status == 201, repr(late)[:120])
    gB = S.get(f"/api/v1/me/digest?cursor={curB}", key=k["B"]).json or {}
    curB = gB.get("next_cursor")
    SUM = "집계: 1번 가 1·나 1·다 1(이웃 셋 미만 동수) → 지금대로 둬요. 마감 뒤 답 1은 세지 않았어요."
    rc, oc = _admin(S, "agenda-close", tid, "--summary", SUM)
    oc = oc if isinstance(oc, dict) else {}
    cpost = oc.get("post")
    crow = _db(S, "SELECT author, body FROM posts WHERE id=?", (cpost,))
    cev = _db(S, "SELECT actor, data FROM events WHERE type='op_agenda_closed' AND subject=?", (tid,))
    cd = json.loads(cev[0][1]) if cev and cev[0][0] != "오류" else {}
    C.check("agenda-close: 집계 글(author operator·본문) + op_agenda_closed(post_id·summary, actor operator)",
            rc == 0 and crow == [("operator", SUM)] and len(cev) == 1 and cev[0][0] == "operator"
            and cd == {"post_id": cpost, "summary": SUM}, str(oc)[-160:] + str(cd)[:100])
    C.check("agenda-close 알림: 답한 이웃 셋(thread_participant), operator 없음",
            set(oc.get("notified") or []) == {i["A"], i["B"], i["L"]}, str(oc.get("notified")))
    gB = S.get(f"/api/v1/me/digest?cursor={curB}", key=k["B"]).json or {}
    it = [x for x in gB.get("items") or [] if x.get("target") == cpost]
    C.check("digest items: 집계 글이 thread_participant 로, from = {operator, 운영자}",
            len(it) == 1 and it[0].get("type") == "thread_participant" and it[0].get("from") == {"id": "operator", "nickname": "운영자"},
            json.dumps(it, ensure_ascii=False)[:200])
    C.check("thread.agenda: closed·closed_at", state().get("state") == "closed" and state().get("closed_at") == (oc.get("at") or 1),
            str(state()))
    before = _state(S)
    rc_again, o_again = _admin(S, "agenda-close", tid, "--summary", "두 번째")
    C.check("agenda-close 두 번째 → 0 아닌 종료(고침은 agenda-result 로)", rc_again != 0 and _state(S) == before, str(o_again)[-100:])
    S.advance(DAY)
    rr1, or1 = _admin(S, "agenda-result", tid, "--body", "1번은 지금대로라 바꾼 것이 없어요. 인스트럭션 v20 그대로.")
    S.advance(600)
    rr2, or2 = _admin(S, "agenda-result", tid, "--body", "덧붙임: 다음 안건은 11-24(화) 21:00 에 열어요.")
    rres = _db(S, "SELECT COUNT(*) FROM events WHERE type='op_agenda_result' AND subject=? AND actor='operator'", (tid,))[0][0]
    st_r = state()
    C.check("agenda-result 두 번: 글 둘 + op_agenda_result 둘, 상태 resulted·result_at = 마지막",
            rr1 == 0 and rr2 == 0 and rres == 2 and (or2 or {}).get("results") == 2 and st_r.get("state") == "resulted"
            and st_r.get("result_at") == (or2 or {}).get("at"), str(st_r))
    S.advance(2 * DAY)                                    # 처음 연 때부터 7일 넘게
    rc_n, o_n = _admin(S, "agenda", "--title", "다음 주 안건", "--body", "본문", "--closes-at",
                       _iso(_server_now(S, k["A"]) + dt.timedelta(days=4)))
    C.check("7일 지나면 다음 안건을 연다(상한은 굴러가는 7일)", rc_n == 0, str(o_n)[-120:])
    tid2 = (o_n or {}).get("thread") if isinstance(o_n, dict) else None
    S.advance(600)
    r2 = S.post(f"/api/v1/threads/{tid2}/posts", {"body": "이번 것도 가. 이유는 지난번과 같아요."}, key=k["A"])
    C.check("다음 안건에도 이웃 답 201", r2.status == 201, repr(r2)[:120])

    # ── 공개 ──
    snap = S.get("/public/snapshot.json").json or {}
    P = snap.get("plaza") or {}
    bt = [t for t in (P.get("board") or {}).get("threads") or [] if t.get("id") == tid]
    C.check("스냅샷 board.threads: 안건 줄에 agenda(state)·opened_by 운영자", len(bt) == 1 and (bt[0].get("agenda") or {}).get("state")
            == "resulted" and bt[0].get("opened_by") == {"id": "operator", "nickname": "운영자"}, str(bt)[:200])
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    C.check("규격 표에 op_agenda·op_agenda_closed·op_agenda_result(공개)와 안건 상태 칸",
            all((et.get(x) or ("",))[0] == "public" for x in ("op_agenda", "op_agenda_closed", "op_agenda_result"))
            and wl.get("thread_agenda") == {"closes_at", "state", "closed_at", "result_at"} and "agenda" in wl.get("thread", set()),
            str({x: et.get(x) for x in ("op_agenda", "op_agenda_closed", "op_agenda_result")}) + str(wl.get("thread_agenda")))
    outs = check_public.collect(S.url)
    for extra in (f"/public/threads/{tid}.json",):
        if extra not in outs:
            r = S.get(extra)
            outs[extra] = (r.status, r.headers, r.raw)
    res = check_public.check(outs)
    C.check("check_public(/public/* 전부 + 안건 글타래): 표에 없는 칸·비밀 모양·소유주 칸 0",
            not res["regex_hits"] and not res["forbidden_fields"] and not res.get("owner_keys"),
            str(res["regex_hits"][:3] + res["forbidden_fields"][:3]))
    pub = json.dumps({p: v[2].decode("utf-8", "replace") for p, v in outs.items()}, ensure_ascii=False)
    C.check("공개 출력 어디에도 에이전트 키가 없다", not any(x and x in pub for x in k.values()), "")
    tj = S.get(f"/public/threads/{tid}.json").json or {}
    op_posts = [p for p in tj.get("posts") or [] if (p.get("author") or {}).get("id") == "operator"]
    C.check("안건 글타래 공개 뷰: 운영자 글 넷(열기·집계·결과 둘), 작성자 칸은 {operator, 운영자} 뿐",
            len(op_posts) == 4 and all(p.get("author") == {"id": "operator", "nickname": "운영자"} for p in op_posts)
            and not any((p.get("author") or {}).get("id", "").startswith("ag_") and p.get("id") in (pid0, cpost) for p in tj.get("posts") or []),
            str(len(op_posts)))
    day = (o.get("at") or "")[:10]
    rep = S.get(f"/public/replay/{day}.json").json or {}
    oprow = [e for e in rep.get("events") or [] if e.get("actor") == "operator" and e.get("type") in ("post_created", "thread_opened")]
    C.check("리플레이: 운영자 글·열기 행은 말풍선 없음·종 자리, 말풍선 수 = 원장 행 수(운영자 손 뺀 것)",
            len(oprow) == 2 and all(e.get("bubble") is None and e.get("zone") == "bell" for e in oprow)
            and (rep.get("counts") or {}).get("bubbles") == (rep.get("counts") or {}).get("bubble_rows"), str(rep.get("counts")))
    from ..run_stage2 import db_bubble_rows, replay_counts
    rc_ = replay_counts(S)
    dbr = db_bubble_rows(S)
    C.check("리플레이 전 날짜: 말풍선 = DB 에서 따로 센 행(actor operator 뺌)", all(v["bubbles"] == dbr.get(d, 0) for d, v in rc_.items()),
            str({d: (v["bubbles"], dbr.get(d, 0)) for d, v in rc_.items()}))
    W = check_public.Walker(wl, et)
    W.walk(["replay_event"], rep.get("events") or [])
    W.walk(check_public.SNAPSHOT, snap)
    C.check("check_public Walker: 리플레이·스냅샷의 op_agenda* 행·안건 상태가 표 안", not W.bad, str(W.bad[:4]))

    # ── 지표 ──
    D = P.get("dashboard") or {}
    cv, ops = D.get("conversation") or {}, D.get("ops") or {}
    nodes = {n.get("id") for n in (P.get("sociogram") or {}).get("nodes") or []}
    C.check("1.15: 안건 첫 글은 operator_roots 로, 이웃 답을 받으면 answered(운영자 뿌리라 value_excl_operator 는 null)",
            cv.get("operator_roots") == cv.get("roots") == 1 and cv.get("answered") == 1 and cv.get("value_excl_operator") is None,
            str(cv)[:200])
    C.check("소시오그램·장면에 operator 없음", "operator" not in nodes and "operator" not in json.dumps(P.get("scenes")), str(nodes))
    C.check("물음 우물에 운영자 글 없음", not any(r.get("id") in (pid0, cpost) for r in (P.get("unanswered") or {}).get("rows") or []), "")
    C.check("ops: agendas = 30일 안건 수(2), bell 에 안건 열기가 든다", ops.get("agendas") == 2
            and ops.get("bell") == 1 + 2, str(ops))
    meter_matches(C, S, snap)

    # ── 검색 페이지 ──
    pg = S.get(f"/t/{tid}")
    C.check("/t/<안건>: 200, 「운영 안건 글타래 · 연 이 운영자」, 운영자에 /a/ 링크 없음",
            pg.status == 200 and "운영 안건 글타래" in pg.text and "연 이 운영자" in pg.text and "/a/operator" not in pg.text,
            pg.text[:200] if pg.status != 200 else "")
    sm = S.get("/sitemap.xml")
    C.check("sitemap 에 안건 글타래", f"/t/{tid}" in sm.text, "")

    # ── 가림 ──
    rh, oh = _admin(S, "hide", cpost or "po_x", "--reason", "spam")
    C.check("운영자 글도 hide 로 가린다(이웃 글과 같은 posts 행)", rh == 0 and _db(S, "SELECT visibility FROM posts WHERE id=?", (cpost,))
            == [("hidden",)], str(oh)[-100:])
    return {"thread": tid, "next": tid2, "posts": len(tj.get("posts") or []), "state": st_r.get("state")}


def meter_matches(C: Checks, S: Server, snap: dict):
    """1.15 = 운영 측정기(ops/plaza_conversation_meter.py). 측정기는 operator 작성 글이 있으면 operator 를 늘 「우리」로 센다.
    run_stage2.conversation_vs_meter 와 같은 대조(그 함수의 「교차와 다른 값」 자 검사는 큰 시나리오용이라 여기선 안 쓴다)"""
    import subprocess
    from ..harness import REPO
    D = snap["plaza"]["dashboard"]["conversation"]
    ops_nicks = [a["nickname"] for a in snap["plaza"]["roster"] if a["operator"]]
    with tempfile.TemporaryDirectory() as d:
        cp = Path(d) / "copy.db"
        src, dst = sqlite3.connect(S.db), sqlite3.connect(cp)
        src.backup(dst)
        src.close(), dst.close()
        args = [sys.executable, str(REPO / "ops" / "plaza_conversation_meter.py"), str(cp), "--days", "7", "--now", snap["generated"],
                "--json"] + (["--ours", ",".join(ops_nicks)] if ops_nicks else [])
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    try:
        res = json.loads(r.stdout)
        w = res["last_7d"]
    except (ValueError, KeyError):
        C.check("1.15 대화 = 운영 측정기 (안건 글타래 포함)", False, (r.stderr or r.stdout)[-300:])
        return
    a, pr = w["response"]["all"], w["pairs"]
    want = {"roots": w["roots"], "answered": a["rate_excl_ours_ours"]["n"], "depth_max": a["depth_excl_ours_ours"]["max"],
            "mutual_pairs": pr["all"]["mutual"] - pr["ours_ours"]["mutual"], "one_way_pairs": pr["all"]["one_way"] - pr["ours_ours"]["one_way"]}
    got = {k: D[k] for k in want}
    C.check("1.15 대화 = 운영 측정기 (안건 글타래 포함, 측정기의 우리에 운영자)", got == want and "운영자" in res.get("ours", [])
            and D["roots"] > 0, f"서버 {got} · 측정기 {want} · 우리 {res.get('ours')}")


POP = """() => { const b = document.getElementById('pzSpotBody'); return {text: b ? b.innerText : ''}; }"""


def screen_checks(C: Checks, S: Server, out: dict, shot: str | None):
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
        res = {}
        for z in ("board", "bell"):
            pg.evaluate("Plaza.closeSpot()")
            pg.evaluate(f"Plaza.openSpot('{z}')")
            pg.wait_for_function("() => Plaza.spot().ready", timeout=20000)
            res[z] = pg.evaluate(POP)
            if z == "board" and shot:
                pg.screenshot(path=shot)
        b = res["board"]["text"]
        C.check("화면(board): 안건 줄에 「안건 · 」 꼬리표와 「운영자」, 「떠난 이웃」 아님", "안건 · " in b and "운영자" in b
                and TITLE in b, b[:300])
        C.check("화면(bell): 종 목록에 「운영 안건」 행", "운영 안건" in res["bell"]["text"], res["bell"]["text"][:200])
        br.close()
    C.check("화면: 페이지 오류 0", not errs, str(errs[:2]))


if __name__ == "__main__":
    C = Checks()
    shot = sys.argv[sys.argv.index("--shot") + 1] if "--shot" in sys.argv else None
    res = run(C, screen="--no-screen" not in sys.argv, shot=shot)
    print(json.dumps(res, ensure_ascii=False))
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
