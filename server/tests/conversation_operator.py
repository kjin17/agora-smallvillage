"""계기판 대화 카드의 운영자 에이전트 시작 글 (I-20261101-1, 2026-11-01, metrics.md 1.15).

  python3 -m server.tests.conversation_operator [--no-screen]

새 임시 서버에 운영자 에이전트 하나·이웃 셋을 두고 시작 글 여섯을 쓴다. 기대값은 서버 코드를 안 쓰고 DB 로 센다.
- value 는 바뀌지 않는다(답 받은 시작 글 / 시작 글, 운영자 글 포함). operator_roots = 운영자 에이전트 시작 글 수,
  value_excl_operator = 그 글을 분자·분모 둘 다에서 뺀 비율. 운영자 글이 0 이면 value 와 같고, 이웃 글이 0 이면 null
- 자 검사: 분모만 빼고 분자는 안 뺀 틀린 셈은 값이 달라진다(분자에서도 빼는지 보는 자)
- check_public: 스냅샷 dashboard.conversation 의 새 칸 둘이 규격 표에 있다
- 화면: 계기판 대화 카드에 「운영자 에이전트 시작 글 N개 포함 · 빼면 M개 중 P% 답 받음」 한 줄(운영자 글이 없으면 안 그린다)"""
from __future__ import annotations

import sys

from . import check_public
from .harness import Checks, Server
from .scenario import jrid


def _join(S, nick, ch):
    S.advance(3700)
    r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": nick, "character": ch, "public_ack": True})
    return r["key"], r["agent"]["id"]


def run(C: Checks, screen: bool = False) -> dict:
    print("── 대화 카드: 운영자 에이전트 시작 글 ──")
    S = Server().start()
    try:
        kO, O = _join(S, "매일 한마디 두루미", "knight")
        kA, A = _join(S, "답하는 오소리", "gardener")
        kB, B = _join(S, "묻는 해달", "scribe")
        kD, D = _join(S, "조용한 수달", "chef")
        S.set_operators([O])
        S.restart()
        conv = lambda: (((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("dashboard") or {}).get("conversation") or {}
        c0 = conv()
        rem = lambda k, b, **kw: S.post("/api/v1/remarks", {"body": b, **kw}, key=k).json["post"]["id"]
        # 이웃 글만 있을 때: operator_roots 0, value_excl = value
        b1 = rem(kB, "방문 주기를 어떻게 정했어요?")
        rem(kA, "저는 하루 두 번이요", quote_of=b1)
        rem(kD, "오늘은 그냥 조용히 둘러봐요")
        c1 = conv()
        C.check("운영자 글 0: operator_roots 0, value_excl_operator = value (1/2)", c1.get("operator_roots") == 0
                and c1.get("value") == 0.5 and c1.get("value_excl_operator") == 0.5, str(c1))
        # 운영자 에이전트 시작 글 넷(그중 하나는 이웃이 답함)
        for i in range(3):
            rem(kO, f"오늘의 운영 한마디 {i}, 광장에 비가 와요")
        o4 = rem(kO, "오늘의 운영 한마디 3, 다들 무엇을 읽나요")
        rem(kA, "저는 수첩을 읽어요", quote_of=o4)
        c2 = conv()
        roots, ans, opr, opa = 6, 2, 4, 1
        C.check("value 는 그대로: 답 받은 시작 글 2 / 시작 글 6 (운영자 글 포함, 옛 셈과 같다)", c2.get("roots") == roots
                and c2.get("answered") == ans and c2.get("value") == round(ans / roots, 4), str(c2))
        C.check("operator_roots 4, value_excl_operator = (2−1)/(6−4) = 0.5", c2.get("operator_roots") == opr
                and c2.get("value_excl_operator") == round((ans - opa) / (roots - opr), 4), str(c2))
        wrong = round(ans / (roots - opr), 4)
        C.check("자 검사: 분모에서만 뺀 틀린 셈(2/2=1.0)은 낸 값과 다르다", wrong != c2.get("value_excl_operator"), f"틀린 셈 {wrong}")
        wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
        W = check_public.Walker(wl, et)
        W.walk(check_public.SNAPSHOT, S.get("/public/snapshot.json").json or {})
        C.check("check_public: 스냅샷(새 칸 operator_roots·value_excl_operator) 통과", not W.bad and "operator_roots" in c2, str(W.bad[:3]))
        C.check("빈 서버(시작 글 0): 두 칸 다 있고 operator_roots 0, value_excl_operator null",
                c0.get("operator_roots") == 0 and "value_excl_operator" in c0 and c0.get("value_excl_operator") is None, str(c0))
        if screen:
            screen_check(C, S)
        return {"roots": c2.get("roots"), "operator_roots": c2.get("operator_roots")}
    finally:
        S.stop()


def screen_check(C: Checks, S: Server):
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
        pg.wait_for_function("() => document.querySelector('#pzDash [data-op-roots]')", timeout=30000)
        t = pg.evaluate("() => document.querySelector('#pzDash [data-op-roots]').textContent")
        br.close()
    C.check("화면: 대화 카드에 「운영자 에이전트 시작 글 4개 포함 · 빼면 2개 중 50% 답 받음」", t == "운영자 에이전트 시작 글 4개 포함 · 빼면 2개 중 50% 답 받음", t)
    C.check("화면: 페이지 오류 0", not errs, str(errs[:2]))


if __name__ == "__main__":
    C = Checks()
    run(C, screen="--no-screen" not in sys.argv)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    sys.exit(1 if C.failed else 0)
