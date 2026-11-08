"""관전 개선 1단계 (spec/snapshot-plaza.md 4.3): 전광판·따라가기 카메라·관계 한 장·답할 차례·말없이 다녀감.
헤드리스 Chromium 으로 3단계 녹화 데이터(docs/stage3/data)를 정적 사본에 올려 화면을 띄우고, 기대값은 화면이 아니라
같은 자료 파일(스냅샷·리플레이·공개 문)에서 파이썬으로 다시 센다.

  python3 -m server.tests.spectator.check [--data docs/stage3/data] [--capture <폴더>]

판정
 1. 전광판: 줄 = 스냅샷 시각 기준 24시간의 말풍선 행·운영 행(틀 문장이 있는 종류)·장면 카드, 최근 순 12줄까지. 행 id·순서가 같다.
    글 행·반응 행 링크 = /t/<글타래>#<글>, 그 밖 = /a/<이웃>, 운영 행 = 링크 없음. 닉네임 뒤 이/가 가 받침에 맞다. 원장 행 id 가 title 에
 2. 관계 한 장: 패널의 이웃 목록 = 스냅샷 sociogram 에서 그 이웃이 낀 선의 상대 전부, 색(우호·대립·엇갈림·중립) = 리플레이 반응 행,
    보냄·받음 = 선 무게. 말없이 다녀감 N회·방문 M회 = 리플레이 30일 행
 3. 답할 차례: 머리 위 띠·끈·패널 줄 = market 의 지목 열린 부탁·손 든 부탁·산출물 온 부탁, 기다린 시간 = requests/{id}.json 단계 시각
 4. 따라가기 카메라: 연출 켬 리플레이에서 말풍선이 뜨면 카메라가 그 이웃의 동네로 가서 확대(auto). + 단추를 누르면 꺼지고 확대는 사람 것.
    ?follow=0 · 연출 끔이면 카메라가 안 움직인다. 켬으로 하루를 끝까지 돌려도 말풍선 수 = 파일 counts
 5. 리플레이 말없이 다녀감 팻말: 그 방문 행 때 팻말이 뜨고, 말풍선 수(.pz-bubble)는 그대로
 6. 폰(390×844): 가로 넘침 0, 전광판·패널이 화면 안
 7. 페이지 오류 0
자 검사(검사기가 실패를 낼 수 있음을 보인다): 조사를 뒤집은 전광판 글은 「틀림」, 우호·대립을 뒤바꾼 기대값은 「다름」,
말없이 다녀감 팻말을 .pz-bubble 로 만든 사본은 말풍선 수가 「다름」.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from ..stage3_check import DET_FLAGS, KST, REPO, Checks, josa_errors, plaza_site, serve

TICK_TYPES = {"post_created", "reaction_added", "request_opened", "request_claimed", "request_delivered", "request_fetched",
              "gold_given", "agent_joined", "op_notice", "op_notice_edit", "op_event", "op_event_result", "op_hidden"}
FRIEND, FOE = {"agree", "thanks", "repro_ok"}, {"rebut", "repro_fail"}
DESKTOP = dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1)


def ms(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000


def load(data: Path):
    snap = json.loads((data / "snapshot.json").read_text(encoding="utf-8"))
    idx = json.loads((data / "replay" / "index.json").read_text(encoding="utf-8"))
    days = {d["date"]: json.loads((data / "replay" / f"{d['date']}.json").read_text(encoding="utf-8")) for d in idx["dates"]}
    return snap, idx, days


def expect_ticker(snap, days):
    gen = ms(snap["generated"])
    rows = [e for d in sorted(days) for e in days[d]["events"]]
    rows = [e for e in rows if (e.get("bubble") or e["type"].startswith("op_")) and e["type"] in TICK_TYPES]
    items = [(e["at"], e["id"], "event") for e in rows] + [(c["at"], c["id"], "scene") for c in snap["plaza"].get("scenes") or []]
    # 화면: 시각 내림차순, 같은 시각이면 id 내림차순
    items = sorted(items, key=lambda x: (ms(x[0]), x[1]), reverse=True)
    day = [x for x in items if ms(x[0]) >= gen - 864e5]
    return (day[:12], False) if day else (items[:5], True), rows


def quiet_visits(rows, aid):
    mine = [e for e in rows if e.get("actor") == aid]
    visits = quiet = 0
    for i, e in enumerate(mine):
        if e["type"] != "agent_visited":
            continue
        visits += 1
        silent = True
        for n in mine[i + 1:]:
            if n["type"] == "agent_visited":
                break
            if n.get("bubble"):
                silent = False
                break
        quiet += silent
    return visits, quiet


def expect_rel(snap, days, aid, flip=False):
    gen = ms(snap["generated"])
    rows = [e for d in sorted(days) for e in days[d]["events"] if gen - 30 * 864e5 <= ms(e["at"]) <= gen]
    per = {}
    for e in snap["plaza"]["sociogram"]["edges"]:
        if aid not in (e["from"], e["to"]):
            continue
        o = e["to"] if e["from"] == aid else e["from"]
        if o == aid:
            continue
        s = per.setdefault(o, {"out": 0, "in": 0, "fr": 0, "fo": 0})
        s["out" if e["from"] == aid else "in"] += e["weight"]
    fr_set, fo_set = (FOE, FRIEND) if flip else (FRIEND, FOE)
    for e in rows:
        if e["type"] != "reaction_added":
            continue
        d = e.get("data") or {}
        o = d.get("target_author") if e.get("actor") == aid else e.get("actor") if d.get("target_author") == aid else None
        if o in per:
            per[o]["fr"] += d.get("kind") in fr_set
            per[o]["fo"] += d.get("kind") in fo_set
    tone = {o: ("mixed" if s["fr"] and s["fo"] else "friend" if s["fr"] else "foe" if s["fo"] else "plain") for o, s in per.items()}
    return per, tone, quiet_visits(rows, aid)


def expect_owe(snap, data: Path):
    out = {}
    for m in snap["plaza"].get("market") or []:
        r = json.loads((data / "requests" / f"{m['id']}.json").read_text(encoding="utf-8")).get("request") or {}
        frm = (m.get("from") or {}).get("id")
        to = (m.get("to") or {}).get("id")
        claimer = (r.get("claimed_by") or {}).get("id") if isinstance(r.get("claimed_by"), dict) else r.get("claimed_by")
        if m["state"] == "open" and to:
            who, since = to, r.get("opened_at")
        elif m["state"] == "claimed" and claimer:
            who, since = claimer, r.get("claimed_at")
        elif m["state"] == "delivered":
            who, since = frm, r.get("delivered_at")
        else:
            continue
        had = out.get(who)
        if not had or (since and (not had[1] or ms(since) < ms(had[1]))):
            out[who] = (m["id"], since)
    return out


def wait_hours(since: str, now_ms: float) -> str:
    h = max(0, int((now_ms - ms(since)) // 3600e3))
    if h < 1:
        return "1시간 안"
    return f"{h}시간째" if h < 24 else f"{h // 24}일 {h % 24}시간째"


REL_JS = r"""async (id) => {
  const wait = (f, ms = 20000) => new Promise((ok, no) => { const t0 = Date.now();
    (function loop() { if (f()) return ok(); if (Date.now() - t0 > ms) return no(new Error('timeout rel ' + id)); setTimeout(loop, 30); })(); });
  const m = document.getElementById('pzWho');
  if (!m.hidden) document.getElementById('pzWhoX').click();
  const b = document.createElement('button'); b.dataset.agent = id;
  document.getElementById('pzTalk').append(b); b.click(); b.remove();
  await wait(() => m.dataset.rel === '1' && m.dataset.who === id);
  const box = m.querySelector('.pz-rel'), sh = m.querySelector('.pz-sheet'), r = sh.getBoundingClientRect();
  return {
    others: [...box.querySelectorAll('.pz-rellist > li[data-other]')].map((li) => ({ id: li.dataset.other, tone: (li.className.match(/tone-(\w+)/) || [])[1],
      text: li.textContent })),
    svg: !!box.querySelector('svg.pz-relsvg'),
    quiet: box.querySelector('.pz-quietrow') ? { n: +box.querySelector('.pz-quietrow').dataset.quiet, v: +box.querySelector('.pz-quietrow').dataset.visits } : null,
    owe: box.querySelector('.pz-owerow') ? { request: box.querySelector('.pz-owerow').dataset.request, text: box.querySelector('.pz-owerow').textContent } : null,
    over: (sh.scrollWidth > sh.clientWidth + 1 ? 1 : 0) + [...box.querySelectorAll('*')].filter((el) => el.getBoundingClientRect().right > r.right + 1).length,
    box: { l: r.left, r: r.right }, vw: innerWidth,
  };
}"""


def open_page(browser, url, q, when, errs, dev=None, motion=False):
    ctx = browser.new_context(**(dev or DESKTOP), reduced_motion="no-preference" if motion else "reduce")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.clock.install(time=when)
    pg.goto(f"{url}/?{q}")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(1500)
    pg.wait_for_function("() => window.Plaza && Plaza.stats().ticker !== undefined && document.querySelectorAll('#pzThings .pz-zone').length > 0", timeout=30000)
    return ctx, pg


def run(data: Path, work: Path, capture: Path | None) -> Checks:
    from playwright.sync_api import sync_playwright
    C = Checks()
    snap, idx, days = load(data)
    site = plaza_site(work / "site", data)
    url, srv = serve(site)
    when = dt.datetime.fromisoformat(snap["generated"]).astimezone(KST) + dt.timedelta(minutes=1)
    now_ms = when.timestamp() * 1000
    nicks = [a["nickname"] for a in snap["plaza"]["roster"]]
    errs: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=DET_FLAGS)

            # 1. 전광판
            G = "전광판"
            ctx, pg = open_page(browser, url, "mode=now&motion=0", when, errs)
            st = pg.evaluate("Plaza.stats()")
            (want, old), rows = expect_ticker(snap, days)
            got = st["ticker"]
            got_ids = [x["event"] or x["scene"] for x in got]
            C.check(G, f"줄 = 24시간 말풍선·운영 행·장면 {len(want)}줄, 최근 순", got_ids == [w[1] for w in want] and len(got) == len(want) and not old,
                    f"화면 {len(got)} · 기대 {len(want)} · 첫 줄 {got_ids[:2]}")
            by_id = {e["id"]: e for e in rows}
            # 녹화 데이터는 최근 12줄이 장면 카드로 차서, 장면 칸을 비운 스냅샷 변형으로 원장 행 줄의 링크·조사를 따로 잔다
            snap2 = json.loads(json.dumps(snap))
            snap2["plaza"]["scenes"] = []
            site2 = plaza_site(work / "site_noscene", data, snap2)
            url2, srv2 = serve(site2)
            ctx2, pg2 = open_page(browser, url2, "mode=now&motion=0", when, errs)
            got2 = pg2.evaluate("Plaza.stats()")["ticker"]
            (want2, _), _ = expect_ticker(snap2, days)
            ctx2.close()
            srv2.shutdown()
            C.check(G, f"장면 없는 변형: 줄 = 24시간 말풍선·운영 행 {len(want2)}줄", [x["event"] for x in got2] == [w[1] for w in want2] and len(got2) > 3,
                    f"화면 {len(got2)} · 기대 {len(want2)}")
            got = got + got2
            bad_href = []
            for x in got:
                if x["scene"]:
                    continue
                e = by_id[x["event"]]
                d = e.get("data") or {}
                if e["type"] == "post_created" and d.get("thread_id"):
                    want_href = f"/t/{d['thread_id']}#{e['subject']}"
                elif e["type"].startswith("op_"):
                    want_href = None
                else:
                    want_href = None if e["type"] == "reaction_added" else f"/a/{e['actor']}"
                if e["type"] == "reaction_added":
                    ok = x["href"] and (x["href"].startswith("/t/") or x["href"].startswith("/a/"))
                else:
                    ok = x["href"] == want_href
                if not ok:
                    bad_href.append((x["event"], x["href"], want_href))
            C.check(G, "링크: 글 행 /t/<글타래>#<글>, 반응 행 /t/·/a/, 부탁·한마디 등 /a/<이웃>, 운영 행 없음", not bad_href, str(bad_href[:3]) or f"{len(got)}줄")
            titles = pg.evaluate("[...document.querySelectorAll('#pzTicker .pz-tka')].map((a) => a.title)")
            C.check(G, "줄마다 원장 행 id 가 title 에", len(titles) == len(st["ticker"]) and all(t.startswith("원장 행 ev_") for t in titles), titles[:2])
            texts = " / ".join(x["text"] for x in got)
            jb = josa_errors(texts, nicks)
            flipped = re.sub(r"(" + "|".join(map(re.escape, sorted(nicks, key=len, reverse=True))) + r")(이|가)(?= )",
                             lambda m: m.group(1) + ("가" if m.group(2) == "이" else "이"), texts)
            C.check(G, "닉네임 뒤 이/가 가 받침에 맞음 (자 검사: 조사를 뒤집으면 틀림)", not jb and josa_errors(flipped, nicks),
                    f"틀림 {jb} · 뒤집은 사본 틀림 {len(josa_errors(flipped, nicks))}")
            if capture:
                pg.screenshot(path=str(capture / "spectator_desktop_now.png"))

            # 3. 답할 차례 (지금)
            G = "답할 차례"
            owe = expect_owe(snap, data)
            got_owe = {o["id"]: o["request"] for o in st["owe"]}
            C.check(G, "대상 = market 의 지목 열린·손 든·산출물 온 부탁", got_owe == {k: v[0] for k, v in owe.items()}, f"화면 {got_owe} · 기대 {owe}")
            chips = pg.evaluate("[...document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-owe')].map((o) => ({ id: o.closest('.pz-agent').dataset.id, req: o.dataset.request, text: o.textContent }))")
            want_chip = {k: f"⏳ 답할 차례 {wait_hours(v[1], now_ms)}" for k, v in owe.items() if v[1]}
            C.check(G, "이름표 아래 띠 = 그 이웃 · 기다린 시간(requests 단계 시각)", {c["id"]: c["text"] for c in chips} == want_chip, f"화면 {chips} · 기대 {want_chip}")
            lines = pg.evaluate("[...document.querySelectorAll('#pzLinks .oweline')].map((l) => l.dataset.request)")
            C.check(G, "끈(점선) = 띠마다 하나 (같은 동네일 때)", sorted(lines) == sorted(v[0] for v in owe.values()), f"끈 {lines}")

            # 2. 관계 한 장 — 선이 가장 많은 이웃 둘
            G = "관계 한 장"
            deg = {}
            for e in snap["plaza"]["sociogram"]["edges"]:
                for a in (e["from"], e["to"]):
                    deg[a] = deg.get(a, 0) + 1
            targets = sorted(deg, key=lambda a: (-deg[a], a))[:2] + list(owe)[:1]
            for aid in dict.fromkeys(targets):
                w = pg.evaluate(REL_JS, aid)
                per, tone, (visits, quiet) = expect_rel(snap, days, aid)
                gt = {o["id"]: o["tone"] for o in w["others"]}
                name = next((a["nickname"] for a in snap["plaza"]["roster"] if a["id"] == aid), aid)
                C.check(G, f"{name}: 이웃·색 = sociogram 선 + 반응 행, 그림 있음", gt == tone and w["svg"], f"화면 {gt} · 기대 {tone}")
                cnt_bad = [o["id"] for o in w["others"] if f"보냄 {per[o['id']]['out']} · 받음 {per[o['id']]['in']}" not in o["text"]]
                C.check(G, f"{name}: 보냄·받음 = 선 무게", not cnt_bad, str(cnt_bad))
                C.check(G, f"{name}: 말없이 다녀감 {quiet}회 / 방문 {visits}회", w["quiet"] == {"n": quiet, "v": visits}, str(w["quiet"]))
                if aid in owe:
                    C.check("답할 차례", f"{name}: 패널 줄 = 그 부탁", w["owe"] and w["owe"]["request"] == owe[aid][0], str(w["owe"]))
            # 자 검사가 실제로 뒤집히는지(대립 선이 있는 이웃에서): 뒤바꾼 기대값과 화면이 달라야 한다
            foe_aid = next((a for a in deg if any(t in ("foe", "friend") for t in expect_rel(snap, days, a)[1].values())), None)
            if foe_aid:
                w = pg.evaluate(REL_JS, foe_aid)
                _, tf, _ = expect_rel(snap, days, foe_aid, flip=True)
                C.check(G, "자 검사: 우호·대립을 뒤바꾼 기대값은 화면과 다름", {o["id"]: o["tone"] for o in w["others"]} != tf, f"뒤바꾼 기대 {tf}")
            if capture:
                pg.evaluate("document.querySelector('#pzWho .pz-rel').scrollIntoView()")
                pg.screenshot(path=str(capture / "spectator_desktop_panel.png"))
            ctx.close()

            # 4. 따라가기 카메라
            G = "따라가기 카메라"
            busiest = max((d for d in idx["dates"] if d["bubbles"]), key=lambda d: d["bubbles"])
            date = busiest["date"]
            ctx, pg = open_page(browser, url, f"view=replay&motion=1&date={date}&autopause=0&speed=60", when, errs, motion=True)
            pg.evaluate(f"Plaza.replay({{date: '{date}', speed: 60, autopause: false}})")
            seen = None
            for _ in range(240):
                pg.clock.run_for(250)
                s = pg.evaluate("Plaza.stats()")
                if s["emitted"] > 0 and s["follow"]["auto"]:
                    seen = s
                    break
            if seen:
                bub = [b for b in seen["bubbleTexts"]]
                fig_d = pg.evaluate("(ids) => ids.map((id) => { const el = document.querySelector(`#pzFigures .pz-agent[data-id='${id}']`); return parseFloat(el.style.left); })",
                                    [b["id"] for b in bub])
                dist = lambda x: max(0, min(2, int((x + 1376) // 1376)))
                names = ["west", "center", "east"]
                C.check(G, "말풍선이 뜨면 그 이웃 동네로 가서 확대 (연출 켬)", seen["zoom"]["z"] > 1.001 and seen["zoom"]["d"] in [names[dist(x)] for x in fig_d],
                        f"확대 {seen['zoom']['z']:.2f} · 동네 {seen['zoom']['d']} · 말풍선 이웃 동네 {[names[dist(x)] for x in fig_d]}")
            else:
                C.check(G, "말풍선이 뜨면 그 이웃 동네로 가서 확대 (연출 켬)", False, "카메라가 안 움직임")
            if capture:
                pg.clock.run_for(900)
                pg.screenshot(path=str(capture / "spectator_desktop_follow.png"))
            pg.click("#pzZoom [data-z=in]")
            pg.clock.run_for(300)
            z_hand = pg.evaluate("Plaza.stats()")
            pg.clock.run_for(20000)
            z_after = pg.evaluate("Plaza.stats()")
            C.check(G, "+ 단추를 누르면 따라가기 꺼짐, 그 뒤 확대는 사람 것(카메라가 안 바꿈)",
                    not z_hand["follow"]["on"] and not z_after["follow"]["auto"] and abs(z_after["zoom"]["z"] - z_hand["zoom"]["z"]) < 1e-6 and z_after["emitted"] > z_hand["emitted"],
                    f"켬 {z_hand['follow']['on']} · 확대 {z_hand['zoom']['z']:.2f} → {z_after['zoom']['z']:.2f} · 말풍선 {z_hand['emitted']} → {z_after['emitted']}")
            ctx.close()
            for q, label, motion in ((f"view=replay&motion=1&follow=0&date={date}&autopause=0&speed=60", "?follow=0", True),
                                     (f"view=replay&motion=0&date={date}&autopause=0&speed=60", "연출 끔", False)):
                ctx, pg = open_page(browser, url, q, when, errs, motion=motion)
                pg.evaluate(f"Plaza.replay({{date: '{date}', speed: 60, autopause: false}})")
                zs = []
                for _ in range(60):
                    pg.clock.run_for(500)
                    s = pg.evaluate("Plaza.stats()")
                    zs.append(s["zoom"]["z"])
                C.check(G, f"{label}: 카메라가 안 움직임", max(zs) < 1.001 and s["emitted"] > 0, f"최대 확대 {max(zs):.2f} · 말풍선 {s['emitted']}")
                ctx.close()
            for d in idx["dates"]:
                if not d["bubbles"]:
                    continue
                ctx, pg = open_page(browser, url, f"view=replay&motion=1&date={d['date']}&autopause=0&speed=600", when, errs, motion=True)
                pg.evaluate(f"Plaza.replay({{date: '{d['date']}', speed: 600, autopause: false}})")
                pg.clock.run_for(150_000)
                s = pg.evaluate("Plaza.stats()")
                ctx.close()
                C.check(G, f"따라가기 켬으로 {d['date']} 끝까지: 말풍선 수 = 파일", s["emitted"] == s["expected"] == d["bubbles"] and not s["playing"],
                        f"{s['emitted']} / {s['expected']} / index {d['bubbles']}")

            # 5. 리플레이 말없이 다녀감 팻말
            G = "말없이 다녀감"
            qdate = next((dd for dd in sorted(days) if any(e["type"] == "agent_visited" and quiet_visits([x for x in days[dd]["events"]], e["actor"])[1]
                                                           for e in days[dd]["events"])), None)
            ctx, pg = open_page(browser, url, f"view=replay&motion=1&date={qdate}&autopause=0&speed=60", when, errs, motion=True)
            pg.evaluate(f"Plaza.replay({{date: '{qdate}', speed: 60, autopause: false}})")
            hit = None
            for _ in range(400):
                pg.clock.run_for(200)
                s = pg.evaluate("Plaza.stats()")
                if s["quiet"]:
                    hit = s
                    break
            tags = pg.evaluate("[...document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-quiet')].map((t) => t.closest('.pz-agent').dataset.id)") if hit else []
            C.check(G, "방문 행에 팻말 「👣 말없이 다녀감」, 말풍선 아님", bool(hit) and set(tags) == set(hit["quiet"]) and hit["bubblesOnStage"] == len(hit["bubbleTexts"]),
                    f"팻말 {tags} · 말풍선 {hit and hit['bubblesOnStage']}")
            if hit:
                if capture:
                    pg.screenshot(path=str(capture / "spectator_desktop_quiet.png"))
                n0 = pg.evaluate("document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-bubble').length")
                pg.evaluate("document.querySelectorAll('#pzFigures .pz-quiet').forEach((t) => t.classList.add('pz-bubble'))")
                n1 = pg.evaluate("document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-bubble').length")
                C.check(G, "자 검사: 팻말을 .pz-bubble 로 만든 사본은 말풍선 수가 다름", n1 != n0, f"{n0} → {n1}")
            ctx.close()

            # 6. 폰
            G = "폰 390×844"
            phone = {k: v for k, v in p.devices["iPhone 13"].items() if k != "default_browser_type"}
            ctx, pg = open_page(browser, url, "mode=now&motion=0", when, errs, dev=phone)
            o = pg.evaluate("(() => { const t = document.getElementById('pzTicker').getBoundingClientRect(); return { sw: document.documentElement.scrollWidth, vw: innerWidth, tl: t.left, tr: t.right }; })()")
            C.check(G, "가로 넘침 0, 전광판이 화면 안", o["sw"] <= o["vw"] and o["tl"] >= 0 and o["tr"] <= o["vw"], str(o))
            if capture:
                pg.screenshot(path=str(capture / "spectator_phone_now.png"))
            aid = sorted(deg, key=lambda a: (-deg[a], a))[0]
            w = pg.evaluate(REL_JS, aid)
            C.check(G, "관계 한 장 패널이 화면 안, 넘침 0", w["over"] == 0 and w["box"]["l"] >= 0 and w["box"]["r"] <= w["vw"] + 0.5, f"넘침 {w['over']} · {w['box']} / {w['vw']}")
            if capture:
                pg.evaluate("document.querySelector('#pzWho .pz-rel').scrollIntoView()")
                pg.screenshot(path=str(capture / "spectator_phone_panel.png"))
            ctx.close()
            browser.close()
        C.check("페이지 오류", "0", not errs, "; ".join(errs[:3]))
    finally:
        srv.shutdown()
    return C


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(REPO / "docs" / "stage3" / "data"))
    ap.add_argument("--work", default=None)
    ap.add_argument("--capture", help="캡처 폴더 (spectator_*.png)")
    a = ap.parse_args(argv)
    import tempfile
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="plaza-spectator-"))
    capture = Path(a.capture).expanduser() if a.capture else None
    if capture:
        capture.mkdir(parents=True, exist_ok=True)
    C = run(Path(a.data), work, capture)
    n = sum(r["ok"] for r in C.rows)
    print(f"판정 {n}/{len(C.rows)} 통과")
    if not a.work and n == len(C.rows):
        import shutil
        shutil.rmtree(work, ignore_errors=True)   # 직접 만든 임시 폴더는 통과하면 지운다(실패면 남겨 본다)
    elif not a.work:
        print(f"작업 폴더 남김: {work}")
    return 0 if n == len(C.rows) else 1


if __name__ == "__main__":
    sys.exit(main())
