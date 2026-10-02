"""공개 주소 검사를 CDN 봇 검사 너머로 돌리는 감싸개.
Cloudflare Browser Integrity Check 는 파이썬 표준 urllib 기본 UA(`Python-urllib/3.x`)를 403 1010 으로 막는다
(docs/deploy.md 「CDN 뒤에 둘 때」, PLAN U14). 검사 모듈들은 urllib.request.urlopen 을 쓰므로 전역 opener 에 UA 를 넣고 부른다.

  python3 -m server.tests.with_ua server.tests.check_public --url https://plaza.example.com
  python3 -m server.tests.with_ua server.tests.check_remote --url https://plaza.example.com
"""
import runpy
import sys
import urllib.request

op = urllib.request.build_opener()
op.addheaders = [("User-Agent", "ai-smallvillage-check/1 (+operator)")]
urllib.request.install_opener(op)
mod = sys.argv[1]
sys.argv = [mod] + sys.argv[2:]
runpy.run_module(mod, run_name="__main__")
