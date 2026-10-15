"""안내 주소는 들어온 이름을 따른다 (허용목록). 새 임시 서버 하나에서 Host 헤더만 바꿔 HTTP 로 잰다.

  python3 -m server.tests.join_host

PLAZA_BASE_URL(옛 이름)·PLAZA_SITE_URL(새 이름) 을 둘 다 준 서버에서
- 새 이름으로 들어오면 /join 본문·?format=json 의 base_url·instruction_notice 의 how_to_clear·가입 응답 next·
  llms.txt 의 API 줄·에이전트 카드 API 주소가 전부 새 이름, 옛 이름이 한 글자도 안 섞인다
- 옛 이름으로 들어오면 지금까지와 똑같다(이미 가입한 멤버는 아무것도 안 바뀐다)
- 허용목록 밖 Host(아무 이름·내부 주소)는 반사하지 않고 base_url
- canonical(Link 헤더)·sitemap·관전 화면 canonical 은 어느 이름으로 와도 site_url
자 검사: Host 를 안 바꾸면(127.0.0.1) 옛 이름이 나온다 — 판정이 늘 새 이름만 보는 자가 아님을 같이 본다."""
from __future__ import annotations

import os
import sqlite3

from .harness import Checks, Server
from .scenario import jrid

BASE, SITE = "https://plaza-old.example.test", "https://plaza-new.example.test"
EVIL = "evil.example.test"


def _host(u: str) -> dict:
    return {"Host": u.split("://", 1)[1]}


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
    print("── 안내 주소: 들어온 이름 (허용목록) ──")
    for tag, want, other, h in (("새 이름", SITE, BASE, _host(SITE)), ("옛 이름", BASE, SITE, _host(BASE)),
                                ("허용 밖 Host", BASE, SITE, {"Host": EVIL}), ("Host 그대로(127.0.0.1)", BASE, SITE, {})):
        md = S.get("/join", headers=h)
        C.check(f"[{tag}] /join 본문이 {want} 로 채워짐, {other}·{EVIL} 없음",
                md.status == 200 and want + "/join" in md.text and other not in md.text and EVIL not in md.text
                and "{BASE_URL}" not in md.text and "{JOIN_URL}" not in md.text, f"{md.status}")
        C.check(f"[{tag}] /join canonical 은 늘 site_url", md.headers.get("Link") == f"<{SITE}/join>; rel=\"canonical\"",
                str(md.headers.get("Link")))
        C.check(f"[{tag}] /join Cache-Control no-cache", md.headers.get("Cache-Control") == "no-cache",
                str(md.headers.get("Cache-Control")))
        js = S.get("/join?format=json", headers=h)
        C.check(f"[{tag}] /join?format=json base_url = {want}, 본문도 같은 주소",
                js.get("base_url") == want and other not in (js.get("instruction") or "")
                and EVIL not in js.text, str(js.get("base_url")))
        llms = S.get("/llms.txt", headers=h).text
        C.check(f"[{tag}] llms.txt API 줄 = {want}/api/v1, /join 은 site_url",
                f"{want}/api/v1" in llms and f"{SITE}/join" in llms and EVIL not in llms
                and (want == SITE or f"{SITE}/api/v1" not in llms))
        card = S.get("/.well-known/agent-card.json", headers=h)
        urls = [x.get("url") for x in (card.get("supportedInterfaces") or [])]
        C.check(f"[{tag}] 에이전트 카드 API 주소 = {want}, 문서 주소는 site_url",
                urls == [want + "/api/v1"] and card.get("documentationUrl") == SITE + "/join", str(urls))
        sm = S.get("/sitemap.xml", headers=h).text
        idx = S.get("/", headers=h).text
        C.check(f"[{tag}] sitemap·관전 화면 canonical 은 site_url 그대로",
                f"<loc>{SITE}/join</loc>" in sm and BASE not in sm and EVIL not in sm
                and f'<link rel="canonical" href="{SITE}/">' in idx and EVIL not in idx)

    # 가입 응답 next · instruction_notice how_to_clear
    keys = {}
    chars = iter(["gardener", "scribe", "cat"])
    for tag, want, h in (("새 이름", SITE, _host(SITE)), ("옛 이름", BASE, _host(BASE)), ("허용 밖 Host", BASE, {"Host": EVIL})):
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": f"이름시험 {len(keys) + 1}",
                                      "character": next(chars), "public_ack": True}, headers=h)
        nx = r.get("next") or []
        C.check(f"[{tag}] 가입 응답 next 의 url 이 전부 {want}",
                r.status == 201 and nx and all(str(x.get("url", "")).startswith(want + "/") for x in nx),
                str([x.get("url") for x in nx]) if nx else repr(r)[:300])
        if r.status != 201:
            continue
        S.advance(3600)                                          # 같은 IP 가입 간격(속도 제한) 밖으로
        keys[tag] = (r["key"], r["agent"]["id"], want, h)
    conn = sqlite3.connect(S.db)
    with conn:
        conn.execute("UPDATE agents SET seen_version=0")        # 판을 올린 배포 뒤의 멤버를 흉내
    conn.close()
    for tag, (key, aid, want, h) in keys.items():
        me = S.get("/api/v1/me", key=key, headers=h)
        n = me.get("instruction_notice") or {}
        C.check(f"[{tag}] instruction_notice how_to_clear = GET {want}/join",
                str(n.get("how_to_clear", "")).startswith(f"GET {want}/join "), str(n.get("how_to_clear")))
    # 같은 키가 다른 이름으로 오면 그 이름을 따른다(키는 이름에 안 묶인다)
    key = keys["옛 이름"][0]
    n = (S.get("/api/v1/me", key=key, headers=_host(SITE)).get("instruction_notice") or {})
    C.check("옛 이름으로 가입한 키가 새 이름으로 오면 how_to_clear 도 새 이름",
            str(n.get("how_to_clear", "")).startswith(f"GET {SITE}/join "), str(n.get("how_to_clear")))
    return {}


def main() -> int:
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
