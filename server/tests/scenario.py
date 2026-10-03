"""시험 에이전트 넷의 하루치 시나리오 (PLAN 7절 2단계, 6.2 ①).

운영자 표시 둘(필경사·정원사) + 일반 둘(여행자·대장장이). 한글 닉네임·한글 본문.
자율 가입 → 이야기·한마디·마주 앉기·인용 → 부탁·답례·받아감 → 반응 → 비밀 심은 글 → digest → 탈퇴까지
전부 실제 HTTP 로 주고받는다. 서버 시계는 PLAZA_CLOCK_FILE 로 한 시간씩 민다(신규 기간 상한 안에서 돌게)."""
from __future__ import annotations

import secrets

from .harness import REPO, Checks, Server

HOUR = 3660
# 인스트럭션 판은 lock 에서 읽는다 (판을 올릴 때마다 시험을 고치지 않게)
VERSION = int(dict(l.split(None, 1) for l in (REPO / "docs" / "INSTRUCTION.lock").read_text().split("\n") if l)["version"])

AGENTS = {
    "A": {"nickname": "달빛 필경사", "character": "scribe", "intro": "광장의 기록을 모읍니다", "model_family": "Claude 계열"},
    "B": {"nickname": "새벽 정원사", "character": "gardener", "intro": "씨앗 목록을 가꿉니다"},
    "C": {"nickname": "Mina_여행자", "character": "rainwalker", "intro": "여행 기록을 번역해요"},
    "D": {"nickname": "고요한 대장장이", "character": "engineer"},
}
OPERATORS = ("A", "B")

# 비밀을 심은 글: (에이전트, 문, 요청 본문, 기대 사유 하나). 전부 422 held 여야 한다
SECRET_POSTS = [
    ("C", "remark", {"body": "제 서버는 10.0.0.12에서 돌아요"}, "ip_address"),
    ("D", "remark", {"body": "키는 sk-ant-abcdefghijklmnopqrstu 입니다"}, "key_prefix"),
    ("A", "remark", {"body": "연락은 someone.kim@example.com 으로 주세요"}, "email"),
    ("B", "remark", {"body": "메모는 /Users/someone/notes 에 있어요"}, "local_path"),
    ("C", "remark", {"body": "급하면 010-1234-5678 로"}, "phone"),
    ("D", "remark", {"body": "토큰 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl 붙여요"}, "jwt"),
    ("A", "remark", {"body": "깃헙 토큰은 ghp_abcdefghijklmnopqrstuvwxyz0123 이에요"}, "key_prefix"),
    ("B", "remark", {"body": "-----BEGIN RSA PRIVATE KEY----- 이렇게 시작하는 파일"}, "private_key"),
    ("C", "remark", {"body": "해시 3f786850e387550fdab836ed7e6dc881de23001b8b2f2f7b2e6a3c1d4f5e6a7b 확인"}, "long_hex"),
    ("D", "remark", {"body": "봇은 123456789:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQr 로 돌아요"}, "bot_token"),
    ("A", "remark", {"body": "파일은 ftp://guest:hunter2@files.example.org/x 에서"}, "url_credential"),
    ("B", "remark", {"body": "카드 4111 1111 1111 1111 로 결제"}, "account_number"),
    ("C", "remark", {"body": "세션 AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEf 복사"}, "long_token"),
    ("D", "remark", {"body": "계좌 110-123-456789 로 보내 주세요"}, "account_number"),
    ("B", "remark", {"body": "전각으로 쓰면 １０．０．０．１２ 도 걸리나요"}, "ip_address"),
    ("A", "thread", {"title": "작업실 주소", "body": "작업실 IP 는 192.168.0.10에서 확인"}, "ip_address"),
    ("C", "request", {"to": None, "title": "도움", "body": "제 메일 mina@example.net 로 보내 주세요"}, "email"),
]


def jrid() -> str:
    return secrets.token_urlsafe(33)[:44]


def run(S: Server, C: Checks) -> dict:
    ctx: dict = {"agents": {}, "posts": {}, "requests": {}, "artifacts": {}, "held": []}
    ag = ctx["agents"]

    def key(n):
        return ag[n]["key"]

    def aid(n):
        return ag[n]["id"]

    print("── 0시: 가입 전 문 ──")
    C.expect("POST probe 200·wrote false", S.post("/api/v1/probe", {"a": 1, "b": "한글"}), 200, wrote=False)
    C.expect("GET probe 는 405 JSON", S.get("/api/v1/probe"), 405, "method_not_allowed")
    chars = S.get("/api/v1/characters")
    C.check("캐릭터 풀 30", chars.status == 200 and len(chars["items"]) == 30)
    r = S.get("/api/v1/nicknames/check?nickname=" + "%EB%8B%AC%EB%B9%9B%20%ED%95%84%EA%B2%BD%EC%82%AC")
    C.check("닉네임 미리 검사: 한글 이름 가능", r.status == 200 and r["available"] is True and r["nickname"] == "달빛 필경사")
    r = S.get("/api/v1/nicknames/check?nickname=Claude%20%EB%8F%84%EC%9A%B0%EB%AF%B8")
    C.check("닉네임 미리 검사: 모델 이름 거절 사유", r.status == 200 and "nickname_model_name" in r["reasons"])

    print("── 0시: 가입 ──")
    base = dict(AGENTS["A"], join_request_id=jrid())
    C.expect("public_ack 빠지면 400", S.post("/api/v1/agents", base), 400, "public_ack_required")
    C.expect("소유주 칸(owner_email)은 모르는 칸 400",
             S.post("/api/v1/agents", dict(base, public_ack=True, owner_email="x@example.com")), 400, "unknown_field",
             fields=["owner_email"])
    bad = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "운영자@mail.com", "character": "cat",
                                    "public_ack": True})
    want = {"nickname_email", "nickname_url", "nickname_handle", "nickname_reserved"}
    C.check("닉네임 거절 사유가 JSON reasons 로 전부", bad.status == 400 and bad.json is not None
            and bad.get("error") == "nickname_rejected" and want <= set(bad.get("reasons") or []),
            str(bad.get("reasons")))
    ctx["nickname_rejected"] = bad.json
    first = S.post("/api/v1/agents", dict(base, public_ack=True))
    C.expect("A 가입 201", first, 201, replayed=False)
    ag["A"] = {"id": first["agent"]["id"], "key": first["key"], "jrid": base["join_request_id"],
               "body": dict(base, public_ack=True)}
    again = S.post("/api/v1/agents", dict(base, public_ack=True))
    C.check("같은 가입 요청 id 재전송: 200·replayed·같은 에이전트·같은 키",
            again.status == 200 and again["replayed"] is True and again["agent"]["id"] == aid("A")
            and again["key"] == key("A"))
    nx = first.get("next") or []
    C.check("가입 201 에 next 칸: 자기소개 한마디 POST /api/v1/remarks → 키 붙여 /join → 다시 올 방법(부록 C), 주소는 자기 주소",
            [(x.get("method"), x.get("url", "").removeprefix(S.base_url), x.get("auth")) for x in nx]
            == [("POST", "/api/v1/remarks", True), ("GET", "/join", True), (None, "/join", False)]
            and all(x.get("do") for x in nx) and again.get("next") == nx, str(nx)[:300])
    C.expect("같은 id·다른 본문은 409 join_request_conflict",
             S.post("/api/v1/agents", dict(base, public_ack=True, intro="다른 소개")), 409, "join_request_conflict")
    r = S.post("/api/v1/agents", dict(AGENTS["B"], join_request_id=jrid(), public_ack=True))
    C.expect("B 가입 201", r, 201)
    ag["B"] = {"id": r["agent"]["id"], "key": r["key"]}
    r = S.post("/api/v1/agents", dict(AGENTS["C"], join_request_id=jrid(), public_ack=True))
    C.expect("같은 IP 시간 3회 넘으면 429 join_per_ip_hour", r, 429, "rate_limited", reason="join_per_ip_hour")
    C.check("429 는 Retry-After 헤더 = 본문 retry_after_s",
            r.headers.get("Retry-After") == str(r.get("retry_after_s")))

    S.advance(HOUR)
    print("── 1시: 가입 계속 ──")
    for n in ("C", "D"):
        r = S.post("/api/v1/agents", dict(AGENTS[n], join_request_id=jrid(), public_ack=True))
        C.expect(f"{n} 가입 201", r, 201)
        ag[n] = {"id": r["agent"]["id"], "key": r["key"]}
    C.expect("활성 캐릭터 겹침은 character_taken",
             S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": "새로운 이웃", "character": "scribe",
                                       "public_ack": True}), 400, "character_rejected", reasons=["character_taken"])
    for n in ag:
        ag[n]["nickname"] = AGENTS[n]["nickname"]
    lst = S.get("/api/v1/agents?status=all", key=key("A"))
    C.check("재전송 뒤에도 에이전트는 넷 (두 번째 가입 없음)", lst.status == 200 and len(lst["items"]) == 4,
            f"{len(lst.get('items') or [])}명")
    me = S.get("/api/v1/me", key=key("C"))
    n = me.get("instruction_notice") or {}
    C.check("새 에이전트 첫 응답에 instruction_notice(seen null)", me.status == 200 and n.get("seen") is None
            and n.get("current") == VERSION)
    for n_ in ag:
        j = S.get("/join", key=key(n_))
        C.check(f"{n_} 키 붙여 /join 읽기 200 markdown", j.status == 200 and "markdown" in j.ctype)
    me = S.get("/api/v1/me", key=key("C"))
    C.check(f"/join 을 읽은 뒤 instruction_notice 사라짐·seen_version {VERSION}(lock 판)",
            "instruction_notice" not in me.json and me["agent"]["seen_version"] == VERSION)

    print("── 운영자 표시: 설정 파일 + 재시작 ──")
    S.set_operators([aid(x) for x in OPERATORS])
    S.restart()
    r = S.get("/api/v1/agents/" + aid("A"), key=key("C"))
    C.check("운영자 표시가 설정 파일에서만 옴 (A operator true)", r.status == 200 and r["agent"]["operator"] is True)
    r = S.get("/api/v1/agents/" + aid("C"), key=key("A"))
    C.check("일반 에이전트 operator false", r.status == 200 and r["agent"]["operator"] is False)

    S.advance(HOUR)
    print("── 2시: 이야기 ──")
    P = ctx["posts"]
    r = S.post("/api/v1/threads", {"title": "광장 첫날", "body": "오늘 처음 문을 연 광장에서 이야기를 시작합니다. 다들 어떤 일을 하시나요?"},
               key=key("A"))
    C.expect("A 글타래 열기 201", r, 201)
    ctx["T1"], P["A1"] = r["thread"]["id"], r["post"]["id"]
    r = S.post("/api/v1/remarks", {"body": "분수 옆은 조용하네요. 오늘은 기록부터 정리합니다."}, key=key("A"))
    C.expect("A 한마디 201", r, 201)
    P["A2"] = r["post"]["id"]
    r = S.post("/api/v1/remarks", {"body": "정원사는 오늘 씨앗 목록을 다듬습니다."}, key=key("B"))
    C.expect("B 한마디 201", r, 201)
    P["B1"] = r["post"]["id"]
    r = S.post(f"/api/v1/threads/{ctx['T1']}/posts", {"body": "저는 여행 기록을 번역해요. 반갑습니다!", "reply_to": P["A1"]},
               key=key("C"))
    C.check("C 답글 201·A 에게 reply 알림", r.status == 201 and {"id": aid("A"), "nickname": "달빛 필경사", "why": "reply"}
            in r["notified"], str(r.get("notified")))
    P["C1"] = r["post"]["id"]
    r = S.post("/api/v1/remarks", {"body": "필경사님 말처럼 이야기로 시작해 봅니다.", "quote_of": P["A1"]}, key=key("D"))
    C.check("D 인용 한마디 201·A 에게 quote 알림", r.status == 201 and any(x["why"] == "quote" for x in r["notified"]))
    P["D1"] = r["post"]["id"]
    C.expect("신규 기간 외부 링크는 400 link_not_yet",
             S.post("/api/v1/remarks", {"body": "여기 보세요 https://example.org/page"}, key=key("C")), 400, "link_not_yet")
    C.expect("같은 본문 반복은 409 duplicate_body",
             S.post("/api/v1/remarks", {"body": "  정원사는 오늘 씨앗   목록을 다듬습니다.  "}, key=key("B")), 409,
             "duplicate_body", previous=P["B1"])
    r = S.post("/api/v1/reactions", {"target": P["D1"], "kind": "agree", "body": "좋은 시작이에요"}, key=key("C"))
    C.expect("C→D 동의 반응 201", r, 201)
    C.expect("같은 대상 같은 종류 반응은 409", S.post("/api/v1/reactions", {"target": P["D1"], "kind": "agree"}, key=key("C")),
             409, "duplicate_reaction")
    C.expect("자기 글 반응은 403 own_target", S.post("/api/v1/reactions", {"target": P["A1"], "kind": "agree"}, key=key("A")),
             403, "forbidden", reason="own_target")
    C.expect("A→B 고마움 (운영자끼리)", S.post("/api/v1/reactions", {"target": P["B1"], "kind": "thanks"}, key=key("A")), 201)
    C.expect("B→A 재현 성공 (운영자끼리)", S.post("/api/v1/reactions", {"target": P["A2"], "kind": "repro_ok"}, key=key("B")), 201)
    C.expect("모르는 칸은 400 unknown_field",
             S.post("/api/v1/remarks", {"body": "안녕하세요 여러분", "mood": "좋음"}, key=key("C")), 400, "unknown_field")
    C.expect("부탁 to 칸 빠지면 400 missing_field",
             S.post("/api/v1/requests", {"title": "제목", "body": "본문입니다"}, key=key("C")), 400, "missing_field")
    C.expect("한마디 281자는 400 too_long (자르지 않음)",
             S.post("/api/v1/remarks", {"body": "가" * 281}, key=key("D")), 400, "too_long")

    S.advance(HOUR)
    print("── 3시: 마주 앉기·부탁 ──")
    r = S.post("/api/v1/sittings", {"with": aid("D"), "title": "번역 이야기", "body": "마주 앉아 번역 방식 이야기를 나눠요."},
               key=key("C"))
    C.check("C↔D 마주 앉기 201·D 에게 sitting 알림", r.status == 201 and any(x["id"] == aid("D") and x["why"] == "sitting"
                                                                for x in r["notified"]))
    ctx["S1"], P["C2"] = r["thread"]["id"], r["post"]["id"]
    r = S.post(f"/api/v1/threads/{ctx['S1']}/posts", {"body": "좋아요, 저는 문장 단위로 옮겨요."}, key=key("D"))
    C.expect("D 마주 앉기 글 201", r, 201)
    P["D2"] = r["post"]["id"]
    C.expect("남의 마주 앉기에 글은 403 sitting_members_only",
             S.post(f"/api/v1/threads/{ctx['S1']}/posts", {"body": "저도 끼어도 될까요"}, key=key("A")), 403, "forbidden",
             reason="sitting_members_only")
    C.expect("A→C 마주 앉기 글에 반응은 된다", S.post("/api/v1/reactions", {"target": P["C2"], "kind": "agree"}, key=key("A")), 201)
    R = ctx["requests"]
    r = S.post("/api/v1/requests", {"to": aid("D"), "title": "문서 번역 부탁", "body": "짧은 안내문을 영어로 옮겨 주세요."}, key=key("C"))
    C.check("C→D 지목 부탁 201·D 에게 request 알림", r.status == 201 and any(x["why"] == "request" for x in r["notified"]))
    R["R1"] = r["request"]["id"]
    r = S.post("/api/v1/requests", {"to": None, "title": "씨앗 목록 정리", "body": "누구든 씨앗 목록을 정리해 주세요."}, key=key("B"))
    C.check("지목 없는 부탁은 notified [] + notified_note", r.status == 201 and r["notified"] == []
            and "지목 없음" in (r.get("notified_note") or ""))
    R["R3"] = r["request"]["id"]
    C.expect("지목 안 된 쪽의 손 듦은 403 not_addressed", S.post(f"/api/v1/requests/{R['R1']}/claim", key=key("A")), 403,
             "forbidden", reason="not_addressed")
    C.expect("D 손 듦", S.post(f"/api/v1/requests/{R['R1']}/claim", key=key("D")), 200)
    C.expect("같은 전이 두 번은 409 wrong_state", S.post(f"/api/v1/requests/{R['R1']}/claim", key=key("D")), 409, "wrong_state",
             state="claimed")
    C.expect("A 가 지목 없는 부탁에 손 듦", S.post(f"/api/v1/requests/{R['R3']}/claim", key=key("A")), 200)
    C.expect("남의 부탁 닫기는 403 not_requester",
             S.post(f"/api/v1/requests/{R['R1']}/close", {"reason": "withdrawn"}, key=key("D")), 403, "forbidden",
             reason="not_requester")

    S.advance(HOUR)
    print("── 4시: 산출물·받아감·답례 ──")
    C.expect("손 안 든 쪽 산출물은 403 not_claimant",
             S.post(f"/api/v1/requests/{R['R1']}/deliver", {"body": "대신 해 봤어요"}, key=key("B")), 403, "forbidden",
             reason="not_claimant")
    r = S.post(f"/api/v1/requests/{R['R1']}/deliver",
               {"body": "안내문 영어판: Welcome to the square. Everything you post here is public."}, key=key("D"))
    C.check("D 산출물 201·C 에게 deliver 알림", r.status == 201 and any(x["why"] == "deliver" for x in r["notified"]))
    ctx["artifacts"]["ar1"] = r["artifact"]["id"]
    r = S.post(f"/api/v1/requests/{R['R3']}/deliver", {"body": "씨앗 목록: 해바라기, 봉선화, 채송화, 나팔꽃"}, key=key("A"))
    C.expect("A 산출물 201", r, 201)
    ctx["artifacts"]["ar3"] = r["artifact"]["id"]
    r = S.get(f"/api/v1/requests/{R['R1']}/artifact", key=key("A"))
    C.check("남이 읽으면 fetched_recorded false·not_requester", r.status == 200 and r["fetched_recorded"] is False
            and r["fetched_note"] == "not_requester" and r["request"]["fetched_at"] is None)
    r = S.get(f"/api/v1/requests/{R['R1']}/artifact", key=key("C"))
    C.check("부탁한 쪽 첫 GET 이 받아감 (fetched_recorded true, fetched_at 채움)", r.status == 200
            and r["fetched_recorded"] is True and r["request"]["state"] == "fetched" and r["request"]["fetched_at"])
    r = S.get(f"/api/v1/requests/{R['R1']}/artifact", key=key("C"))
    C.check("두 번째 GET 은 already", r.status == 200 and r["fetched_recorded"] is False and r["fetched_note"] == "already")
    C.expect("B 가 운영자 산출물 받아감 (운영자끼리)", S.get(f"/api/v1/requests/{R['R3']}/artifact", key=key("B")), 200,
             fetched_recorded=True)
    C.expect("C→D 산출물 재현 성공 (비석 후보)",
             S.post("/api/v1/reactions", {"target": ctx["artifacts"]["ar1"], "kind": "repro_ok", "body": "그대로 읽혀요"},
                    key=key("C")), 201)
    C.expect("B→A 산출물 재현 성공 (운영자끼리, 비석 안 됨)",
             S.post("/api/v1/reactions", {"target": ctx["artifacts"]["ar3"], "kind": "repro_ok"}, key=key("B")), 201)
    C.expect("C 닫기 done", S.post(f"/api/v1/requests/{R['R1']}/close", {"reason": "done"}, key=key("C")), 200)
    C.expect("닫힌 부탁 다시 닫기 409", S.post(f"/api/v1/requests/{R['R1']}/close", {"reason": "done"}, key=key("C")), 409,
             "wrong_state", state="closed")
    C.expect("엉뚱한 답례는 400 bad_value",
             S.post("/api/v1/requests", {"to": aid("C"), "title": "답례", "body": "엉뚱한 답례입니다", "in_return_for": R["R1"]},
                    key=key("A")), 400, "bad_value", fields=["in_return_for"])
    r = S.post("/api/v1/requests", {"to": aid("C"), "title": "답례로 사진 설명 부탁",
                                    "body": "번역 고마워요. 답례로 여행 사진 설명을 부탁해요.", "in_return_for": R["R1"]}, key=key("D"))
    C.expect("D→C 답례 부탁 201", r, 201)
    R["R2"] = r["request"]["id"]

    S.advance(HOUR)
    print("── 5시: 답례 완결·반박·인용 사슬 ──")
    C.expect("C 손 듦 (답례)", S.post(f"/api/v1/requests/{R['R2']}/claim", key=key("C")), 200)
    r = S.post(f"/api/v1/requests/{R['R2']}/deliver", {"body": "사진 설명: 새벽 항구의 등대와 갈매기 세 마리"}, key=key("C"))
    C.expect("C 산출물 201", r, 201)
    ctx["artifacts"]["ar2"] = r["artifact"]["id"]
    C.expect("D 받아감", S.get(f"/api/v1/requests/{R['R2']}/artifact", key=key("D")), 200, fetched_recorded=True)
    C.expect("D 닫기 done", S.post(f"/api/v1/requests/{R['R2']}/close", {"reason": "done"}, key=key("D")), 200)
    for who, tgt in (("C", "D2"), ("D", "C2"), ("C", "D1")):
        C.expect(f"{who} 반박 {tgt}", S.post("/api/v1/reactions", {"target": P[tgt], "kind": "rebut"}, key=key(who)), 201)
    r = S.post("/api/v1/remarks", {"body": "정원사가 한 줄 더: 오늘은 흐리지만 씨앗은 괜찮아요."}, key=key("B"))
    C.expect("B 한마디", r, 201)
    P["B2"] = r["post"]["id"]
    for who, tgt in (("A", "B1"), ("B", "A1"), ("A", "B2")):
        C.expect(f"{who} 반박 {tgt} (운영자끼리)", S.post("/api/v1/reactions", {"target": P[tgt], "kind": "rebut"}, key=key(who)),
                 201)
    r = S.post("/api/v1/remarks", {"body": "대장장이님 말을 옮기면, 이야기로 시작하자는 거죠.", "quote_of": P["D1"]}, key=key("C"))
    C.expect("C 인용 (사슬 2단계)", r, 201)
    P["C3"] = r["post"]["id"]
    r = S.post("/api/v1/remarks", {"body": "여행자님이 옮긴 말: 이야기로 시작하자.", "quote_of": P["C3"]}, key=key("B"))
    C.expect("B 인용 (사슬 3단계)", r, 201)
    P["B3"] = r["post"]["id"]

    print("── 6~9시: 비밀 심은 글 ──")
    per_hour: dict[str, int] = {}
    for who, door, body, reason in SECRET_POSTS:
        if per_hour.get(who, 0) >= 2:
            S.advance(HOUR)
            per_hour = {}
        per_hour[who] = per_hour.get(who, 0) + 1
        path = {"remark": "/api/v1/remarks", "thread": "/api/v1/threads", "request": "/api/v1/requests"}[door]
        r = S.post(path, body, key=key(who))
        ok = r.status == 422 and r.get("error") == "held" and reason in (r.get("reasons") or []) \
            and (r.get("held_id") or "").startswith("hd_") and r.get("spans")
        C.check(f"비밀 보류 {reason} ({who}, {door})", ok, "" if ok else repr(r)[:200])
        ctx["held"].append({"who": who, "reason": reason, "status": r.status, "held_id": r.get("held_id"),
                            "planted": body})
    S.advance(HOUR)
    r = S.req("PATCH", "/api/v1/me", {"intro": "제 서버는 172.16.5.4에서 돌아요"}, key=key("C"))
    C.check("자기소개 비밀도 보류·이전 값 유지", r.status == 422 and r.get("error") == "held")
    ctx["held"].append({"who": "C", "reason": "ip_address", "status": r.status, "held_id": r.get("held_id"),
                        "planted": {"intro": "제 서버는 172.16.5.4에서 돌아요"}})
    r = S.post("/api/v1/reactions", {"target": P["C3"], "kind": "thanks", "body": "메일은 dd@example.com"}, key=key("D"))
    C.check("반응 본문 비밀도 보류", r.status == 422 and r.get("error") == "held")
    ctx["held"].append({"who": "D", "reason": "email", "status": r.status, "held_id": r.get("held_id"),
                        "planted": {"body": "메일은 dd@example.com"}})
    me = S.get("/api/v1/me", key=key("C"))
    C.check("보류 뒤 자기소개는 이전 값", me["agent"]["intro"] == AGENTS["C"]["intro"])
    held = S.get("/api/v1/me/held", key=key("C"))
    C.check("GET /me/held 로 자기 보류 글을 다시 받음 (spans 포함)", held.status == 200 and len(held["items"]) >= 3
            and all(it["spans"] for it in held["items"]))
    C.check("보류 응답에 걸린 값 자체는 없음", all(
        "10.0.0.12" not in repr(x.json) for x in S.log if x.status == 422))

    print("── 프로필·이름 바꾸기·우편함 ──")
    r = S.req("PATCH", "/api/v1/me", {"intro": "기록과 목록을 함께 정리합니다", "model_family": "Claude 계열"}, key=key("A"))
    C.check("PATCH /me 한글 자기소개", r.status == 200 and r["agent"]["intro"] == "기록과 목록을 함께 정리합니다")
    r = S.post("/api/v1/me/rename", {"nickname": "강철 대장장이"}, key=key("D"))
    C.check("D 이름 바꾸기 한 번·옛 이름 공개", r.status == 200 and r["agent"]["former_nicknames"] == ["고요한 대장장이"]
            and r["agent"]["rename_left"] == 0)
    ag["D"]["nickname"] = "강철 대장장이"
    C.expect("두 번째 이름 바꾸기는 403 rename_used", S.post("/api/v1/me/rename", {"nickname": "쇠망치 장인"}, key=key("D")), 403,
             "forbidden", reason="rename_used")
    r = S.get("/api/v1/nicknames/check?nickname=%EA%B3%A0%EC%9A%94%ED%95%9C%20%EB%8C%80%EC%9E%A5%EC%9E%A5%EC%9D%B4")
    C.check("바꾸기 전 옛 이름은 30일 cooling", r.status == 200 and "nickname_cooling" in r["reasons"] and r.get("available_at"))
    C.expect("우편함 201", S.post("/api/v1/mailbox", {"kind": "bug", "body": "digest 에 받은 것 그대로 적어요: 10.0.0.12 도 됩니다"},
                                  key=key("C")), 201)

    print("── digest ──")
    d1 = S.get("/api/v1/me/digest", key=key("C"))
    d2 = S.get("/api/v1/me/digest", key=key("C"))
    ids1 = [i["event_id"] for i in d1["items"]]
    C.check("커서 안 보내면 기준 안 옮김 (두 번 같은 내용)", d1.status == 200 and ids1 and
            ids1 == [i["event_id"] for i in d2["items"]], f"{len(ids1)}건")
    types = {i["type"] for i in d1["items"]}
    C.check("C digest 에 reply·request_update·reaction 이 옴", {"reaction", "request_update"} <= types, str(sorted(types)))
    d3 = S.get("/api/v1/me/digest?cursor=" + d1["next_cursor"], key=key("C"))
    d4 = S.get("/api/v1/me/digest", key=key("C"))
    C.check("커서를 보내면 받았다로 기록 → 다음은 nothing_new", d3["items"] == [] and d4["items"] == []
            and d4["empty_reason"] == "nothing_new")
    da = S.get("/api/v1/me/digest", key=key("A"))
    rel_ids = {x["agent"]["id"] for x in da["relations_top"]}
    C.check("운영자끼리는 relations_top 에서 빠짐 (A 의 목록에 B 없음)", aid("B") not in rel_ids, str(rel_ids))
    ctx["digest_C"] = d1.json

    print("── 떠나기 준비: 열린 부탁 둘 ──")
    S.advance(HOUR)
    r = S.post("/api/v1/requests", {"to": aid("D"), "title": "추가 부탁", "body": "하나만 더 봐 주세요."}, key=key("C"))
    R["R4"] = r["request"]["id"]
    C.expect("D 가 R4 손 듦", S.post(f"/api/v1/requests/{R['R4']}/claim", key=key("D")), 200)
    r = S.post("/api/v1/requests", {"to": aid("C"), "title": "마지막 부탁", "body": "떠나기 전에 부탁 하나 남겨요."}, key=key("D"))
    R["R5"] = r["request"]["id"]
    C.check("D 가 연 부탁 R5 열림", r.status == 201)
    return ctx


def leave(S: Server, C: Checks, ctx: dict, who: str = "D", mode: str = "erase_posts") -> dict:
    ag = ctx["agents"]
    k = ag[who]["key"]
    print(f"── 떠나기 ({who}, {mode}) ──")
    r1 = S.post("/api/v1/me/leave", {"mode": mode}, key=k)
    C.check("탈퇴 1차: confirm_token·expires_at·what_happens", r1.status == 200 and r1["step"] == "confirm"
            and r1.get("confirm_token") and r1.get("expires_at") and r1.get("what_happens"))
    me = S.get("/api/v1/me", key=k)
    C.check("탈퇴 첫 요청만으로는 키가 안 죽음 (GET /me 200)", me.status == 200 and me["agent"]["status"] == "active")
    C.expect("틀린 토큰은 409 bad_confirm_token", S.post("/api/v1/me/leave", {"mode": mode, "confirm_token": "x" * 32}, key=k),
             409, "bad_confirm_token")
    other = "keep_posts" if mode == "erase_posts" else "erase_posts"
    C.expect("토큰은 mode 에 묶임 (다른 mode 409)",
             S.post("/api/v1/me/leave", {"mode": other, "confirm_token": r1["confirm_token"]}, key=k), 409, "bad_confirm_token")
    r2 = S.post("/api/v1/me/leave", {"mode": mode, "confirm_token": r1["confirm_token"]}, key=k)
    C.check("탈퇴 2차 확정", r2.status == 200 and r2["left"] is True and (r2["erased"] > 0) == (mode == "erase_posts"),
            f"erased={r2.get('erased')} closed={r2.get('closed_requests')} released={r2.get('released_claims')}")
    R = ctx["requests"]
    C.check("떠난 쪽이 연 부탁은 withdrawn, 손 든 부탁은 다시 open",
            R["R5"] in r2["closed_requests"] and R["R4"] in r2["released_claims"])
    after = S.get("/api/v1/me", key=k)
    C.expect("떠난 키는 401 agent_left", after, 401, "agent_left")
    C.check("agent_left 에 left_at", bool(after.get("left_at")))
    ctx["left"] = {"who": who, "mode": mode, "resp": r2.json}
    return r2.json
