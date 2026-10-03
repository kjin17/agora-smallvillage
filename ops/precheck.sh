#!/bin/sh
# push·배포 길목의 사전 점검. 실패하면 0 아닌 값으로 끝나 push(ops/hooks/pre-push)·배포(deploy/deploy.sh)를 막는다.
#   ops/precheck.sh <push|deploy> <커밋>...
# 하는 일 (커밋마다 그 커밋의 트리를 임시 폴더에 떠서 — 작업 트리가 아니라 나갈 것을 잰다):
#   1. ops/sensitive_check.py --strict <트리>   실값·개인 용어·키 모양 (리포가 공개라 push 가 곧 공개다)
#   2. 마지막 커밋 트리에서 판정 시험: server.tests.run_stage2, ops/plaza_*_check.py (측정기·운영 상태 칸)
# 설치별 값은 리포 밖 ${PLAZA_PRECHECK_ENV:-~/.config/ai-smallvillage/precheck.env} 에서 읽는다(셸 문법, 없으면 환경변수만):
#   PLAZA_SECRET_SOURCES=<실값 파일·폴더, 콜론 구분>   PLAZA_SECRET_TARS=<서버 설정 백업 tar.gz, 콜론 구분 — 0700 임시 폴더에 풀어 대조>
# 건너뛰기는 배포만 PLAZA_SKIP_CHECKS=1 (deploy.sh 가 본다). push 는 git push --no-verify 뿐이고 그건 사람이 고른 것이다.
set -eu
MODE=${1:?push 또는 deploy}; shift
[ $# -gt 0 ] || { echo "precheck: 잴 커밋이 없다"; exit 1; }
cd "$(git rev-parse --show-toplevel)"
ENV_FILE=${PLAZA_PRECHECK_ENV:-$HOME/.config/ai-smallvillage/precheck.env}
# shellcheck disable=SC1090
[ ! -f "$ENV_FILE" ] || . "$ENV_FILE"
PY=${PLAZA_PYTHON:-python3}

WORK=$(mktemp -d "${TMPDIR:-/tmp}/plaza-precheck.XXXXXX")
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT INT TERM

SRC=${PLAZA_SECRET_SOURCES:-}
i=0
for t in $(echo "${PLAZA_SECRET_TARS:-}" | tr ':' ' '); do
  i=$((i+1)); mkdir -m 700 "$WORK/tar$i"
  tar -xzf "$t" -C "$WORK/tar$i" || { echo "precheck 멈춤: 설정 백업 $t 을 못 풂"; exit 1; }
  SRC=${SRC:+$SRC:}$WORK/tar$i
done
export PLAZA_SECRET_SOURCES="$SRC"

LAST=
for c in "$@"; do
  rev=$(git rev-parse --short=7 "$c^{commit}")
  rm -rf "$WORK/tree"; mkdir "$WORK/tree"
  git archive --format=tar "$rev" | tar -x -C "$WORK/tree"
  echo "precheck($MODE): $rev 민감정보 점검"
  "$PY" ops/sensitive_check.py --strict "$WORK/tree" || { echo "precheck 멈춤: $rev 민감정보 점검 실패 (위 목록)"; exit 1; }
  LAST=$rev
done

echo "precheck($MODE): $LAST 판정 시험"
rm -rf "$WORK/tree"; mkdir "$WORK/tree"
git archive --format=tar "$LAST" | tar -x -C "$WORK/tree"
(cd "$WORK/tree" && "$PY" -m server.tests.run_stage2 > "$WORK/stage2.log" 2>&1) || {
  tail -25 "$WORK/stage2.log"; echo "precheck 멈춤: $LAST run_stage2 실패"; exit 1; }
sed -n '/판정 .*개 중 실패/p' "$WORK/stage2.log"
for chk in "$WORK"/tree/ops/plaza_*_check.py; do
  [ -f "$chk" ] || continue
  (cd "$WORK/tree" && "$PY" "ops/$(basename "$chk")" > "$WORK/chk.log" 2>&1) || {
    tail -15 "$WORK/chk.log"; echo "precheck 멈춤: $LAST $(basename "$chk") 실패"; exit 1; }
done
echo "precheck($MODE): 통과 ($*)"
