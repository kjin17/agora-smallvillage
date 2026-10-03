"""검색 노출 검사: robots.txt · sitemap.xml · 관전 화면 머리(메타·OG·canonical) · X-Robots-Tag · 소유 확인.

  python3 -m server.tests.seo_check                       # 임시 서버 둘(https 주소 / 터널 주소)을 띄워 잰다
  python3 -m server.tests.with_ua server.tests.seo_check --url https://plaza.example.com   # 떠 있는 공개 서버

판정 함수는 응답 글자만 받는 순수 함수라, 일부러 틀린 입력(API 를 안 막는 robots, 바깥 주소가 섞인 sitemap,
내부 경로가 박힌 메타)을 넣어 실패를 내는지도 같이 잰다(통과만 내는 자도 부러진 자)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from .check_public import secret_patterns
from .harness import Checks, Server

PAGES = {"/", "/join"}                     # 검색에 내놓는 공개 페이지 (app.py SEO_PAGES)
MUST_BLOCK = ["/api/", "/api/v1/agents", "/api/v1/me", "/public/report"]
MUST_ALLOW = ["/", "/join", "/web/plaza.js", "/img/promo/og_card_1200x630.jpg", "/public/snapshot.json",
              "/llms.txt", "/.well-known/agent-card.json"]          # 에이전트 입구도 크롤러에 열어 둔다
# 메타에 있으면 안 되는 내부 정보: guard.md 의 비밀 모양 전부 + 원점·운영 흔적
INTERNAL = [("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")), ("home_path", re.compile(r"/Users/|/home/|~/\.")),
            ("tunnel_port", re.compile(r":18765|127\.0\.0\.1")),
            ("placeholder", re.compile(r"\{(SITE_URL|ROBOTS|VERIFY)\}|\?v=dev"))]


# ── robots.txt 해석 (가장 긴 일치 규칙이 이긴다, Google 방식) ──
def robots_rules(text: str) -> list[tuple[str, str]]:
    rules, in_star = [], False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (s.strip() for s in line.split(":", 1))
        if k.lower() == "user-agent":
            in_star = v == "*"
        elif in_star and k.lower() in ("allow", "disallow") and v:
            rules.append((k.lower(), v))
    return rules


def robots_allows(text: str, path: str) -> bool:
    best = ("allow", "")
    for kind, prefix in robots_rules(text):
        if path.startswith(prefix) and (len(prefix) > len(best[1]) or (len(prefix) == len(best[1]) and kind == "allow")):
            best = (kind, prefix)
    return best[0] == "allow"


def judge_robots(text: str, base: str, indexable: bool = True) -> list[str]:
    bad = []
    if not indexable:
        return [] if not robots_allows(text, "/") else ["색인 끈 서버인데 / 를 허용"]
    bad += [f"막아야 할 {p} 를 허용" for p in MUST_BLOCK if robots_allows(text, p)]
    bad += [f"열어야 할 {p} 를 막음" for p in MUST_ALLOW if not robots_allows(text, p)]
    if f"Sitemap: {base}/sitemap.xml" not in text:
        bad.append("Sitemap 줄이 자기 주소가 아님")
    return bad


def judge_sitemap(text: str, base: str) -> list[str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"XML 아님: {e}"]
    locs = [e.text or "" for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    bad = [f"바깥 주소 {u}" for u in locs if not u.startswith(base + "/")]
    paths = {u[len(base):] for u in locs if u.startswith(base + "/")}
    bad += [f"공개 페이지 아닌 경로 {p}" for p in sorted(paths - PAGES)]
    bad += [f"빠진 공개 페이지 {p}" for p in sorted(PAGES - paths)]
    return bad


def head_of(html: str) -> str:
    return html.split("</head>", 1)[0]


def meta(head: str, attr: str, name: str) -> str | None:
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', head)
    return m.group(1) if m else None


def judge_head(html: str, base: str, indexable: bool = True) -> list[str]:
    h, bad = head_of(html), []
    robots = meta(h, "name", "robots") or ""
    if indexable and "noindex" in robots:
        bad.append(f"robots 메타가 noindex: {robots}")
    if not indexable and "noindex" not in robots:
        bad.append("색인 끈 서버인데 noindex 가 없다")
    if not re.search(r"<title>[^<]{4,}</title>", h):
        bad.append("title 없음")
    for attr, name in (("name", "description"), ("property", "og:title"), ("property", "og:description"),
                       ("property", "og:image"), ("property", "og:url"), ("name", "twitter:card")):
        if not meta(h, attr, name):
            bad.append(f"{name} 없음")
    if f'<link rel="canonical" href="{base}/">' not in h:
        bad.append("canonical 이 자기 주소가 아님")
    for name in ("og:image", "og:url"):
        v = meta(h, "property", name) or ""
        if v and not v.startswith(base + "/"):
            bad.append(f"{name} 가 바깥 주소 {v}")
    if not re.search(r'plaza\.(js|css)\?v=[0-9a-f]{10}"', html):
        bad.append("정적 판번호가 해시로 안 바뀜")
    texts = re.findall(r'content="([^"]*)"|href="([^"]*)"|<title>([^<]*)</title>', h)
    flat = " ".join(x for t in texts for x in t if x).replace(base, "BASE")
    for reason, pat in INTERNAL + secret_patterns():
        if reason in ("url", "domain", "link", "external_link"):
            continue        # 자기 주소는 위에서 BASE 로 바꿨다. 남은 바깥 주소는 og 판정이 잡는다
        if pat.search(flat):
            bad.append(f"머리에 내부/비밀 모양 {reason}")
    return sorted(set(bad))


# ── 에이전트 입구: llms.txt · A2A 에이전트 카드 ──
CARD_REQUIRED = ("name", "description", "supportedInterfaces", "version", "capabilities",
                 "defaultInputModes", "defaultOutputModes", "skills")            # A2A 1.0 AgentCard 필수 칸
SKILL_REQUIRED = ("id", "name", "description", "tags")


def judge_llms(text: str, site: str) -> list[str]:
    bad = []
    if not text.startswith("# "):
        bad.append("첫 줄이 H1 이 아님 (llms.txt 형식)")
    if f"{site}/join" not in text:
        bad.append("가입 안내 /join 링크가 대표 주소가 아님")
    if re.search(r"\{(SITE_URL|BASE_URL)\}", text):
        bad.append("안 채운 자리")
    for reason, pat in INTERNAL[:3]:
        if pat.search(text.replace(site, "SITE")):
            bad.append(f"내부 모양 {reason}")
    return bad


def judge_card(text: str, site: str) -> list[str]:
    try:
        card = json.loads(text)
    except ValueError as e:
        return [f"JSON 아님: {e}"]
    bad = [f"필수 칸 {k} 없음" for k in CARD_REQUIRED if k not in card]
    for i, sk in enumerate(card.get("skills") or []):
        bad += [f"skills[{i}].{k} 없음" for k in SKILL_REQUIRED if not sk.get(k)]
    if not card.get("skills"):
        bad.append("skills 가 비었다")
    for it in card.get("supportedInterfaces") or [{}]:
        if not all(it.get(k) for k in ("url", "protocolBinding", "protocolVersion")):
            bad.append("supportedInterfaces 칸이 모자람")
        elif not it["url"].startswith("http"):
            bad.append("interface url 이 절대 주소가 아님")
    if card.get("documentationUrl") != f"{site}/join":
        bad.append("documentationUrl 이 대표 주소의 /join 이 아님")
    for reason, pat in INTERNAL:
        if pat.search(text.replace(site, "SITE")):
            bad.append(f"내부 모양 {reason}")
    return bad


# ── HTTP ──
def fetch(url: str, ua: str | None = None) -> tuple[int, dict, str]:
    rq = urllib.request.Request(url, headers={"User-Agent": ua} if ua else {})
    try:
        with urllib.request.urlopen(rq, timeout=20) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode("utf-8", "replace")


def judge_server(C: Checks, url: str, base: str, indexable: bool, tag: str):
    st, hd, robots = fetch(url + "/robots.txt")
    C.check(f"[{tag}] robots.txt 200 text/plain", st == 200 and hd.get("content-type", "").startswith("text/plain"), f"{st}")
    bad = judge_robots(robots, base, indexable)
    C.check(f"[{tag}] robots.txt: API·신고 막고 공개 페이지·렌더 자료 열기" if indexable else f"[{tag}] robots.txt: 전면 금지",
            not bad, "; ".join(bad))
    st, hd, sm = fetch(url + "/sitemap.xml")
    C.check(f"[{tag}] sitemap.xml 200 xml", st == 200 and "xml" in hd.get("content-type", ""), f"{st}")
    if indexable:
        bad = judge_sitemap(sm, base)
        C.check(f"[{tag}] sitemap: 공개 페이지({', '.join(sorted(PAGES))})만, 자기 주소로", not bad, "; ".join(bad))
    else:
        C.check(f"[{tag}] sitemap: 색인 끈 서버는 빈 목록", "<loc>" not in sm)
    st, hd, html = fetch(url + "/")
    bad = judge_head(html, base, indexable)
    C.check(f"[{tag}] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음", st == 200 and not bad,
            "; ".join(bad))
    if indexable:
        img = (meta(head_of(html), "property", "og:image") or "").replace(base, url)
        st, hd, _ = fetch(img) if img.startswith(url) else (0, {}, "")
        C.check(f"[{tag}] og:image 가 실제 그림", st == 200 and hd.get("content-type", "").startswith("image/"), f"{st} {img[len(url):]}")
    st, hd, _ = fetch(url + "/join")
    C.check(f"[{tag}] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더",
            st == 200 and ("noindex" not in hd.get("x-robots-tag", "")) == indexable
            and hd.get("link") == f'<{base}/join>; rel="canonical"', f"{st} {hd.get('x-robots-tag')} {hd.get('link')}")
    st, hd, txt = fetch(url + "/llms.txt")
    bad = judge_llms(txt, base) if st == 200 else []
    C.check(f"[{tag}] /llms.txt: 200 text/plain, /join 은 대표 주소", st == 200 and hd.get("content-type", "").startswith("text/plain")
            and not bad, f"{st} {hd.get('content-type')} " + "; ".join(bad))
    cards = []
    for p in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
        st, hd, txt = fetch(url + p)
        bad = judge_card(txt, base) if st == 200 else []
        cards.append(txt)
        C.check(f"[{tag}] {p}: 200 JSON, A2A 필수 칸", st == 200 and hd.get("content-type", "").startswith("application/json")
                and not bad, f"{st} {hd.get('content-type')} " + "; ".join(bad))
    C.check(f"[{tag}] A2A 카드 새 경로·옛 경로가 같은 내용", len(set(cards)) == 1)
    for p in ("/api/v1/characters", "/public/snapshot.json"):
        st, hd, _ = fetch(url + p)
        C.check(f"[{tag}] {p}: X-Robots-Tag noindex", st == 200 and hd.get("x-robots-tag") == "noindex", f"{st} {hd.get('x-robots-tag')}")


def rulers(C: Checks, base: str):
    """자 검사: 일부러 틀린 입력에 판정이 실패를 내는가."""
    good_robots = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /public/report\n\nSitemap: {base}/sitemap.xml\n"
    C.check("자 검사: 옳은 robots 는 통과", not judge_robots(good_robots, base))
    C.check("자 검사: API 를 안 막는 robots 는 실패", bool(judge_robots(good_robots.replace("Disallow: /api/\n", ""), base)))
    C.check("자 검사: /public/ 을 통째로 막은 robots 는 실패(관전 화면 렌더가 빈다)",
            bool(judge_robots(good_robots + "Disallow: /public/\n", base)))
    C.check("자 검사: 다른 봇 묶음의 Disallow 는 * 에 안 섞인다",
            bool(judge_robots("User-agent: Googlebot\nDisallow: /api/\n" + good_robots.replace("Disallow: /api/\n", ""), base)))
    sm = (f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}/</loc></url>'
          f'<url><loc>{base}/join</loc></url>__</urlset>')
    C.check("자 검사: 옳은 sitemap 은 통과", not judge_sitemap(sm.replace("__", ""), base))
    C.check("자 검사: API 경로가 섞인 sitemap 은 실패",
            bool(judge_sitemap(sm.replace("__", f"<url><loc>{base}/api/v1/agents</loc></url>"), base)))
    C.check("자 검사: 바깥(원점 IP) 주소가 섞인 sitemap 은 실패",
            bool(judge_sitemap(sm.replace("__", "<url><loc>http://10.0.0.12/</loc></url>"), base)))
    head = (f'<head><meta name="robots" content="index, follow"><title>에이전트 광장</title>'
            f'<meta name="description" content="d"><link rel="canonical" href="{base}/">'
            f'<meta property="og:title" content="t"><meta property="og:description" content="d">'
            f'<meta property="og:image" content="{base}/img/a.jpg"><meta property="og:url" content="{base}/">'
            f'<meta name="twitter:card" content="summary_large_image">__</head><script src="web/plaza.js?v=0123456789"></script>')
    C.check("자 검사: 옳은 머리는 통과", not judge_head(head.replace("__", ""), base), str(judge_head(head.replace("__", ""), base)))
    for bad, why in (('<meta name="x" content="/Users/someone/plaza">', "맥 경로"),
                     ('<meta name="x" content="origin 10.0.0.12">', "IP"),
                     ('<meta name="x" content="sk-ant-abcdefghijklmnopqrstu">', "키 모양"),
                     ('<meta name="x" content="{SITE_URL}">', "안 채운 자리")):
        C.check(f"자 검사: 머리에 {why}가 있으면 실패", bool(judge_head(head.replace("__", bad), base)))
    llms = f"# Plaza\n\n- [Join]({base}/join)\n"
    C.check("자 검사: 옳은 llms.txt 는 통과", not judge_llms(llms, base))
    C.check("자 검사: 안 채운 자리가 남은 llms.txt 는 실패", bool(judge_llms(llms + "{BASE_URL}/api\n", base)))
    C.check("자 검사: /join 이 다른 주소인 llms.txt 는 실패", bool(judge_llms(llms.replace(base, "https://other.example"), base)))
    card = {"name": "p", "description": "d", "version": "1", "capabilities": {}, "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"], "documentationUrl": f"{base}/join",
            "supportedInterfaces": [{"url": f"{base}/api/v1", "protocolBinding": "PLAZA-REST", "protocolVersion": "1.0"}],
            "skills": [{"id": "join", "name": "j", "description": "d", "tags": ["t"]}]}
    C.check("자 검사: 옳은 카드는 통과", not judge_card(json.dumps(card), base), str(judge_card(json.dumps(card), base)))
    C.check("자 검사: JSON 이 아닌 카드는 실패", bool(judge_card("{", base)))
    C.check("자 검사: skills 가 빠진 카드는 실패", bool(judge_card(json.dumps({**card, "skills": []}), base)))
    C.check("자 검사: tags 없는 skill 은 실패",
            bool(judge_card(json.dumps({**card, "skills": [{"id": "a", "name": "b", "description": "c"}]}), base)))
    C.check("자 검사: 원점 IP 가 든 카드는 실패",
            bool(judge_card(json.dumps({**card, "supportedInterfaces": [{"url": "http://10.0.0.12:18765/api/v1",
                                                                          "protocolBinding": "x", "protocolVersion": "1.0"}]}), base)))
    C.check("자 검사: noindex 가 남은 머리는 실패",
            bool(judge_head(head.replace("index, follow", "noindex").replace("__", ""), base)))


def verify_file_checks(C: Checks, tmp: str):
    """소유 확인 자리: 설정 파일의 모양 좁은 값만 붙고, 이상한 이름·값은 버린다."""
    vf = os.path.join(tmp, "site_verification.json")
    with open(vf, "w") as f:
        json.dump({"meta": {"google-site-verification": "abcDEF123_-xyz", "naver-site-verification": "0123456789abcdef",
                            "evil": "zzzzzzzzzz", "msvalidate.01": '"><script>alert(1)</script>'},
                   "files": {"google0123456789abcdef.html": "google-site-verification: google0123456789abcdef.html",
                             "../etc/passwd": "x"}}, f)
    os.environ["PLAZA_SITE_VERIFY_FILE"] = vf
    try:
        S = Server(base_url="https://plaza.example.test").start()
    finally:
        del os.environ["PLAZA_SITE_VERIFY_FILE"]
    try:
        _, _, html = fetch(S.url + "/")
        h = head_of(html)
        C.check("소유 확인: 허용된 메타 둘은 붙는다",
                meta(h, "name", "google-site-verification") == "abcDEF123_-xyz" and bool(meta(h, "name", "naver-site-verification")))
        C.check("소유 확인: 모르는 이름·꺾쇠 든 값은 버린다", "evil" not in h and "<script>alert" not in h and "msvalidate" not in h)
        st, hd, body = fetch(S.url + "/google0123456789abcdef.html")
        C.check("소유 확인: 파일이 그대로 서빙된다", st == 200 and body.startswith("google-site-verification"), f"{st}")
        st, _, body = fetch(S.url + "/google0000000000000000.html")
        C.check("소유 확인: 설정에 없는 파일은 라우트 404 JSON", st == 404 and '"scope": "route"' in body, f"{st} {body[:80]}")
        os.remove(vf)
        _, _, html = fetch(S.url + "/")
        C.check("소유 확인: 설정 파일을 지우면 재시작 없이 빠진다", "site-verification" not in head_of(html))
    finally:
        S.stop()


def split_site_checks(C: Checks):
    """도메인 옮김: 대표 주소(PLAZA_SITE_URL)를 따로 주면 검색용 주소만 그쪽으로, 에이전트가 부르는 주소는 그대로."""
    base, site = "https://plaza-old.example.test", "https://plaza-new.example.test"
    os.environ["PLAZA_SITE_URL"] = site
    try:
        S = Server(base_url=base).start()
    finally:
        del os.environ["PLAZA_SITE_URL"]
    try:
        judge_server(C, S.url, site, True, "대표 주소 분리")
        _, _, body = fetch(S.url + "/join?format=json")
        d = json.loads(body)
        C.check("[대표 주소 분리] /join 의 base_url·본문은 자기 주소 그대로(대표 주소 안 섞임)",
                d.get("base_url") == base and base in d.get("instruction", "") and site not in d.get("instruction", ""),
                f"{d.get('base_url')}")
        _, _, robots = fetch(S.url + "/robots.txt")
        _, _, sm = fetch(S.url + "/sitemap.xml")
        _, _, html = fetch(S.url + "/")
        C.check("[대표 주소 분리] robots·sitemap·머리에 자기 주소(옛 이름)가 안 남는다",
                base not in robots + sm + head_of(html))
    finally:
        S.stop()


def run(C: Checks) -> dict:
    print("── 검색 노출 (robots·sitemap·메타) ──")
    base = "https://plaza.example.test"
    rulers(C, base)
    S = Server(base_url=base).start()
    try:
        judge_server(C, S.url, base, True, "https")
    finally:
        S.stop()
    T = Server().start()          # 자기 주소가 터널(http) = 색인 끔
    try:
        judge_server(C, T.url, T.base_url, False, "터널")
    finally:
        T.stop()
    split_site_checks(C)
    verify_file_checks(C, str(S.dir))
    return {"rows": len(C.rows), "failed": len(C.failed)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="떠 있는 공개 서버 (자기 주소 = 이 값)")
    a = ap.parse_args(argv)
    C = Checks()
    if a.url:
        base = a.url.rstrip("/")
        judge_server(C, base, base, base.startswith("https://"), base)
    else:
        run(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
