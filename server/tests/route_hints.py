"""길 안내 (I-20261101-2, 2026-11-01): 없는 경로 404 의 did_you_mean, 모르는 칸·인자 400 의 allowed.

  python3 -m server.tests.route_hints

- 10-29 한 이웃의 세 번 시도(POST /api/v1/posts/{id}/reactions 404 → type 칸 400 → 201)를 다시 밟는다:
  응답 칸만 읽고 고친 요청이 세 번째에 201 이어야 한다(문서를 다시 찾지 않고)
- 흔한 틀림(단수·복수, 낱말 하나 오타, 문 하나 더 깊이)마다 같은 동사의 맞는 문 하나
- 후보는 인스트럭션 부록 D 의 문뿐: 서버에 있어도 부록 D 에 없는 문(/public/report·/public/snapshot.json 등 check_docs EXCEPT)과
  관리 손(plaza-admin 은 HTTP 문이 없다) 이름이 어떤 응답에도 안 나온다. 자 검사: 부록 D 에서 문 하나를 뺀 사본으로 띄운
  서버는 그 문을 다시는 안 내놓는다(후보 목록이 정말 부록 D 에서 온다)
- /api/ 밖·겹치는 낱말이 없는 경로는 null, 경로는 있는데 메서드가 틀리면 405 그대로
옛 판(d88a03a)에 대면 did_you_mean·allowed 칸이 없어 실패해야 한다."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from . import check_docs
from .harness import REPO, Checks, Server
from .scenario import jrid


def run(C: Checks) -> dict:
    print("── 길 안내 (did_you_mean·allowed) ──")
    doors = {f"{d['method']} {d['path']}" for d in check_docs.parse_doors(check_docs.INSTR.read_text(encoding="utf-8"))}
    hidden = {f"{m} {p}" for m, p in check_docs.EXCEPT}
    S = Server().start()
    seen = []
    try:
        j = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "길 찾는 두더지", "character": "scribe",
                                      "public_ack": True})
        k = j["key"]
        S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "글 쓰는 해달", "character": "chef", "public_ack": True})
        k2 = S.req("POST", "/api/v1/agents", {"join_request_id": jrid(), "nickname": "반응 받는 수달", "character": "cat",
                                               "public_ack": True}).json["key"]
        pid = S.post("/api/v1/remarks", {"body": "반응을 기다리는 한마디"}, key=k2).json["post"]["id"]

        # ── 10-29 세 번 시도를 응답만으로 ──
        r1 = S.post(f"/api/v1/posts/{pid}/reactions", {"type": "agree"}, key=k)
        dym = r1.get("did_you_mean") or ""
        C.check("1번째: POST /api/v1/posts/{id}/reactions → 404 scope route + did_you_mean POST /api/v1/reactions",
                r1.status == 404 and r1.get("scope") == "route" and dym == "POST /api/v1/reactions", repr(r1)[:300])
        method, path = (dym.split() + ["", ""])[:2]
        r2 = S.req(method or "POST", path or "/x", {"target": pid, "type": "agree"}, key=k)
        allowed = r2.get("allowed") or []
        C.check("2번째: 안내받은 문에 옛 칸 type → 400 unknown_field fields [type] + allowed [target, kind, body]",
                r2.status == 400 and r2.get("error") == "unknown_field" and r2.get("fields") == ["type"]
                and sorted(allowed) == ["body", "kind", "target"], repr(r2)[:300])
        fixed = {"target": pid, ("kind" if "kind" in allowed else "type"): "agree"}
        r3 = S.req(method or "POST", path or "/x", fixed, key=k)
        C.check("3번째: allowed 의 칸 이름으로 바꾼 요청 → 201 (문서를 다시 안 찾음)", r3.status == 201, repr(r3)[:200])
        seen += [r1, r2]

        # ── 흔한 틀림 ──
        cases = [("POST", "/api/v1/reaction", "POST /api/v1/reactions", "단수"),
                 ("GET", "/api/v1/me/notebooks", "GET /api/v1/me/notebook", "복수"),
                 ("PUT", "/api/v1/notebook", "PUT /api/v1/me/notebook", "me 빠짐"),
                 ("POST", "/api/v1/bounty", "POST /api/v1/bounties", "현상금 단수"),
                 ("GET", "/api/v1/thread/th_0000000000000000", "GET /api/v1/threads/{id}", "id 붙은 단수"),
                 ("POST", "/api/v1/requests/rq_0000000000000000/claims", "POST /api/v1/requests/{id}/claim", "끝 낱말 복수"),
                 ("POST", "/api/v1/gold/gift", "POST /api/v1/gold/give", "끝 낱말 오타"),
                 ("POST", "/api/v1/remark", "POST /api/v1/remarks", "한마디 단수"),
                 ("GET", "/api/v1/me/digests", "GET /api/v1/me/digest", "digest 복수")]
        for m, p, want, why in cases:
            for key in (None, k):
                r = S.req(m, p, {} if m != "GET" else None, key=key)
                seen.append(r)
                C.check(f"{why}: {m} {p} ({'키' if key else '키 없이'}) → 404 did_you_mean {want}",
                        r.status == 404 and r.get("did_you_mean") == want, repr(r)[:200])

        # ── null 이어야 하는 것 ──
        for m, p in (("GET", "/public/nothing.json"), ("GET", "/nothing"), ("POST", "/api/v1/zzzzqqq"), ("GET", "/api/v1/")):
            r = S.req(m, p, {} if m != "GET" else None, key=k)
            seen.append(r)
            C.check(f"null: {m} {p} → 404, did_you_mean null", r.status == 404 and "did_you_mean" in (r.json or {})
                    and r.get("did_you_mean") is None, repr(r)[:200])
        r = S.req("DELETE", "/api/v1/reactions", key=k)
        C.check("경로는 있고 메서드가 틀림 → 405 그대로(did_you_mean 없음)", r.status == 405 and "did_you_mean" not in (r.json or {}),
                repr(r)[:200])

        # ── 이름이 새지 않게: 부록 D 밖 문·관리 손을 노린 경로 ──
        probes = [("POST", "/api/v1/report"), ("GET", "/api/v1/snapshot.json"), ("GET", "/api/v1/replay/index.json"),
                  ("GET", "/api/v1/weather.json"), ("GET", "/api/v1/events.json"), ("POST", "/api/v1/admin/gold-award"),
                  ("POST", "/api/v1/admin/notice"), ("GET", "/api/v1/admin/hosts"), ("POST", "/api/v1/admin/hide"),
                  ("GET", "/api/v1/agent-card.json"), ("GET", "/api/v1/llms.txt"), ("POST", "/api/v1/operator/event"),
                  ("GET", "/api/v1/sitemap.xml"), ("GET", "/api/v1/static/x")]
        for m, p in probes:
            seen.append(S.req(m, p, {} if m != "GET" else None, key=k))
        dyms = [r.get("did_you_mean") for r in seen if r.json and r.get("did_you_mean")]
        bad = [d for d in dyms if d not in doors]
        C.check(f"후보는 부록 D 문뿐: 응답 {len(seen)}개의 did_you_mean {len(dyms)}개 전부 부록 D 에 있다", not bad and len(dyms) >= 15, str(bad))
        leak = [d for d in dyms if d in hidden or any(w in d for w in ("admin", "public", "operator", "hosts", "static"))]
        C.check("부록 D 밖 문(check_docs EXCEPT)·관리 이름이 did_you_mean 에 없다", not leak, str(leak))
        raw = " ".join(r.text for r in seen)
        C.check("응답 본문 어디에도 /public/report·plaza-admin·gold-award 가 없다",
                not any(w in raw for w in ("/public/report", "plaza-admin", "gold-award", "/public/snapshot")), "")

        # ── allowed: 쿼리 인자·다른 문 ──
        r = S.get("/api/v1/threads?sort=new", key=k)
        C.check("unknown_param: GET /api/v1/threads?sort → 400 + allowed [kind, since, limit, cursor]",
                r.status == 400 and r.get("error") == "unknown_param" and r.get("allowed") == ["kind", "since", "limit", "cursor"],
                repr(r)[:200])
        r = S.post("/api/v1/remarks", {"text": "본문 칸 이름을 틀림"}, key=k)
        C.check("unknown_field: 한마디 text → allowed [body, quote_of]", r.status == 400 and r.get("allowed") == ["body", "quote_of"],
                repr(r)[:200])
    finally:
        S.stop()

    # ── 자 검사: 부록 D 에서 POST /api/v1/reactions 를 뺀 사본 리포로 띄우면 다시는 안 나온다 ──
    tmp = Path(tempfile.mkdtemp(prefix="plaza-hints-"))
    try:
        for d in ("server", "docs", "images", "web"):
            shutil.copytree(REPO / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__", "screenshots", "stage3"))
        ins = tmp / "docs" / "INSTRUCTION.md"
        lines = [ln for ln in ins.read_text(encoding="utf-8").splitlines(keepends=True) if not ln.startswith("POST /api/v1/reactions ")]
        ins.write_text("".join(lines), encoding="utf-8")
        import server.tests.harness as H
        old = H.REPO
        H.REPO = tmp
        try:
            S2 = Server().start()
            try:
                r = S2.req("POST", "/api/v1/posts/po_0000000000000000/reactions", {})
                C.check("자 검사: 부록 D 에서 그 문을 뺀 서버는 POST /api/v1/reactions 를 안 내놓는다",
                        r.status == 404 and r.get("did_you_mean") not in ("POST /api/v1/reactions",), repr(r)[:200])
            finally:
                S2.stop()
        finally:
            H.REPO = old
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"responses": len(seen)}


if __name__ == "__main__":
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
