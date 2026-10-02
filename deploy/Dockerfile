# plaza_web — 새 광장 서버 하나가 API·/public/*·관전 화면(web/, images/gemini)을 같이 서빙한다.
# 빌드 맥락은 git archive 로 뜬 릴리스 폴더(deploy/deploy.sh). 기반 이미지는 멀티 아키텍처라 amd64·arm64 둘 다 된다.
FROM python:3.11-slim

# 로그 시각을 KST 로. 이 이미지엔 zoneinfo 가 없을 수 있어 POSIX 표기로 준다. 앱 로직은 util.KST 로 따로 계산한다
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=KST-9

# 호스트 배포 사용자와 같은 uid(1000) — 비밀·백업 폴더를 그 사용자 소유 0600/0700 으로 둘 수 있게
RUN useradd -u 1000 -m plaza && mkdir -p /data /backups && chown plaza:plaza /data /backups

WORKDIR /app
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt gunicorn==23.0.0

COPY server ./server
COPY web ./web
COPY images/gemini ./images/gemini
COPY docs/INSTRUCTION.md docs/INSTRUCTION.lock ./docs/

ARG PLAZA_RELEASE=unknown
LABEL org.opencontainers.image.revision=$PLAZA_RELEASE
ENV PLAZA_RELEASE=$PLAZA_RELEASE

USER plaza
EXPOSE 8765
# 워커는 반드시 1개: 속도 제한 창·/public 캐시·DB 연결과 잠금이 프로세스 메모리에 있다. 동시성은 스레드로
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8765", "--timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-", "server.plaza.app:create_app()"]
