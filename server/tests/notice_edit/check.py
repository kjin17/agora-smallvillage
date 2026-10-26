"""공지 고치기 plaza-admin notice-edit (api.md 11.2, 2026-10-26). 새 임시 서버에서 plaza-admin 과 HTTP 로만 잰다.

  python3 -m server.tests.notice_edit.check [--no-screen] [--shot <png 경로>]

기대값은 출력을 믿지 않고 DB(notices·events)와 직접 계산한 sha256 으로 따로 잰다.
- 거절: 없는 id·행사(op_event) id·바뀐 것 없음·빈 본문은 0 아닌 종료, notices·원장 그대로
- 고침: notices 본문(앞뒤 공백 뗌)·제목, 원장 op_notice_edit 한 행(옛·새 sha256 = 직접 계산), 처음 op_notice 행은 그대로(덧붙이기 전용)
- 공개: 스냅샷 board.pinned = 마지막 고침의 제목·본문, edited_at = 고침 시각. 옛 문구 0. 리플레이에 처음 행(옛 본문)과 고침 행 둘 다,
  고침 행 data 는 title·body·before_sha256·after_sha256 만. bell 셈은 안 늘어난다. check_public 통과, 자 검사(옛 본문 칸을 넣은 사본은 잡힌다)
- 다시 알리지 않음: 고친 뒤 에이전트 digest 어디에도 공지 id·새 본문이 없다
- 화면: 게시판·종 자리의 공지에 「고침 · 」, 리플레이 종 목록에 「운영 공지 고침」
옛 판(b05e3c3)에 대면 명령이 없어 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .. import check_public
from ..gold import _admin
from ..harness import Checks, Server
from ..scenario import jrid

OLD = ("골드는 광장 행사에서 받는 몫이에요.\n쓰는 곳\n- 부탁 보상: 부탁을 열 때 reward 칸에 골드를 걸어요.\n"
       "- 답례는 아직 후보: 이웃끼리 건네기. 정해지면 행사 글로 먼저 알려요.")
NEW = ("골드는 광장 행사에서 받는 몫이에요.\n쓰는 곳\n- 부탁 보상: 부탁을 열 때 reward 칸에 골드를 걸어요.\n"
       "- 이웃에게 건네기: 고마우면 POST /api/v1/gold/give 로 골드를 건네요(1~10, 24시간에 3번·20골드까지).\n")
NEW2 = NEW.strip() + "\n- 장부에는 건넴·건네받음 줄로 공개돼요."
STALE = "답례는 아직 후보"


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _db(S: Server, sql: str, args=()):
    c = sqlite3.connect(S.db)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error as e:
        return [("오류", str(e))]
    finally:
        c.close()


def _state(S):
    return (_db(S, "SELECT id, kind, title, body FROM notices ORDER BY id"),
            _db(S, "SELECT COUNT(*) FROM events")[0][0])


def _pinned(S) -> dict:
    snap = S.get("/public/snapshot.json").json or {}
    return ((snap.get("plaza") or {}).get("board") or {}).get("pinned") or {}


def _bell(S):
    return ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("bell", {}).get("count_30d")


def run(C: Checks, screen: bool = False, shot: str | None = None) -> dict:
    S = Server().start()
    try:
        out = _run(S, C)
        if screen:
            screen_checks(C, S, out, shot)
        return out
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 공지 고치기 ──")
    S.advance(3700)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "공지 읽는 수달", "character": "scribe", "public_ack": True})
    key = r.get("key")
    S.advance(60)                                          # 운영과 같은 순서: 행사 뒤에 공지(고정 칸은 가장 최근 것)
    rc, evt = _admin(S, "event", "--title", "둘째 행사", "--body", "행사 본문")
    eid = evt.get("subject") if not rc and isinstance(evt, dict) else None
    S.advance(60)
    rc, ev = _admin(S, "notice", "--title", "골드 안내", "--body", OLD)
    nid = ev.get("subject") if not rc and isinstance(ev, dict) else None
    S.advance(60)
    first = _db(S, "SELECT data FROM events WHERE type='op_notice' AND subject=?", (nid,))
    bell0 = _bell(S)
    dg0 = S.get("/api/v1/me/digest", key=key).json or {}
    cur = dg0.get("next_cursor")

    before = _state(S)
    tmp = Path(tempfile.mkdtemp(prefix="plaza-ne-"))
    f = tmp / "본문.txt"
    f.write_text("\n" + NEW + "\n\n", encoding="utf-8")       # 앞뒤 공백은 뗀다
    bad = [("없는 id", ("notice-edit", "nt_0000000000000000", "--body", "x")),
           ("행사 id", ("notice-edit", eid or "nt_x", "--body", "행사를 고치려 함")),
           ("바뀐 것 없음", ("notice-edit", nid or "nt_x", "--body", OLD)),
           ("빈 본문", ("notice-edit", nid or "nt_x", "--body", "  \n ")),
           ("본문 없음", ("notice-edit", nid or "nt_x"))]
    for name, args in bad:
        rc_b, o = _admin(S, *args)
        C.check(f"notice-edit 거절: {name} → 0 아닌 종료, notices·원장 그대로", rc_b != 0 and _state(S) == before,
                str(o)[-160:])

    S.advance(120)
    rc, o = _admin(S, "notice-edit", nid or "nt_x", "--body-file", str(f))
    o = o if isinstance(o, dict) else {}
    row = _db(S, "SELECT title, body FROM notices WHERE id=?", (nid,))
    edits = _db(S, "SELECT at, actor, data FROM events WHERE type='op_notice_edit' AND subject=?", (nid,))
    C.check("notice-edit --body-file: 성공, notices 본문 = 앞뒤 공백 뗀 새 본문, 제목 그대로",
            rc == 0 and row == [("골드 안내", NEW.strip())], str(o)[-200:] + " " + str(row)[:120])
    d = json.loads(edits[0][2]) if edits and edits[0][0] != "오류" else {}
    C.check("원장: op_notice_edit 한 행(actor operator), 옛·새 sha256 = 직접 계산, 출력과 같다",
            len(edits) == 1 and edits[0][1] == "operator" and d.get("before_sha256") == sha(OLD)
            and d.get("after_sha256") == sha(NEW.strip()) and o.get("before_sha256") == sha(OLD)
            and o.get("after_sha256") == sha(NEW.strip()) and o.get("after_chars") == len(NEW.strip()),
            json.dumps(d, ensure_ascii=False)[:200])
    C.check("원장 덧붙이기 전용: 처음 op_notice 행(옛 본문)은 그대로", _db(S, "SELECT data FROM events WHERE type='op_notice'"
            " AND subject=?", (nid,)) == first and STALE in (first[0][0] if first else ""), "")

    p = _pinned(S)
    C.check("스냅샷 board.pinned: 새 본문·제목 그대로·edited_at = 고침 시각, 옛 문구 0",
            p.get("body") == NEW.strip() and p.get("title") == "골드 안내" and p.get("edited_at") == (edits[0][0] if edits else 1)
            and STALE not in json.dumps(p, ensure_ascii=False), json.dumps(p, ensure_ascii=False)[:200])
    C.check("bell 셈: 고침은 종을 안 울린다", _bell(S) == bell0, f"{bell0} → {_bell(S)}")

    S.advance(120)
    rc2, o2 = _admin(S, "notice-edit", nid or "nt_x", "--body", NEW2, "--title", "골드 안내 (고침)")
    p2 = _pinned(S)
    edits = _db(S, "SELECT at FROM events WHERE type='op_notice_edit' AND subject=? ORDER BY seq", (nid,))
    C.check("두 번째 고침(--title): 고침 행 둘, pinned = 마지막 고침, edited_at 이 앞으로", rc2 == 0 and len(edits) == 2
            and p2.get("body") == NEW2 and p2.get("title") == "골드 안내 (고침)" and p2.get("edited_at") == edits[-1][0]
            and p2.get("at") == p.get("at"), json.dumps(p2, ensure_ascii=False)[:160])
    o2 = o2 if isinstance(o2, dict) else {}
    C.check("두 번째 고침의 before_sha256 = 첫 고침 뒤 본문", o2.get("before_sha256") == sha(NEW.strip()), str(o2)[:120])

    day = (p.get("at") or "")[:10]
    evs = [e for e in (S.get(f"/public/replay/{day}.json").json or {}).get("events", [])
           if e.get("subject") == nid]
    kinds = [e.get("type") for e in evs]
    ed = [e for e in evs if e.get("type") == "op_notice_edit"]
    C.check("리플레이: 처음 op_notice(옛 본문) + op_notice_edit 둘, 고침 data 칸은 title·body·before/after_sha256 만",
            kinds.count("op_notice") == 1 and len(ed) == 2
            and all(set(e.get("data", {})) == {"title", "body", "before_sha256", "after_sha256"} for e in ed),
            str(kinds))
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    W = check_public.Walker(wl, et)
    snap = S.get("/public/snapshot.json").json or {}
    W.walk(check_public.SNAPSHOT, snap)
    W.walk(["replay_event"], evs)
    C.check("check_public: 스냅샷·리플레이 통과 (규격 표에 op_notice_edit)", not W.bad and "op_notice_edit" in et, str(W.bad[:4]))
    probe = json.loads(json.dumps(evs))
    for e in probe:
        if e.get("type") == "op_notice_edit":
            e["data"]["before_body"] = OLD
    W2 = check_public.Walker(wl, et)
    W2.walk(["replay_event"], probe)
    C.check("자 검사: 고침 행에 옛 본문 칸을 넣은 사본은 check_public 이 잡는다", any("before_body" in b for b in W2.bad), str(W2.bad[:2]))
    outs = check_public.collect(S.url)
    res = check_public.check(outs)
    C.check("check_public 원문 검사(/public/* 전부): 비밀 모양 0 — 해시 두 칸 값은 long_hex 에서 빠진다",
            not res["regex_hits"] and not res["forbidden_fields"], str(res["regex_hits"][:3] + res["forbidden_fields"][:3]))
    path = f"/public/replay/{day}.json"
    st, h, raw = outs[path]
    planted = raw.decode("utf-8").replace('"title": "골드 안내 (고침)"', '"title": "' + sha(OLD) + '"', 1).encode("utf-8")
    res2 = check_public.check({path: (st, h, planted)})
    C.check("자 검사: 해시 칸 밖(제목)에 같은 64자 hex 를 넣은 사본은 long_hex 로 잡힌다",
            any("long_hex" in x for x in res2["regex_hits"]), str(res2["regex_hits"][:2]))

    dg = S.get(f"/api/v1/me/digest?cursor={cur}" if cur else "/api/v1/me/digest", key=key)
    raw = json.dumps(dg.json or {}, ensure_ascii=False)
    C.check("다시 알리지 않음: 고친 뒤 digest 어디에도 공지 id·새 본문이 없다", dg.status == 200 and (nid or "?") not in raw
            and "gold/give" not in raw, raw[:160])
    return {"notice": nid, "edits": len(edits), "after_sha256": sha(NEW2), "date": day}


POP = """() => { const b = document.getElementById('pzSpotBody'); const pin = b && b.querySelector('.pz-pin');
  return {pin: pin ? pin.innerText : null, text: b ? b.innerText : ''}; }"""


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
        for z in ("board", "bell"):
            pin = res[z]["pin"] or ""
            C.check(f"화면({z}): 고정 공지에 새 본문과 「고침 · 」, 옛 문구 0", "고침 · " in pin and "장부에는 건넴" in pin
                    and STALE not in pin, pin[-160:])
        C.check("화면(bell): 종 목록에 「운영 공지 고침」 행", "운영 공지 고침" in res["bell"]["text"], res["bell"]["text"][:200])
        br.close()
    C.check("화면: 페이지 오류 0", not errs, str(errs[:2]))


if __name__ == "__main__":
    C = Checks()
    shot = sys.argv[sys.argv.index("--shot") + 1] if "--shot" in sys.argv else None
    res = run(C, screen="--no-screen" not in sys.argv, shot=shot)
    print(json.dumps(res, ensure_ascii=False))
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
