"""첫 방문 소개 영상 팝업 판정 (web/intro.js, 운영자 10-28). 헤드리스 Chrome 으로 첫 화면을 연다.

  python3 -m server.tests.intro_check [--url https://…] [--capture <폴더>]

--url 이 없으면 시험 서버(빈 광장)를 띄운다. 공개 주소에 대면 같은 판정 + 영상 응답(200·크기·형식·Range)을 본다.
영상 재생은 H.264 가 있어야 하므로 설치된 Chrome(channel=chrome)을 쓴다(Playwright 의 Chromium 은 H.264 가 없다).
자동화 브라우저에선 팝업이 저절로 안 뜨게 해 두었으므로(다른 화면 시험이 가리지 않게) 「사람」 판정은
navigator.webdriver 를 false 로 덮은 컨텍스트에서 한다.

판정
 1. 첫 방문(데스크톱): 대화상자가 뜨고 role=dialog·aria-modal·aria-label, 포커스는 닫기 버튼, 영상이 재생 중(무음)
    영상·포스터 요청은 팝업이 열린 뒤에만, 첫 화면 문서·스크립트 응답보다 늦게
 2. 닫기 ✕ → 사라지고 포커스는 「소개 영상」 링크, 저장소에 본 표시
 3. 재방문: 안 뜨고 영상·포스터 요청 0. 「소개 영상」 링크가 화면 구석에 있다
 4. 다시 보기: 링크 → 열림, Esc → 닫힘, 다시 열고 바깥 클릭 → 닫힘, 다시 열고 끝까지 → 저절로 닫힘. Tab 은 팝업 안에서 돈다
 5. 폰 세로(390×844): 대화상자·영상 칸이 화면 안, 가로 넘침 0, 영상 칸 16:9
 6. prefers-reduced-motion: 뜨지만 자동재생 안 함(멈춤 + 재생 버튼), 버튼을 누르면 재생
 7. 자동화 브라우저(webdriver=true): 저절로 안 뜬다
 8. 페이지 오류 0
 9. (--url) 영상 200·video/mp4·4~8MB, Range 206, 포스터 200·image/jpeg
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from .harness import Server

HUMAN = "Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => false});"
DESKTOP = {"viewport": {"width": 1440, "height": 900}}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
DLG = ".pz-promo [role=dialog]"


class Checks:
    def __init__(self):
        self.rows = []

    def check(self, group, name, ok, detail=""):
        self.rows.append((group, name, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {group} · {name}" + (f" — {detail}" if detail else ""), flush=True)
        return bool(ok)


STATE_JS = """() => {
  const d = document.querySelector('.pz-promo [role=dialog]'), v = d && d.querySelector('video');
  const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  return {open: !!d, role: d && d.getAttribute('role'), modal: d && d.getAttribute('aria-modal'), label: d && d.getAttribute('aria-label'),
          focus: document.activeElement && (document.activeElement.className || document.activeElement.id),
          paused: v ? v.paused : null, muted: v ? v.muted : null, t: v ? v.currentTime : null, err: v && v.error ? v.error.code : null,
          play: d ? !d.querySelector('.pz-promo-play').hidden : null, dlg: r(d), vid: r(d && d.querySelector('.pz-promo-v')),
          link: r(document.getElementById('pzIntroLink')), vw: innerWidth, vh: innerHeight,
          sw: document.documentElement.scrollWidth, seen: Object.keys(localStorage).filter((k) => k.startsWith('pz-intro-seen-'))};
}"""


def is_media(u: str) -> bool:
    return "/img/promo/plaza-promo-" in u


def inside(box, vw, vh) -> bool:
    return bool(box) and box[0] >= 0 and box[1] >= 0 and box[2] <= vw + 0.5 and box[3] <= vh + 0.5


def run(C: Checks, url: str, cap: Path | None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        errs = []

        def page(ctx):
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            return pg

        # 1~4 데스크톱, 한 컨텍스트(같은 저장소)에서 첫 방문 → 재방문
        G = "첫 방문"
        ctx = b.new_context(**DESKTOP)
        ctx.add_init_script(HUMAN)
        pg = page(ctx)
        log = []
        pg.on("request", lambda r: log.append(r.url))
        pg.goto(url + "/")
        pg.wait_for_selector(DLG, timeout=15000)
        pg.wait_for_function("() => { const v = document.querySelector('.pz-promo video'); return v && v.currentTime > 0.8; }", timeout=20000)
        s = pg.evaluate(STATE_JS)
        C.check(G, "대화상자가 뜸 · role=dialog · aria-modal · aria-label", s["open"] and s["role"] == "dialog" and s["modal"] == "true" and s["label"],
                f"{s['role']} {s['modal']} {s['label']}")
        C.check(G, "포커스가 닫기 버튼", s["focus"] == "pz-promo-x", s["focus"])
        C.check(G, "무음 자동재생 중", s["muted"] and not s["paused"] and s["t"] > 0.8 and s["err"] is None and not s["play"], f"t={s['t']:.2f} err={s['err']}")
        first_media = next((i for i, u in enumerate(log) if is_media(u)), None)
        js_i = next((i for i, u in enumerate(log) if "/web/intro.js" in u), None)
        C.check(G, "영상·포스터 요청은 intro.js 를 받은 뒤(첫 화면 로딩에 안 낌)", first_media is not None and js_i is not None and first_media > js_i,
                f"intro.js #{js_i}, 영상 #{first_media}")
        C.check(G, "저장소에 본 표시(키에 판번호)", s["seen"] == ["pz-intro-seen-v2"], s["seen"])
        if cap:
            pg.screenshot(path=str(cap / "intro_desktop_first.png"))

        G = "닫기"
        pg.click(".pz-promo-x")
        s = pg.evaluate(STATE_JS)
        C.check(G, "✕ → 사라짐 · 포커스는 「소개 영상」 링크", not s["open"] and s["focus"] in ("pz-promo-link", "pzIntroLink"), s["focus"])

        G = "재방문"
        log.clear()
        pg.reload()
        pg.wait_for_selector("#pzIntroLink")
        pg.wait_for_timeout(1500)
        s = pg.evaluate(STATE_JS)
        C.check(G, "안 뜸 · 영상/포스터 요청 0", not s["open"] and not [u for u in log if is_media(u)], [u for u in log if is_media(u)])
        lk = s["link"]
        C.check(G, "「소개 영상」 링크가 왼쪽 아래 구석", lk and lk[0] <= 20 and s["vh"] - lk[3] <= 20, lk)
        if cap:
            pg.screenshot(path=str(cap / "intro_desktop_revisit.png"))

        G = "다시 보기"
        pg.click("#pzIntroLink")
        pg.wait_for_selector(DLG)
        foc = [pg.evaluate("document.activeElement.className")]
        for _ in range(3):
            pg.keyboard.press("Tab")
            foc.append(pg.evaluate("document.activeElement.className"))
        C.check(G, "Tab 이 팝업 밖으로 안 나감", all(f.startswith("pz-promo") for f in foc), foc)
        pg.keyboard.press("Escape")
        C.check(G, "링크 → 열림, Esc → 닫힘", not pg.evaluate(STATE_JS)["open"])
        pg.click("#pzIntroLink")
        pg.wait_for_selector(DLG)
        pg.mouse.click(8, 8)
        C.check(G, "바깥 클릭 → 닫힘", not pg.evaluate(STATE_JS)["open"])
        pg.click("#pzIntroLink")
        pg.wait_for_function("() => { const v = document.querySelector('.pz-promo video'); return v && v.duration > 0; }", timeout=20000)
        pg.evaluate("() => { const v = document.querySelector('.pz-promo video'); v.currentTime = v.duration - 0.4; v.play(); }")
        pg.wait_for_function("() => !document.querySelector('.pz-promo')", timeout=10000)
        C.check(G, "끝까지 보면 저절로 닫힘", True)
        ctx.close()

        G = "폰 세로"
        ctx = b.new_context(**PHONE)
        ctx.add_init_script(HUMAN)
        pg = page(ctx)
        pg.goto(url + "/")
        pg.wait_for_selector(DLG, timeout=15000)
        pg.wait_for_timeout(1200)
        s = pg.evaluate(STATE_JS)
        v = s["vid"]
        ratio = (v[2] - v[0]) / (v[3] - v[1]) if v else 0
        C.check(G, "대화상자·영상 칸이 화면 안 · 가로 넘침 0 · 영상 칸 16:9",
                inside(s["dlg"], s["vw"], s["vh"]) and inside(v, s["vw"], s["vh"]) and s["sw"] <= s["vw"] and abs(ratio - 16 / 9) < 0.02,
                f"dlg={s['dlg']} vid={v} 비율={ratio:.3f} 화면={s['vw']}x{s['vh']}")
        x = pg.locator(".pz-promo-x").bounding_box()
        C.check(G, "닫기 버튼 44px 이상", x and x["width"] >= 44 and x["height"] >= 44, x)
        if cap:
            pg.screenshot(path=str(cap / "intro_phone_first.png"))
        pg.tap(".pz-promo-x")
        C.check(G, "탭으로 닫힘", not pg.evaluate(STATE_JS)["open"])
        ctx.close()

        G = "움직임 줄이기"
        ctx = b.new_context(**DESKTOP, reduced_motion="reduce")
        ctx.add_init_script(HUMAN)
        pg = page(ctx)
        pg.goto(url + "/")
        pg.wait_for_selector(DLG, timeout=15000)
        pg.wait_for_timeout(1500)
        s = pg.evaluate(STATE_JS)
        C.check(G, "뜨지만 자동재생 안 함(멈춤·재생 버튼)", s["open"] and s["paused"] and s["play"] and s["t"] == 0, f"paused={s['paused']} t={s['t']}")
        if cap:
            pg.screenshot(path=str(cap / "intro_reduced_motion.png"))
        pg.click(".pz-promo-play")
        pg.wait_for_function("() => document.querySelector('.pz-promo video').currentTime > 0.3", timeout=15000)
        C.check(G, "재생 버튼 → 재생", not pg.evaluate(STATE_JS)["paused"])
        ctx.close()

        G = "자동화 브라우저"
        ctx = b.new_context(**DESKTOP)
        pg = page(ctx)
        pg.goto(url + "/")
        pg.wait_for_selector("#pzIntroLink")
        pg.wait_for_timeout(1500)
        C.check(G, "webdriver=true 면 저절로 안 뜸(다른 화면 시험·검색 렌더 보호)", not pg.evaluate(STATE_JS)["open"])
        ctx.close()

        C.check("오류", "페이지 오류 0", not errs, errs[:3])
        b.close()


def media_checks(C: Checks, url: str):
    G = "영상 응답"
    req = urllib.request.Request(url + "/img/promo/plaza-promo-v2-720p.mp4", method="HEAD", headers={"User-Agent": "Mozilla/5.0 intro_check"})
    with urllib.request.urlopen(req, timeout=20) as r:
        n = int(r.headers.get("Content-Length") or 0)
        C.check(G, "영상 200 · video/mp4 · 4~8MB", r.status == 200 and r.headers.get_content_type() == "video/mp4" and 4e6 <= n <= 8e6,
                f"{r.status} {r.headers.get_content_type()} {n}B cf-cache={r.headers.get('cf-cache-status')}")
    req = urllib.request.Request(url + "/img/promo/plaza-promo-v2-720p.mp4", headers={"User-Agent": "Mozilla/5.0 intro_check", "Range": "bytes=0-1023"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
        C.check(G, "Range → 206 · 1024B · 앞 상자 ftyp 다음 moov(faststart)", r.status == 206 and len(body) == 1024 and body[4:8] == b"ftyp" and b"moov" in body[:64],
                f"{r.status} {r.headers.get('Content-Range')}")
    req = urllib.request.Request(url + "/img/promo/plaza-promo-v2-poster.jpg", method="HEAD", headers={"User-Agent": "Mozilla/5.0 intro_check"})
    with urllib.request.urlopen(req, timeout=20) as r:
        C.check(G, "포스터 200 · image/jpeg", r.status == 200 and r.headers.get_content_type() == "image/jpeg", r.headers.get("Content-Length"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--capture")
    a = ap.parse_args()
    cap = Path(a.capture).expanduser() if a.capture else None
    if cap:
        cap.mkdir(parents=True, exist_ok=True)
    C = Checks()
    S = None
    try:
        if a.url:
            url = a.url.rstrip("/")
        else:
            S = Server().start()
            url = S.url
        media_checks(C, url)
        run(C, url, cap)
    finally:
        if S:
            S.stop()
    bad = [r for r in C.rows if not r[2]]
    print(f"intro_check: {len(C.rows) - len(bad)}/{len(C.rows)} 통과")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
