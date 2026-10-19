"""행사 결과판과 행사 우편함 (api.md 9절·10.1). 새 임시 서버에서 HTTP 와 plaza-admin 으로만 잰다.

  python3 -m server.tests.event_board

- 결과판 상태는 시계로 바뀐다: 마감 전 open → 마감이 지나면 결과가 없어도 tallying(발표 예정 시각과 함께) → 결과를 올리면 announced
- 발표 예정 시각: 안 정하면 마감 + 7일, announce-by 로 고친다
- 결과는 마감 뒤에만, 한 번(고치기는 --replace, 원장에 한 행 더). 제출 수를 안 주면 우편함 kind event 의 보낸 이 수
- 골드 지급 줄은 받은 이 수·합계만(에이전트 id·닉네임이 결과판에 안 나온다). 제출이 3 미만이면 운영자 출력에 경고
- 우편함 kind event: 열린 행사에 붙이고 「행사 제출 접수, 결과는 ~까지」, 열린 행사가 없으면 받되 그렇다고 말한다.
  other·bug 는 예전 응답 그대로(1차 행사 제출 경로)
- 스냅샷 plaza.event_board = /public/events.json 의 최근 것
옛 판에 대 보면 정상 경로가 실패해야 한다."""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys

from server.plaza.util import iso, now

from .gold import _admin
from .harness import REPO, Checks, Server
from .scenario import jrid


def _board(S) -> list:
    return (S.get("/public/events.json").json or {}).get("events")


def _admin_err(S, *args):
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    return out.returncode, out.stdout, out.stderr


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 행사 결과판·행사 우편함 ──")
    k, ids = {}, {}
    for who, nick, ch in (("M", "예측하는 물총새", "scribe"), ("O", "옆집 두루미", "gardener")):
        S.advance(3700)
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], ids[who] = r["key"], r["agent"]["id"]
    C.check("결과판: 행사가 없으면 빈 목록, 스냅샷 event_board 도 빈 목록", _board(S) == [] and
            ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("event_board") == [], str(_board(S)))

    r = S.post("/api/v1/mailbox", {"kind": "event", "body": "내 생각: 그렇다"}, key=k["O"])
    C.check("우편함 event: 열린 행사가 없어도 201, event null, 「받는 행사가 없다」", r.status == 201 and r.get("event") is None
            and "받는 행사가 없다" in (r.get("note") or ""), repr(r)[:300])

    S.advance(60)
    os.environ["PLAZA_CLOCK_FILE"] = str(S.clock)            # 이 과정의 now() 도 서버 시계를 따른다
    closes = now() + dt.timedelta(days=2)
    rc, ev = _admin(S, "event", "--title", "같은 이웃일까", "--body", "우편함 event 로 내 주세요", "--closes-at", iso(closes))
    nid = ev["subject"] if not rc else None
    b = _board(S) or [{}]
    it = b[0]
    C.check("결과판: 마감 전 status open, closes_at, 발표 예정 = 마감 + 7일, 결과·골드 null",
            len(b) == 1 and it.get("id") == nid and it.get("status") == "open" and it.get("closes_at") == iso(closes)
            and it.get("announce_by") == iso(closes + dt.timedelta(days=7)) and it.get("result") is None
            and it.get("gold") is None, str(it))
    C.check("결과판 줄의 칸은 고정 여덟", set(it) == {"id", "title", "opened_at", "closes_at", "status", "announce_by",
                                                "result", "gold"}, str(sorted(it)))

    r = S.post("/api/v1/mailbox", {"kind": "event", "body": "내 생각: 그렇다 / 다수: 그렇다"}, key=k["M"])
    C.check("우편함 event: 201, 열린 행사에 붙고 「행사 제출 접수, 결과는 <발표 예정> 까지」",
            r.status == 201 and (r.get("event") or {}).get("id") == nid and "행사 제출 접수" in (r.get("note") or "")
            and (r.get("event") or {}).get("announce_by") in (r.get("note") or ""), repr(r)[:300])
    c = sqlite3.connect(S.db)
    try:
        row = c.execute("SELECT kind, notice_id FROM mailbox WHERE id=?", (r.get("mailbox_id"),)).fetchone()
    except sqlite3.OperationalError as e:                  # 옛 판: 칸이 없다
        row = str(e)
    c.close()
    C.check("우편함 event: 서버 행에 kind event·행사 id", row == ("event", nid), str(row))
    r = S.post("/api/v1/mailbox", {"kind": "other", "body": "내 생각: 아니다 / 다수: 그렇다"}, key=k["O"])
    C.check("우편함 other: 예전 응답 그대로(행사 칸 없음) — 1차 제출 경로", r.status == 201 and "event" not in (r.json or {})
            and r.get("note") == "운영자만 읽는다. 답장 경로는 없다. 고쳐지면 인스트럭션 판이 오른다", repr(r)[:300])
    r = S.post("/api/v1/mailbox", {"kind": "bug", "body": "오류 신고"}, key=k["O"])
    C.check("우편함 bug: 예전 응답 그대로", r.status == 201 and "event" not in (r.json or {}), repr(r)[:200])
    r = S.post("/api/v1/mailbox", {"kind": "party", "body": "x"}, key=k["O"])
    C.check("우편함 모르는 kind 는 400 bad_value", r.status == 400 and r.get("error") == "bad_value", repr(r)[:200])

    rc, out, err = _admin_err(S, "event-result", nid, "--summary", "이른 결과")
    C.check("event-result: 마감 전엔 거절", rc != 0 and "마감 전" in err, err[-200:])

    S.advance(2 * 86400 + 60)
    it = (_board(S) or [{}])[0]
    C.check("결과판: 마감이 지나면 결과 없이도 status tallying·발표 예정 시각", it.get("status") == "tallying"
            and it.get("announce_by") == iso(closes + dt.timedelta(days=7)) and it.get("result") is None, str(it))
    snap = ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("event_board") or [{}]
    C.check("스냅샷 event_board 가 같은 값", snap[0] == it, str(snap[0]))
    r = S.post("/api/v1/mailbox", {"kind": "event", "body": "늦은 제출"}, key=k["O"])
    C.check("우편함 event: 마감 뒤엔 event null·「받는 행사가 없다」", r.status == 201 and r.get("event") is None
            and "받는 행사가 없다" in (r.get("note") or ""), repr(r)[:200])
    dg = S.get("/api/v1/me/digest", key=k["O"]).json or {}
    C.check("digest events: 마감 지난 행사는 안 싣는다(그대로)", dg.get("events") == [], str(dg.get("events")))

    ab = now() + dt.timedelta(days=3)
    rc, out = _admin(S, "announce-by", nid, iso(ab))
    it = (_board(S) or [{}])[0]
    C.check("announce-by: 발표 예정 시각을 고치고 전후 값을 낸다", not rc and out.get("after") == iso(ab)
            and it.get("announce_by") == iso(ab), f"{out} {it}")

    rc, out = _admin(S, "gold-award", ids["M"], "10", "--reason", "다수 예측 적중", "--notice", nid)
    it = (_board(S) or [{}])[0]
    C.check("결과판 골드: 받은 이 수·합계만 {recipients 1, total 10}", it.get("gold") == {"recipients": 1, "total": 10}, str(it))
    blob = json.dumps(S.get("/public/events.json").json, ensure_ascii=False)
    C.check("결과판에 받은 이 id·닉네임이 안 나온다", ids["M"] not in blob and "물총새" not in blob, blob[:200])

    rc, out, err = _admin_err(S, "event-result", nid, "--summary", "그렇다 1, 아니다 1. 다수는 동수라 예측한 이웃 모두 맞힘")
    res = json.loads(out) if not rc else {}
    C.check("event-result: 제출 수를 안 주면 우편함 kind event 보낸 이 수(마감 전 1명)", not rc and res.get("submissions") == 1,
            f"{out} {err[-200:]}")
    C.check("event-result: 제출 3 미만이면 경고(지급 줄로 드러남)", "경고" in err and "드러날 수 있다" in err, err[-200:])
    it = (_board(S) or [{}])[0]
    C.check("결과판: status announced, 결과(요약·제출 수·발표 시각), 발표 예정은 null", it.get("status") == "announced"
            and (it.get("result") or {}).get("submissions") == 1 and bool((it.get("result") or {}).get("announced_at"))
            and it.get("announce_by") is None, str(it))
    rc, out, err = _admin_err(S, "event-result", nid, "--summary", "다시")
    C.check("event-result: 두 번째는 --replace 없이 거절", rc != 0 and "--replace" in err, err[-200:])
    rc, out, err = _admin_err(S, "event-result", nid, "--summary", "고친 결과", "--submissions", "2", "--replace")
    it = (_board(S) or [{}])[0]
    C.check("event-result --replace: 고치고 원장에 한 행 더", rc == 0 and (it.get("result") or {}).get("summary") == "고친 결과"
            and (it.get("result") or {}).get("submissions") == 2, f"{out} {it}")

    evs = []
    for d in (S.get("/public/replay/index.json").json or {}).get("dates", []):
        evs += [e for e in (S.get(f"/public/replay/{d['date']}.json").json or {}).get("events", [])
                if e.get("type") == "op_event_result"]
    C.check("리플레이: op_event_result 두 행, data 는 summary·submissions 만", len(evs) == 2
            and all(set(e.get("data", {})) == {"summary", "submissions"} and e.get("subject") == nid for e in evs),
            json.dumps(evs, ensure_ascii=False)[:300])
    last = (((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("bell") or {}).get("last") or {}
    C.check("결과 발표는 종을 안 울린다 (마지막 종 = 행사)", last.get("type") == "op_event", str(last))
    agg = ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("dashboard", {}).get("ops", {})
    C.check("우편함 공개 집계는 행사 제출(event 3통)을 빼고 센다 — other·bug 2", agg.get("mailbox") == 2, str(agg))
    return {"notice": nid}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
