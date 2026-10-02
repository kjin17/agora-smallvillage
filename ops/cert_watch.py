#!/usr/bin/env python3
"""광장 인증서 감시 — 공개 도메인의 오리진(VM nginx)·엣지(CDN)를 매주 잰다.

■ 무엇을 재는가
  1. 오리진 파일   certbot 볼륨의 live/<도메인>/fullchain.pem 만료일 (읽기 전용 마운트)
  2. 오리진 서빙   VM:443 에 이 이름(SNI)으로 붙어 nginx 가 실제로 내주는 인증서. 검증까지 한다
                  (이름이 안 맞으면 다른 server 블록의 인증서가 나온 것 = 광장 server 블록이 빠졌다)
  3. 엣지          <도메인>:443 (CDN 이 앞에 있으면 CDN 인증서)
  4. 파일≠서빙     certbot 이 갱신했는데 nginx 가 아직 옛것을 들고 있다. reload 가 주 1회라면
                  갱신 뒤 최대 7일은 정상이다. 파일의 notBefore 가 8일을 넘었는데도 다르면 reload 가 안 된 것
  5. 갱신 루프     certbot 컨테이너 로그(최근 7일)에서 이 이름의 renewal 처리 횟수와 실패 줄 수.
                  처리 0회 = renew 루프가 이 이름을 안 보고 있다. 로그는 읽기만 한다

■ 문턱: 오리진 21일(certbot 은 30일 전부터 시도하니 두 번 실패했다는 뜻), 엣지 14일(우리가 못 고친다).

■ 조용한 것이 정상이다. 상태는 설정의 state_dir/plaza_cert_watch.json 에 남기고, 일일 보고 같은 다른 잡이
  그 파일의 남은 날과 측정 나이를 읽는다. 감시기가 죽으면 그 나이가 8일을 넘는다.

설치별 값(도메인·컨테이너·볼륨 이름·상태 폴더·알림)은 ops/opslib.py 의 설정 파일에서 읽는다.

    python3 ops/cert_watch.py            # 문턱을 넘거나 확인이 실패하면 알림, exit 1
    python3 ops/cert_watch.py --report   # 지금 상태를 무조건 한 번 보낸다
    python3 ops/cert_watch.py --no-alert # 손으로 돌려 볼 때
    PLAZA_CERT_DOMAIN=<이름> 으로 이름을 바꿔 잴 수 있다(없는 이름을 넣어 실패가 나는지 보는 용도)

■ 같은 certbot 볼륨에 자기 인증서(live/<이름>)를 가진 다른 이름이 있으면 설정 extra_cert_lineages 에
  extra_cert_domains 의 라벨로 적는다. 그 이름들도 같은 다섯 가지를 재고, 상태 파일의 extra.<라벨> 에 남긴다.
  알림은 한 통으로 묶고, 어느 이름이든 걸리면 exit 1. PLAZA_CERT_DOMAIN 으로 돌릴 때는 그 이름 하나만 잰다.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import socket
import ssl
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import KST, conf, log, path_conf, save_json, send_telegram, ssh, vm  # noqa: E402

DEFAULT_DOMAIN = conf("domain")
DOMAIN = os.environ.get("PLAZA_CERT_DOMAIN", DEFAULT_DOMAIN)
EXTRA_DOMAINS = conf("extra_cert_domains", {})
EXTRA = ({} if DOMAIN != DEFAULT_DOMAIN else
         {label: EXTRA_DOMAINS[label] for label in conf("extra_cert_lineages", [])})
STATE = path_conf("state_dir") / "plaza_cert_watch.json"
CERTBOT = conf("certbot_container", "certbot")
CERTBOT_VOLUME = conf("certbot_volume", "certbot_conf")
NGINX = conf("nginx_container", "nginx")
WARN_ORIGIN = 21
WARN_EDGE = 14
RELOAD_GRACE_DAYS = 8
UTC = dt.timezone.utc


def openssl_dates(pem: bytes) -> tuple[dt.datetime, dt.datetime, str]:
    p = subprocess.run(["/usr/bin/openssl", "x509", "-noout", "-startdate", "-enddate", "-fingerprint", "-sha256"],
                       input=pem, capture_output=True, timeout=30)
    out = p.stdout.decode()
    if p.returncode != 0:
        raise RuntimeError(f"openssl 실패: {p.stderr.decode()[:200]}")
    nb = re.search(r"notBefore=(.+)", out).group(1)
    na = re.search(r"notAfter=(.+)", out).group(1)
    fp = re.search(r"Fingerprint=(.+)", out, re.I).group(1).replace(":", "").strip().lower()
    parse = lambda s: dt.datetime.strptime(s.strip(), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)  # noqa: E731
    return parse(nb), parse(na), fp


def origin_file(domain: str):
    pem = ssh(f"docker run --rm -v {CERTBOT_VOLUME}:/le:ro alpine cat /le/live/{domain}/fullchain.pem",
              binary=True, timeout=120)
    if b"BEGIN CERTIFICATE" not in pem:
        raise RuntimeError("볼륨에서 인증서를 못 읽음")
    return openssl_dates(pem)


def served(domain: str, host: str, port: int = 443):
    """검증까지 하는 TLS. 이름이 안 맞거나 체인이 깨지면 예외가 그대로 올라온다."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname=domain) as tls:
            cert = tls.getpeercert()
            der = tls.getpeercert(binary_form=True)
    parse = lambda s: dt.datetime.strptime(s, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)  # noqa: E731
    return parse(cert["notBefore"]), parse(cert["notAfter"]), hashlib.sha256(der).hexdigest()


def renew_log(domain: str):
    out = ssh(f"docker logs --since 168h {CERTBOT} 2>&1 | awk '/^Processing /{{cur=$0}} "
              f"index(cur, \"/{domain}.conf\") || index($0, \"{domain}\") {{print}}'", timeout=60)
    lines = out.splitlines()
    processed = sum(1 for ln in lines if ln.startswith("Processing "))
    failed = [ln for ln in lines if re.search(r"fail|error|problem", ln, re.I)]
    return processed, failed


def measure(domain: str, host_ip: str, now: dt.datetime) -> dict:
    """이름 하나의 다섯 가지. 상태 파일 한 칸 모양으로 돌려준다."""
    rows, alerts, errors, info = [], [], [], []
    got = {}
    for key, label, getter, warn in (
            ("file", "오리진 파일(certbot)", lambda: origin_file(domain), WARN_ORIGIN),
            ("origin", "오리진 서빙(VM nginx)", lambda: served(domain, host_ip), WARN_ORIGIN),
            ("edge", "엣지(CDN)", lambda: served(domain, domain), WARN_EDGE)):
        try:
            nb, na, fp = getter()
        except Exception as e:
            errors.append(f"{label}: 확인 실패 — {type(e).__name__} {str(e)[:200]}")
            continue
        days = (na - now).days
        got[key] = {"not_before": nb.isoformat(), "not_after": na.isoformat(), "days": days, "sha256": fp[:16]}
        rows.append(f"{label}: {na.astimezone(KST):%Y-%m-%d} · {days}일 남음")
        if days <= warn:
            alerts.append(f"{label} 만료 {days}일 전 (문턱 {warn}일)")

    if "file" in got and "origin" in got and got["file"]["sha256"] != got["origin"]["sha256"]:
        age = (now - dt.datetime.fromisoformat(got["file"]["not_before"])).days
        msg = f"파일과 서빙이 다름 — 갱신 {age}일 전, nginx reload 대기"
        (alerts if age >= RELOAD_GRACE_DAYS else info).append(
            msg if age < RELOAD_GRACE_DAYS else f"파일과 서빙이 {age}일째 다름 — nginx reload 가 안 됐다")

    try:
        processed, failed = renew_log(domain)
        rows.append(f"갱신 루프(7일): 처리 {processed}회 · 실패 줄 {len(failed)}")
        got["renew"] = {"processed_7d": processed, "failed_lines_7d": len(failed)}
        if failed:
            alerts.append("certbot 갱신 실패 로그: " + " / ".join(failed[-3:])[:300])
        if processed == 0:
            (info if "file" in got and (now - dt.datetime.fromisoformat(got["file"]["not_before"])).days < 1
             else alerts).append("갱신 루프가 최근 7일 이 이름을 한 번도 처리하지 않음")
    except Exception as e:
        errors.append(f"갱신 로그: 확인 실패 — {type(e).__name__} {str(e)[:200]}")

    return {"domain": domain, "ok": not (alerts or errors), "certs": got, "rows": rows,
            "alerts": alerts, "errors": errors, "info": info}


def main(argv) -> int:
    force, alert = "--report" in argv, "--no-alert" not in argv
    now = dt.datetime.now(UTC)
    host_ip = vm()[0].split("@", 1)[1]

    state = measure(DOMAIN, host_ip, now)
    state = {"domain": DOMAIN, "at": now.astimezone(KST).isoformat(timespec="seconds"), **state}
    blocks = [state] + [measure(d, host_ip, now) for d in EXTRA.values()]
    if EXTRA:
        state["extra"] = {label: b for label, b in zip(EXTRA, blocks[1:])}
    if DOMAIN == DEFAULT_DOMAIN:            # 시험용 이름으로 돌린 결과가 일일 보고를 덮지 않게
        save_json(STATE, state)

    any_alert = any(b["alerts"] for b in blocks)
    any_error = any(b["errors"] for b in blocks)
    text_blocks = []
    for b in blocks:
        body = ([b["domain"]] + b["rows"] + b["info"]
                + ([""] + b["alerts"] if b["alerts"] else []) + ([""] + b["errors"] if b["errors"] else []))
        text_blocks.append("\n".join(body))
    print("\n\n".join(text_blocks), flush=True)

    if alert and (any_alert or any_error or force):
        head = ("🔴 광장 인증서 경보" if any_alert else
                "⚠️ 광장 인증서 확인 실패" if any_error else "🔒 광장 인증서")
        text = head + "\n\n" + "\n\n".join(text_blocks)
        for b in blocks:
            if b["alerts"]:
                text += (f"\n\n오리진 강제 갱신({b['domain']}): VM 에서 `docker exec {CERTBOT} certbot renew "
                         f"--cert-name {b['domain']}` 뒤 `docker exec {NGINX} nginx -t && "
                         f"docker exec {NGINX} nginx -s reload`")
        send_telegram(text)
    return 1 if (any_alert or any_error) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
