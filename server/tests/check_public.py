"""공개 검사 (events-public.md 2절 「기계 시험」 1~5).

허용 칸은 서버 코드가 아니라 **규격 문서(events-public.md·snapshot-plaza.md·metrics.md)** 에서 읽는다.
서버 상수로 서버를 재면 규격과 구현을 쓴 같은 손이 같은 답을 낸다.
정규식도 guard.md 1.2 표에서 꺼낸다.

  python3 -m server.tests.check_public --url http://127.0.0.1:8765     # 떠 있는 서버를 잰다
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "spec"


# ── 규격에서 허용 칸 읽기 ──

def _ticks(s: str) -> list[str]:
    return re.findall(r"`([^`]+)`", s)


def spec_whitelist() -> dict[str, set[str]]:
    """events-public.md 2절 표: 대상 → 칸 이름."""
    text = (SPEC / "events-public.md").read_text(encoding="utf-8")
    sec = text.split("## 2. 공개 뷰 화이트리스트")[1].split("**절대 비공개**")[0]
    out = {}
    names = {"agent": "agent", "thread": "thread", "post": "post", "request": "request", "artifact": "artifact",
             "reaction": "reaction", "event": "event", "집계": "aggregate", "운영 공지·행사": "notice",
             "골드 장부 행": "gold", "행사 결과판": "event_board", "행사 결과": "event_result",
             "행사 골드": "event_gold", "골드 장부 자리 한 줄": "gold_move", "거울샘 결과": "agent_type", "지난 결과": "type_history"}
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] in names:
            fields = set()
            # 괄호 안 설명(`visible` 일 때만, `null` 등)과 한글 설명 토큰(`공개` 종류만)은 칸 이름이 아니다
            for t in _ticks(re.sub(r"\([^)]*\)", "", cells[1])):
                name = re.split(r"[{(]", t)[0]
                if re.fullmatch(r"[a-z_0-9]+", name):
                    fields.add(name)
            out[names[cells[0]]] = fields
    return out


def spec_event_types() -> dict[str, tuple[str, set[str]]]:
    """events-public.md 1절 표: type → (공개 등급, data 칸)."""
    text = (SPEC / "events-public.md").read_text(encoding="utf-8")
    sec = text.split("## 1. 사건 종류")[1].split("## 2.")[0]
    out = {}
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not cells[0].startswith("`"):
            continue
        t = _ticks(cells[0])[0]
        grade = "public" if cells[4].startswith("공개") else ("aggregate" if cells[4].startswith("집계") else "internal")
        data = set(_ticks(cells[3].split("(")[0])) if "없음" not in cells[3][:3] else set()
        # data 칸의 값 열거(`self`·`left` 등)는 이름이 아니다. 이름은 `x`, `y` 형태이고 값은 `:` 뒤에 온다
        data = {d for d in data if d not in ("self", "left", "sitting", "\"server\"")}
        m = re.findall(r"`([a-z_]+)`(?:\s*\(|,|\s*$|:|\s)", cells[3])
        names = set(m)
        vals = set()
        for seg in re.findall(r":\s*((?:`[^`]+`\s*[·,]?\s*)+)", cells[3]):
            vals |= set(_ticks(seg))
        out[t] = (grade, (names - vals) or set())
    return out


def secret_patterns() -> list[tuple[str, re.Pattern]]:
    """guard.md 1.2 표의 정규식 (전부) + /data/ + sv_. 유니코드·ASCII 두 벌로 건다."""
    text = (SPEC / "guard.md").read_text(encoding="utf-8")
    sec = text.split("### 1.2 패턴 목록")[1].split("- 사유 종류는")[0]
    pats = []
    for line in sec.splitlines():
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 3 or not cells[0].startswith("`"):
            continue
        reason = _ticks(cells[0])[0]
        if reason == "account_number":
            continue  # 표의 이 행은 정규식이 아니라 말(Luhn·앞뒤 20자)이다. account_hits() 가 따로 옮겼다
        for raw in _ticks(cells[2]):
            raw = raw.replace("\\|", "|")
            if raw in ("(?i)",):
                continue
            try:
                for flags in (0, re.ASCII):
                    pats.append((reason, re.compile(raw, flags)))
            except re.error:
                pass
    pats.append(("data_path", re.compile(r"/data/")))
    pats.append(("sv_key", re.compile(r"sv_")))
    return pats


def _luhn(d: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


_ID = re.compile(r"\b[a-z]{2}_[0-9a-f]{16}\b")


def account_hits(text: str) -> list[int]:
    """guard.md 1.2 account_number 행을 말 그대로 옮김: 13~19자리(공백·- 허용) Luhn 통과,
    또는 계좌·입금·송금·account·IBAN 앞뒤 20자 안의 숫자·- 10~20자.
    서버가 만든 id(`ev_` + hex 16)는 같은 길이 x 로 가리고 잰다. hex 16자가 우연히 숫자 13자 이상 + Luhn 이 되는
    일이 id 하나당 0.05% 쯤 있어, 공개 출력의 id 수백 개 중 하나가 가끔 카드 번호로 잡혔다(시각마다 id 가 달라 가끔 FAIL)."""
    text = _ID.sub(lambda m: "x" * len(m.group(0)), text)
    out = []
    for m in re.finditer(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)", text):
        d = re.sub(r"\D", "", m.group(0))
        if 13 <= len(d) <= 19 and _luhn(d):
            out.append(m.start())
    for m in re.finditer(r"계좌|입금|송금|account|IBAN", text, re.I):
        win = text[max(0, m.start() - 20):m.end() + 20]
        if re.search(r"(?<![\d-])[\d-]{10,20}(?![\d-])", win) and re.search(r"\d{3}", win):
            out.append(m.start())
    return out


# ── 구조: 스냅샷·리플레이의 틀은 snapshot-plaza.md · metrics.md 에서 옮겼다 ──
# 값이 문자열이면 그 대상의 화이트리스트, dict 면 칸 → 하위 틀, list 면 [항목 틀], "*" 는 스칼라,
# "map:X" 는 키가 자유(날짜·사유 이름)이고 값이 X.

META = {"window_days", "note", "null_reason"}  # metrics.md 가 칸 옆에 두는 설명 칸 (1.2·1.6 등)
REF = {"id": "*", "nickname": "*"}

DASH = {
    "activity": {"hourly": ["*"]},
    "cross": {"value": "*", "numerator": "*", "denominator": "*", "window_days": "*", "note": "*", "null_reason": "*"},
    "conversation": {k: "*" for k in ("value", "roots", "answered", "mutual_pairs", "one_way_pairs", "depth_max", "depth_median",
                                      "first_reply_hours_median", "window_days", "note", "null_reason")},
    "agents": {"active": "*", "operator": "*", "visited_7d": "*", "joined_7d": "*", "left_7d": "*"},
    "requests": {k: "*" for k in ("window_days", "opened", "claimed", "delivered", "fetched", "closed_done",
                                  "closed_withdrawn", "addressed_share", "fetch_hours_median",
                                  "fetch_hours_null_reason", "exchanges")} | {"now": "map:*"},
    "diversity": {"weeks": [{"week": "*", "value": "*", "n_items": "*", "n_pairs": "*", "model": "*",
                             "null_reason": "*"}],
                  "words": [{"word": "*", "spread": "*", "first_at": "*"}]},
    "conflict": {"ratio": "*", "null_reason": "*", "window_days": "*", "chains": "*", "note": "*", "reactions": "*"},
    "rumor": {"enabled": "*", "reason": "*", "chains": "*", "note": "*",
              "drift_by_depth": [{"depth": "*", "median": "*", "n": "*"}]},
    "ops": {"window_days": "*", "bell": "*", "hidden_by_reason": "map:*", "events": "*", "notices": "*",
            "held_by_reason": "map:*", "mailbox": "*", "reports": "*"},
    # 1.16 글 길이: 종류 이름까지 고정한다(map 으로 열면 본문 조각이 키로 새어도 못 잡는다)
    "length": {"unit": "*", "near_cap": "*", "window_days": ["*"],
               "caps": {k: "*" for k in ("remark", "post", "reply", "request")},
               **{w: {k: {f: "*" for f in ("n", "median", "p90", "max", "near_cap_n", "near_cap_share")}
                      for k in ("remark", "post", "reply", "request")} for w in ("d7", "d30")}},
}
# 거울샘 결과의 축 넷(api.md 12절): 두 극 백분율과 선명도만. 문항별 답 칸이 생기면 여기서 걸린다
TYPE_AXES = {ax: {p: "*", q: "*", "clarity": "*"} for ax, p, q in (("EI", "E", "I"), ("SN", "S", "N"), ("TF", "T", "F"), ("JP", "J", "P"))}
CARD = {"id": "*", "rule": "*", "at": "*", "agents": [REF], "event_ids": ["*"], "text": "*"}
PLAZA = {
    "schema": "*", "labels": {k: "*" for k in ("motion", "ai_images", "owner_unverified", "operator",
                                               "model_self_reported")},
    "weather": "*", "live": {"last_action_at": "*", "next_visit_soonest": "*"},
    "residents": [{"id": "*", "nickname": "*", "character": "*", "operator": "*", "zone": "*",
                   "last_action": {"kind": "*", "at": "*", "event_id": "*"},
                   "bubble": {"icon": "*", "event_id": "*"}, "dim": "*",
                   "next_visit": {"estimate": "*", "overdue": "*"}, "type_tag": "*"}],
    "roster": [{"id": "*", "nickname": "*", "character": "*", "operator": "*", "status": "*", "joined_at": "*",
                "last_visit_at": "*"}],
    "board": {"pinned": {"id": "*", "title": "*", "body": "*", "at": "*"},
              "threads": [{"id": "*", "kind": "*", "title": "*", "opened_by": REF, "post_count": "*",
                           "last_post_at": "*"}]},
    "market": [{"id": "*", "from": REF, "to": REF, "title": "*", "state": "*", "in_return_for": "*", "lit": "*",
                "reward": "*", "reward_state": "*"}],
    "event_board": ["event_board"],
    "spring": {"window_days": "*", "takers": "*", "shown": "*", "min_for_types": "*", "by_type": "map:*"},
    # 골드 장부 자리(snapshot-plaza.md 2절): 줄은 events-public 2절 「골드 장부 자리 한 줄」 표로. 잔액 순위 칸이 생기면 여기서 걸린다
    "gold_moves": {"window_days": "*", "count": "*", "received": "*", "supply": "*", "rows": ["gold_move"]},
    "stage": [{"artifact_id": "*", "request_id": "*", "author": REF, "fetched_by": REF, "fetched_at": "*"}],
    "steles": [{"target": "*", "kind": "*", "author": REF, "by": [REF], "at": "*", "note": "*"}],
    "bell": {"count_30d": "*", "last": {"type": "*", "title": "*", "at": "*"}},
    "dashboard": DASH,
    "sociogram": {"window_days": "*",
                  "nodes": [{"id": "*", "nickname": "*", "character": "*", "operator": "*", "status": "*",
                             "in": "*", "out": "*"}],
                  "edges": [{"from": "*", "to": "*", "weight": "*", "types": "map:*", "dim": "*",
                             "first_at": "*", "last_at": "*"}]},
    "scenes": [CARD],
}
SNAPSHOT = {"format": "*", "schema": "*", "generated": "*",   # 스냅샷 2 (광장 자체 형식, snapshot-plaza.md 1절)
            "site": {"name": "*", "subtitle": "*", "lang": "*"}, "plaza": PLAZA}
REPLAY = {"schema": "*", "date": "*", "tz": "*", "final": "*", "generated": "*", "season": "*",
          "events": ["replay_event"], "scenes": [CARD], "counts": {"bubbles": "*", "bubble_rows": "*"}}
INDEX = {"dates": [{"date": "*", "bubbles": "*", "scenes": "*"}]}


class Walker:
    def __init__(self, wl, ev_types):
        self.wl, self.ev_types = wl, ev_types
        self.bad: list[str] = []

    def obj(self, kind: str, v, path: str):
        """화이트리스트 대상 하나. 참조 칸은 {id,nickname} 만."""
        if v is None:
            return
        if kind == "replay_event":
            extra = {"nickname", "zone", "bubble"}  # snapshot-plaza.md 3절 리플레이 행
            self._event(v, path, extra)
            return
        if kind == "event":
            self._event(v, path, set())
            return
        allowed = self.wl[kind]
        for k, x in v.items():
            if k not in allowed:
                self.bad.append(f"{path}.{k}")
            elif k in ("author", "from", "to", "claimed_by", "opened_by"):
                self.walk(REF, x, f"{path}.{k}")
            elif k == "members":
                self.walk([REF], x, f"{path}.{k}")
            elif k == "reactions":
                self.walk({r: "*" for r in ("agree", "rebut", "repro_ok", "repro_fail", "thanks")}, x, f"{path}.{k}")
            elif k == "former_nicknames":
                self.walk(["*"], x, f"{path}.{k}")
            elif kind == "event_board" and k in ("result", "gold"):
                self.obj("event_" + k, x, f"{path}.{k}")
            elif kind == "agent" and k == "type":
                self.obj("agent_type", x, f"{path}.{k}")
            elif kind == "agent_type" and k == "axes":
                self.walk(TYPE_AXES, x, f"{path}.{k}")
            elif isinstance(x, (dict, list)):
                self.bad.append(f"{path}.{k}(구조)")
        # 골드 장부 자리의 행사 지급 묶음은 받은 이를 안 싣는다(events-public.md 4절): 이름이 붙으면 「누가 받았나」 목록이 된다
        if kind == "gold_move" and (v.get("kind") == "event_award" or v.get("notice_id")) and (v.get("from") or v.get("to")):
            self.bad.append(f"{path}(행사 지급 묶음에 이름)")

    def _event(self, v, path, extra):
        allowed = self.wl["event"] | extra
        for k in v:
            if k not in allowed:
                self.bad.append(f"{path}.{k}")
        spec = self.ev_types.get(v.get("type"))
        if not spec or spec[0] != "public":
            self.bad.append(f"{path}.type={v.get('type')}(공개 종류 아님)")
            return
        for k, x in (v.get("data") or {}).items():
            if k not in spec[1]:
                self.bad.append(f"{path}.data.{k}")
            elif k == "members":
                self.walk([REF], x, f"{path}.data.{k}")
            elif isinstance(x, (dict, list)) and k != "fields":
                self.bad.append(f"{path}.data.{k}(구조)")

    def walk(self, shape, v, path="$"):
        if v is None:
            return
        if isinstance(shape, str):
            if shape == "*":
                if isinstance(v, (dict, list)):
                    self.bad.append(f"{path}(스칼라여야)")
            elif shape.startswith("map:"):
                if not isinstance(v, dict):
                    self.bad.append(f"{path}(map 이어야)")
                    return
                for k, x in v.items():
                    self.walk(shape[4:], x, f"{path}[{k}]")
            else:
                self.obj(shape, v, path)
            return
        if isinstance(shape, list):
            if not isinstance(v, list):
                self.bad.append(f"{path}(목록이어야)")
                return
            for i, x in enumerate(v):
                self.walk(shape[0], x, f"{path}[{i}]")
            return
        if not isinstance(v, dict):
            self.bad.append(f"{path}(객체여야)")
            return
        for k, x in v.items():
            if k not in shape:
                self.bad.append(f"{path}.{k}")
            else:
                self.walk(shape[k], x, f"{path}.{k}")


# 배경용 실제 날씨 (snapshot-plaza.md 5절에서 옮겼다). 원장에서 나오지 않는 유일한 공개 문이라 칸을 따로 고정한다.
# 좌표·기온 같은 원시 값 칸이 생기면 여기서 「표에 없는 칸」으로 걸린다
WEATHER = {"schema": "*", "generated": "*", "state": "*", "source": "*", "place": "*",
           "weather": {"sky": "*", "daylight": "*", "observed_at": "*", "label": "*"},
           "fetch": {"last_ok_at": "*", "last_try_at": "*", "last_error": "*", "fail_streak": "*", "fails_24h": "*",
                     "fails_24h_by_kind": "map:*"}}


def shape_for(path: str):
    if path == "/public/snapshot.json":
        return SNAPSHOT
    if path == "/public/weather.json":
        return WEATHER
    if path == "/public/replay/index.json":
        return INDEX
    if path.startswith("/public/replay/"):
        return REPLAY
    if path == "/public/threads.json":
        return {"threads": ["thread"], "remarks": ["post"]}
    if path.startswith("/public/threads/"):
        return {"thread": "thread", "posts": ["post"], "reactions": ["reaction"]}
    if path.startswith("/public/agents/"):
        return {"agent": "agent", "recent_posts": ["post"], "gold": {"balance": "*", "entries": ["gold"]},
                "type_history": ["type_history"]}
    if path == "/public/events.json":
        return {"events": ["event_board"]}
    if path.startswith("/public/requests/"):
        return {"request": "request", "artifact": "artifact", "reactions": ["reaction"]}
    return None


OWNER_KEY = re.compile(r"owner|소유주|email|이메일|real_name|실명", re.I)


def owner_keys(v, path="$", out=None):
    """공개 출력의 키 이름에 소유주 칸이 있나. 예외: plaza.labels.owner_unverified (표기 문구 자리, 규격 2절)."""
    out = [] if out is None else out
    if isinstance(v, dict):
        for k, x in v.items():
            p = f"{path}.{k}"
            # map 칸(보류 사유별 수 등)의 키는 칸 이름이 아니라 값(사유 이름 `email` 등)이다
            in_map = path.endswith(("held_by_reason", "hidden_by_reason", "held_by_reason_daily", "op_hidden_30d")) \
                or ".held_by_reason_daily[" in path
            if OWNER_KEY.search(k) and not in_map and not p.endswith("labels.owner_unverified"):
                out.append(p)
            owner_keys(x, p, out)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            owner_keys(x, f"{path}[{i}]", out)
    return out


def fetch(url: str, path: str, method="GET", data=None):
    rq = urllib.request.Request(url + path, method=method, data=data,
                                headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(rq, timeout=30) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def collect(url: str) -> dict[str, object]:
    """/public/* 전부와 리플레이 전 날짜를 모은다."""
    out = {}
    for p in ("/public/snapshot.json", "/public/replay/index.json", "/public/threads.json", "/public/weather.json",
              "/public/events.json"):
        st, h, raw = fetch(url, p)
        out[p] = (st, h, raw)
    idx = json.loads(out["/public/replay/index.json"][2])
    for d in idx["dates"]:
        p = f"/public/replay/{d['date']}.json"
        out[p] = fetch(url, p)
    snap = json.loads(out["/public/snapshot.json"][2])
    ths = json.loads(out["/public/threads.json"][2])
    for t in ths["threads"]:
        p = f"/public/threads/{t['id']}.json"
        out[p] = fetch(url, p)
    for a in snap["plaza"]["roster"]:
        p = f"/public/agents/{a['id']}.json"
        out[p] = fetch(url, p)
    for m in snap["plaza"]["market"]:
        p = f"/public/requests/{m['id']}.json"
        out[p] = fetch(url, p)
    return out


_URL_AT = re.compile(r"https?://[^\s\"'<>]*$", re.I)
_SLUG = re.compile(r"[A-Za-z0-9]{1,20}(?:-[A-Za-z0-9]{1,20}){3,}")


def long_token_counts(text: str, m: re.Match) -> bool:
    """guard.md 1.2 의 long_token 은 정규식 + 말(대문자·소문자·숫자가 모두 들어 있는 것)이다.
    표에서 꺼낸 정규식만으로는 말 쪽이 빠져 기사 주소 슬러그까지 걸렸다(2026-10-02, techcrunch).
    말을 마저 적용하고, 주소 안의 하이픈 단어열(슬러그)도 뺀다. 주소 안이라도 토큰 모양이면 그대로 잡는다."""
    s = m.group(0)
    if not (re.search("[A-Z]", s) and re.search("[a-z]", s) and re.search("[0-9]", s)):
        return False
    in_url = _URL_AT.search(text, max(0, m.start() - 500), m.start()) is not None
    return not (in_url and _SLUG.fullmatch(s))


def check(outputs: dict[str, tuple], planted: list[str] | None = None) -> dict:
    """outputs: path → (status, headers, raw bytes). 결과 dict 에 항목별 실패 목록."""
    wl, ev = spec_whitelist(), spec_event_types()
    pats = secret_patterns()
    res = {"paths": len(outputs), "forbidden_fields": [], "regex_hits": [], "planted_hits": [], "owner_keys": [],
           "non_json": []}
    for path, (st, h, raw) in outputs.items():
        ct = h.get("Content-Type", "")
        if "json" not in ct:
            res["non_json"].append(f"{path} {st} {ct}")
            continue
        obj = json.loads(raw)
        shape = shape_for(path)
        w = Walker(wl, ev)
        if shape is None:
            res["forbidden_fields"].append(f"{path}: 틀 없음")
        else:
            w.walk(shape, obj)
        res["forbidden_fields"] += [f"{path}: {b}" for b in w.bad]
        text = raw.decode("utf-8")
        for reason, pat in pats:
            for m in pat.finditer(text):
                if reason == "long_token" and not long_token_counts(text, m):
                    continue
                res["regex_hits"].append(f"{path}: {reason} @{m.start()}")
        for pos in account_hits(text):
            res["regex_hits"].append(f"{path}: account_number @{pos}")
        for s in planted or []:
            if s in text:
                res["planted_hits"].append(f"{path}: 심은 값 {s[:12]}…")
        res["owner_keys"] += [f"{path}: {k}" for k in owner_keys(obj)]
    res["regex_hits"] = sorted(set(res["regex_hits"]))
    return res


# ── 서버 렌더 공개 HTML (/t/<id> · /a/<id> · / 의 보조 영역, spec/seo-pages.md) ──
# 화이트리스트 키 검사는 JSON 에 한다. HTML 은 그 JSON 에서만 그리므로 여기서는 (1) 같은 정규식·심은 값 0
# (2) 운영 비공개 칸 이름·보류/거울샘 행 id 0 (3) 꺾쇠가 안 풀렸는지(스크립트는 JSON-LD 하나뿐, <img 없음)
# (4) JSON-LD 가 파싱되고 허용 키만 (5) JSON 의 보이는 본문이 이스케이프된 채 전부 실렸는지를 잰다
PRIVATE_WORDS = ("key_hash", "join_req", "seen_version", "acked_seq", "acked_cursor", "confirm_hash", "confirm_token",
                 "rename_left", "rename_used", "new_until", "self_status", "last_seen_at", "left_mode", "body_hash")
PRIVATE_IDS = re.compile(r"\b(?:hd|ty|mb)_[0-9a-f]{16}\b")
LD_KEYS = {"@context", "@type", "@id", "url", "headline", "datePublished", "dateModified", "author", "isPartOf",
           "interactionStatistic", "text", "comment", "name", "description", "interactionType", "userInteractionCount",
           "dateCreated", "mainEntity", "identifier", "alternateName"}
_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
# CDN(Cloudflare Web Analytics)이 엣지에서 </body> 앞에 끼워 넣는 비컨. 원점 응답엔 없고 토큰은 사이트 분석용 공개 값이다.
# 이 정확한 모양만 떼고 잰다(떼어 낸 수는 cdn_injected 로 남긴다). 다른 스크립트는 그대로 걸린다
CDN_BEACON = re.compile(r'<script defer src="https://static\.cloudflareinsights\.com/beacon\.min\.js[^"]*"[^<>]*></script>'
                        r'|<script type="module" src="https://static\.cloudflareinsights\.com/beacon\.min\.js[^"]*"[^<>]*></script>')


def collect_pages(url: str, outputs: dict) -> dict[str, tuple]:
    """공개 JSON 에 나온 글타래·에이전트마다 HTML 페이지를 받는다. 첫 화면 / 도."""
    out = {"/": fetch(url, "/")}
    for path in outputs:
        m = re.fullmatch(r"/public/(threads|agents)/((?:th|ag)_[0-9a-f]{16})\.json", path)
        if m:
            p = f"/{m.group(1)[0]}/{m.group(2)}"
            out[p] = fetch(url, p)
    return out


def _ld_keys(v, bad, path="$"):
    if isinstance(v, dict):
        for k, x in v.items():
            if k not in LD_KEYS:
                bad.append(f"{path}.{k}")
            _ld_keys(x, bad, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _ld_keys(x, bad, f"{path}[{i}]")


def _markup(text: str) -> list[str]:
    """HTML 파서로 실제 태그만 본다: 넣으면 안 되는 태그(img·iframe·svg·object·embed)와 on… 이벤트 속성.
    속성 값 안의 「onerror=」 글자(이스케이프된 본문을 옮긴 description 등)는 태그가 아니라 안 센다"""
    from html.parser import HTMLParser
    out = []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in ("img", "iframe", "svg", "object", "embed"):
                out.append(tag)
            out.extend(f"{tag}[{k}]" for k, _ in attrs if k.lower().startswith("on"))
    P().feed(text)
    return out


def check_pages(pages: dict[str, tuple], outputs: dict | None = None, planted: list[str] | None = None) -> dict:
    """pages: path → (status, headers, raw). outputs 를 주면 같은 글타래·에이전트 JSON 과 값을 맞춘다."""
    import html as H
    pats = secret_patterns()
    res = {"pages": len(pages), "cdn_injected": 0, "page_status": [], "page_regex": [], "page_planted": [], "page_private": [],
           "page_markup": [], "page_ld": [], "page_mismatch": []}
    for path, (st, h, raw) in pages.items():
        text = raw.decode("utf-8", "replace")
        if st != 200 or "text/html" not in h.get("Content-Type", ""):
            res["page_status"].append(f"{path} {st} {h.get('Content-Type')}")
            continue
        text, n = CDN_BEACON.subn("", text)
        res["cdn_injected"] += n
        # 자기 주소(canonical 의 앞부분)는 정규식에서 뺀다. 터널·시험 서버는 127.0.0.1 이 자기 주소다
        base = re.search(r'<link rel="canonical" href="(https?://[^/"]+)', text)
        scan = text.replace(base.group(1), "BASE") if base else text
        for reason, pat in pats:
            for m in pat.finditer(scan):
                if reason == "long_token" and not long_token_counts(scan, m):
                    continue
                if reason in ("url", "domain", "link", "external_link"):
                    continue          # 자기 주소(canonical·og)는 seo_check 가 잰다
                res["page_regex"].append(f"{path}: {reason} @{m.start()}")
        for pos in account_hits(text):
            res["page_regex"].append(f"{path}: account_number @{pos}")
        res["page_planted"] += [f"{path}: 심은 값 {s[:12]}…" for s in planted or [] if s in text]
        res["page_private"] += [f"{path}: {w}" for w in PRIVATE_WORDS if w in text]
        res["page_private"] += [f"{path}: 행 id {m.group(0)[:3]}…" for m in PRIVATE_IDS.finditer(text)]
        scripts = re.findall(r"<script\b[^>]*>", text, re.I)
        if path != "/" and scripts != ['<script type="application/ld+json">']:
            res["page_markup"].append(f"{path}: 스크립트 태그 {scripts}")
        bad_tags = _markup(text)
        if bad_tags:
            res["page_markup"].append(f"{path}: 풀린 태그·이벤트 속성 {bad_tags[:3]}")
        if path == "/":
            continue
        lds = _LD.findall(text)
        try:
            obj = json.loads(lds[0]) if len(lds) == 1 else None
        except ValueError as e:
            obj = None
            res["page_ld"].append(f"{path}: JSON-LD 파싱 실패 {e}")
        if obj is None:
            res["page_ld"].append(f"{path}: JSON-LD {len(lds)}개")
        else:
            bad = []
            _ld_keys(obj, bad)
            res["page_ld"] += [f"{path}: 허용 밖 키 {b}" for b in bad]
        m = re.fullmatch(r"/(t|a)/(\S+)", path)
        src = (outputs or {}).get(f"/public/{'threads' if m.group(1) == 't' else 'agents'}/{m.group(2)}.json") if m else None
        if src:
            d = json.loads(src[2])
            posts = d.get("posts") if m.group(1) == "t" else d.get("recent_posts")
            names = [p["author"]["nickname"] for p in d.get("posts") or [] if p.get("author")]
            if m.group(1) == "t":
                want = [H.escape(p["body"], quote=True) for p in posts if p.get("body") is not None]
                want += [H.escape(d["thread"]["title"], quote=True)] + [H.escape(n, quote=True) for n in names]
            else:
                want = [H.escape(d["agent"]["nickname"], quote=True)] + \
                       ([H.escape(d["agent"]["intro"], quote=True)] if d["agent"].get("intro") else [])
            res["page_mismatch"] += [f"{path}: JSON 값이 안 실림 {w[:20]}…" for w in want if w not in text]
    return res


def check_404(url: str) -> list[str]:
    """3. /public/ 아래 없는 경로·/data/·설정 파일 이름이 404 JSON."""
    bad = []
    for p in ("/public/", "/public/nope.json", "/public/../data/plaza.db", "/data/", "/data/plaza.db",
              "/public/operators.json", "/public/secret", "/public/plaza.db", "/.env", "/public/replay/",
              "/public/threads/th_0000000000000000.json", "/public/agents/ag_0000000000000000.json",
              "/public/replay/../../secret"):
        st, h, raw = fetch(url, p)
        ok = st == 404 and "json" in h.get("Content-Type", "")
        if ok:
            try:
                ok = json.loads(raw).get("error") == "not_found"
            except ValueError:
                ok = False
        if not ok:
            bad.append(f"{p} → {st} {h.get('Content-Type')}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    a = ap.parse_args(argv)
    outs = collect(a.url)
    res = check(outs)
    res["not_404"] = check_404(a.url)
    res.update(check_pages(collect_pages(a.url, outs), outs))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    fails = sum(len(v) for k, v in res.items() if isinstance(v, list))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
