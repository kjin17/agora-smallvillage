"""떠 있는 원격 서버(터널 주소)에 PLAN 4.7 문서-서버 검사 중 밖에서 쏠 수 있는 것만 돌린다.

  python3 -m server.tests.check_remote --url http://127.0.0.1:18765

1 문 목록(HTTP)·2 권한(키 없이·틀린 키)·3 미정 0·5 오류는 JSON(6종)·6 치환 잔여 0·lock(서빙 판).
4 열거값과 5 의 429·500 은 서버 상수·시험 라우트가 필요해 로컬 몫(run_stage2). 아무것도 쓰지 않는다
(가입 문에는 칸 모양이 틀린 요청만 보내 속도 제한 앞에서 400 으로 끝난다).

옛 이름(PLAZA_OLD_URLS)으로 쏘면 서버는 본문·base_url 에 대표 주소를 싣고 X-Plaza-Moved 로 알린다
(docs/deploy.md 「자기 주소까지 옮기기」). --base-url 이 없으면 /join?format=json 의 X-Plaza-Moved 를 자기 주소로
쓰고, 결과의 base_url_from 에 근거를 남긴다(헤더가 없으면 기존대로 --url).
"""
from __future__ import annotations

import argparse
import json
import sys

from . import check_docs as C
from .harness import Server


def _moved_to(S) -> tuple[str, str] | None:
    """옛 이름이면 (대표 주소, 근거). 헤더만 본다: 본문 base_url 을 기대값으로 삼으면 6 치환이 자기 답을 채점한다."""
    r = S.get("/join?format=json")
    hdr = next((v for k, v in r.headers.items() if k.lower() == "x-plaza-moved"), "").strip()
    return (hdr.rstrip("/"), "X-Plaza-Moved") if hdr else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--base-url", help="서버의 PLAZA_BASE_URL (기본 --url 과 같음)")
    a = ap.parse_args(argv)
    S = Server()                       # 띄우지 않는다. 주소만 원격으로
    S.url = a.url.rstrip("/")
    S.base_url, base_from = (a.base_url or a.url).rstrip("/"), ("--base-url" if a.base_url else "--url")
    if not a.base_url:
        moved = _moved_to(S)
        if moved:
            S.base_url, base_from = moved
    doors = C.parse_doors(C.INSTR.read_text(encoding="utf-8"))
    res = {
        "1_2 문 목록·권한 (HTTP)": C.check_doors_http(S, doors),
        "3 미정 0": C.check_undecided(S),
        "5 오류는 JSON (원격 6종)": [x for x in C.check_errors_json(S) if not x.startswith(("429", "500"))],
        "6 치환 잔여 0": C.check_substitution(S),
        "lock (서빙 판)": C.check_lock(S),
    }
    html = [f"{r.method} {r.path} {r.status}" for r in S.log if "html" in r.ctype.lower()]
    res["HTML 응답 0"] = html
    print(json.dumps({"doors": len(doors), "requests": len(S.log), "base_url": S.base_url, "base_url_from": base_from,
                      "result": res}, ensure_ascii=False, indent=1))
    return 1 if any(res.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
