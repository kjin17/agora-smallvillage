"""3단계 완료 조건 판정 (PLAN 7절 3단계, 독립 렌더러 판). 헤드리스 Chromium 으로 실제 화면을 띄워 잰다.

  python3 -m server.tests.stage3_check --data <stage3_data 출력 폴더> --work <작업 폴더>
         [--office <원본 렌더러 리포> --office-base <커밋>] [--report docs/stage3-results.md] [--compare <비교 캡처.png>]

화면은 리포 web/ 을 서버와 같은 주소 모양(/ · web/ · img/ · public/)으로 정적 사본에 올려 찍는다.

판정
 0. 별개 프로젝트: 광장 리포에 원본 렌더러(걷기·말풍선 코드를 복사해 온 다른 리포)로 가는 링크·서브모듈이 없고,
    화면이 부르는 주소는 web/·img/·public/ 뿐. --office 를 주면 그 리포 작업 트리·origin/main 이 --office-base 와 diff 0 인지도 본다
 1. 폰 폭(390×844, iPhone 13)에서 첫 화면에 광장 그림 전체(장면 상자 = 틀 상자, 뷰포트 안)가 들어오고, 핀치·한 손가락
    끌기·두 번 탭·+ − 전체 보기 버튼으로 확대/축소·이동이 된다. 확대 1~4배, 가장자리 밖이 안 보임, 확대·이동 뒤 말풍선 수와
    장면 좌표 자리 불변, 확대한 채 연출 켬·끔·리플레이 끝까지. 전체 보기에서는 휠·세로 스크롤을 페이지에 넘긴다.
    Chromium 모바일 에뮬레이션과 WebKit(iPhone 13, 깔려 있으면) 두 벌. (앞 판은 폰에서 「구역 넷」만 잘라 그렸다)
 2. 연출을 끄면 말풍선 수 불변: 「지금」 화면의 말풍선 수, 리플레이 하루치를 끝까지 돌린 말풍선 수를 연출 켬·끔으로 각각 세서
    서로 같고 리플레이 파일의 counts.bubbles(원장 공개 행 수)와 같아야 한다. 장면 자동 일시정지, 60× 버튼의 실제 배속
 3. 앞 판 흠: 광장 아래 프레임 밖 활동 막대 없음, 장면 카드 조사가 받침에 맞음, 배속 버튼 1×·16×·60×
 4. 결정성: 같은 스냅샷·같은 시각이면 같은 그림(연출 끔). 서버가 내보낸 코드 = 리포 web/
 5. 페이지 오류 0
 6. 대화 보기: 말풍선 = 그 원장 행의 공개 본문 앞 16자, 「최근 이야기」에 지난 24시간 글 행 전부가
    글자 그대로(줄바꿈·이모지), 답글·인용 연결, 말 없이 다녀간 방문은 「한 말 없음」, 캐릭터를 누르면 agents/{id}.json 글 전문,
    두 번 탭은 확대만, 본문은 textContent 로만(태그 글자가 요소가 되지 않음), 보류된 글은 어디에도 없음. 폰 두 엔진·데스크톱
 7. 캐릭터가 시설 앞에: 시설 아홉 곳 발끝 바로 위에 세워 몸·발·말풍선이 맨 위, 캐릭터끼리는 발 y 순서
 8. 리플레이 타임라인 글자: 광장·계기판 막대의 시각 눈금·장면 깃발·재생 표시가 가로/세로 배율 1(눌림 없음), 눈금끼리·깃발끼리
    안 겹치고 막대 안. 폰 두 엔진·데스크톱. (앞 판은 viewBox 1510 을 비율 무시로 폰 폭에 담아 글자가 가로로 약 1/4)
 9. 아바타 표정(docs/faces.md): 규칙표(web/faces.json)를 파이썬으로 따로 적용한 기대값과 화면의 표정이 같다. 지금 화면(시험 데이터),
    스냅샷 칸만으로(원장 행을 못 찾을 때), 리플레이 시각별(모든 규칙을 지나는 지어낸 하루 + 시험 데이터 날마다), 모르는 종류 → 기본 그림,
    떠난 이웃 → 기본 그림. 불러온 표정 그림 = 화면에 보이는 것뿐. 그림 파일은 메타데이터 청크 0

통과만 내는 자가 되지 않게 판정마다 자 검사를 둔다: diff 0 은 한 커밋 앞에 대면 「다름」, 픽셀 비교는
생성 시각 1분 차이를 「다름」, 활동 막대 검사는 원본 렌더러의 옛 활동 막대를 끼워 넣으면 「있음」, 조사 검사는 「라일락가」를 「틀림」,
전체 보기 검사는 2배 첫 화면·옛 구역 넷 자르기를 「전체 아님」, 가장자리 검사는 40px 밀린 장면을 「밖」, 말풍선 수는 틀 안만 세면 「다름」,
말풍선 글은 17자로 자르면 「틀림」, 표정은 규칙표를 바꾼 기대값·표정 앞 판을 「틀림」, EXIF 를 붙인 WebP 를 「그림 아닌 청크」, 같은 글자를 innerHTML 로 넣으면 「요소 생김」, 보류 글자를 화면에 넣으면 「있음」,
옛 층 순서(한 층, 발 y 만)로 되돌리면 겹친 시설마다 「뒤로 들어감」, 타임라인은 앞 판 모양 글자를 끼우면 「눌림」.
픽셀 비교는 결정적 래스터 깃발(DET_FLAGS)로 찍고 대조군(같은 입력 두 번)을 판정마다 같이 적는다."""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import http.server
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from server.plaza.util import has_batchim

REPO = Path(__file__).resolve().parents[2]
KST = dt.timezone(dt.timedelta(hours=9))
WEB_FILES = ("index.html", "plaza.js", "plaza.css", "faces.json", "board_rules.js")
WEB_CODE = WEB_FILES[1:]   # 서버 판번호 = 이 순서로 이은 내용의 해시 (server/plaza/app.py WEB_CODE)
# 「전」 판(옛 plaza.js·plaza.css)은 공개 리포 첫 커밋 이전 커밋이라 이 리포 이력에 없다 → 고정 파일로 둔다
BEFORE_DIR = REPO / "server" / "tests" / "fixtures" / "stage3_before"


def before_web(ref: str, name: str) -> str:
    """옛 판 web/<name> 내용. ref 가 폴더면 그 안의 파일, 아니면 이 리포의 커밋으로 읽는다."""
    d = Path(ref).expanduser()
    if d.is_dir():
        return (d / name).read_text(encoding="utf-8")
    return subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:web/{name}"],
                          capture_output=True, text=True, check=True).stdout


def before_label(ref: str) -> str:
    """판정 이름에 쓸 짧은 이름. 폴더면 끝의 커밋 꼬리(faces_b0af64d → b0af64d) — 보고서에 로컬 경로를 남기지 않는다."""
    d = Path(ref).expanduser()
    return d.name.rsplit("_", 1)[-1] if d.is_dir() else ref
# 기본 Chromium 은 같은 코드·같은 입력도 8쌍 중 4쌍이 수십 픽셀 다르게 찍었다(GPU 래스터·LCD 글자). 이 깃발로 0/8.
# 대조군(같은 입력 두 번)도 같이 찍어, 「동일」이 캡처 잡음에 가려지지 않았음을 판정마다 보인다
DET_FLAGS = ["--force-color-profile=srgb", "--disable-gpu", "--disable-lcd-text", "--disable-partial-raster",
             "--disable-skia-runtime-opts", "--font-render-hinting=none",
             "--disable-checker-imaging"]   # 09-26 대화 보기: 그림 수십 장이 늘자 비동기 그림 풀기가 몇 점씩 흔들렸다(아래 still 의 기다림과 함께 8/8)

# 광장 페이지 안에서 「프레임 밖 활동 막대」를 찾는다: #plaza 밖에 보이는 요소가 있거나, 활동 띠 모양(원본 렌더러 .strip)이
# 있거나, 「지난 24시간 활동/행동」 제목이 계기판·날씨 칸 밖에 있으면 걸린다
STRAY_JS = r"""() => {
  const out = [];
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  for (const el of document.body.children) {
    if (el.id === 'plaza' || ['SCRIPT', 'NOSCRIPT', 'STYLE'].includes(el.tagName)) continue;
    if (vis(el)) out.push('body>' + el.tagName.toLowerCase() + (el.className ? '.' + el.className : ''));
  }
  document.querySelectorAll('.strip, #strip, .strip-wrap, #activityLabel').forEach((el) => { if (vis(el)) out.push('strip:' + (el.id || el.className)); });
  const ok = (el) => el.closest('.pz-aside, .pz-weather, .pz-dash, .pz-kpis');
  document.querySelectorAll('h1,h2,h3,h4,div,span,p').forEach((el) => {
    if (el.children.length === 0 && /지난 24시간 (활동|행동)/.test(el.textContent) && vis(el) && !ok(el)) out.push('title:' + el.textContent.trim().slice(0, 30));
  });
  return out;
}"""
OLD_STRIP = ("() => { const f = document.createElement('footer'); f.className = 'foot';"
             "f.innerHTML = '<div class=\"card strip-wrap\"><h3 id=\"activityLabel\">지난 24시간 행동</h3><div class=\"strip\" id=\"strip\" style=\"height:60px\"></div></div>';"
             "document.body.appendChild(f); }")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(root: Path) -> tuple[str, http.server.ThreadingHTTPServer]:
    h = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", srv


class Checks:
    def __init__(self):
        self.rows = []

    def check(self, group, name, ok, detail=""):
        self.rows.append({"group": group, "name": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {group} · {name}" + (f" — {detail}" if detail else ""), flush=True)
        return ok


def plaza_site(dst: Path, data: Path, snap: dict | None = None) -> Path:
    """서버와 같은 주소 모양의 정적 사본: / · web/ · img/(링크) · public/."""
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "web").mkdir(parents=True)
    shutil.copy(REPO / "web" / "index.html", dst / "index.html")
    for f in WEB_CODE:
        shutil.copy(REPO / "web" / f, dst / "web" / f)
    (dst / "img").symlink_to(REPO / "images" / "gemini")
    shutil.copytree(data, dst / "public")
    if snap is not None:
        (dst / "public" / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return dst


def same_pixels(a: Path, b: Path) -> tuple[bool, str]:
    A, B = Image.open(a).convert("RGBA"), Image.open(b).convert("RGBA")
    if A.size != B.size:
        return False, f"크기 다름 {A.size} vs {B.size}"
    # RGBA 차이 그림의 getbbox() 는 알파만 본다(둘 다 불투명이면 늘 None). 색과 알파를 따로 잰다
    box = ImageChops.difference(A.convert("RGB"), B.convert("RGB")).getbbox() or \
        ImageChops.difference(A.getchannel("A"), B.getchannel("A")).getbbox()
    return box is None, ("동일 " + "x".join(map(str, A.size))) if box is None else f"다른 영역 {box}"


def josa_errors(text: str, nicks: list[str]) -> list[str]:
    """닉네임 바로 뒤의 이/가·와/과 가 받침과 맞는지. 틀린 곳 목록."""
    bad = []
    for n in sorted(nicks, key=len, reverse=True):
        for m in re.finditer(re.escape(n) + r"(이|가|와|과)(?=\s|$|[^가-힣])", text):
            j = m.group(1)
            want = {"이": True, "과": True, "가": False, "와": False}[j]
            if has_batchim(n) != want:
                bad.append(m.group(0))
    return bad


def office_refs(code: str) -> list[str]:
    """주석(/* */ · <!-- --> · 줄 끝 //)을 뺀 코드에서 원본 렌더러 파일·전역 이름을 찾는다."""
    code = re.sub(r"/\*.*?\*/|<!--.*?-->", "", code, flags=re.S)
    code = re.sub(r"(^|[\s;{}])//.*$", r"\1", code, flags=re.M)
    return re.findall(r"office\.(?:js|css)|office/site/|OakPlaza", code)


# ── 0. 별개 프로젝트 ──
def separate_checks(C: Checks, args):
    if args.office:
        office = Path(args.office).expanduser()
        base = args.office_base
        git = lambda *a: subprocess.run(["git", "-C", str(office), *a], capture_output=True, text=True)  # noqa: E731
        git("fetch", "-q", "origin")
        wt = git("diff", base).stdout
        staged = git("diff", "--cached", base).stdout
        remote = git("diff", base, "origin/main").stdout
        C.check("별개 프로젝트", f"원본 렌더러 리포 작업 트리·origin/main 이 {base} 와 diff 0",
                wt == "" and staged == "" and remote == "",
                f"작업 트리 {len(wt.splitlines())}줄 · 스테이지 {len(staged.splitlines())}줄 · origin/main {len(remote.splitlines())}줄 · "
                f"HEAD {git('rev-parse', '--short', 'HEAD').stdout.strip()}")
        # 자 검사: 한 커밋 앞과 대면 diff 가 0 이 아니어야 한다
        prev = git("rev-parse", "--short", f"{base}~1").stdout.strip()
        probe = git("diff", f"{base}~1", base).stdout
        C.check("별개 프로젝트", f"자 검사: {base}~1({prev}) 에 대면 「다름」", probe != "", f"{len(probe.splitlines())}줄")
    ls = subprocess.run(["git", "-C", str(REPO), "ls-files", "-s"], capture_output=True, text=True).stdout.splitlines()
    links = [l.split("\t")[1] for l in ls if l.startswith(("120000", "160000"))]
    refs = [f for f in WEB_FILES if office_refs((REPO / "web" / f).read_text(encoding="utf-8"))]
    C.check("별개 프로젝트", "광장 리포에 링크·서브모듈 없음, web/ 코드가 원본 렌더러 파일을 안 부름 (주석의 출처 표기는 뺌)",
            not links and not (REPO / ".gitmodules").exists() and not refs,
            f"링크·서브모듈 {links or 0} · 원본 렌더러 참조 {refs or 0}")
    probe = office_refs('<script src="office.js"></script>') + office_refs('s.src = "../office/site/plaza.js"; // x')
    C.check("별개 프로젝트", "자 검사: 원본 렌더러 파일을 부르는 줄을 「참조」로 잡는다", len(probe) == 2, ", ".join(probe))


# ── 1. 폰 폭 전체 보기·확대/축소·이동 (앞 판의 「구역 넷」 대신) ──
# 장면(#pzStage)·틀(#pzWrap) 상자, 뷰포트, 스크롤, 틀의 touch-action
BOX_JS = """() => { const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return {l: b.left, t: b.top, r: b.right, b: b.bottom}; };
  return {stage: r('#pzStage'), wrap: r('#pzWrap'), vw: innerWidth, vh: innerHeight, sy: scrollY,
          ta: getComputedStyle(document.getElementById('pzWrap')).touchAction}; }"""
# 말풍선마다 화면 상자 가운데를 장면 좌표로 되돌린 자리, 틀 안에 보이는지
BUBBLES_JS = """() => { const s = Plaza.stats().zoom, w = document.getElementById('pzWrap').getBoundingClientRect(), k = s.fit * s.z;
  return [...document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-bubble')].map((b) => { const r = b.getBoundingClientRect();
    return {id: b.closest('.pz-agent').dataset.id,
            x: s.cx + ((r.left + r.right) / 2 - w.left - 1376 * s.fit / 2) / k, y: s.cy + ((r.top + r.bottom) / 2 - w.top - 768 * s.fit / 2) / k,
            inView: r.right > w.left && r.left < w.right && r.bottom > w.top && r.top < w.bottom}; }); }"""
# 손가락 흉내: PointerEvent(touch) 를 누른 자리의 요소에 쏜다. 두 엔진 다 같은 처리기를 탄다
POINTER_JS = """(steps) => { window.__pt = window.__pt || {};
  for (const [type, id, x, y] of steps) {
    if (type === 'pointerdown') window.__pt[id] = document.elementFromPoint(x, y);
    window.__pt[id].dispatchEvent(new PointerEvent(type, {pointerId: id, pointerType: 'touch', isPrimary: id === 1,
      clientX: x, clientY: y, bubbles: true, cancelable: true, buttons: type === 'pointerup' ? 0 : 1}));
    if (type === 'pointerup') delete window.__pt[id];
  } }"""
PHONE_DEVICE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
ZOOM_MAX = 4


def full_view(b: dict) -> bool:
    """장면 상자 = 틀 상자(잘린 곳 없음)이고 뷰포트 안."""
    s, w = b["stage"], b["wrap"]
    same = all(abs(s[k] - w[k]) <= 1.5 for k in "ltrb")
    inside = s["l"] >= -1 and s["t"] >= -1 and s["r"] <= b["vw"] + 1 and s["b"] <= b["vh"] + 1
    return same and inside


def covers(b: dict) -> bool:
    """확대한 장면이 틀을 다 덮는다(가장자리 밖 빈 곳이 안 보임)."""
    s, w = b["stage"], b["wrap"]
    return s["l"] <= w["l"] + 1 and s["t"] <= w["t"] + 1 and s["r"] >= w["r"] - 1 and s["b"] >= w["b"] - 1


def fmt_box(b: dict) -> str:
    s = b["stage"]
    return f"장면 ({s['l']:.0f},{s['t']:.0f})~({s['r']:.0f},{s['b']:.0f}) · 뷰포트 {b['vw']}×{b['vh']}"


def pinch(pg, x, y, d0, d1, n=8):
    steps = [["pointerdown", 1, x - d0 / 2, y], ["pointerdown", 2, x + d0 / 2, y]]
    for i in range(1, n + 1):
        d = d0 + (d1 - d0) * i / n
        steps += [["pointermove", 1, x - d / 2, y], ["pointermove", 2, x + d / 2, y]]
    steps += [["pointerup", 1, x - d1 / 2, y], ["pointerup", 2, x + d1 / 2, y]]
    pg.evaluate(POINTER_JS, steps)


def drag(pg, x, y, dx, dy, n=8):
    steps = [["pointerdown", 1, x, y]] + [["pointermove", 1, x + dx * i / n, y + dy * i / n] for i in range(1, n + 1)]
    pg.evaluate(POINTER_JS, steps + [["pointerup", 1, x + dx, y + dy]])


def zoom_checks(C: Checks, browser, label, device, url, at, want_now, busiest, shots, errs, reqs, capture=None):
    """폰에서 처음 화면에 광장 전체, 핀치·끌기·두 번 탭·버튼, 범위·가장자리, 확대 중 말풍선 수·자리, 연출 켬/끔, 리플레이."""
    G = f"폰 전체 보기·확대 ({label})"

    def open_(q, motion=False):
        ctx = browser.new_context(**device, reduced_motion="no-preference" if motion else "reduce")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"{label}: {e}"))
        pg.on("request", lambda r: reqs.append(r.url))
        pg.clock.install(time=at)
        pg.goto(f"{url}/?{q}")
        pg.wait_for_load_state("networkidle")
        pg.clock.run_for(3000)
        return ctx, pg

    zs = lambda pg: pg.evaluate("Plaza.stats().zoom")
    box = lambda pg: pg.evaluate(BOX_JS)

    def mid(pg):
        w = box(pg)["wrap"]
        return (w["l"] + w["r"]) / 2, (w["t"] + w["b"]) / 2

    ctx, pg = open_("mode=now&motion=0")
    b0, st0 = box(pg), pg.evaluate("Plaza.stats()")
    stray = pg.evaluate(STRAY_JS)
    pg.evaluate("document.fonts.ready")
    pg.screenshot(path=str(shots / f"phone_fit_{label.split()[0].lower()}.png"))
    C.check(G, f"{device['viewport']['width']}×{device['viewport']['height']} 첫 화면에 광장 그림 전체 (장면 상자 = 틀, 뷰포트 안) · 구역 아홉",
            full_view(b0) and abs(st0["zoom"]["z"] - 1) < 1e-6 and len(st0["zonesShown"]) == 9 and st0["phone"],
            f"{fmt_box(b0)} · 확대 {st0['zoom']['z']:.2f} · 구역 {len(st0['zonesShown'])}")
    C.check(G, "전체 보기에서는 장면이 세로 스크롤을 페이지에 넘긴다 (touch-action pan-y)", b0["ta"] == "pan-y", b0["ta"])

    B0 = pg.evaluate(BUBBLES_JS)
    x, y = mid(pg)
    pinch(pg, x, y, 60, 120)
    z1 = zs(pg)
    drag(pg, x, y, -80, -40)
    z2 = zs(pg)
    B1 = pg.evaluate(BUBBLES_JS)
    b1 = box(pg)
    C.check(G, "두 손가락 벌리기 2배 → 한 손가락 끌어 이동", 1.9 <= z1["z"] <= 2.1 and z2["cx"] - z1["cx"] > 60 and z2["cy"] - z1["cy"] > 30
            and b1["ta"] == "none",
            f"확대 {z1['z']:.2f} · 가운데 ({z1['cx']:.0f},{z1['cy']:.0f}) → ({z2['cx']:.0f},{z2['cy']:.0f}) · touch-action {b1['ta']}")
    p0 = {d["id"]: d for d in B0}
    moved = max((abs(d["x"] - p0[d["id"]]["x"]) + abs(d["y"] - p0[d["id"]]["y"]) for d in B1 if d["id"] in p0), default=0)
    C.check(G, "확대·이동 뒤 말풍선 수 불변, 장면 좌표 자리 그대로",
            len(B0) == len(B1) == want_now and {d["id"] for d in B0} == {d["id"] for d in B1} and moved <= 1.5,
            f"전체 {len(B0)} · 확대 {len(B1)} · 스냅샷 {want_now} · 자리 차이 최대 {moved:.2f}px(장면)")
    pg.evaluate("Plaza.setMotion(true)")
    pg.clock.run_for(4000)
    on = pg.evaluate("Plaza.stats()")
    pg.evaluate("Plaza.setMotion(false)")
    pg.clock.run_for(1000)
    off = pg.evaluate("Plaza.stats()")
    C.check(G, "확대한 채 연출 켬·끔: 말풍선 수 불변, 확대 상태 유지",
            on["bubblesOnStage"] == off["bubblesOnStage"] == want_now and abs(on["zoom"]["z"] - z2["z"]) < 1e-6 and abs(off["zoom"]["cx"] - z2["cx"]) < 1e-6,
            f"켬 {on['bubblesOnStage']} · 끔 {off['bubblesOnStage']} · 스냅샷 {want_now} · 확대 {off['zoom']['z']:.2f}")

    # 자 검사: 틀 안에 보이는 말풍선만 세면 확대 뒤 수가 줄어야 한다 (전체를 세는 판정이 잘림을 못 가리는 자가 아님을 보인다)
    pg.evaluate(f"Plaza.zoom.set({ZOOM_MAX}, 170, 100)")
    inview = sum(d["inView"] for d in pg.evaluate(BUBBLES_JS))
    C.check(G, "자 검사: 왼쪽 위 4배에서 틀 안에 보이는 것만 세면 「다름」", inview < want_now, f"틀 안 {inview} / 전체 {want_now}")

    # 범위·가장자리
    pg.evaluate("Plaza.zoom.reset()")
    x, y = mid(pg)
    pinch(pg, x, y, 20, 400)
    zmax = zs(pg)["z"]
    drag(pg, x, y, 3000, 3000)
    b_edge, z_edge = box(pg), zs(pg)
    drag(pg, x, y, -6000, -6000)
    b_edge2 = box(pg)
    pinch(pg, x, y, 300, 20)
    zmin, b_min = zs(pg)["z"], box(pg)
    C.check(G, f"확대 범위 1~{ZOOM_MAX}배, 끝까지 끌어도 가장자리 밖이 안 보임",
            abs(zmax - ZOOM_MAX) < 1e-6 and covers(b_edge) and covers(b_edge2) and abs(zmin - 1) < 1e-6 and full_view(b_min),
            f"20배로 벌림 → {zmax:.2f} · 왼쪽 위 끝 가운데 ({z_edge['cx']:.0f},{z_edge['cy']:.0f}) · 오므림 → {zmin:.2f}")
    probe = json.loads(json.dumps(b_edge))
    probe["stage"]["l"] += 40
    probe["stage"]["r"] += 40
    C.check(G, "자 검사: 장면이 40px 밀려 가장자리가 보이면 「밖」", not covers(probe) and not full_view(probe), "")

    # 버튼 · 두 번 탭
    pg.tap("#pzZoom [data-z=in]")
    pg.tap("#pzZoom [data-z=in]")
    za = zs(pg)["z"]
    pg.tap("#pzZoom [data-z=out]")
    zb = zs(pg)["z"]
    pg.tap("#pzZoom [data-z=fit]")
    zc, bc = zs(pg)["z"], box(pg)
    C.check(G, "버튼 + + − 전체 보기", abs(za - 2.25) < 1e-3 and abs(zb - 1.5) < 1e-3 and abs(zc - 1) < 1e-6 and full_view(bc),
            f"{za:.2f} → {zb:.2f} → {zc:.2f}")
    x, y = mid(pg)
    pg.touchscreen.tap(x, y)
    pg.touchscreen.tap(x, y)
    zd = zs(pg)["z"]
    pg.clock.run_for(1000)
    pg.touchscreen.tap(x, y)
    pg.touchscreen.tap(x, y)
    ze = zs(pg)["z"]
    C.check(G, "두 번 탭 2배, 다시 두 번 탭 전체 보기", abs(zd - 2) < 1e-3 and abs(ze - 1) < 1e-6, f"{zd:.2f} → {ze:.2f}")
    ctx.close()

    # 자 검사: 틀린 첫 화면(2배, 옛 「구역 넷」 자르기)을 「전체 아님」으로
    ctx, pg = open_("mode=now&motion=0")
    pg.evaluate("Plaza.zoom.set(2)")
    probe2 = box(pg)
    pg.evaluate("""() => { const w = document.getElementById('pzWrap'), k = w.clientWidth / 880;
      w.style.height = Math.round(468 * k) + 'px'; document.getElementById('pzStage').style.transform = `translate(${-40 * k}px, ${-300 * k}px) scale(${k})`; }""")
    probe3 = box(pg)
    ctx.close()
    C.check(G, "자 검사: 2배 첫 화면·옛 구역 넷 자르기를 「전체 아님」", not full_view(probe2) and not full_view(probe3),
            f"2배 {fmt_box(probe2)} · 옛 자르기 {fmt_box(probe3)}")

    # 리플레이를 확대한 채 끝까지
    date = busiest["date"]
    ctx, pg = open_(f"view=replay&motion=1&date={date}&autopause=0&speed=600", motion=True)
    pg.evaluate(f"Plaza.replay({{date: '{date}', speed: 600, autopause: false}})")
    x, y = mid(pg)
    pinch(pg, x, y, 50, 125)
    drag(pg, x, y, 60, 30)
    zr = zs(pg)
    pg.clock.run_for(150_000)
    st = pg.evaluate("Plaza.stats()")
    ctx.close()
    C.check(G, f"확대한 채 리플레이 {date} 끝까지 (600×, 연출 켬)",
            st["emitted"] == st["expected"] == busiest["bubbles"] and not st["playing"] and abs(st["zoom"]["z"] - zr["z"]) < 1e-6 and zr["z"] > 2,
            f"말풍선 {st['emitted']} / 파일 {st['expected']} / index {busiest['bubbles']} · 확대 {st['zoom']['z']:.2f}")

    # 캡처: 처음 전체 보기 · 분수 쪽을 벌려 확대한 상태 (연출 켬)
    if capture:
        ctx, pg = open_("mode=now&motion=1", motion=True)
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(capture[0]))
        w = box(pg)["wrap"]
        fit = zs(pg)["fit"]
        fx, fy = w["l"] + 690 * fit, w["t"] + 600 * fit
        pinch(pg, fx, fy, 40, 110)
        pg.clock.run_for(1500)
        pg.screenshot(path=str(capture[1]))
        ctx.close()
    return stray


def until(pg, expr, tries=30):
    """가짜 시계(clock.install) 아래선 wait_for_function 이 안 돈다(rAF·타이머가 멈춰 있음). 진짜 시간으로 물어본다."""
    for _ in range(tries):
        if pg.evaluate(expr):
            return True
        pg.wait_for_timeout(100)
    return False


def desktop_zoom_checks(C: Checks, browser, url, at, errs, reqs):
    """데스크톱: 전체 보기에서 휠은 페이지 스크롤, 더블클릭·마우스 끌기·확대 중 휠, 확대 중에도 모드 버튼이 눌린다."""
    G = "데스크톱 확대 (Chromium)"
    ctx = browser.new_context(viewport={"width": 1280, "height": 480}, device_scale_factor=1, reduced_motion="reduce")   # 페이지가 스크롤되는 높이
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"desktop: {e}"))
    pg.on("request", lambda r: reqs.append(r.url))
    pg.clock.install(time=at)
    pg.goto(f"{url}/?mode=now&motion=0")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(3000)
    w = pg.evaluate(BOX_JS)["wrap"]
    x, y = (w["l"] + w["r"]) / 2, w["t"] + 120
    pg.mouse.move(x, y)
    pg.mouse.wheel(0, 300)
    until(pg, "scrollY > 0")
    pg.wait_for_timeout(800)   # 부드러운 스크롤 꼬리가 끝날 때까지 (안 기다리면 뒤 판정의 scrollY 가 몇 px 흔들린다)
    sy, z0 = pg.evaluate("scrollY"), pg.evaluate("Plaza.stats().zoom.z")
    C.check(G, "전체 보기에서 장면 위 휠 = 페이지 스크롤 (확대 안 함)", sy > 0 and z0 == 1, f"scrollY {sy} · 확대 {z0}")
    pg.evaluate("scrollTo(0, 0)")
    until(pg, "scrollY === 0")
    pg.wait_for_timeout(300)
    sy0 = pg.evaluate("scrollY")
    pg.mouse.dblclick(x, y)
    za = pg.evaluate("Plaza.stats().zoom")
    pg.mouse.move(x, y)
    pg.mouse.down()
    pg.mouse.move(x - 120, y - 60, steps=6)
    pg.mouse.up()
    zb = pg.evaluate("Plaza.stats().zoom")
    pg.mouse.wheel(0, -200)
    pg.wait_for_timeout(800)
    zc, sy2 = pg.evaluate("Plaza.stats().zoom"), pg.evaluate("scrollY")
    C.check(G, "더블클릭 2배 · 마우스로 끌어 이동 · 확대 중 휠은 확대 (페이지는 안 움직임)",
            abs(za["z"] - 2) < 1e-3 and zb["cx"] - za["cx"] > 40 and zc["z"] > zb["z"] + 0.1 and sy2 == sy0,
            f"{za['z']:.2f} · 가운데 x {za['cx']:.0f}→{zb['cx']:.0f} · 휠 → {zc['z']:.2f} · scrollY {sy0}→{sy2}")
    pg.click("#pzModeChip [data-mode=replay]")
    mode = pg.evaluate("Plaza.stats().mode")
    pg.click("#pzZoom [data-z=fit]")
    zf = pg.evaluate("Plaza.stats().zoom.z")
    ctx.close()
    C.check(G, "확대 중에도 장면 위 버튼이 눌린다 (모드 「리플레이」 · 「전체 보기」)", mode == "replay" and zf == 1, f"모드 {mode} · 확대 {zf}")


# ── 6. 대화 보기 (말풍선이 행동 종류만 보여 무슨 말을 했는지 모른다는 피드백) ──
# 말풍선 = 원장 행의 공개 본문 앞 16자, 캐릭터를 누르면 그 에이전트 글 전문, 장면 아래 「최근 이야기」.
# 본문은 서버 공개 문(threads.json·threads/·requests/·agents/)에서만 읽고 textContent 로만 넣는다
BUBBLE_CHARS = 16
TAG_MARK = "<img src=x"          # stage3_data TAG_REMARK 의 앞. 화면에 글자로 보여야 한다
HELD_MARK = "/Users/lilac"       # stage3_data 에서 보류된 글. 화면 어디에도 없어야 한다
LONG_MIN_LINES = 8                # stage3_data LONG_POST 는 줄바꿈 8개 + 긴 줄 꺾임
TALK_JS = """() => [...document.querySelectorAll('#pzTalk > li.pz-ti')].map((li) => ({
  event: li.dataset.event, type: li.dataset.type, post: li.dataset.post || null,
  state: [...li.classList].find((c) => c.startsWith('st-')),
  body: (li.querySelector('.pz-tb:not(.note)') || {}).textContent ?? null,
  note: (li.querySelector('.pz-tb.note') || {}).textContent ?? null,
  targets: [...li.querySelectorAll('.pz-tl')].map((b) => b.dataset.target || null) }))"""
MORE_JS = "() => { const m = document.getElementById('pzTalkMore'); let n = 0; while (!m.hidden && n < 50) { m.click(); n++; } return n; }"
# 본문 칸 안에 요소가 하나라도 생기면 innerHTML 로 들어간 것이다
XSS_JS = """() => ({ flag: window.__xss ?? null,
  els: document.querySelectorAll('.pz-tb *, .pz-bs *, .pz-bk *, .pz-tl q *, .pz-intro *').length,
  literal: document.body.textContent.includes('<img src=x') })"""
WHO_JS = """() => { const m = document.getElementById('pzWho'), sh = m.querySelector('.pz-sheet'), r = sh.getBoundingClientRect();
  const lists = m.querySelectorAll('.pz-wholist');
  const posts = lists.length ? [...lists[0].querySelectorAll(':scope > li.pz-ti')].map((li) => ({ post: li.dataset.post,
    body: (li.querySelector('.pz-tb:not(.note)') || {}).textContent ?? null, note: (li.querySelector('.pz-tb.note') || {}).textContent ?? null })) : [];
  const tb = [...m.querySelectorAll('.pz-tb')];
  const lines = tb.map((el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)));
  return { open: !m.hidden, ready: m.dataset.ready === '1', title: document.getElementById('pzWhoT').textContent, posts, lines,
    over: tb.filter((el) => el.scrollWidth > el.clientWidth + 1).length + (sh.scrollWidth > sh.clientWidth + 1 ? 1 : 0),
    box: { l: r.left, t: r.top, r: r.right, b: r.bottom }, vw: innerWidth, vh: innerHeight, html: document.documentElement.outerHTML.includes('/Users/lilac') }; }"""


# 캐릭터끼리 겹치면 앞 캐릭터가 누름을 받는다. 그 캐릭터가 맨 위인 점을 몸 상자 안에서 찾는다
FIG_POINT_JS = """(id) => { const f = document.querySelector(`.pz-agent[data-id="${id}"]`), r = f.querySelector('.pz-body').getBoundingClientRect();
  for (const fy of [0.6, 0.4, 0.8, 0.25, 0.9]) for (const fx of [0.5, 0.3, 0.7, 0.15, 0.85]) {
    const x = r.left + r.width * fx, y = r.top + r.height * fy, e = document.elementFromPoint(x, y);
    if (e && e.closest('.pz-agent') === f) return [x, y]; }
  return [(r.left + r.right) / 2, r.top + r.height * 0.6]; }"""


def pclip(s: str, n: int) -> str:
    a = " ".join(s.split())
    return a[:n] + "…" if len(a) > n else a


def public_texts(pub: Path) -> dict:
    """정적 사본의 공개 문에서 글 id → 글 (서버가 public_view 로 낸 그대로)."""
    rd = lambda f: json.loads(f.read_text(encoding="utf-8"))
    posts = {p["id"]: p for p in rd(pub / "threads.json")["remarks"]}
    for f in sorted((pub / "threads").glob("*.json")):
        posts.update({p["id"]: p for p in rd(f)["posts"]})
    for f in sorted((pub / "agents").glob("*.json")):
        posts.update({p["id"]: p for p in rd(f)["recent_posts"]})
    return posts


def replay_rows(pub: Path) -> list[dict]:
    rows = []
    for f in sorted((pub / "replay").glob("20*.json")):
        rows += json.loads(f.read_text(encoding="utf-8"))["events"]
    return rows


def silent(rows: list[dict], i: int) -> bool:
    """렌더러와 같은 정의: 그 방문 뒤 같은 에이전트의 다음 방문 전까지 말풍선 행이 없다."""
    for n in rows[i + 1:]:
        if n["actor"] != rows[i]["actor"]:
            continue
        if n["type"] == "agent_visited":
            return True
        if n["bubble"]:
            return False
    return True


def talk_checks(C: Checks, browser, label, device, url, at, pub: Path, snap: dict, errs, reqs, phone: bool):
    G = f"대화 보기 ({label})"
    posts = public_texts(pub)
    rows = replay_rows(pub)
    P = snap["plaza"]
    ctx = browser.new_context(**device, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{label}: {e}"))
    pg.on("request", lambda r: reqs.append(r.url))
    pg.clock.install(time=at)
    pg.goto(f"{url}/?mode=now&motion=0")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(2000)
    st = pg.evaluate("Plaza.stats()")

    # 1. 말풍선 = 공개 본문 앞 16자. 말풍선 수는 그대로
    byid = {e["id"]: e for e in rows}
    want, bad = {}, []
    for r in P["residents"]:
        b = r["bubble"]
        e = b and byid.get(b["event_id"])
        if e and e["type"] == "post_created" and posts.get(e["subject"], {}).get("visibility") == "visible":
            want[r["id"]] = "“" + pclip(posts[e["subject"]]["body"], BUBBLE_CHARS) + "”"
    got = {b["id"]: b["words"] for b in st["bubbleTexts"] if b["words"] and b["words"].startswith("“")}
    bad = [k for k in set(want) | set(got) if want.get(k) != got.get(k)]
    C.check(G, "말풍선에 그 행의 공개 본문 앞 16자, 말풍선 수 = 스냅샷", not bad and len(st["bubbleTexts"]) == sum(1 for r in P["residents"] if r["bubble"])
            and want and not st["textsFailed"],
            f"본문 말풍선 {len(got)}/{len(want)} · 전체 {len(st['bubbleTexts'])} · 틀림 {bad[:2] or 0} · 못 읽음 {st['textsFailed'] or 0}")
    # 자 검사: 17자로 자르면 「틀림」
    probe = {k: "“" + pclip(posts[byid[r['bubble']['event_id']]['subject']]["body"], BUBBLE_CHARS + 1) + "”"
             for r in P["residents"] for k in [r["id"]] if k in want}
    C.check(G, "자 검사: 17자로 자른 기대값은 「틀림」", any(probe[k] != got.get(k) for k in probe), "")

    # 2. 최근 이야기: 지난 24시간 글 행 전부, 본문 = 공개 본문(줄바꿈 그대로), 가린 글은 본문 없이 표시, 답글·인용 연결
    pg.evaluate(MORE_JS)
    T = pg.evaluate(TALK_JS)
    since = dt.datetime.fromisoformat(snap["generated"]) - dt.timedelta(hours=24)
    recent = [e for e in rows if dt.datetime.fromisoformat(e["at"]) >= since]
    dom_posts = {t["post"]: t for t in T if t["type"] == "post_created"}
    miss, wrong, link_bad = [], [], []
    for e in recent:
        if e["type"] != "post_created":
            continue
        t, p = dom_posts.get(e["subject"]), posts.get(e["subject"])
        if not t:
            miss.append(e["subject"]); continue
        if p and p["visibility"] == "visible":
            if t["body"] != p["body"]:
                wrong.append(e["subject"])
        elif t["body"] is not None or not t["note"]:
            wrong.append(e["subject"])
        want_t = [x for x in (e["data"].get("reply_to"), e["data"].get("quote_of")) if x]
        if t["targets"] != want_t:
            link_bad.append(e["subject"])
    hidden = [t for t in T if t["type"] == "post_created" and posts.get(t["post"], {}).get("visibility") not in (None, "visible")]
    C.check(G, "최근 이야기: 지난 24시간 글 행 전부, 본문 글자 그대로(줄바꿈·이모지), 답글·인용 연결",
            not miss and not wrong and not link_bad and len(dom_posts) >= sum(1 for e in recent if e["type"] == "post_created"),
            f"글 행 {len(dom_posts)} (24시간 {sum(1 for e in recent if e['type'] == 'post_created')}) · 빠짐 {miss[:2] or 0} · 본문 틀림 {wrong[:2] or 0} · 연결 틀림 {link_bad[:2] or 0} · 가린·지운 글 {len(hidden)}")
    long_ok = any(t["body"] and t["body"].count("\n") >= 5 and "🍜" in t["body"] for t in T)
    C.check(G, "긴 글·여러 줄·이모지 글이 목록에 한 글자도 안 바뀌고 들어감", long_ok, "")
    # 말 없이 다녀간 방문
    idx = {e["id"]: i for i, e in enumerate(rows)}
    dom_sil = [t["event"] for t in T if t["type"] == "agent_visited"]
    want_sil = [e["id"] for i, e in enumerate(rows) if e["type"] == "agent_visited" and dt.datetime.fromisoformat(e["at"]) >= since and silent(rows, i)]
    fake = [x for x in dom_sil if not silent(rows, idx[x])]
    C.check(G, "말 없이 다녀간 방문은 「한 말 없음」으로, 말한 방문은 안 적음",
            not fake and set(want_sil) <= set(dom_sil) and want_sil,
            f"화면 {len(dom_sil)} · 24시간 기대 {len(want_sil)} · 말했는데 적힘 {fake or 0}")
    probe = [e["id"] for i, e in enumerate(rows) if e["type"] == "agent_visited" and not silent(rows, i)]
    C.check(G, "자 검사: 말한 방문을 넣으면 「말했는데 적힘」", bool(probe) and not silent(rows, idx[probe[0]]), f"말한 방문 {len(probe)}")

    # 3. 글자 그대로: HTML 처럼 생긴 본문이 요소가 되지 않는다
    x = pg.evaluate(XSS_JS)
    C.check(G, "본문은 글자로만 (innerHTML 없음): 태그 글자가 보이고 요소 0, 스크립트 안 돎",
            x["flag"] is None and x["els"] == 0 and x["literal"], f"__xss {x['flag']} · 본문 안 요소 {x['els']} · 글자 {x['literal']}")
    ctx2 = browser.new_context(**device)
    pg2 = ctx2.new_page()
    pg2.goto(f"{url}/?mode=now&motion=0")
    pg2.wait_for_load_state("networkidle")
    pg2.evaluate("(h) => document.getElementById('pzTalk').insertAdjacentHTML('beforeend', '<li><p class=\"pz-tb\">' + h + '</p></li>')",
                 '<img src=x onerror="window.__xss=1"> <b>굵게</b>')
    pg2.wait_for_timeout(300)
    x2 = pg2.evaluate(XSS_JS)
    ctx2.close()
    C.check(G, "자 검사: 같은 글자를 innerHTML 로 넣으면 「요소 생김」", x2["els"] > 0 and x2["flag"] == 1, f"요소 {x2['els']} · __xss {x2['flag']}")

    # 4. 캐릭터를 누르면 그 에이전트 글 전문 (긴 글 쓴 호두)
    long_id = next(p["id"] for p in posts.values() if (p.get("body") or "").startswith("호두의 긴 글"))
    aid = posts[long_id]["author"]["id"]
    aj = json.loads((pub / "agents" / f"{aid}.json").read_text(encoding="utf-8"))

    def fig_point(i):
        return pg.evaluate(FIG_POINT_JS, i)
    # 폰 전체 보기에선 캐릭터가 손가락보다 작아 브라우저가 누름을 옆 캐릭터로 붙인다(Chromium 터치 보정). 사람처럼 그 자리를 키우고 누른다
    pg.evaluate("scrollTo(0, 0)")
    zin = f"() => {{ const e = document.querySelector('.pz-agent[data-id=\"{aid}\"]'); Plaza.zoom.set(2.5, parseFloat(e.style.left), parseFloat(e.style.top) - 40); }}"
    pg.evaluate(zin)
    z0 = pg.evaluate("Plaza.stats().zoom.z")
    fx, fy = fig_point(aid)
    if phone:
        pg.touchscreen.tap(fx, fy)
    else:
        pg.mouse.click(fx, fy)
    pg.clock.run_for(600)
    until(pg, "document.getElementById('pzWho').dataset.ready === '1'")
    w = pg.evaluate(WHO_JS)
    want_p = [(p["id"], p["body"] if p["visibility"] == "visible" else None) for p in aj["recent_posts"]]
    got_p = [(q["post"], q["body"]) for q in w["posts"]]
    long_lines = max(w["lines"] or [0])
    inside = w["box"]["l"] >= -1 and w["box"]["r"] <= w["vw"] + 1 and w["box"]["b"] <= w["vh"] + 1 and w["box"]["t"] >= -1
    C.check(G, f"캐릭터를 {'탭' if phone else '클릭'}하면 그 에이전트 글 전문 (공개 문 agents/{{id}}.json 과 같은 순서·같은 글자)",
            w["open"] and w["ready"] and got_p == want_p and w["title"] == aj["agent"]["nickname"] and pg.evaluate("Plaza.stats().zoom.z") == z0,
            f"{w['title']} · 글 {len(got_p)}/{len(want_p)} · 확대 {z0}→{pg.evaluate('Plaza.stats().zoom.z')}")
    C.check(G, "패널: 긴 글이 줄바꿈대로 여러 줄, 가로 넘침 0, 패널이 화면 안",
            long_lines >= LONG_MIN_LINES and w["over"] == 0 and inside,
            f"가장 긴 본문 {long_lines}줄 · 넘침 {w['over']} · 패널 ({w['box']['l']:.0f},{w['box']['t']:.0f})~({w['box']['r']:.0f},{w['box']['b']:.0f}) / {w['vw']}×{w['vh']}")
    pg.click("#pzWhoX")
    # 두 번 탭/더블클릭은 확대 전환(2.5 → 전체 보기)이지 패널이 아니다
    pg.evaluate(zin)
    pg.wait_for_timeout(500)   # 앞 탭(패널 연 것)과 짝지어 두 번 탭이 되지 않게, 사람 손 간격만큼 (터치 이벤트 시각은 가짜 시계 밖)
    fx, fy = fig_point(aid)
    if phone:
        pg.touchscreen.tap(fx, fy)
        pg.touchscreen.tap(fx, fy)
    else:
        pg.mouse.dblclick(fx, fy)
    pg.clock.run_for(800)
    pg.wait_for_timeout(300)
    zz, op = pg.evaluate("Plaza.stats().zoom.z"), pg.evaluate("!document.getElementById('pzWho').hidden")
    C.check(G, f"캐릭터 위 {'두 번 탭' if phone else '더블클릭'}은 확대 전환만 (패널 안 열림)", abs(zz - 1) < 1e-6 and not op, f"확대 2.50 → {zz:.2f} · 패널 {op}")
    pg.evaluate("Plaza.zoom.reset()")

    # 5. 보류 글은 어디에도 없다 (보류당한 라일락 패널까지 열어 본다)
    lil = next(a["id"] for a in P["roster"] if a["nickname"] == "라일락")
    pg.evaluate(f"""() => {{ const b = document.createElement('button'); b.dataset.agent = '{lil}'; b.id = 'pzProbeOpen';
      document.getElementById('pzTalk').append(b); b.click(); b.remove(); }}""")
    until(pg, "document.getElementById('pzWho').dataset.ready === '1'")
    w2 = pg.evaluate(WHO_JS)
    raw = "".join(f.read_text(encoding="utf-8") for f in pub.rglob("*.json"))
    C.check(G, "보류된 글은 목록·패널·말풍선 어디에도 없음 (공개 문에도 없음)", not w2["html"] and HELD_MARK not in raw and w2["title"] == "라일락",
            f"라일락 패널 글 {len(w2['posts'])} · 화면에 {HELD_MARK} {w2['html']}")
    pg.evaluate(f"() => document.body.append(document.createTextNode('{HELD_MARK}/photos'))")
    C.check(G, "자 검사: 그 글자를 화면에 넣으면 「있음」", pg.evaluate(WHO_JS)["html"], "")
    ctx.close()


# ── 7. 캐릭터가 시설 앞에 (09-26 16:33 「벤치나 다른 광장내 시설과 겹치면 … 캐릭터는 앞으로」) ──
# 시설 그림 발끝 바로 위(6px)에 캐릭터를 세우면 옛 층 순서(발 y 하나)에선 그림 뒤로 들어간다. 그 자리에서 몸 가운데·발 쪽·
# 말풍선 가운데를 elementFromPoint 로 물어 캐릭터가 맨 위인지 본다. 시설 그림은 원래 pointer-events 가 없어 잠깐 켠다
FRONT_SPOTS = [("분수", 690, 606), ("벤치", 555, 729), ("벤치2", 880, 759), ("카페", 1215, 712), ("카페 앞자리(실제 슬롯)", 1212, 662),
               ("게시판", 555, 446), ("노점", 205, 594), ("노점2", 335, 666), ("무대", 1195, 554)]
FRONT_JS = """([id, spots, old]) => {
  const add = (css, sid) => { const s = document.createElement('style'); s.id = sid; s.textContent = css; document.head.append(s); };
  if (old) add('#pzThings, #pzFigures { position: static !important; z-index: auto !important; }', 'pzOldLayers');
  add('.pz-thing { pointer-events: auto !important; }', 'pzPE');
  const f = document.querySelector(`.pz-agent[data-id="${id}"]`), keep = [f.style.left, f.style.top, f.style.zIndex];
  const out = [];
  for (const [name, x, y] of spots) {
    f.style.left = x + 'px'; f.style.top = y + 'px'; f.style.zIndex = String(Math.round(y) + 2);
    for (const [part, el, fy] of [['몸', f.querySelector('.pz-body'), 0.5], ['발', f.querySelector('.pz-body'), 0.9], ['말풍선', f.querySelector('.pz-bubble'), 0.5]]) {
      if (!el) continue;
      const r = el.getBoundingClientRect(), px = (r.left + r.right) / 2, py = r.top + r.height * fy;
      // 시설 그림이 이 캐릭터보다 위에 있으면 「뒤」. 다른 캐릭터가 위에 있는 건 발 y 순서라 따지지 않는다
      const stack = document.elementsFromPoint(px, py);
      const iF = stack.findIndex((e) => e.closest('.pz-agent') === f), iT = stack.findIndex((e) => e.closest('.pz-thing'));
      out.push({ name, part, front: iF >= 0 && (iT < 0 || iF < iT), overlap: iT >= 0 });
    }
  }
  [f.style.left, f.style.top, f.style.zIndex] = keep;
  document.getElementById('pzPE').remove();
  const o = document.getElementById('pzOldLayers'); if (o) o.remove();
  return out; }"""


def front_checks(C: Checks, browser, label, device, url, at, snap, errs):
    G = f"캐릭터 앞 ({label})"
    ctx = browser.new_context(**device, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{label}: {e}"))
    pg.clock.install(time=at)
    pg.goto(f"{url}/?mode=now&motion=0")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(2000)
    fid = next(r["id"] for r in snap["plaza"]["residents"] if r["bubble"])
    spots = [list(s) for s in FRONT_SPOTS]
    new = pg.evaluate(FRONT_JS, [fid, spots, False])
    old = pg.evaluate(FRONT_JS, [fid, spots, True])
    ov = [r for r in new if r["overlap"]]
    behind = [f"{r['name']}·{r['part']}" for r in new if not r["front"]]
    C.check(G, "시설 아홉 곳에 겹쳐 세워도 캐릭터 몸·발·말풍선이 맨 위 (캐릭터끼리는 발 y 순서 그대로)",
            not behind and len({r["name"] for r in ov}) == len(FRONT_SPOTS),
            f"잰 점 {len(new)} · 시설과 겹친 점 {len(ov)} (시설 {len({r['name'] for r in ov})}/{len(FRONT_SPOTS)}) · 뒤로 들어감 {behind[:3] or 0}")
    old_behind = [f"{r['name']}·{r['part']}" for r in old if not r["front"]]
    C.check(G, "자 검사: 옛 층 순서(한 층, 발 y 만)로 되돌리면 겹친 시설마다 「뒤로 들어감」",
            {r["name"] for r in old if not r["front"]} == {r["name"] for r in ov} and old_behind,
            f"뒤로 들어감 {len(old_behind)}곳 · 예 {', '.join(old_behind[:3])}")
    z = pg.evaluate("[...document.querySelectorAll('#pzFigures .pz-agent:not([hidden])')].map((e) => [Number(e.style.zIndex), parseFloat(e.style.top)])")
    C.check(G, "캐릭터끼리 순서 = 발 y 순서 (z-index = y + 2)", all(abs(a - round(b) - 2) <= 1 for a, b in z) and z, f"캐릭터 {len(z)}")
    ctx.close()


# 리플레이 타임라인 글자: 글자를 가진 요소마다 화면까지의 가로·세로 배율(SVG 는 getScreenCTM, HTML 은 조상 transform 곱)과
# 상자. 막대는 폭에 맞춰 늘어나도 되지만 글자는 가로/세로 = 1 이어야 한다 (앞 판은 viewBox 1510 을 폰 폭에 눌러 담아 ≈0.26)
TL_TEXT_JS = r"""(sel) => {
  const out = [];
  const scale = (el) => {
    let m;
    if (el instanceof SVGGraphicsElement) m = el.getScreenCTM();
    else { m = new DOMMatrix(); for (let e = el; e; e = e.parentElement) { const t = getComputedStyle(e).transform; if (t && t !== 'none') m = new DOMMatrix(t).multiply(m); } }
    return [Math.hypot(m.a, m.b), Math.hypot(m.c, m.d)];
  };
  for (const tl of document.querySelectorAll(sel)) {
    const box = tl.getBoundingClientRect();
    if (!box.width) continue;
    for (const el of [tl, ...tl.querySelectorAll('*')]) {
      const txt = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
      if (!txt) continue;
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      if (!r.width || cs.display === 'none' || cs.visibility === 'hidden') continue;
      const [sx, sy] = scale(el);
      out.push({t: txt, cls: el.getAttribute('class') || el.tagName, ratio: sx / sy, l: r.left, r: r.right, top: r.top, b: r.bottom,
                inside: r.left >= box.left - 0.5 && r.right <= box.right + 0.5});
    }
  }
  return out;
}"""
TL_PROBE_JS = ("() => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'pz-probe');"
               "s.setAttribute('viewBox', '0 0 1510 128'); s.setAttribute('preserveAspectRatio', 'none'); s.style.cssText = 'width:100%;height:128px;display:block';"
               "s.innerHTML = '<text x=\"0\" y=\"116\" font-size=\"11\">00:00</text><text x=\"755\" y=\"116\" font-size=\"11\">12:00</text>';"
               "document.querySelector('#pzRbarPlaza').appendChild(s); }")


def timeline_checks(C: Checks, browser, label, device, url, at, date, errs, phone: bool):
    """리플레이 타임라인의 시각 눈금·장면 깃발·재생 표시 글자가 눌리지 않고, 겹치지 않고, 막대 안에 있는가. 광장·계기판 두 막대."""
    G = f"타임라인 글자 ({label})"
    ctx = browser.new_context(**device, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{label}: {e}"))
    pg.clock.install(time=at)
    res = {}
    for view, sel in (("replay", "#pzRbarPlaza .pz-timeline"), ("watch", "#pzRbarWatch .pz-timeline")):
        pg.goto(f"{url}/?view={view}&motion=0&autopause=0&date={date}")
        pg.wait_for_load_state("networkidle")
        pg.clock.run_for(2000)
        pg.evaluate(f"Plaza.replay({{date: '{date}', speed: 60, autopause: false}})")
        pg.clock.run_for(1500)
        pg.evaluate("document.fonts.ready")
        res[view] = (pg.evaluate("(s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().width) : 0; }", sel),
                     pg.evaluate(TL_TEXT_JS, sel))
    for view, (w, T) in res.items():
        where = "광장" if view == "replay" else "계기판"
        ticks = [t for t in T if ":00" in t["t"] and "재생" not in t["t"]]
        rs = [t["ratio"] for t in T]
        C.check(G, f"{where} 막대 {w}px: 글자 가로/세로 배율 = 1 (눌림 없음)",
                w > 0 and len(ticks) >= 3 and any("재생" in t["t"] for t in T) and all(abs(r - 1) < 0.03 for r in rs),
                f"글자 {len(T)} · 눈금 {len(ticks)} · 배율 {min(rs, default=0):.3f}~{max(rs, default=0):.3f}")
        rows = {}
        for t in T:
            if "pz-tick" in t["cls"] or "pz-tlflag" in t["cls"]:
                rows.setdefault(t["cls"].split()[0], []).append(t)
        hits = []
        for k, row in rows.items():
            row.sort(key=lambda t: t["l"])
            hits += [f"{a['t']}|{b['t']}" for a, b in zip(row, row[1:]) if b["l"] < a["r"] - 0.5]
        outside = [t["t"] for t in T if not t["inside"] and "재생" not in t["t"]]
        C.check(G, f"{where}: 눈금끼리·깃발끼리 안 겹침, 막대 밖으로 안 나감",
                "pz-tick" in rows and not hits and not outside,
                f"눈금 {len(rows.get('pz-tick', []))} · 깃발 {len(rows.get('pz-tlflag', []))} · 겹침 {hits[:3] or 0} · 밖 {outside[:3] or 0}")
    # 자 검사: 같은 폭에 앞 판 모양(viewBox 1510 · preserveAspectRatio none)의 글자를 끼워 넣으면 「눌림」
    pg.goto(f"{url}/?view=replay&motion=0&autopause=0&date={date}")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(2000)
    pg.evaluate(TL_PROBE_JS)
    P = pg.evaluate(TL_TEXT_JS, "#pzRbarPlaza .pz-probe")
    pr = [t["ratio"] for t in P]
    C.check(G, "자 검사: 앞 판 모양(viewBox 1510, 비율 무시) 글자를 끼우면 「눌림」",
            len(pr) == 2 and all(r < 0.9 for r in pr), f"배율 {' · '.join(f'{r:.3f}' for r in pr)}")
    ctx.close()


def capture_extra(browser, device, url, url_before, pub: Path, at, snap, prefix: Path):
    """폰 캡처: 대화 패널·최근 이야기 목록, 캐릭터 앞 전(옛 판)·후. 겹치는 자리는 분수 발끝·벤치2 앞자리."""
    P = snap["plaza"]
    shots = []

    def open_(u):
        ctx = browser.new_context(**device, reduced_motion="reduce")
        pg = ctx.new_page()
        pg.clock.install(time=at)
        pg.goto(f"{u}/?mode=now&motion=0")
        pg.wait_for_load_state("networkidle")
        pg.clock.run_for(2000)
        pg.evaluate("document.fonts.ready")
        return ctx, pg
    ctx, pg = open_(url)
    posts = public_texts(pub)
    long_id = next(p["id"] for p in posts.values() if (p.get("body") or "").startswith("호두의 긴 글"))
    aid = posts[long_id]["author"]["id"]
    pg.evaluate("Plaza.zoom.set(2.2, 820, 560)")
    pg.clock.run_for(300)
    out = Path(f"{prefix}_bubbles.png"); pg.screenshot(path=str(out)); shots.append(out)
    pg.evaluate(f"() => {{ const e = document.querySelector('.pz-agent[data-id=\"{aid}\"]'); Plaza.zoom.set(2.5, parseFloat(e.style.left), parseFloat(e.style.top) - 40); }}")
    r = pg.evaluate(FIG_POINT_JS, aid)
    pg.touchscreen.tap(*r)
    pg.clock.run_for(600)
    until(pg, "document.getElementById('pzWho').dataset.ready === '1'")
    pg.evaluate("document.querySelector('#pzWho .pz-ti.hot') && document.querySelector('#pzWho .pz-ti.hot').scrollIntoView({block: 'start'})")
    out = Path(f"{prefix}_panel.png"); pg.screenshot(path=str(out)); shots.append(out)
    pg.click("#pzWhoX")
    pg.evaluate("document.querySelector('.pz-talk').scrollIntoView({block: 'start'})")
    out = Path(f"{prefix}_list.png"); pg.screenshot(path=str(out)); shots.append(out)
    ctx.close()
    ids = [r["id"] for r in P["residents"] if r["bubble"]][:2]
    for tag, u in (("before", url_before), ("after", url)):
        ctx, pg = open_(u)
        pg.evaluate(f"""() => {{ for (const [id, x, y] of {json.dumps([[ids[0], 690, 606], [ids[1], 880, 759]])}) {{
            const f = document.querySelector(`.pz-agent[data-id="${{id}}"]`); f.style.left = x + 'px'; f.style.top = y + 'px'; f.style.zIndex = String(y + 2); }} }}""")
        pg.evaluate("Plaza.zoom.set(2.3, 790, 640)")
        pg.clock.run_for(300)
        out = Path(f"{prefix}_front_{tag}.png"); pg.screenshot(path=str(out)); shots.append(out)
        ctx.close()
    return shots


# ── 1~5. 광장 화면 ──
# ── 9. 아바타 표정 (docs/faces.md) ──
# 화면(web/plaza.js)과 따로 파이썬으로 같은 규칙표(web/faces.json)를 적용한 기대값을 만들어 화면의 표정과 맞춘다
FACE_KEEP = object()   # 이름 바꾸기·소개 바꾸기: 표정 그대로
FACE_PICTURE_CHUNKS = {b"VP8X", b"VP8 ", b"VP8L", b"ALPH"}
IDLE_TO_BENCH_S = 2 * 3600   # plaza.js IDLE_TO_BENCH_MS


def face_key(e: dict):
    t, d = e["type"], e.get("data") or {}
    if t in ("post_created", "thread_opened"):
        return "sitting" if d.get("kind") == "sitting" else "talk"
    simple = {"request_claimed": "claim", "request_unclaimed": "unclaim", "request_delivered": "deliver",
              "request_fetched": "fetch", "request_closed": "close", "agent_joined": "joined", "agent_visited": "visited",
              "agent_left": "left"}
    if t == "request_opened":
        return "return_favor" if d.get("in_return_for") else "request"
    if t == "reaction_added":
        return f"reaction:{d.get('kind')}"
    if t in simple:
        return simple[t]
    if t in ("agent_renamed", "agent_profile_changed"):
        return FACE_KEEP
    return "?" + t


def snap_face_key(r: dict, rows: dict):
    la = r.get("last_action")
    if not la:
        return "joined" if r["zone"] == "arch" else "visited"
    if la["event_id"] in rows:
        return face_key(rows[la["event_id"]])
    icon = (r.get("bubble") or {}).get("icon") or ""
    k = la["kind"]
    if k in ("post", "remark"):
        return "talk"
    if k == "sitting":
        return "sitting"
    if k == "thread_opened":
        return "sitting" if r["zone"] == "cafe" else "talk"
    if k == "reaction_added":
        return "reaction:" + icon[10:] if icon.startswith("reactions/") else "reaction:?"
    if k == "request_opened":
        return "return_favor" if icon == "actions/return_favor" else "request"
    fk = face_key({"type": k})
    return None if fk is FACE_KEEP else fk


def face_seed(s: str) -> int:
    a = 0
    for ch in s:
        a = ((a * 31 + ord(ch) + 2**31) % 2**32) - 2**31   # JS (a * 31 + c) | 0
    return a % 2**32                                      # >>> 0


def pick_face(T: dict, left: bool, dim: bool, key, seed: str):
    for r in T["rules"]:
        if (left if r["when"] == "left" else dim if r["when"] == "dim" else r["when"] == key):
            return r["id"], (r["faces"][face_seed(seed) % len(r["faces"])] if r["faces"] else None)
    return None, None


def face_src(T: dict, character: str, face: str | None) -> str:
    if face:
        return "img/" + T["src"].replace("{character}", character).replace("{face}", face) + f"?v={T['rev']}"
    return f"img/chars/out/{character}.png"


def expect_now(T: dict, snap: dict, rows: dict) -> dict:
    """지금 화면: 거주자마다 (규칙, 표정, 그림 주소)."""
    roster = {a["id"]: a for a in snap["plaza"]["roster"]}
    out = {}
    for r in snap["plaza"]["residents"]:
        ag = roster.get(r["id"]) or {}
        seed = r["last_action"]["event_id"] if r.get("last_action") else r["id"]
        rule, face = pick_face(T, bool(ag) and ag.get("status") != "active", bool(r.get("dim")), snap_face_key(r, rows), seed)
        out[r["id"]] = (rule, face, face_src(T, ag.get("character") or r["character"], face))
    return out


def expect_replay(T: dict, events: list[dict], t: dt.datetime, roster: dict) -> dict:
    """리플레이 시각 t: 그날 행을 t 까지 적용한 표정. 2시간 행 없는 에이전트는 벤치에서 존다(연출 규칙, dim)."""
    st: dict[str, dict] = {}
    for e in events:
        at = dt.datetime.fromisoformat(e["at"])
        if at > t:
            break
        a = e.get("actor")
        if not a or a in ("operator", "server"):
            continue
        s = st.setdefault(a, {"key": None, "seed": None, "acted": False, "left": False, "last": at})
        s["last"] = at
        k = face_key(e)
        if k is FACE_KEEP or (k == "visited" and s["acted"]):
            continue
        if k == "left":
            s["left"] = True
            continue
        s["key"], s["seed"] = k, e["id"]
        if k not in ("visited", "joined"):
            s["acted"] = True
    out = {}
    for a, s in st.items():
        dim = (t - s["last"]).total_seconds() > IDLE_TO_BENCH_S
        rule, face = pick_face(T, s["left"], dim, s["key"], s["seed"] or a)
        out[a] = (rule, face, face_src(T, (roster.get(a) or {}).get("character") or "cat", face))
    return out


def face_diff(want: dict, got: list[dict]) -> list[str]:
    g = {x["id"]: x for x in got}
    bad = []
    for a, (rule, face, src) in want.items():
        x = g.get(a)
        if not x or (x["face"] or None) != face or x["src"] != src or (x["rule"] or None) != rule:
            bad.append(f"{a[-4:]}: 기대 {rule}/{face} · 화면 {x and x['rule']}/{x and x['face']}")
    bad += [f"{a[-4:]}: 기대에 없는 캐릭터" for a in g if a not in want]
    return bad


def face_page(browser, url, q, when, errs, reqs=None):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    if reqs is not None:
        pg.on("request", lambda r: reqs.append(r.url))
    pg.clock.install(time=when)
    pg.goto(f"{url}/?{q}")
    pg.wait_for_load_state("networkidle")
    pg.clock.run_for(1500)
    return ctx, pg


def faces_now(browser, url, when, errs, reqs=None) -> tuple[list[dict], dict]:
    ctx, pg = face_page(browser, url, "mode=now&motion=0", when, errs, reqs)
    until(pg, "Plaza.stats().facesPending === 0 && [...document.images].every((i) => i.complete)", tries=60)
    pg.clock.run_for(200)
    st = pg.evaluate("Plaza.stats()")
    loaded = pg.evaluate("[...document.querySelectorAll('#pzFigures .pz-body')].every((b) => b.complete && b.naturalWidth > 0)")
    ctx.close()
    return st["faces"], {"loaded": loaded, "table": st.get("faceTable")}


def synth_day(date: str, roster: list[dict], req_id: str) -> dict:
    """모든 표정 규칙과 모르는 종류를 한 번씩 지나는 지어낸 하루. 사람은 명단의 에이전트를 돌려 쓴다.
    부탁 행의 subject 는 시험 데이터에 있는 부탁 하나(없는 부탁 id 면 화면이 글을 찾으러 가 404 를 받는다)."""
    ids = [a["id"] for a in roster]
    plan = [   # (에이전트 번호, type, data)
        (0, "agent_joined", {}), (1, "agent_visited", {}),
        (0, "post_created", {"kind": "remark"}), (2, "post_created", {"kind": "post"}), (3, "post_created", {"kind": "remark"}),
        (0, "agent_visited", {}),                                   # 말한 뒤 방문: 표정 그대로
        (4, "post_created", {"kind": "sitting"}), (5, "thread_opened", {"kind": "sitting"}), (6, "thread_opened", {"kind": "story"}),
        (1, "request_opened", {"to": None, "in_return_for": None}), (2, "request_opened", {"to": None, "in_return_for": "rq_x"}),
        (3, "request_claimed", {}), (3, "request_unclaimed", {"cause": "self"}), (7, "request_delivered", {}),
        (8, "request_fetched", {}), (1, "request_closed", {"reason": "done", "cause": "self"}),
        (4, "reaction_added", {"kind": "agree"}), (5, "reaction_added", {"kind": "rebut"}), (6, "reaction_added", {"kind": "thanks"}),
        (7, "reaction_added", {"kind": "repro_ok"}), (8, "reaction_added", {"kind": "repro_fail"}),
        (9, "reaction_added", {"kind": "wow"}),                     # 모르는 반응 → 기본 그림
        (10, "agent_waved", {}),                                    # 모르는 사건 종류 → 기본 그림
        (2, "agent_renamed", {"from": "a", "to": "b"}),             # 표정 그대로
        (0, "agent_left", {"mode": "keep"}),                        # 떠난 이웃 → 기본 그림
    ]
    t0 = dt.datetime.fromisoformat(f"{date}T01:00:00+09:00")
    zone = {"post_created": "fountain", "thread_opened": "board", "reaction_added": "fountain", "agent_joined": "arch", "agent_left": "arch"}
    events = []
    for i, (who_, typ, data) in enumerate(plan):
        a = ids[who_ % len(ids)]
        events.append({"id": f"ev_face{i:02d}", "type": typ, "at": (t0 + dt.timedelta(minutes=7 * i)).isoformat(), "actor": a,
                       "subject": req_id if typ.startswith("request_") else a, "data": data, "nickname": None, "zone": zone.get(typ, "market" if typ.startswith("request_") else None),
                       "bubble": None})
    return {"schema": 1, "date": date, "tz": "+09:00", "final": True, "generated": t0.isoformat(), "events": events, "scenes": [],
            "counts": {"bubbles": 0, "bubble_rows": 0}}


def synth_snapshot(snap: dict) -> dict:
    """스냅샷 쪽 대체 경로(원장 행을 못 찾을 때): 거주자마다 last_action 종류를 바꾸고 event_id 는 없는 값으로."""
    s = json.loads(json.dumps(snap))
    kinds = [("remark", "fountain", None), ("sitting", "cafe", None), ("thread_opened", "cafe", None), ("thread_opened", "board", None),
             ("reaction_added", "fountain", "reactions/rebut"), ("reaction_added", "fountain", None),
             ("request_opened", "market", "actions/return_favor"), ("request_opened", "market", None),
             ("request_claimed", "market", None), ("mystery_kind", "market", None), (None, "bench", None)]
    for i, r in enumerate(s["plaza"]["residents"]):
        kind, zone, icon = kinds[i % len(kinds)]
        r.update(zone=zone, dim=kind is None, bubble={"icon": icon, "event_id": f"ev_nope{i}"} if icon else None,
                 last_action={"kind": kind, "at": s["generated"], "event_id": f"ev_nope{i}"} if kind else None)
    return s


def face_checks(C: Checks, browser, args, work: Path, data: Path, url: str, at: dt.datetime, snap: dict, errs: list):
    G = "아바타 표정"
    T = json.loads((REPO / "web" / "faces.json").read_text(encoding="utf-8"))
    rows = {e["id"]: e for p in sorted((data / "replay").glob("20*.json")) for e in json.loads(p.read_text(encoding="utf-8"))["events"]}
    roster = {a["id"]: a for a in snap["plaza"]["roster"]}

    # 그림: 규칙표가 쓰는 표정 × 30명 전부, 240×240 WebP, 그림 청크 말고 없음(EXIF·XMP·ICC·C2PA), rev = 그림 해시
    pool = [c["id"] for c in json.loads((REPO / "images/gemini/chars/pool.json").read_text(encoding="utf-8"))["pool"]]
    used = sorted({f for r in T["rules"] for f in r["faces"]})
    fdir = REPO / "images/gemini/faces"
    files = sorted(fdir.glob("*/*.webp"))
    want_files = sorted(fdir / c / f"{f}.webp" for c in pool for f in used)
    extra_chunks, sizes = [], set()
    h = hashlib.sha256()
    for p in files:
        b = p.read_bytes()
        i = 12
        while i + 8 <= len(b):
            tag, n = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], "little")
            if tag not in FACE_PICTURE_CHUNKS:
                extra_chunks.append(f"{p.parent.name}/{p.name}:{tag.decode('latin-1')}")
            i += 8 + n + (n & 1)
        sizes.add(Image.open(p).size)
        h.update(p.relative_to(fdir).as_posix().encode() + b"\0" + b)
    total = sum(p.stat().st_size for p in files)
    C.check(G, "표정 그림 = 규칙표의 표정 × 캐릭터 30명, 240×240 WebP, 그림 청크 말고 없음, rev = 그림 해시",
            files == want_files and sizes == {(T["size"], T["size"])} and not extra_chunks and h.hexdigest()[:10] == T["rev"],
            f"{len(files)}장 (기대 {len(want_files)}) · {total / 1024:.0f}KB · 크기 {sorted(sizes)} · 그림 아닌 청크 {extra_chunks[:3] or 0} · rev {T['rev']}")
    probe = fdir / "cat" / f"{used[0]}.webp"
    tmp = work / "exif_probe.webp"
    Image.open(probe).save(tmp, "WEBP", exif=b"Exif\x00\x00MM\x00*\x00\x00\x00\x08\x00\x00")
    tags = []
    b = tmp.read_bytes()
    i = 12
    while i + 8 <= len(b):
        n = int.from_bytes(b[i + 4:i + 8], "little")
        tags.append(b[i:i + 4])
        i += 8 + n + (n & 1)
    C.check(G, "자 검사: EXIF 를 붙여 쓴 WebP 는 「그림 아닌 청크」로 잡힌다", b"EXIF" in tags, " ".join(t.decode("latin-1") for t in tags))

    # 지금 화면 (시험 데이터 그대로): 거주자마다 기대 표정, 불러온 그림 = 화면에 보이는 표정뿐(지연 로드)
    reqs: list[str] = []
    got, meta = faces_now(browser, url, at, errs, reqs)
    want = expect_now(T, snap, rows)
    bad = face_diff(want, got)
    shown = sorted({x["face"] for x in got if x["face"]})
    C.check(G, "지금 화면: 거주자마다 규칙표대로 (마지막 행동 → 표정, 쉬는 중 → 수면, 새 입주 → 인사) · 그림이 실제로 뜸",
            not bad and meta["loaded"] and got,
            f"{len(got)}명 · 틀림 {bad[:3] or 0} · 보인 표정 {', '.join(shown)} · 규칙 {', '.join(sorted({x['rule'] or '-' for x in got}))}")
    face_reqs = sorted({u.split("/img/")[1].split("?")[0] for u in reqs if "/img/faces/" in u})
    want_reqs = sorted({v[2].split("img/")[1].split("?")[0] for v in want.values() if v[1]})
    C.check(G, "지연 로드: 부른 표정 그림 = 지금 화면에 보이는 표정뿐 (390장 중)", face_reqs == want_reqs,
            f"부름 {len(face_reqs)}장 · 보이는 표정 {len(want_reqs)}장")
    T2 = json.loads(json.dumps(T))
    for r in T2["rules"]:
        if r["id"] in ("talk", "sitting"):
            r["faces"] = r["faces"][::-1] if len(r["faces"]) > 1 else ["10_no"]
    C.check(G, "자 검사: 규칙표를 바꾼 기대값(한마디 표정 순서 뒤집기·마주 앉기 → NO)은 「틀림」", face_diff(expect_now(T2, snap, rows), got),
            f"틀림 {len(face_diff(expect_now(T2, snap, rows), got))}명")

    # 원장 행을 못 찾을 때(스냅샷 칸만): 종류·말풍선 아이콘·구역으로. 모르는 종류·아이콘 없는 반응은 기본 그림
    s2 = synth_snapshot(snap)
    site2 = plaza_site(work / "site_faces_snap", data, s2)
    url2, srv2 = serve(site2)
    got2, meta2 = faces_now(browser, url2, at, errs)
    srv2.shutdown()
    want2 = expect_now(T, s2, {})
    bad2 = face_diff(want2, got2)
    plain = sorted(a[-4:] for a, v in want2.items() if v[1] is None)
    C.check(G, "스냅샷 칸만으로(행 없음): 종류·아이콘·구역 → 표정, 모르는 종류(mystery_kind)·아이콘 없는 반응 → 기본 그림",
            not bad2 and meta2["loaded"] and len(plain) == 2,
            f"{len(got2)}명 · 틀림 {bad2[:3] or 0} · 기본 그림 {len(plain)}명")

    # 리플레이: 지어낸 하루로 모든 규칙·모르는 종류·떠난 이웃, 그리고 시험 데이터 날마다 몇 시각
    synth_date = "2026-09-20"
    site3 = plaza_site(work / "site_faces_replay", data)
    day = synth_day(synth_date, snap["plaza"]["roster"], sorted((data / "requests").glob("rq_*.json"))[0].stem)
    (site3 / "public/replay" / f"{synth_date}.json").write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")
    idx = json.loads((site3 / "public/replay/index.json").read_text(encoding="utf-8"))
    idx["dates"] = [{"date": synth_date, "bubbles": 0, "scenes": 0}] + idx["dates"]
    (site3 / "public/replay/index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    url3, srv3 = serve(site3)
    days = {synth_date: day["events"]}
    for p in sorted((data / "replay").glob("20*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        if j["events"]:
            days[j["date"]] = j["events"]

    def at_times(date, times):
        ctx, pg = face_page(browser, url3, f"view=replay&motion=0&date={date}&autopause=0&speed=1", at, errs)
        pg.evaluate(f"Plaza.replay({{date: '{date}', speed: 1, autopause: false}})")
        res = []
        for t in times:
            pg.evaluate(f"Plaza.seek('{t.isoformat()}')")
            pg.clock.run_for(100)
            until(pg, "Plaza.stats().facesPending === 0", tries=60)
            pg.clock.run_for(100)
            got_t = pg.evaluate("Plaza.stats().faces")
            res.append((t, face_diff(expect_replay(T, days[date], t, roster), got_t), got_t))
        ctx.close()
        return res

    t_syn = [dt.datetime.fromisoformat(e["at"]) + dt.timedelta(seconds=30) for e in day["events"]]
    t_syn.append(dt.datetime.fromisoformat(day["events"][-1]["at"]) + dt.timedelta(hours=3))   # 모두 2시간 넘게 조용함 → 수면, 떠난 이웃은 기본
    res = at_times(synth_date, t_syn)
    bad3 = [f"{t:%H:%M} {b[0]}" for t, b, _ in res if b]
    rules_seen = sorted({x["rule"] or "-" for _, _, g in res for x in g})
    want_rules = sorted({r["id"] for r in T["rules"]} | {"-"})
    C.check(G, f"리플레이 지어낸 하루 {len(res)}개 시각: 행마다 규칙표대로, 모르는 반응·모르는 종류 → 기본, 떠난 이웃 → 기본, 2시간 조용 → 수면",
            not bad3 and rules_seen == want_rules,
            f"틀림 {bad3[:3] or 0} · 거친 규칙 {len(rules_seen) - 1}/{len(want_rules) - 1}")
    probe = sum(len(face_diff(expect_replay(T2, days[synth_date], t, roster), g)) for t, _, g in res)
    C.check(G, "자 검사: 같은 리플레이 시각들에 규칙표를 바꾼 기대값을 대면 「틀림」", probe > 0, f"틀림 {probe}칸")
    last = res[-1][2]
    left_id = day["events"][-1]["actor"]
    lg = next((x for x in last if x["id"] == left_id), None)
    C.check(G, "떠난 이웃: 조용해져도 수면이 아니라 기본 그림 (표정 없음)", lg and lg["face"] is None and lg["rule"] == "left" and "chars/out/" in lg["src"],
            f"{lg and lg['rule']} · {lg and lg['src']}")
    real = []
    for date, evs in days.items():
        if date == synth_date:
            continue
        acts = sorted({dt.datetime.fromisoformat(e["at"]) for e in evs})
        pts = sorted({acts[0] + dt.timedelta(seconds=30), acts[len(acts) // 2] + dt.timedelta(seconds=30), acts[-1] + dt.timedelta(seconds=30),
                      acts[-1] + dt.timedelta(hours=2, minutes=5)})
        pts = [t for t in pts if t.strftime("%Y-%m-%d") == date]
        real += [(date, t, b) for t, b, _ in at_times(date, pts)]
    bad4 = [f"{d} {t:%H:%M} {b[0]}" for d, t, b in real if b]
    C.check(G, f"리플레이 시험 데이터 {len(days) - 1}일 × 시각 {len(real)}개: 그 시각까지의 행으로 정한 표정과 같음", not bad4 and real,
            f"틀림 {bad4[:3] or 0}")
    srv3.shutdown()

    # 자 검사: 표정 앞 판(규칙표·그림 없는 plaza.js)은 같은 기대에서 「틀림」
    before = plaza_site(work / "site_faces_before", data)
    for f in ("plaza.js", "plaza.css"):
        (before / "web" / f).write_text(before_web(args.faces_before, f), encoding="utf-8")
    ub, sb = serve(before)
    ctx, pg = face_page(browser, ub, "mode=now&motion=0", at, [])
    old = pg.evaluate("""() => [...document.querySelectorAll('#pzFigures .pz-agent:not([hidden]) .pz-body')].map((b) =>
        ({id: b.closest('.pz-agent').dataset.id, face: b.dataset.face || null, rule: b.dataset.rule || null, src: b.getAttribute('src')}))""")
    ctx.close()
    sb.shutdown()
    C.check(G, f"자 검사: 표정 앞 판({before_label(args.faces_before)})은 같은 기대에서 「틀림」", len(face_diff(want, old)) == len(want),
            f"틀림 {len(face_diff(want, old))}/{len(want)}명")


def plaza_checks(C: Checks, browser, args, work: Path, extra=(), capture=None):
    data = Path(args.data)
    site = plaza_site(work / "site_plaza", data)
    url, srv = serve(site)
    snap = json.loads((site / "public" / "snapshot.json").read_text(encoding="utf-8"))
    P = snap["plaza"]
    at = dt.datetime.fromisoformat(snap["generated"]).astimezone(KST) + dt.timedelta(minutes=1)
    idx = json.loads((site / "public" / "replay" / "index.json").read_text(encoding="utf-8"))
    want_now = sum(1 for r in P["residents"] if r["bubble"])
    shots = work / "plaza_shots"
    shots.mkdir(exist_ok=True)
    errs_all: list[str] = []
    reqs_all: list[str] = []

    def page(w, h, q, motion=True, base=None, when=None):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  reduced_motion="no-preference" if motion else "reduce")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs_all.append(str(e)))
        pg.on("request", lambda r: reqs_all.append(r.url))
        pg.clock.install(time=when or at)
        pg.goto(f"{base or url}/?{q}")
        pg.wait_for_load_state("networkidle")
        pg.clock.run_for(1500)
        return ctx, pg

    # 2a. 지금 화면: 연출 켬·끔
    counts = {}
    for motion in (True, False):
        ctx, pg = page(1840, 1080, f"mode=now&motion={int(motion)}", motion)
        pg.clock.run_for(8000)
        counts[motion] = pg.evaluate("Plaza.stats()")["bubblesOnStage"]
        pg.screenshot(path=str(shots / f"now_{'on' if motion else 'off'}.png"), full_page=True)
        ctx.close()
    C.check("연출 끄면 말풍선 수 불변", "지금 화면 켬 = 끔 = 스냅샷 residents.bubble 수",
            counts[True] == counts[False] == want_now, f"켬 {counts[True]} · 끔 {counts[False]} · 스냅샷 {want_now}")

    # 2b. 리플레이 하루치를 끝까지: 날짜마다 연출 켬·끔, 자동 일시정지 끔. 시간을 줄이려고 API 로 600×
    def run_day(date, motion, speed, ms):
        ctx, pg = page(1840, 1080, f"view=replay&motion={int(motion)}&date={date}&autopause=0&speed={speed}", motion)
        pg.evaluate(f"Plaza.replay({{date: '{date}', speed: {speed}, autopause: false}})")
        pg.clock.run_for(ms)
        st = pg.evaluate("Plaza.stats()")
        ctx.close()
        return st["emitted"], st["expected"], st["playing"]

    for d in idx["dates"]:
        if not d["bubbles"]:
            continue
        got = {m: run_day(d["date"], m, 600, 150_000) for m in (True, False)}
        ok = got[True][0] == got[False][0] == got[True][1] == d["bubbles"] and not got[True][2] and not got[False][2]
        C.check("연출 끄면 말풍선 수 불변", f"리플레이 {d['date']} 끝까지 (600×)", ok,
                f"켬 {got[True][0]} · 끔 {got[False][0]} · 파일 counts {got[True][1]} · index {d['bubbles']}")
    busiest = max((d for d in idx["dates"] if d["bubbles"]), key=lambda d: d["bubbles"])
    # UI 최고 배속: 60× 버튼을 눌러 벽시계 20초에 리플레이 시계가 20분 가는지 (하루 끝까지는 프레임 9만 개라 600× 로 잰다)
    ctx, pg = page(1840, 1080, f"view=replay&date={busiest['date']}&autopause=0", False)
    pg.click("#pzRbarPlaza [data-rp=speed][data-s='60']")
    t0 = pg.evaluate("Plaza.stats().t")
    pg.clock.run_for(20_000)
    st = pg.evaluate("Plaza.stats()")
    ctx.close()
    adv = (st["t"] - t0) / 1000
    C.check("리플레이", "60× 버튼: 벽시계 20초 = 리플레이 20분", st["playing"] and abs(adv - 1200) <= 30,
            f"리플레이 시계 {adv:.0f}초 전진 (기대 1200)")

    # 2c. 장면 자동 일시정지 켬: 멈춘 횟수 = 그날 장면 시각 수, 말풍선 수는 그대로
    day = json.loads((site / "public" / "replay" / f"{busiest['date']}.json").read_text(encoding="utf-8"))
    ctx, pg = page(1840, 1080, f"view=replay&date={busiest['date']}")
    pg.evaluate(f"Plaza.replay({{date: '{busiest['date']}', speed: 600, autopause: true}})")
    pauses, shot_done = 0, False
    for _ in range(400):
        pg.clock.run_for(1000)
        st = pg.evaluate("Plaza.stats()")
        if st["paused"]:
            pauses += 1
            if not shot_done:
                pg.screenshot(path=str(shots / "replay_scene.png"), full_page=True)
                shot_done = True
            pg.evaluate("Plaza.resume()")
        elif not st["playing"]:
            break
    st = pg.evaluate("Plaza.stats()")
    ctx.close()
    moments = len({c["at"] for c in day["scenes"]})   # 같은 때 난 장면은 한 번에 멈춘다
    C.check("리플레이", f"장면 자동 일시정지 {busiest['date']}", pauses == moments and len(st["pausedScenes"]) == len(day["scenes"])
            and st["emitted"] == day["counts"]["bubbles"],
            f"멈춤 {pauses} = 장면 시각 {moments} · 보인 장면 {len(st['pausedScenes'])}/{len(day['scenes'])} · 말풍선 {st['emitted']}/{day['counts']['bubbles']}")

    # 9. 아바타 표정: 지금 화면·스냅샷 칸만·리플레이 시각별, 앞 판 자 검사
    face_checks(C, browser, args, work, data, url, at, snap, errs_all)

    # 1. 폰 폭: 처음 화면에 광장 전체 + 확대/축소·이동 (Chromium 모바일 에뮬레이션)
    stray_phone = zoom_checks(C, browser, "Chromium 모바일 에뮬레이션", PHONE_DEVICE, url, at, want_now, busiest, shots, errs_all, reqs_all,
                              capture=None if extra else capture)
    for label, br, device in extra:   # WebKit(iPhone) 이 깔려 있으면 같은 판정을 한 벌 더
        zoom_checks(C, br, label, device, url, at, want_now, busiest, shots, errs_all, reqs_all, capture=capture)
    desktop_zoom_checks(C, browser, url, at, errs_all, reqs_all)

    # 6·7·8. 대화 보기 · 캐릭터 앞 · 타임라인 글자: 폰 두 엔진과 데스크톱
    desk = {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1}
    for label, br, dev, phone in [("Chromium 모바일 에뮬레이션", browser, PHONE_DEVICE, True)] + \
            [(l, b, d, True) for l, b, d in extra] + [("데스크톱 Chromium", browser, desk, False)]:
        talk_checks(C, br, label, dev, url, at, site / "public", snap, errs_all, reqs_all, phone)
        front_checks(C, br, label, dev, url, at, snap, errs_all)
        timeline_checks(C, br, label, dev, url, at, busiest["date"], errs_all, phone)
    if args.capture_extra:
        before = plaza_site(work / "site_before", data)
        for f in ("plaza.js", "plaza.css"):
            (before / "web" / f).write_text(before_web(args.front_before, f), encoding="utf-8")
        url_b, srv_b = serve(before)
        br, dev = (extra[0][1], extra[0][2]) if extra else (browser, PHONE_DEVICE)
        for f in capture_extra(br, dev, url, url_b, site / "public", at, snap, Path(args.capture_extra).expanduser()):
            print("캡처", f)
        srv_b.shutdown()

    # 3. 앞 판 흠
    ctx, pg = page(1840, 1080, "mode=now")
    pg.clock.run_for(4000)
    pg.screenshot(path=str(shots / "plaza.png"), full_page=True)
    stray = pg.evaluate(STRAY_JS)
    pg.evaluate(OLD_STRIP)
    stray_probe = pg.evaluate(STRAY_JS)
    speeds = pg.evaluate("[...document.querySelectorAll('#pzRbarWatch [data-rp=speed]')].map(b => b.textContent)")
    ctx.close()
    C.check("앞 판 흠", "광장 아래 프레임 밖 활동 막대 없음 (데스크톱·폰)", not stray and not stray_phone,
            f"데스크톱 {stray or 0} · 폰 {stray_phone or 0}")
    C.check("앞 판 흠", "자 검사: 원본 렌더러의 옛 활동 막대를 끼워 넣으면 「있음」", bool(stray_probe), ", ".join(stray_probe[:3]))
    C.check("앞 판 흠", "리플레이 배속 버튼 = 목업 1×·16×·60×", speeds == ["1×", "16×", "60×"], " ".join(speeds))

    ctx, pg = page(1640, 1000, "view=watch&mode=now")
    pg.clock.run_for(4000)
    pg.screenshot(path=str(shots / "watch.png"), full_page=True)
    texts = pg.evaluate("[...document.querySelectorAll('#pzScenes .pz-t')].map(e => e.textContent)")
    ctx.close()
    nicks = [a["nickname"] for a in P["roster"]]
    bad = [b for t in texts for b in josa_errors(t, nicks)]
    hits = sum(len(re.findall("|".join(map(re.escape, nicks)) + r"(이|가|와|과)", t)) for t in texts)
    C.check("앞 판 흠", "장면 카드 조사가 받침에 맞음 (화면에 그린 카드 전부)", texts and hits and not bad,
            f"카드 {len(texts)} · 닉네임+조사 {hits}곳 · 틀림 {bad or 0}")
    probe = josa_errors("라일락가 도토리와 72시간 · Pebble와 Nova-7가", ["라일락", "도토리", "Pebble", "Nova-7"])
    C.check("앞 판 흠", "자 검사: 「라일락가」「Pebble와」「Nova-7가」를 「틀림」", len(probe) == 3, ", ".join(probe))

    # 4. 결정성: 같은 입력이면 같은 그림 (연출 끔), 생성 시각 1분 차이면 다른 그림
    def still(base, name, when=None):
        ctx, pg = page(1440, 900, "mode=now&motion=0", False, base=base, when=when)
        pg.clock.run_for(2000)
        pg.evaluate("document.fonts.ready")
        # 최근 이야기가 얼굴 그림 수십 장을 더 불러, 같은 그림을 여러 크기로 줄여 그리는 곳에서 몇 점이 흔들렸다(최대 57/255, 줄이는 필터 차이).
        # 그림이 다 받아진 뒤 한 판 더 그리고 찍는다. img.decode() 로 강제로 풀면 오히려 흔들린다(9번 중 2~3번). 깃발 --disable-checker-imaging 과 함께 8/8
        until(pg, "[...document.images].every((i) => i.complete) && Plaza.stats().facesPending === 0", tries=60)
        pg.wait_for_timeout(400)
        pg.clock.run_for(200)
        pg.screenshot(path=str(shots / name), full_page=True)
        ctx.close()
    still(url, "det_a.png")
    still(url, "det_b.png")
    ok0, why0 = same_pixels(shots / "det_a.png", shots / "det_b.png")
    snap2 = json.loads(json.dumps(snap))
    snap2["generated"] = (dt.datetime.fromisoformat(snap["generated"]) + dt.timedelta(minutes=1)).isoformat()
    site2 = plaza_site(work / "site_plaza_probe", data, snap2)
    url2, srv2 = serve(site2)
    still(url2, "det_probe.png")
    ok1, why1 = same_pixels(shots / "det_a.png", shots / "det_probe.png")
    srv2.shutdown()
    C.check("결정성", "같은 스냅샷·같은 시각이면 같은 그림 (연출 끔, 대조군)", ok0, why0)
    C.check("결정성", "자 검사: 생성 시각 1분 차이를 「다름」", not ok1, why1)

    # 입구 버튼
    ctx, pg = page(1840, 1080, "view=plaza&mode=now")
    pg.click("#pzJoin")
    pg.screenshot(path=str(shots / "join.png"))
    line = pg.text_content("#pzJoinLine")
    ctx.close()
    C.check("입구 버튼", "「내 에이전트 데려오기」 → 문서 주소 한 줄", "/join" in (line or ""), line or "")

    host = url.split("//")[1]
    outside = sorted({u for u in reqs_all if host in u and not re.search(rf"{re.escape(host)}/(\?|$|web/|img/|public/)", u)})
    C.check("별개 프로젝트", "화면이 부른 주소는 / · web/ · img/ · public/ 뿐", reqs_all and not outside,
            f"요청 {len(reqs_all)}건 · 밖 {outside[:3] or 0}")
    C.check("페이지 오류", "광장 화면 페이지 오류 0", not errs_all, "; ".join(errs_all[:3]))
    srv.shutdown()
    return shots


def served_checks(C: Checks):
    """2단계 서버가 같이 서빙하는 화면이 리포 web/ 과 같은가 (판번호 자리만 다름)."""
    from .harness import Server
    S = Server()
    S.start()
    try:
        got = {}
        for path, f in (("/", "index.html"), *((f"/web/{f}", f) for f in WEB_CODE)):
            r = S.get(path)
            got[f] = (r.status, r.raw)
        img = S.get("/img/background/agora_bg_gate.png")
        md = S.get("/img/PROMPTS.md")
        face = S.get("/img/faces/cat/01_joy.webp")
    finally:
        S.stop()
    rev = re.search(rb"\?v=([0-9a-f]{10})", got["index.html"][1] or b"")
    # 머리의 검색용 자리: 시험 서버는 자기 주소가 http 라 robots 는 noindex, 소유 확인 설정은 없다(seo_check 가 따로 잰다)
    want_index = ((REPO / "web" / "index.html").read_text(encoding="utf-8").replace("{SITE_URL}", S.base_url)
                  .replace("{ROBOTS}", "noindex").replace("{VERIFY}", "")).encode("utf-8")
    same = all(got[f][0] == 200 for f in WEB_FILES) and rev and \
        got["index.html"][1].replace(b"?v=" + rev.group(1), b"?v=dev") == want_index and \
        all(got[f][1] == (REPO / "web" / f).read_bytes() for f in WEB_CODE)
    want_rev = hashlib.sha256(b"".join((REPO / "web" / f).read_bytes() for f in WEB_CODE)).hexdigest()[:10]
    C.check("서버 서빙", "서버의 / · /web/plaza.js·css·faces.json·board_rules.js = 리포 web/ (판번호 = 코드·표정 규칙표·분류 규칙 해시)",
            same and rev.group(1).decode() == want_rev,
            f"판번호 {rev.group(1).decode() if rev else '없음'} · 기대 {want_rev}")
    C.check("서버 서빙", "그림은 /img/ 로, 그림 아닌 파일은 404", img.status == 200 and md.status == 404,
            f"배경 {img.status} · PROMPTS.md {md.status}")
    ctype = lambda r: (r.headers.get("Content-Type") or "").split(";")[0]   # noqa: E731
    C.check("서버 서빙", "그림 형식 머리글: png → image/png, 표정 webp → image/webp (환경의 mimetypes 에 안 기댄다)",
            face.status == 200 and ctype(face) == "image/webp" and ctype(img) == "image/png",
            f"webp {face.status} {ctype(face)} · png {ctype(img)}")


def square_checks(C: Checks):
    """digest square_new(api.md 7.1)를 공개 문만으로 다시 계산해 맞춘다. 3단계 데이터 시나리오(열한 명·사흘)를
    새 서버에 돌리고, 지목 없는 부탁 둘(하나는 운영자 숨김)을 더한 뒤 모두가 커서 없이 digest 를 부른다.
    기대값은 서버 코드가 아니라 /public/replay·threads·requests 에서 만든다. 걸러야 할 숨김·보류 글이 들어 있다."""
    from . import stage3_data as D
    from .harness import Server
    G = "digest 광장 새 글"
    S = Server()
    S.start()
    try:
        R = D.Run(S)
        D.scenario(R)
        R.at(dt.datetime.now(KST))
        R.request("dot", None, "open1", "아무나: 우산 이름", "비 오는 날 우산 이름 세 개만 지어 주세요.")
        R.request("peb", None, "open2", "아무나: 숨길 부탁", "운영자가 숨길 부탁입니다.")
        R.admin("hide", R.r["open2"], "--reason", "spam")
        C.check(G, "시나리오 완주 (부탁 둘·숨김 포함)", not R.fail, "; ".join(R.fail[:2]))
        evs = [e for d in S.get("/public/replay/index.json")["dates"]
               for e in S.get(f"/public/replay/{d['date']}.json")["events"]]
        pub = S.get("/public/threads.json").json
        body = {p["id"]: p for p in pub["remarks"]}
        for t in pub["threads"]:
            for p in S.get(f"/public/threads/{t['id']}.json")["posts"]:
                body[p["id"]] = p
        titles = {t["id"]: t["title"] for t in pub["threads"]}

        def expect(me, targets, keep_hidden=False):
            i0 = next(k for k, e in enumerate(evs) if e["type"] == "agent_joined" and e["actor"] == me)
            out = []
            for e in evs[i0 + 1:]:
                if e["actor"] == me:
                    continue
                if e["type"] == "post_created" and e["data"]["kind"] == "remark":
                    p = body[e["subject"]]
                    it = ("remark", e["subject"], e["subject"], None, p)
                elif e["type"] == "thread_opened" and e["data"]["kind"] == "story":
                    p = body[e["data"]["first_post"]]
                    it = ("thread", e["subject"], p["id"], titles[e["subject"]], p)
                elif e["type"] == "request_opened" and e["data"]["to"] is None:
                    p = S.get(f"/public/requests/{e['subject']}.json")["request"]
                    it = ("request", e["subject"], None, p["title"], p)
                else:
                    continue
                shown = p.get("visibility", "visible" if p["body"] is not None else "hidden") == "visible"  # 공개 부탁엔 visibility 칸이 없다: 숨김·지움이면 body null
                if (keep_hidden or shown) and (it[2] or it[1]) not in targets:
                    out.append({"type": it[0], "id": it[1], "post_id": it[2], "title": it[3], "at": e["at"],
                                "from": e["actor"], "excerpt": (p["body"] or "")[:200] or None})
            return out[::-1]

        bad, totals, hidden_seen, probe = [], {}, 0, 0
        for n in D.AGENTS:
            d = S.get("/api/v1/me/digest", key=R.key[n])
            sq = (d.json or {}).get("square_new") or {}
            tg = {x["target"] for x in d.get("items") or []}
            want = expect(R.id[n], tg)
            probe += expect(R.id[n], tg, keep_hidden=True) != want
            got = [{"type": x.get("type"), "id": x.get("id"), "post_id": x.get("post_id"), "title": x.get("title"),
                    "at": x.get("at"), "from": (x.get("from") or {}).get("id"), "excerpt": x.get("excerpt")}
                   for x in sq.get("items") or []]
            totals[n] = sq.get("total")
            hidden_seen += sum(1 for x in got if x["id"] in (R.p.get("lx"), R.r["open2"]))
            if got != want[:5] or sq.get("total") != len(want) or sq.get("more") != (len(want) > 5):
                bad.append(f"{n}: 받음 {[x['id'] for x in got]} total {sq.get('total')} · 공개 문 {[x['id'] for x in want[:5]]} {len(want)}")
            er = "nothing_to_me" if want else "nothing_new"
            if d.get("empty_reason") != (None if d.get("items") else er):
                bad.append(f"{n}: empty_reason {d.get('empty_reason')}")
        C.check(G, "열한 명 모두: square_new = 공개 문으로 다시 센 남의 한마디·글타래·지목 없는 부탁 (최근 5개·total·more·excerpt)",
                not bad and any(totals.values()), "; ".join(bad[:3]) or f"total {totals}")
        C.check(G, "숨긴 한마디·숨긴 부탁은 누구의 square_new 에도 없음, 보류 글자도 없음",
                all(v is not None for v in totals.values()) and hidden_seen == 0 and HELD_MARK not in repr([x.json for x in S.log if "/me/digest" in x.path]), "")
        C.check(G, "자 검사: 숨김 거르기를 빼고 센 기대값은 「다름」", probe > 0, f"{probe}명에게서 다름")
    finally:
        S.stop()


def notebook_checks(C: Checks):
    """수첩(api.md 7.2)은 공개 쪽 어디에도 안 나간다. 3단계 데이터 시나리오(열한 명·사흘)를 새 서버에 돌리고,
    모두가 digest 로 한 번 들른 뒤 각자 표식을 박은 수첩을 쓰고 읽는다. 공개 문 전부(스냅샷·리플레이 전 날짜·글타래·
    에이전트·부탁·/)에서 표식 0, 공개 원장 행 수 불변, 각자 digest 에는 자기 표식만 있어야 한다(자 검사)."""
    from . import check_public
    from . import stage3_data as D
    from .harness import Server
    G = "수첩 비공개"
    S = Server()
    S.start()
    try:
        R = D.Run(S)
        D.scenario(R)
        R.at(dt.datetime.now(KST))
        for n in D.AGENTS:
            S.get("/api/v1/me/digest", key=R.key[n])            # 방문 사건은 여기서 먼저 생긴다

        def public_rows():
            idx = S.get("/public/replay/index.json")["dates"]
            return sum(len(S.get(f"/public/replay/{d['date']}.json")["events"]) for d in idx)
        rows0 = public_rows()
        marks = {n: f"수첩표식-{n}-{R.id[n][-6:]}" for n in D.AGENTS}
        put = [S.req("PUT", "/api/v1/me/notebook", body={"body": f"다음엔 {marks[n]} 부터 본다"}, key=R.key[n]).status
               for n in D.AGENTS]
        own = {n: S.get("/api/v1/me/digest", key=R.key[n]).text for n in D.AGENTS}
        rows1 = public_rows()
        outs = check_public.collect(S.url)
        blob = "\n".join(v[2].decode("utf-8", "replace") for v in outs.values()) + S.get("/").text
        leaked = [n for n, m in marks.items() if m in blob or m in S.get("/join").text]
        C.check(G, "열한 명 수첩 쓰기 200", put == [200] * len(D.AGENTS), str(put))
        C.check(G, "공개 문 전부(스냅샷·리플레이 전 날짜·글타래·에이전트·부탁·/·/join)에 수첩 표식 0·notebook 칸 0",
                bool(outs) and not leaked and '"notebook"' not in blob, f"{len(outs)}개 응답 · 샌 표식 {leaked}")
        C.check(G, "수첩 쓰기·읽기 전후 공개 원장 행 수 같음 (사건을 안 만든다)", rows0 == rows1 and rows0 > 0,
                f"{rows0} → {rows1}")
        wrong = [n for n in D.AGENTS if marks[n] not in own[n] or any(marks[o] in own[n] for o in D.AGENTS if o != n)]
        C.check(G, "자 검사: 각자 digest notebook 에는 자기 표식만 있음 (같은 자로 잡힌다)", not wrong, str(wrong))
    finally:
        S.stop()


def compare_image(shots: Path, out: Path):
    """왼쪽 목업, 오른쪽 실제 렌더. 광장 한 쌍 + 계기판 한 쌍."""
    mock = REPO / "docs" / "screenshots"
    pairs = [(mock / "sample_plaza.png", shots / "plaza.png", "광장"), (mock / "sample_watch.png", shots / "watch.png", "계기판")]
    W = 1840
    try:
        font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 30)
    except OSError:
        font = ImageFont.load_default()
    tiles = []
    for m, a, label in pairs:
        for src, cap in ((m, f"목업 · {label} (docs/screenshots)"),
                         (a, f"실제 렌더 · {label} (agora-smallvillage web/, 2단계 서버가 낸 스냅샷 2)")):
            im = Image.open(src).convert("RGB")
            if im.width != W:
                im = im.resize((W, round(im.height * W / im.width)))
            if im.height > 1300:
                im = im.crop((0, 0, W, 1300))
            tile = Image.new("RGB", (W, im.height + 50), "#fbf5ea")
            ImageDraw.Draw(tile).text((16, 8), cap, fill="#4a3b2f", font=font)
            tile.paste(im, (0, 50))
            tiles.append(tile)
    rows = [tiles[0:2], tiles[2:4]]
    height = sum(max(t.height for t in r) for r in rows) + 20 * len(rows)
    canvas = Image.new("RGB", (W * 2 + 20, height), "#e6d8c3")
    y = 0
    for r in rows:
        for i, t in enumerate(r):
            canvas.paste(t, (i * (W + 20), y))
        y += max(t.height for t in r) + 20
    canvas = canvas.resize((canvas.width // 2, canvas.height // 2), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out


def report(C: Checks, path: Path, meta: dict):
    lines = ["# 3단계 렌더러 판정 결과 (독립 렌더러)", "",
             f"`python3 -m server.tests.stage3_check` 가 {meta['at']} 에 헤드리스 {meta['engines']} 로 잰 결과다. "
             f"화면 = 리포 `web/`, 데이터 = `{meta['data']}`"
             + (f", 원본 렌더러 기준 커밋 `{meta['base']}`" if meta.get("base") else "") + ".", "",
             f"판정 {sum(r['ok'] for r in C.rows)}/{len(C.rows)} 통과.", "", "| 조건 | 판정 | 결과 | 값 |", "|---|---|---|---|"]
    for r in C.rows:
        lines.append(f"| {r['group']} | {r['name']} | {'통과' if r['ok'] else '**실패**'} | {r['detail'].replace('|', '/')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--office", help="원본 렌더러 리포 경로. 주면 그 리포가 --office-base 와 diff 0 인지도 잰다")
    ap.add_argument("--office-base")
    ap.add_argument("--report")
    ap.add_argument("--compare")
    ap.add_argument("--capture", nargs=2, metavar=("FIT.png", "ZOOM.png"), help="폰 캡처 두 장 (처음 전체 보기, 확대)")
    ap.add_argument("--no-webkit", action="store_true")
    ap.add_argument("--capture-extra", metavar="PREFIX", help="폰 캡처: PREFIX_bubbles·_panel·_list·_front_before·_front_after.png")
    ap.add_argument("--front-before", default=str(BEFORE_DIR / "front_c87d9f3"),
                    help="캐릭터 앞 「전」 캡처에 쓸 옛 판 (plaza.js·plaza.css 가 든 폴더, 또는 이 리포의 커밋)")
    ap.add_argument("--faces-before", default=str(BEFORE_DIR / "faces_b0af64d"),
                    help="아바타 표정 자 검사에 쓸 표정 앞 판 (폴더 또는 이 리포의 커밋)")
    a = ap.parse_args(argv)
    work = Path(a.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    C = Checks()
    print("── 별개 프로젝트 ──")
    separate_checks(C, a)
    print("── 서버 서빙 ──")
    served_checks(C)
    print("── digest 광장 새 글 ──")
    square_checks(C)
    print("── 수첩 비공개 ──")
    notebook_checks(C)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=DET_FLAGS)
        extra, wk = [], None
        if not a.no_webkit:
            try:
                wk = p.webkit.launch()
                dev = {k: v for k, v in p.devices["iPhone 13"].items() if k != "default_browser_type"}
                extra.append((f"WebKit {wk.version} iPhone 13", wk, dev))
            except Exception as e:   # 안 깔려 있으면 Chromium 모바일 에뮬레이션만. 보고서에 그렇게 적힌다
                print(f"  WebKit 못 띄움 — Chromium 모바일 에뮬레이션만: {str(e).splitlines()[0]}")
        engines = ["Chromium " + browser.version] + [e[0] for e in extra]
        print("── 광장 ──", " · ".join(engines))
        capture = [Path(x).expanduser() for x in a.capture] if a.capture else None
        shots = plaza_checks(C, browser, a, work, extra, capture)
        browser.close()
        if wk:
            wk.close()
    if a.compare:
        print("비교 캡처", compare_image(shots, Path(a.compare).expanduser()))
    if a.report:
        report(C, Path(a.report), {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "base": a.office_base if a.office else None, "data": a.data,
                                   "engines": " · ".join(engines)})
    bad = [r for r in C.rows if not r["ok"]]
    print(f"판정 {len(C.rows) - len(bad)}/{len(C.rows)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
