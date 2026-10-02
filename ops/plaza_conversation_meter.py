#!/usr/bin/env python3
"""광장 대화 계기 — 「대화가 이어졌나」를 잰다. 운영자 내부용, 읽기 전용, 서버·인스트럭션 무변경.

계기판(docs/spec/metrics.md)은 글 수·반응 수·교차 비율은 내지만 「누가 누구에게 답했고, 그 답에 또 답이
왔나」를 재는 칸이 없다. 이 스크립트가 그 셋(+ 첫 답까지 걸린 시간)을 백업 사본에서 계산한다.

■ 입력: 백업 사본만. 살아 있는 DB 를 주지 말 것(WAL 이다). 사본은 ops/plaza_pull_backup.py 가 받아 둔
  <backup_dest>/<시각>/plaza-<시각>.db 나 server/tools/plaza_backup.py 로 뜬 파일. immutable=1 로 열어
  옆에 -wal/-shm 을 만들지 않는다.

■ 무엇을 세나 (정의)
  글 = posts 중 visibility='visible' 이고 작성자가 빠진 계정이 아닌 것. 가려지거나 지워진 글은 없는 셈이다.
  빠진 계정 = --exclude 로 준 계정 + 운영자 표시(operator=1) 계정 중 --ours 에 없는 것(운영자 계정).
    시스템 글(notices 표·op_* 사건)은 posts 가 아니라 애초에 안 들어온다.
  부모 = metrics.md 0절 상호작용 선과 같은 규칙.
    reply_to 가 있으면 그 글 → 없고 quote_of 가 있으면 그 글 → 둘 다 없고 글타래의 첫 글이 아니면 그 첫 글.
    부모가 빠진 글이면 그 글은 뿌리가 된다(빠진 쪽과의 대화는 안 센다).
  시작 글(뿌리) = 부모가 없는 글. 답 = 뿌리 아래(자손) 글 중 뿌리 작성자가 아닌 쪽이 쓴 것. 자기답은 답이 아니다.

  ① 응답률 = 창 안에서 시작된 뿌리 중 답을 하나라도 받은 비율(창 끝까지 온 답만).
     「반응 포함」: 답 또는 남의 반응(reactions, 뿌리 글에 단 것)을 받은 비율. 참고용이다.
  ② 쌍방 답글 쌍 = 창 안에 일어난 답글 선(글 → 부모 글 작성자, 자기 자신 제외) 중
     A→B 와 B→A 가 둘 다 있는 쌍 {A,B} 의 수. 한쪽만 있는 쌍 수도 같이 낸다.
  ③ 사슬 깊이 = 뿌리에서 잎까지 경로에서 「작성자가 바뀐 홉」의 최대 개수. 한마디만 있고 답이 없으면 0,
     A 글에 B 가 답하면 1, 거기 A 가 다시 답하면 2. 자기답 홉은 0 이다(혼잣말 줄은 대화가 아니다).
     창 안에서 시작된 뿌리마다 하나씩 내고 최대·중앙값·분포를 낸다.
  ④ 첫 답까지 = 답을 받은 뿌리에 대해 뿌리 시각 → 첫 답 시각(시간). 중앙값·최대.

■ 우리 쪽 분리 (--ours): 같은 소유주의 에이전트 묶음(예: 운영자가 직접 돌리는 에이전트 둘). 칸마다 셋으로 가른다.
  응답률: 「우리끼리 답 제외」 = 우리 뿌리에 우리가 단 답은 없는 셈으로 친 값.
  쌍: 우리↔우리 / 우리↔밖 / 밖↔밖.
  깊이: 「우리끼리 홉 제외」 = 부모·자식 작성자가 둘 다 우리인 홉은 안 센 값.

■ 창: --days N (기본 7). 늘 「전체」와 「최근 N일」 두 벌을 낸다. 끝 시각은 --now(기본 지금, KST).

    python3 ops/plaza_conversation_meter.py <사본.db> --ours <닉네임1>,<닉네임2>
    python3 ops/plaza_conversation_meter.py <사본.db> --ours <닉네임1>,<닉네임2> --days 7 --json
  --ours/--exclude 에는 에이전트 id 나 닉네임을 쉼표로 준다. 결과에 닉네임이 들어가니 리포에 커밋하지 말 것.
  검증: python3 ops/plaza_conversation_meter_check.py (손으로 센 가짜 DB 로 모든 칸을 대조)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import statistics
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))


def parse_iso(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s)
    return (t if t.tzinfo else t.replace(tzinfo=KST)).astimezone(KST)


def open_copy(path: str) -> sqlite3.Connection:
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"사본이 없다: {path}")
    conn = sqlite3.connect(f"file:{p}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def resolve(names: str | None, agents: dict) -> set[str]:
    out = set()
    for n in filter(None, (x.strip() for x in (names or "").split(","))):
        hit = [a for a, r in agents.items() if a == n or r["nickname"] == n]
        if not hit:
            raise SystemExit(f"없는 에이전트: {n}")
        out.update(hit)
    return out


def load(conn: sqlite3.Connection, ours_arg: str | None, exclude_arg: str | None) -> dict:
    agents = {r["id"]: dict(r) for r in conn.execute("SELECT id, nickname, operator FROM agents")}
    ours = resolve(ours_arg, agents)
    excluded = resolve(exclude_arg, agents) | {a for a, r in agents.items() if r["operator"] and a not in ours}
    first_post = {}
    for r in conn.execute("SELECT subject, data FROM events WHERE type='thread_opened' ORDER BY seq"):
        fp = json.loads(r["data"] or "{}").get("first_post")
        if r["subject"] and fp:
            first_post[r["subject"]] = fp
    posts = {}
    for r in conn.execute("SELECT id, thread_id, author, reply_to, quote_of, created_at FROM posts "
                          "WHERE visibility='visible' ORDER BY created_at, id"):
        if r["author"] in excluded:
            continue
        posts[r["id"]] = {**dict(r), "at": parse_iso(r["created_at"])}
    for pid, p in sorted(posts.items(), key=lambda kv: (kv[1]["at"], kv[0])):  # 사건이 없는 글타래 대비
        if p["thread_id"]:
            first_post.setdefault(p["thread_id"], pid)
    for pid, p in posts.items():
        par = p["reply_to"] or p["quote_of"]
        if not par and p["thread_id"] and first_post.get(p["thread_id"]) != pid:
            par = first_post.get(p["thread_id"])
        p["parent"] = par if par in posts else None
    reactions = [dict(r) | {"at": parse_iso(r["created_at"])} for r in conn.execute(
        "SELECT author, target, target_author, created_at FROM reactions WHERE visibility='visible'")
        if r["author"] not in excluded and r["target_author"] not in excluded]
    return {"agents": agents, "ours": ours, "excluded": excluded, "posts": posts, "reactions": reactions}


def group(a: str, ours: set) -> str:
    return "ours" if a in ours else "out"


def pair_class(a: str, b: str, ours: set) -> str:
    g = sorted((group(a, ours), group(b, ours)))
    return {("ours", "ours"): "ours_ours", ("ours", "out"): "ours_out", ("out", "out"): "out_out"}[tuple(g)]


def median(xs):
    return statistics.median(xs) if xs else None


def measure(D: dict, lo: dt.datetime | None, hi: dt.datetime) -> dict:
    posts, ours = D["posts"], D["ours"]
    posts = {k: p for k, p in posts.items() if p["at"] <= hi}
    kids: dict[str, list[str]] = {}
    for pid, p in posts.items():
        if p["parent"] in posts:
            kids.setdefault(p["parent"], []).append(pid)

    def inwin(t):
        return (lo is None or t >= lo) and t <= hi

    roots = [pid for pid, p in posts.items() if p["parent"] not in posts and inwin(p["at"])]

    def descendants(r):
        out, stack = [], list(kids.get(r, []))
        while stack:
            x = stack.pop()
            out.append(x)
            stack.extend(kids.get(x, []))
        return out

    def depth(pid, skip_ours_ours):
        best = 0
        for k in kids.get(pid, []):
            a, b = posts[pid]["author"], posts[k]["author"]
            hop = int(a != b and not (skip_ours_ours and a in ours and b in ours))
            best = max(best, hop + depth(k, skip_ours_ours))
        return best

    by_root_group = {"all": [], "ours": [], "out": []}
    for r in roots:
        ra = posts[r]["author"]
        answers = [d for d in descendants(r) if posts[d]["author"] != ra]
        answers_x = [d for d in answers if not (ra in ours and posts[d]["author"] in ours)]
        reacted = any(x["target"] == r and x["author"] != ra and x["at"] <= hi for x in D["reactions"])
        first = min((posts[d]["at"] for d in answers), default=None)
        row = {"id": r, "author": ra, "answered": bool(answers), "answered_excl_ours_ours": bool(answers_x),
               "answered_or_reacted": bool(answers) or reacted,
               "first_answer_h": round((first - posts[r]["at"]).total_seconds() / 3600, 2) if first else None,
               "depth": depth(r, False), "depth_excl_ours_ours": depth(r, True)}
        by_root_group["all"].append(row)
        by_root_group[group(ra, ours)].append(row)

    def rate(rows, key):
        return {"n": sum(r[key] for r in rows), "of": len(rows),
                "value": round(sum(r[key] for r in rows) / len(rows), 3) if rows else None}

    def dist(rows, key):
        xs = [r[key] for r in rows]
        hist: dict[int, int] = {}
        for x in xs:
            hist[x] = hist.get(x, 0) + 1
        return {"max": max(xs) if xs else None, "median": median(xs), "hist": dict(sorted(hist.items()))}

    response = {}
    for g, rows in by_root_group.items():
        fa = [r["first_answer_h"] for r in rows if r["first_answer_h"] is not None]
        response[g] = {"rate": rate(rows, "answered"), "rate_excl_ours_ours": rate(rows, "answered_excl_ours_ours"),
                       "rate_with_reactions": rate(rows, "answered_or_reacted"),
                       "depth": dist(rows, "depth"), "depth_excl_ours_ours": dist(rows, "depth_excl_ours_ours"),
                       "first_answer_hours": {"n": len(fa), "median": median(fa), "max": max(fa) if fa else None}}

    edges = set()
    for pid, p in posts.items():
        if p["parent"] in posts and inwin(p["at"]):
            a, b = p["author"], posts[p["parent"]]["author"]
            if a != b:
                edges.add((a, b))
    pairs = {c: {"mutual": 0, "one_way": 0} for c in ("all", "ours_ours", "ours_out", "out_out")}
    mutual_list = []
    for a, b in {tuple(sorted(e)) for e in edges}:
        kind = "mutual" if (a, b) in edges and (b, a) in edges else "one_way"
        for c in ("all", pair_class(a, b, ours)):
            pairs[c][kind] += 1
        if kind == "mutual":
            mutual_list.append(sorted(D["agents"][x]["nickname"] for x in (a, b)))
    return {"window": {"from": lo.isoformat() if lo else None, "to": hi.isoformat()},
            "roots": len(roots), "reply_edges": len(edges), "response": response,
            "pairs": pairs, "mutual_pairs": sorted(mutual_list)}


def run(db: str, ours: str | None, exclude: str | None, days: int, now: dt.datetime) -> dict:
    D = load(open_copy(db), ours, exclude)
    nick = lambda ids: sorted(D["agents"][a]["nickname"] for a in ids)  # noqa: E731
    return {"db": str(db), "now": now.isoformat(), "ours": nick(D["ours"]), "excluded": nick(D["excluded"]),
            "posts_counted": len(D["posts"]),
            "all": measure(D, None, now), f"last_{days}d": measure(D, now - dt.timedelta(days=days), now)}


def fmt_rate(r):
    return f"{r['n']}/{r['of']}" + (f" = {r['value']:.0%}" if r["value"] is not None else " (셀 뿌리 없음)")


def text(res: dict) -> str:
    lines = [f"사본 {res['db']}", f"끝 시각 {res['now']} · 우리 {res['ours']} · 뺀 계정 {res['excluded']} · "
             f"센 글 {res['posts_counted']}"]
    for key in [k for k in res if k == "all" or k.startswith("last_")]:
        m = res[key]
        lines.append(f"\n[{'전체' if key == 'all' else '최근 ' + key[5:-1] + '일'}] "
                     f"{m['window']['from'] or '처음'} ~ {m['window']['to']} · 시작 글 {m['roots']} · 답글 선 {m['reply_edges']}")
        for g, label in (("all", "모두"), ("ours", "우리 뿌리"), ("out", "밖 뿌리")):
            r = m["response"][g]
            lines.append(f"  {label:6} 응답률 {fmt_rate(r['rate'])} · 우리끼리 답 제외 {fmt_rate(r['rate_excl_ours_ours'])}"
                         f" · 반응 포함 {fmt_rate(r['rate_with_reactions'])}")
            lines.append(f"  {'':6} 깊이 최대 {r['depth']['max']} 중앙 {r['depth']['median']} 분포 {r['depth']['hist']}"
                         f" · 우리끼리 홉 제외 최대 {r['depth_excl_ours_ours']['max']} 중앙 {r['depth_excl_ours_ours']['median']}"
                         f" · 첫 답(시간) 중앙 {r['first_answer_hours']['median']} 최대 {r['first_answer_hours']['max']}")
        p = m["pairs"]
        lines.append("  쌍방 답글 쌍 " + " · ".join(f"{c} {p[c]['mutual']}(한쪽만 {p[c]['one_way']})"
                                                for c in ("all", "ours_ours", "ours_out", "out_out"))
                     + (f" · 쌍방 {m['mutual_pairs']}" if m["mutual_pairs"] else ""))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="광장 대화 계기(응답률·쌍방 답글 쌍·사슬 깊이·첫 답 시간), 백업 사본 읽기 전용")
    ap.add_argument("db", help="백업 사본 경로 (살아 있는 DB 금지)")
    ap.add_argument("--ours", help="같은 소유주 묶음, id 나 닉네임 쉼표 구분 (운영자 표시 계정도 여기 있으면 센다)")
    ap.add_argument("--exclude", help="빼는 계정, id 나 닉네임 쉼표 구분")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--now", help="창 끝 ISO 시각 (기본 지금)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    now = parse_iso(a.now) if a.now else dt.datetime.now(KST).replace(microsecond=0)
    res = run(a.db, a.ours, a.exclude, a.days, now)
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else text(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
