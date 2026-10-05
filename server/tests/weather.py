"""배경용 실제 날씨 (snapshot-plaza.md 5절). 출처는 이 시험이 띄운 가짜 HTTP 서버다(바깥 네트워크 안 씀).

  python3 -m server.tests.weather

1. 범주 매핑: WMO 코드 경계값 전부(각 범위의 양 끝과 바로 바깥), 정수 아님·참거짓
2. 실패 경로(모듈 안에서): 정상 → 타임아웃·5xx·200 + HTML·깨진 JSON·current 없음·모르는 코드·is_day 이상 → 마지막 정상값 유지,
   실패 종류별 계수. 정상값이 6시간 넘으면 버림(null), 처음부터 실패만 하면 null(화면은 지금 배경)
3. 실제 서버(HTTP): 출처가 느려도(8초) /public/weather.json·스냅샷이 1초 안에 200, 출처가 죽은 채 떠도 문이 200 + null,
   공개 칸에 좌표·원시 값 없음, 캐시 머리, 시험 서버 기본은 꺼짐(off)
옛 판(문·모듈이 없는 서버)에 대면 1·2 는 import 에서, 3 은 404 로 실패해야 한다. 칸이 없어도 예외로 죽지 않게 .get 으로 읽는다."""
from __future__ import annotations

import datetime as dt
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
from pathlib import Path

from .harness import Checks, Server

OK_BODY = {"latitude": 37.55, "longitude": 127.0, "utc_offset_seconds": 32400, "timezone": "Asia/Seoul",
           "current": {"time": "2026-10-05T21:00", "interval": 900, "weather_code": 63, "is_day": 0}}

# 경계값 → 기대 범주 (None = 모르는 코드, 출처 이상)
BOUNDS = {0: "clear", 1: "clear", 2: "cloudy", 3: "cloudy", 4: None, 44: None, 45: "fog", 48: "fog", 46: None, 47: None,
          49: None, 50: None, 51: "rain", 55: "rain", 56: "rain", 57: "rain", 61: "rain", 65: "rain", 66: "rain", 67: "rain",
          68: None, 70: None, 71: "snow", 75: "snow", 77: "snow", 78: None, 79: None, 80: "rain", 82: "rain", 83: None,
          84: None, 85: "snow", 86: "snow", 87: None, 94: None, 95: "storm", 96: "storm", 97: None, 98: None, 99: "storm",
          100: None, -1: None}
ODD = [True, False, "0", 2.0, None, [0]]


class FakeResp:
    def __init__(self, status, ctype, body: bytes):
        self.status, self._body = status, body
        self.headers = {"Content-Type": ctype} if ctype else {}

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(plan: list):
    """plan 의 다음 항목을 돌려준다: ("ok", body) · ("timeout",) · ("http", code) · ("raw", status, ctype, bytes)."""
    def op(req, timeout=None):
        step = plan.pop(0)
        if step[0] == "timeout":
            raise TimeoutError("timed out")
        if step[0] == "http":
            raise urllib.error.HTTPError(req.full_url, step[1], "x", {}, io.BytesIO(b""))
        if step[0] == "ok":
            return FakeResp(200, "application/json; charset=utf-8", json.dumps(step[1]).encode())
        return FakeResp(step[1], step[2], step[3])
    return op


def unit(C: Checks) -> dict:
    try:
        from server.plaza import weather as W
    except ImportError as e:
        C.check("날씨 모듈 있음", False, str(e))
        return {"unit": "모듈 없음"}
    bad = [f"{c}→{W.sky_of(c)} (기대 {want})" for c, want in BOUNDS.items() if W.sky_of(c) != want]
    C.check("WMO 코드 경계값 → 범주", not bad, "; ".join(bad))
    bad = [repr(v) for v in ODD if W.sky_of(v) is not None]
    C.check("정수 아닌 코드(참거짓·문자·실수·없음)는 범주 없음", not bad, ", ".join(bad))
    # 자 검사: 기대표를 하나 틀리게 바꾸면 위 대조가 잡는다
    C.check("자 검사: 틀린 기대(3→rain)를 「다름」으로", W.sky_of(3) != "rain")

    clock = [dt.datetime(2026, 10, 5, 21, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))]
    real_now, W.now = W.now, lambda: clock[0]
    try:
        return _unit_clock(C, W, clock)
    finally:
        W.now = real_now


def _unit_clock(C: Checks, W, clock) -> dict:
    cfg = dict(W.DEFAULTS)
    plan = [("ok", OK_BODY), ("timeout",), ("http", 503), ("raw", 200, "text/html; charset=utf-8", b"<html>maintenance</html>"),
            ("raw", 200, "application/json", b"{not json"), ("raw", 200, "application/json", b'{"hourly": {}}'),
            ("ok", {**OK_BODY, "current": {"weather_code": 42, "is_day": 1}}),
            ("ok", {**OK_BODY, "current": {"weather_code": 0, "is_day": 2}}),
            ("raw", 204, "application/json", b"")]
    w = W.Weather(cfg, url="http://fake.invalid/x", opener=opener_for(plan))
    first = w.fetch_once()
    v = w.view()
    C.check("정상 응답 → rain · night, state ok", first and v.get("state") == "ok" and (v.get("weather") or {}).get("sky") == "rain"
            and (v.get("weather") or {}).get("daylight") == "night" and (v.get("weather") or {}).get("label") == "비 · 밤", json.dumps(v)[:300])
    C.check("관측 시각은 출처의 시각대로", (v.get("weather") or {}).get("observed_at") == "2026-10-05T21:00:00+09:00", str(v.get("weather")))
    kinds = []
    for _ in range(8):
        clock[0] += dt.timedelta(minutes=15)
        r = w.fetch_once()
        kinds.append((r, w.last_error))
    v = w.view()
    want = ["timeout", "http_status", "not_json", "bad_json", "bad_json", "bad_value", "bad_value", "http_status"]
    C.check("실패 종류: 타임아웃·5xx·200+HTML·깨진 JSON·current 없음·모르는 코드·is_day 이상·204",
            [k for _, k in kinds] == want and not any(r for r, _ in kinds), str(kinds))
    C.check("실패 8번 뒤에도 마지막 정상값(비 · 밤), state stale", v.get("state") == "stale"
            and (v.get("weather") or {}).get("label") == "비 · 밤", json.dumps(v)[:300])
    f = v.get("fetch") or {}
    C.check("실패 계수: streak 8 · 24시간 8 · 종류별", f.get("fail_streak") == 8 and f.get("fails_24h") == 8
            and f.get("fails_24h_by_kind") == {"timeout": 1, "http_status": 2, "not_json": 1, "bad_json": 2, "bad_value": 2}, str(f))
    clock[0] += dt.timedelta(hours=6)
    v = w.view()
    C.check("정상값이 6시간 넘으면 버림 → weather null, state none", v.get("state") == "none" and v.get("weather") is None, json.dumps(v)[:200])
    clock[0] += dt.timedelta(hours=19)
    C.check("하루 지난 실패는 24시간 계수에서 빠짐", (w.view().get("fetch") or {}).get("fails_24h") == 0, str(w.view().get("fetch")))

    w2 = W.Weather(cfg, url="http://fake.invalid/x", opener=opener_for([("timeout",), ("http", 500)]))
    w2.fetch_once(), w2.fetch_once()
    v = w2.view()
    C.check("처음부터 실패만 → weather null(화면은 지금 배경), state none", v.get("weather") is None and v.get("state") == "none", json.dumps(v)[:200])

    def boom(req, timeout=None):
        raise RuntimeError("뜻밖의 예외")
    w3 = W.Weather(cfg, url="http://fake.invalid/x", opener=boom)
    C.check("뜻밖의 예외도 밖으로 안 샌다(network 로 셈)", w3.fetch_once() is False and w3.last_error == "network")
    off = W.Weather(dict(cfg, enabled=False), url="http://fake.invalid/x", opener=boom)
    C.check("꺼진 설정 → state off, 스레드 안 띄움", off.view().get("state") == "off" and off.start() is off)
    return {"unit": "ok"}


class Source(http.server.BaseHTTPRequestHandler):
    mode = "ok"
    hits = 0

    def do_GET(self):
        Source.hits += 1
        if Source.mode == "slow":
            time.sleep(8)
        if Source.mode == "dead":
            self.send_response(502)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>bad gateway</html>")
            return
        body = json.dumps(OK_BODY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def http_checks(C: Checks) -> dict:
    src = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Source)
    threading.Thread(target=src.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{src.server_address[1]}/v1/forecast"
    out = {}
    try:
        d = tempfile.mkdtemp(prefix="plaza-weather-")
        cfgf = Path(d) / "weather.json"
        cfgf.write_text(json.dumps({"lat": 37.5665, "lon": 126.978, "place": "서울", "interval_s": 300}))
        for mode in ("ok", "slow", "dead"):
            Source.mode, Source.hits = mode, 0
            S = Server(env={"PLAZA_WEATHER": "on", "PLAZA_WEATHER_URL": url, "PLAZA_WEATHER_FILE": str(cfgf)}).start()
            try:
                if mode != "slow":
                    for _ in range(50):          # 스레드의 첫 가져오기를 기다린다
                        if Source.hits and (S.get("/public/weather.json").json or {}).get("fetch", {}).get("last_try_at"):
                            break
                        time.sleep(0.1)
                t0 = time.time()
                r = S.get("/public/weather.json")
                dt_w = time.time() - t0
                t0 = time.time()
                snap = S.get("/public/snapshot.json")
                dt_s = time.time() - t0
                j = r.json or {}
                w = j.get("weather") or {}
                out[mode] = {"status": r.status, "state": j.get("state"), "weather": j.get("weather"), "ms": round(dt_w * 1000)}
                if mode == "ok":
                    C.check("서버: 출처 정상 → 200 · 비 · 밤 · state ok", r.status == 200 and w.get("label") == "비 · 밤"
                            and j.get("state") == "ok", r.text[:300])
                    raw = r.text
                    leaks = [k for k in ("latitude", "longitude", "37.5", "126.9", "127.0", "weather_code", "is_day", url)
                             if k in raw]
                    C.check("서버: 공개 칸에 좌표·원시 값·출처 주소 없음", not leaks, str(leaks))
                    C.check("서버: 캐시 머리 public, max-age=300", "max-age=300" in r.headers.get("Cache-Control", ""),
                            r.headers.get("Cache-Control", ""))
                    C.check("서버: 같은 칸 = snapshot-plaza.md 5절 틀(check_public)", _shape_ok(r), "")
                elif mode == "slow":
                    C.check(f"서버: 출처가 8초 걸려도 weather.json {dt_w*1000:.0f}ms · 스냅샷 {dt_s*1000:.0f}ms 안에 200",
                            r.status == 200 and snap.status == 200 and dt_w < 1.0 and dt_s < 2.0 and j.get("weather") is None,
                            r.text[:200])
                else:
                    C.check("서버: 출처 502 + HTML → 문은 200, weather null, 실패 계수 1 이상", r.status == 200
                            and j.get("weather") is None and (j.get("fetch") or {}).get("fails_24h", 0) >= 1
                            and (j.get("fetch") or {}).get("last_error") == "http_status" and snap.status == 200, r.text[:300])
                    log = (S.dir / "server.log").read_text(errors="replace")
                    C.check("서버: 실패가 로그에 한 줄(weather fetch_failed kind=…)", "weather fetch_failed kind=http_status" in log, log[-300:])
            finally:
                S.stop()
        S = Server().start()
        try:
            r = S.get("/public/weather.json")
            C.check("시험 서버 기본은 꺼짐: state off, 바깥 출처를 안 부름", r.status == 200 and (r.json or {}).get("state") == "off",
                    r.text[:200])
        finally:
            S.stop()
    finally:
        src.shutdown()
    return out


def _shape_ok(r) -> bool:
    from . import check_public
    obj = r.json
    if not isinstance(obj, dict) or not isinstance(obj.get("weather"), dict):
        return False
    w = check_public.Walker(check_public.spec_whitelist(), check_public.spec_event_types())
    shape = check_public.shape_for("/public/weather.json")
    if shape is None:
        return False
    w.walk(shape, obj)
    # 자 검사: 좌표 칸을 하나 끼우면 같은 틀이 잡아야 한다
    w2 = check_public.Walker(check_public.spec_whitelist(), check_public.spec_event_types())
    w2.walk(shape, dict(obj, weather=dict(obj["weather"], lat=37.5)))
    return not w.bad and bool(w2.bad)


def run(C: Checks) -> dict:
    return {"unit": unit(C), "http": http_checks(C)}


def main():
    C = Checks()
    out = run(C)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
