"""골드 장부 (api.md 6.1·11절). 새 임시 서버에서 plaza-admin 과 HTTP 로만 잰다.

  python3 -m server.tests.gold

- gold-award 로 준 골드가 /api/v1/me·/api/v1/agents/{id}·/public/agents/{id}.json 에 같은 잔액·내역으로 나온다
- 차감(음수)은 받고, 잔액이 0 밑이 되는 차감·0·없는 에이전트·없는 공지 id 는 거절하고 장부도 원장도 그대로다
- 행마다 원장 op_gold 가 하나 남고, 공개 리플레이에 delta·reason·notice_id 만 나간다
- 남의 골드는 지급 대상에만 붙는다(다른 에이전트 잔액 0)
옛 판(칸이 없는 서버)에 대 보면 정상 경로가 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

from .harness import REPO, Checks, Server
from .scenario import jrid


def _admin(S: Server, *args) -> tuple[int, dict | str]:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        return out.returncode, out.stderr
    return 0, json.loads(out.stdout)


def _gold(d) -> dict:
    return (d.json or {}).get("gold") or {}


def _rows(S: Server) -> tuple[int, int]:
    c = sqlite3.connect(S.db)
    try:
        return (c.execute("SELECT COUNT(*) FROM gold_ledger").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM events WHERE type='op_gold'").fetchone()[0])
    except sqlite3.OperationalError:                 # 옛 판: 표가 없다
        return (-1, -1)
    finally:
        c.close()


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 골드 장부 ──")
    k, i = {}, {}
    for who, nick, ch in (("M", "골드 받는 물총새", "scribe"), ("O", "옆집 두루미", "gardener")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]
    S.advance(60)
    rc, ev = _admin(S, "event", "--title", "같은 이웃일까", "--body", "다수를 맞히면 10골드")
    nid = ev["subject"] if not rc else None

    g0 = S.get("/api/v1/me", key=k["M"])
    C.check("gold: 처음엔 잔액 0·내역 빈 목록 (칸은 늘 있다)", _gold(g0).get("balance") == 0 and _gold(g0).get("entries") == [],
            str(_gold(g0)))

    S.advance(60)
    rc, out = _admin(S, "gold-award", i["M"], "10", "--reason", "1차 행사 다수 예측 적중", "--notice", nid)
    C.check("gold-award: 10 지급, 전후 잔액을 출력", not rc and out.get("before") == 0 and out.get("after") == 10, str(out))
    S.advance(60)
    rc, out = _admin(S, "gold-award", i["M"], "-3", "--reason", "시험 차감")
    C.check("gold-award: 음수(차감)는 받는다 10 → 7", not rc and out.get("after") == 7, str(out))

    before = _rows(S)
    bad = [("잔액보다 큰 차감", ("gold-award", i["M"], "-8", "--reason", "너무 큼")),
           ("0", ("gold-award", i["M"], "0", "--reason", "영")),
           ("없는 에이전트", ("gold-award", "ag_0000000000000000", "5", "--reason", "없음")),
           ("없는 공지 id", ("gold-award", i["M"], "5", "--reason", "x", "--notice", "nt_0000000000000000")),
           ("빈 사유", ("gold-award", i["M"], "5", "--reason", "  "))]
    for name, args in bad:
        rc, out = _admin(S, *args)
        C.check(f"gold-award 거절: {name}", rc != 0, str(out)[:200])
    C.check("gold-award 거절은 장부·원장을 안 건드린다", _rows(S) == before, f"{before} → {_rows(S)}")
    C.check("gold: 장부 2행·원장 op_gold 2행", _rows(S) == (2, 2), str(_rows(S)))

    me = _gold(S.get("/api/v1/me", key=k["M"]))
    other = _gold(S.get(f"/api/v1/agents/{i['M']}", key=k["O"]))
    pub = _gold(S.get(f"/public/agents/{i['M']}.json"))
    C.check("gold: /api/v1/me 잔액 7, 내역 최근 순", me.get("balance") == 7 and
            [x.get("delta") for x in me.get("entries") or []] == [-3, 10], str(me))
    C.check("gold: 내역 행에 사유·공지 id·시각", (me.get("entries") or [{}, {}])[-1:] == [
        {"delta": 10, "kind": "award", "reason": "1차 행사 다수 예측 적중", "notice_id": nid, "request_id": None,
         "at": ((me.get("entries") or [{}, {}])[-1] or {}).get("at")}] and bool((me.get("entries") or [{}])[-1].get("at")),
            str(me.get("entries")))
    C.check("gold: 남이 본 /api/v1/agents/{id} · 관전자 /public/agents/{id}.json 이 같은 값", me == other == pub,
            f"{other} | {pub}")
    C.check("gold: 지급받지 않은 에이전트는 0", _gold(S.get(f"/public/agents/{i['O']}.json")).get("balance") == 0,
            str(_gold(S.get(f"/public/agents/{i['O']}.json"))))
    rc, rep = _admin(S, "gold")
    C.check("gold 조회: 에이전트별 잔액 목록", not rc and [(b["agent_id"], b["balance"]) for b in rep.get("balances", [])]
            == [(i["M"], 7)], str(rep))

    day = S.get("/public/replay/index.json")
    dates = [d["date"] for d in (day.json or {}).get("dates", [])]
    evs = []
    for d in dates:
        evs += [e for e in (S.get(f"/public/replay/{d}.json").json or {}).get("events", []) if e.get("type") == "op_gold"]
    C.check("gold: 공개 리플레이에 op_gold 두 행, data 는 delta·reason·notice_id 만",
            len(evs) == 2 and all(set(e.get("data", {})) == {"delta", "reason", "notice_id"} for e in evs)
            and {e.get("subject") for e in evs} == {i["M"]}, json.dumps(evs, ensure_ascii=False)[:300])
    snap = S.get("/public/snapshot.json").json or {}
    last = ((snap.get("plaza") or {}).get("bell") or {}).get("last") or {}
    C.check("gold: 골드는 종을 안 울린다 (마지막 종 = 행사)", last.get("type") == "op_event", str(last))
    return {"balance": me.get("balance")}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
