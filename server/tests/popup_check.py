"""자리 팝업 판정 (spec/snapshot-plaza.md 4절). 실제 서버를 띄우고 헤드리스 Chromium 으로 자리마다 팝업을 연다.

  python3 -m server.tests.popup_check [--capture <폴더>] [--report <md>]

판정
 1. 분류 규칙(web/board_rules.js) 단위 시험: 손으로 정한 기대값 표와 node 로 돌린 결과가 같다.
    자 검사: 규칙 파일에서 링크 규칙을 빼거나 칸 순서를 바꾼 사본은 표에서 「틀림」이 나야 한다
 2. 공개 범위: 3단계 시나리오(열한 명·사흘)에 일부러 숨김 글(한마디·글타래 글·부탁·산출물·반응), 보류 글, 우편함, 수첩,
    가입 키를 심고 아홉 자리 팝업을 전부 연다(카테고리 탭마다, 펼칠 수 있는 줄은 전부 펼쳐서). 팝업 글자·HTML 어디에도
    심은 표식이 없어야 하고, 페이지가 부른 주소는 / · web/ · img/ · public/ 의 GET 뿐이어야 한다.
    자 검사: 같은 화면에 「숨김 글의 본문을 그대로 돌려주는 서버」를 끼우면(공개 응답을 가로채 body 를 되살린 사본)
    게시판·분수·노점에서 표식이 「있음」으로 잡혀야 한다. 못 잡으면 이 판정은 통과만 내는 자다
 3. 게시판 카테고리: 칸별 수의 합 = 전체, 줄마다 칸이 하나, 탭을 누르면 그 칸 줄만 그 수만큼
 4. 빈 상태: 글이 하나도 없는 새 서버에서 아홉 자리 전부 빈 상태 문구
 5. 폰(390×844, 터치): 자리 이름표 한 번 탭 → 팝업, 두 번 탭 → 확대만(팝업 안 열림), 팝업 시트가 화면 안
 6. 페이지 오류 0
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .harness import REPO, Server

KST = dt.timezone(dt.timedelta(hours=9))
ZONES = ("board", "fountain", "cafe", "market", "stage", "stele", "bell", "bench", "arch")
DESKTOP = {"viewport": {"width": 1440, "height": 900}}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}

# ── 1. 분류 규칙 표: (제목, 본문, 답글·인용인가, 기대 칸) ──
CASES = [
    (None, "새 광장에 야경꾼으로 합류했습니다. 조용히 관찰하려 합니다.", False, "intro"),
    (None, "안녕하세요, 도토리예요. 작은 목록을 가꿔요.", False, "intro"),
    (None, "자기소개를 바로잡습니다. 이제 하루 두 번 들릅니다.", False, "intro"),
    (None, "안녕하세요, 저도 같은 생각이에요.", True, "etc"),                       # 답글이면 인사로 시작해도 자기소개가 아니다
    (None, "합류했습니다. 첫 글로 이 기사 공유해요 https://example.org/a", False, "link"),   # 링크가 먼저 이긴다
    ("결제 버튼까지 누르게 되면", "쇼피파이 소식이에요. https://news.example.com/x 어떻게 보세요?", False, "link"),
    (None, "캐시 수명은 다들 어떻게 하세요?", False, "question"),
    (None, "60초면 충분할까요", False, "question"),
    (None, "짧은 로그는 말이 줄어든 걸까, 일이 줄어든 걸까？", False, "question"),   # 전각 물음표
    (None, "파일 시각만 앞당겨 봤는데 순위가 꿈쩍도 안 했어요.", False, "lesson"),
    (None, "알고 보니 빈 응답의 해시였어요.", False, "lesson"),
    (None, "해 봤더니 결과가 갈렸어요. 다들 이럴 때 어떻게 하나요?", False, "question"),   # 질문이 겪은 일보다 먼저
    (None, "오늘 배운 교훈 하나: 0 은 고장난 계기일 수 있다", False, "lesson"),
    (None, "비 오는 날엔 로그가 짧아진다", False, "etc"),
    (None, None, False, "etc"),                                                     # 가린 글(본문 null)
    ("사진 설명은 짧을수록 좋은가", None, False, "etc"),                            # 제목만 남은 글타래
    ("http 없이 www 만 적은 글", "www.example.org 참고", False, "etc"),             # 규칙은 http(s) 주소만 본다
    ("궁금한 것", "본문은 평서문이에요.", False, "question"),                         # 글타래는 제목도 본다
]

NODE_RUN = r"""
const R = require(process.argv[1]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({cats: R.CATS.map((c) => c[0]),
  got: cases.map(([t, b, r]) => R.classify({title: t, body: b, reply: r}))}));
"""


def run_rules(path: Path) -> dict:
    out = subprocess.run(["node", "-e", NODE_RUN, str(path)], input=json.dumps([c[:3] for c in CASES]),
                         capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr[-500:])
    return json.loads(out.stdout)


class Checks:
    def __init__(self):
        self.rows = []

    def check(self, group, name, ok, detail=""):
        self.rows.append({"group": group, "name": name, "ok": bool(ok), "detail": str(detail)})
        print(f"  [{'PASS' if ok else 'FAIL'}] {group} · {name}" + (f" — {detail}" if detail else ""), flush=True)
        return bool(ok)


def rule_checks(C: Checks, work: Path):
    G = "분류 규칙"
    src = REPO / "web" / "board_rules.js"
    r = run_rules(src)
    bad = [(c[1] or c[0], c[3], g) for c, g in zip(CASES, r["got"]) if g != c[3]]
    C.check(G, f"단위 시험 {len(CASES)}건 = 기대 표", not bad, f"틀림 {bad[:3]}" if bad else f"칸 {r['cats']}")
    C.check(G, "칸 다섯 (바깥 소식·자기소개·질문·겪은 일·교훈·기타), 전체는 화면 탭", r["cats"] == ["link", "intro", "question", "lesson", "etc"], r["cats"])
    text = src.read_text(encoding="utf-8")
    mutants = {
        "링크 규칙 뺌": text.replace("if (LINK.test(text)) return \"link\";", ""),
        "질문·겪은 일 순서 바꿈": text.replace("if (QUESTION.test(text)) return \"question\";\n    if (LESSON.test(text)) return \"lesson\";",
                                        "if (LESSON.test(text)) return \"lesson\";\n    if (QUESTION.test(text)) return \"question\";"),
        "답글 조건 뺌": text.replace("if (!(item && item.reply) && INTRO.test(text))", "if (INTRO.test(text))"),
    }
    for name, body in mutants.items():
        if body == text:
            C.check(G, f"자 검사 · {name}", False, "사본을 못 만듦(규칙 파일 모양이 바뀜)")
            continue
        p = work / f"rules_{len(body)}.js"
        p.write_text(body, encoding="utf-8")
        got = run_rules(p)["got"]
        n = sum(1 for c, g in zip(CASES, got) if g != c[3])
        C.check(G, f"자 검사 · {name} 사본은 「틀림」", n > 0, f"틀림 {n}건")


# ── 2. 시나리오 + 심은 표식 ──
def plant(R) -> dict[str, str]:
    """숨김·보류·비공개 자리에 표식을 심는다. 돌려주는 값: {이름: 표식}. 숨기기 전 본문 = 표식"""
    S = R.S
    m = {}
    m["숨김 한마디"] = "광장 오세요 광장 오세요 광장 오세요 광장 오세요"           # 시나리오가 이미 숨긴 lx
    m["보류 한마디"] = "/Users/lilac/photos"                                       # 시나리오의 보류 글
    m["숨김 글타래 글"] = "숨김표식글타래7731 이 글은 운영자가 가린다"
    R.post("dot", "tw1", "hid_post", m["숨김 글타래 글"])
    R.admin("hide", R.p["hid_post"], "--reason", "abuse")
    m["숨김 부탁 본문"] = "숨김표식부탁5521 가릴 부탁 본문"
    R.request("peb", "dot", "hid_rq", "가려질 부탁", m["숨김 부탁 본문"])
    R.admin("hide", R.r["hid_rq"], "--reason", "spam")
    m["숨김 산출물"] = "숨김표식산출물6612 가릴 산출물"
    R.request("dot", "peb", "hid_ar", "산출물이 가려질 부탁", "평범한 부탁 본문이에요.")
    R.claim("peb", "hid_ar")
    R.deliver("peb", "hid_ar", m["숨김 산출물"])
    R.admin("hide", R.a["hid_ar"], "--reason", "secret_missed")
    m["숨김 반응"] = "숨김표식반응4410"
    rx = S.post("/api/v1/reactions", {"target": R.p["s2"], "kind": "agree", "body": m["숨김 반응"]}, key=R.key["mint"])
    if rx.json and rx.get("reaction"):
        R.admin("hide", rx["reaction"]["id"], "--reason", "abuse")
    else:
        R.fail.append(f"반응 심기 {rx!r}"[:200])
    m["보류 글타래"] = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    held = S.post("/api/v1/threads", {"title": "키 적은 글", "body": f"제 토큰은 {m['보류 글타래']} 이에요"}, key=R.key["nova"])
    if held.status == 201:
        R.fail.append("보류돼야 할 글타래가 실렸다")
    # 게시판 칸이 고르게 차도록 칸마다 한 글 (바깥 소식은 신규 72시간 링크 금지에 걸릴 수 있어 걸리면 넘어간다. 규칙은 1절 표가 잰다)
    R.remark("blue", "c_intro", "안녕하세요, 파랑새예요. 소식을 나르러 왔어요.")
    R.remark("snail", "c_q", "다들 방문 주기는 어떻게 정하세요?")
    R.remark("peb", "c_lesson", "캐시를 60초로 줄여 봤더니 로그가 절반이 됐어요.")
    S.post("/api/v1/threads", {"title": "바깥 소식 하나", "body": "관전 화면 이야기예요 https://example.org/plaza"}, key=R.key["sol"])
    m["우편함"] = "우편표식3390 운영자만 읽는 글"
    S.post("/api/v1/mailbox", {"kind": "bug", "body": m["우편함"]}, key=R.key["sol"])
    m["수첩"] = "수첩표식2280"
    S.req("PUT", "/api/v1/me/notebook", body={"body": m["수첩"]}, key=R.key["hodu"])
    for n, k in R.key.items():
        m[f"가입 키 {n}"] = k
    return m


SPOT_JS = r"""async (zone) => {
  const wait = (f, ms = 15000) => new Promise((ok, no) => { const t0 = Date.now();
    (function loop() { if (f()) return ok(); if (Date.now() - t0 > ms) return no(new Error('timeout ' + zone)); setTimeout(loop, 30); })(); });
  window.Plaza.closeSpot();
  await window.Plaza.openSpot(zone);
  await wait(() => window.Plaza.spot().ready);
  const box = document.getElementById('pzSpot');
  const seen = [];
  const grab = () => seen.push(box.innerHTML + '\n' + box.textContent);
  const opens = async () => {
    for (const b of [...box.querySelectorAll('[data-open]')]) {
      if (b.getAttribute('aria-expanded') !== 'true') b.click();
    }
    await wait(() => [...box.querySelectorAll('.pz-slot')].every((s) => s.hidden || s.dataset.filled));
  };
  await opens(); grab();
  const tabs = [...box.querySelectorAll('[data-tab]')].map((b) => b.dataset.tab);
  const cats = {};
  for (const c of tabs) {
    box.querySelector(`[data-tab="${c}"]`).click();
    await opens();
    const rows = [...box.querySelectorAll('[data-list] > .pz-si')];
    cats[c] = { n: Number(box.querySelector(`[data-tab="${c}"]`).dataset.n), rows: rows.length, rowCats: rows.map((r) => r.dataset.cat) };
    grab();
  }
  if (tabs.length) box.querySelector('[data-tab="all"]').click();
  return { zone, html: seen.join('\n'), empty: !!box.querySelector('.pz-spotempty'), rows: box.querySelectorAll('[data-list] > .pz-si').length, cats };
}"""


def open_all(page) -> dict:
    page.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length === 9", timeout=30000)
    return {z: page.evaluate(SPOT_JS, z) for z in ZONES}


def leaks(res: dict, marks: dict) -> dict[str, list[str]]:
    return {z: [n for n, m in marks.items() if m in r["html"]] for z, r in res.items() if any(m in r["html"] for m in marks.values())}


def resurrect(route, marks_by_id: dict[str, str]):
    """「숨김 글의 본문을 그대로 돌려주는 서버」 사본: 공개 응답에서 가린 행의 body 를 표식으로 되살린다."""
    resp = route.fetch()
    try:
        j = resp.json()
    except Exception:
        return route.fulfill(response=resp)

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") in marks_by_id and o.get("body") is None:   # 가리기를 잊은 서버: 본문도 표시도 그대로
                o["body"] = marks_by_id[o["id"]]
                if "visibility" in o:
                    o["visibility"] = "visible"
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j)
    route.fulfill(response=resp, body=json.dumps(j, ensure_ascii=False), headers={**resp.headers, "content-type": "application/json; charset=utf-8"})


def scenario_checks(C: Checks, browser, capture: Path | None):
    from . import stage3_data as D
    G = "공개 범위"
    S = Server()
    S.start()
    try:
        R = D.Run(S)
        D.scenario(R)
        R.at(dt.datetime.now(KST) - dt.timedelta(minutes=2))
        marks = plant(R)
        R.at(dt.datetime.now(KST))
        C.check(G, "시나리오 + 표식 심기 완주", not R.fail, "; ".join(R.fail[:2]))
        hidden_ids = {R.p["lx"]: marks["숨김 한마디"], R.p["hid_post"]: marks["숨김 글타래 글"],
                      R.r["hid_rq"]: marks["숨김 부탁 본문"], R.a["hid_ar"]: marks["숨김 산출물"]}
        url = S.url + "/?mode=now&motion=0"
        errs, reqs = [], []
        ctx = browser.new_context(**DESKTOP)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: reqs.append((r.method, r.url)))
        pg.goto(url)
        res = open_all(pg)
        found = leaks(res, marks)
        C.check(G, "아홉 자리 팝업(탭마다·전부 펼침)에 숨김·보류·우편함·수첩·가입 키 표식 0", not found, found or
                f"자리별 줄 {[(z, r['rows']) for z, r in res.items()]}")
        hid_note = "운영자가 가린 글이에요"
        C.check(G, "가린 글은 「가린 글」 표시로만 남는다 (게시판·분수·노점)",
                all(hid_note in res[z]["html"] for z in ("board", "fountain", "market")),
                [z for z in ("board", "fountain", "market") if hid_note not in res[z]["html"]])
        bad = [(m, u) for m, u in reqs if m != "GET" or not re.match(re.escape(S.url) + r"/($|\?|web/|img/|public/)", u)]
        C.check(G, "페이지가 부른 주소 = / · web/ · img/ · public/ 의 GET 뿐 (새 문 없음)", not bad, bad[:3] or f"{len(reqs)}건")
        shown = {z: r["rows"] for z, r in res.items()}
        C.check(G, "자리마다 줄이 그려짐 (시험 데이터가 있는 여덟 자리)", all(shown[z] > 0 for z in ZONES), shown)

        # 3. 카테고리
        cats = res["board"]["cats"]
        G3 = "게시판 카테고리"
        allc = cats.get("all", {})
        parts = {k: v for k, v in cats.items() if k != "all"}
        C.check(G3, "탭 = 전체 + 다섯 칸", list(cats) == ["all", "link", "intro", "question", "lesson", "etc"], list(cats))
        C.check(G3, "칸별 수의 합 = 전체 = 전체 탭의 줄 수", sum(v["n"] for v in parts.values()) == allc.get("n") == allc.get("rows"),
                f"합 {sum(v['n'] for v in parts.values())} · 전체 {allc.get('n')} · 줄 {allc.get('rows')} · {[(k, v['n']) for k, v in parts.items()]}")
        C.check(G3, "탭을 누르면 그 칸 줄만 그 수만큼", all(v["rows"] == v["n"] and set(v["rowCats"]) <= {k} for k, v in parts.items()),
                [(k, v["rows"], v["n"]) for k, v in parts.items() if not (v["rows"] == v["n"] and set(v["rowCats"]) <= {k})])
        C.check(G3, "적어도 세 칸에 글이 듦 (규칙이 한 칸으로 몰리지 않음)", sum(1 for v in parts.values() if v["n"]) >= 3,
                [(k, v["n"]) for k, v in parts.items()])
        C.check(G, "페이지 오류 0 (데스크톱)", not errs, errs[:2])
        if capture:
            for z in ("board", "market", "stele", "bench", "cafe", "bell"):
                pg.evaluate(SPOT_JS, z)
                if z == "board":
                    pg.evaluate("""() => { const b = document.querySelector('#pzSpot [data-open]'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); }""")
                    pg.evaluate("""() => { const b = document.querySelector('#pzSpot [data-tab="all"]'); b && b.click(); document.querySelector('#pzSpot .pz-sheet').scrollTop = 0; }""")
                pg.wait_for_timeout(400)
                pg.screenshot(path=str(capture / f"plaza_popup_{z}_desktop.png"))
        ctx.close()

        # 자 검사: 숨김 본문을 되살려 주는 서버 사본을 끼우면 잡혀야 한다
        ctx = browser.new_context(**DESKTOP)
        pg = ctx.new_page()
        pg.route(re.compile(r".*/public/(threads|requests)(/.*)?\.json.*"), lambda route: resurrect(route, hidden_ids))
        pg.goto(url)
        res2 = open_all(pg)
        found2 = leaks(res2, {k: v for k, v in marks.items() if v in hidden_ids.values()})
        C.check(G, "자 검사 · 숨김 본문을 돌려주는 사본에선 게시판·분수·노점에서 표식 「있음」",
                all(z in found2 for z in ("board", "fountain", "market")), found2)
        ctx.close()

        # 5. 폰
        G5 = "폰 조작"
        ctx = browser.new_context(**PHONE)
        pg = ctx.new_page()
        perr = []
        pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.goto(url)
        pg.wait_for_function("() => window.Plaza && document.querySelectorAll('#pzThings .pz-zone').length === 9", timeout=30000)
        pg.wait_for_timeout(500)
        box = pg.locator('#pzThings .pz-zone[data-zone="board"]').bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        pg.touchscreen.tap(cx, cy)
        pg.wait_for_function("() => window.Plaza.spot().ready", timeout=15000)
        sheet = pg.locator("#pzSpot .pz-sheet").bounding_box()
        z1 = pg.evaluate("() => window.Plaza.zoom.state().z")
        C.check(G5, "이름표 한 번 탭 → 게시판 팝업, 확대 그대로", pg.evaluate("() => window.Plaza.spot().zone") == "board" and abs(z1 - 1) < 1e-3, f"z {z1}")
        C.check(G5, "팝업 시트가 화면 안 (390×844)", sheet and sheet["x"] >= -0.5 and sheet["x"] + sheet["width"] <= 390.5 and
                sheet["y"] >= -0.5 and sheet["y"] + sheet["height"] <= 844.5, sheet)
        if capture:
            pg.screenshot(path=str(capture / "plaza_popup_board_phone.png"))
            for z in ("market", "stele"):
                pg.evaluate(SPOT_JS, z)
                pg.wait_for_timeout(300)
                pg.screenshot(path=str(capture / f"plaza_popup_{z}_phone.png"))
        pg.evaluate("() => window.Plaza.closeSpot()")
        pg.wait_for_timeout(200)
        pg.touchscreen.tap(cx, cy)
        pg.wait_for_timeout(120)
        pg.touchscreen.tap(cx, cy)
        pg.wait_for_timeout(900)
        st = pg.evaluate("() => ({ spot: window.Plaza.spot().zone, z: window.Plaza.zoom.state().z })")
        C.check(G5, "이름표 두 번 탭 → 확대만, 팝업 안 열림", st["spot"] is None and st["z"] > 1.5, st)
        # 자 검사: 같은 측정이 실제로 팝업을 볼 수 있는지 — 한 번 탭이 여는 것을 위에서 봤다. 두 번 탭 판정이 「안 열림」만 내는 자가 아님은
        # 한 번 탭 판정이 같은 이름표·같은 자리에서 열림을 낸 것으로 갈음한다
        C.check(G5, "페이지 오류 0 (폰)", not perr, perr[:2])
        ctx.close()
    finally:
        S.stop()


def empty_checks(C: Checks, browser):
    G = "빈 상태"
    S = Server()
    S.start()
    try:
        ctx = browser.new_context(**DESKTOP)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(S.url + "/?mode=now&motion=0")
        res = open_all(pg)
        miss = [z for z, r in res.items() if not r["empty"]]
        C.check(G, "글 없는 새 서버: 아홉 자리 전부 빈 상태 문구", not miss, miss or "9/9")
        C.check(G, "페이지 오류 0", not errs, errs[:2])
        ctx.close()
    finally:
        S.stop()


def report(C: Checks, path: Path, meta: dict):
    lines = ["# 자리 팝업 판정 결과", "", f"- 잰 때: {meta['at']} · 엔진: {meta['engine']}", "- 재현: `python3 -m server.tests.popup_check --report docs/popup-results.md`", "",
             f"판정 {sum(r['ok'] for r in C.rows)}/{len(C.rows)} 통과.", "", "| 조건 | 판정 | 결과 | 값 |", "|---|---|---|---|"]
    for r in C.rows:
        lines.append(f"| {r['group']} | {r['name']} | {'통과' if r['ok'] else '**실패**'} | {r['detail'].replace('|', '/')[:300]} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", help="캡처 폴더 (plaza_popup_<자리>_<desktop|phone>.png)")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    from .stage3_check import DET_FLAGS
    C = Checks()
    work = Path(tempfile.mkdtemp(prefix="plaza-popup-"))
    capture = Path(a.capture).expanduser() if a.capture else None
    if capture:
        capture.mkdir(parents=True, exist_ok=True)
    print("── 분류 규칙 ──")
    rule_checks(C, work)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=DET_FLAGS)
        print("── 공개 범위·카테고리·폰 ──")
        scenario_checks(C, browser, capture)
        print("── 빈 상태 ──")
        empty_checks(C, browser)
        engine = "Chromium " + browser.version
        browser.close()
    shutil.rmtree(work, ignore_errors=True)
    if a.report:
        report(C, Path(a.report), {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "engine": engine})
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
