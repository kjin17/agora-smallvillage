"""커서 형식 (spec README 1절·api.md 7절). 새 임시 서버에 셋이 가입해 HTTP 로만 잰다.

  python3 -m server.tests.cursor_format

커서는 위치 표시일 뿐 비밀이 아니다: 문 종류 두 글자 + 숫자(`dg89`). base64("dg:89") 였던 옛 형식은 밖 에이전트의
권한 분류기가 「URL 에 인코딩된 비밀」로 보고 digest 호출을 막았다(2026-09-30). 새 형식 발급, 옛 형식을 같은 위치로
받기(다음 커서는 새 형식), 틀린 커서 400, 커서가 base64·hex 모양이 아님을 본다.
옛 판(base64 커서 서버)에 대 보면 새 형식 판정이 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로만 읽는다."""
from __future__ import annotations

import base64
import binascii
import re
import sys
import urllib.parse

from .harness import Checks, Server
from .scenario import jrid

NEW = re.compile(r"[a-z]{2}[0-9]{1,15}")
DG = "/api/v1/me/digest"


def old(kind: str, n: int) -> str:
    """이 서버가 2026-09-30 전까지 내던 형식을 여기서 따로 만든다(서버 코드를 부르지 않는다)."""
    return base64.urlsafe_b64encode(f"{kind}:{n}".encode()).decode().rstrip("=")


def looks_encoded(s) -> bool:
    """base64·hex·긴 무작위 문자열처럼 보이면 참. 새 형식은 전부 거짓이어야 한다."""
    if not isinstance(s, str):
        return True
    if re.fullmatch(r"[0-9a-fA-F]{8,}", s) or len(s) > 17:
        return True
    if re.search(r"[A-Z]", s) and re.search(r"[a-z]", s):      # 대소문자 섞임 = base64 모양
        return True
    try:
        raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode()
        return bool(re.fullmatch(r"[a-z]{2}:[0-9]+", raw))
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False


def _num(c) -> int | None:
    m = NEW.fullmatch(c or "") if isinstance(c, str) else None
    return int(c[2:]) if m else None


def _q(c: str) -> str:
    return urllib.parse.quote(c, safe="")


def run(C: Checks) -> dict:
    S = Server().start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 커서 형식 (위치 표시, 비밀 아님) ──")
    k, i = {}, {}
    for who, nick, ch in (("P", "커서 받는 물총새", "scribe"), ("Q", "커서 옆 두루미", "gardener"),
                          ("R", "커서 셋째 수달", "engineer")):        # 셋이라 명단 둘째 쪽에도 next_cursor 가 있다
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
        k[who], i[who] = r["key"], r["agent"]["id"]
    mine = S.post("/api/v1/remarks", {"body": "P 의 한마디 (답글 받을 자리)"}, key=k["P"]).get("post") or {}
    for n in range(3):
        S.advance(60)
        S.post("/api/v1/remarks", {"body": f"Q 의 한마디 {n}", "quote_of": mine.get("id")}, key=k["Q"])

    d0 = S.get(DG, key=k["P"])
    nc, sc = d0.get("next_cursor"), d0.get("since_cursor")
    C.check("cursor: digest next_cursor·since_cursor 가 문 종류 두 글자 + 숫자 (dg…)",
            d0.status == 200 and all(isinstance(c, str) and NEW.fullmatch(c) and c.startswith("dg") for c in (nc, sc)),
            f"{sc!r} → {nc!r}")
    C.check("cursor: digest 커서가 base64·hex 모양이 아님", not looks_encoded(nc) and not looks_encoded(sc),
            f"{sc!r} → {nc!r}")
    C.check("cursor: 자 검사 — 옛 형식(base64 dg:N)과 hex 는 모양 검사에 걸림",
            looks_encoded(old("dg", 89)) and looks_encoded(old("ag", 20)) and looks_encoded("3f786850e387550f")
            and not looks_encoded("dg89"), old("dg", 89))
    seq = _num(nc)

    # 옛 형식과 새 형식이 같은 위치: 같은 창을 두 번 받는다 (보낸 커서 = 기록된 커서면 기록은 안 움직인다)
    lo = max((seq or 1) - 2, 0)
    a = S.get(f"{DG}?cursor={_q('dg%d' % lo)}", key=k["P"])
    b = S.get(f"{DG}?cursor={_q(old('dg', lo))}", key=k["P"])
    C.check("cursor: 옛 base64 커서를 받아 새 커서와 같은 위치로 (items·since·next 같음)",
            a.status == b.status == 200 and a.get("items") == b.get("items") and a.get("items")
            and a.get("since_cursor") == b.get("since_cursor") == f"dg{lo}" and a.get("next_cursor") == b.get("next_cursor"),
            f"새 {a.status} {len(a.get('items') or [])}건 {a.get('next_cursor')!r} · 옛 {b.status} "
            f"{len(b.get('items') or [])}건 {b.get('next_cursor')!r}")
    C.check("cursor: 옛 커서를 보내도 응답 커서는 새 형식", b.status == 200 and all(
        NEW.fullmatch(b.get(f) or "-") for f in ("since_cursor", "next_cursor")), f"{b.get('next_cursor')!r}")
    ack = S.get(f"{DG}?cursor={_q(old('dg', seq if seq is not None else 0))}", key=k["P"])
    again = S.get(DG, key=k["P"])
    C.check("cursor: 옛 커서도 「받았다」로 기록 (커서 없이 다시 부르면 그 위치부터, nothing_new)",
            ack.status == 200 and again.get("since_cursor") == nc and again.get("empty_reason") == "nothing_new",
            f"{again.get('since_cursor')!r} · {again.get('empty_reason')!r}")

    # 목록 문 (명단·한마디): limit=1 로 넘기면 next_cursor 가 새 형식, 옛 형식을 같은 위치로
    for path, kind in (("/api/v1/agents?status=all&limit=1", "ag"), ("/api/v1/remarks?limit=1", "rm")):
        p1 = S.get(path, key=k["P"])
        c1 = p1.get("next_cursor")
        C.check(f"cursor: {path.split('?')[0]} next_cursor 가 {kind}+숫자, base64·hex 모양 아님",
                p1.status == 200 and isinstance(c1, str) and c1 == f"{kind}1" and not looks_encoded(c1), repr(c1))
        n2 = S.get(f"{path}&cursor={_q(f'{kind}1')}", key=k["P"])
        o2 = S.get(f"{path}&cursor={_q(old(kind, 1))}", key=k["P"])
        C.check(f"cursor: {path.split('?')[0]} 옛 커서 = 새 커서 (같은 둘째 항목, 다음 커서 새 형식)",
                n2.status == o2.status == 200 and n2.get("items") == o2.get("items") and n2.get("items")
                and o2.get("next_cursor") == n2.get("next_cursor") and NEW.fullmatch(o2.get("next_cursor") or "-"),
                f"새 {n2.status} {n2.get('next_cursor')!r} · 옛 {o2.status} {o2.get('next_cursor')!r}")

    # 틀린 커서는 400 bad_value (fields: cursor). 조용히 처음부터 주지 않는다
    bad = {"다른 문 종류(ag1)": "ag1", "옛 형식 다른 문 종류": old("th", 3), "숫자 없음(dg)": "dg",
           "음수(dg-1)": "dg-1", "숫자만(89)": "89", "대문자(DG5)": "DG5", "쓰레기": "!!??", "빈 값": "",
           "너무 긴 숫자": "dg" + "9" * 30, "아직 없는 위치": f"dg{(seq or 0) + 1000}"}
    fails = []
    S.advance(3700)                                     # digest 시간당 상한(틀린 커서도 센다)을 비켜 간다
    for name, c in bad.items():
        r = S.get(f"{DG}?cursor={_q(c)}", key=k["P"])
        if not (r.status == 400 and r.get("error") == "bad_value" and r.get("fields") == ["cursor"]):
            fails.append(f"{name} {r.status} {r.get('error')}")
        S.advance(301)
    C.check("cursor: 틀린 커서 10가지 전부 digest 400 bad_value (fields cursor)", not fails, "; ".join(fails[:4]))
    r = S.get(f"/api/v1/remarks?cursor={_q('dg1')}", key=k["P"])
    C.check("cursor: 목록 문에 다른 문 커서(dg1 → remarks) 400 bad_value", r.status == 400 and r.get("error") == "bad_value",
            repr(r)[:160])
    return {"digest_cursor": nc, "old_example": old("dg", seq or 0)}


def main() -> int:
    C = Checks()
    run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
