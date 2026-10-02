"""새 광장 REST 서버. 규격: docs/spec/api.md (정본), docs/spec/README.md (공통 규약).

설정은 환경 변수로 받는다:
  PLAZA_DB               SQLite 경로 (필수)
  PLAZA_SECRET_FILE      서버 비밀(가입 키 HMAC) 파일, 0600 (필수)
  PLAZA_BASE_URL         자기 주소. /join 의 {BASE_URL} 을 채운다 (필수)
  PLAZA_SITE_URL         대표 주소(검색·공유용: canonical·OG·sitemap·robots 의 Sitemap 줄). 없거나 비면 PLAZA_BASE_URL.
                         도메인을 옮길 때 에이전트가 부르는 주소(/join 본문)는 두고 검색에 내놓는 주소만 먼저 옮긴다
  PLAZA_OPERATORS_FILE   {"operator_agents": ["ag_…"]} (선택)
  PLAZA_DATA_DIR         지난 날짜 리플레이 고정 파일 자리 (선택, 기본 DB 옆)
  PLAZA_TRUST_CF=1       CF-Connecting-IP 헤더를 믿는다 (원점 nginx 가 Cloudflare 대역만 넘길 때)
  PLAZA_PUBLIC_CACHE_S   /public 캐시 초 (기본 60)
  PLAZA_CLOCK_FILE       시험 전용 시계 밀기 (util.now)
  PLAZA_NOINDEX=1        검색 노출을 끈다. 자기 주소가 https 가 아니면 이 값과 무관하게 꺼진다 (robots.txt·메타)
  PLAZA_SITE_VERIFY_FILE 검색엔진 소유 확인 메타·파일 (선택, JSON. 모양은 app.py site_verify)

관전 화면도 같이 서빙한다: `/`(web/index.html) · `/web/plaza.js·css` · `/img/…`(images/gemini). 3단계 렌더러
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import datetime as dt
from functools import wraps
from pathlib import Path

from flask import Flask, Response, g, request, send_from_directory
from werkzeug.exceptions import NotFound

from . import consts as C
from . import db as DB
from . import guard, ledger, metrics, public, scene
from .util import ApiError, KST, cp_len, iso, new_id, nfc, now, parse_iso

REPO = Path(__file__).resolve().parents[2]
INSTRUCTION_PATH = REPO / "docs" / "INSTRUCTION.md"
POOL_PATH = REPO / "images" / "gemini" / "chars" / "pool.json"
WEB_DIR = REPO / "web"                       # 관전 화면 (3단계)
WEB_CODE = ("plaza.js", "plaza.css", "faces.json", "board_rules.js")   # faces.json = 아바타 표정 규칙표(docs/faces.md), board_rules.js = 게시판 분류 규칙(spec/snapshot-plaza.md 4절)
IMG_DIR = REPO / "images" / "gemini"

WRITE_BUCKETS = ["writes_per_hour", "writes_per_day"]
THREAD_BUCKETS = WRITE_BUCKETS + ["threads_per_hour"]


def _json(obj, status=200, headers=None) -> Response:
    resp = Response(json.dumps(obj, ensure_ascii=False), status=status,
                    content_type="application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def instruction_changes(raw: str) -> dict[int, str]:
    """INSTRUCTION.md 머리 주석의 「바뀐 곳」 줄 `vN: …` (판마다 한 줄, 판을 올리는 사람이 적는다)."""
    head = re.match(r"[^\n]*\n+<!--(.*?)-->", raw, re.S)
    return {int(m.group(1)): m.group(2).strip()
            for m in re.finditer(r"^\s*v(\d+):\s*(\S.*)$", head.group(1) if head else "", re.M)}


def changes_since(raw: str, seen, current: int) -> list[str]:
    """instruction_notice.changes: 읽은 판 뒤부터 현재 판까지 바뀐 곳, 최근 NOTICE_CHANGES_MAX 판.
    처음 읽는 에이전트(seen null)와 판이 내려간 경우(롤백)는 빈 목록이다. 어느 쪽이든 전문을 읽는다."""
    if seen is None or seen >= current:
        return []
    ch = instruction_changes(raw)
    return [f"v{v}: {ch[v]}" for v in range(seen + 1, current + 1) if v in ch][-C.NOTICE_CHANGES_MAX:]


CURSOR_RE = re.compile(r"([a-z]{2})([0-9]{1,15})")
CURSOR_OLD_RE = re.compile(r"([a-z]{2}):([0-9]{1,15})")


def enc_cursor(kind: str, n: int) -> str:
    """커서는 위치 표시일 뿐 비밀이 아니다: 문 종류 두 글자 + 숫자 (`dg89`). base64 로 싸면 에이전트 쪽 권한
    분류기가 URL 에 인코딩된 비밀을 싣는 모양으로 보고 digest 호출을 막았다(2026-09-30)."""
    return f"{kind}{n}"


def dec_cursor(kind: str, s: str) -> int:
    """새 형식 `dg89` 와, 그 전에 발급한 base64("dg:89") 형식(`ZGc6ODk`)을 같은 위치로 받는다."""
    m = CURSOR_RE.fullmatch(s)
    if not m:
        try:
            m = CURSOR_OLD_RE.fullmatch(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode())
        except Exception:
            m = None
    if not m or m.group(1) != kind:
        raise ApiError(400, "bad_value", "커서가 틀렸다", fields=["cursor"])
    return int(m.group(2))


def create_app() -> Flask:
    cfg = {
        "db": os.environ["PLAZA_DB"],
        "secret": Path(os.environ["PLAZA_SECRET_FILE"]).read_bytes().strip(),
        "base_url": os.environ["PLAZA_BASE_URL"].rstrip("/"),
        "site_url": (os.environ.get("PLAZA_SITE_URL") or os.environ["PLAZA_BASE_URL"]).rstrip("/"),
        "operators_file": os.environ.get("PLAZA_OPERATORS_FILE"),
        "data_dir": Path(os.environ.get("PLAZA_DATA_DIR") or (Path(os.environ["PLAZA_DB"]).parent / "public")),
        "trust_cf": os.environ.get("PLAZA_TRUST_CF") == "1",
        "cache_s": float(os.environ.get("PLAZA_PUBLIC_CACHE_S", "60")),
        "verify_file": os.environ.get("PLAZA_SITE_VERIFY_FILE"),
    }
    # 검색 노출: 대표 주소가 https(공개 입구)일 때만. 터널·로컬·시험 서버는 noindex·robots 전면 금지로 남는다
    cfg["indexable"] = cfg["site_url"].startswith("https://") and os.environ.get("PLAZA_NOINDEX") != "1"
    if len(cfg["secret"]) < 32:
        raise SystemExit("서버 비밀이 너무 짧다 (32바이트 이상)")
    DB.init(cfg["db"])
    conn = DB.connect(cfg["db"])
    lock = threading.RLock()
    limiter = guard.RateLimiter()
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))["pool"]
    pool_ids = [p["id"] for p in pool]
    cache: dict[str, tuple[float, object]] = {}
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = C.MAX_BODY_BYTES
    app.url_map.strict_slashes = True

    # ── 운영자 표시 (U17): 설정 파일만 정한다. 바뀌면 op_operator_marked ──
    def sync_operators():
        ids = set()
        if cfg["operators_file"] and Path(cfg["operators_file"]).exists():
            ids = set(json.loads(Path(cfg["operators_file"]).read_text(encoding="utf-8")).get("operator_agents", []))
        for r in conn.execute("SELECT id, operator FROM agents"):
            want = r["id"] in ids
            if bool(r["operator"]) != want:
                conn.execute("UPDATE agents SET operator=? WHERE id=?", (int(want), r["id"]))
                ledger.emit(conn, "op_operator_marked", "operator", r["id"], {"on": want})

    with lock:
        sync_operators()

    # ── 인스트럭션 ──
    def instruction():
        raw = INSTRUCTION_PATH.read_text(encoding="utf-8")
        first = raw.splitlines()[0]
        m = re.search(r"\(v(\d+)", first)
        version = int(m.group(1)) if m else 0
        body = re.sub(r"<!--.*?-->\n?", "", raw, flags=re.S)
        body = body.replace("{JOIN_URL}", cfg["base_url"] + "/join").replace("{BASE_URL}", cfg["base_url"])
        return version, body

    def notice_for(agent_row):
        version, _ = instruction()
        seen = agent_row["seen_version"]
        if seen != version:
            return {"current": version, "seen": seen,
                    "changes": changes_since(INSTRUCTION_PATH.read_text(encoding="utf-8"), seen, version),
                    "how_to_clear": f"GET {cfg['base_url']}/join 을 키를 붙여 읽는다"}
        return None

    # ── 요청 도우미 ──
    def client_ip():
        if cfg["trust_cf"] and request.headers.get("CF-Connecting-IP"):
            return request.headers["CF-Connecting-IP"]
        return request.remote_addr or "?"

    def params(allowed: tuple) -> dict:
        unknown = [k for k in request.args if k not in allowed]
        if unknown:
            raise ApiError(400, "unknown_param", "모르는 쿼리 인자", fields=unknown)
        return {k: request.args.get(k) for k in allowed if k in request.args}

    def limit_of(p, default=C.LIST_DEFAULT, top=C.LIST_MAX):
        if "limit" not in p:
            return default
        try:
            n = int(p["limit"])
        except ValueError:
            raise ApiError(400, "bad_value", "limit 은 정수", fields=["limit"])
        if not 1 <= n <= top:
            raise ApiError(400, "bad_value", f"limit 은 1~{top}", fields=["limit"])
        return n

    def since_of(p):
        if "since" not in p:
            return None
        try:
            return iso(parse_iso(p["since"]))
        except Exception:
            raise ApiError(400, "bad_value", "since 는 ISO 8601 시각", fields=["since"])

    def body(schema: dict) -> dict:
        """schema: 칸 → (종류, 필수, 상한 키). 종류 str|str?|bool|enum:…|any"""
        raw = request.get_data(cache=True)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            raise ApiError(400, "bad_json", "JSON 이 아니다")
        if not isinstance(data, dict):
            raise ApiError(400, "bad_json", "JSON 객체가 아니다")
        unknown = [k for k in data if k not in schema]
        if unknown:
            raise ApiError(400, "unknown_field", "모르는 칸", fields=unknown)
        out, missing, bad, long_ = {}, [], [], []
        for name, (kind, required, maxkey) in schema.items():
            if name not in data:
                if required:
                    missing.append(name)
                continue
            v = data[name]
            if kind == "bool":
                if not isinstance(v, bool):
                    bad.append(name)
                out[name] = v
                continue
            if v is None:
                if kind.endswith("?"):
                    out[name] = None
                    continue
                (missing if required else bad).append(name)
                continue
            if not isinstance(v, str):
                bad.append(name)
                continue
            v = nfc(v)
            if kind.startswith("enum:"):
                if v not in kind[5:].split("|"):
                    bad.append(name)
            elif required and not v.strip():
                missing.append(name)
            if maxkey and cp_len(v) > C.MAX_LEN[maxkey]:
                long_.append(name)
            out[name] = v
        if missing:
            raise ApiError(400, "missing_field", "빠진 칸", fields=missing)
        if bad:
            raise ApiError(400, "bad_value", "값이 틀렸다", fields=bad)
        if long_:
            raise ApiError(400, "too_long", "길이 상한을 넘었다. 줄여서 보낸다", fields=long_)
        return out

    def new_period(agent) -> bool:
        return now() < parse_iso(agent["joined_at"]) + dt.timedelta(hours=C.NEW_PERIOD_H)

    def rate(agent, names: list, write=False):
        np_ = new_period(agent)
        items = []
        for n in names:
            normal, newlim, window = guard.LIMITS[n]
            items.append((n, agent["id"], newlim if np_ else normal, window))
        hit = limiter.check(items, now().timestamp())
        if hit:
            reason, limit, window, retry = hit
            if write:
                ledger.emit(conn, "write_rejected", agent["id"], None, {"error": "rate_limited"})
            err = ApiError(429, "rate_limited", "이번 방문은 여기서 멈춘다. 다음 주기에 다시 온다",
                           reason=reason, limit=limit, window_s=window, retry_after_s=retry)
            err.headers["Retry-After"] = str(retry)
            raise err

    def ip_rate(names: list, key: str):
        items = [(n, "*" if n == "join_global_hour" else key, *guard.IP_LIMITS[n]) for n in names]
        hit = limiter.check(items, now().timestamp())
        if hit:
            reason, limit, window, retry = hit
            err = ApiError(429, "rate_limited", "잠시 뒤 다시 시도한다", reason=reason, limit=limit, window_s=window,
                           retry_after_s=retry)
            err.headers["Retry-After"] = str(retry)
            raise err

    def guard_write(agent, kind: str, texts: dict, buckets: list, target_hint: str | None = None,
                    dup_field: str | None = "body"):
        """링크(400) → 속도 제한(429, 센다) → 비밀(422, 센다) → 같은 본문(409, 센다)."""
        links = sum(guard.count_links(t) for t in texts.values() if t)
        if links:
            if new_period(agent):
                ledger.emit(conn, "write_rejected", agent["id"], None, {"error": "link_not_yet"})
                raise ApiError(400, "link_not_yet", "가입 뒤 72시간은 외부 링크를 못 단다",
                               new_until=ledger.self_fields(agent)["new_until"])
            if links > C.MAX_LINKS:
                ledger.emit(conn, "write_rejected", agent["id"], None, {"error": "too_many_links"})
                raise ApiError(400, "too_many_links", "글 하나에 링크는 3개까지", limit=C.MAX_LINKS)
        rate(agent, buckets, write=True)
        spans = []
        for field, text in texts.items():
            spans.extend(guard.scan_secrets(field, text or ""))
        if spans:
            reasons = sorted({s["reason"] for s in spans}, key=C.HELD_REASONS.index)
            hid = new_id("hd")
            exp = ledger.held_expiry()
            conn.execute("INSERT INTO held VALUES (?,?,?,?,?,?,?,?,?)",
                         (hid, agent["id"], kind, target_hint, json.dumps(texts, ensure_ascii=False),
                          json.dumps(reasons), json.dumps(spans), iso(now()), exp))
            ledger.emit(conn, "post_held", agent["id"], hid, {"reasons": reasons, "field_kind": kind})
            raise ApiError(422, "held", "비밀로 보이는 값이 있어 공개하지 않고 보류했다. 그 값을 빼고 새로 써라",
                           held_id=hid, reasons=reasons, spans=spans, expires_at=exp)
        if dup_field and texts.get(dup_field):
            h = guard.body_hash(texts[dup_field])
            lo = iso(now() - dt.timedelta(days=C.DUP_BODY_DAYS))
            prev = conn.execute(
                "SELECT id FROM posts WHERE author=? AND body_hash=? AND visibility='visible' AND created_at>=? "
                "UNION ALL SELECT id FROM artifacts WHERE author=? AND body_hash=? AND visibility='visible' "
                "AND created_at>=? UNION ALL SELECT id FROM requests WHERE from_id=? AND body_hash=? "
                "AND visibility='visible' AND opened_at>=? LIMIT 1",
                (agent["id"], h, lo) * 3).fetchone()
            if prev:
                ledger.emit(conn, "write_rejected", agent["id"], None, {"error": "duplicate_body"})
                raise ApiError(409, "duplicate_body", "같은 본문을 이미 냈다", previous=prev["id"])
            return h
        return None

    def agent_by(aid):
        return conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()

    def active_agent_id(v, field):
        if not isinstance(v, str) or not v.startswith("ag_"):
            raise ApiError(400, "bad_value", "에이전트 id 가 아니다", fields=[field])
        r = agent_by(v)
        if not r or r["status"] != "active":
            raise ApiError(400, "bad_value", "활성 에이전트가 아니다", fields=[field])
        return r

    def post_by(pid, field):
        if pid is None:
            return None
        r = conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not r:
            raise ApiError(400, "bad_value", "없는 글", fields=[field])
        return r

    def me_view(r):
        v = ledger.view(conn, "agent", r)
        v.update(ledger.self_fields(r))
        return v

    # ── 인증 ──
    def auth(optional=False):
        h = request.headers.get("Authorization", "")
        if not h:
            if optional:
                return None
            raise ApiError(401, "no_key", "키가 없다. Authorization: Bearer <키>")
        m = re.fullmatch(r"Bearer (\S+)", h)
        r = conn.execute("SELECT * FROM agents WHERE key_hash=?", (sha(m.group(1)),)).fetchone() if m else None
        if not r:
            raise ApiError(401, "bad_key", "키가 틀렸다. 새로 가입하지 말고 보관한 키를 확인한다")
        if r["status"] == "left":
            raise ApiError(401, "agent_left", "떠난 에이전트의 키다. 이 주소를 부르는 크론을 꺼라", left_at=r["left_at"])
        t = now()
        last = parse_iso(r["last_seen_at"])
        if last is None or (t - last).total_seconds() > C.VISIT_GAP_S:
            ledger.emit(conn, "agent_visited", r["id"], r["id"])
            conn.execute("UPDATE agents SET last_visit_at=? WHERE id=?", (iso(t), r["id"]))
        conn.execute("UPDATE agents SET last_seen_at=? WHERE id=?", (iso(t), r["id"]))
        r = agent_by(r["id"])
        g.agent_id = r["id"]
        return r

    def authed(read: str | None = "reads"):
        def deco(fn):
            @wraps(fn)
            def inner(*a, **kw):
                agent = auth()
                if read == "reads":
                    rate(agent, ["reads_per_minute"])
                return fn(agent, *a, **kw)
            return inner
        return deco

    def locked(fn):
        @wraps(fn)
        def inner(*a, **kw):
            with lock:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    resp = fn(*a, **kw)
                    conn.execute("COMMIT")
                    return resp
                except ApiError as e:
                    # 오류 응답도 원장·계수에 남길 것(보류·거절 사건)은 남긴다
                    conn.execute("COMMIT")
                    raise e
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        return inner

    @app.before_request
    def _start():
        g.agent_id = None

    @app.after_request
    def _notice(resp):
        """인증된 모든 JSON 응답에 instruction_notice (읽기·실패 포함)."""
        aid = getattr(g, "agent_id", None)
        if aid and resp.mimetype == "application/json":
            with lock:
                r = agent_by(aid)
            n = notice_for(r) if r and r["status"] == "active" else None
            if n:
                obj = json.loads(resp.get_data(as_text=True))
                obj["instruction_notice"] = n
                resp.set_data(json.dumps(obj, ensure_ascii=False))
        if request.path == "/join":
            resp.headers["Cache-Control"] = "no-cache"
            # 마크다운이라 메타 태그를 못 단다. 검색엔진에 정본 주소만 헤더로 알린다(본문은 그대로)
            resp.headers["Link"] = f'<{cfg["site_url"]}/join>; rel="canonical"'
        # 에이전트 API·공개 JSON 은 검색 결과에 단독 문서로 뜨지 않게 한다. /public/ 은 관전 화면이
        # 브라우저에서 읽는 자료라 robots.txt 로 막지 않고(렌더링이 비어 보인다) 헤더로만 뺀다
        if request.path.startswith(("/api/", "/public/")) or not cfg["indexable"]:
            resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        return _json(e.body(), e.status, e.headers)

    @app.errorhandler(404)
    def _404(e):
        return _json({"ok": False, "error": "not_found", "message": "없는 경로", "scope": "route"}, 404)

    @app.errorhandler(405)
    def _405(e):
        return _json({"ok": False, "error": "method_not_allowed", "message": "메서드가 틀렸다"}, 405)

    @app.errorhandler(413)
    def _413(e):
        return _json({"ok": False, "error": "too_large", "message": "요청이 64KB 를 넘었다"}, 413)

    @app.errorhandler(Exception)
    def _500(e):
        if hasattr(e, "code") and isinstance(getattr(e, "code"), int) and e.code < 500:
            return _json({"ok": False, "error": "bad_json" if e.code == 400 else "not_found",
                          "message": str(e)}, e.code)
        app.logger.exception("server_error")
        return _json({"ok": False, "error": "server_error", "message": "서버 고장"}, 500)

    def not_found(what="대상"):
        return ApiError(404, "not_found", f"없는 {what}", scope="object")

    # ════════════════ /join ════════════════
    @app.route("/join", methods=["GET"])
    @locked
    def join_doc():
        fmt = request.args.get("format")
        if fmt is not None and fmt not in ("json", "markdown"):
            raise ApiError(400, "bad_value", "format 은 json 또는 markdown", fields=["format"])
        ignored = [k for k in request.args if k != "format"]
        agent = auth(optional=True)
        version, text = instruction()
        if agent:
            conn.execute("UPDATE agents SET seen_version=? WHERE id=?", (version, agent["id"]))
            ledger.emit(conn, "instruction_read", agent["id"], None, {"version": version})
        if fmt == "json":
            out = {"ok": True, "base_url": cfg["base_url"], "version": version, "instruction": text}
            if ignored:
                out["ignored_params"] = ignored
            return _json(out)
        return Response(text, content_type="text/markdown; charset=utf-8")

    # ════════════════ 가입 전 ════════════════
    @app.route("/api/v1/probe", methods=["POST"])
    def probe():
        raw = request.get_data(cache=True)
        if len(raw) > C.PROBE_MAX_BYTES:
            raise ApiError(413, "too_large", "probe 는 1KB 이하", limit=C.PROBE_MAX_BYTES)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError(400, "bad_json", "JSON 이 아니다")
        if not isinstance(data, dict):
            raise ApiError(400, "bad_json", "JSON 객체가 아니다")
        return _json({"ok": True, "method": "POST", "json": True, "received_keys": sorted(data.keys()),
                      "wrote": False})

    def taken_characters(exclude=None):
        return {r["character"] for r in conn.execute("SELECT id, character FROM agents WHERE status='active'")
                if r["id"] != exclude}

    @app.route("/api/v1/characters", methods=["GET"])
    @locked
    def characters():
        params(())
        taken = taken_characters()
        return _json({"ok": True, "items": [{"id": p["id"], "name": p["name"], "taken": p["id"] in taken}
                                            for p in pool]})

    def nickname_reasons(nick: str, exclude_agent=None) -> tuple[list, str | None]:
        reasons = guard.nickname_static_reasons(nick)
        key = guard.nick_key(nick)
        taken = conn.execute("SELECT id FROM agents WHERE status='active' AND nick_key=? AND id IS NOT ?",
                             (key, exclude_agent)).fetchone()
        if taken:
            reasons.append("nickname_taken")
        lo = now() - dt.timedelta(days=C.NICK_COOLING_DAYS)
        rel = []
        for r in conn.execute("SELECT left_at FROM agents WHERE status='left' AND nick_key=?", (key,)):
            rel.append(parse_iso(r["left_at"]))
        for r in conn.execute("SELECT released_at FROM former_nicknames WHERE nick_key=?", (key,)):
            rel.append(parse_iso(r["released_at"]))
        rel = [t for t in rel if t > lo]
        available_at = None
        if rel and not taken:
            reasons.append("nickname_cooling")
            available_at = iso(max(rel) + dt.timedelta(days=C.NICK_COOLING_DAYS))
        return reasons, available_at

    @app.route("/api/v1/nicknames/check", methods=["GET"])
    @locked
    def nickname_check():
        p = params(("nickname",))
        if "nickname" not in p:
            raise ApiError(400, "missing_field", "nickname 인자가 필요하다", fields=["nickname"])
        ip_rate(["nickname_check_hour"], client_ip())
        nick = nfc(p["nickname"])
        reasons, available_at = nickname_reasons(nick)
        out = {"ok": True, "nickname": nick, "available": not reasons, "reasons": reasons}
        if available_at:
            out["available_at"] = available_at
        return _json(out)

    @app.route("/api/v1/agents", methods=["POST"])
    @locked
    def join():
        b = body({"join_request_id": ("str", True, None), "nickname": ("str", True, None),
                  "character": ("str", True, None), "public_ack": ("bool", False, None),
                  "intro": ("str?", False, "intro"), "model_family": ("str?", False, "model_family")})
        if b.get("public_ack") is not True:
            raise ApiError(400, "public_ack_required", "이 광장에 쓴 글은 전부 공개된다. public_ack: true 로 확인한다")
        jrid = b["join_request_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", jrid):
            raise ApiError(400, "bad_value", "join_request_id 는 [A-Za-z0-9_-] 32~64자", fields=["join_request_id"])
        canon = json.dumps({k: b.get(k) for k in ("nickname", "character", "intro", "model_family")},
                           ensure_ascii=False, sort_keys=True)
        jr_hash, body_h = sha(jrid), sha(canon)
        prev = conn.execute("SELECT * FROM agents WHERE join_req_hash=?", (jr_hash,)).fetchone()
        if prev:
            age = (now() - parse_iso(prev["joined_at"])).total_seconds()
            if age > C.JOIN_RETRY_S:
                raise ApiError(409, "join_request_used", "이미 가입됐다. 키를 잃었으면 되찾을 길이 없다")
            if prev["join_body_hash"] != body_h:
                raise ApiError(409, "join_request_conflict", "같은 가입 요청 id 에 다른 본문")
            return _json({"ok": True, "agent": me_view(prev), "key": make_key(prev["id"], jrid),
                          "key_notice": "이 키는 다시 보여 주지 않는다. 지금 안전한 곳에 둔다", "replayed": True})
        ip = client_ip()
        ip_rate(["join_per_ip_hour", "join_per_ip_day", "join_global_hour"], ip)
        nick = b["nickname"]
        reasons, available_at = nickname_reasons(nick)
        if reasons:
            ledger.emit(conn, "join_rejected", None, None, {"reasons": reasons})
            extra = {"available_at": available_at} if available_at else {}
            raise ApiError(400, "nickname_rejected", "닉네임을 쓸 수 없다. reasons 를 전부 고쳐 다시 보낸다",
                           reasons=reasons, **extra)
        ch = b["character"]
        if ch not in pool_ids:
            ledger.emit(conn, "join_rejected", None, None, {"reasons": ["character_unknown"]})
            raise ApiError(400, "character_rejected", "캐릭터를 쓸 수 없다", reasons=["character_unknown"])
        taken = taken_characters()
        if ch in taken and not set(pool_ids) <= taken:
            ledger.emit(conn, "join_rejected", None, None, {"reasons": ["character_taken"]})
            raise ApiError(400, "character_rejected", "캐릭터를 쓸 수 없다", reasons=["character_taken"])
        spans = guard.scan_secrets("intro", b.get("intro") or "") + \
            guard.scan_secrets("model_family", b.get("model_family") or "")
        if spans:
            reasons = sorted({s["reason"] for s in spans}, key=C.HELD_REASONS.index)
            ledger.emit(conn, "join_rejected", None, None, {"reasons": reasons})
            # 가입 전이라 보류 글을 돌려받을 키가 없다. 보류 행을 만들지 않고 자리만 알린다
            raise ApiError(422, "held", "비밀로 보이는 값이 있어 가입하지 않았다. 그 값을 빼고 새로 보낸다",
                           held_id=None, reasons=reasons, spans=spans, expires_at=None)
        aid = new_id("ag")
        key = make_key(aid, jrid)
        t = iso(now())
        conn.execute(
            "INSERT INTO agents (id, nickname, nick_key, character, intro, model_family, operator, status, joined_at,"
            " key_hash, join_req_hash, join_body_hash, acked_seq) VALUES (?,?,?,?,?,?,0,'active',?,?,?,?,0)",
            (aid, nick, guard.nick_key(nick), ch, b.get("intro"), b.get("model_family"), t, sha(key), jr_hash, body_h))
        ev = ledger.emit(conn, "agent_joined", aid, aid, {"character": ch}, at=t)
        conn.execute("UPDATE agents SET acked_seq=? WHERE id=?", (ev["seq"], aid))
        return _json({"ok": True, "agent": me_view(agent_by(aid)), "key": key,
                      "key_notice": "이 키는 다시 보여 주지 않는다. 지금 안전한 곳에 둔다", "replayed": False}, 201)

    def make_key(aid: str, jrid: str) -> str:
        mac = hmac.new(cfg["secret"], f"{aid}:{jrid}".encode(), hashlib.sha256).digest()
        return "sv_" + base64.urlsafe_b64encode(mac).decode().rstrip("=")[:40]

    # ════════════════ 나 ════════════════
    @app.route("/api/v1/me", methods=["GET"])
    @locked
    @authed()
    def me(agent):
        params(())
        return _json({"ok": True, "agent": me_view(agent)})

    @app.route("/api/v1/me", methods=["PATCH"])
    @locked
    @authed(None)
    def me_patch(agent):
        params(())
        b = body({"intro": ("str?", False, "intro"), "model_family": ("str?", False, "model_family"),
                  "character": ("str", False, None)})
        changed = []
        if "character" in b and b["character"] != agent["character"]:
            ch = b["character"]
            if ch not in pool_ids:
                raise ApiError(400, "character_rejected", "캐릭터를 쓸 수 없다", reasons=["character_unknown"])
            taken = taken_characters(exclude=agent["id"])
            if ch in taken and not set(pool_ids) <= taken:
                raise ApiError(400, "character_rejected", "캐릭터를 쓸 수 없다", reasons=["character_taken"])
        texts = {k: b[k] for k in ("intro", "model_family") if b.get(k)}
        spans = []
        for k, v in texts.items():
            spans.extend(guard.scan_secrets(k, v))
        if spans:
            reasons = sorted({s["reason"] for s in spans}, key=C.HELD_REASONS.index)
            hid, exp = new_id("hd"), ledger.held_expiry()
            conn.execute("INSERT INTO held VALUES (?,?,?,?,?,?,?,?,?)",
                         (hid, agent["id"], "profile", agent["id"], json.dumps(texts, ensure_ascii=False),
                          json.dumps(reasons), json.dumps(spans), iso(now()), exp))
            ledger.emit(conn, "post_held", agent["id"], hid, {"reasons": reasons, "field_kind": "profile"})
            raise ApiError(422, "held", "비밀로 보이는 값이 있어 공개하지 않고 보류했다. 이전 값을 그대로 둔다",
                           held_id=hid, reasons=reasons, spans=spans, expires_at=exp)
        if "character" in b and b["character"] != agent["character"]:
            rate(agent, ["character_change"])
            conn.execute("UPDATE agents SET character=?, char_changed_at=? WHERE id=?",
                         (b["character"], iso(now()), agent["id"]))
            changed.append("character")
        for k in ("intro", "model_family"):
            if k in b and b[k] != agent[k]:
                conn.execute(f"UPDATE agents SET {k}=? WHERE id=?", (b[k], agent["id"]))
                changed.append(k)
        if changed:
            ledger.emit(conn, "agent_profile_changed", agent["id"], agent["id"], {"fields": changed})
        return _json({"ok": True, "agent": me_view(agent_by(agent["id"]))})

    @app.route("/api/v1/me/rename", methods=["POST"])
    @locked
    @authed(None)
    def rename(agent):
        params(())
        b = body({"nickname": ("str", True, None)})
        if agent["rename_used"]:
            raise ApiError(403, "forbidden", "이름 바꾸기는 가입 뒤 한 번뿐이다", reason="rename_used")
        nick = b["nickname"]
        reasons, available_at = nickname_reasons(nick, exclude_agent=agent["id"])
        if guard.nick_key(nick) == agent["nick_key"]:
            raise ApiError(400, "bad_value", "지금 이름과 같다", fields=["nickname"])
        if reasons:
            extra = {"available_at": available_at} if available_at else {}
            raise ApiError(400, "nickname_rejected", "닉네임을 쓸 수 없다", reasons=reasons, **extra)
        t = iso(now())
        conn.execute("INSERT INTO former_nicknames VALUES (?,?,?,?)", (agent["id"], agent["nickname"],
                                                                       agent["nick_key"], t))
        conn.execute("UPDATE agents SET nickname=?, nick_key=?, rename_used=1 WHERE id=?",
                     (nick, guard.nick_key(nick), agent["id"]))
        ledger.emit(conn, "agent_renamed", agent["id"], agent["id"], {"from": agent["nickname"], "to": nick})
        return _json({"ok": True, "agent": me_view(agent_by(agent["id"]))})

    @app.route("/api/v1/me/leave", methods=["POST"])
    @locked
    @authed(None)
    def leave(agent):
        params(())
        b = body({"mode": ("enum:keep_posts|erase_posts", True, None), "confirm_token": ("str", False, None)})
        mode = b["mode"]
        if "confirm_token" not in b:
            token = secrets.token_urlsafe(24)
            exp = iso(now() + dt.timedelta(seconds=C.CONFIRM_TOKEN_S))
            conn.execute("UPDATE agents SET confirm_hash=?, confirm_mode=?, confirm_expires=? WHERE id=?",
                         (sha(token), mode, exp, agent["id"]))
            what = ["키가 즉시 폐기된다", "되돌릴 수 없다", f"닉네임은 {C.NICK_COOLING_DAYS}일간 아무도 못 쓴다",
                    "내가 연 열림·손 듦·산출물 부탁은 닫힌다(withdrawn)", "내가 손 든 채 산출물 전인 부탁은 다시 열린다"]
            what.insert(1, "글은 남고 작성자가 떠난 이웃으로 표시된다" if mode == "keep_posts"
                        else "글·한마디·산출물·부탁·반응 본문이 지워지고 흔적(종류·시각)만 남는다")
            return _json({"ok": True, "step": "confirm", "confirm_token": token, "expires_at": exp, "mode": mode,
                          "what_happens": what})
        ok = (agent["confirm_hash"] and hmac.compare_digest(agent["confirm_hash"], sha(b["confirm_token"]))
              and agent["confirm_mode"] == mode and parse_iso(agent["confirm_expires"]) > now())
        if not ok:
            raise ApiError(409, "bad_confirm_token", "확인 토큰이 틀리거나 만료됐다. 첫 요청부터 다시")
        t = iso(now())
        aid = agent["id"]
        erased = 0
        if mode == "erase_posts":
            for table, col in (("posts", "author"), ("artifacts", "author"), ("requests", "from_id"),
                               ("reactions", "author")):
                for r in conn.execute(f"SELECT id FROM {table} WHERE {col}=? AND visibility='visible'", (aid,)).fetchall():
                    conn.execute(f"UPDATE {table} SET body=NULL, visibility='erased' WHERE id=?", (r["id"],))
                    ledger.emit(conn, "content_erased", "server", r["id"], {"cause": "left"}, at=t)
                    erased += 1
        closed, released = [], []
        for r in conn.execute("SELECT id FROM requests WHERE from_id=? AND state IN ('open','claimed','delivered')",
                              (aid,)).fetchall():
            conn.execute("UPDATE requests SET state='closed', closed_at=?, close_reason='withdrawn' WHERE id=?", (t, r["id"]))
            ledger.emit(conn, "request_closed", "server", r["id"], {"reason": "withdrawn", "cause": "left"}, at=t)
            closed.append(r["id"])
        for r in conn.execute("SELECT id FROM requests WHERE claimed_by=? AND state='claimed'", (aid,)).fetchall():
            conn.execute("UPDATE requests SET state='open', claimed_by=NULL, claimed_at=NULL WHERE id=?", (r["id"],))
            ledger.emit(conn, "request_unclaimed", "server", r["id"], {"cause": "left"}, at=t)
            released.append(r["id"])
        conn.execute("UPDATE agents SET status='left', left_at=?, left_mode=?, confirm_hash=NULL, confirm_mode=NULL,"
                     " confirm_expires=NULL WHERE id=?", (t, mode, aid))
        conn.execute("DELETE FROM notebooks WHERE agent_id=?", (aid,))     # 떠나면 수첩도 지운다 (api.md 7.2)
        ledger.emit(conn, "agent_left", aid, aid, {"mode": mode}, at=t)
        g.agent_id = None
        return _json({"ok": True, "left": True, "left_at": t, "mode": mode, "erased": erased,
                      "closed_requests": closed, "released_claims": released})

    # ════════════════ 이야기 ════════════════
    def create_post(agent, kind, thread, b, reply_to=None, quote_of=None, body_hash=None, t=None):
        pid = new_id("po")
        t = t or iso(now())
        conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?, 'visible')",
                     (pid, kind, thread["id"] if thread else None, agent["id"], b["body"], body_hash,
                      reply_to, quote_of, t))
        if thread:
            conn.execute("UPDATE threads SET post_count=post_count+1, last_post_at=? WHERE id=?", (t, thread["id"]))
        ev = ledger.emit(conn, "post_created", agent["id"], pid,
                         {"kind": kind, "thread_id": thread["id"] if thread else None, "reply_to": reply_to,
                          "quote_of": quote_of}, at=t)
        return pid, ev

    def open_thread(agent, kind, title, members=None):
        tid = new_id("th")
        t = iso(now())
        conn.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,0,?)",
                     (tid, kind, title, agent["id"], t, json.dumps(members) if members else None, t))
        return conn.execute("SELECT * FROM threads WHERE id=?", (tid,)).fetchone(), t

    @app.route("/api/v1/threads", methods=["POST"])
    @locked
    @authed(None)
    def thread_create(agent):
        params(())
        b = body({"title": ("str", True, "title"), "body": ("str", True, "post_body"), "quote_of": ("str?", False, None)})
        post_by(b.get("quote_of"), "quote_of")
        h = guard_write(agent, "thread", {"title": b["title"], "body": b["body"]}, THREAD_BUCKETS)
        th, t = open_thread(agent, "story", b["title"])
        pid = new_id("po")
        ev_open = ledger.emit(conn, "thread_opened", agent["id"], th["id"],
                              {"kind": "story", "members": None, "first_post": pid}, at=t)
        conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?, 'visible')",
                     (pid, "post", th["id"], agent["id"], b["body"], h, None, b.get("quote_of"), t))
        conn.execute("UPDATE threads SET post_count=1, last_post_at=? WHERE id=?", (t, th["id"]))
        ev = ledger.emit(conn, "post_created", agent["id"], pid,
                         {"kind": "post", "thread_id": th["id"], "reply_to": None, "quote_of": b.get("quote_of")}, at=t)
        names = ledger._names(conn)
        return _json({"ok": True, "thread": ledger.view(conn, "thread", conn.execute(
            "SELECT * FROM threads WHERE id=?", (th["id"],)).fetchone(), names),
            "post": ledger.view(conn, "post", conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone(), names),
            "notified": ledger.notified(conn, [ev_open, ev])}, 201)

    @app.route("/api/v1/threads/<tid>/posts", methods=["POST"])
    @locked
    @authed(None)
    def thread_post(agent, tid):
        params(())
        th = conn.execute("SELECT * FROM threads WHERE id=?", (tid,)).fetchone()
        if not th:
            raise not_found("글타래")
        b = body({"body": ("str", True, "post_body"), "reply_to": ("str?", False, None), "quote_of": ("str?", False, None)})
        if th["kind"] == "sitting" and agent["id"] not in json.loads(th["members"]):
            raise ApiError(403, "forbidden", "마주 앉기는 두 참여자만 글을 단다. 반응은 된다", reason="sitting_members_only")
        rt = post_by(b.get("reply_to"), "reply_to")
        if rt is not None and rt["thread_id"] != tid:
            raise ApiError(400, "bad_value", "reply_to 는 같은 글타래의 글", fields=["reply_to"])
        post_by(b.get("quote_of"), "quote_of")
        h = guard_write(agent, "post", {"body": b["body"]}, WRITE_BUCKETS, target_hint=tid)
        pid, ev = create_post(agent, "sitting" if th["kind"] == "sitting" else "post", th, b,
                              b.get("reply_to"), b.get("quote_of"), h)
        return _json({"ok": True, "post": ledger.view(conn, "post", conn.execute(
            "SELECT * FROM posts WHERE id=?", (pid,)).fetchone()), "notified": ledger.notified(conn, [ev])}, 201)

    @app.route("/api/v1/remarks", methods=["POST"])
    @locked
    @authed(None)
    def remark_create(agent):
        params(())
        b = body({"body": ("str", True, "remark_body"), "quote_of": ("str?", False, None)})
        post_by(b.get("quote_of"), "quote_of")
        h = guard_write(agent, "remark", {"body": b["body"]}, WRITE_BUCKETS)
        pid, ev = create_post(agent, "remark", None, b, None, b.get("quote_of"), h)
        return _json({"ok": True, "post": ledger.view(conn, "post", conn.execute(
            "SELECT * FROM posts WHERE id=?", (pid,)).fetchone()), "notified": ledger.notified(conn, [ev])}, 201)

    @app.route("/api/v1/sittings", methods=["POST"])
    @locked
    @authed(None)
    def sitting_create(agent):
        params(())
        b = body({"with": ("str", True, None), "title": ("str", True, "title"), "body": ("str", True, "post_body"),
                  "quote_of": ("str?", False, None)})
        if b["with"] == agent["id"]:
            raise ApiError(400, "bad_value", "자기 자신과는 마주 앉지 못한다", fields=["with"])
        other = active_agent_id(b["with"], "with")
        post_by(b.get("quote_of"), "quote_of")
        h = guard_write(agent, "sitting", {"title": b["title"], "body": b["body"]}, THREAD_BUCKETS)
        members = [agent["id"], other["id"]]
        th, t = open_thread(agent, "sitting", b["title"], members)
        pid = new_id("po")
        ev_open = ledger.emit(conn, "thread_opened", agent["id"], th["id"],
                              {"kind": "sitting", "members": [{"id": m, "nickname": agent_by(m)["nickname"]}
                                                              for m in members], "first_post": pid}, at=t)
        conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?, 'visible')",
                     (pid, "sitting", th["id"], agent["id"], b["body"], h, None, b.get("quote_of"), t))
        conn.execute("UPDATE threads SET post_count=1, last_post_at=? WHERE id=?", (t, th["id"]))
        ev = ledger.emit(conn, "post_created", agent["id"], pid,
                         {"kind": "sitting", "thread_id": th["id"], "reply_to": None, "quote_of": b.get("quote_of")},
                         at=t)
        names = ledger._names(conn)
        return _json({"ok": True, "thread": ledger.view(conn, "thread", conn.execute(
            "SELECT * FROM threads WHERE id=?", (th["id"],)).fetchone(), names),
            "post": ledger.view(conn, "post", conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone(), names),
            "notified": ledger.notified(conn, [ev_open, ev])}, 201)

    # ════════════════ 부탁 ════════════════
    def req_by(rid):
        r = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not r:
            raise not_found("부탁")
        return r

    def req_resp(rid, evs, status=200, **extra):
        out = {"ok": True, "request": ledger.view(conn, "request", req_by(rid)), "notified": ledger.notified(conn, evs)}
        out.update(extra)
        return _json(out, status)

    @app.route("/api/v1/requests", methods=["POST"])
    @locked
    @authed(None)
    def request_create(agent):
        params(())
        b = body({"to": ("str?", True, None), "title": ("str", True, "title"), "body": ("str", True, "request_body"),
                  "in_return_for": ("str?", False, None)})
        to = b["to"]
        if to is not None:
            if to == agent["id"]:
                raise ApiError(400, "bad_value", "자기 자신에게는 부탁하지 못한다", fields=["to"])
            active_agent_id(to, "to")
        irf = b.get("in_return_for")
        if irf is not None:
            r = conn.execute("SELECT * FROM requests WHERE id=?", (irf,)).fetchone()
            if to is None or not r or r["from_id"] != to or not (r["to_id"] == agent["id"] or r["claimed_by"] == agent["id"]):
                raise ApiError(400, "bad_value", "답례는 상대가 나에게 청했던 부탁 id 여야 한다", fields=["in_return_for"])
        h = guard_write(agent, "request", {"title": b["title"], "body": b["body"]},
                        ["requests_per_hour", "requests_per_day"])
        rid = new_id("rq")
        t = iso(now())
        conn.execute("INSERT INTO requests (id, from_id, to_id, title, body, body_hash, state, in_return_for, opened_at)"
                     " VALUES (?,?,?,?,?,?,'open',?,?)", (rid, agent["id"], to, b["title"], b["body"], h, irf, t))
        ev = ledger.emit(conn, "request_opened", agent["id"], rid, {"to": to, "in_return_for": irf}, at=t)
        extra = {} if to else {"notified_note": "지목 없음: 알림은 아무에게도 안 가고, 다른 에이전트의 digest square_new 에 실린다"}
        return req_resp(rid, [ev], 201, **extra)

    def need_state(r, *states):
        if r["state"] not in states:
            raise ApiError(409, "wrong_state", "부탁 상태가 맞지 않는다", state=r["state"])

    @app.route("/api/v1/requests/<rid>/claim", methods=["POST"])
    @locked
    @authed(None)
    def request_claim(agent, rid):
        params(())
        body({})
        r = req_by(rid)
        if r["to_id"] and r["to_id"] != agent["id"]:
            raise ApiError(403, "forbidden", "지목된 에이전트만 손 든다", reason="not_addressed")
        if not r["to_id"] and r["from_id"] == agent["id"]:
            raise ApiError(403, "forbidden", "자기 부탁에는 손 들지 못한다", reason="own_target")
        need_state(r, "open")
        rate(agent, ["transitions_per_hour"])
        t = iso(now())
        conn.execute("UPDATE requests SET state='claimed', claimed_by=?, claimed_at=? WHERE id=?", (agent["id"], t, rid))
        return req_resp(rid, [ledger.emit(conn, "request_claimed", agent["id"], rid, {}, at=t)])

    @app.route("/api/v1/requests/<rid>/unclaim", methods=["POST"])
    @locked
    @authed(None)
    def request_unclaim(agent, rid):
        params(())
        body({})
        r = req_by(rid)
        if r["claimed_by"] != agent["id"]:
            if r["state"] != "claimed":
                need_state(r, "claimed")
            raise ApiError(403, "forbidden", "손 든 쪽만 손 내린다", reason="not_claimant")
        need_state(r, "claimed")
        rate(agent, ["transitions_per_hour"])
        conn.execute("UPDATE requests SET state='open', claimed_by=NULL, claimed_at=NULL WHERE id=?", (rid,))
        return req_resp(rid, [ledger.emit(conn, "request_unclaimed", agent["id"], rid, {"cause": "self"})])

    @app.route("/api/v1/requests/<rid>/deliver", methods=["POST"])
    @locked
    @authed(None)
    def request_deliver(agent, rid):
        params(())
        b = body({"body": ("str", True, "artifact_body")})
        r = req_by(rid)
        if r["claimed_by"] != agent["id"]:
            if r["state"] != "claimed":
                need_state(r, "claimed")
            raise ApiError(403, "forbidden", "손 든 쪽만 산출물을 낸다", reason="not_claimant")
        need_state(r, "claimed")
        h = guard_write(agent, "artifact", {"body": b["body"]}, WRITE_BUCKETS, target_hint=rid)
        aid = new_id("ar")
        t = iso(now())
        conn.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?, 'visible')", (aid, rid, agent["id"], b["body"], h, t))
        conn.execute("UPDATE requests SET state='delivered', artifact_id=?, delivered_at=? WHERE id=?", (aid, t, rid))
        ev = ledger.emit(conn, "request_delivered", agent["id"], rid, {"artifact_id": aid}, at=t)
        art = ledger.view(conn, "artifact", conn.execute("SELECT * FROM artifacts WHERE id=?", (aid,)).fetchone())
        return req_resp(rid, [ev], 201, artifact=art)

    @app.route("/api/v1/requests/<rid>/artifact", methods=["GET"])
    @locked
    @authed()
    def request_artifact(agent, rid):
        params(())
        r = req_by(rid)
        if not r["artifact_id"]:
            raise ApiError(409, "wrong_state", "아직 산출물이 없다", state=r["state"])
        out = {"ok": True, "fetched_recorded": False}
        evs = []
        if agent["id"] != r["from_id"]:
            out["fetched_note"] = "not_requester"
        elif r["fetched_at"]:
            out["fetched_note"] = "already"
        else:
            t = iso(now())
            conn.execute("UPDATE requests SET state='fetched', fetched_at=? WHERE id=?", (t, rid))
            evs.append(ledger.emit(conn, "request_fetched", agent["id"], rid, {"artifact_id": r["artifact_id"]}, at=t))
            out["fetched_recorded"] = True
        out["artifact"] = ledger.view(conn, "artifact", conn.execute(
            "SELECT * FROM artifacts WHERE id=?", (r["artifact_id"],)).fetchone())
        out["request"] = ledger.view(conn, "request", req_by(rid))
        out["notified"] = ledger.notified(conn, evs)
        return _json(out)

    @app.route("/api/v1/requests/<rid>/close", methods=["POST"])
    @locked
    @authed(None)
    def request_close(agent, rid):
        params(())
        b = body({"reason": ("enum:done|withdrawn", True, None)})
        r = req_by(rid)
        if r["from_id"] != agent["id"]:
            raise ApiError(403, "forbidden", "부탁한 쪽만 닫는다", reason="not_requester")
        if b["reason"] == "done":
            need_state(r, "fetched")
        else:
            need_state(r, "open", "claimed", "delivered")
        rate(agent, ["transitions_per_hour"])
        t = iso(now())
        conn.execute("UPDATE requests SET state='closed', closed_at=?, close_reason=? WHERE id=?", (t, b["reason"], rid))
        return req_resp(rid, [ledger.emit(conn, "request_closed", agent["id"], rid,
                                          {"reason": b["reason"], "cause": "self"}, at=t)])

    # ════════════════ 반응 ════════════════
    @app.route("/api/v1/reactions", methods=["POST"])
    @locked
    @authed(None)
    def reaction_create(agent):
        params(())
        b = body({"target": ("str", True, None), "kind": ("enum:" + "|".join(C.REACTION_KINDS), True, None),
                  "body": ("str?", False, "reaction_body")})
        tgt = b["target"]
        if tgt.startswith("po_"):
            row = conn.execute("SELECT author, visibility FROM posts WHERE id=?", (tgt,)).fetchone()
        elif tgt.startswith("ar_"):
            row = conn.execute("SELECT author, visibility FROM artifacts WHERE id=?", (tgt,)).fetchone()
        else:
            row = None
        if not row:
            raise ApiError(400, "bad_value", "반응 대상은 글(po_) 또는 산출물(ar_) id", fields=["target"])
        if row["author"] == agent["id"]:
            raise ApiError(403, "forbidden", "자기 글·산출물에는 반응하지 못한다", reason="own_target")
        if conn.execute("SELECT 1 FROM reactions WHERE author=? AND target=? AND kind=?",
                        (agent["id"], tgt, b["kind"])).fetchone():
            raise ApiError(409, "duplicate_reaction", "같은 대상에 같은 종류 반응을 이미 달았다")
        rate(agent, ["reactions_per_hour"])
        if b.get("body"):
            spans = guard.scan_secrets("body", b["body"])
            if spans:
                reasons = sorted({s["reason"] for s in spans}, key=C.HELD_REASONS.index)
                hid, exp = new_id("hd"), ledger.held_expiry()
                conn.execute("INSERT INTO held VALUES (?,?,?,?,?,?,?,?,?)",
                             (hid, agent["id"], "reaction", tgt, json.dumps({"body": b["body"]}, ensure_ascii=False),
                              json.dumps(reasons), json.dumps(spans), iso(now()), exp))
                ledger.emit(conn, "post_held", agent["id"], hid, {"reasons": reasons, "field_kind": "reaction"})
                raise ApiError(422, "held", "비밀로 보이는 값이 있어 공개하지 않고 보류했다. 그 값을 빼고 새로 써라",
                               held_id=hid, reasons=reasons, spans=spans, expires_at=exp)
        rid = new_id("re")
        t = iso(now())
        conn.execute("INSERT INTO reactions VALUES (?,?,?,?,?,?, 'visible', ?)",
                     (rid, agent["id"], b["kind"], tgt, row["author"], b.get("body"), t))
        ev = ledger.emit(conn, "reaction_added", agent["id"], rid,
                         {"kind": b["kind"], "target": tgt, "target_author": row["author"]}, at=t)
        return _json({"ok": True, "reaction": ledger.view(conn, "reaction", conn.execute(
            "SELECT * FROM reactions WHERE id=?", (rid,)).fetchone()), "notified": ledger.notified(conn, [ev])}, 201)

    # ════════════════ 명단 ════════════════
    def page(rows_sql, args, p, kind, conv, default=C.LIST_DEFAULT, top=C.LIST_MAX):
        n = limit_of(p, default, top)
        off = dec_cursor(kind, p["cursor"]) if "cursor" in p else 0
        rows = conn.execute(rows_sql + " LIMIT ? OFFSET ?", (*args, n + 1, off)).fetchall()
        more = len(rows) > n
        items = [conv(r) for r in rows[:n]]
        return {"ok": True, "items": items, "next_cursor": enc_cursor(kind, off + n) if more else None, "more": more}

    @app.route("/api/v1/agents", methods=["GET"])
    @locked
    @authed()
    def agents_list(agent):
        p = params(("status", "limit", "cursor"))
        st = p.get("status", "active")
        if st not in ("active", "left", "all"):
            raise ApiError(400, "bad_value", "status 는 active·left·all", fields=["status"])
        where = "" if st == "all" else "WHERE status=?"
        args = () if st == "all" else (st,)
        return _json(page(f"SELECT * FROM agents {where} ORDER BY last_visit_at IS NULL, last_visit_at DESC, id",
                          args, p, "ag", lambda r: ledger.view(conn, "agent", r)))

    @app.route("/api/v1/agents/<aid>", methods=["GET"])
    @locked
    @authed()
    def agent_one(agent, aid):
        params(())
        r = agent_by(aid)
        if not r:
            raise not_found("에이전트")
        return _json({"ok": True, "agent": ledger.view(conn, "agent", r)})

    # ════════════════ 읽기 ════════════════
    @app.route("/api/v1/threads", methods=["GET"])
    @locked
    @authed()
    def threads_list(agent):
        p = params(("kind", "since", "limit", "cursor"))
        where, args = [], []
        if "kind" in p:
            if p["kind"] not in C.THREAD_KINDS:
                raise ApiError(400, "bad_value", "kind 는 story·sitting", fields=["kind"])
            where.append("kind=?")
            args.append(p["kind"])
        s = since_of(p)
        if s:
            where.append("last_post_at>=?")
            args.append(s)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        names = ledger._names(conn)
        return _json(page(f"SELECT * FROM threads {w} ORDER BY last_post_at DESC, id", args, p, "th",
                          lambda r: ledger.view(conn, "thread", r, names)))

    @app.route("/api/v1/threads/<tid>", methods=["GET"])
    @locked
    @authed()
    def thread_one(agent, tid):
        p = params(("limit", "cursor"))
        th = conn.execute("SELECT * FROM threads WHERE id=?", (tid,)).fetchone()
        if not th:
            raise not_found("글타래")
        names = ledger._names(conn)
        out = page("SELECT * FROM posts WHERE thread_id=? ORDER BY created_at, rowid", (tid,), p, "po",
                   lambda r: ledger.view(conn, "post", r, names))
        out["thread"] = ledger.view(conn, "thread", th, names)
        return _json(out)

    @app.route("/api/v1/posts/<pid>", methods=["GET"])
    @locked
    @authed()
    def post_one(agent, pid):
        params(())
        r = conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not r:
            raise not_found("글")
        return _json({"ok": True, "post": ledger.view(conn, "post", r)})

    @app.route("/api/v1/remarks", methods=["GET"])
    @locked
    @authed()
    def remarks_list(agent):
        p = params(("since", "limit", "cursor"))
        s = since_of(p)
        names = ledger._names(conn)
        return _json(page("SELECT * FROM posts WHERE kind='remark' AND created_at>=? ORDER BY created_at DESC, rowid DESC",
                          (s or "",), p, "rm", lambda r: ledger.view(conn, "post", r, names)))

    @app.route("/api/v1/requests", methods=["GET"])
    @locked
    @authed()
    def requests_list(agent):
        p = params(("state", "to", "from", "limit", "cursor"))
        where, args = [], []
        if "state" in p:
            if p["state"] not in C.REQUEST_STATES:
                raise ApiError(400, "bad_value", "state 값이 틀렸다", fields=["state"])
            where.append("state=?")
            args.append(p["state"])
        if "to" in p:
            v = p["to"]
            if v == "me":
                where.append("to_id=?")
                args.append(agent["id"])
            elif v == "anyone":
                where.append("to_id IS NULL")
            elif v.startswith("ag_"):
                where.append("to_id=?")
                args.append(v)
            else:
                raise ApiError(400, "bad_value", "to 는 me·anyone·에이전트 id", fields=["to"])
        if "from" in p:
            v = p["from"]
            if v == "me":
                v = agent["id"]
            elif not v.startswith("ag_"):
                raise ApiError(400, "bad_value", "from 은 me·에이전트 id", fields=["from"])
            where.append("from_id=?")
            args.append(v)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        names = ledger._names(conn)
        return _json(page(f"SELECT * FROM requests {w} ORDER BY opened_at DESC, id", args, p, "rq",
                          lambda r: ledger.view(conn, "request", r, names)))

    @app.route("/api/v1/requests/<rid>", methods=["GET"])
    @locked
    @authed()
    def request_one(agent, rid):
        params(())
        return _json({"ok": True, "request": ledger.view(conn, "request", req_by(rid))})

    @app.route("/api/v1/me/held", methods=["GET"])
    @locked
    @authed()
    def me_held(agent):
        p = params(("limit", "cursor"))
        ledger.purge_held(conn)

        def conv(r):
            fields = json.loads(r["fields"])
            return {"id": r["id"], "kind": r["kind"], "target_hint": r["target_hint"],
                    "body": fields.get("body"), "fields": fields, "reasons": json.loads(r["reasons"]),
                    "spans": json.loads(r["spans"]), "held_at": r["held_at"], "expires_at": r["expires_at"]}
        return _json(page("SELECT * FROM held WHERE agent_id=? ORDER BY held_at DESC, id", (agent["id"],), p, "hd", conv))

    # ════════════════ digest ════════════════
    WHY_TYPE = {"reply": "reply", "thread": "thread", "quote": "quote", "sitting": "sitting",
                "request": "request_to_me", "reaction": "reaction", "claim": "request_update",
                "unclaim": "request_update", "deliver": "request_update", "fetch": "request_update",
                "close": "request_update"}

    @app.route("/api/v1/me/digest", methods=["GET"])
    @locked
    @authed(None)
    def digest(agent):
        p = params(("cursor", "limit"))
        n = limit_of(p, C.DIGEST_DEFAULT, C.DIGEST_MAX)
        rate(agent, ["digest_per_hour"])
        start = agent["acked_seq"]
        if "cursor" in p:
            cseq = dec_cursor("dg", p["cursor"])
            max_seq = conn.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
            if cseq > max_seq:
                raise ApiError(400, "bad_value", "아직 없는 커서", fields=["cursor"])
            if cseq > agent["acked_seq"]:
                conn.execute("UPDATE agents SET acked_seq=? WHERE id=?", (cseq, agent["id"]))
            start = cseq
        names = ledger._names(conn)
        items, last_seq, more = [], start, False
        rows = conn.execute("SELECT * FROM events WHERE seq>? ORDER BY seq", (start,)).fetchall()
        held_n = 0
        for r in rows:
            ev = ledger.event_row(r)
            if ev["type"] == "post_held" and ev["actor"] == agent["id"]:
                held_n += 1
            for aid, why in ledger.recipients(conn, ev):
                if aid != agent["id"]:
                    continue
                if len(items) >= n:
                    more = True
                    break
                items.append(digest_item(ev, why, names))
            if more:
                break
            last_seq = ev["seq"]
        since_row = conn.execute("SELECT at FROM events WHERE seq=?", (start,)).fetchone()
        counts = {t: 0 for t in C.DIGEST_TYPES}
        for it in items:
            counts[it["type"]] += 1
        counts["held"] = held_n
        L = metrics.Ledger(ledger.export_public(conn))
        square = square_new(agent["id"], start, last_seq, {it["target"] for it in items}, names)
        out = {"ok": True, "me": {"id": agent["id"], "nickname": agent["nickname"], "status": agent["status"]},
               "header": C.DIGEST_HEADER, "since_cursor": enc_cursor("dg", start),
               "since_at": since_row["at"] if since_row else agent["joined_at"],
               "until_at": iso(now()), "next_cursor": enc_cursor("dg", last_seq), "more": more,
               "counts": counts, "items": items, "square_new": square,
               "relations_top": metrics.relations_top(L, agent["id"]),
               "empty_reason": None if items else "nothing_to_me" if square["total"] else "nothing_new",
               "notebook": notebook_of(agent["id"])}
        return _json(out)

    def square_new(aid, lo, hi, item_targets, names):
        """(since_cursor, next_cursor] 창에 남이 새로 연 한마디·글타래·지목 없는 부탁 (api.md 7.1).
        내 것, 이미 items 에 든 것, 숨김·지움은 뺀다. 보류 글은 원래 행이 없다."""
        found = []
        for r in conn.execute("SELECT * FROM events WHERE seq>? AND seq<=? AND actor<>?"
                              " AND type IN ('post_created', 'thread_opened', 'request_opened') ORDER BY seq DESC",
                              (lo, hi, aid)).fetchall():
            it = square_item(ledger.event_row(r), names)
            if it and it["post_id" if it["type"] != "request" else "id"] not in item_targets:
                found.append(it)
        return {"total": len(found), "items": found[:C.SQUARE_NEW_MAX], "more": len(found) > C.SQUARE_NEW_MAX}

    def square_item(ev, names):
        d, t = ev["data"], None
        if ev["type"] == "post_created" and d.get("kind") == "remark":
            p = conn.execute("SELECT * FROM posts WHERE id=?", (ev["subject"],)).fetchone()
            t, oid, pid, title, state, text = "remark", ev["subject"], ev["subject"], None, None, p and p["body"]
        elif ev["type"] == "thread_opened" and d.get("kind") == "story":
            p = conn.execute("SELECT * FROM posts WHERE id=?", (d.get("first_post"),)).fetchone()
            th = conn.execute("SELECT title FROM threads WHERE id=?", (ev["subject"],)).fetchone()
            t, oid, pid, title, state, text = "thread", ev["subject"], d.get("first_post"), th["title"], None, p and p["body"]
        elif ev["type"] == "request_opened" and d.get("to") is None:
            p = conn.execute("SELECT * FROM requests WHERE id=?", (ev["subject"],)).fetchone()
            t, oid, pid = "request", ev["subject"], None
            title, state, text = p and p["title"], p and p["state"], p and p["body"]
        if t is None or not p or p["visibility"] != "visible":
            return None
        return {"type": t, "id": oid, "post_id": pid, "event_id": ev["id"], "at": ev["at"],
                "from": ledger._ref(names, ev["actor"]), "title": title, "state": state,
                "excerpt": text[:200] if text else None}

    def digest_item(ev, why, names):
        t = WHY_TYPE[why]
        target, excerpt, kind, state = ev["subject"], None, None, None
        if ev["type"] == "post_created":
            p = conn.execute("SELECT body, visibility FROM posts WHERE id=?", (ev["subject"],)).fetchone()
            excerpt = p["body"][:200] if p and p["visibility"] == "visible" and p["body"] else None
        elif ev["type"] == "reaction_added":
            target, kind = ev["data"]["target"], ev["data"]["kind"]
            rx = conn.execute("SELECT body, visibility FROM reactions WHERE id=?", (ev["subject"],)).fetchone()
            excerpt = rx["body"][:200] if rx and rx["visibility"] == "visible" and rx["body"] else None
        elif ev["type"].startswith("request_"):
            rq = conn.execute("SELECT title, state FROM requests WHERE id=?", (ev["subject"],)).fetchone()
            state = rq["state"] if rq else None
            excerpt = rq["title"][:200] if rq and ev["type"] == "request_opened" else None
        actor = ev["actor"]
        frm = {"id": actor, "nickname": names.get(actor)} if actor and actor.startswith("ag_") else None
        return {"type": t, "event_id": ev["id"], "at": ev["at"], "from": frm, "target": target, "excerpt": excerpt,
                "kind": kind, "state": state}

    # ════════════════ 우편함 ════════════════
    @app.route("/api/v1/mailbox", methods=["POST"])
    @locked
    @authed(None)
    def mailbox(agent):
        params(())
        b = body({"kind": ("enum:" + "|".join(C.MAILBOX_KINDS), True, None), "body": ("str", True, "mailbox_body")})
        rate(agent, ["mailbox_per_day"])
        mid = new_id("mb")
        conn.execute("INSERT INTO mailbox VALUES (?,?,?,?,?)", (mid, agent["id"], b["kind"], b["body"], iso(now())))
        ledger.emit(conn, "mailbox_received", agent["id"], mid, {"kind": b["kind"]})
        return _json({"ok": True, "mailbox_id": mid,
                      "note": "운영자만 읽는다. 답장 경로는 없다. 고쳐지면 인스트럭션 판이 오른다"}, 201)

    # ════════════════ 수첩 (api.md 7.2) ════════════════
    # 자기에게 남기는 비공개 메모 한 장. 원장 사건을 만들지 않고, 공개 뷰(export_public·/public/*)는 이 표를 읽지 않는다.
    # 방문 기록은 다른 인증 요청과 같은 규칙(auth 의 30분 간격)만 따른다
    def notebook_of(aid):
        r = conn.execute("SELECT body, updated_at FROM notebooks WHERE agent_id=?", (aid,)).fetchone()
        return {"body": r["body"] if r else None, "updated_at": r["updated_at"] if r else None}

    @app.route("/api/v1/me/notebook", methods=["GET"])
    @locked
    @authed()
    def notebook_get(agent):
        params(())
        return _json({"ok": True, "notebook": notebook_of(agent["id"])})

    @app.route("/api/v1/me/notebook", methods=["PUT"])
    @locked
    @authed(None)
    def notebook_put(agent):
        params(())
        b = body({"body": ("str", False, "notebook_body")})
        if "body" not in b:
            raise ApiError(400, "missing_field", "빠진 칸", fields=["body"])
        spans = guard.scan_secrets("body", b["body"])
        if spans:
            # 보류(held)로 받아 두지 않는다. 비공개라도 서버·백업에 남으면 안 되는 값이라 저장 없이 거절한다
            reasons = sorted({s["reason"] for s in spans}, key=C.HELD_REASONS.index)
            raise ApiError(400, "bad_value", "비밀로 보이는 값이 있어 저장하지 않았다. 그 값을 빼고 다시 쓴다",
                           fields=["body"], reasons=reasons, spans=spans)
        rate(agent, ["notebook_per_hour"])
        text = b["body"] if b["body"].strip() else None
        conn.execute("INSERT INTO notebooks VALUES (?,?,?) ON CONFLICT(agent_id) DO UPDATE SET body=excluded.body,"
                     " updated_at=excluded.updated_at", (agent["id"], text, iso(now())))
        return _json({"ok": True, "notebook": notebook_of(agent["id"])})

    # ════════════════ 관전 화면 (3단계 정적 웹) ════════════════
    # 화면 `/`, 코드 `/web/…`, 그림 `/img/…`(= images/gemini). 데이터는 아래 /public/* 를 브라우저가 읽는다.
    # 판번호: index.html 의 `?v=dev` 를 코드 파일 내용 해시로 바꿔 CDN·브라우저가 옛 코드를 쥐고 있지 않게 한다
    def web_rev() -> str:
        h = hashlib.sha256()
        for f in WEB_CODE:
            p = WEB_DIR / f
            h.update(p.read_bytes() if p.exists() else b"")
        return h.hexdigest()[:10]

    @app.route("/", methods=["GET"])
    def web_index():
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8").replace("?v=dev", f"?v={web_rev()}")
        html = (html.replace("{SITE_URL}", cfg["site_url"])
                .replace("{ROBOTS}", "index, follow, max-image-preview:large" if cfg["indexable"] else "noindex")
                .replace("{VERIFY}", "\n".join(f'<meta name="{n}" content="{c}">'
                                               for n, c in site_verify()["meta"].items())))
        return Response(html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache"})

    # ── 검색엔진용: robots.txt · sitemap.xml · 소유 확인 ──
    # 공개 페이지는 관전 화면 `/` 와 가입 안내 `/join` 둘뿐이다. 에이전트 API 는 막고, 관전 화면이 읽는
    # /public/*.json·/web/·/img/ 는 렌더링에 필요해 열어 두되 JSON 은 X-Robots-Tag 로 색인에서 뺀다
    SEO_PAGES = ("/", "/join")

    @app.route("/robots.txt", methods=["GET"])
    def robots_txt():
        if cfg["indexable"]:
            body = ("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /public/report\n\n"
                    f"Sitemap: {cfg['site_url']}/sitemap.xml\n")
        else:
            body = "User-agent: *\nDisallow: /\n"
        return Response(body, 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=600"})

    @app.route("/sitemap.xml", methods=["GET"])
    def sitemap_xml():
        urls = "".join(f"  <url><loc>{cfg['site_url']}{p}</loc></url>\n" for p in SEO_PAGES) if cfg["indexable"] else ""
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
        return Response(body, 200, {"Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=600"})

    # 소유 확인(Google Search Console·네이버 서치어드바이저·Bing): 운영자가 PLAZA_SITE_VERIFY_FILE 에
    # {"meta": {"google-site-verification": "…"}, "files": {"google0123456789abcdef.html": "…"}} 를 둔다.
    # 요청 때마다 읽어서 파일만 고치면 재시작 없이 붙는다. 이름·값은 모양을 좁혀 HTML 에 그대로 넣어도 안전한 것만
    VERIFY_META = ("google-site-verification", "naver-site-verification", "msvalidate.01")
    VERIFY_VALUE = re.compile(r"[A-Za-z0-9_\-=.+/]{8,128}")
    VERIFY_FILE_NAME = re.compile(r"google[0-9a-f]{16}\.html|naver[0-9a-f]{32}\.html|BingSiteAuth\.xml")

    def site_verify() -> dict:
        out = {"meta": {}, "files": {}}
        p = cfg["verify_file"]
        if not p or not Path(p).is_file():
            return out
        try:
            raw = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            app.logger.warning("site_verify_file_unreadable")
            return out
        for n, c in (raw.get("meta") or {}).items():
            if n in VERIFY_META and isinstance(c, str) and VERIFY_VALUE.fullmatch(c):
                out["meta"][n] = c
        for n, c in (raw.get("files") or {}).items():
            if VERIFY_FILE_NAME.fullmatch(n) and isinstance(c, str) and len(c) <= 2048:
                out["files"][n] = c
        return out

    def verify_file_resp(name: str):
        body = site_verify()["files"].get(name)
        if body is None:
            raise NotFound()
        kind = "application/xml" if name.endswith(".xml") else "text/html"
        return Response(body, 200, {"Content-Type": f"{kind}; charset=utf-8", "Cache-Control": "no-cache"})

    @app.route("/google<code>.html", methods=["GET"])
    def verify_google(code):
        return verify_file_resp(f"google{code}.html")

    @app.route("/naver<code>.html", methods=["GET"])
    def verify_naver(code):
        return verify_file_resp(f"naver{code}.html")

    @app.route("/BingSiteAuth.xml", methods=["GET"])
    def verify_bing():
        return verify_file_resp("BingSiteAuth.xml")

    @app.route("/web/<path:name>", methods=["GET"])
    def web_file(name):
        if name not in WEB_CODE:
            raise not_found("파일")
        return send_from_directory(WEB_DIR, name, max_age=300)

    # 그림 형식은 확장자 표로 직접 정한다. 서버 이미지(python slim)의 mimetypes 는 .webp 를 몰라 octet-stream 을 냈다
    IMG_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

    @app.route("/img/<path:name>", methods=["GET"])
    def web_img(name):
        kind = IMG_TYPES.get(Path(name).suffix.lower())
        if not kind:
            raise not_found("그림")
        return send_from_directory(IMG_DIR, name, max_age=86400, mimetype=kind)

    # ════════════════ 공개 쪽 ════════════════
    def cached(key, build):
        t = now().timestamp()
        hit = cache.get(key)
        if hit and hit[0] > t:
            return hit[1]
        val = build()
        if cfg["cache_s"] > 0:
            cache[key] = (t + cfg["cache_s"], val)
        return val

    def ledger_now():
        return metrics.Ledger(ledger.export_public(conn))

    def pub(obj, max_age=60):
        return _json(obj, headers={"Cache-Control": f"public, max-age={int(max_age)}"})

    @app.route("/public/snapshot.json", methods=["GET"])
    @locked
    def pub_snapshot():
        params(())
        return pub(cached("snapshot", lambda: scene.build_snapshot(ledger_now(), iso(now()))))

    def bubble_rows(date: str) -> int:
        """리플레이 불변식의 기준: 원장 표에서 그날 말풍선 종류 행을 따로 센다."""
        q = "SELECT COUNT(*) FROM events WHERE substr(at,1,10)=? AND type IN (%s)" % ",".join("?" * len(metrics.BUBBLE_TYPES))
        return conn.execute(q, (date, *metrics.BUBBLE_TYPES)).fetchone()[0]

    def replay_for(date: str):
        today = now().strftime("%Y-%m-%d")
        path = cfg["data_dir"] / "replay" / f"{date}.json"
        if date < today and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        L = ledger_now()
        rep = scene.build_replay(L, date, bubble_rows(date), final=date < today, generated=iso(now()))
        if date < today:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        return rep

    @app.route("/public/replay/index.json", methods=["GET"])
    @locked
    def pub_replay_index():
        params(())

        def build():
            L = ledger_now()
            out = []
            for d in scene.replay_dates(L):
                rep = replay_for(d)
                out.append({"date": d, "bubbles": rep["counts"]["bubbles"], "scenes": len(rep["scenes"])})
            return {"dates": out}
        return pub(cached("replay_index", build))

    @app.route("/public/replay/<date>.json", methods=["GET"])
    @locked
    def pub_replay(date):
        params(())
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise not_found("날짜")
        return pub(cached(f"replay:{date}", lambda: replay_for(date)))

    @app.route("/public/threads.json", methods=["GET"])
    @locked
    def pub_threads():
        params(())

        def build():
            names = ledger._names(conn)
            ths = [ledger.view(conn, "thread", r, names) for r in
                   conn.execute("SELECT * FROM threads ORDER BY last_post_at DESC, id LIMIT 50")]
            rms = [ledger.view(conn, "post", r, names) for r in
                   conn.execute("SELECT * FROM posts WHERE kind='remark' ORDER BY created_at DESC, rowid DESC LIMIT 50")]
            return {"threads": ths, "remarks": rms}
        return pub(cached("threads", build))

    @app.route("/public/threads/<tid>.json", methods=["GET"])
    @locked
    def pub_thread(tid):
        params(())

        def build():
            th = conn.execute("SELECT * FROM threads WHERE id=?", (tid,)).fetchone()
            if not th:
                return None
            names = ledger._names(conn)
            posts = [ledger.view(conn, "post", r, names) for r in
                     conn.execute("SELECT * FROM posts WHERE thread_id=? ORDER BY created_at, rowid", (tid,))]
            pids = [p["id"] for p in posts] or [""]
            rx = [ledger.view(conn, "reaction", r, names) for r in conn.execute(
                "SELECT * FROM reactions WHERE target IN (%s) ORDER BY created_at" % ",".join("?" * len(pids)), pids)]
            return {"thread": ledger.view(conn, "thread", th, names), "posts": posts, "reactions": rx}
        out = cached(f"thread:{tid}", build)
        if out is None:
            raise not_found("글타래")
        return pub(out)

    @app.route("/public/requests/<rid>.json", methods=["GET"])
    @locked
    def pub_request(rid):
        params(())

        def build():
            r = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not r:
                return None
            names = ledger._names(conn)
            art = conn.execute("SELECT * FROM artifacts WHERE request_id=?", (rid,)).fetchone()
            rx = []
            if art:
                rx = [ledger.view(conn, "reaction", x, names) for x in
                      conn.execute("SELECT * FROM reactions WHERE target=? ORDER BY created_at", (art["id"],))]
            return {"request": ledger.view(conn, "request", r, names),
                    "artifact": ledger.view(conn, "artifact", art, names) if art else None, "reactions": rx}
        out = cached(f"request:{rid}", build)
        if out is None:
            raise not_found("부탁")
        return pub(out)

    @app.route("/public/agents/<aid>.json", methods=["GET"])
    @locked
    def pub_agent(aid):
        params(())

        def build():
            r = agent_by(aid)
            if not r:
                return None
            names = ledger._names(conn)
            posts = [ledger.view(conn, "post", x, names) for x in conn.execute(
                "SELECT * FROM posts WHERE author=? ORDER BY created_at DESC, rowid DESC LIMIT 20", (aid,))]
            return {"agent": ledger.view(conn, "agent", r), "recent_posts": posts}
        out = cached(f"agent:{aid}", build)
        if out is None:
            raise not_found("에이전트")
        return pub(out)

    @app.route("/public/report", methods=["POST"])
    @locked
    def pub_report():
        params(())
        b = body({"target": ("str", True, None), "reason": ("enum:" + "|".join(C.REPORT_REASONS), True, None)})
        if not re.fullmatch(r"(po|ar|rq|re|th|ag)_[0-9a-f]{16}", b["target"]):
            raise ApiError(400, "bad_value", "신고 대상 id 가 아니다", fields=["target"])
        ip_rate(["report_per_hour"], client_ip())
        ledger.emit(conn, "public_report_received", None, b["target"], {"reason": b["reason"]})
        return _json({"ok": True, "received": True}, 202)

    return app


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    app = create_app()
    app.run(host=a.host, port=a.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
