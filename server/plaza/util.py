"""시각·id·정규화·오류 봉투. 규격: docs/spec/README.md 1절."""
from __future__ import annotations

import datetime as dt
import os
import secrets
import unicodedata

KST = dt.timezone(dt.timedelta(hours=9))

ID_PREFIXES = ("ag", "th", "po", "rq", "ar", "re", "ev", "hd", "mb", "sc")


def _clock_offset() -> float:
    """시험 전용: PLAZA_CLOCK_FILE 이 있으면 그 안의 초만큼 시계를 민다.
    라우트를 하나 더 만들지 않으려고 파일로 둔다(문 목록 대조에 걸리지 않게)."""
    path = os.environ.get("PLAZA_CLOCK_FILE")
    if not path:
        return 0.0
    try:
        with open(path, encoding="utf-8") as f:
            return float(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0.0


def now() -> dt.datetime:
    base = dt.datetime.now(KST).replace(microsecond=0)
    return base + dt.timedelta(seconds=_clock_offset())


def iso(t: dt.datetime | None) -> str | None:
    if t is None:
        return None
    return t.astimezone(KST).replace(microsecond=0).isoformat()


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=KST)
    return t.astimezone(KST)


def kst_date(s: str) -> str:
    return parse_iso(s).strftime("%Y-%m-%d")


def new_id(prefix: str) -> str:
    assert prefix in ID_PREFIXES, prefix
    return f"{prefix}_{secrets.token_hex(8)}"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def cp_len(s: str) -> int:
    """길이는 NFC 뒤 코드포인트 수 (바이트 아님)."""
    return len(nfc(s))


# 숫자 끝의 받침: 영·일·삼·육·칠·팔 은 받침 있음
_DIGIT_BATCHIM = {"0": True, "1": True, "2": False, "3": True, "4": False, "5": False, "6": True, "7": True,
                  "8": True, "9": False}


def has_batchim(word: str) -> bool:
    """마지막 소리에 받침이 있나. 한글은 음절 코드로, 숫자는 읽는 소리로, 로마자는 흔한 끝소리만
    (l·m·n·ng·-le 는 받침, 나머지는 없음 — Pebble=페블, Mintleaf=민트리프). 끝의 기호·공백은 건너뛴다."""
    w = nfc(word or "").rstrip()
    while w and not w[-1].isalnum():
        w = w[:-1]
    if not w:
        return False
    c = w[-1]
    if "가" <= c <= "힣":
        return (ord(c) - 0xAC00) % 28 != 0
    if c in _DIGIT_BATCHIM:
        return _DIGIT_BATCHIM[c]
    return w.lower().endswith(("l", "m", "n", "ng", "le"))


# 받침 있을 때 / 없을 때
JOSA = {"이/가": ("이", "가"), "와/과": ("과", "와"), "은/는": ("은", "는"), "을/를": ("을", "를")}


def josa(word: str, pair: str) -> str:
    """word + 받침에 맞는 조사. josa("라일락", "이/가") → "라일락이", josa("솔바람", "와/과") → "솔바람과"."""
    with_b, without = JOSA[pair]
    return word + (with_b if has_batchim(word) else without)


class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str, **extra):
        super().__init__(error)
        self.status = status
        self.error = error
        self.message = message
        self.extra = extra
        self.headers: dict[str, str] = {}

    def body(self) -> dict:
        out = {"ok": False, "error": self.error, "message": self.message}
        out.update(self.extra)
        return out
