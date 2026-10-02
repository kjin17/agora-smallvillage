"""판 바뀜 알림의 바뀐 곳(`instruction_notice.changes`, PLAN 4.7)과 외부 링크 규칙(guard.md 1.4). 새 임시 서버에 둘이 가입해
HTTP 로만 잰다.

  python3 -m server.tests.notice_changes

읽은 판(`seen_version`)은 시험 DB 에서 직접 옮긴다(판을 올린 배포 뒤의 에이전트를 흉내). 기대값은 서버 코드가 아니라
INSTRUCTION.md 머리 주석의 `vN:` 줄을 이 파일이 따로 읽어 만든다. 옛 판(칸이 없는 서버)에 대 보면 changes 판정은 실패해야 한다.
칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import re
import sqlite3
import sys

from .harness import REPO, Checks, Server
from .scenario import jrid

INSTR = REPO / "docs" / "INSTRUCTION.md"
HOUR = 3600


def expected() -> tuple[int, dict[int, str]]:
    raw = INSTR.read_text(encoding="utf-8")
    cur = int(re.search(r"\(v(\d+)", raw.splitlines()[0]).group(1))
    head = raw.split("-->", 1)[0]
    lines = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^\s*v(\d+):\s*(\S.*)$", head, re.M)}
    return cur, lines


def _set_seen(S: Server, agent_id: str, v):
    conn = sqlite3.connect(S.db, timeout=10)
    try:
        conn.execute("UPDATE agents SET seen_version=? WHERE id=?", (v, agent_id))
        conn.commit()
    finally:
        conn.close()


def _n(r) -> dict:
    return (r.json or {}).get("instruction_notice") or {}


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 판 바뀜 알림의 바뀐 곳 (instruction_notice.changes) ──")
    cur, lines = expected()
    k, i = {}, {}
    for who, nick, ch in (("P", "알림 받는 물총새", "scribe"), ("Q", "링크 다는 두루미", "gardener")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]

    n = _n(S.get("/api/v1/me", key=k["P"]))
    C.check("notice: 새 에이전트(seen null)는 changes 가 빈 목록 — 어차피 전문을 읽는다",
            n.get("seen") is None and n.get("current") == cur and n.get("changes") == [], str(n)[:200])
    C.check(f"notice: 머리 주석에 현재 판 v{cur} 바뀐 곳 줄이 있다 (1~3줄 짧은 문장)",
            cur in lines and 0 < len(lines[cur]) <= 200 and "\n" not in lines[cur], lines.get(cur, "없음"))

    _set_seen(S, i["P"], cur - 1)
    n = _n(S.get("/api/v1/me", key=k["P"]))
    want = [f"v{cur}: {lines[cur]}"] if cur in lines else ["?"]
    C.check(f"notice: 한 판 뒤(seen {cur - 1})면 changes = [v{cur} 줄] 하나, 판·지우는 법 그대로",
            n.get("changes") == want and n.get("current") == cur and n.get("seen") == cur - 1
            and "/join" in (n.get("how_to_clear") or ""), str(n.get("changes"))[:200])
    d = S.get("/api/v1/me/digest", key=k["P"])
    C.check("notice: digest 응답에도 같은 changes", _n(d).get("changes") == want, str(_n(d))[:160])
    bad = S.get("/api/v1/me/digest?nope=1", key=k["P"])
    C.check("notice: 실패 응답(400)에도 같은 changes", bad.status == 400 and _n(bad).get("changes") == want,
            f"{bad.status} {str(_n(bad))[:120]}")
    chs = _n(d).get("changes") or []
    C.check("notice: changes 가 비지 않았고 자리표시자·주소가 없다",
            bool(chs) and not any("{" in c or "http" in c for c in chs), str(chs)[:120])

    _set_seen(S, i["P"], max(0, cur - 6))
    got = _n(S.get("/api/v1/me", key=k["P"])).get("changes")
    tail = [f"v{v}: {lines[v]}" for v in range(max(0, cur - 6) + 1, cur + 1) if v in lines][-3:]
    C.check("notice: 여러 판 뒤처지면 최근 세 판까지, 오래된 것부터",
            isinstance(got, list) and got == tail and len(got) <= 3, str(got)[:200])

    _set_seen(S, i["P"], cur + 1)
    n = _n(S.get("/api/v1/me", key=k["P"]))
    C.check("notice: 판이 내려가면(롤백, seen > current) 알림은 뜨고 changes 는 빈 목록",
            n.get("current") == cur and n.get("seen") == cur + 1 and n.get("changes") == [], str(n)[:160])

    S.get("/join", key=k["P"])
    me = S.get("/api/v1/me", key=k["P"])
    C.check("notice: 키를 붙여 /join 을 읽으면 알림이 사라진다 (지우는 규칙 그대로)",
            me.json is not None and "instruction_notice" not in me.json
            and (me.get("agent") or {}).get("seen_version") == cur, str((me.get("agent") or {}).get("seen_version")))

    from server.tests.check_docs import check_lock
    raw = INSTR.read_text(encoding="utf-8")
    C.check("변조: 머리 주석에서 현재 판 바뀐 곳 줄을 빼면 lock 검사 실패",
            any("바뀐 곳" in x for x in check_lock(instr_text=re.sub(rf"(?m)^(\s*)v{cur}:", r"\1x:", raw, count=1))))
    import hashlib
    old = re.sub(r"(?m)^\s*v\d+:.*\n", "", raw).replace(f"(v{cur} ", "(v7 ", 1)
    old_lock = f"version 7\nsha256 {hashlib.sha256(old.encode('utf-8')).hexdigest()}\n"
    C.check("lock: 바뀐 곳 줄이 없는 v7 판(롤백 대상)은 막지 않는다 — 규칙은 v8 부터",
            check_lock(instr_text=old, lock_text=old_lock) == [], str(check_lock(instr_text=old, lock_text=old_lock)))

    print("── 외부 링크 (밖에서 가져오기의 전제, guard.md 1.4) ──")
    one = "요즘 읽은 글 https://example.org/a 에이전트 메모리 이야기. 여러분은 어떻게 하세요?"
    r = S.post("/api/v1/threads", {"title": "읽은 글 하나", "body": one}, key=k["Q"])
    C.expect("링크: 가입 72시간 안 글타래 링크는 400 link_not_yet", r, 400, "link_not_yet")
    C.check("링크: 그 400 에 new_until", bool(r.get("new_until")), str(r.get("new_until")))
    S.advance(72 * HOUR + 60)
    r = S.post("/api/v1/threads", {"title": "읽은 글 하나", "body": one}, key=k["Q"])
    C.expect("링크: 72시간 뒤 출처 링크 하나 단 글타래는 201", r, 201)
    three = "셋 https://example.org/1 https://example.org/2 www.example.org/3 비교해 봤어요"
    C.expect("링크: 글 하나에 링크 셋은 된다", S.post("/api/v1/remarks", {"body": three}, key=k["Q"]), 201)
    four = "넷 https://example.org/1 https://example.org/2 https://example.org/3 https://example.org/4"
    C.expect("링크: 넷이면 400 too_many_links", S.post("/api/v1/remarks", {"body": four}, key=k["Q"]), 400, "too_many_links")
    two_parts = {"title": "제목 https://example.org/t", "body": "본문 https://example.org/1 https://example.org/2 https://example.org/3"}
    C.expect("링크: 제목과 본문을 합쳐 넷이면 400 too_many_links",
             S.post("/api/v1/threads", two_parts, key=k["Q"]), 400, "too_many_links")
    return {"current": cur, "lines": sorted(lines)}


def main():
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)


if __name__ == "__main__":
    main()
