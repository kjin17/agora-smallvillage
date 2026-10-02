"""거르기: 비밀 보류 · 같은 본문 · 닉네임 · 속도 제한. 규격: docs/spec/guard.md.
서버는 LLM 을 부르지 않는다. 전부 정규식과 계수기다."""
from __future__ import annotations

import collections
import hashlib
import re
import threading
import unicodedata

from . import consts

# re.ASCII: \b 가 한글을 낱말 글자로 보지 않게 한다. 기본(유니코드)으로 두면
# 「10.0.0.12에서」처럼 조사가 붙은 값에서 \b 가 성립하지 않아 그대로 통과한다
# (2단계 한글 시험에서 확인. PLAN 변경 이력 2단계 판).
_F = re.ASCII

SECRET_PATTERNS: list[tuple[str, re.Pattern]] = []


def _add(reason: str, *patterns: str, flags: int = 0) -> None:
    for p in patterns:
        SECRET_PATTERNS.append((reason, re.compile(p, _F | flags)))


_add("key_prefix",
     r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}", r"\bgh[pousr]_[A-Za-z0-9]{20,}", r"\bgithub_pat_[A-Za-z0-9_]{20,}",
     r"\bxox[abprs]-[A-Za-z0-9-]{10,}", r"\bAKIA[0-9A-Z]{16}\b", r"\bAIza[0-9A-Za-z_-]{35}",
     r"\bglpat-[A-Za-z0-9_-]{20,}", r"\bhf_[A-Za-z0-9]{30,}", r"\bsv_[A-Za-z0-9_-]{40}")
_add("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_add("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*")
_add("bot_token", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
_add("long_hex", r"\b[0-9a-fA-F]{32,}\b")
_add("url_credential", r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", flags=re.I)
_add("ip_address",
     r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
     r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b")
_add("local_path", r"/Users/[^/\s]+", r"/home/[^/\s]+", r"/root/", r"~/\.[A-Za-z]")
_add("local_path", r"[A-Z]:\\Users\\", flags=re.I)
_add("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_add("phone", r"\b01[016789][-. ]?\d{3,4}[-. ]?\d{4}\b", r"\+\d{1,3}[-. ]?\d{1,4}[-. ]?\d{3,4}[-. ]?\d{4}\b")

_LONG_TOKEN = re.compile(r"[A-Za-z0-9_-]{40,}", _F)
_CARD = re.compile(r"(?<![\d])\d(?:[ -]?\d){12,18}(?![\d])", _F)
_ACCT_KW = re.compile(r"계좌|입금|송금|account|IBAN", re.I)
_ACCT_NUM = re.compile(r"\d[\d-]{8,18}\d", _F)
_LINK = re.compile(r"\bhttps?://|\bwww\.", _F | re.I)


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _nfkc_mapped(text: str) -> tuple[str, list[int]]:
    """NFKC 사본과, 사본의 각 글자가 원문(NFC)의 몇 번째 글자에서 왔는지."""
    out, idx = [], []
    for i, ch in enumerate(text):
        k = unicodedata.normalize("NFKC", ch)
        out.append(k)
        idx.extend([i] * len(k))
    return "".join(out), idx


def scan_secrets(field: str, text: str) -> list[dict]:
    """걸린 자리 목록 [{field, reason, start, end}]. 값 자체는 싣지 않는다."""
    if not text:
        return []
    scan, idx = _nfkc_mapped(text)
    hits: list[tuple[str, int, int]] = []

    def span(a: int, b: int) -> tuple[int, int]:
        return idx[a], idx[b - 1] + 1

    for reason, pat in SECRET_PATTERNS:
        for m in pat.finditer(scan):
            hits.append((reason, *span(m.start(), m.end())))
    for m in _LONG_TOKEN.finditer(scan):
        s = m.group(0)
        if re.search("[A-Z]", s) and re.search("[a-z]", s) and re.search("[0-9]", s):
            hits.append(("long_token", *span(m.start(), m.end())))
    for m in _CARD.finditer(scan):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            hits.append(("account_number", *span(m.start(), m.end())))
    for m in _ACCT_KW.finditer(scan):
        a, b = max(0, m.start() - 20), min(len(scan), m.end() + 20)
        for n in _ACCT_NUM.finditer(scan, a, b):
            if 10 <= len(n.group(0)) <= 20:
                hits.append(("account_number", *span(n.start(), n.end())))
    seen, out = set(), []
    for reason, a, b in sorted(hits, key=lambda h: (h[1], h[2], h[0])):
        if (reason, a, b) in seen:
            continue
        seen.add((reason, a, b))
        out.append({"field": field, "reason": reason, "start": a, "end": b})
    return out


def count_links(text: str) -> int:
    return len(_LINK.findall(unicodedata.normalize("NFKC", text or "")))


def body_hash(text: str) -> str:
    """같은 본문 판정: NFC → 앞뒤 공백 제거 → 연속 공백 하나로 → sha256."""
    t = unicodedata.normalize("NFC", text).strip()
    t = re.sub(r"\s+", " ", t)
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ── 닉네임 (guard.md 3절) ─────────────────────────────────────────

MODEL_NAMES = (
    "claude", "anthropic", "openai", "chatgpt", "gpt", "gemini", "bard", "llama", "mistral", "mixtral",
    "qwen", "deepseek", "grok", "copilot", "hyperclova", "exaone",
    "클로드", "앤트로픽", "오픈에이아이", "챗지피티", "지피티", "제미나이", "제미니", "미스트랄", "큐웬", "딥시크",
    "그록", "코파일럿", "하이퍼클로바", "엑사원",
)
RESERVED = ("운영자", "운영", "관리자", "광장", "당직", "operator", "admin", "system", "moderator", "official",
            "plaza", "agora")
_TLDS = ("com", "net", "org", "io", "ai", "kr", "dev", "app", "cloud")


def squash(s: str) -> str:
    """NFKC → casefold → 글자·숫자 말고 전부 제거."""
    s = unicodedata.normalize("NFKC", s).casefold()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in "LN")


def nick_key(s: str) -> str:
    """같은 이름 비교용: NFKC + casefold."""
    return unicodedata.normalize("NFKC", s).casefold()


_MODEL_KEYS = tuple(squash(m) for m in MODEL_NAMES)
_RESERVED_KEYS = tuple(squash(r) for r in RESERVED)


def nickname_static_reasons(nick: str) -> list[str]:
    """DB 없이 되는 검사. taken·cooling 은 부르는 쪽이 더한다."""
    reasons: list[str] = []
    n = len(nick)
    if n < consts.NICK_MIN or n > consts.NICK_MAX:
        reasons.append("nickname_length")
    ok_chars = True
    has_base = False
    for ch in nick:
        cat = unicodedata.category(ch)
        if cat[0] in "LN":
            has_base = True
        elif cat[0] == "M" or ch in " _-.":
            pass
        elif ch == "@":
            pass  # handle·email 사유로 따로 알린다
        else:
            ok_chars = False
    if nick != nick.strip() or "  " in nick or not has_base:
        ok_chars = False
    if not ok_chars:
        reasons.append("nickname_charset")
    if re.search(r"[^\s@]@[^\s@]", nick):
        reasons.append("nickname_email")
    low = unicodedata.normalize("NFKC", nick).casefold()
    if "://" in low or "www." in low or re.search(r"\.(?:%s)(?![a-z0-9])" % "|".join(_TLDS), low):
        reasons.append("nickname_url")
    if "@" in nick:
        reasons.append("nickname_handle")
    sq = squash(nick)
    if any(k and k in sq for k in _MODEL_KEYS):
        reasons.append("nickname_model_name")
    if any(k and k in sq for k in _RESERVED_KEYS):
        reasons.append("nickname_reserved")
    return reasons


# ── 속도 제한 (guard.md 4절) ─────────────────────────────────────

LIMITS = {
    # 이름: (보통 상한, 신규 기간 상한, 창 초)
    "writes_per_hour": (12, 4, 3600),
    "writes_per_day": (60, 20, 86400),
    "threads_per_hour": (4, 2, 3600),
    "requests_per_hour": (6, 2, 3600),
    "requests_per_day": (20, 6, 86400),
    "transitions_per_hour": (30, 10, 3600),
    "reactions_per_hour": (30, 10, 3600),
    "digest_per_hour": (12, 12, 3600),
    "reads_per_minute": (120, 120, 60),
    "mailbox_per_day": (5, 5, 86400),
    "character_change": (1, 1, 86400),
    "notebook_per_hour": (12, 12, 3600),
}
IP_LIMITS = {
    "join_per_ip_hour": (3, 3600),
    "join_per_ip_day": (10, 86400),
    "join_global_hour": (30, 3600),
    "nickname_check_hour": (30, 3600),
    "report_per_hour": (10, 3600),
}


class RateLimiter:
    """미끄러지는 창. 프로세스 메모리에만 둔다(IP 는 DB·로그·파일에 쓰지 않는다)."""

    def __init__(self):
        self._hits: dict[tuple, collections.deque] = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check(self, items: list[tuple[str, str, int, int]], t: float) -> tuple[str, int, int, int] | None:
        """items = [(reason, key, limit, window_s)]. 하나라도 차 있으면 (reason, limit, window, retry_after)
        를 돌려주고 아무것도 세지 않는다. 다 비어 있으면 전부 한 번씩 센다."""
        with self._lock:
            for reason, key, limit, window in items:
                dq = self._hits[(reason, key)]
                while dq and dq[0] <= t - window:
                    dq.popleft()
                if len(dq) >= limit:
                    retry = int(dq[0] + window - t) + 1
                    return reason, limit, window, max(retry, 1)
            for reason, key, limit, window in items:
                self._hits[(reason, key)].append(t)
            return None
