"""캐릭터 패널 머리 「최근 한 말」·「하려는 일」 (spec/snapshot-plaza.md 4.2). 실제 서버를 띄우고 헤드리스 Chromium 으로 패널을 연다.

  python3 -m server.tests.who_now.check [--capture <폴더>]

시나리오는 3단계 사흘치(stage3_data) + 팝업 판정의 표식(popup_check.plant) 위에, 라일락이 끝 무렵 2분 안에 이렇게 한다:
  t1 호두가 라일락에게 낸 부탁 q4 에 라일락이 손 듦
  T0 (리플레이 판정 시각)
  t3 라일락이 q4 산출물을 냄 · 한마디 「미래표식」 · 지목 없는 부탁 w3 「미래부탁표식」
  t4 라일락이 한마디 「거둔표식」을 쓰고 거둠. 그 뒤 표식 심기에서 운영자가 도토리의 가장 최근 글타래 글을 가린다
판정
 1. 지금: 「최근 한 말」 = DB 에서 그 이웃의 visible 글 최근 3개(거둔·가린 글 빠짐), 글타래 글은 /t/<id> 링크, 한마디는 링크 없음.
    「하려는 일」 = DB 의 부탁 표에서 손 든 부탁(산출물 전)·낸 부탁(안 끝남). q4 는 산출물을 냈으니 「손 든」 아님, w3 는 「낸 부탁」.
    도토리 패널에선 가장 최근 글(운영자가 가림)이 빠진다
 2. 리플레이 T0: 「최근 한 말」·아래 전체 목록·그 밖의 행동 어디에도 T0 뒤 글이 없다(미래표식 0). q4 는 그 시각 「손 든 부탁」,
    w3 은 아직 없는 부탁이라 안 보인다. 기대값은 패널이 적은 시각(data-clock)으로 DB 에서 다시 센다
 3. 계획 없는 이웃은 「남긴 계획 없음」
 4. 공개 범위: 패널 글자·HTML 에 거둔표식·가린 글·보류·수첩·가입 키 표식 0, 페이지가 부른 주소는 / · web/ · img/ · public/ 의 GET 뿐
    자 검사: 공개 응답에서 거둔·가린 글 본문을 되살린 사본을 끼우면 「최근 한 말」에 표식이 「있음」으로 잡혀야 한다
 5. 폰(390×844): 패널이 화면 안, 가로 넘침 0
 6. 페이지 오류 0
옛 판(이 칸이 없는 화면)에 대 보면 1~3 이 실패해야 한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path

from ..harness import Server
from ..popup_check import DESKTOP, KST, PHONE, Checks, plant, resurrect

FUTURE_MARK = "미래표식8812"
FUTURE_REQ = "미래부탁표식7741"
RETRACT_MARK = "거둔표식6630"

PANEL_JS = r"""async (id) => {
  const wait = (f, ms = 15000) => new Promise((ok, no) => { const t0 = Date.now();
    (function loop() { if (f()) return ok(); if (Date.now() - t0 > ms) return no(new Error('timeout who ' + id)); setTimeout(loop, 30); })(); });
  const m = document.getElementById('pzWho');
  if (!m.hidden) document.getElementById('pzWhoX').click();
  const b = document.createElement('button'); b.dataset.agent = id; b.id = 'pzProbeOpen';
  document.getElementById('pzTalk').append(b); b.click(); b.remove();
  await wait(() => m.dataset.ready === '1' && m.dataset.who === id);
  const box = m.querySelector('.pz-whonow');
  const sh = m.querySelector('.pz-sheet'), r = sh.getBoundingClientRect();
  const lists = m.querySelectorAll('.pz-wholist');
  return {
    has: !!box, clock: m.dataset.clock || null, mode: box ? box.dataset.clock : null,
    said: box ? [...box.querySelectorAll('.pz-whosaid > li[data-said]')].map((li) => ({ id: li.dataset.said,
      href: (li.querySelector('a') || {}).getAttribute ? li.querySelector('a') && li.querySelector('a').getAttribute('href') : null,
      text: li.textContent })) : [],
    plans: box ? [...box.querySelectorAll('.pz-whoplan > li[data-request]')].map((li) => ({ id: li.dataset.request,
      what: (li.querySelector('.pz-tk') || {}).textContent || '' })) : [],
    planNone: box ? (box.querySelector('.pz-whoplan .pz-none') || {}).textContent || null : null,
    full: lists.length ? [...lists[0].querySelectorAll(':scope > li.pz-ti')].map((li) => li.dataset.post) : [],
    otherEvents: lists.length > 1 ? [...lists[1].querySelectorAll(':scope > li.pz-ti')].map((li) => li.dataset.event) : [],
    html: m.innerHTML + '\n' + m.textContent,
    over: [...m.querySelectorAll('.pz-tb, .pz-whonow')].filter((el) => el.scrollWidth > el.clientWidth + 1).length + (sh.scrollWidth > sh.clientWidth + 1 ? 1 : 0),
    box: { l: r.left, t: r.top, r: r.right, b: r.bottom }, vw: innerWidth, vh: innerHeight,
  };
}"""


def ms(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000   # 패널 data-clock 은 UTC Z 표기


def db_rows(S: Server):
    c = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    posts = [dict(r) for r in c.execute("SELECT rowid, * FROM posts")]
    reqs = [dict(r) for r in c.execute("SELECT * FROM requests")]
    evs = [dict(r) for r in c.execute("SELECT * FROM events")]
    c.close()
    return posts, reqs, evs


def want_said(posts, aid, t):
    """그 이웃의 visible 글 중 t 까지 최근 3개. 같은 시각 끝자리는 어느 쪽이어도 맞는다 → (꼭 있어야 할 id, 있어도 되는 id, 개수)"""
    mine = sorted([p for p in posts if p["author"] == aid and p["visibility"] == "visible" and ms(p["created_at"]) <= t],
                  key=lambda p: ms(p["created_at"]), reverse=True)
    if len(mine) <= 3:
        ids = {p["id"] for p in mine}
        return ids, ids, len(mine)
    cut = ms(mine[2]["created_at"])
    must = {p["id"] for p in mine if ms(p["created_at"]) > cut}
    may = {p["id"] for p in mine if ms(p["created_at"]) >= cut}
    return must, may, 3


def state_at(r, t):
    if not r["opened_at"] or ms(r["opened_at"]) > t:
        return None
    for k, st in (("closed_at", "closed"), ("fetched_at", "fetched"), ("delivered_at", "delivered"), ("claimed_at", "claimed")):
        if r[k] and ms(r[k]) <= t:
            return st
    return "open"


def want_plans(reqs, aid, t):
    out = {}
    for r in reqs:
        if r["visibility"] != "visible":
            continue
        st = state_at(r, t)
        if r["claimed_by"] == aid and st == "claimed":
            out[r["id"]] = "손 든"
        elif r["from_id"] == aid and st in ("open", "claimed", "delivered"):
            out[r["id"]] = "낸 부탁"
    return out


def got_plans(w):
    return {p["id"]: ("손 든" if p["what"].startswith("손 든") else "낸 부탁" if p["what"].startswith("낸 부탁") else p["what"]) for p in w["plans"]}


def judge(C, G, w, posts, reqs, aid, threads_of):
    t = float("inf") if w["clock"] in (None, "now") else ms(w["clock"])
    must, may, n = want_said(posts, aid, t)
    got = [s["id"] for s in w["said"]]
    C.check(G, "「최근 한 말」 = DB 의 visible 글 최근 3개 (거둔·가린 글 빠짐)",
            w["has"] and len(got) == n and must <= set(got) <= may, f"화면 {got} · 기대 {sorted(may)} 중 {n}개")
    bad_link = [s for s in w["said"] if (threads_of.get(s["id"]) and s["href"] != f"/t/{threads_of[s['id']]}")
                or (not threads_of.get(s["id"]) and s["href"])]
    C.check(G, "글타래 글은 /t/<글타래 id> 링크, 한마디는 링크 없음", not bad_link, bad_link[:2] or [s["href"] for s in w["said"]])
    wp, gp = want_plans(reqs, aid, t), got_plans(w)
    C.check(G, "「하려는 일」 = DB 부탁 표의 손 든 부탁(산출물 전)·낸 부탁(안 끝남), 그 시각 기준", w["has"] and gp == wp,
            f"화면 {gp} · 기대 {wp}")
    return t


def scenario(R):
    """라일락의 끝 무렵 2분: 위 머리 주석의 t1~t4. 신규 기간(72시간)이라 쓰기가 시간당 4번이어서, 끝 무렵에 쓰기가 없던
    라일락이 쓰기 넷(산출물·한마디 둘·부탁)만 한다. 돌려주는 값: (T0 iso, {이름: id})"""
    S = R.S
    base = R.last + dt.timedelta(seconds=10)
    R.at(base)
    R.claim("lilac", "q4")                 # 사흘치 끝 회차에 호두가 라일락에게 낸 부탁
    t0 = base + dt.timedelta(seconds=30)
    R.at(base + dt.timedelta(seconds=60))
    R.deliver("lilac", "q4", "분수 앞, 물소리가 사진 밖까지 들리는 오후.")
    R.remark("lilac", "fut", f"{FUTURE_MARK} 리플레이 시각 뒤에 쓴 한마디")
    R.request("lilac", None, "w3", f"{FUTURE_REQ} 나중 부탁", "리플레이 시각 뒤에 연 부탁이에요.")
    R.at(base + dt.timedelta(seconds=75))
    R.remark("lilac", "ret", f"{RETRACT_MARK} 곧 거둘 한마디")
    rr = S.post(f"/api/v1/posts/{R.p.get('ret', 'po_none')}/retract", {}, key=R.key["lilac"])
    if rr.status != 200:
        R.fail.append(f"거두기 {rr!r}"[:200])
    return t0.isoformat(), {k: R.r[k] for k in ("q4", "w3") if k in R.r}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", help="캡처 폴더 (who_now_<desktop|phone|replay>.png)")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    from .. import stage3_data as D
    from ..stage3_check import DET_FLAGS
    C = Checks()
    capture = Path(a.capture).expanduser() if a.capture else None
    if capture:
        capture.mkdir(parents=True, exist_ok=True)
    S = Server()
    S.start()
    try:
        R = D.Run(S)
        D.scenario(R)
        t0, W = scenario(R)
        R.at(max(R.last + dt.timedelta(seconds=5), dt.datetime.now(KST) - dt.timedelta(minutes=2)))
        marks = plant(R)
        R.at(max(R.last, dt.datetime.now(KST)))
        marks[f"거둔 한마디"] = RETRACT_MARK
        C.check("준비", "시나리오 + 라일락 끝 무렵 + 표식 심기 완주", not R.fail and len(W) == 2, "; ".join(R.fail[:2]) or W)
        posts, reqs, _ = db_rows(S)
        threads_of = {p["id"]: p["thread_id"] for p in posts}
        lil, dot = R.id["lilac"], R.id["dot"]
        hidden_ids = {R.p["ret"]: RETRACT_MARK, R.p["hid_post"]: marks["숨김 글타래 글"]}
        with sync_playwright() as p:
            browser = p.chromium.launch(args=DET_FLAGS)
            errs, reqlog = [], []
            ctx = browser.new_context(**DESKTOP)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("request", lambda r: reqlog.append((r.method, r.url)))

            # 1. 지금
            G = "지금"
            pg.goto(S.url + "/?mode=now&motion=0")
            pg.wait_for_function("() => window.Plaza && Plaza.stats().mode === 'now' && document.querySelectorAll('#pzThings .pz-zone').length === 10", timeout=30000)
            w = pg.evaluate(PANEL_JS, lil)
            judge(C, G, w, posts, reqs, lil, threads_of)
            gp = got_plans(w)
            C.check(G, "q4(산출물 냄)는 「손 든」 아님 · w3 는 「낸 부탁」", W["q4"] not in gp and gp.get(W["w3"]) == "낸 부탁", gp)
            C.check(G, "거둔 한마디는 「최근 한 말」에 없고 그다음 글로 채움", R.p["ret"] not in [x["id"] for x in w["said"]] and len(w["said"]) == 3,
                    [x["id"] for x in w["said"]])
            C.check(G, "「지금 기준」 머리 · 미래표식 한마디가 보임(지금은 미래가 아님)", w["mode"] == "now" and FUTURE_MARK in w["html"], w["mode"])
            leak = [n for n, mk in marks.items() if mk in w["html"]]
            C.check(G, "패널에 거둔표식·가린 글·보류·우편함·수첩·가입 키 표식 0", not leak, leak)
            if capture:
                pg.evaluate("document.querySelector('#pzWho .pz-sheet').scrollTop = 0")
                pg.screenshot(path=str(capture / "who_now_desktop.png"))
            wd = pg.evaluate(PANEL_JS, dot)   # 도토리: 가장 최근 글(표식 심기의 글타래 글)을 운영자가 가렸다
            judge(C, "지금 · 가린 글", wd, posts, reqs, dot, threads_of)
            C.check("지금 · 가린 글", "운영자가 가린 글은 「최근 한 말」에 없음 (가장 최근 글인데도)",
                    R.p["hid_post"] not in [x["id"] for x in wd["said"]] and marks["숨김 글타래 글"] not in wd["html"], [x["id"] for x in wd["said"]])
            # 3. 계획 없는 이웃
            G3 = "계획 없음"
            none_id = next((R.id[n] for n in ("snail", "blue", "sol", "mint", "nova", "sand", "tower")
                            if not want_plans(reqs, R.id[n], float("inf"))), None)
            wn = pg.evaluate(PANEL_JS, none_id) if none_id else None
            C.check(G3, "낸 부탁·손 든 부탁이 없는 이웃은 「남긴 계획 없음」", bool(wn) and wn["has"] and not wn["plans"] and wn["planNone"] == "남긴 계획 없음",
                    (wn or {}).get("planNone"))
            if wn:
                judge(C, G3, wn, posts, reqs, none_id, threads_of)

            # 2. 리플레이 T0
            G2 = "리플레이"
            pg.goto(S.url + f"/?view=replay&motion=0&autopause=0&date={t0[:10]}")
            pg.wait_for_function("() => window.Plaza && Plaza.stats().mode === 'replay' && Plaza.stats().date", timeout=30000)
            if pg.evaluate("Plaza.stats().playing"):   # 멈춘 뒤 옮긴다(옮기고 멈추면 그사이 시계가 흐른다)
                pg.click("[data-rp=play]")
            pg.evaluate("(iso) => Plaza.seek(iso)", t0)
            st = pg.evaluate("Plaza.stats()")
            w2 = pg.evaluate(PANEL_JS, lil)
            t = judge(C, G2, w2, posts, reqs, lil, threads_of)
            C.check(G2, "패널 시각 = 멈춘 리플레이 시각 (T0)", w2["mode"] == "replay" and abs(t - ms(t0)) < 2000 and not st["playing"],
                    f"{w2['clock']} · T0 {t0}")
            tl = t if w2["clock"] not in (None, "now") else ms(t0)   # 시각을 안 적는 화면(옛 판)은 T0 로 센다
            later = {p["id"] for p in posts if p["author"] == lil and ms(p["created_at"]) > tl}
            leak_f = [x for x in [s["id"] for s in w2["said"]] + w2["full"] if x in later]
            C.check(G2, "「최근 한 말」·전체 목록에 T0 뒤 글 0 (미래표식 글자도 0)", not leak_f and FUTURE_MARK not in w2["html"] and bool(later),
                    f"뒤 글 {len(later)} · 샌 것 {leak_f}")
            ev_at = {e["id"]: e["at"] for e in db_rows(S)[2]}
            leak_e = [x for x in w2["otherEvents"] if ms(ev_at.get(x, t0)) > tl]
            C.check(G2, "그 밖의 행동에 T0 뒤 행 0", not leak_e, leak_e[:3])
            gp2 = got_plans(w2)
            C.check(G2, "T0 에 q4 는 「손 든 부탁」(지금은 산출물 냄), w3(뒤에 연 부탁)은 없음 · 미래부탁표식 글자 0",
                    gp2.get(W["q4"]) == "손 든" and W["w3"] not in gp2 and FUTURE_REQ not in w2["html"], gp2)
            if capture:
                pg.screenshot(path=str(capture / "who_now_replay.png"))
            bad = [(m, u) for m, u in reqlog if m != "GET" or not re.match(re.escape(S.url) + r"/($|\?|web/|img/|public/)", u)]
            C.check("공개 범위", "페이지가 부른 주소 = / · web/ · img/ · public/ 의 GET 뿐 (새 문 없음)", not bad, bad[:3] or f"{len(reqlog)}건")
            C.check("공개 범위", "페이지 오류 0", not errs, errs[:2])
            ctx.close()

            # 4. 자 검사: 거둔·가린 글 본문을 되살린 사본
            ctx = browser.new_context(**DESKTOP)
            pg = ctx.new_page()
            pg.route(re.compile(r".*/public/.*\.json.*"), lambda route: resurrect(route, hidden_ids))
            pg.goto(S.url + "/?mode=now&motion=0")
            pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length === 10", timeout=30000)
            wr = pg.evaluate(PANEL_JS, lil)
            C.check("자 검사", "되살린 사본에선 「최근 한 말」에 거둔·가린 표식이 「있음」",
                    any(mk in " ".join(s["text"] for s in wr["said"]) for mk in hidden_ids.values()), [s["id"] for s in wr["said"]])
            ctx.close()

            # 5. 폰
            ctx = browser.new_context(**PHONE)
            pg = ctx.new_page()
            pg.goto(S.url + "/?mode=now&motion=0")
            pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length === 10", timeout=30000)
            wp = pg.evaluate(PANEL_JS, lil)
            inside = wp["box"]["l"] >= -1 and wp["box"]["r"] <= wp["vw"] + 1 and wp["box"]["t"] >= -1 and wp["box"]["b"] <= wp["vh"] + 1
            C.check("폰", "패널 화면 안 · 가로 넘침 0 · 머리 칸 있음", wp["has"] and inside and wp["over"] == 0,
                    f"넘침 {wp['over']} · {wp['box']} / {wp['vw']}×{wp['vh']}")
            if capture:
                pg.screenshot(path=str(capture / "who_now_phone.png"))
            ctx.close()
            browser.close()
    finally:
        S.stop()
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
