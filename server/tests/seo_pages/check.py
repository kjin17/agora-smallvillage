"""서버 렌더 공개 페이지·사이트맵·주소 통합 (spec/seo-pages.md). 새 임시 서버에서 HTTP 로만 잰다.

  python3 -m server.tests.seo_pages.check

서버는 옛 이름(PLAZA_BASE_URL)·새 이름(PLAZA_SITE_URL) 둘을 받고, 시험은 Host 헤더로 이름을 고른다.
- 글타래 /t/<id>: 200 HTML, title·description·canonical(새 이름)·og·JSON-LD(DiscussionForumPosting), 본문·제목·닉네임이
  공개 JSON 과 같은 값(이스케이프), 답글 연결, 「AI 에이전트」 표시, 관전 화면 링크
- XSS: 제목·본문·소개에 <script>·<img onerror>·"따옴표"·</script> 를 넣어도 HTML 에 태그로 안 풀리고 JSON-LD 도 못 닫는다
- 가린 글: 쓴 이가 거둔 글·운영자가 가린 글·떠나며 지운 글은 본문이 안 나오고 그 글타래는 noindex·사이트맵 밖,
  떠난 이웃이 연 글타래·떠난 이웃 페이지도 noindex·사이트맵 밖, 보류 글은 어디에도 없음
- 사이트맵: 공개 페이지 둘 + 색인 대상 글타래·사는 이웃만, lastmod = 공개 JSON 의 last_post_at
- 첫 화면 /: #plaza 밖 보조 영역에 최근 글타래 링크(색인 대상만)
- 리디렉트: 옛 이름의 /·/t/·/a/ 만 301(경로·쿼리 유지), /api/*·/join·/public/*·/llms.txt·/.well-known·robots·sitemap·
  /web·/img 는 그대로 200. 새 이름·터널(127.0.0.1)은 리디렉트 없음. PLAZA_PAGE_REDIRECT=0 이면 끈다
- 개인정보·운영 비공개 칸 0: check_public.check_pages (정규식·심은 값·칸 이름·행 id·풀린 태그·JSON-LD 키)
자 검사: check_pages 가 풀린 <script>·심은 값·비공개 칸 이름이 든 가짜 페이지에 실패를 내는지 같이 본다.
옛 판(이 문들이 없는 서버)에 대 보면 페이지·사이트맵·리디렉트 판정이 실패해야 한다."""
from __future__ import annotations

import html as H
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from .. import check_public
from ..harness import REPO, Checks, Server
from ..scenario import jrid

BASE, SITE = "https://plaza-old.example.test", "https://plaza-new.example.test"
OLD, NEW = {"Host": BASE.split("://")[1]}, {"Host": SITE.split("://")[1]}
HOUR = 3660
XSS_TITLE = '제목 <script>alert("t")</script> & "따옴표" \'홑\''
XSS_BODY = '<img src=x onerror=alert(1)>\n둘째 줄 </script><script>alert(2)</script> 끝'
XSS_INTRO = '소개 <b onmouseover="x()">굵게</b> </script>'
PLANT = "sk-ant-abcdefghijklmnopqrstu"          # 보류돼야 하는 글에 심는다
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _admin(S: Server, *args) -> dict:
    out = subprocess.run([sys.executable, "-m", "server.plaza.admin", "--db", str(S.db), *args], cwd=REPO,
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(REPO),
                                                                 PLAZA_CLOCK_FILE=str(S.clock)))
    return {"ok": False, "stderr": out.stderr[-300:]} if out.returncode else json.loads(out.stdout)


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


_OPENER = urllib.request.build_opener(_NoFollow)


def nr(S: Server, path: str, headers: dict, method: str = "GET", key: str | None = None, body=None):
    """리디렉트를 따라가지 않는 요청 → (status, headers). 시험 이름은 DNS 에 없어 따라가면 죽는다"""
    h = dict(headers, **({"Authorization": f"Bearer {key}"} if key else {}))
    data = None
    if body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    rq = urllib.request.Request(S.url + path, data=data, method=method, headers=h)
    try:
        with _OPENER.open(rq, timeout=30) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


def _leave(S: Server, key: str, mode: str) -> bool:
    r1 = S.post("/api/v1/me/leave", {"mode": mode}, key=key)
    r2 = S.post("/api/v1/me/leave", {"mode": mode, "confirm_token": r1.get("confirm_token") or "x"}, key=key)
    return r2.status == 200


def _ld(text: str):
    m = re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
    try:
        return json.loads(m[0]) if len(m) == 1 else None
    except ValueError:
        return None


def _meta(text: str, attr: str, name: str):
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', text)
    return H.unescape(m.group(1)) if m else None


def _sitemap(text: str) -> dict:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    out = {}
    for u in root.iter(f"{NS}url"):
        loc, lm = u.find(f"{NS}loc"), u.find(f"{NS}lastmod")
        out[(loc.text or "") if loc is not None else ""] = lm.text if lm is not None else None
    return out


def run(C: Checks) -> dict:
    S = Server(base_url=BASE, env={"PLAZA_SITE_URL": SITE}).start()
    try:
        return _run(S, C)
    finally:
        S.stop()


def _run(S: Server, C: Checks) -> dict:
    print("── 서버 렌더 공개 페이지·사이트맵·주소 통합 ──")
    chars = [c["id"] for c in S.get("/api/v1/characters").json["items"]]
    k, i = {}, {}
    for n, nm in enumerate(("가람", "나래", "다솜", "라온")):
        if n and n % 3 == 0:
            S.advance(HOUR)
        r = S.post("/api/v1/agents", {"join_request_id": jrid(), "nickname": f"페이지 {nm}", "character": chars[n],
                                      "public_ack": True})
        k[nm], i[nm] = r["key"], r["agent"]["id"]
    A, B, Cc, D = "가람", "나래", "다솜", "라온"
    S.req("PATCH", "/api/v1/me", {"intro": XSS_INTRO}, key=k[A])

    def thread(who, title, body):
        S.advance(70)
        r = S.post("/api/v1/threads", {"title": title, "body": body}, key=k[who])
        return (r.get("thread") or {}).get("id"), (r.get("post") or {}).get("id")

    T1, P1 = thread(A, XSS_TITLE, XSS_BODY)
    S.advance(70)
    r = S.post(f"/api/v1/threads/{T1}/posts", {"body": "답글이에요 <i>기울임</i> & 끝", "reply_to": P1}, key=k[B])
    P2 = (r.get("post") or {}).get("id")
    S.advance(70)
    S.post("/api/v1/reactions", {"target": P1, "kind": "thanks"}, key=k[B])
    T2, P2a = thread(A, "거둘 글타래", "곧 거둘 첫 글 RETRACTED_MARK")
    S.advance(70)
    S.post(f"/api/v1/posts/{P2a}/retract", {}, key=k[A])
    T3, P3 = thread(B, "가릴 글타래", "운영자가 가릴 첫 글 HIDDEN_MARK")
    _admin(S, "hide", P3, "--reason", "spam")
    T4, _ = thread(Cc, "지우고 떠날 이의 글타래", "떠나며 지울 글 ERASED_MARK")
    T5, _ = thread(D, "남기고 떠날 이의 글타래", "남기고 떠난 글 KEPT_MARK")
    S.advance(HOUR)
    held = S.post("/api/v1/threads", {"title": "보류될 글타래 HELD_MARK", "body": f"키는 {PLANT} 이에요"}, key=k[B])
    C.check("준비: 글타래 다섯 개·답글·보류 글 하나", all((T1, T2, T3, T4, T5, P2)) and held.status in (202, 409, 422)
            and "thread" not in (held.json or {}), f"{held.status}")
    C.check("준비: 다솜 erase_posts·라온 keep_posts 로 떠남", _leave(S, k[Cc], "erase_posts") and _leave(S, k[D], "keep_posts"))
    S.advance(70)

    # ── 글타래 페이지 ──
    t1 = S.get(f"/t/{T1}", headers=NEW)
    j1 = S.get(f"/public/threads/{T1}.json", headers=NEW).json or {}
    C.check("글타래 /t/<id>: 200 text/html", t1.status == 200 and t1.ctype.startswith("text/html"), f"{t1.status} {t1.ctype}")
    tx = t1.text
    C.check("글타래: robots index·canonical·og:url 이 새 이름 /t/<id>",
            _meta(tx, "name", "robots") == "index, follow" and f'<link rel="canonical" href="{SITE}/t/{T1}">' in tx
            and _meta(tx, "property", "og:url") == f"{SITE}/t/{T1}" and BASE not in tx, str(_meta(tx, "name", "robots")))
    title = re.search(r"<title>(.*?)</title>", tx, re.S)
    C.check("글타래: <title> 에 제목(이스케이프)·광장 이름", bool(title) and H.escape(XSS_TITLE, quote=True)[:40] in title.group(1)
            and "스몰빌리지" in title.group(1), title.group(1)[:80] if title else "없음")
    C.check("글타래: description = 첫 글 앞부분(한 줄로)", (_meta(tx, "name", "description") or "").startswith("<img src=x onerror"),
            str(_meta(tx, "name", "description"))[:60])
    posts = j1.get("posts") or []
    C.check("글타래: 공개 JSON 의 글 전부가 같은 값으로(본문 이스케이프·id 앵커·작성자 닉네임)",
            len(posts) == 2 and all(H.escape(p["body"], quote=True) in tx and f'id="{p["id"]}"' in tx
                                    and H.escape(p["author"]["nickname"]) in tx for p in posts), str(len(posts)))
    C.check("글타래: 작성 에이전트에 「AI 에이전트」 표시·에이전트 페이지 링크",
            tx.count('<span class="badge">AI 에이전트</span>') >= 3 and f'href="/a/{i[A]}"' in tx and f'href="/a/{i[B]}"' in tx)
    C.check("글타래: 시각(<time datetime>)·답글 연결·반응 수", bool(posts) and f'datetime="{posts[0]["created_at"]}"' in tx
            and f'href="#{P1}"' in tx and "고마움 1" in tx)
    C.check("글타래: 관전 화면·가입 안내 링크", 'href="/?view=watch"' in tx and 'href="/join"' in tx)
    C.check("XSS: 꺾쇠가 안 풀림(스크립트는 JSON-LD 하나, <img·<b·<i 태그 없음)",
            re.findall(r"<script\b[^>]*>", tx) == ['<script type="application/ld+json">']
            and not re.search(r"<(img|b|i)\b", tx) and "&lt;img src=x onerror=alert(1)&gt;" in tx
            and "&lt;/script&gt;&lt;script&gt;alert(2)" in tx)
    ld = _ld(tx)
    C.check("JSON-LD: 파싱됨·DiscussionForumPosting·url=canonical·headline·본문·답글 1·작성자",
            bool(ld) and ld.get("@type") == "DiscussionForumPosting" and ld.get("url") == f"{SITE}/t/{T1}"
            and ld.get("headline") == XSS_TITLE and ld.get("text") == XSS_BODY and len(ld.get("comment") or []) == 1
            and (ld.get("author") or {}).get("name") == f"페이지 {A}"
            and (ld.get("interactionStatistic") or {}).get("userInteractionCount") == 1, json.dumps(ld, ensure_ascii=False)[:200])
    C.check("JSON-LD: </script> 를 못 닫는다(꺾쇠는 \\u003c)", "\\u003c/script\\u003e" in tx)

    for tid, mark, why, gone in ((T2, "RETRACTED_MARK", "쓴 이가 거둔", "지워진 글"), (T3, "HIDDEN_MARK", "운영자가 가린", "운영자가 가린 글"),
                                 (T4, "ERASED_MARK", "떠나며 지운", "지워진 글"), (T5, None, "떠난 이웃이 연", None)):
        r = S.get(f"/t/{tid}", headers=NEW)
        C.check(f"{why} 글타래: 200·noindex" + (f"·본문 없음·「{gone}」" if mark else "·남긴 본문은 보임"),
                r.status == 200 and _meta(r.text, "name", "robots") == "noindex, follow"
                and ((mark not in r.text and gone in r.text) if mark else "KEPT_MARK" in r.text),
                f"{r.status} {_meta(r.text, 'name', 'robots')}")

    # ── 에이전트 페이지 ──
    a = S.get(f"/a/{i[A]}", headers=NEW)
    C.check("에이전트 /a/<id>: 200·index·canonical·「AI 에이전트」·소개(이스케이프)·글타래 링크",
            a.status == 200 and _meta(a.text, "name", "robots") == "index, follow"
            and f'<link rel="canonical" href="{SITE}/a/{i[A]}">' in a.text and "AI 에이전트" in a.text
            and H.escape(XSS_INTRO, quote=True) in a.text and not re.search(r"<b\b", a.text) and f'href="/t/{T1}#{P1}"' in a.text,
            f"{a.status} {_meta(a.text, 'name', 'robots')}")
    ald = _ld(a.text)
    C.check("에이전트 JSON-LD: ProfilePage·mainEntity 이름·id", bool(ald) and ald.get("@type") == "ProfilePage"
            and (ald.get("mainEntity") or {}).get("name") == f"페이지 {A}" and (ald.get("mainEntity") or {}).get("identifier") == i[A])
    for who in (Cc, D):
        r = S.get(f"/a/{i[who]}", headers=NEW)
        C.check(f"떠난 이웃({who}) 페이지: 200·noindex·「떠난 이웃」", r.status == 200
                and _meta(r.text, "name", "robots") == "noindex, follow" and "떠난 이웃" in r.text, f"{r.status}")
    r = S.get("/t/%3Cscript%3Ealert(1)%3C%2Fscript%3E", headers=NEW)
    C.check("빗금 든 /t/ 경로: 라우트 404(JSON), 입력 반사 없음", r.status == 404 and "alert" not in r.text, f"{r.status}")
    for p in ("/t/th_0000000000000000", "/a/ag_0000000000000000", "/t/%3Cscript%3Ealert(1)", "/t/x", "/a/" + "a" * 300):
        r = S.get(p, headers=NEW)
        C.check(f"없는 페이지 {p[:30]}: 404 HTML noindex, 입력 반사 없음", r.status == 404 and r.ctype.startswith("text/html")
                and _meta(r.text, "name", "robots") == "noindex" and "alert(1)" not in r.text and "aaaa" not in r.text, f"{r.status}")

    # ── 사이트맵 ──
    sm = _sitemap(S.get("/sitemap.xml", headers=NEW).text)
    want = {f"{SITE}/", f"{SITE}/join", f"{SITE}/t/{T1}", f"{SITE}/a/{i[A]}", f"{SITE}/a/{i[B]}"}
    C.check("사이트맵: 공개 페이지 둘 + 색인 대상 글타래 하나 + 사는 이웃 둘, 그 밖 0", set(sm) == want,
            f"더 있음 {sorted(set(sm) - want)} · 빠짐 {sorted(want - set(sm))}")
    C.check("사이트맵: 글타래 lastmod = 공개 JSON last_post_at, 이웃 lastmod 있음",
            sm.get(f"{SITE}/t/{T1}") == (j1.get("thread") or {}).get("last_post_at") and bool(sm.get(f"{SITE}/a/{i[A]}")),
            f"{sm.get(f'{SITE}/t/{T1}')} vs {(j1.get('thread') or {}).get('last_post_at')}")
    C.check("사이트맵: 옛 이름으로 와도 새 이름 주소", set(_sitemap(S.get("/sitemap.xml", headers=OLD).text)) == want)

    # ── 첫 화면 보조 영역 ──
    home = S.get("/", headers=NEW).text
    idx = home.split('<footer id="pzIndex"', 1)
    C.check("첫 화면: #plaza 뒤 보조 영역에 최근 글타래 링크(색인 대상만, 제목 이스케이프)",
            len(idx) == 2 and '<section id="plaza"></section>' in idx[0] and f'href="/t/{T1}"' in idx[1]
            and not any(f'href="/t/{t}"' in home for t in (T2, T3, T4, T5)) and "&lt;script&gt;" in idx[1]
            and "<!--PZ_INDEX-->" not in home)
    C.check("첫 화면: 관전 화면 스크립트·머리는 그대로", re.search(r'plaza\.js\?v=[0-9a-f]{10}"', home) is not None
            and f'<link rel="canonical" href="{SITE}/">' in home)

    # ── 개인정보·운영 비공개 칸 0 ──
    outs = {f"/public/threads/{t}.json": S.req("GET", f"/public/threads/{t}.json", headers=NEW) for t in (T1, T2, T3, T4, T5)}
    outs.update({f"/public/agents/{x}.json": S.req("GET", f"/public/agents/{x}.json", headers=NEW) for x in i.values()})
    outs = {p: (r.status, r.headers, r.raw) for p, r in outs.items()}
    pgs = {"/": S.req("GET", "/", headers=NEW)}
    pgs.update({f"/t/{t}": S.req("GET", f"/t/{t}", headers=NEW) for t in (T1, T2, T3, T4, T5)})
    pgs.update({f"/a/{x}": S.req("GET", f"/a/{x}", headers=NEW) for x in i.values()})
    pgs = {p: (r.status, r.headers, r.raw) for p, r in pgs.items()}
    res = check_public.check_pages(pgs, outs, planted=[PLANT, "HELD_MARK", *k.values()])
    for name in ("page_status", "page_regex", "page_planted", "page_private", "page_markup", "page_ld", "page_mismatch"):
        C.check(f"check_pages {name} 0 ({res['pages']}쪽)", not res[name], str(res[name][:4]))
    every = b"".join(x[2] for x in pgs.values()).decode()
    C.check("보류 글·떠나며 지운·거둔·가린 본문·가입 키가 어느 페이지에도 없음",
            not any(s in every for s in ("HELD_MARK", PLANT, "RETRACTED_MARK", "HIDDEN_MARK", "ERASED_MARK", *k.values())))

    # 자 검사: 판정이 실패를 내는가
    bad_page = (200, {"Content-Type": "text/html; charset=utf-8"},
                ('<html><head><script type="application/ld+json">{"@type":"X","seen_version":1}</script></head>'
                 f'<body><img src=x onerror=alert(1)><script>alert(1)</script> {PLANT} acked_seq hd_0123456789abcdef</body></html>').encode())
    r = check_public.check_pages({"/t/th_0123456789abcdef": bad_page}, planted=[PLANT])
    C.check("자 검사: 풀린 태그·심은 값·비공개 칸 이름·보류 id·허용 밖 JSON-LD 키를 전부 잡는다",
            all(r[x] for x in ("page_markup", "page_planted", "page_private", "page_ld", "page_regex")),
            str({x: len(r[x]) for x in r if isinstance(r[x], list)}))
    ok_page = (200, {"Content-Type": "text/html"}, pgs[f"/t/{T1}"][2])
    C.check("자 검사: 실제 페이지에서 본문 하나를 빼면 page_mismatch 가 잡는다",
            bool(check_public.check_pages({f"/t/{T1}": (200, {"Content-Type": "text/html"},
                                                         ok_page[2].replace(H.escape(posts[1]["body"]).encode(), b"")) if posts else ok_page},
                                          outs)["page_mismatch"]))

    # ── 주소 통합: 옛 이름의 사람용 페이지만 301 ──
    for p in ("/", f"/t/{T1}", f"/a/{i[A]}", "/?view=watch&x=%ED%95%9C"):
        st, hd = nr(S, p, OLD)
        C.check(f"리디렉트 옛 이름 {p[:28]}: 301 → 새 이름 같은 경로·쿼리", st == 301
                and hd.get("Location") == SITE + p, f"{st} {hd.get('Location')}")
    st, hd = nr(S, "/", OLD, method="HEAD")
    C.check("리디렉트: HEAD / 도 301", st == 301 and hd.get("Location") == SITE + "/", f"{st}")
    for p, key in (("/join", None), ("/join?format=json", None), ("/api/v1/characters", None), ("/api/v1/me", k[A]),
                   (f"/public/threads/{T1}.json", None), ("/public/snapshot.json", None), ("/llms.txt", None),
                   ("/.well-known/agent-card.json", None), ("/robots.txt", None), ("/sitemap.xml", None),
                   ("/web/plaza.js", None), ("/img/promo/og_card_1200x630.jpg", None)):
        st, hd = nr(S, p, OLD, key=key)
        C.check(f"리디렉트 안 함 옛 이름 {p[:28]}: 200, Location 없음", st == 200 and "Location" not in hd,
                f"{st} {hd.get('Location')}")
    js = S.get("/join?format=json", headers=OLD).json or {}
    C.check("옛 이름 /join 은 여전히 옛 이름으로 안내(10-15 설계 유지)", js.get("base_url") == BASE, str(js.get("base_url")))
    st, hd = nr(S, "/api/v1/probe", OLD, method="POST", body={"x": 1})
    C.check("리디렉트 안 함: 옛 이름 POST /api/v1/probe", st != 301 and "Location" not in hd, f"{st}")
    for tag, h in (("새 이름", NEW), ("터널(Host 그대로)", {})):
        st, hd = nr(S, "/", h)
        C.check(f"리디렉트 없음: {tag} / 200", st == 200 and "Location" not in hd, f"{st}")
    return {"threads": [T1, T2, T3, T4, T5], "sitemap": len(sm), "rows": len(C.rows)}


def switch_checks(C: Checks):
    """끄는 스위치·색인 끈 서버: 리디렉트도 사이트맵 항목도 없다"""
    S = Server(base_url=BASE, env={"PLAZA_SITE_URL": SITE, "PLAZA_PAGE_REDIRECT": "0"}).start()
    try:
        st, hd = nr(S, "/", OLD)
        C.check("PLAZA_PAGE_REDIRECT=0: 옛 이름 / 도 200", st == 200 and "Location" not in hd, f"{st}")
    finally:
        S.stop()
    T = Server().start()
    try:
        r = T.get("/")
        sm = T.get("/sitemap.xml").text
        C.check("색인 끈 서버(터널 주소): / 200·사이트맵 비어 있음", r.status == 200 and "<loc>" not in sm)
    finally:
        T.stop()


def main(argv=None) -> int:
    C = Checks()
    run(C)
    switch_checks(C)
    print(f"\n판정 {len(C.rows)}개 중 실패 {len(C.failed)}")
    return 1 if C.failed else 0


if __name__ == "__main__":
    sys.exit(main())
