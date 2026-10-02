#!/bin/sh
# 개발 기기에서 돈다. 서버에 git 이 없어도 되게 커밋 하나를 git archive 로 떠서 ssh 로 흘린다(작업 트리가 아니라 커밋이 판번호다).
#   PLAZA_VM=<user@host> PLAZA_VM_KEY=<키 경로> [PLAZA_EDGE_NET=<프록시 네트워크>] [PLAZA_SITE_URL=<대표 주소>] deploy/deploy.sh [커밋, 기본 HEAD]
#   PLAZA_DRY_RUN=1 이면 배포 전 검사(미커밋·lock·같은 커밋 규칙)만 하고 서버에는 읽기 한 번 말고 아무것도 안 한다
# 절차 전문·롤백은 docs/deploy.md
set -eu
cd "$(git rev-parse --show-toplevel)"
: "${PLAZA_VM:?PLAZA_VM=<user@host>}" "${PLAZA_VM_KEY:?PLAZA_VM_KEY=<키 경로>}"
REF=${1:-HEAD}
REV=$(git rev-parse --short=7 "$REF^{commit}")
PATHS="server web images/gemini docs/INSTRUCTION.md docs/INSTRUCTION.lock deploy"
SSH="ssh -i $PLAZA_VM_KEY -o ConnectTimeout=15 -o ServerAliveInterval=10 -o BatchMode=yes $PLAZA_VM"

if [ "$REF" = HEAD ] && [ -n "$(git status --porcelain -- $PATHS)" ]; then
  echo "멈춤: 배포 범위에 커밋 안 된 변경이 있다 (배포는 커밋된 판만)"; exit 1; fi

# PLAN 4.7 검사 3·lock: 미정이 남았거나 본문 해시가 lock 과 다르면 거부
git show "$REV:docs/INSTRUCTION.md" > /tmp/plaza-instr.$$ ; git show "$REV:docs/INSTRUCTION.lock" > /tmp/plaza-lock.$$
python3 - /tmp/plaza-instr.$$ /tmp/plaza-lock.$$ <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, ".")
from server.tests.check_docs import check_lock
t, l = (Path(p).read_text(encoding="utf-8") for p in sys.argv[1:3])
bad = check_lock(instr_text=t, lock_text=l) + (["미정 남음"] if "서버 구현 때 확정" in t else [])
if bad:
    sys.exit("멈춤: " + "; ".join(bad))
PY
rm -f /tmp/plaza-instr.$$ /tmp/plaza-lock.$$

# PLAN 4.7 같은 커밋 규칙: 앞 판 이후 라우트 파일이 바뀌었는데 INSTRUCTION.md 가 그대로면 멈춘다
PREV=$($SSH "sed -n 's/^PLAZA_RELEASE=//p' ~/plaza/.env 2>/dev/null" || true)
if [ -n "$PREV" ] && ! git cat-file -e "$PREV^{commit}" 2>/dev/null; then
  echo "알림: 앞 판 $PREV 이 이 리포에 없다(리포 이전 등) — 같은 커밋 규칙 검사를 건너뜀. check_docs 로 확인할 것"
elif [ -n "$PREV" ] && [ "$PREV" != "$REV" ] && [ "${PLAZA_FORCE:-}" != 1 ]; then
  ch=$(git diff --name-only "$PREV" "$REV" -- server/plaza/app.py docs/INSTRUCTION.md)
  if echo "$ch" | grep -q app.py && ! echo "$ch" | grep -q INSTRUCTION.md; then
    echo "멈춤: $PREV..$REV 에 app.py 가 바뀌었는데 INSTRUCTION.md 가 그대로 (문서가 맞으면 PLAZA_FORCE=1)"; exit 1; fi
fi

echo "배포: $REV (앞 판 ${PREV:-없음})"
if [ "${PLAZA_DRY_RUN:-}" = 1 ]; then echo "PLAZA_DRY_RUN=1: 검사 통과, 여기서 멈춤"; exit 0; fi
$SSH "mkdir -p ~/plaza/releases/$REV"
git archive --format=tar "$REV" $PATHS | $SSH "tar -x -C ~/plaza/releases/$REV"
$SSH "PLAZA_EDGE_NET='${PLAZA_EDGE_NET:-}' PLAZA_SITE_URL='${PLAZA_SITE_URL:-}' sh ~/plaza/releases/$REV/deploy/vm-up.sh $REV"
