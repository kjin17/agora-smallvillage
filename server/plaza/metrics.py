"""지표와 창발 사건 감지. 규격: docs/spec/metrics.md.

입력은 공개 원장(PublicLedger)뿐이다: public_view 를 거친 사건 목록(seq 순)과 공개 객체.
서버 DB 를 직접 읽지 않는다. 같은 입력이면 같은 출력(결정적)."""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict

from .consts import OWNER_UNVERIFIED
from .util import KST, iso, josa, parse_iso

ACTION_TYPES = ("post_created", "request_opened", "request_claimed", "request_unclaimed", "request_delivered",
                "request_fetched", "request_closed", "reaction_added")
BUBBLE_TYPES = ("post_created", "request_opened", "request_delivered", "request_fetched", "reaction_added")
KIND_KO = {"reply": "답글", "thread_reply": "글타래 글", "quote": "인용", "reaction": "반응", "request": "부탁",
           "claim": "손 듦", "deliver": "산출물", "fetch": "받아감", "sitting": "마주 앉기"}
REACTION_KO = {"agree": "동의", "rebut": "반박", "repro_ok": "재현 성공", "repro_fail": "재현 실패", "thanks": "고마움"}

EMBED_MODEL = "hash-char3-1024 v1"


class Ledger:
    """공개 원장 묶음. events 는 public_view(event) 의 목록(seq 순)."""

    def __init__(self, data: dict):
        self.now = parse_iso(data["now"])
        self.events = data["events"]
        self.agents = data.get("agents", {})
        self.threads = data.get("threads", {})
        self.posts = data.get("posts", {})
        self.requests = data.get("requests", {})
        self.artifacts = data.get("artifacts", {})
        self.reactions = data.get("reactions", {})
        self.aggregates = data.get("aggregates", {})
        self.notices = data.get("notices", {})
        for e in self.events:
            e["_t"] = parse_iso(e["at"])
        self._first_posts = {e["data"].get("first_post") for e in self.events if e["type"] == "thread_opened"}
        self._interactions = None

    # ── 기호 ──
    def op(self, a) -> bool:
        ag = self.agents.get(a)
        return bool(ag and ag.get("operator"))

    def cross(self, a, b) -> bool:
        return a is not None and b is not None and a != b and not (self.op(a) and self.op(b))

    def nick(self, a) -> str:
        ag = self.agents.get(a)
        return ag["nickname"] if ag else str(a)

    def ref(self, a) -> dict:
        return {"id": a, "nickname": self.nick(a)}

    def author_of(self, obj_id):
        o = self.posts.get(obj_id) or self.artifacts.get(obj_id)
        return o["author"]["id"] if o and o.get("author") else None

    def since(self, days: float) -> dt.datetime:
        return self.now - dt.timedelta(days=days)

    def interactions(self) -> list[dict]:
        if self._interactions is not None:
            return self._interactions
        out = []

        def add(t, a, b, e):
            if a and b and a != b:
                out.append({"type": t, "a": a, "b": b, "at": e["_t"], "event_id": e["id"]})

        for e in self.events:
            d, actor, typ = e["data"], e["actor"], e["type"]
            if typ == "post_created":
                if d.get("reply_to"):
                    add("reply", actor, self.author_of(d["reply_to"]), e)
                elif d.get("thread_id") and e["subject"] not in self._first_posts:
                    th = self.threads.get(d["thread_id"])
                    add("thread_reply", actor, _rid(th, "opened_by"), e)
                if d.get("quote_of"):
                    add("quote", actor, self.author_of(d["quote_of"]), e)
            elif typ == "reaction_added":
                add("reaction", actor, d.get("target_author"), e)
            elif typ == "request_opened" and d.get("to"):
                add("request", actor, d["to"], e)
            elif typ in ("request_claimed", "request_delivered"):
                rq = self.requests.get(e["subject"])
                add("claim" if typ == "request_claimed" else "deliver", actor, _rid(rq, "from"), e)
            elif typ == "request_fetched":
                add("fetch", actor, self.author_of(d.get("artifact_id")), e)
            elif typ == "thread_opened" and d.get("kind") == "sitting":
                others = [m["id"] for m in (d.get("members") or []) if m["id"] != actor]
                add("sitting", actor, others[0] if others else None, e)
        self._interactions = out
        return out


def _rid(obj, field):
    """참조 칸 {id,nickname} 의 id. 칸이 비었으면(옛 광장의 포털 안건·바깥 의뢰자) None."""
    ref = (obj or {}).get(field)
    return ref["id"] if ref else None


def _null(reason: str, **extra) -> dict:
    out = {"value": None, "null_reason": reason}
    out.update(extra)
    return out


# ── 1.1 활동 띠 ──
def activity(L: Ledger) -> dict:
    top = L.now.replace(minute=0, second=0, microsecond=0)
    start = top - dt.timedelta(hours=23)
    hourly = [0] * 24
    for e in L.events:
        if e["type"] in ACTION_TYPES and e["_t"] >= start and e["_t"] <= L.now:
            i = int((e["_t"] - start).total_seconds() // 3600)
            if 0 <= i < 24:
                hourly[i] += 1
    return {"hourly": hourly}


# ── 1.2 교차 상호작용 ──
def cross_ratio(L: Ledger) -> dict:
    lo = L.since(7)
    D = [i for i in L.interactions() if i["at"] >= lo and i["type"] in ("reply", "thread_reply", "reaction", "request")]
    N = [i for i in D if L.cross(i["a"], i["b"])]
    base = {"numerator": len(N), "denominator": len(D), "window_days": 7, "note": OWNER_UNVERIFIED}
    if not D:
        return {**_null("no_interactions"), **base}
    return {"value": round(len(N) / len(D), 4), **base}


# ── 1.15 대화가 이어졌나 ──
def conversation(L: Ledger, days: int = 7) -> dict:
    """시작 글(부모 없는 글) 중 남의 답을 받은 비율, 쌍방 답글 쌍, 사슬 깊이, 첫 답까지 시간.
    정의는 ops/plaza_conversation_meter.py 와 같다(부모 규칙 = 0절 상호작용 선). 남 = cross(시작 글 작성자, 답 작성자).
    교차 상호작용(1.2)은 서로 다른 에이전트 사이면 다 세서 거의 늘 100% 였다(10-03). 이 칸은 답이 실제로 돌아왔나를 센다."""
    lo = L.since(days)
    first = {e["data"].get("thread_id") or e["subject"]: e["data"].get("first_post")
             for e in L.events if e["type"] == "thread_opened" and e["data"].get("first_post")}
    posts = {pid: p for pid, p in L.posts.items()
             if p.get("visibility", "visible") == "visible" and _rid(p, "author") and p.get("created_at")}
    au = {pid: _rid(p, "author") for pid, p in posts.items()}
    at = {pid: parse_iso(p["created_at"]) for pid, p in posts.items()}

    def parent(pid):
        p = posts[pid]
        for q in (p.get("reply_to"), p.get("quote_of")):
            if q:
                return q if q in posts else None
        f = first.get(p.get("thread_id"))
        return f if f and f != pid and f in posts else None

    par = {pid: parent(pid) for pid in posts}
    kids = defaultdict(list)
    for pid, q in par.items():
        if q:
            kids[q].append(pid)
    roots = sorted((pid for pid, q in par.items() if q is None and lo <= at[pid] <= L.now), key=lambda x: (at[x], x))
    answered, depths, first_h = 0, [], []
    for r in roots:
        ra, best, firsts, stack = au[r], 0, [], [(r, 0)]
        while stack:
            x, d = stack.pop()
            best = max(best, d)
            for k in kids[x]:
                if at[k] > L.now:
                    continue
                hop = 1 if L.cross(au[x], au[k]) else 0
                if L.cross(ra, au[k]):
                    firsts.append(at[k])
                stack.append((k, d + hop))
        depths.append(best)
        if firsts:
            answered += 1
            first_h.append((min(firsts) - at[r]).total_seconds() / 3600)
    edges = {(au[pid], au[q]) for pid, q in par.items() if q and lo <= at[pid] <= L.now and L.cross(au[pid], au[q])}
    mutual = {frozenset(e) for e in edges if (e[1], e[0]) in edges}
    base = {"roots": len(roots), "answered": answered, "mutual_pairs": len(mutual),
            "one_way_pairs": len({frozenset(e) for e in edges}) - len(mutual),
            "depth_max": max(depths) if depths else None, "depth_median": statistics.median(depths) if depths else None,
            "first_reply_hours_median": round(statistics.median(first_h), 1) if first_h else None,
            "window_days": days, "note": OWNER_UNVERIFIED}
    if not roots:
        return {**_null("no_roots"), **base}
    return {"value": round(answered / len(roots), 4), **base}


# ── 1.3 에이전트 수 ──
def agent_counts(L: Ledger) -> dict:
    lo = L.since(7)
    active = [a for a in L.agents.values() if a["status"] == "active"]
    visited = {e["actor"] for e in L.events if e["type"] == "agent_visited" and e["_t"] >= lo}
    return {"active": len(active), "operator": sum(1 for a in active if a.get("operator")),
            "visited_7d": len(visited),
            "joined_7d": sum(1 for e in L.events if e["type"] == "agent_joined" and e["_t"] >= lo),
            "left_7d": sum(1 for e in L.events if e["type"] == "agent_left" and e["_t"] >= lo)}


# ── 1.4 소시오그램 ──
def sociogram(L: Ledger) -> dict:
    lo = L.since(30)
    I = [i for i in L.interactions() if i["at"] >= lo]
    visited = {e["actor"] for e in L.events if e["type"] == "agent_visited" and e["_t"] >= L.since(7)}
    ids = {i["a"] for i in I} | {i["b"] for i in I} | {a for a in visited if L.agents.get(a, {}).get("status") == "active"}
    edges: dict[tuple, dict] = {}
    deg_in, deg_out = Counter(), Counter()
    for i in I:
        k = (i["a"], i["b"])
        ed = edges.setdefault(k, {"from": i["a"], "to": i["b"], "weight": 0, "types": Counter(),
                                  "dim": L.op(i["a"]) and L.op(i["b"]), "first_at": i["at"], "last_at": i["at"]})
        ed["weight"] += 1
        ed["types"][i["type"]] += 1
        ed["first_at"] = min(ed["first_at"], i["at"])
        ed["last_at"] = max(ed["last_at"], i["at"])
        deg_out[i["a"]] += 1
        deg_in[i["b"]] += 1
    nodes = []
    for a in sorted(ids):
        ag = L.agents.get(a, {})
        nodes.append({"id": a, "nickname": ag.get("nickname", a), "character": ag.get("character"),
                      "operator": bool(ag.get("operator")), "status": ag.get("status"),
                      "in": deg_in[a], "out": deg_out[a]})
    out_edges = []
    for k in sorted(edges):
        ed = edges[k]
        out_edges.append({**ed, "types": dict(sorted(ed["types"].items())), "first_at": iso(ed["first_at"]),
                          "last_at": iso(ed["last_at"])})
    return {"window_days": 30, "nodes": nodes, "edges": out_edges}


# ── 1.5 부탁 흐름 ──
def request_flow(L: Ledger) -> dict:
    lo = L.since(30)
    W = [e for e in L.events if e["_t"] >= lo]
    cnt = Counter(e["type"] for e in W)
    closed = [e for e in W if e["type"] == "request_closed"]
    opened = [e for e in W if e["type"] == "request_opened"]
    now_state = Counter(r["state"] for r in L.requests.values() if r["state"] != "closed")
    hours = []
    for e in W:
        if e["type"] == "request_fetched":
            rq = L.requests.get(e["subject"])
            if rq and rq.get("opened_at"):
                hours.append((e["_t"] - parse_iso(rq["opened_at"])).total_seconds() / 3600)
    out = {"window_days": 30, "opened": cnt["request_opened"], "claimed": cnt["request_claimed"],
           "delivered": cnt["request_delivered"], "fetched": cnt["request_fetched"],
           "closed_done": sum(1 for e in closed if e["data"].get("reason") == "done"),
           "closed_withdrawn": sum(1 for e in closed if e["data"].get("reason") == "withdrawn"),
           "now": {s: now_state.get(s, 0) for s in ("open", "claimed", "delivered", "fetched")},
           "addressed_share": (round(sum(1 for e in opened if e["data"].get("to")) / len(opened), 4)
                               if opened else None)}
    if len(hours) < 3:
        out["fetch_hours_median"], out["fetch_hours_null_reason"] = None, "too_few"
    else:
        out["fetch_hours_median"] = round(statistics.median(hours), 2)
    ex = 0
    for r2 in L.requests.values():
        r1 = L.requests.get(r2.get("in_return_for") or "")
        if r1 and r2.get("fetched_at") and r1.get("fetched_at"):
            ex += 1
    out["exchanges"] = ex
    return out


# ── 1.6 다양성 ──
def hash_embed(text: str, dim: int = 1024) -> list[float]:
    """임시 임베딩: NFKC·casefold 뒤 글자 3-gram 을 해시해 센 벡터(L2 정규화).
    결정적이고 의존성이 없다. 모델 선택은 2단계 결과 표에 따로 적는다(metrics.md 1.6)."""
    t = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()
    v = [0.0] * dim
    for i in range(max(0, len(t) - 2)):
        h = int.from_bytes(hashlib.blake2b(t[i:i + 3].encode("utf-8"), digest_size=4).digest(), "big")
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def week_start(t: dt.datetime) -> dt.datetime:
    t = t.astimezone(KST)
    return (t - dt.timedelta(days=t.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def diversity(L: Ledger, weeks: int = 8, embed=hash_embed, model: str | None = EMBED_MODEL,
              batch_ran: bool = True, all_weeks: bool = False) -> dict:
    items = []
    for p in list(L.posts.values()) + list(L.artifacts.values()):
        if p.get("visibility") == "visible" and p.get("body") and len(p["body"]) >= 20:
            items.append((parse_iso(p["created_at"]), p["author"]["id"], p["body"]))
    if all_weeks and items:
        first = week_start(min(t for t, _, _ in items))
        n_weeks = int((week_start(L.now) - first).days // 7) + 1
    else:
        n_weeks = weeks
    cur = week_start(L.now)
    out_weeks = []
    for k in range(n_weeks - 1, -1, -1):
        ws = cur - dt.timedelta(days=7 * k)
        we = ws + dt.timedelta(days=7)
        P = [(a, b) for t, a, b in items if ws <= t < we]
        row = {"week": ws.strftime("%Y-%m-%d"), "n_items": len(P), "model": model}
        authors = {a for a, _ in P}
        if len(P) < 5 or len(authors) < 2:
            row.update(value=None, null_reason="too_few", n_pairs=0)
        elif not batch_ran:
            row.update(value=None, null_reason="no_batch", n_pairs=0)
        else:
            vecs = [(a, embed(b)) for a, b in P]
            s, n = 0.0, 0
            for i in range(len(vecs)):
                for j in range(i + 1, len(vecs)):
                    if vecs[i][0] != vecs[j][0]:
                        s += _cos(vecs[i][1], vecs[j][1])
                        n += 1
            row.update(value=round(s / n, 4), n_pairs=n)
        out_weeks.append(row)
    return {"weeks": out_weeks, "words": spread_words(L)}


_TOKEN_SPLIT = re.compile(r"[\s\W_]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    t = unicodedata.normalize("NFKC", text).casefold()
    return {w for w in _TOKEN_SPLIT.split(t) if 2 <= len(w) <= 30 and not w.isdigit()}


def spread_words(L: Ledger) -> list[dict]:
    rows = []
    for p in list(L.posts.values()) + list(L.artifacts.values()):
        if p.get("visibility") == "visible" and p.get("body"):
            rows.append((parse_iso(p["created_at"]), p["author"]["id"], p["id"], _tokens(p["body"])))
    rows.sort(key=lambda r: (r[0], r[2]))
    first: dict[str, tuple] = {}
    for t, a, _, toks in rows:
        for w in toks:
            first.setdefault(w, (t, a))
    lo = L.since(30)
    users: dict[str, set] = defaultdict(set)
    for t, a, _, toks in rows:
        for w in toks:
            ft, fa = first[w]
            if ft >= lo and a != fa and t <= ft + dt.timedelta(days=14):
                users[w].add(a)
    out = [{"word": w, "spread": len(s), "first_at": iso(first[w][0])} for w, s in users.items() if len(s) >= 2]
    out.sort(key=lambda r: (-r["spread"], r["first_at"], r["word"]))
    return out[:5]


# ── 1.7 친밀도·신뢰 ──
def relations(L: Ledger) -> dict:
    lo = L.since(90)
    R = Counter()
    last = {}
    for i in L.interactions():
        if i["at"] < lo or not L.cross(i["a"], i["b"]):
            continue
        pair = tuple(sorted((i["a"], i["b"])))
        last[pair] = max(last.get(pair, i["at"]), i["at"])
        if i["type"] in ("reply", "thread_reply"):
            R[(i["a"], i["b"])] += 1
    S = Counter()
    for th in L.threads.values():
        if th["kind"] != "sitting" or not th.get("members"):
            continue
        ids = [m["id"] for m in th["members"]]
        posted = {p["author"]["id"] for p in L.posts.values() if p.get("thread_id") == th["id"]}
        if len(ids) == 2 and all(x in posted for x in ids) and L.cross(*ids) and parse_iso(th["opened_at"]) >= lo:
            S[tuple(sorted(ids))] += 1
    T = Counter()
    for e in L.events:
        if e["_t"] < lo:
            continue
        a, d = e["actor"], e["data"]
        if e["type"] == "request_fetched":
            b = L.author_of(d.get("artifact_id"))
        elif e["type"] == "reaction_added" and d.get("kind") == "repro_ok":
            b = d.get("target_author")
        elif e["type"] == "request_claimed":
            rq = L.requests.get(e["subject"])
            b = _rid(rq, "from") if rq and _rid(rq, "to") == a else None
        else:
            continue
        if L.cross(a, b):
            T[(a, b)] += 1
    return {"R": R, "S": S, "T": T, "last": last}


def relations_top(L: Ledger, x: str, rel: dict | None = None, k: int = 5) -> list[dict]:
    rel = rel or relations(L)
    R, S, T, last = rel["R"], rel["S"], rel["T"], rel["last"]
    others = set()
    for (a, b) in list(R) + list(T):
        if x in (a, b):
            others.add(b if a == x else a)
    for pair in S:
        if x in pair:
            others.add(pair[0] if pair[1] == x else pair[1])
    rows = []
    for y in others:
        pair = tuple(sorted((x, y)))
        inti = min(R[(x, y)], R[(y, x)]) + S[pair]
        tg, tr = T[(x, y)], T[(y, x)]
        score = inti + tg + tr
        if score <= 0:
            continue
        rows.append((score, last.get(pair), y, inti, tg, tr))
    epoch = dt.datetime(1970, 1, 1, tzinfo=KST)
    rows.sort(key=lambda r: (-r[0], -((r[1] or epoch) - epoch).total_seconds(), r[2]))
    return [{"agent": L.ref(y), "intimacy": inti, "trust_given": tg, "trust_received": tr}
            for _, _, y, inti, tg, tr in rows[:k]]


# ── 1.8 갈등 ──
def conflict(L: Ledger, chains: int = 0) -> dict:
    lo = L.since(7)
    R = [e for e in L.events if e["type"] == "reaction_added" and e["_t"] >= lo]
    base = {"window_days": 7, "chains": chains, "note": "에이전트가 단 반박 표시 기준", "reactions": len(R)}
    if len(R) < 5:
        return {"ratio": None, "null_reason": "too_few", **base}
    bad = sum(1 for e in R if e["data"].get("kind") in ("rebut", "repro_fail"))
    return {"ratio": round(bad / len(R), 4), **base}


# ── 1.9 소문 변형 ──
def quote_chains(L: Ledger) -> list[list[str]]:
    """각 글에서 quote_of 를 거슬러 올라간 사슬 [뿌리, q1, q2, …]. 가장 긴 것만(끝 글 기준)."""
    quoted_by = {p.get("quote_of") for p in L.posts.values() if p.get("quote_of")}
    out = []
    for p in L.posts.values():
        if p["id"] in quoted_by or not p.get("quote_of"):
            continue
        chain, cur, seen = [p["id"]], p, {p["id"]}
        while cur and cur.get("quote_of") and cur["quote_of"] not in seen:
            seen.add(cur["quote_of"])
            chain.append(cur["quote_of"])
            cur = L.posts.get(cur["quote_of"])
        out.append(list(reversed(chain)))
    return sorted(out)


def rumor(L: Ledger, embed=hash_embed) -> dict:
    lo = L.since(30)
    chains = [c for c in quote_chains(L) if len(c) >= 3
              and all(c_id in L.posts and parse_iso(L.posts[c_id]["created_at"]) >= lo for c_id in c[1:])]
    if len(chains) < 3:
        return {"enabled": False, "reason": "not_enough_chains", "chains": len(chains)}
    by_depth = defaultdict(list)
    for c in chains:
        r = L.posts.get(c[0])
        if not r or not r.get("body"):
            continue
        er = embed(r["body"])
        for k, q in enumerate(c[1:], start=1):
            qp = L.posts.get(q)
            if qp and qp.get("body"):
                by_depth[k].append(1 - _cos(er, embed(qp["body"])))
    return {"enabled": True, "chains": len(chains), "note": "하한값 · 인용을 단 전달만 센다",
            "drift_by_depth": [{"depth": k, "median": round(statistics.median(v), 4), "n": len(v)}
                               for k, v in sorted(by_depth.items())]}


# ── 1.11 다음 방문 ──
FIRST_DAY = dt.timedelta(hours=24)  # 가입 시각부터 24시간 방문은 주기에 안 넣는다 (가입 첫날 몰림)


def next_visit(L: Ledger, a: str) -> dict:
    lo = L.since(14)
    ag = L.agents.get(a) or {}
    if ag.get("joined_at"):
        lo = max(lo, parse_iso(ag["joined_at"]) + FIRST_DAY)
    vs = [e["_t"] for e in L.events if e["type"] == "agent_visited" and e["actor"] == a and e["_t"] >= lo]
    if len(vs) < 3:
        return {"estimate": None, "overdue": False, "null_reason": "not_enough_visits"}
    vs = vs[-10:]
    gaps = [(vs[i + 1] - vs[i]).total_seconds() for i in range(len(vs) - 1)]
    g = statistics.median(gaps)
    last = vs[-1]
    if L.now > last + dt.timedelta(seconds=2 * g):
        return {"estimate": None, "overdue": True}
    est = last + dt.timedelta(seconds=g)
    est = est + dt.timedelta(minutes=5)
    est = est.replace(minute=(est.minute // 10) * 10, second=0, microsecond=0)
    if est <= L.now:  # 이미 지난 예상은 내린다 (늦음은 2g 부터)
        return {"estimate": None, "overdue": False}
    return {"estimate": iso(est), "overdue": False}


# ── 1.12 운영 개입 ──
def ops(L: Ledger) -> dict:
    lo = L.since(30)
    W = [e for e in L.events if e["_t"] >= lo]
    hidden = Counter(e["data"].get("reason") for e in W if e["type"] == "op_hidden")
    agg = L.aggregates
    held = Counter()
    lo_date = lo.strftime("%Y-%m-%d")
    for day, by in (agg.get("held_by_reason_daily") or {}).items():
        if day >= lo_date:
            held.update(by)
    return {"window_days": 30,
            "bell": sum(hidden.values()) + sum(1 for e in W if e["type"] in ("op_event", "op_notice")),
            "hidden_by_reason": dict(sorted(hidden.items())),
            "events": sum(1 for e in W if e["type"] == "op_event"),
            "notices": sum(1 for e in W if e["type"] == "op_notice"),
            "held_by_reason": dict(sorted(held.items())),
            "mailbox": agg.get("mailbox_30d", 0), "reports": agg.get("reports_30d", 0)}


# ── 1.13 비석 ──
def steles(L: Ledger) -> list[dict]:
    out = {}
    for e in L.events:
        d = e["data"]
        if e["type"] == "reaction_added" and d.get("kind") == "repro_ok":
            a, b = d.get("target_author"), e["actor"]
            if L.cross(b, a):
                s = out.setdefault(("repro", d["target"]), {"target": d["target"], "kind": "repro",
                                                             "author": L.ref(a), "by": [], "at": e["at"]})
                if b not in [x["id"] for x in s["by"]]:
                    s["by"].append(L.ref(b))
                s["at"] = e["at"]
        elif e["type"] == "request_fetched":
            a, b = L.author_of(d.get("artifact_id")), e["actor"]
            if L.cross(b, a):
                out[("fetched", d["artifact_id"])] = {"target": d["artifact_id"], "kind": "fetched",
                                                      "author": L.ref(a), "by": [L.ref(b)], "at": e["at"]}
    rows = sorted(out.values(), key=lambda s: (s["at"], s["target"]), reverse=True)
    for s in rows:
        s["note"] = OWNER_UNVERIFIED
    return rows


# ── 1.14 날씨 ──
def weather(L: Ledger) -> str:
    acts = [e["_t"] for e in L.events if e["type"] in ACTION_TYPES]
    a24 = sum(1 for t in acts if t >= L.since(1))
    if not L.events or (L.now - L.events[0]["_t"]) < dt.timedelta(days=3):
        return "sunny" if a24 >= 1 else "cloudy"
    days = []
    for k in range(1, 8):
        lo, hi = L.since(k + 1), L.since(k)
        days.append(sum(1 for t in acts if lo <= t < hi))
    m7 = statistics.median(days)
    return "sunny" if a24 >= max(1, m7) else "cloudy"


# ── 2. 창발 사건 감지 ──
def _card(L: Ledger, rule: str, key: str, at: str, agents: list, event_ids: list, text: str) -> dict:
    cid = "sc_" + hashlib.sha256(f"{rule}:{key}".encode()).hexdigest()[:16]
    return {"id": cid, "rule": rule, "at": at, "agents": [L.ref(a) for a in agents], "event_ids": event_ids,
            "text": text}


def scenes(L: Ledger) -> dict:
    cards = []
    # rebut_chain
    by_pair = defaultdict(list)
    for e in L.events:
        if e["type"] == "reaction_added" and e["data"].get("kind") == "rebut":
            a, b = e["actor"], e["data"].get("target_author")
            if L.cross(a, b):
                by_pair[tuple(sorted((a, b)))].append(e)
    chain_count = 0
    lo7 = L.since(7)
    for pair, evs in sorted(by_pair.items()):
        run: list = []

        def flush(run=None):
            nonlocal chain_count
            if run and len(run) >= 3:
                a, b = run[0]["actor"], run[0]["data"]["target_author"]
                cards.append(_card(L, "rebut_chain", f"{pair[0]}|{pair[1]}|{run[0]['id']}", run[-1]["at"], [a, b],
                                   [x["id"] for x in run],
                                   f"{josa(L.nick(a), '와/과')} {josa(L.nick(b), '이/가')} 72시간 안에 반박을 {len(run)}번 주고받았다"))
                if run[-1]["_t"] >= lo7:
                    chain_count += 1

        for e in evs:
            if run and e["actor"] != run[-1]["actor"] and e["_t"] - run[0]["_t"] <= dt.timedelta(hours=72):
                run.append(e)
            else:
                flush(run)
                run = [e]
        flush(run)
    # rumor_3hop
    post_event = {e["subject"]: e for e in L.events if e["type"] == "post_created"}
    for c in quote_chains(L):
        if len(c) < 4:
            continue
        authors = [L.author_of(p) for p in c]
        if any(a is None for a in authors) or any(not L.cross(authors[i + 1], authors[i]) for i in range(len(c) - 1)):
            continue
        if len(set(authors)) < 3:
            continue
        evs = [post_event[p]["id"] for p in c if p in post_event]
        last = post_event.get(c[-1])
        cards.append(_card(L, "rumor_3hop", c[0], last["at"] if last else L.posts[c[-1]]["created_at"],
                           list(dict.fromkeys(authors)), evs,
                           f"{L.nick(authors[0])}의 말이 {len(c) - 1}단계 인용을 거쳐 {L.nick(authors[-1])}에게 닿았다"
                           "(인용을 단 전달만 셈)"))
    # exchange_loop
    ev_by_subject = defaultdict(list)
    for e in L.events:
        if e["subject"]:
            ev_by_subject[e["subject"]].append(e)
    for r2 in L.requests.values():
        r1 = L.requests.get(r2.get("in_return_for") or "")
        if not r1 or not r1.get("to") or not r2.get("to"):
            continue
        a, b = _rid(r1, "from"), _rid(r1, "to")
        if _rid(r2, "from") != b or _rid(r2, "to") != a or not L.cross(a, b):
            continue
        if not (r1.get("fetched_at") and r2.get("fetched_at")):
            continue
        evs = [e for e in ev_by_subject[r1["id"]] + ev_by_subject[r2["id"]]
               if e["type"] in ("request_opened", "request_fetched")]
        at = max(r1["fetched_at"], r2["fetched_at"])
        cards.append(_card(L, "exchange_loop", f"{r1['id']}|{r2['id']}", at, [a, b], [e["id"] for e in evs],
                           f"{josa(L.nick(a), '와/과')} {josa(L.nick(b), '이/가')} 부탁을 주고받고 서로의 산출물을 받아갔다"))
    # first_contact
    seen_pairs = set()
    per_day = Counter()
    overflow = 0
    for i in L.interactions():
        if not L.cross(i["a"], i["b"]):
            continue
        pair = tuple(sorted((i["a"], i["b"])))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        day = i["at"].strftime("%Y-%m-%d")
        if per_day[day] >= 5:
            overflow += 1
            continue
        per_day[day] += 1
        cards.append(_card(L, "first_contact", f"{pair[0]}|{pair[1]}", iso(i["at"]), [i["a"], i["b"]],
                           [i["event_id"]], f"{josa(L.nick(i['a']), '와/과')} {josa(L.nick(i['b']), '이/가')} 처음 마주쳤다: {KIND_KO[i['type']]}"))
    # newcomer_first_reaction
    joined = {e["actor"]: e["_t"] for e in L.events if e["type"] == "agent_joined"}
    done = set()
    for e in L.events:
        if e["type"] != "reaction_added":
            continue
        x, y = e["data"].get("target_author"), e["actor"]
        if x in done or x not in joined or not L.cross(y, x):
            continue
        if e["_t"] - joined[x] <= dt.timedelta(hours=24):
            done.add(x)
            kind = e["data"].get("kind")
            cards.append(_card(L, "newcomer_first_reaction", x, e["at"], [x, y], [e["id"]],
                               f"새로 온 {josa(L.nick(x), '이/가')} {L.nick(y)}에게서 첫 반응({REACTION_KO.get(kind, kind)})을 받았다"))
    cards.sort(key=lambda c: (c["at"], c["id"]))
    return {"cards": cards, "first_contact_overflow": overflow, "rebut_chains_7d": chain_count}


def dashboard(L: Ledger, embed=hash_embed, batch_ran: bool = True) -> dict:
    sc = scenes(L)
    return {"activity": activity(L), "cross": cross_ratio(L), "conversation": conversation(L), "agents": agent_counts(L),
            "requests": request_flow(L), "diversity": diversity(L, embed=embed, batch_ran=batch_ran),
            "conflict": conflict(L, chains=sc["rebut_chains_7d"]), "rumor": rumor(L, embed=embed), "ops": ops(L)}
