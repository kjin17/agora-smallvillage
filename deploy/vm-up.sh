#!/bin/sh
# 서버에서 돈다: deploy/deploy.sh 가 릴리스를 ~/plaza/releases/<rev> 에 풀고 이걸 부른다.
#   [PLAZA_EDGE_NET=<프록시 네트워크>] sh ~/plaza/releases/<rev>/deploy/vm-up.sh <rev>
# 하는 일: 이름 겹침 검사 → 비밀·설정 폴더(처음 한 번) → 이미지 빌드 → compose up → 건강 확인 → DEPLOYED 한 줄.
# ~/plaza 밖의 컨테이너·볼륨·네트워크는 읽지도 쓰지도 않는다(입구 프록시 네트워크에 plaza_web 을 끼우는 것만 빼고).
set -eu
REV=${1:?판번호}
P=$HOME/plaza
R=$P/releases/$REV
PORT=18765
cd "$P"

# ── 겹침 검사: 이름·포트가 같은 호스트의 다른 것과 부딪치지 않는지 (PLAN 6.2) ──
for n in plaza_web; do
  img=$(docker inspect -f '{{.Config.Image}}' "$n" 2>/dev/null || true)
  case "$img" in ""|plaza-web:*) ;; *) echo "멈춤: 컨테이너 $n 이 다른 이미지($img)로 있다"; exit 1;; esac
done
holder=$(docker ps --filter "publish=$PORT" --format '{{.Names}}' | grep -v '^plaza_web$' || true)
[ -z "$holder" ] || { echo "멈춤: $PORT 을 $holder 가 쥐고 있다"; exit 1; }
if ss -ltn | awk '{print $4}' | grep -q ":$PORT\$" && [ -z "$(docker ps -q --filter name=^plaza_web\$)" ]; then
  echo "멈춤: $PORT 을 컨테이너 밖 프로세스가 쥐고 있다"; exit 1; fi

# ── 자기 주소·대표 주소·입구 네트워크: 있던 .env 값을 이어 쓴다. 입구 네트워크·대표 주소는 환경변수가 이긴다 ──
BASE=http://127.0.0.1:$PORT
EDGE=${PLAZA_EDGE_NET:-}
SITE=${PLAZA_SITE_URL:-}
if [ -f .env ]; then
  BASE=$(sed -n 's/^PLAZA_BASE_URL=//p' .env); BASE=${BASE:-http://127.0.0.1:$PORT}
  [ -n "$EDGE" ] || EDGE=$(sed -n 's/^PLAZA_EDGE_NET=//p' .env)
  [ -n "$SITE" ] || SITE=$(sed -n 's/^PLAZA_SITE_URL=//p' .env)
fi
[ -n "$EDGE" ] || { echo "멈춤: PLAZA_EDGE_NET(입구 프록시가 붙은 도커 네트워크 이름)이 없다. 한 번 넘겨 주면 .env 에 남는다"; exit 1; }
docker network inspect "$EDGE" >/dev/null 2>&1 || { echo "멈춤: 도커 네트워크 $EDGE 이 없다"; exit 1; }

# ── 비밀·설정 (처음 한 번). 비밀은 찍지 않는다 ──
mkdir -p secret config backups logs
chmod 700 secret backups
if [ ! -s secret/secret ]; then
  (umask 077; head -c 48 /dev/urandom | base64 | tr -d '\n' > secret/secret)
  echo "비밀 새로 만듦 (0600, 내용은 찍지 않음)"
fi
chmod 600 secret/secret
[ -f config/operators.json ] || echo '{"operator_agents": []}' > config/operators.json

# ── 이미지 ──
docker build -q -t "plaza-web:$REV" --build-arg "PLAZA_RELEASE=$REV" -f "$R/deploy/Dockerfile" "$R"

# ── 설정 파일: 판번호·자기 주소·입구 네트워크 (비밀 없음). 앞 판은 .env.prev 로 ──
[ ! -f .env ] || cp .env .env.prev
printf '# deploy/vm-up.sh 가 쓴다. 비밀을 넣지 말 것 (비밀은 secret/)\nPLAZA_RELEASE=%s\nPLAZA_BASE_URL=%s\nPLAZA_EDGE_NET=%s\n' "$REV" "$BASE" "$EDGE" > .env
[ -z "$SITE" ] || printf 'PLAZA_SITE_URL=%s\n' "$SITE" >> .env
cp "$R/deploy/compose.yaml" compose.yaml
ln -sfn "releases/$REV" current

# deploy.sh 는 이 변수들을 빈 값으로도 넘긴다. 빈 채로 export 된 변수는 compose 에서 .env 를 이기니 고른 값으로 덮는다
export PLAZA_EDGE_NET="$EDGE" PLAZA_SITE_URL="$SITE"
docker compose up -d

# ── 건강 확인 ──
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' plaza_web)" = healthy ]; do
  i=$((i+1)); [ $i -le 30 ] || { docker logs --tail 40 plaza_web; echo "멈춤: 60초 안에 healthy 가 안 됨"; exit 1; }
  sleep 2
done
curl -fsS -m 5 "http://127.0.0.1:$PORT/join?format=json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("join 판", d["version"], "base_url", d["base_url"])'
echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $REV $(docker inspect -f '{{.Image}}' plaza_web | cut -c8-19)" >> DEPLOYED
echo "올림: plaza-web:$REV"
