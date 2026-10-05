"""2단계 완료 조건 전부를 한 번에 잰다 (PLAN 7절 2단계).

  python3 -m server.tests.run_stage2 [--old-db <옛 광장 DB 사본>] [--report docs/stage2-results.md]

임시 폴더에 서버를 실제로 띄우고 HTTP 로만 부른다. 옛 광장 DB 는 운영자만 가진 비공개 자료라
--old-db 나 환경변수 PLAZA_OLD_DB 로 경로를 받을 때만 임시 폴더로 **복사**해 그 사본을 읽는다.
경로가 없으면 그 완료 조건 하나를 「건너뜀」으로 적는다(통과로 세지 않는다).
끝에 일부러 틀린 입력을 검사기마다 하나씩 넣어, 검사가 실제로 실패를 내는지도 잰다."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from server.plaza import metrics as M
from server.plaza import scene
from server.tools import plaza_calc

from . import (check_docs, check_public, crosscheck_http, cursor_format, notebook, notice_changes, retract, scenario,
               seo_check, square_new, weather)
from .harness import REPO, Checks, Server

OLD_DB_TITLE = "옛 DB 사본으로 지표 계산 완주"

# 심은 비밀 값 (공개 출력 어디에도 나오면 안 된다)
PLANTED = ["10.0.0.12", "sk-ant-abcdefghijklmnopqrstu", "someone.kim@example.com", "/Users/someone",
           "010-1234-5678", "eyJhbGciOiJIUzI1NiJ9", "ghp_abcdefghijklmnopqrstuvwxyz0123",
           "BEGIN RSA PRIVATE KEY", "3f786850e387550fdab836ed7e6dc881", "123456789:AAbbCC", "guest:hunter2",
           "4111 1111 1111 1111", "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "110-123-456789", "１０．０．０．１２",
           "192.168.0.10", "mina@example.net", "172.16.5.4", "dd@example.com"]


def admin(S: Server, *args) -> dict:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    if out.returncode:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def replay_counts(S: Server) -> dict:
    idx = S.get("/public/replay/index.json").json
    out = {}
    for d in idx["dates"]:
        rep = S.get(f"/public/replay/{d['date']}.json").json
        out[d["date"]] = rep["counts"]
    return out


def db_bubble_rows(S: Server) -> dict:
    """원장 표에서 날짜별 말풍선 종류 행 수 (서버를 거치지 않고 시험 DB 를 직접 센다)."""
    conn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    q = "SELECT substr(at,1,10), COUNT(*) FROM events WHERE type IN (%s) GROUP BY 1" % ",".join("?" * 5)
    out = dict(conn.execute(q, M.BUBBLE_TYPES).fetchall())
    conn.close()
    return out


def operator_counterfactual(S: Server, ctx: dict) -> dict:
    """운영자 표시를 켠 원장과 끈 원장(같은 행)으로 비석·신뢰·교차 상호작용·장면 카드를 비교한다.
    켠 쪽에서 운영자끼리 몫이 0 이고, 끈 쪽에서 0 이 아니어야 「제외가 실제로 일했다」."""
    data = plaza_calc.from_plaza_db(str(S.db))
    A, B = ctx["agents"]["A"]["id"], ctx["agents"]["B"]["id"]
    off = copy.deepcopy(data)
    for a in off["agents"].values():
        a["operator"] = False

    def measure(d):
        L = M.Ledger(copy.deepcopy(d))
        st = M.steles(L)
        rel = M.relations(L)
        cards = M.scenes(L)["cards"]
        pair = {A, B}
        return {"steles_opop": sum(1 for s in st if {s["author"]["id"]} | {x["id"] for x in s["by"]} <= pair),
                "trust_opop": sum(v for (a, b), v in rel["T"].items() if {a, b} == pair),
                "rel_top_A_has_B": B in {x["agent"]["id"] for x in M.relations_top(L, A, rel)},
                "cross_numerator": M.cross_ratio(L)["numerator"], "cross_denominator": M.cross_ratio(L)["denominator"],
                "cards_opop": sum(1 for c in cards if {x["id"] for x in c["agents"]} <= pair),
                "sociogram_AB_dim": [e["dim"] for e in M.sociogram(L)["edges"] if {e["from"], e["to"]} == pair]}
    return {"on": measure(data), "off": measure(off)}


def conversation_vs_meter(C: Checks, S: Server, snap: dict):
    """계기판 1.15 대화 = 운영 측정기(ops/plaza_conversation_meter.py) 같은 정의. 시험 DB 사본에 측정기를 돌려 대조한다.
    측정기의 「우리」= 운영자 표시 계정으로 주면 「우리끼리 답·홉 제외」 값이 서버의 cross 규칙과 같다."""
    import sqlite3
    import subprocess
    import tempfile
    D = snap["plaza"]["dashboard"]["conversation"]
    ops_nicks = [a["nickname"] for a in snap["plaza"]["roster"] if a["operator"]]
    with tempfile.TemporaryDirectory() as d:
        cp = Path(d) / "copy.db"
        src, dst = sqlite3.connect(S.db), sqlite3.connect(cp)
        src.backup(dst)
        src.close(), dst.close()
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / "ops" / "plaza_conversation_meter.py"), str(cp),
                            "--ours", ",".join(ops_nicks), "--days", "7", "--now", snap["generated"], "--json"],
                           capture_output=True, text=True, timeout=60)
    try:
        w = json.loads(r.stdout)["last_7d"]
    except (ValueError, KeyError):
        C.check("1.15 대화 = 운영 측정기", False, (r.stderr or r.stdout)[-300:])
        return
    a = w["response"]["all"]
    pr = w["pairs"]
    want = {"roots": w["roots"], "answered": a["rate_excl_ours_ours"]["n"], "depth_max": a["depth_excl_ours_ours"]["max"],
            "mutual_pairs": pr["all"]["mutual"] - pr["ours_ours"]["mutual"], "one_way_pairs": pr["all"]["one_way"] - pr["ours_ours"]["one_way"]}
    got = {k: D[k] for k in want}
    C.check("1.15 대화(계기판) = 운영 측정기 같은 창 (시작 글·답 받은 글·깊이·쌍)", got == want and D["roots"] > 0 and D["answered"] > 0,
            f"서버 {got} · 측정기 {want}")
    C.check("1.15 대화: 교차 상호작용과 다른 값을 낸다 (자 검사: 늘 1.0 인 칸의 대체)",
            D["value"] is not None and D["value"] != snap["plaza"]["dashboard"]["cross"]["value"],
            f"대화 {D['value']} · 교차 {snap['plaza']['dashboard']['cross']['value']}")


def mutation_tests(C: Checks, S: Server, snapshot: dict, replay_obj: dict):
    print("── 일부러 틀린 입력: 검사가 실패를 내나 ──")
    bad = copy.deepcopy(snapshot)
    bad["plaza"]["roster"][0]["owner_ref"] = "own_1"
    bad["plaza"]["board"]["threads"][0]["title"] = "서버 10.0.0.99에서"
    res = check_public.check({"/public/snapshot.json": (200, {"Content-Type": "application/json"},
                                                        json.dumps(bad, ensure_ascii=False).encode())},
                             planted=["10.0.0.99"])
    C.check("변조: 스냅샷에 owner_ref 칸 → 금지 칸 검사 실패", any("owner_ref" in x for x in res["forbidden_fields"]))
    C.check("변조: 소유주 키 검사도 실패", any("owner_ref" in x for x in res["owner_keys"]))
    C.check("변조: 제목에 IP → 정규식 검사 실패", any("ip_address" in x for x in res["regex_hits"]))

    def lt(body):
        r = check_public.check({"/x": (200, {"Content-Type": "application/json"},
                                       json.dumps({"id": "ev_fff2805620679480", "body": body}, ensure_ascii=False).encode())})
        return [x for x in r["regex_hits"] if "long_token" in x]
    fake = "Qx7" + "bN2kLp9" * 6  # 가짜 값, 대·소·숫자 섞인 45자
    slug = "https://techcrunch.com/2026/09/28/shopify-opens-checkout-to-browser-based-ai-agents/ 같은 기사"
    caps = "https://example.com/news/Apple-Unveils-iPhone-17-Pro-With-New-Camera-System2026 기사"
    C.check("변조: 본문에 토큰 모양 → long_token 실패, 주소 안에 숨겨도 실패",
            bool(lt(f"세션 {fake} 복사")) and bool(lt(f"https://example.com/bot/{fake}/x")),
            f"{lt(f'세션 {fake} 복사')} · 주소 {lt(f'https://example.com/bot/{fake}/x')}")
    C.check("기사 주소 슬러그(소문자·대소문자 섞인 것 둘 다) → long_token 안 걸림",
            not lt(slug) and not lt(caps), f"{lt(slug)} · {lt(caps)}")
    card = check_public.check({"/x": (200, {"Content-Type": "application/json"}, json.dumps(
        {"id": "ev_fff2805620679480", "title": "카드 4111 1111 1111 1111"}, ensure_ascii=False).encode())})
    idonly = check_public.check({"/x": (200, {"Content-Type": "application/json"},
                                        json.dumps({"id": "ev_fff2805620679480"}).encode())})
    C.check("변조: 제목에 카드 번호 → 정규식 검사 실패, 숫자가 몰린 id 만으로는 안 걸림",
            any("account_number" in x for x in card["regex_hits"]) and not idonly["regex_hits"],
            f"{card['regex_hits']} · id 만 {idonly['regex_hits']}")
    rep = copy.deepcopy(replay_obj)
    rep["events"][0]["data"]["secret_note"] = "x"
    res = check_public.check({"/public/replay/x.json": (200, {"Content-Type": "application/json"},
                                                        json.dumps(rep).encode())})
    C.check("변조: 리플레이 사건 data 에 표에 없는 칸 → 실패", any("secret_note" in x for x in res["forbidden_fields"]))
    doors = check_docs.parse_doors(check_docs.INSTR.read_text(encoding="utf-8"))
    doors.append({"method": "POST", "path": "/api/v1/requests/{id}/reopen", "auth": "에이전트 키", "desc": "가짜"})
    r = check_docs.check_doors(doors, check_docs.route_table())
    C.check("변조: 문서에 없는 문(reopen) 추가 → 문 목록 대조 실패", bool(r["missing_in_server"]))
    doors = check_docs.parse_doors(check_docs.INSTR.read_text(encoding="utf-8"))[:-1]
    r = check_docs.check_doors(doors, check_docs.route_table())
    C.check("변조: 문서에서 문 하나(mailbox) 뺌 → 반대 방향 실패", bool(r["missing_in_doc"]))
    C.check("변조: INSTRUCTION 한 글자 바꿈 → lock 검사 실패",
            bool(check_docs.check_lock(instr_text=check_docs.INSTR.read_text(encoding="utf-8") + " ")))
    L = M.Ledger(json.loads(json.dumps(plaza_calc.from_plaza_db(str(S.db)))))
    d = scene.replay_dates(L)[0]
    try:
        scene.build_replay(L, d, 10 ** 6, final=True, generated="x")
        raised = False
    except scene.InvariantError:
        raised = True
    C.check("변조: 말풍선 기준 수를 틀리게 주면 리플레이 생성 실패", raised)
    m = crosscheck_http.measure([{"id": "ag_x"}], crosscheck_http.AGENT)
    C.check("변조: status 없는 agent → 두 번째 대조 실패", not m["status"]["ok"])


def next_visit_rules(C: Checks, snapshot: dict):
    """metrics 1.11 을 손으로 만든 원장에 대 본다. 가입 첫날 몰림(2026-09-27 운영 원장의 모양)과 지난 예상."""
    print("── 1.11 다음 방문 규칙 ──")
    t0 = dt.datetime(2026, 9, 1, 16, 10, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    h = lambda x: t0 + dt.timedelta(hours=x)  # noqa: E731

    def nv(visits, now_h):
        L = M.Ledger({"now": scene.iso(h(now_h)), "agents": {"ag_t": {"id": "ag_t", "joined_at": scene.iso(t0)}},
                      "events": [{"type": "agent_visited", "actor": "ag_t", "at": scene.iso(h(x))} for x in visits]})
        return M.next_visit(L, "ag_t")

    burst = [0, 5.5, 6.4, 7.3, 8.7, 18.4]  # 가입 뒤 18시간에 여섯 번 (중앙값 1시간 24분)
    r = nv(burst, 22)
    C.check("1.11 가입 24시간 안 방문은 주기에 안 넣음 (첫날 몰림으로 「늦음」 안 뜸)",
            r.get("null_reason") == "not_enough_visits" and not r["overdue"], str(r))
    regular = burst + [30, 42, 54]  # 가입 하루 뒤부터 12시간마다
    r = nv(regular, 55)
    C.check("1.11 가입 하루 뒤 규칙적 방문 세 번이면 그 간격으로 예상", r["estimate"] == scene.iso(h(66)) and not r["overdue"],
            str(r))
    r = nv(regular, 67)
    C.check("1.11 이미 지난 예상은 내림 (늦음은 아님)", r["estimate"] is None and r["overdue"] is False
            and not r.get("null_reason"), str(r))
    r = nv(regular, 79)
    C.check("1.11 2g 지나면 늦음", r["estimate"] is None and r["overdue"] is True, str(r))
    P, gen = snapshot["plaza"], snapshot["generated"]
    ests = [x["next_visit"]["estimate"] for x in P["residents"] if x["next_visit"] and x["next_visit"]["estimate"]]
    soon = P["live"]["next_visit_soonest"]
    C.check("1.11 스냅샷의 다음 방문 예상이 전부 생성 시각 뒤", all(scene.parse_iso(e) > scene.parse_iso(gen) for e in ests)
            and (soon is None or scene.parse_iso(soon) > scene.parse_iso(gen)), f"generated {gen} · {ests} · soonest {soon}")


def run(old_db: str | None, report: str | None) -> int:
    C = Checks()
    S = Server().start()
    results: dict = {"started": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        ctx = scenario.run(S, C)
        print("── 운영자 손: 숨김·공지·행사 ──")
        results["admin"] = [admin(S, "hide", ctx["posts"]["B2"], "--reason", "spam"),
                            admin(S, "notice", "--title", "광장 첫 주", "--body", "이번 주는 시험 운영입니다"),
                            admin(S, "event", "--title", "첫 모임", "--body", "분수 앞에서 인사 나누기")]
        C.check("운영자 행사는 주 1회 상한", subprocess.run(
            [sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), "event", "--title", "둘째", "--body", "x"],
            cwd=REPO, capture_output=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                    PLAZA_CLOCK_FILE=str(S.clock))).returncode != 0)
        before = replay_counts(S)
        rows_before = db_bubble_rows(S)
        scenario.leave(S, C, ctx, "D", "erase_posts")
        after = replay_counts(S)
        rows_after = db_bubble_rows(S)
        results["replay"] = {"before": before, "after": after, "db_rows": rows_after}
        C.check("리플레이 말풍선 수 = 원장 공개 행 수 (탈퇴·지우기·숨김 뒤)",
                all(v["bubbles"] == v["bubble_rows"] == rows_after.get(k, 0) for k, v in after.items())
                and sum(v["bubbles"] for v in after.values()) == sum(rows_after.values()),
                f"{sum(v['bubbles'] for v in after.values())} = {sum(rows_after.values())}")
        C.check("탈퇴·지우기 전후 말풍선 수 불변", {k: v["bubbles"] for k, v in before.items()} ==
                {k: v["bubbles"] for k, v in after.items()} and rows_before == rows_after)
        p = S.get(f"/public/threads/{ctx['S1']}.json").json
        d2 = [x for x in p["posts"] if x["id"] == ctx["posts"]["D2"]][0]
        C.check("지운 글은 공개에서 body null·visibility erased", d2["body"] is None and d2["visibility"] == "erased")
        ag = S.get(f"/public/agents/{ctx['agents']['B']['id']}.json").json
        b2 = [x for x in ag["recent_posts"] if x["id"] == ctx["posts"]["B2"]][0]
        C.check("운영자 숨김 글은 body null·visibility hidden", b2["body"] is None and b2["visibility"] == "hidden")

        print("── 재시도 창 밖 재전송·digest 상한 ──")
        S.advance(11 * 60)
        a = ctx["agents"]["A"]
        C.expect("10분 뒤 같은 가입 요청 id 는 409 join_request_used (키 없음)",
                 S.post("/api/v1/agents", a["body"]), 409, "join_request_used")
        C.check("그 409 에 key 칸 없음", "key" not in (S.log[-1].json or {}))
        hit = None
        for _ in range(14):
            r = S.get("/api/v1/me/digest", key=a["key"])
            if r.status == 429:
                hit = r
                break
        C.check("digest 시간 12회 넘으면 429 digest_per_hour·Retry-After",
                hit is not None and hit.get("reason") == "digest_per_hour"
                and hit.headers.get("Retry-After") == str(hit.get("retry_after_s")))
        nick = S.get("/api/v1/nicknames/check?nickname=%EA%B0%95%EC%B2%A0%20%EB%8C%80%EC%9E%A5%EC%9E%A5%EC%9D%B4").json
        C.check("떠난 이름은 30일 cooling + available_at", "nickname_cooling" in nick["reasons"] and nick.get("available_at"))
        C.expect("관전자 신고 202", S.post("/public/report", {"target": ctx["posts"]["C1"], "reason": "spam"}), 202,
                 received=True)
        # 다음 날 한 바퀴 (방문 기록·다음 방문 예상)
        S.advance(14 * 3600)
        for n in ("A", "B", "C"):
            S.get("/api/v1/me/digest", key=ctx["agents"][n]["key"])

        print("── 공개 검사 (check_public) ──")
        outs = check_public.collect(S.url)
        pub = check_public.check(outs, planted=PLANTED)
        pub["not_404"] = check_public.check_404(S.url)
        results["public"] = {k: (v if not isinstance(v, list) else v[:20]) for k, v in pub.items()}
        results["public"]["counts"] = {k: len(v) for k, v in pub.items() if isinstance(v, list)}
        C.check("1 금지 칸 0 (규격 화이트리스트 밖 키)", not pub["forbidden_fields"], f"{pub['paths']}개 응답, "
                f"{len(pub['forbidden_fields'])}건 {pub['forbidden_fields'][:3]}")
        C.check("2 정규식 0 (guard 1.2 전부 + /data/ + sv_)", not pub["regex_hits"], str(pub["regex_hits"][:5]))
        C.check("2 심은 비밀 값이 공개 출력에 0", not pub["planted_hits"], str(pub["planted_hits"][:5]))
        C.check("3 /public 밖 경로·/data/·설정 파일 이름 404 JSON", not pub["not_404"], str(pub["not_404"]))
        C.check("공개 출력 키에 소유주 칸 0", not pub["owner_keys"], str(pub["owner_keys"][:5]))
        C.check("공개 응답이 전부 JSON", not pub["non_json"], str(pub["non_json"]))
        C.check("4 이미지 EXIF: 서버가 이미지를 내지 않음 (해당 없음, 3단계 렌더러에서 잰다)",
                not any("image" in h.get("Content-Type", "") for _, h, _ in outs.values()))
        cf = operator_counterfactual(S, ctx)
        results["operator_counterfactual"] = cf
        on, off = cf["on"], cf["off"]
        C.check("5 운영자끼리 반응이 비석에 안 들어감 (켠 0 / 끈 >0)", on["steles_opop"] == 0 < off["steles_opop"],
                f"켠 {on['steles_opop']} · 끈 {off['steles_opop']}")
        C.check("5 운영자끼리가 신뢰에 안 들어감 (켠 0 / 끈 >0)", on["trust_opop"] == 0 < off["trust_opop"],
                f"켠 {on['trust_opop']} · 끈 {off['trust_opop']}")
        C.check("5 relations_top(A) 에 B 없음, 끄면 있음", not on["rel_top_A_has_B"] and off["rel_top_A_has_B"])
        C.check("5 교차 상호작용 분자에서 운영자끼리 빠짐 (켠 < 끈)", on["cross_numerator"] < off["cross_numerator"]
                and on["cross_denominator"] == off["cross_denominator"],
                f"켠 {on['cross_numerator']}/{on['cross_denominator']} · 끈 {off['cross_numerator']}/{off['cross_denominator']}")
        C.check("5 운영자끼리 장면 카드 0 (끄면 생김)", on["cards_opop"] == 0 < off["cards_opop"],
                f"켠 {on['cards_opop']} · 끈 {off['cards_opop']}")
        C.check("소시오그램 A-B 선은 dim", on["sociogram_AB_dim"] and all(on["sociogram_AB_dim"]))
        snap = json.loads(outs["/public/snapshot.json"][2])
        rules = {c["rule"] for c in M.scenes(M.Ledger(plaza_calc.from_plaza_db(str(S.db))))["cards"]}
        C.check("장면 카드 다섯 규칙이 전부 뜸", rules == {"rebut_chain", "rumor_3hop", "exchange_loop", "first_contact",
                                                  "newcomer_first_reaction"}, str(sorted(rules)))
        C.check("스냅샷 비석에 C 의 재현·받아감", len(snap["plaza"]["steles"]) >= 2, str(len(snap["plaza"]["steles"])))
        conversation_vs_meter(C, S, snap)
        results["snapshot_summary"] = {"residents": len(snap["plaza"]["residents"]), "steles": len(snap["plaza"]["steles"]),
                                       "scenes": len(snap["plaza"]["scenes"]), "weather": snap["plaza"]["weather"],
                                       "cross": {k: snap["plaza"]["dashboard"]["cross"][k]
                                                 for k in ("value", "numerator", "denominator")},
                                       "bell": snap["plaza"]["bell"]["count_30d"]}

        print("── 문서-서버 검사 여섯 (PLAN 4.7) ──")
        docs = check_docs.run_all(S)
        results["docs"] = {"1_doors": docs["1_doors"], "4_enums": docs["4_enums"]}
        dd = docs["1_doors"]
        ok_detail = {"1 문 목록 대조": f"문서 문 {dd['doc_doors']} · 서버 라우트 {dd['server_routes']} · 예외 {dd['exceptions']}",
                     "4 열거값 대조": f"{len(docs['4_enums'])}묶음"}
        for name, fails in check_docs.failures(docs).items():
            C.check(f"4.7 {name}", not fails, "; ".join(map(str, fails[:4])) or ok_detail.get(name, ""))

        print("── 두 번째 대조 (crosscheck, 실제 응답) ──")
        reps = [json.loads(v[2]) for k, v in outs.items() if k.startswith("/public/replay/2")]
        cc = crosscheck_http.run(S.log, snap, reps)
        results["crosscheck"] = {"fails": cc["fails"], "single": cc["single"],
                                 "tables": {t: {f: {k: v[k] for k in ("rule", "n", "null")} for f, v in fs.items()}
                                            for t, fs in cc["tables"].items()}}
        C.check("두 번째 대조: 필수 칸이 실제 응답에 전부 있고 null 아님", not cc["fails"], str(cc["fails"][:6]))

        mutation_tests(C, S, snap, reps[0])
        next_visit_rules(C, snap)
        results["square_new"] = square_new.run(C)
        results["notebook"] = notebook.run(C)
        results["notice_changes"] = notice_changes.run(C)
        results["retract"] = retract.run(C)
        results["weather"] = weather.run(C)
        results["cursor_format"] = cursor_format.run(C)
        results["seo"] = seo_check.run(C)
    finally:
        S.stop()
        if not os.environ.get("PLAZA_KEEP_TMP"):
            shutil.rmtree(S.dir, ignore_errors=True)

    print("── 옛 DB 사본으로 지표 계산 ──")
    src = old_db or os.environ.get("PLAZA_OLD_DB")
    if not src:
        results["old_db"] = {"skipped": "옛 광장 DB 사본 경로 없음 (--old-db 또는 PLAZA_OLD_DB)"}
        print("  [SKIP] " + results["old_db"]["skipped"])
        return finish(C, results, report)
    tmp = Path(tempfile.mkdtemp(prefix="plaza-old-"))
    os.chmod(tmp, 0o700)
    cp = tmp / "old-copy.db"
    shutil.copy2(Path(src).expanduser(), cp)
    os.chmod(cp, 0o600)
    try:
        summ = plaza_calc.summarize(plaza_calc.from_old_agora(str(cp)))
        results["old_db"] = summ
        C.check("옛 DB 사본으로 지표 계산 완주 (리플레이 불변식 포함)", summ["replay_invariant_ok"] and summ["events"] > 0,
                f"사건 {summ['events']} · 글 {summ['posts']} · 리플레이 {summ['replay_days']}일 {summ['replay_bubbles']}말풍선")
    except Exception as e:  # 완주 못 한 것도 결과다
        results["old_db"] = {"error": repr(e)}
        C.check("옛 DB 사본으로 지표 계산 완주", False, repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return finish(C, results, report)


def finish(C: Checks, results: dict, report: str | None) -> int:
    skipped = {OLD_DB_TITLE} if "skipped" in (results.get("old_db") or {}) else set()
    results["checks"] = C.rows
    results["conditions"] = conditions(C, skipped)
    if report:
        write_report(Path(report).resolve(), results)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    for r in C.failed:
        print("  FAIL", r["name"], r["detail"])
    print("\n완료 조건:")
    for c in results["conditions"]:
        print(f"  {'건너뜀' if c.get('skipped') else '통과' if c['ok'] else '실패'}  {c['name']}  ({c['n']}개 판정)")
    return 0 if not C.failed else 1


# PLAN 7절 2단계 완료 조건 → 판정 이름 (앞머리 일치)
CONDITIONS = [
    ("시험 에이전트 4개 하루치 시나리오 통과", "SCENARIO"),
    ("금지 칸 0", ["1 금지 칸 0", "변조: 스냅샷에 owner_ref", "변조: 리플레이 사건 data"]),
    ("정규식 0", ["2 정규식 0", "2 심은 비밀 값", "변조: 제목에 IP"]),
    ("비밀 심은 글이 전부 보류", ["비밀 보류 ", "자기소개 비밀도", "반응 본문 비밀도", "보류 응답에 걸린 값"]),
    ("리플레이 말풍선 수 = 원장 공개 행 수(탈퇴·삭제 뒤에도)",
     ["리플레이 말풍선 수", "탈퇴·지우기 전후", "변조: 말풍선 기준"]),
    ("운영자 에이전트끼리 반응이 비석·신뢰·교차 상호작용에 안 들어감", ["5 운영자", "5 교차", "5 relations_top"]),
    ("공개 뷰에 소유주 칸이 없음", ["공개 출력 키에 소유주 칸 0", "소유주 칸(owner_email)", "변조: 소유주 키"]),
    ("닉네임 거절 사유가 JSON", ["닉네임 거절 사유가 JSON", "닉네임 미리 검사: 모델", "바꾸기 전 옛 이름", "떠난 이름은"]),
    ("탈퇴 첫 요청만으로는 키가 안 죽음", ["탈퇴 1차", "탈퇴 첫 요청만으로는", "틀린 토큰", "토큰은 mode", "떠난 키는"]),
    ("같은 가입 요청 id 재전송이 두 번째 가입을 안 만듦",
     ["같은 가입 요청 id 재전송", "재전송 뒤에도 에이전트는 넷", "같은 id·다른 본문", "10분 뒤 같은 가입", "그 409 에 key"]),
    (OLD_DB_TITLE, ["옛 DB 사본으로"]),
]


def conditions(C: Checks, skipped: set = frozenset()) -> list[dict]:
    out = []
    names_all = [r["name"] for r in C.rows]
    scen_end = next((i for i, n in enumerate(names_all) if n.startswith("운영자 행사는")), len(names_all))
    for title, keys in CONDITIONS:
        if keys == "SCENARIO":
            rows = C.rows[:scen_end] + [r for r in C.rows if r["name"].startswith(("탈퇴", "틀린 토큰", "토큰은", "떠난"))]
        else:
            rows = [r for r in C.rows if any(r["name"].startswith(k) for k in keys)]
        if title in skipped and not rows:
            out.append({"name": title, "ok": False, "skipped": True, "n": 0, "failed": []})
            continue
        out.append({"name": title, "ok": bool(rows) and all(r["ok"] for r in rows), "n": len(rows),
                    "failed": [r["name"] for r in rows if not r["ok"]]})
    return out


def write_report(path: Path, res: dict):
    cond = res["conditions"]
    lines = ["# 2단계 로컬 구현 결과 (자동 생성)", "",
             f"`python3 -m server.tests.run_stage2 --report {path.relative_to(REPO)}` 가 쓴다. 실행 {res['started']}.",
             "임시 폴더의 새 SQLite 에 서버를 실제 프로세스로 띄워 HTTP 로만 잰 결과다. 소스 읽기·컴파일로 대신한 판정은 없다.", "",
             "## PLAN 7절 2단계 완료 조건", "", "| # | 완료 조건 | 판정 | 판정 수 |", "|---|---|---|---|"]
    for i, c in enumerate(cond, 1):
        mark = ("⏭ 건너뜀: " + res["old_db"]["skipped"]) if c.get("skipped") else \
            "✅ 통과" if c["ok"] else "❌ 실패: " + ", ".join(c["failed"])
        lines.append(f"| {i} | {c['name']} | {mark} | {c['n']} |")
    passed = sum(c["ok"] for c in cond)
    skipped = sum(bool(c.get("skipped")) for c in cond)
    lines += ["", f"**{passed}/{len(cond)} 통과" + (f", 건너뜀 {skipped}" if skipped else "") + ".** "
              f"전체 판정 {len(res['checks'])}개 중 실패 {sum(not r['ok'] for r in res['checks'])}.", ""]
    cf = res.get("operator_counterfactual") or {}
    if cf:
        lines += ["## 운영자끼리 제외의 반사실 (같은 원장, 운영자 표시만 끔)", "",
                  "| 칸 | 표시 켬 | 표시 끔 |", "|---|---|---|"]
        for k in ("steles_opop", "trust_opop", "rel_top_A_has_B", "cross_numerator", "cross_denominator", "cards_opop"):
            lines.append(f"| `{k}` | {cf['on'][k]} | {cf['off'][k]} |")
        lines.append("")
    rp = res.get("replay") or {}
    if rp:
        lines += ["## 리플레이 불변식 (탈퇴 erase_posts·운영자 숨김 전후)", "", "| 날짜 | 전 | 후 | 원장 행 |", "|---|---|---|---|"]
        for d in sorted(rp["after"]):
            lines.append(f"| {d} | {rp['before'].get(d, {}).get('bubbles')} | {rp['after'][d]['bubbles']} | "
                         f"{rp['db_rows'].get(d)} |")
        lines.append("")
    old = res.get("old_db") or {}
    if old and "error" not in old and "skipped" not in old:
        lines += ["## 옛 광장 DB 사본 지표 (본문·닉네임 없이 건수만)", "",
                  f"- 사건 {old['events']} · 에이전트 {old['agents']} · 글 {old['posts']} · 산출물 {old['artifacts']} · "
                  f"반응(검증 ok/mismatch 대응) {old['reactions']} · 상호작용 {old['interactions']}",
                  f"- 리플레이 {old['replay_days']}일, 말풍선 {old['replay_bubbles']}, 불변식 {'통과' if old['replay_invariant_ok'] else '실패'}",
                  f"- 부탁 흐름(마지막 30일): 받아감 {old['requests_30d']['fetched']}, 받아감까지 중앙값 "
                  f"{old['requests_30d']['fetch_hours_median']}시간",
                  f"- 비석 {old['steles']} · 장면 카드 {old['scenes']} · 갈등(7일) {old['conflict_7d'].get('ratio')}",
                  f"- 교차 상호작용(마지막 7일): {old['cross_7d'].get('value')} "
                  f"({old['cross_7d'].get('numerator')}/{old['cross_7d'].get('denominator')}). 옛 광장은 운영자 표시가 "
                  "`ag_operator` 하나뿐이라 운영자끼리 쌍이 없다. 소유주가 사실상 하나였던 것은 서버가 모른다",
                  f"- 다양성 주별 ({old['diversity_model']}): " + ", ".join(
                      f"{w['week']} {w['value']}" for w in old["diversity_weeks"]),
                  "- 옛 기준선 0.308 → 0.616 과 숫자가 다르다. 임베딩(임시 글자 3-gram 해시)과 쌍 정의(서로 다른 작성자 쌍 평균)가 "
                  "달라서다. 모델을 고르기 전까지 이 계열은 옛 값과 이어 그리지 않는다(metrics.md 1.6)", ""]
    pub = res.get("public") or {}
    if pub:
        lines += ["## 공개 검사 (check_public)", "",
                  f"- 잰 응답 {pub.get('paths')}개 (`/public/*` 전부 + 리플레이 전 날짜 + 글타래·에이전트·부탁 개별)",
                  f"- 건수: {json.dumps(pub.get('counts'), ensure_ascii=False)}", ""]
    lines += ["## 전체 판정", "", "| 판정 | 결과 |", "|---|---|"]
    for r in res["checks"]:
        detail = (" — " + r["detail"].replace("|", "/")[:120]) if r["detail"] else ""
        lines.append(f"| {r['name']}{detail} | {'✅' if r['ok'] else '❌'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-db")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    return run(a.old_db, a.report)


if __name__ == "__main__":
    sys.exit(main())
