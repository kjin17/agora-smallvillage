"""주소 옮기기 (spec/api.md 「안내 주소」·seo-pages.md 4절). 새 임시 서버에서 Host 헤더만 바꿔 HTTP 로 잰다.

  python3 -m server.tests.address_move.check

서버는 자기 주소·대표 주소를 새 이름 하나로(PLAZA_BASE_URL = PLAZA_SITE_URL), 옛 이름을 PLAZA_OLD_URLS 로 받는다.
- 옛 이름으로 온 에이전트: 리디렉트 없이 그대로 답하고, 안내 주소(/join 본문·base_url·how_to_clear·가입 응답 next·
  llms.txt API 줄·에이전트 카드)는 전부 새 이름, 옛 이름이 한 글자도 안 섞인다
- 옛 이름의 /api/* JSON(성공·실패·인증 없는 문)과 /join?format=json 에 address_notice{use,old,message,how_to_clear},
  모든 응답에 헤더 X-Plaza-Moved. 원래 칸은 새 이름으로 받은 것과 같은 이름·같은 값(시각 칸 빼고) — 응답 모양 그대로
- 옛 이름의 /join·/llms.txt 에 X-Robots-Tag: noindex. 새 이름에는 안 붙는다
- 옛 이름의 사람용 페이지(/·/t/<id>)는 새 이름으로 301, /public/* 은 그대로(address_notice 없음)
- 새 이름·터널(127.0.0.1)은 address_notice·X-Plaza-Moved 없음
- 들어온 이름 집계(agent_host_daily)는 옛 이름을 그대로 센다(주간 점검이 읽는 값)
자 검사: 같은 키로 새 이름에 오면 칸이 사라진다 — 판정이 늘 「있음」만 내는 자가 아님을 같이 본다.
옛 판(PLAZA_OLD_URLS 를 모르는 서버)에 대 보면 안내 주소·address_notice·noindex 판정이 실패해야 한다."""
from __future__ import annotations

import sqlite3
import sys

from ..harness import Checks, Server
from ..scenario import jrid

SITE, OLDURL = "https://plaza-new.example.test", "https://plaza-old.example.test"
NEW, OLD = {"Host": SITE.split("://")[1]}, {"Host": OLDURL.split("://")[1]}
HOUR = 3660
TIME_KEYS = {"now", "server_time", "at", "joined_at", "last_seen_at"}


def _shape(obj, drop=("address_notice",)):
    """칸 이름 나무(값은 시각 칸만 빼고 그대로). 응답 모양 비교용"""
    if isinstance(obj, dict):
        return {k: (None if k in TIME_KEYS else _shape(v, ())) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [_shape(x, ()) for x in obj]
    return obj


def run(C: Checks) -> dict:
    S = Server(base_url=SITE, env={"PLAZA_SITE_URL": SITE, "PLAZA_OLD_URLS": OLDURL + "/, "}).start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 주소 옮기기: 옛 이름 → 새 이름 안내 ──")
    # 안내 주소
    for tag, h in (("옛 이름", OLD), ("새 이름", NEW), ("터널(Host 그대로)", {})):
        old = h is OLD
        md = S.get("/join", headers=h)
        C.check(f"[{tag}] /join 200 본문이 {SITE}/join, 옛 이름 없음",
                md.status == 200 and SITE + "/join" in md.text and OLDURL not in md.text, f"{md.status}")
        rb = md.headers.get("X-Robots-Tag")
        C.check(f"[{tag}] /join X-Robots-Tag " + ("noindex" if old else "없음"), rb == ("noindex" if old else None), str(rb))
        mv = md.headers.get("X-Plaza-Moved")
        C.check(f"[{tag}] /join X-Plaza-Moved " + (SITE if old else "없음"), mv == (SITE if old else None), str(mv))
        C.check(f"[{tag}] /join canonical 은 새 이름", md.headers.get("Link") == f'<{SITE}/join>; rel="canonical"',
                str(md.headers.get("Link")))
        js = S.get("/join?format=json", headers=h)
        an = js.get("address_notice")
        C.check(f"[{tag}] /join?format=json base_url = 새 이름, address_notice " + ("있음" if old else "없음"),
                js.get("base_url") == SITE and OLDURL not in (js.get("instruction") or "")
                and ((an or {}).get("use") == SITE and an.get("old") == OLDURL if old else an is None), str(an)[:120])
        lt = S.get("/llms.txt", headers=h)
        rb = lt.headers.get("X-Robots-Tag")
        C.check(f"[{tag}] llms.txt API 줄 새 이름, X-Robots-Tag " + ("noindex" if old else "없음"),
                lt.status == 200 and f"{SITE}/api/v1" in lt.text and OLDURL not in lt.text
                and rb == ("noindex" if old else None), str(rb))
        card = S.get("/.well-known/agent-card.json", headers=h)
        urls = [x.get("url") for x in (card.get("supportedInterfaces") or [])]
        C.check(f"[{tag}] 에이전트 카드 API 주소 = 새 이름", urls == [SITE + "/api/v1"], str(urls))

    # 가입: 옛 이름과 새 이름에서 하나씩. 모양은 같고 옛 이름에만 address_notice
    joined = {}
    chars = iter(["gardener", "scribe"])
    for tag, h in (("옛 이름", OLD), ("새 이름", NEW)):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": f"이사시험 {len(joined) + 1}",
                                      "character": next(chars), "public_ack": True}, headers=h)
        nx = r.get("next") or []
        C.check(f"[{tag}] 가입 201·next 전부 새 이름", r.status == 201 and nx
                and all(str(x.get("url", "")).startswith(SITE + "/") for x in nx), repr(r)[:200])
        joined[tag] = r
        S.advance(HOUR)
    jo, jn = joined["옛 이름"], joined["새 이름"]
    C.check("[옛 이름] 가입 응답에 address_notice·키는 그대로", (jo.get("address_notice") or {}).get("use") == SITE
            and bool(jo.get("key")), str(jo.get("address_notice"))[:120])
    C.check("[새 이름] 가입 응답에 address_notice 없음", jn.status == 201 and "address_notice" not in (jn.json or {}))
    C.check("가입 응답 칸 이름이 두 이름에서 같다(address_notice 만 다름)",
            set((jo.json or {})) - {"address_notice"} == set(jn.json or {}),
            str(set(jo.json or {}) ^ set(jn.json or {})))
    key, aid = jo["key"], jo["agent"]["id"]
    S.get("/join", key=key, headers=NEW)                      # instruction_notice 를 지워 두 응답을 같은 조건으로

    # 같은 키로 두 이름: /me 값이 같고 옛 이름에만 칸·헤더
    mo, mn = S.get("/api/v1/me", key=key, headers=OLD), S.get("/api/v1/me", key=key, headers=NEW)
    C.check("[옛 이름] /me 200·address_notice·X-Plaza-Moved", mo.status == 200
            and (mo.get("address_notice") or {}).get("use") == SITE and mo.headers.get("X-Plaza-Moved") == SITE,
            repr(mo)[:200])
    C.check("자 검사: 같은 키가 새 이름으로 오면 address_notice·X-Plaza-Moved 없음", mn.status == 200
            and "address_notice" not in (mn.json or {}) and mn.headers.get("X-Plaza-Moved") is None)
    C.check("/me 원래 칸은 두 이름에서 같은 값(시각 칸 빼고)", _shape(mo.json) == _shape(mn.json))
    C.check("[옛 이름] /api/v1/* 에 X-Robots-Tag noindex 그대로", mo.headers.get("X-Robots-Tag") == "noindex")
    dg = S.get("/api/v1/me/digest", key=key, headers=OLD)
    C.check("[옛 이름] digest 200·address_notice", dg.status == 200 and "address_notice" in (dg.json or {}), repr(dg)[:160])
    # 실패 응답도 원래 칸 그대로 + 칸 하나
    eo, en = S.get("/api/v1/me", headers=OLD), S.get("/api/v1/me", headers=NEW)
    C.check("[옛 이름] 401 도 JSON 그대로 + address_notice", eo.status == 401 == en.status
            and _shape(eo.json) == _shape(en.json) and "address_notice" in (eo.json or {}), repr(eo)[:160])
    po = S.post("/api/v1/probe", {"x": 1}, headers=OLD)
    C.check("[옛 이름] POST probe 200, 리디렉트 없음", po.status == 200 and po.get("ok") is True
            and "Location" not in po.headers and "address_notice" in (po.json or {}), repr(po)[:160])
    # 공개 자료는 손대지 않는다
    sn = S.get("/public/snapshot.json", headers=OLD)
    C.check("[옛 이름] /public/snapshot.json 200·address_notice 없음", sn.status == 200
            and "address_notice" not in (sn.json or {}), f"{sn.status}")
    # 사람용 페이지는 301
    for p in ("/", "/?view=watch", f"/a/{aid}"):
        r = S.get(p, headers=OLD, follow=False)
        C.check(f"[옛 이름] {p} → 새 이름으로 301", r.status == 301 and r.headers.get("Location") == SITE + p,
                f"{r.status} {r.headers.get('Location')}")
    r = S.get("/", headers=NEW, follow=False)
    C.check("[새 이름] / 200 리디렉트 없음", r.status == 200 and "Location" not in r.headers, f"{r.status}")
    # 들어온 이름 집계는 옛 이름을 그대로 센다
    conn = sqlite3.connect(S.db)
    rows = dict(conn.execute("SELECT host, SUM(count) FROM agent_host_daily WHERE agent_id=? GROUP BY host", (aid,)).fetchall())
    conn.close()
    C.check("들어온 이름 집계: 옛 이름(/me·digest 2)·새 이름 둘 다 센다", rows.get(OLDURL.split("://")[1], 0) == 2
            and rows.get(SITE.split("://")[1], 0) >= 1, str(rows))
    return {"rows": len(C.rows)}


def main(argv=None) -> int:
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
