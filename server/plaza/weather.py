"""관전 화면 배경용 실제 날씨 (연출, PLAN 3.3). 규격: docs/spec/snapshot-plaza.md 5절.

서버가 Open-Meteo(키 없음) 현재 날씨를 15분마다 받아 메모리에 쥐고, /public/weather.json 으로 범주만 내보낸다
(맑음·구름·안개·비·눈·뇌우 + 낮·밤). 좌표·기온 같은 원시 값은 공개 칸에 넣지 않는다. 브라우저는 출처를 직접 부르지 않는다.

날씨는 장식이다. 이 모듈의 어떤 실패도 요청 경로로 새지 않는다:
  - 가져오기는 데몬 스레드 하나에서만 돈다. 공개 문은 메모리 값을 읽기만 한다(네트워크·잠금 대기 없음)
  - 출처가 죽거나 느리거나(타임아웃 4초) 이상한 값(5xx, 200 + HTML, 깨진 JSON, 모르는 코드)을 주면 마지막 정상값을 쓴다.
    정상값이 MAX_AGE_S 보다 오래됐거나 아예 없으면 weather 는 null 이고 화면은 지금 배경(활동 날씨 1.14)을 그대로 둔다
  - 실패는 종류별로 세어 공개 칸 fetch 에 싣고(운영 상태 잡이 읽는다) stderr 에 한 줄씩 남긴다(docker logs)

설정: PLAZA_WEATHER_FILE(JSON, 없으면 기본값) — {"enabled": true, "lat": .., "lon": .., "place": "서울", "interval_s": 900}.
기본 위치는 서울 시청 근처(광장 운영 시간대가 KST). 시험용: PLAZA_WEATHER=off 면 끈다, PLAZA_WEATHER_URL 로 출처 주소를 바꾼다.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .util import iso, now

SOURCE_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULTS = {"enabled": True, "lat": 37.5665, "lon": 126.9780, "place": "서울", "interval_s": 900}
TIMEOUT_S = 4.0
MAX_BYTES = 64 * 1024
MAX_AGE_S = 6 * 3600          # 이보다 오래된 정상값은 버린다(밤낮이 틀린 그림이 남지 않게)
UA = "agora-smallvillage-weather/1"

SKIES = ("clear", "cloudy", "fog", "rain", "snow", "storm")
SKY_KO = {"clear": "맑음", "cloudy": "구름", "fog": "안개", "rain": "비", "snow": "눈", "storm": "뇌우"}
DAYLIGHT_KO = {"day": "낮", "night": "밤"}
FAIL_KINDS = ("timeout", "network", "http_status", "not_json", "bad_json", "bad_value")


def sky_of(code) -> str | None:
    """WMO 날씨 코드 → 범주. 모르는 코드·정수 아님은 None (출처 이상으로 센다)."""
    if isinstance(code, bool) or not isinstance(code, int):
        return None
    if code in (0, 1):
        return "clear"                     # 맑음, 대체로 맑음
    if code in (2, 3):
        return "cloudy"                    # 구름 조금, 흐림
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"                      # 이슬비·어는 이슬비·비·어는 비·소나기
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"                      # 눈·싸락눈·눈 소나기
    if code in (95, 96, 99):
        return "storm"                     # 뇌우(우박 동반 포함)
    return None


class SourceError(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind


def parse(status: int, content_type: str | None, body: bytes) -> dict:
    """출처 응답 하나 → {sky, daylight, observed_at}. 이상하면 SourceError."""
    if status != 200:
        raise SourceError("http_status", str(status))
    if not (content_type or "").split(";")[0].strip().lower().endswith("json"):
        raise SourceError("not_json", (content_type or "없음")[:60])
    try:
        d = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise SourceError("bad_json", type(e).__name__)
    cur = d.get("current") if isinstance(d, dict) else None
    if not isinstance(cur, dict):
        raise SourceError("bad_json", "current 없음")
    sky = sky_of(cur.get("weather_code"))
    if sky is None:
        raise SourceError("bad_value", f"weather_code={str(cur.get('weather_code'))[:20]}")
    is_day = cur.get("is_day")
    if is_day not in (0, 1) or isinstance(is_day, bool):
        raise SourceError("bad_value", f"is_day={str(is_day)[:20]}")
    observed = None
    try:
        off = d.get("utc_offset_seconds", 0)
        tz = dt.timezone(dt.timedelta(seconds=int(off)))
        observed = iso(dt.datetime.fromisoformat(str(cur["time"])).replace(tzinfo=tz))
    except (KeyError, TypeError, ValueError):
        pass                               # 관측 시각은 보조 칸이다. 없어도 범주는 쓴다
    return {"sky": sky, "daylight": "day" if is_day == 1 else "night", "observed_at": observed}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    path = os.environ.get("PLAZA_WEATHER_FILE")
    if path and Path(path).exists():
        try:
            got = json.loads(Path(path).read_text(encoding="utf-8"))
            cfg.update({k: got[k] for k in DEFAULTS if k in got})
        except (OSError, ValueError) as e:
            print(f"weather config_unreadable {type(e).__name__} — 기본값으로", file=sys.stderr, flush=True)
    if os.environ.get("PLAZA_WEATHER") == "off":
        cfg["enabled"] = False
    try:
        cfg["lat"], cfg["lon"] = float(cfg["lat"]), float(cfg["lon"])
        cfg["interval_s"] = max(300, int(cfg["interval_s"]))
        if not (-90 <= cfg["lat"] <= 90 and -180 <= cfg["lon"] <= 180):
            raise ValueError("좌표 범위")
    except (TypeError, ValueError) as e:
        print(f"weather config_invalid {e} — 끔", file=sys.stderr, flush=True)
        cfg["enabled"] = False
    cfg["place"] = str(cfg.get("place") or "")[:20]
    return cfg


class Weather:
    """마지막 정상값과 실패 계수를 쥔다. fetch_once 는 예외를 밖으로 내지 않는다."""

    def __init__(self, cfg: dict | None = None, url: str | None = None, opener=None):
        self.cfg = cfg or load_config()
        base = url or os.environ.get("PLAZA_WEATHER_URL") or SOURCE_URL
        q = urllib.parse.urlencode({"latitude": self.cfg["lat"], "longitude": self.cfg["lon"],
                                    "current": "weather_code,is_day", "timezone": "auto"})
        self.url = f"{base}?{q}"
        self.opener = opener or urllib.request.urlopen
        self.lock = threading.Lock()
        self.good: dict | None = None          # {sky, daylight, observed_at, fetched_at(datetime)}
        self.last_try: dt.datetime | None = None
        self.last_error: str | None = None
        self.streak = 0
        self.ok_total = 0
        self.fails: collections.deque = collections.deque(maxlen=500)   # (시각, 종류)
        self._stop = threading.Event()

    # ── 가져오기 ──
    def _get(self) -> dict:
        req = urllib.request.Request(self.url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with self.opener(req, timeout=TIMEOUT_S) as r:
                return parse(r.status, r.headers.get("Content-Type"), r.read(MAX_BYTES))
        except SourceError:
            raise
        except urllib.error.HTTPError as e:
            raise SourceError("http_status", str(e.code))
        except TimeoutError:
            raise SourceError("timeout")
        except urllib.error.URLError as e:
            kind = "timeout" if isinstance(e.reason, TimeoutError) or "timed out" in str(e.reason) else "network"
            raise SourceError(kind, type(e.reason).__name__)
        except OSError as e:          # 읽는 도중 끊김 등
            raise SourceError("timeout" if "timed out" in str(e) else "network", type(e).__name__)

    def fetch_once(self) -> bool:
        t = now()
        try:
            got = self._get()
        except Exception as e:        # 무엇이 나도 장식 하나 못 그리는 것으로 끝난다
            kind = e.kind if isinstance(e, SourceError) else "network"
            with self.lock:
                self.last_try, self.last_error = t, kind
                self.streak += 1
                self.fails.append((t, kind))
                streak = self.streak
            print(f"weather fetch_failed kind={kind} streak={streak} detail={str(e)[:80]}", file=sys.stderr, flush=True)
            return False
        with self.lock:
            self.good = dict(got, fetched_at=t)
            self.last_try, self.last_error, self.streak = t, None, 0
            self.ok_total += 1
        return True

    # ── 공개 칸 ──
    def view(self) -> dict:
        t = now()
        with self.lock:
            good = self.good
            if not self.cfg["enabled"]:
                state = "off"
            elif good and (t - good["fetched_at"]).total_seconds() <= MAX_AGE_S:
                state = "ok" if self.streak == 0 else "stale"
            else:
                state, good = "none", None
            fails_24h = collections.Counter(k for at, k in self.fails if (t - at).total_seconds() <= 86400)
            fetch = {"last_ok_at": iso(self.good["fetched_at"]) if self.good else None,
                     "last_try_at": iso(self.last_try), "last_error": self.last_error,
                     "fail_streak": self.streak, "fails_24h": sum(fails_24h.values()),
                     "fails_24h_by_kind": {k: fails_24h[k] for k in FAIL_KINDS if fails_24h[k]}}
        w = None
        if good:
            w = {"sky": good["sky"], "daylight": good["daylight"], "observed_at": good["observed_at"],
                 "label": f"{SKY_KO[good['sky']]} · {DAYLIGHT_KO[good['daylight']]}"}
        return {"schema": 1, "generated": iso(t), "state": state, "source": "Open-Meteo",
                "place": self.cfg["place"], "weather": w, "fetch": fetch}

    # ── 스레드 ──
    def start(self) -> "Weather":
        if self.cfg["enabled"]:
            threading.Thread(target=self._loop, name="plaza-weather", daemon=True).start()
        return self

    def _loop(self):
        while not self._stop.is_set():
            self.fetch_once()
            self._stop.wait(self.cfg["interval_s"])

    def stop(self):
        self._stop.set()
