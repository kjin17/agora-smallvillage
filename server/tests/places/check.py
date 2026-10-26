"""장소 셋: 골드 장부(시장 거리 W1)·환영 정자(중앙 C1)·소문 나무(샘·정원 E1) (2026-10-23, snapshot-plaza.md 2·4절).

  python3 -m server.tests.places.check [--capture <폴더>]

새 임시 서버에 3단계 시나리오 + 골드 이동(운영 지급·차감·행사 지급 셋·보상 넘김·돌려줌·걸린 채)·떠난 이웃을 얹고 잰다.
- 공개 칸: 스냅샷 plaza.gold_moves 의 count·received·supply = DB 에서 따로 센 값, 행사 지급은 한 줄 「N명」(이름 없음),
  잔액 순위 칸 없음, roster[].joined_at = agents/{id}.json 의 agent.joined_at, check_public 화이트리스트 통과
  자 검사: 묶음 줄에 이름을 붙이거나 잔액 칸을 넣은 사본은 check_public Walker 가 「표에 없는 칸」으로 잡는다
- 화면: 장소 셋이 그려지고(구역 이름표 열은 그대로), 그림 발끝이 원래 빈 땅 자리, 그림·이름표가 그 동네 틀 안,
  다른 그림·이름표·문 팻말·노점 팻말·등과 안 겹침(자 검사: 이름표를 노점 이름표 자리로 옮기면 「겹침」),
  데스크톱 장면 아래 설명 띠에 안 가림
- 팝업: 골드 첫 줄 = 스냅샷·DB, 행사 지급만 받은 이웃 이름이 골드 팝업에 없음, 정자 N·M = DB, 떠난 이웃 없음,
  소문 나무 사슬 수 = dashboard.rumor, 긴 사슬 이름 순서, 장면 카드는 rumor_3hop 만. 빈 서버에선 세 곳 다 빈 상태 문구
- 폰: 이름표 한 번 탭 → 팝업. 페이지 오류 0
옛 판(561c35a)에 대면 칸·화면 판정이 실패해야 한다(.get 으로만 읽는다)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

from .. import check_public
from ..harness import Checks, Server
from . import data

DESKTOP = {"viewport": {"width": 1440, "height": 900}}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
PLACES = ("gold", "welcome", "rumor")
ALL_PLACES = PLACES + ("well",)   # 10-25 물음 우물(E2)도 그림 자리·겹침은 같이 잰다. 팝업은 server/tests/question_well
EAST, WEST = 1376, -1376
HOME = {"gold": WEST, "welcome": 0, "rumor": EAST, "well": EAST}

# 장면 위 요소 상자를 세계 좌표로 (stage3_check WORLD_BOXES_JS 와 같은 식)
BOXES_JS = """() => { const s = Plaza.stats(), z = s.zoom, w = document.getElementById('pzWrap').getBoundingClientRect(), k = z.fit * z.z;
  const back = (r) => [z.cx + (r.left - w.left - 1376 * z.fit / 2) / k, z.cy + (r.top - w.top - 768 * z.fit / 2) / k,
                       z.cx + (r.right - w.left - 1376 * z.fit / 2) / k, z.cy + (r.bottom - w.top - 768 * z.fit / 2) / k];
  return [...document.querySelectorAll('#pzThings > *')].map((e) => ({cls: e.className, zone: e.dataset.zone || '', place: e.dataset.place || '',
    to: e.dataset.to || '', box: back(e.getBoundingClientRect())})); }"""


def _db(S, q, a=()):
    cn = sqlite3.connect(f"file:{S.db}?mode=ro", uri=True)
    try:
        return cn.execute(q, a).fetchall()
    finally:
        cn.close()


def hits(items: list, mine: list) -> list[str]:
    out = []
    for m in mine:
        for it in items:
            if it["place"] == m["place"]:   # 자기 그림·이름표끼리는 안 잰다(이름표는 그림 위·옆)
                continue
            a, b = m["box"], it["box"]
            if a[0] < b[2] - 0.5 and a[2] > b[0] + 0.5 and a[1] < b[3] - 0.5 and a[3] > b[1] + 0.5:
                out.append(f"{m['place']}({'그림' if 'pz-thing' in m['cls'] else '이름표'})×{it['cls'].split()[0]}:{it['zone'] or it['place'] or it['to']}")
    return out


def popup(pg, place):
    pg.evaluate("Plaza.closeSpot()")
    pg.evaluate(f"Plaza.openSpot('{place}')")
    pg.wait_for_function("() => Plaza.spot().ready", timeout=15000)
    return pg.evaluate("""() => { const b = document.getElementById('pzSpotBody'), st = b.querySelector('.pz-spotstat');
      return {text: b.innerText, stat: st ? {...st.dataset, text: st.textContent} : null, empty: !!b.querySelector('.pz-spotempty'),
        lists: Object.fromEntries([...b.querySelectorAll('[data-list]')].map((l) => [l.dataset.list, l.innerText])),
        rows: Object.fromEntries([...b.querySelectorAll('ul[data-list]')].map((l) => [l.dataset.list, l.querySelectorAll(':scope > .pz-si').length])),
        kinds: [...b.querySelectorAll('[data-list=gold] > .pz-si')].map((l) => l.dataset.kind),
        depth: [...b.querySelectorAll('[data-list=rumor] > .pz-si')].map((l) => Number(l.dataset.depth)),
        agents: [...b.querySelectorAll('[data-list=welcome] > .pz-si')].map((l) => l.dataset.agent2),
        rules: [...b.querySelectorAll('[data-list=rumor-scenes] .pz-scene')].length }; }""")


def data_checks(C: Checks, S, R) -> dict:
    snap = S.get("/public/snapshot.json").json or {}
    P = snap.get("plaza") or {}
    gm = P.get("gold_moves") or {}
    gen = dt.datetime.fromisoformat(snap.get("generated", "2000-01-01T00:00:00+09:00"))
    lo = (gen - dt.timedelta(days=7)).isoformat(timespec="seconds")
    rows = _db(S, "SELECT agent_id, delta, kind, notice_id FROM gold_ledger WHERE at>=?", (lo,))
    want_count = sum(1 for r in rows if not (r[2] is None and r[3])) + len({r[3] for r in rows if r[2] is None and r[3]})
    want_recv = sum(r[1] for r in rows if (r[2] is None and r[1] > 0) or r[2] == "payout")
    want_supply = _db(S, "SELECT COALESCE(SUM(delta),0) FROM gold_ledger")[0][0]
    C.check("골드 장부 칸: count·received·supply = DB 에서 따로 센 값 (행사 지급은 한 줄)",
            gm.get("count") == want_count and gm.get("received") == want_recv and gm.get("supply") == want_supply and want_count == 9,
            f"스냅샷 {gm.get('count')}/{gm.get('received')}/{gm.get('supply')} · DB {want_count}/{want_recv}/{want_supply}")
    ev = [r for r in gm.get("rows") or [] if r.get("kind") == "event_award"]
    C.check("행사 지급 묶음: 한 줄 · 3명 · 30골드 · 이름 없음, 다른 줄에 그 행사 id 없음",
            len(ev) == 1 and ev[0].get("recipients") == 3 and ev[0].get("delta") == 30 and ev[0].get("from") is None
            and ev[0].get("to") is None and all(not r.get("notice_id") for r in gm.get("rows") or [] if r.get("kind") != "event_award"), str(ev))
    C.check("골드 장부 칸 모양: 잔액·순위 칸 없음, 줄 ≤ 10 최근 순",
            set(gm) == {"window_days", "count", "received", "given", "supply", "rows"} and 0 < len(gm.get("rows") or []) <= 10
            and [r["at"] for r in gm["rows"]] == sorted((r["at"] for r in gm["rows"]), reverse=True)
            and not any("balance" in r for r in gm["rows"]), f"{sorted(gm)} · {len(gm.get('rows') or [])}줄")
    kinds = {r.get("kind"): r for r in gm.get("rows") or []}
    pay = kinds.get("payout") or {}
    C.check("방향: 보상 넘김 = 부탁 낸 이 → 산출물 쓴 이, 맡김 = 낸 이 → 노점, 돌려줌 = 노점 → 낸 이",
            (pay.get("from") or {}).get("id") == R.id["sol"] and (pay.get("to") or {}).get("id") == R.id["peb"]
            and (kinds.get("escrow") or {}).get("to") is None and (kinds.get("refund") or {}).get("from") is None,
            json.dumps({k: [((v.get("from") or {}).get("nickname")), ((v.get("to") or {}).get("nickname"))] for k, v in kinds.items()}, ensure_ascii=False))
    bad = []
    for a in P.get("roster") or []:
        j = S.get(f"/public/agents/{a['id']}.json").json or {}
        if "joined_at" not in a or a.get("joined_at") != (j.get("agent") or {}).get("joined_at"):
            bad.append(a.get("nickname"))
    C.check("roster[].joined_at = agents/{id}.json 의 agent.joined_at (떠난 이웃 포함 전부)", not bad and len(P.get("roster") or []) == 12,
            bad[:3] or f"{len(P.get('roster') or [])}명")
    wl, et = check_public.spec_whitelist(), check_public.spec_event_types()
    W = check_public.Walker(wl, et)
    W.walk(check_public.SNAPSHOT, snap)
    C.check("check_public 화이트리스트: 새 칸(gold_moves·joined_at) 포함 스냅샷 통과", not W.bad and "gold_move" in wl, W.bad[:4])
    probe = json.loads(json.dumps(snap))
    for r in probe["plaza"].get("gold_moves", {}).get("rows", []):
        if r.get("kind") == "event_award":
            r["to"] = {"id": R.id["dot"], "nickname": "도토리"}
    probe["plaza"].setdefault("gold_moves", {})["balances"] = [{"id": R.id["sol"], "balance": 1}]
    W2 = check_public.Walker(wl, et)
    W2.walk(check_public.SNAPSHOT, probe)
    C.check("자 검사: 묶음 줄에 이름·잔액 칸을 넣은 사본은 check_public 이 잡는다",
            any("행사 지급 묶음에 이름" in b for b in W2.bad) and any("balances" in b for b in W2.bad), W2.bad[:3])
    return snap


def screen_checks(C: Checks, browser, S, R, snap, capture: Path | None):
    errs = []
    ctx = browser.new_context(**DESKTOP)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(S.url + "/?mode=now&motion=0")
    pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
    pg.wait_for_timeout(800)
    st = pg.evaluate("Plaza.stats()")
    C.check("장소 셋이 그려짐 (이름표·그림), 구역 이름표 열은 그대로",
            st.get("placesShown") == list(ALL_PLACES) and len(st.get("zonesShown") or []) == 10
            and pg.evaluate("document.querySelectorAll('#pzThings .pz-thing[data-place]').length") == len(ALL_PLACES),
            f"장소 {st.get('placesShown')} · 구역 {len(st.get('zonesShown') or [])}")
    pl = st.get("places") or {}
    foot = {k: v for k, v in pl.items() if not (v["lot"][0] - v["lot"][2] / 2 <= v["prop"][1] <= v["lot"][0] + v["lot"][2] / 2
                                                 and abs(v["prop"][2] - v["lot"][1]) <= v["lot"][3] / 2 + 40)}
    C.check("그림 발끝이 원래 빈 땅 자리 (W1·C1·E1·E2 상자 가로 안, 세로 ±40)", len(pl) == len(ALL_PLACES) and not foot,
            {k: v["prop"][1:] for k, v in pl.items()})
    out = {}
    for d in ("west", "center", "east"):
        pg.evaluate(f"Plaza.district('{d}')")
        pg.wait_for_timeout(300)
        items = pg.evaluate(BOXES_JS)
        mine = [i for i in items if i["place"]]
        out[d] = (items, mine)
    allitems = out["west"][0]
    mine = [i for i in allitems if i["place"]]
    frame = [f"{m['place']} {[round(x) for x in m['box']]}" for m in mine
             if not (HOME[m["place"]] <= m["box"][0] and m["box"][2] <= HOME[m["place"]] + 1376 and 0 <= m["box"][1] and m["box"][3] <= 768)]
    over = hits(allitems, mine)
    C.check("장소 그림·이름표가 그 동네 틀 안", len(mine) == 2 * len(ALL_PLACES) and not frame, frame or f"{len(mine)}개")
    C.check("장소 그림·이름표가 다른 그림·이름표·문 팻말·노점 팻말·등·서로와 안 겹침", len(mine) == 2 * len(ALL_PLACES) and not over,
            over[:4] or f"잰 상자 {len(allitems)}")
    zone_m = next((i for i in allitems if i["zone"] == "market" and "pz-zone" in i["cls"]), None)
    probe = [dict(m) for m in mine]
    if zone_m:
        g = next(m for m in probe if m["place"] == "gold" and "pz-place" in m["cls"])
        g["box"] = [zone_m["box"][0] + 5, zone_m["box"][1] + 2, zone_m["box"][2] + 5, zone_m["box"][3] + 2]
    C.check("자 검사: 골드 장부 이름표를 노점 이름표 자리로 옮기면 「겹침」", bool(zone_m) and any("pz-zone:market" in h for h in hits(allitems, [p for p in probe if p["place"] == "gold"])),
            "노점 이름표 없음" if not zone_m else "")
    # 데스크톱: 장면 아래 설명 띠(pz-corner)가 장소 그림·이름표를 가리지 않는다
    hid = []
    for d, place in (("west", "gold"), ("center", "welcome"), ("east", "rumor")):
        pg.evaluate(f"Plaza.district('{d}')")
        pg.wait_for_timeout(300)
        hid += pg.evaluate("""(p) => { const c = document.getElementById('pzCorner').getBoundingClientRect(), out = [];
          for (const e of document.querySelectorAll(`#pzThings [data-place="${p}"]`)) { const r = e.getBoundingClientRect();
            if (r.left < c.right && r.right > c.left && r.top < c.bottom && r.bottom > c.top) out.push(p + ':' + e.className); } return out; }""", place)
        if capture:
            pg.screenshot(path=str(capture / f"places_{d}_desktop.png"))
    C.check("데스크톱: 장면 아래 설명 띠에 장소 그림·이름표가 안 가림", not hid, hid)

    P = snap["plaza"]
    g = popup(pg, "gold")
    held = _db(S, "SELECT COALESCE(SUM(reward),0) FROM requests WHERE reward_state='held'")[0][0]
    names_only_event = ("도토리", "Mintleaf")
    C.check("골드 팝업 첫 줄: 이동 수 = 스냅샷 count, 걸린 골드 = DB held 합, 줄 수 = 스냅샷 rows",
            g["stat"] and g["stat"].get("count") == str(P["gold_moves"]["count"]) and g["stat"].get("held") == str(held) == "5"
            and g["rows"].get("gold") == len(P["gold_moves"]["rows"]), f"{g['stat']} · DB held {held} · 줄 {g['rows']}")
    C.check("골드 팝업: 행사 지급은 「행사 지급 · 3명」 한 줄, 행사로만 받은 이웃 이름은 팝업 어디에도 없음, 잔액 순위 없음",
            "행사 지급 · 3명" in g["text"] and g["kinds"].count("event_award") == 1 and not any(n in g["text"] for n in names_only_event)
            and "순위" in g["text"] and "잔액 상위" not in g["text"],
            [n for n in names_only_event if n in g["text"]] or g["kinds"])
    if capture:
        pg.screenshot(path=str(capture / "places_gold_popup_desktop.png"))
    w = popup(pg, "welcome")
    lo = (dt.datetime.fromisoformat(snap["generated"]) - dt.timedelta(days=14)).isoformat(timespec="seconds")
    # 같은 초 가입은 화면처럼 id 오름차순(roster 가 (joined_at, id) 순이고 화면 정렬은 안정 정렬). 없으면 동순위 순서가 들쭉날쭉해 3번에 1~2번 실패했다
    act = _db(S, "SELECT id FROM agents WHERE status<>'left' AND joined_at>=? ORDER BY joined_at DESC, id ASC", (lo,))
    posted = {r[0] for r in _db(S, "SELECT DISTINCT author FROM posts")}
    n, m = len(act), sum(1 for (a,) in act if a in posted)
    C.check("정자 첫 줄: 14일 새 이웃 N·첫 글 M = DB 따로 센 값 (떠난 이웃 뺌)",
            w["stat"] and w["stat"].get("n") == str(n) and w["stat"].get("posted") == str(m) and n == 11, f"{w['stat']} · DB {n}/{m}")
    C.check("정자 목록: 최근 가입 순 5명, 떠난 이웃 없음, 자기소개·첫 글 줄",
            w["agents"] == [a for (a,) in act][:5] and R.id["ghost"] not in w["agents"] and "떠난유령" not in w["text"]
            and "아직 첫 글 전" in w["text"] and "소식을 나릅니다" in w["text"], w["agents"])
    if capture:
        pg.screenshot(path=str(capture / "places_welcome_popup_desktop.png"))
    r = popup(pg, "rumor")
    rm = (P.get("dashboard") or {}).get("rumor") or {}
    C.check("소문 나무 첫 줄: 사슬 수 = dashboard.rumor.chains, 긴 사슬 = 솔바람 → 도토리 → Pebble → Mintleaf (3단계)",
            r["stat"] and r["stat"].get("chains") == str(rm.get("chains")) and r["depth"][:1] == [3]
            and "솔바람\n→\n도토리\n→\nPebble\n→\nMintleaf" in (r["lists"].get("rumor") or ""),
            f"{r['stat']} · 깊이 {r['depth']} · {(r['lists'].get('rumor') or '')[:60]!r}")
    cards = [c for c in P.get("scenes") or [] if c.get("rule") == "rumor_3hop"]
    C.check("소문 나무 장면 카드 = rumor_3hop 만, 최대 2장", 1 <= r["rules"] <= 2 and r["rules"] == min(2, len(cards)) and "반박 연쇄" not in r["lists"].get("rumor-scenes", ""),
            f"화면 {r['rules']} · 스냅샷 rumor_3hop {len(cards)}")
    if capture:
        pg.screenshot(path=str(capture / "places_rumor_popup_desktop.png"))
    C.check("페이지 오류 0 (데스크톱)", not errs, errs[:2])
    ctx.close()

    perr = []
    ctx = browser.new_context(**PHONE)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: perr.append(str(e)))
    pg.goto(S.url + "/?mode=now&motion=0")
    pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length >= 10", timeout=30000)
    opened = {}
    for d, place in (("west", "gold"), ("center", "welcome"), ("east", "rumor")):
        pg.evaluate(f"Plaza.district('{d}')")
        pg.wait_for_timeout(500)
        if capture:
            pg.screenshot(path=str(capture / f"places_{d}_phone.png"))
        b = pg.locator(f'#pzThings .pz-place[data-place="{place}"]').bounding_box()
        if not b:
            opened[place] = None
            continue
        pg.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        try:
            pg.wait_for_function("() => Plaza.spot().ready", timeout=15000)
            opened[place] = pg.evaluate("Plaza.spot().zone")
        except Exception:
            opened[place] = None
        if capture:
            pg.screenshot(path=str(capture / f"places_{place}_popup_phone.png"))
        pg.evaluate("Plaza.closeSpot()")
        pg.wait_for_timeout(200)
    C.check("폰: 장소 이름표 한 번 탭 → 그 장소 팝업 (셋)", opened == {p: p for p in PLACES}, opened)
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
        res = {p: popup(pg, p) for p in PLACES}
        C.check("빈 서버: 장소 셋 다 빈 상태 문구, 첫 줄 0", all(r["empty"] for r in res.values())
                and "골드 이동 0건" in res["gold"]["text"] and "새 이웃 0명" in res["welcome"]["text"] and "인용 사슬 0개" in res["rumor"]["text"],
                {p: (r["empty"], (r["stat"] or {}).get("text")) for p, r in res.items()})
        gm = ((S.get("/public/snapshot.json").json or {}).get("plaza") or {}).get("gold_moves")
        C.check("빈 서버: 스냅샷 gold_moves 는 빈 판(0·0·0·[])", gm == {"window_days": 7, "count": 0, "received": 0, "supply": 0, "rows": []}, str(gm))
        C.check("빈 서버: 페이지 오류 0", not errs, errs[:2])
        ctx.close()
    finally:
        S.stop()


def run_data(C: Checks) -> dict:
    """run_stage2 용: 브라우저 없이 공개 칸 판정만 (화면·팝업은 main 이 같이 돈다)"""
    S = Server()
    S.start()
    try:
        R = data.build(S)
        C.check("장소 셋 시나리오 완주", not R.fail, "; ".join(R.fail[:2]))
        data_checks(C, S, R)
    finally:
        S.stop()
    return {"checks": len(C.rows)}


def run(C: Checks, capture: Path | None = None) -> dict:
    from playwright.sync_api import sync_playwright
    S = Server()
    S.start()
    try:
        R = data.build(S)
        C.check("시나리오 + 골드·떠난 이웃 얹기 완주", not R.fail, "; ".join(R.fail[:2]))
        snap = data_checks(C, S, R)
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
    print(f"\n장소 셋: {len(C.rows) - len(C.failed)}/{len(C.rows)} 통과")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
