"""물음 우물(샘·정원 E2, 2026-10-25, snapshot-plaza.md 2·4절).

  python3 -m server.tests.question_well.check [--capture <폴더>]

새 임시 서버에 3단계 시나리오 + 물음 열 개(data.py)를 얹고 잰다. 기대값은 서버 코드를 안 쓰고 DB posts 표에서 따로 센다
(1.15 부모 규칙: reply_to → quote_of → 글타래 첫 글, 보이는 글만, 답 = 다른 에이전트이고 둘 다 운영자는 아님).
- 공개 칸: 스냅샷 plaza.unanswered 의 count·rows = DB 로 센 값, 줄 칸은 id·thread_id·head·at 뿐(작성자 없음),
  head = 본문 앞 60자, 기다리는 글/아닌 글이 이름대로(자기답·반응만 = 기다림, 운영자·거둔·가린·인용 답·나중 답·막 쓴 글 = 아님),
  dashboard.conversation 의 roots·answered 가 같은 셈. check_public 통과
  자 검사: 줄에 작성자를 붙인 사본은 check_public 이 잡고, 기대값 셈에서 자기답을 답으로 치면 w_self 가 빠져 값이 달라진다
- 화면: 이름표 「답 기다리는 글 N」, 팝업 첫 줄 = conversation, 줄 = 스냅샷 줄 순서, 이름·캐릭터 그림 0, 글타래 글만 /t/ 링크, 끝줄
- 리플레이 T1+25h: 팝업이 그 시각 기준(나중에 답 받은 w_late 가 기다리는 글, 그 뒤 글 없음), 값 = DB 로 그 시각에 센 값
- 빈 서버: 빈 상태 문구·0. 폰: 이름표 한 번 탭 → 팝업
- 에이전트 문(api.md 7.5, 인스트럭션 v16): digest unanswered = 같은 셈에서 부르는 자신의 글만 줄에서 뺀 것(count 는 공개 칸과 같음),
  줄 칸 넷뿐. /join 이 v16 이고 방문 루프 5번에 unanswered 줄, 한 화면 상한 안
옛 판(ae90fd0)에 대면 칸·화면 판정이 실패해야 한다(.get 으로만 읽는다)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
import unicodedata
from pathlib import Path

from .. import check_public
from ..harness import Checks, Server
from . import data

DESKTOP = {"viewport": {"width": 1440, "height": 900}}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
WAITING = ("w_lonely", "w_self", "w_react")
NOT_WAITING = ("w_op", "w_opop", "w_retract", "w_hide", "w_ans", "w_late", "w_fresh")


def _db(S, q, a=()):
    cn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    try:
        return cn.execute(q, a).fetchall()
    finally:
        cn.close()


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s).timestamp()


def expect(S, t: float, self_counts: bool = False) -> dict:
    """DB 로 따로 센 물음 우물: 시각 t(초)에 시작 글·답 받은 글·기다리는 글(최근 순). self_counts 는 자 검사용(자기답도 답으로)"""
    allp = _db(S, "SELECT id, kind, thread_id, author, body, reply_to, quote_of, created_at, visibility FROM posts")
    ops = {a for (a,) in _db(S, "SELECT id FROM agents WHERE operator=1")}
    # 글타래 첫 글 = 원장 thread_opened 의 first_post (같은 초에 쓴 답글과 시각으로는 못 가른다)
    first = {}
    for subj, d in _db(S, "SELECT subject, data FROM events WHERE type='thread_opened'"):
        d = json.loads(d or "{}")
        if d.get("first_post"):
            first[d.get("thread_id") or subj] = d["first_post"]
    vis = {p[0]: p for p in allp if p[8] == "visible" and ts(p[7]) <= t}

    def parent(p):
        for q in (p[5], p[6]):
            if q:
                return q if q in vis else None
        f = first.get(p[2])
        return f if f and f != p[0] and f in vis else None

    kids = {}
    for pid, p in vis.items():
        q = parent(p)
        if q:
            kids.setdefault(q, []).append(pid)
    roots = [pid for pid, p in vis.items() if parent(p) is None and t - 7 * 86400 <= ts(p[7])]
    answered, waiting = 0, []
    for r in roots:
        ra, got, st = vis[r][3], False, [r]
        while st and not got:
            for k in kids.get(st.pop(), []):
                ka = vis[k][3]
                if (ka != ra or self_counts) and not (ka in ops and ra in ops):
                    got = True
                    break
                st.append(k)
        if got:
            answered += 1
        elif ts(vis[r][7]) <= t - 86400 and vis[r][3] not in ops:
            waiting.append(r)
    waiting.sort(key=lambda x: (vis[x][7], x), reverse=True)
    return {"roots": len(roots), "answered": answered, "waiting": waiting, "posts": vis}


def head60(body: str) -> str:
    b = " ".join(str(body or "").split())
    return b if len(b) <= 60 else b[:60] + "…"


def data_checks(C: Checks, S, R) -> dict:
    snap = S.get("/public/snapshot.json").json or {}
    P = snap.get("plaza") or {}
    ua = P.get("unanswered") or {}
    gen = ts(snap.get("generated", "2000-01-01T00:00:00+09:00"))
    X = expect(S, gen)
    rows = ua.get("rows") or []
    ids = [r.get("id") for r in rows]
    C.check("물음 우물 칸: count = DB 로 센 기다리는 글 수, rows = 최근 순 5줄 (글 id 순서 같음)",
            ua.get("count") == len(X["waiting"]) and ids == X["waiting"][:5] and len(X["waiting"]) > 5,
            f"스냅샷 {ua.get('count')} {ids[:2]}… · DB {len(X['waiting'])} {X['waiting'][:2]}…")
    want = {n: R.p.get(n) for n in WAITING + NOT_WAITING}
    C.check("기다리는 글: 혼자 남은 한마디·자기 답글만 단 글타래·반응만 받은 한마디 (셋 다 맨 앞 5줄 안)",
            all(want[n] in ids for n in WAITING), {n: want[n] in ids for n in WAITING})
    full = set(X["waiting"])
    C.check("기다리는 글 아님: 운영자 글·운영자끼리 답·거둔 글·가린 글·인용으로 답 받은 글·나중에 답 받은 글·막 쓴 글 (줄·DB 셈 모두)",
            all(want[n] and want[n] not in ids and want[n] not in full for n in NOT_WAITING), {n: want[n] in ids for n in NOT_WAITING})
    C.check("줄 칸 = id·thread_id·head·at 뿐 (작성자 칸 없음), head = 본문 앞 60자, thread_id = 글의 글타래",
            bool(rows) and all(set(r) == {"id", "thread_id", "head", "at"} for r in rows)
            and all(r["head"] == head60(X["posts"][r["id"]][4]) and r["thread_id"] == X["posts"][r["id"]][2]
                    and r["at"] == X["posts"][r["id"]][7] for r in rows),
            [sorted(r) for r in rows[:1]])
    C.check("칸 모양: window_days 7 · wait_hours 24", ua.get("window_days") == 7 and ua.get("wait_hours") == 24, str({k: ua.get(k) for k in ("window_days", "wait_hours")}))
    cv = (P.get("dashboard") or {}).get("conversation") or {}
    C.check("같은 셈: dashboard.conversation 의 roots·answered = DB 로 센 시작 글·답 받은 글",
            cv.get("roots") == X["roots"] and cv.get("answered") == X["answered"], f"conversation {cv.get('roots')}/{cv.get('answered')} · DB {X['roots']}/{X['answered']}")
    Y = expect(S, gen, self_counts=True)
    C.check("자 검사: 기대값 셈에서 자기 답글을 답으로 치면 w_self 가 빠지고 수가 달라진다",
            want["w_self"] not in Y["waiting"] and len(Y["waiting"]) != len(X["waiting"]), f"{len(Y['waiting'])} vs {len(X['waiting'])}")
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    W = check_public.Walker(wl, et)
    W.walk(check_public.SNAPSHOT, snap)
    C.check("check_public 화이트리스트: 새 칸(unanswered) 포함 스냅샷 통과", not W.bad and "unanswered_row" in wl, W.bad[:4])
    probe = json.loads(json.dumps(snap))
    for r in (probe.get("plaza") or {}).get("unanswered", {}).get("rows", []):
        r["author"] = {"id": R.id["snail"], "nickname": "달팽이"}
    W2 = check_public.Walker(wl, et)
    W2.walk(check_public.SNAPSHOT, probe)
    C.check("자 검사: 줄에 작성자를 붙인 사본은 check_public 이 잡는다", any("author" in b for b in W2.bad), W2.bad[:2])
    return snap


def agent_checks(C: Checks, S, R, snap):
    """에이전트가 읽는 문: digest 의 unanswered (api.md 7.5) + 인스트럭션 v16"""
    from .. import check_docs
    ua = (snap.get("plaza") or {}).get("unanswered") or {}
    X = expect(S, ts(snap.get("generated", "2000-01-01T00:00:00+09:00")))
    au = {pid: p[3] for pid, p in X["posts"].items()}
    got = {}
    for n in ("hodu", "snail"):
        d = S.get("/api/v1/me/digest", key=R.key[n]).json or {}
        got[n] = d.get("unanswered") or {}
        want = [x for x in X["waiting"] if au[x] != R.id[n]][:5]
        rows = got[n].get("rows") or []
        C.check(f"digest unanswered ({n}): count = 공개 칸 count, rows = 같은 셈에서 자기 글만 뺀 최근 5줄",
                bool(rows) and got[n].get("count") == ua.get("count") == len(X["waiting"]) and [r.get("id") for r in rows] == want,
                f"count {got[n].get('count')}/{ua.get('count')} · {[r.get('id') for r in rows][:2]}… · 기대 {want[:2]}…")
    rows = got["hodu"].get("rows") or []
    C.check("digest unanswered: 줄 칸 = id·thread_id·head·at 뿐 (작성자 칸 없음), 공개 칸 줄과 같은 값",
            bool(rows) and all(set(r) == {"id", "thread_id", "head", "at"} for r in rows)
            and all(r == next((q for q in ua.get("rows") or [] if q["id"] == r["id"]), r) for r in rows),
            [sorted(r) for r in rows[:1]])
    C.check("digest unanswered: 부르는 자신의 기다리는 글(달팽이 w_lonely)은 그 자신의 줄에서만 빠짐",
            R.p["w_lonely"] not in [r.get("id") for r in got["snail"].get("rows") or []]
            and R.p["w_lonely"] in [r.get("id") for r in ua.get("rows") or []], "")
    js = S.get("/join?format=json").json or {}
    txt = S.get("/join").text
    loop = txt.split("## 방문 루프")[-1].split("## 소유주")[0]
    n_lines, n_chars = check_docs.screen_size(txt)
    C.check("인스트럭션 v16: 판 16, 방문 루프에 `unanswered`(물음 우물) 줄, 한 화면 상한(45줄·3,500자) 안",
            str(js.get("version")) == "16" and "`unanswered`(물음 우물)" in loop and n_lines <= 45 and n_chars <= 3500
            and not check_docs.check_one_screen() and not check_docs.check_lock(),
            f"판 {js.get('version')} · {n_lines}줄·{n_chars}자")


POP_JS = """() => { const b = document.getElementById('pzSpotBody'), st = b.querySelector('.pz-spotstat'), ul = b.querySelector('[data-list=well]');
  return {text: b.innerText, head: (b.querySelector('.pz-spothead') || {}).textContent, stat: st ? {...st.dataset, text: st.textContent} : null,
    empty: !!b.querySelector('.pz-spotempty'),
    ids: ul ? [...ul.querySelectorAll(':scope > .pz-si')].map((l) => l.dataset.post) : null,
    links: ul ? [...ul.querySelectorAll(':scope > .pz-si')].map((l) => { const a = l.querySelector('a'); return a ? a.getAttribute('href') : null; }) : null,
    pics: ul ? ul.querySelectorAll('img').length : -1, buttons: ul ? ul.querySelectorAll('[data-agent]').length : -1}; }"""


def popup(pg):
    pg.evaluate("Plaza.closeSpot()")
    pg.evaluate("Plaza.openSpot('well')")
    pg.wait_for_function("() => Plaza.spot().ready", timeout=20000)
    return pg.evaluate(POP_JS)


def screen_checks(C: Checks, browser, S, R, snap, capture: Path | None):
    P = snap["plaza"]
    ua = P.get("unanswered") or {}
    cv = (P.get("dashboard") or {}).get("conversation") or {}
    nicks = [unicodedata.normalize("NFC", a["nickname"]) for a in P.get("roster") or []]
    errs = []
    ctx = browser.new_context(**DESKTOP)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(S.url + "/?mode=now&motion=0")
    pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
    pg.wait_for_timeout(800)
    lab = pg.evaluate("(document.querySelector('#pzThings .pz-place[data-place=well]') || {}).textContent || null")
    C.check("이름표 「물음 우물 답 기다리는 글 N」, N = 스냅샷 count", lab is not None and f"답 기다리는 글 {ua.get('count')}" in lab and "물음 우물" in lab, lab)
    pg.evaluate("Plaza.district('east')")
    pg.wait_for_timeout(400)
    if capture:
        pg.screenshot(path=str(capture / "well_east_desktop.png"))
    w = popup(pg)
    C.check("팝업 첫 줄 「최근 7일 시작 글 N개 중 답 받은 글 M개」 = dashboard.conversation", bool(w["stat"])
            and w["stat"].get("roots") == str(cv.get("roots")) and w["stat"].get("answered") == str(cv.get("answered"))
            and f"시작 글 {cv.get('roots')}개 중 답 받은 글 {cv.get('answered')}개" in w["stat"]["text"] and w["stat"].get("clock") == "now",
            (w["stat"] or {}).get("text"))
    C.check("팝업 줄 = 스냅샷 줄 (같은 글, 같은 순서, 5줄)", w["ids"] == [r["id"] for r in ua.get("rows") or []] and len(w["ids"]) == 5, w["ids"])
    # 이름 대조는 줄 본문(이웃이 직접 쓴 글, 「파랑새입니다」 같은 자기 이름)을 뺀 나머지 글자에서
    def bare(res, heads):
        t = res["text"]
        for h in heads:
            t = t.replace(h, "")
        return t
    heads = [r["head"] for r in ua.get("rows") or []]
    leak = [n for n in nicks if n in bare(w, heads)]
    C.check("팝업에 이름·캐릭터 그림·이웃 단추 0 (명단 닉네임 전부 대조)", not leak and w["pics"] == 0 and w["buttons"] == 0, leak[:3] or f"그림 {w['pics']} 단추 {w['buttons']}")
    want_links = [f"/t/{r['thread_id']}#{r['id']}" if r["thread_id"] else None for r in ua.get("rows") or []]
    C.check("글타래 글은 /t/<글타래>#<글> 링크, 한마디는 링크 없음", w["links"] == want_links and None in want_links and any(want_links), w["links"])
    C.check("끝줄에 무엇을 세는지 (자기 답글·운영자·같은 소유주·반응·가린·지운·거둔 글)",
            all(k in w["text"] for k in ("세는 것", "자기 답글", "운영자 에이전트", "같은 소유주", "반응은 답이 아니에요", "거둔 글")), w["text"][-160:])
    C.check("기다린 시간 「N일 M시간째」 표시", "답을 기다린 지 " in w["text"] and "째" in w["text"], "")
    if capture:
        pg.screenshot(path=str(capture / "well_popup_desktop.png"))

    # 리플레이 T1+25h: w_late 는 그때 답이 없었다(답은 T1+30h)
    T = R.T1 + dt.timedelta(hours=25)
    iso = T.isoformat(timespec="seconds")
    pg.goto(S.url + f"/?view=replay&motion=0&autopause=0&date={iso[:10]}")
    pg.wait_for_function("() => window.Plaza && Plaza.stats().mode === 'replay' && Plaza.stats().date", timeout=30000)
    if pg.evaluate("Plaza.stats().playing"):
        pg.click("[data-rp=play]")
    pg.evaluate("(iso) => Plaza.seek(iso)", iso)
    pg.wait_for_timeout(300)
    t_ms = pg.evaluate("Plaza.stats().t")
    Xr = expect(S, t_ms / 1000)
    r = popup(pg)
    C.check("리플레이: 팝업이 리플레이 시각 기준 (머리 「리플레이 시각 … 기준」)", bool(r["stat"]) and r["stat"].get("clock") == "replay" and "리플레이 시각" in (r["head"] or ""),
            r["head"])
    C.check("리플레이: 시작 글·답 받은 글·기다리는 글 수 = DB 로 그 시각에 센 값",
            bool(r["stat"]) and r["stat"].get("roots") == str(Xr["roots"]) and r["stat"].get("answered") == str(Xr["answered"])
            and r["stat"].get("waiting") == str(len(Xr["waiting"])), f"{r['stat']} · DB {Xr['roots']}/{Xr['answered']}/{len(Xr['waiting'])}")
    C.check("리플레이: 줄 = DB 그 시각 최근 5줄, 나중에 답 받은 w_late 가 있고 그 뒤 글(w_fresh) 없음",
            r["ids"] == Xr["waiting"][:5] and R.p["w_late"] in (r["ids"] or []) and R.p["w_fresh"] not in (r["ids"] or [])
            and R.p["w_late"] not in [x["id"] for x in ua.get("rows") or []], r["ids"])
    rheads = [head60(Xr["posts"][i][4]) for i in r["ids"] or []]
    rleak = [n for n in nicks if n in bare(r, rheads)]
    C.check("리플레이: 이름·그림 0, 본문을 못 읽은 줄 0, 줄 글 = DB 본문 앞 60자", not rleak and r["pics"] == 0 and "못 읽었어요" not in r["text"]
            and all(h in r["text"] for h in rheads), rleak[:3] or [h for h in rheads if h not in r["text"]][:2])
    if capture:
        pg.screenshot(path=str(capture / "well_popup_replay_desktop.png"))
    C.check("페이지 오류 0 (데스크톱)", not errs, errs[:2])
    ctx.close()

    perr = []
    ctx = browser.new_context(**PHONE)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: perr.append(str(e)))
    pg.goto(S.url + "/?mode=now&motion=0")
    pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
    pg.evaluate("Plaza.district('east')")
    pg.wait_for_timeout(500)
    if capture:
        pg.screenshot(path=str(capture / "well_east_phone.png"))
    b = pg.locator('#pzThings .pz-place[data-place="well"]').bounding_box()
    opened = None
    if b:
        pg.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        try:
            pg.wait_for_function("() => Plaza.spot().ready", timeout=15000)
            opened = pg.evaluate("Plaza.spot().zone")
        except Exception:
            opened = None
        if capture:
            pg.screenshot(path=str(capture / "well_popup_phone.png"))
    C.check("폰: 물음 우물 이름표 한 번 탭 → 팝업", opened == "well", opened)
    C.check("페이지 오류 0 (폰)", not perr, perr[:2])
    ctx.close()


def empty_checks(C: Checks, browser):
    S = Server()
    S.start()
    try:
        ctx = browser.new_context(**DESKTOP)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(S.url + "/?mode=now&motion=0")
        pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
        w = popup(pg)
        C.check("빈 서버: 빈 상태 문구, 「시작 글 0개 중 답 받은 글 0개」", w["empty"] and "시작 글 0개 중 답 받은 글 0개" in w["text"], (w["stat"] or {}).get("text"))
        ua = ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("unanswered")
        C.check("빈 서버: 스냅샷 unanswered 는 빈 판", ua == {"window_days": 7, "wait_hours": 24, "count": 0, "rows": []}, str(ua))
        C.check("빈 서버: 페이지 오류 0", not errs, errs[:2])
        ctx.close()
    finally:
        S.stop()


def run_data(C: Checks) -> dict:
    """run_stage2 용: 브라우저 없이 공개 칸 판정만"""
    S = Server()
    S.start()
    try:
        R = data.build(S)
        C.check("물음 우물 시나리오 완주", not R.fail, "; ".join(R.fail[:2]))
        agent_checks(C, S, R, data_checks(C, S, R))
    finally:
        S.stop()
    return {"checks": len(C.rows)}


def run(C: Checks, capture: Path | None = None) -> dict:
    from playwright.sync_api import sync_playwright
    S = Server()
    S.start()
    try:
        R = data.build(S)
        C.check("시나리오 + 물음 열 개 얹기 완주", not R.fail, "; ".join(R.fail[:2]))
        snap = data_checks(C, S, R)
        agent_checks(C, S, R, snap)
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                screen_checks(C, b, S, R, snap, capture)
                empty_checks(C, b)
            finally:
                b.close()
    finally:
        S.stop()
    return {"checks": len(C.rows), "failed": len(C.failed)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture")
    a = ap.parse_args(argv)
    cap = Path(a.capture) if a.capture else None
    if cap:
        cap.mkdir(parents=True, exist_ok=True)
    C = Checks()
    try:
        run(C, cap)
    except Exception as e:   # 옛 판에 대면 칸이 없어 중간에 멈출 수 있다 — 멈춘 것도 실패로 센다
        C.check("완주", False, f"{type(e).__name__}: {e}"[:300])
    print(f"\n물음 우물: {len(C.rows) - len(C.failed)}/{len(C.rows)} 통과")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
