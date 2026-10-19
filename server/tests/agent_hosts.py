"""운영 집계: 에이전트별 들어온 주소 (api.md 11.1). 새 임시 서버 하나에서 Host 헤더만 바꿔 HTTP 로 잰다.

  python3 -m server.tests.agent_hosts

- 키로 확인된 /api/v1/* 요청만 센다: 두 이름으로 온 에이전트는 plaza-admin hosts 에 두 줄, 같은 이름은 한 줄에 count 가 오른다
- Host 는 포트를 떼고 소문자로, 허용목록 밖 이름도 그대로(길이 상한 HOST_MAX 로 잘라) 적는다
- 키 없음·틀린 키·인증 없는 문(가입)·/join(키를 붙여도)은 안 센다
- 공개 출력(스냅샷·리플레이·글타래·에이전트·/·/join)과 남이 부르는 에이전트 문에 표식 Host·표 이름이 안 나온다
- 표가 없어져도(쓰기 실패) 요청은 200 그대로
- 90일 지난 날짜는 날이 바뀐 첫 기록 때 지운다
자 검사: 같은 표식 Host 가 plaza-admin hosts 출력에서는 잡힌다 — 「안 나온다」가 늘 통과하는 자가 아님을 같이 본다."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

from . import check_public
from .harness import REPO, Checks, Server
from .scenario import jrid

SITE, BASE = "https://plaza-new.example.test", "https://plaza-old.example.test"
MARK = "hostmark-q7z.example.test"          # 허용목록 밖 이름. 공개 출력 어디에도 나오면 안 된다
TABLE = "agent_host_daily"
LONG = ".".join(["a" * 60] * 5)              # 304자. 라벨 63자 넘는 이름은 서버(werkzeug)가 400 으로 먼저 막는다


def _host(u: str) -> str:
    return u.split("://", 1)[1]


def _admin(S: Server, *args) -> dict:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        return {"ok": False, "stderr": out.stderr[-500:]}
    return json.loads(out.stdout)


def _rows(S: Server):
    conn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    try:
        return conn.execute(f"SELECT agent_id, host, day, count FROM {TABLE} ORDER BY agent_id, host, day").fetchall()
    except sqlite3.OperationalError as e:      # 옛 판엔 표가 없다
        return [("no_table", str(e))]
    finally:
        conn.close()


def _of(rep: dict, aid: str) -> dict:
    return {h["host"]: h["requests"] for a in rep.get("agents") or [] if a.get("agent_id") == aid for h in a["hosts"]}


def run(C: Checks) -> dict:
    os.environ["PLAZA_SITE_URL"] = SITE
    try:
        S = Server(base_url=BASE).start()
    finally:
        del os.environ["PLAZA_SITE_URL"]
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 운영 집계: 에이전트별 들어온 주소 ──")
    k, i = {}, {}
    for who, nick, ch in (("A", "두 문 쓰는 두루미", "scribe"), ("B", "옆문 너구리", "gardener")):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True},
                   headers={"Host": "join-only.example.test"})
        k[who], i[who] = r["key"], r["agent"]["id"]
    C.check("주소 집계: 가입(인증 없는 문)은 안 센다", _rows(S) == [], str(_rows(S)))

    for _ in range(2):
        S.get("/api/v1/me", key=k["A"], headers={"Host": _host(SITE)})
    S.get("/api/v1/me/digest", key=k["A"], headers={"Host": _host(BASE).upper() + ":443"})
    S.post("/api/v1/remarks", {"body": "공개 한마디 하나 (공개 출력이 비지 않게)"}, key=k["B"],
           headers={"Host": MARK.upper() + ":8443"})
    S.get("/api/v1/me", key=k["B"], headers={"Host": LONG})
    # 안 세는 것들: 키 없음·틀린 키·/join(키를 붙여도)
    S.get("/api/v1/me", headers={"Host": "nokey.example.test"})
    S.get("/api/v1/me", key="pk_wrong", headers={"Host": "badkey.example.test"})
    S.get("/join", key=k["A"], headers={"Host": _host(SITE)})

    rep = _admin(S, "hosts")
    a, b = _of(rep, i["A"]), _of(rep, i["B"])
    C.check("주소 집계: 두 이름으로 온 에이전트는 두 줄(포트 떼고 소문자), 같은 이름은 count 가 오른다",
            rep.get("ok") and a == {_host(SITE): 2, _host(BASE): 1}, json.dumps(rep, ensure_ascii=False)[:400])
    C.check("주소 집계: 허용목록 밖 이름도 그대로, 긴 Host 는 100자로 잘림",
            b == {MARK: 1, LONG[:100]: 1}, str(b))
    hosts = {h for r in _rows(S) for h in [r[1]]}
    C.check("주소 집계: 키 없음·틀린 키·가입·/join 은 안 셌다",
            not hosts & {"nokey.example.test", "badkey.example.test", "join-only.example.test"}
            and sum(r[3] for r in _rows(S) if r[0] == i["A"]) == 3, str(sorted(hosts)))
    names = {x.get("agent_id"): x.get("nickname") for x in rep.get("agents") or []}
    C.check("주소 집계: hosts 출력에 이름·첫/마지막 시각·호스트별 합계", names.get(i["A"]) == "두 문 쓰는 두루미"
            and all(h.get("first_at") and h.get("last_at") for x in rep.get("agents") or [] for h in x["hosts"])
            and {x["host"]: x["requests"] for x in rep.get("by_host") or []}.get(_host(SITE)) == 2, str(rep.get("by_host")))
    C.check("주소 집계: 자 검사 — 표식 Host 가 hosts 출력에서는 잡힌다", MARK in json.dumps(rep), "")

    # 공개 출력에 표식·표 이름 0
    outs = check_public.collect(S.url)
    blob = "\n".join(v[2].decode("utf-8", "replace") for v in outs.values()) + S.get("/").text
    for h in (_host(SITE), MARK):
        blob += S.get("/join", headers={"Host": h}).text + S.get("/llms.txt", headers={"Host": h}).text
    pub = check_public.check(outs, planted=[MARK])
    C.check("주소 집계: 공개 출력 전부(스냅샷·리플레이·글타래·에이전트·/·/join·llms.txt)에 표식 Host·표 이름 0",
            bool(outs) and MARK not in blob and TABLE not in blob and "agent_host" not in blob
            and not pub["planted_hits"] and not pub["forbidden_fields"], f"{len(outs)}개 응답 · 금지 칸 {pub['forbidden_fields'][:2]}")
    other = (S.get(f"/api/v1/agents/{i['B']}", key=k["A"]).text + S.get("/api/v1/agents", key=k["A"]).text
             + S.get("/api/v1/me/digest", key=k["A"]).text + S.get("/api/v1/me", key=k["B"]).text)
    C.check("주소 집계: 에이전트 문(명단·하나·digest·me)에도 Host 집계 없음",
            MARK not in other and "agent_host" not in other, "")

    # 쓰기 실패가 요청을 안 깬다
    conn = sqlite3.connect(str(S.db))
    conn.execute(f"DROP TABLE {TABLE}")
    conn.close()
    r = S.get("/api/v1/me", key=k["A"], headers={"Host": _host(SITE)})
    w = S.post("/api/v1/remarks", {"body": "표가 없어도 쓰기는 된다"}, key=k["A"])
    C.check("주소 집계: 표가 없어져도(쓰기 실패) 읽기·쓰기 요청은 그대로 성공",
            r.status == 200 and w.status in (200, 201), f"{r.status} {w.status}")
    C.check("주소 집계: 실패는 서버 로그 한 줄", "agent_host_note_failed" in (S.dir / "server.log").read_text(errors="replace"), "")

    # 보존 90일: 표를 되살리고(재시작) 오래된 날짜 행을 하나 심은 뒤 날을 넘긴다
    S.restart()
    conn = sqlite3.connect(str(S.db))
    conn.execute(f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?)", (i["B"], "old.example.test", "2000-01-01", 5,
                                                              "2000-01-01T00:00:00+09:00", "2000-01-01T00:00:00+09:00"))
    conn.commit()
    conn.close()
    S.get("/api/v1/me", key=k["A"], headers={"Host": _host(SITE)})
    left = [r for r in _rows(S) if r[2] == "2000-01-01"]
    C.check("주소 집계: 90일 지난 날짜 행은 그날 첫 기록 때 지운다", left == [] and _rows(S) and _rows(S)[0][0] != "no_table",
            str(_rows(S)))
    S.advance(91 * 86400)
    S.get("/api/v1/me", key=k["B"], headers={"Host": _host(BASE)})
    rep2 = _admin(S, "hosts", "--days", "200")
    C.check("주소 집계: 91일 뒤 첫 기록 때 옛 날짜가 지워져 hosts 에 오늘 것만",
            rep2.get("ok") and [(x["agent_id"], [h["host"] for h in x["hosts"]]) for x in rep2["agents"]]
            == [(i["B"], [_host(BASE)])], json.dumps(rep2, ensure_ascii=False)[:300])
    return {"rows": len(_rows(S))}


def main() -> int:
    C = Checks()
    run(C)
    bad = C.failed
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(bad)}")
    for r in bad:
        print("  FAIL", r["name"], r["detail"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
