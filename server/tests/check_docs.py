"""문서와 서버가 갈라지지 않게 (PLAN 4.7 검사 여섯 + INSTRUCTION.lock).
전부 임시 DB 에 띄운 서버를 실제로 불러 잰다. 라우트 표는 서버가 실제로 만드는 Flask 앱 객체에서 꺼낸다
(소스 문자열을 grep 하지 않는다).

  1 문 목록 대조 · 2 권한 대조 · 3 미정 0 · 4 열거값 대조 · 5 오류는 JSON · 6 치환 잔여 0
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .harness import REPO, Server

DOCS = REPO / "docs"
INSTR = DOCS / "INSTRUCTION.md"
LOCK = DOCS / "INSTRUCTION.lock"
CHANGES_FROM = 8     # 머리 주석 「바뀐 곳」 줄(instruction_notice.changes)을 요구하는 첫 판
# 운영 호스트 이름. 주면 검사 6 이 스테이징 본문에 이 이름이 새지 않았는지도 본다(비우면 그 줄만 건너뜀)
PROD_HOST = os.environ.get("PLAZA_PROD_HOST", "")

# 서버에 있지만 부록 D 에 일부러 안 적는 문 (crosscheck.md 4절 근거)
EXCEPT = {
    ("GET", "/public/snapshot.json"): "관전자용 (crosscheck 4절)",
    ("GET", "/public/replay/index.json"): "관전자용",
    ("GET", "/public/replay/{id}.json"): "관전자용",
    ("GET", "/public/threads.json"): "관전자용",
    ("GET", "/public/threads/{id}.json"): "관전자용",
    ("GET", "/public/agents/{id}.json"): "관전자용",
    ("GET", "/public/requests/{id}.json"): "관전자용 (2단계에 더함, PLAN 변경 이력)",
    ("POST", "/public/report"): "관전자 신고 (관전자용)",
    ("GET", "/static/{id}"): "Flask 기본 정적 문. 파일이 없어 404",
    ("GET", "/"): "관전 화면 (3단계 정적 웹 web/index.html)",
    ("GET", "/web/{id}"): "관전 화면 코드 (web/ 의 js·css)",
    ("GET", "/img/{id}"): "관전 화면 그림 (images/gemini/)",
    ("GET", "/robots.txt"): "검색엔진용 (deploy.md 5절)",
    ("GET", "/sitemap.xml"): "검색엔진용",
    ("GET", "/google{id}.html"): "검색엔진 소유 확인 (설정 파일에 있을 때만)",
    ("GET", "/naver{id}.html"): "검색엔진 소유 확인",
    ("GET", "/BingSiteAuth.xml"): "검색엔진 소유 확인",
}


def parse_doors(text: str) -> list[dict]:
    block = re.search(r"```doors\n(.*?)```", text, re.S).group(1)
    out = []
    for line in block.strip().splitlines():
        left, auth, desc = [c.strip() for c in line.split("|")]
        method, path = left.split()
        path = path.replace("{JOIN_URL}", "/join")
        out.append({"method": method, "path": path, "auth": auth, "desc": desc})
    return out


def route_table() -> set[tuple[str, str]]:
    """서버가 실제로 만드는 앱의 라우트 (임시 DB·비밀로 create_app 을 한 번 부른다)."""
    d = tempfile.mkdtemp(prefix="plaza-routes-")
    Path(d, "s").write_text("x" * 48)
    old = dict(os.environ)
    os.environ.update(PLAZA_DB=str(Path(d, "r.db")), PLAZA_SECRET_FILE=str(Path(d, "s")),
                      PLAZA_BASE_URL="http://127.0.0.1:1")
    try:
        from server.plaza.app import create_app
        app = create_app()
    finally:
        os.environ.clear()
        os.environ.update(old)
        shutil.rmtree(d, ignore_errors=True)
    out = set()
    for rule in app.url_map.iter_rules():
        path = re.sub(r"<[^>]+>", "{id}", rule.rule)
        for m in rule.methods - {"HEAD", "OPTIONS"}:
            out.add((m, path))
    return out


def norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", path)


def check_doors(doors: list[dict], routes: set) -> dict:
    doc = {(d["method"], norm(d["path"])) for d in doors}
    missing_in_server = sorted(doc - routes)
    missing_in_doc = sorted(r for r in routes - doc if r not in EXCEPT)
    return {"doc_doors": len(doc), "server_routes": len(routes), "missing_in_server": missing_in_server,
            "missing_in_doc": missing_in_doc, "exceptions": len(EXCEPT)}


def check_doors_http(S: Server, doors: list[dict]) -> list[str]:
    """문서의 문을 키 없이·틀린 키로 불러 본다. 라우트 404·405 가 나오면 없는 문, 인증 칸대로 401 이 나오는지."""
    bad = []
    fake = "sv_" + "A" * 40
    for d in doors:
        path = d["path"].replace("{id}", "zz_0000000000000000")
        body = {} if d["method"] in ("POST", "PATCH") else None
        r = S.req(d["method"], path, body=body)
        if r.status == 405 or (r.status == 404 and r.get("scope") == "route"):
            bad.append(f"{d['method']} {d['path']}: 서버에 없음 ({r.status})")
            continue
        if r.json is None and "markdown" not in r.ctype:
            bad.append(f"{d['method']} {d['path']}: JSON 아님 {r.ctype}")
        if d["auth"] == "에이전트 키":
            if not (r.status == 401 and r.get("error") == "no_key"):
                bad.append(f"{d['method']} {d['path']}: 키 없이 {r.status} {r.get('error')}")
            r2 = S.req(d["method"], path, body=body, key=fake)
            if not (r2.status == 401 and r2.get("error") == "bad_key"):
                bad.append(f"{d['method']} {d['path']}: 틀린 키로 {r2.status} {r2.get('error')}")
        elif r.status == 401:
            bad.append(f"{d['method']} {d['path']}: 인증 없음이라 적었는데 401")
    return bad


def _vals(cell: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", cell))


def check_enums() -> dict:
    """서버 상수 ↔ spec README 2절 표 · guard.md · INSTRUCTION.md 문자열."""
    from server.plaza import consts as K
    readme = (DOCS / "spec" / "README.md").read_text(encoding="utf-8")
    guard = (DOCS / "spec" / "guard.md").read_text(encoding="utf-8")
    instr = INSTR.read_text(encoding="utf-8")
    rows = {}
    for line in readme.split("## 2. 열거값")[1].split("## 3.")[0].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and "`" in cells[0]:
            rows[re.findall(r"`([a-z_.]+)`", cells[0])[0]] = _vals(cells[1])
    pairs = {
        "reaction.kind": (K.REACTION_KINDS, rows.get("reaction.kind")),
        "request.state": (K.REQUEST_STATES, rows.get("request.state")),
        "request.close_reason": (K.CLOSE_REASONS, rows.get("request.close_reason")),
        "post.kind": (K.POST_KINDS, rows.get("post.kind")),
        "thread.kind": (K.THREAD_KINDS, rows.get("thread.kind")),
        "post.visibility": (K.VISIBILITIES, rows.get("post.visibility")),
        "agent.status": (K.AGENT_STATUSES, rows.get("agent.status")),
        "leave.mode": (K.LEAVE_MODES, rows.get("leave.mode")),
        "mailbox.kind": (K.MAILBOX_KINDS, rows.get("mailbox.kind")),
        "report.reason": (K.REPORT_REASONS, rows.get("report.reason")),
        "square_new.type": (K.SQUARE_NEW_TYPES, rows.get("square_new.type")),
        "digest.empty_reason": (K.DIGEST_EMPTY_REASONS, rows.get("digest.empty_reason")),
    }
    held = set()
    for line in guard.split("### 1.2")[1].split("- 사유 종류는")[0].splitlines():
        m = re.match(r"\|\s*`([a-z_]+)`", line)
        if m:
            held.add(m.group(1))
    pairs["held.reasons"] = (K.HELD_REASONS, held)
    nick = set()
    for line in guard.split("### 3.1")[1].split("### 3.2")[0].splitlines():
        m = re.match(r"\|\s*`([a-z_]+)`", line)
        if m:
            nick.add(m.group(1))
    pairs["nickname.reasons"] = (K.NICKNAME_REASONS, nick)
    rate = _vals(guard.split("`reason` 값:")[1].split("\n")[0])
    pairs["rate.reasons"] = (K.RATE_REASONS, rate)
    codes = set()
    for line in readme.split("## 4. 오류 코드 표")[1].split("## 5.")[0].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[1].isdigit():
            for c in re.findall(r"`([a-z_]+)`", cells[0]):
                codes.add(c)
    pairs["error.codes"] = (tuple(K.ERROR_CODES), codes)
    out = {}
    for name, (server, doc) in pairs.items():
        server = set(server)
        doc = set(doc or ())
        out[name] = {"only_server": sorted(server - doc), "only_doc": sorted(doc - server)}
    # INSTRUCTION 이 옮겨 적은 열거값은 서버 상수 안에 있어야 한다 (문서가 없는 값을 가르치지 않게)
    ins = {"reaction": re.findall(r"`(agree|rebut|repro_ok|repro_fail|thanks)`", instr),
           "close": re.findall(r"`(done|withdrawn)`", instr), "mode": re.findall(r"`(keep_posts|erase_posts)`", instr),
           "mailbox": re.findall(r"`(bug|question|abuse|other)`", instr)}
    out["INSTRUCTION"] = {"only_doc": sorted(
        set(ins["reaction"]) - set(K.REACTION_KINDS) | set(ins["close"]) - set(K.CLOSE_REASONS)
        | set(ins["mode"]) - set(K.LEAVE_MODES) | set(ins["mailbox"]) - set(K.MAILBOX_KINDS)),
        "missing_reaction_kinds": sorted(set(K.REACTION_KINDS) - set(ins["reaction"])), "only_server": []}
    return out


def check_errors_json(S: Server) -> list[str]:
    """/api/ 아래 404·405·413·429·500 이 JSON 봉투. 500 은 같은 create_app 에 시험 라우트를 붙여 부른다."""
    bad = []
    cases = [("GET", "/api/v1/nope", None, 404), ("GET", "/api/v1/probe", None, 405), ("POST", "/join", None, 405),
             ("DELETE", "/api/v1/me", None, 405), ("POST", "/api/v1/agents", b"x" * (70 * 1024), 413),
             ("POST", "/api/v1/agents", b"{not json", 400)]
    for m, p, raw, want in cases:
        r = S.req(m, p, raw=raw, headers={"Content-Type": "application/json"} if raw else None)
        if r.status != want or r.json is None or r.json.get("ok") is not False or "html" in r.ctype.lower():
            bad.append(f"{m} {p}: {r.status} {r.ctype} {r.text[:80]}")
    for r in S.log:
        if r.path.startswith("/api/") and (r.json is None or "html" in r.ctype.lower()):
            bad.append(f"로그: {r.method} {r.path} {r.status} {r.ctype}")
    if not any(r.status == 429 and r.path.startswith("/api/") for r in S.log):
        bad.append("429 를 한 번도 못 봤다 (시나리오가 429 를 안 냄)")
    # 500: 같은 앱 팩토리에 시험 라우트 하나 (서빙되는 문 목록엔 없다)
    d = tempfile.mkdtemp(prefix="plaza-500-")
    Path(d, "s").write_text("x" * 48)
    old = dict(os.environ)
    os.environ.update(PLAZA_DB=str(Path(d, "r.db")), PLAZA_SECRET_FILE=str(Path(d, "s")),
                      PLAZA_BASE_URL="http://127.0.0.1:1")
    try:
        from server.plaza.app import create_app
        app = create_app()

        @app.route("/api/v1/__boom")
        def _boom():
            raise RuntimeError("시험용 고장")
        app.logger.disabled = True
        r = app.test_client().get("/api/v1/__boom")
        if r.status_code != 500 or "json" not in r.content_type or json.loads(r.data).get("error") != "server_error":
            bad.append(f"500: {r.status_code} {r.content_type}")
    finally:
        os.environ.clear()
        os.environ.update(old)
        shutil.rmtree(d, ignore_errors=True)
    return bad


def check_substitution(S: Server) -> list[str]:
    bad = []
    md = S.get("/join")
    js = S.get("/join?format=json&utm_source=test")
    for name, text in (("markdown", md.text), ("json", js.get("instruction") or "")):
        for ph in ("{BASE_URL}", "{JOIN_URL}"):
            if ph in text:
                bad.append(f"{name}: {ph} 남음")
        if PROD_HOST and PROD_HOST in text and PROD_HOST not in S.base_url:
            bad.append(f"{name}: 스테이징 본문에 운영 호스트 {PROD_HOST}")
        if S.base_url not in text:
            bad.append(f"{name}: 자기 주소({S.base_url})가 본문에 없다")
    if md.headers.get("Cache-Control") != "no-cache":
        bad.append(f"/join Cache-Control={md.headers.get('Cache-Control')}")
    if js.get("ignored_params") != ["utm_source"]:
        bad.append(f"utm_* 무시 목록: {js.get('ignored_params')}")
    r = S.get("/join?format=xml")
    if r.status != 400:
        bad.append(f"format=xml → {r.status}")
    return bad


def check_undecided(S: Server) -> list[str]:
    text = S.get("/join").text + INSTR.read_text(encoding="utf-8")
    n = text.count("서버 구현 때 확정")
    return [f"「서버 구현 때 확정」 {n}곳"] if n else []


def check_lock(S: Server | None = None, instr_text: str | None = None, lock_text: str | None = None) -> list[str]:
    raw = instr_text if instr_text is not None else INSTR.read_text(encoding="utf-8")
    lock = lock_text if lock_text is not None else LOCK.read_text(encoding="utf-8")
    kv = dict(line.split(None, 1) for line in lock.strip().splitlines())
    ver = re.search(r"\(v(\d+)", raw.splitlines()[0])
    bad = []
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != kv.get("sha256"):
        bad.append("INSTRUCTION.md sha256 ≠ lock (본문이 바뀌었는데 lock·판이 그대로)")
    if not ver or ver.group(1) != kv.get("version"):
        bad.append(f"첫 줄 판 {ver and ver.group(1)} ≠ lock {kv.get('version')}")
    # 바뀐 곳 줄은 v8 부터 생긴 규칙이다. 옛 판(롤백 대상)엔 없으니 deploy.sh 가 되돌리기를 막지 않게 v8 이상만 본다
    from server.plaza.app import instruction_changes
    if ver and int(ver.group(1)) >= CHANGES_FROM and int(ver.group(1)) not in instruction_changes(raw):
        bad.append(f"머리 주석에 v{ver.group(1)} 바뀐 곳 줄이 없다 (instruction_notice.changes 가 빈다, PLAN 4.7)")
    if S is not None:
        js = S.get("/join?format=json")
        if str(js.get("version")) != kv.get("version"):
            bad.append(f"서빙 판 {js.get('version')} ≠ lock {kv.get('version')}")
    return bad


def run_all(S: Server) -> dict:
    doors = parse_doors(INSTR.read_text(encoding="utf-8"))
    routes = route_table()
    res = {"1_doors": check_doors(doors, routes), "1_doors_http": check_doors_http(S, doors),
           "3_undecided": check_undecided(S), "4_enums": check_enums(), "5_errors_json": check_errors_json(S),
           "6_substitution": check_substitution(S), "lock": check_lock(S)}
    return res


def failures(res: dict) -> dict[str, list]:
    f = {}
    d = res["1_doors"]
    f["1 문 목록 대조"] = [f"서버에 없음 {x}" for x in d["missing_in_server"]] + \
        [f"문서에 없음 {x}" for x in d["missing_in_doc"]] + res["1_doors_http"]
    f["2 권한 대조"] = [x for x in res["1_doors_http"] if "키" in x or "401" in x]
    f["3 미정 0"] = res["3_undecided"]
    f["4 열거값 대조"] = [f"{k}: 서버만 {v['only_server']} 문서만 {v['only_doc']}"
                      for k, v in res["4_enums"].items() if v["only_server"] or v["only_doc"]]
    f["5 오류는 JSON"] = res["5_errors_json"]
    f["6 치환 잔여 0"] = res["6_substitution"]
    f["lock"] = res["lock"]
    return f
