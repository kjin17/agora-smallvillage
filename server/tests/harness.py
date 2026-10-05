"""시험 하네스: 임시 폴더에 새 SQLite 로 서버를 실제 프로세스로 띄우고 HTTP 로만 부른다.
소스를 읽거나 컴파일하는 것으로 검증을 대신하지 않는다(컴파일은 이름 해석을 안 한다)."""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Resp:
    def __init__(self, method, path, status, headers, raw: bytes):
        self.method, self.path, self.status, self.headers, self.raw = method, path, status, headers, raw
        self.ctype = headers.get("Content-Type", "")
        self.text = raw.decode("utf-8", "replace")
        self.json = None
        if "json" in self.ctype:
            try:
                self.json = json.loads(self.text)
            except ValueError:
                pass

    def __getitem__(self, k):
        return self.json[k]

    def get(self, k, default=None):
        return (self.json or {}).get(k, default)

    def __repr__(self):
        return f"<{self.method} {self.path} {self.status} {self.text[:200]}>"


class Server:
    def __init__(self, workdir: str | None = None, cache_s: float = 0, base_url: str | None = None,
                 env: dict | None = None):
        self.dir = Path(workdir or tempfile.mkdtemp(prefix="plaza-test-"))
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self.db = self.dir / "plaza.db"
        self.secret = self.dir / "secret"
        if not self.secret.exists():
            self.secret.write_text(secrets.token_urlsafe(48))
            os.chmod(self.secret, 0o600)
        self.clock = self.dir / "clock"
        self.clock.write_text("0")
        self.operators = self.dir / "operators.json"
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.base_url = base_url or self.url
        self.cache_s = cache_s
        self.proc = None
        self.log: list[Resp] = []   # 모든 응답 (두 번째 대조가 읽는다)
        self.offset = 0.0
        # 시험 서버는 바깥 날씨 출처를 부르지 않는다(기본 꺼짐). 날씨 시험만 가짜 출처 주소와 함께 켠다
        self.env = {"PLAZA_WEATHER": "off", **(env or {})}

    # ── 프로세스 ──
    def start(self):
        env = dict(os.environ, PLAZA_DB=str(self.db), PLAZA_SECRET_FILE=str(self.secret),
                   PLAZA_BASE_URL=self.base_url, PLAZA_OPERATORS_FILE=str(self.operators),
                   PLAZA_PUBLIC_CACHE_S=str(self.cache_s), PLAZA_CLOCK_FILE=str(self.clock),
                   PYTHONPATH=str(REPO), **self.env)
        self.stderr = open(self.dir / "server.log", "ab")
        self.proc = subprocess.Popen([sys.executable, "-m", "server.plaza.app", "--port", str(self.port)],
                                     cwd=REPO, env=env, stdout=self.stderr, stderr=self.stderr)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.url + "/api/v1/characters", timeout=1).read()
                return self
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("서버가 뜨다 죽었다: " + (self.dir / "server.log").read_text()[-2000:])
                time.sleep(0.1)
        raise RuntimeError("서버가 10초 안에 안 떴다")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            self.proc = None
            self.stderr.close()

    def restart(self):
        self.stop()
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        if self.base_url.startswith("http://127.0.0.1:"):
            self.base_url = self.url
        return self.start()

    def set_operators(self, ids: list[str]):
        self.operators.write_text(json.dumps({"operator_agents": ids}))

    # ── 시계 ──
    def advance(self, seconds: float):
        """서버 시계를 민다 (PLAZA_CLOCK_FILE). 속도 제한 창·재시도 창·방문 간격이 같이 움직인다."""
        self.offset += seconds
        self.clock.write_text(str(self.offset))

    # ── HTTP ──
    def req(self, method: str, path: str, body=None, key: str | None = None, raw: bytes | None = None,
            headers: dict | None = None) -> Resp:
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h.setdefault("Content-Type", "application/json; charset=utf-8")
        if key:
            h["Authorization"] = f"Bearer {key}"
        rq = urllib.request.Request(self.url + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(rq, timeout=30) as r:
                resp = Resp(method, path, r.status, dict(r.headers), r.read())
        except urllib.error.HTTPError as e:
            resp = Resp(method, path, e.code, dict(e.headers), e.read())
        self.log.append(resp)
        return resp

    def get(self, path, key=None, **kw):
        return self.req("GET", path, key=key, **kw)

    def post(self, path, body=None, key=None, **kw):
        return self.req("POST", path, body=body if body is not None else ({} if kw.get("raw") is None else None),
                        key=key, **kw)


class Checks:
    """판정 모음. 실패도 그대로 적는다(통과만 내는 자도 부러진 자)."""

    def __init__(self):
        self.rows: list[dict] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append({"name": name, "ok": bool(ok), "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""), flush=True)
        return bool(ok)

    def expect(self, name: str, resp: Resp, status: int, error: str | None = None, **fields) -> bool:
        ok = resp.status == status and resp.json is not None
        if error is not None:
            ok = ok and resp.get("error") == error
        for k, v in fields.items():
            ok = ok and resp.get(k) == v
        return self.check(name, ok, "" if ok else repr(resp)[:300])

    @property
    def failed(self):
        return [r for r in self.rows if not r["ok"]]
