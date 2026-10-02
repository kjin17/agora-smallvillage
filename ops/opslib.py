"""운영자 기기에서 도는 광장 운영 잡(ops/)이 같이 쓰는 것: 설정·VM 접속·ssh·알림.

호스트·도메인·경로 같은 설치별 값은 리포에 적지 않는다. 전부 리포 밖 설정 파일 하나에서 읽는다.
  PLAZA_OPS_CONFIG (기본 ~/.config/ai-smallvillage/ops.json) — 모양은 ops/ops.example.json
VM 접속은 환경변수 PLAZA_VM·PLAZA_VM_KEY(deploy.sh 와 같은 이름)가 있으면 그것이 이긴다.
필요한 값이 없으면 이름을 남기고 멈춘다(조용한 기본값을 두지 않는다).

알림은 텔레그램 Bot API 한 경로뿐이고 폴백은 두지 않는다(이중화는 1순위의 고장을 감춘다).
보내기에 실패하면 예외가 그대로 올라가 잡이 exit 1 로 끝난다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.request
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
CONFIG_PATH = Path(os.environ.get("PLAZA_OPS_CONFIG", "~/.config/ai-smallvillage/ops.json")).expanduser()


def _load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError) as e:
        raise RuntimeError(f"운영 설정을 못 읽음: {CONFIG_PATH} ({e}). ops/ops.example.json 을 보고 만들 것")


def conf(key: str, default=None):
    """설정 값 하나. default 가 None 이면 필수 값이다."""
    c = _load()
    if key in c:
        return c[key]
    if default is None:
        raise RuntimeError(f"운영 설정 {CONFIG_PATH} 에 {key!r} 가 없다")
    return default


def path_conf(key: str, default: str | None = None) -> Path:
    return Path(conf(key, default)).expanduser()


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(KST):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def vm() -> tuple[str, str]:
    """(user@host, 키 경로). 환경변수 → 설정의 vm_host·vm_key → 설정의 vm_cred_file(host·key 를 담은 JSON)."""
    host, key = os.environ.get("PLAZA_VM"), os.environ.get("PLAZA_VM_KEY")
    if not (host and key):
        c = _load()
        if "vm_cred_file" in c:
            f = Path(c["vm_cred_file"]).expanduser()
            try:
                cred = json.loads(f.read_text())
            except (OSError, ValueError) as e:
                raise RuntimeError(f"VM 접속 정보 없음: {f} 를 못 읽음 ({e})")
            c = {"vm_host": cred.get("host"), "vm_key": cred.get("key"), **c}
        host, key = host or c.get("vm_host"), key or c.get("vm_key")
        if not (host and key):
            raise RuntimeError(f"VM 접속 정보 없음: PLAZA_VM/PLAZA_VM_KEY 도 {CONFIG_PATH} 의 "
                               "vm_host·vm_key·vm_cred_file 도 없다")
    return host, os.path.expanduser(key)


def ssh(cmd: str, binary: bool = False, timeout: int = 180):
    host, key = vm()
    p = subprocess.run(
        ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20",
         "-o", "BatchMode=yes", host, cmd],
        capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"ssh 실패 rc={p.returncode}: {p.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def send_telegram(text: str) -> None:
    cred = json.loads(path_conf("telegram_cred_file").read_text())
    body = json.dumps({"chat_id": cred["chat_id"], "text": text[:4000],
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{cred['bot_token']}/sendMessage", data=body,
        headers={"Content-Type": "application/json", "User-Agent": "plaza-ops"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError(f"텔레그램 HTTP {r.status}")


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    os.replace(tmp, path)
