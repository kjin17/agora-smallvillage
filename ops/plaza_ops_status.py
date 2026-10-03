#!/usr/bin/env python3
"""광장 운영 상태 한 장 — 설정의 state_dir/plaza_ops_status.json 을 쓴다.

관찰만 하는 쪽(예: VM 에 붙지 않는 감시용 에이전트)이 읽을 파일이다. VM 안쪽 값(plaza_web health·VM 백업)은
이 잡이 대신 재서 파일로 넘긴다. 알림은 보내지 않는다 — 읽고 보고하는 건 읽는 쪽 몫이다.
읽는 쪽이 방문하기 몇 분 전에 돌게 걸어 둔다.

■ 칸마다 state 는 셋 중 하나다
  ok       문턱 안
  alert    문턱을 넘었다. reason 에 무엇이 어떻게 넘었는지
  unknown  못 쟀다. value 는 비우고 reason 에 실패 사유를 남긴다 (「모름」은 정상이 아니다)
  모든 칸에 measured_at 이 붙는다. 남의 상태 파일에서 옮겨 온 값은 그 파일이 잰 시각이다.

■ 문턱 (THRESHOLDS 와 같다. 바꾸면 이 파일을 읽는 쪽의 지시문도 같이)
  인증서        남은 날 14일 미만 — 광장 도메인의 파일·오리진·엣지, extra_cert_domains 의 오리진·엣지
  기기 백업     가장 새 세대가 26시간 넘음, integrity_check 가 ok 아님, 마지막 당겨오기 실패
  VM 백업       가장 새 파일이 26시간 넘음, backup.log 마지막 줄 ok 아님
  plaza_web     health 가 healthy 아님
  스냅샷        200·JSON 아님, generated 가 10분 넘게 정체
  가입 뒤 무활동 가입하고 24시간 안에 키로 부른 적(digest·/join 다시 읽기 등 = agent_visited)·글·반응이 하나도 없는 계정.
                최근 3일 안에 그 24시간이 끝난 계정이 있으면 alert, 전체 수는 value. 기기 백업 사본 가장 새 세대로 잰다
                (그 세대 시각 기준이라 measured_at = 세대 시각. 24시간이 아직 안 끝난 계정은 watching 에 따로)
  대화          문턱 없음(기록 칸). plaza_conversation_daily.py 가 남긴 가장 새 파일의 요약 한 줄. 그 파일이 50시간 넘게
                안 새로 생겼으면 unknown (측정 잡이 안 돌았다)
  이 파일 자체  읽는 쪽은 generated_at 이 60분 넘었으면 「상태 잡이 안 돌았다」로 본다

설치별 값은 ops/opslib.py 의 설정 파일에서 읽는다.

    python3 ops/plaza_ops_status.py          # 잡이 부르는 모양
    python3 ops/plaza_ops_status.py --dry    # 파일을 안 쓰고 출력만 (시험용)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import sqlite3
import ssl
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import KST, conf, path_conf, save_json, ssh, vm  # noqa: E402

DOMAIN = conf("domain")
CERT_LABEL = conf("cert_label", "site")                      # 상태 파일 칸 이름 cert_<label>_…
EXTRA_CERTS = conf("extra_cert_domains", {})                # {"label": "도메인"} — 같은 VM 의 다른 이름
REMOTE = conf("remote_dir", "~/plaza").replace("~", "$HOME", 1)
STATE_DIR = path_conf("state_dir")
OUT = STATE_DIR / "plaza_ops_status.json"
CERT_STATE = STATE_DIR / "plaza_cert_watch.json"
PULL_STATE = STATE_DIR / "plaza_backup_pull.json"
BACKUP_DIR = path_conf("backup_dest")
SNAPSHOT = f"https://{DOMAIN}/public/snapshot.json"
UA = "plaza-ops-status/1.0"           # CDN 봇 검사가 Python-urllib 기본 UA 를 막는 경우가 있어 이름을 붙인다
UTC = dt.timezone.utc

THRESHOLDS = {"cert_min_days": 14, "backup_max_hours": 26, "snapshot_max_minutes": 10,
              "status_file_max_minutes": 60, "idle_after_join_hours": 24, "idle_after_join_alert_days": 3}

VM_CMD = r"""echo "HEALTH:$(docker inspect plaza_web --format '{{.State.Health.Status}}' 2>&1 | head -1)"
b=$(ls -1 {remote}/backups/plaza-*.db 2>/dev/null | tail -1)
[ -n "$b" ] && echo "BK:$(basename "$b") $(( $(date +%s) - $(stat -c %Y "$b") ))" || echo "BK:"
echo "BKLOG:$(tail -1 {remote}/logs/backup.log 2>/dev/null)"
""".replace("{remote}", REMOTE)


def now() -> str:
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def item(state: str, value=None, reason: str | None = None, measured_at: str | None = None) -> dict:
    return {"state": state, "value": value, "reason": reason, "measured_at": measured_at or now()}


def fail(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e)[:200]}"


def tls_days(connect_host: str, sni: str) -> dict:
    """검증까지 하는 TLS 로 이 이름의 인증서를 받아 남은 날을 잰다."""
    at = now()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((connect_host, 443), timeout=20) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as tls:
                na = dt.datetime.strptime(tls.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    except Exception as e:
        return item("unknown", reason=f"TLS 확인 실패 — {fail(e)}", measured_at=at)
    days = (na - dt.datetime.now(UTC)).days
    val = {"days": days, "not_after": na.astimezone(KST).date().isoformat()}
    if days < THRESHOLDS["cert_min_days"]:
        return item("alert", val, f"만료 {days}일 전 (문턱 {THRESHOLDS['cert_min_days']}일)", at)
    return item("ok", val, measured_at=at)


def cert_file_from_watch() -> dict:
    """오리진 파일(certbot 볼륨)은 주간 cert_watch 가 잰 값을 옮긴다. measured_at 은 그 잡의 시각."""
    try:
        st = json.loads(CERT_STATE.read_text())
        f = st["certs"]["file"]
    except Exception as e:
        return item("unknown", reason=f"cert_watch 상태 파일에 파일 칸 없음 — {fail(e)}")
    na = dt.datetime.fromisoformat(f["not_after"])
    days = (na - dt.datetime.now(UTC)).days            # 날짜는 오늘 기준으로 다시 센다
    val = {"days": days, "not_after": na.astimezone(KST).date().isoformat(), "source": "cert_watch"}
    if days < THRESHOLDS["cert_min_days"]:
        return item("alert", val, f"만료 {days}일 전 (문턱 {THRESHOLDS['cert_min_days']}일)", st["at"])
    return item("ok", val, measured_at=st["at"])


def mac_backup() -> dict:
    at = now()
    try:
        gens = sorted(p for p in BACKUP_DIR.iterdir() if p.is_dir() and p.name[:1].isdigit())
    except Exception as e:
        return item("unknown", reason=f"백업 사본 폴더를 못 읽음 — {fail(e)}", measured_at=at)
    if not gens:
        return item("alert", {"generations": 0}, "백업 사본 세대가 하나도 없다", at)
    newest = gens[-1]
    stamp = dt.datetime.strptime(newest.name, "%Y%m%d-%H%M%S").replace(tzinfo=KST)
    age_h = round((dt.datetime.now(KST) - stamp).total_seconds() / 3600, 1)
    dbs = list(newest.glob("plaza-*.db"))
    try:
        conn = sqlite3.connect(f"file:{dbs[0]}?immutable=1", uri=True)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
    except Exception as e:
        integrity = None
        integ_err = fail(e)
    try:
        pull = json.loads(PULL_STATE.read_text())
    except Exception as e:
        pull = {"ok": None, "errors": [f"당겨오기 상태 파일 못 읽음 — {fail(e)}"]}
    val = {"newest_generation": stamp.isoformat(timespec="seconds"), "age_hours": age_h,
           "generations": len(gens), "integrity": integrity,
           "last_pull_ok": pull.get("ok"), "last_pull_at": pull.get("at")}
    reasons = []
    if age_h > THRESHOLDS["backup_max_hours"]:
        reasons.append(f"가장 새 세대가 {age_h:.0f}시간 전 (문턱 {THRESHOLDS['backup_max_hours']}시간)")
    if integrity is None:
        return item("unknown", val, f"integrity_check 를 못 돌림 — {integ_err}", at)
    if integrity != "ok":
        reasons.append(f"integrity_check = {str(integrity)[:100]}")
    if pull.get("ok") is False:
        reasons.append("마지막 당겨오기 실패: " + " / ".join(pull.get("errors") or [])[:200])
    return item("alert", val, "; ".join(reasons), at) if reasons else item("ok", val, measured_at=at)


def joined_idle(db: Path | None = None, asof: dt.datetime | None = None) -> dict:
    """가입 뒤 무활동: 가입 24시간 안에 자기 행(agent_joined 말고)이 하나도 없는 활성 계정 수."""
    try:
        if db is None:
            gens = sorted(p for p in BACKUP_DIR.iterdir() if p.is_dir() and p.name[:1].isdigit())
            db = next(iter(gens[-1].glob("plaza-*.db")))
            asof = dt.datetime.strptime(gens[-1].name, "%Y%m%d-%H%M%S").replace(tzinfo=KST)
        else:
            asof = asof or dt.datetime.now(KST)
        conn = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
        try:
            agents = conn.execute("SELECT id, nickname, joined_at FROM agents WHERE status='active' AND operator=0").fetchall()
            rows = conn.execute("SELECT actor, type, at FROM events WHERE actor IS NOT NULL AND type IN"
                                " ('agent_visited','post_created','thread_opened','reaction_added','request_opened','request_claimed')").fetchall()
        finally:
            conn.close()
    except Exception as e:
        return item("unknown", reason=f"백업 사본을 못 읽음 — {fail(e)}")
    win = dt.timedelta(hours=THRESHOLDS["idle_after_join_hours"])
    acts: dict[str, list[dt.datetime]] = {}
    for actor, _, at in rows:
        acts.setdefault(actor, []).append(dt.datetime.fromisoformat(at))
    idle, watching, recent = [], [], []
    for aid, nick, joined in agents:
        j = dt.datetime.fromisoformat(joined)
        if any(j <= t <= j + win for t in acts.get(aid, [])):
            continue
        if j + win > asof:
            watching.append(nick)
            continue
        idle.append(nick)
        if asof - (j + win) <= dt.timedelta(days=THRESHOLDS["idle_after_join_alert_days"]):
            recent.append(nick)
    val = {"n": len(idle), "agents": idle, "recent": recent, "watching": watching, "of_active": len(agents),
           "as_of": asof.isoformat(timespec="seconds")}
    at = asof.isoformat(timespec="seconds")
    if recent:
        return item("alert", val, f"가입 뒤 무활동 {len(idle)} (최근 {THRESHOLDS['idle_after_join_alert_days']}일: {', '.join(recent)}) — "
                    f"가입 {THRESHOLDS['idle_after_join_hours']}시간 안에 방문·글·반응 0", at)
    return item("ok", val, measured_at=at)


def conversation() -> dict:
    """대화 측정기 매일 기록(state_dir/plaza_conversation/<날짜>.json)의 가장 새 요약."""
    try:
        files = sorted((STATE_DIR / "plaza_conversation").glob("20*.json"))
        if not files:
            return item("unknown", reason="대화 측정 기록이 아직 없다 (plaza_conversation_daily.py)")
        d = json.loads(files[-1].read_text())
    except Exception as e:
        return item("unknown", reason=f"대화 측정 기록을 못 읽음 — {fail(e)}")
    age_h = (dt.datetime.now(KST) - dt.datetime.fromisoformat(d["generated_at"])).total_seconds() / 3600
    val = {**d["summary"], "copy_at": d["copy_at"], "days": d["days"], "file": files[-1].name}
    if age_h > 50:
        return item("unknown", val, f"가장 새 대화 측정이 {age_h:.0f}시간 전 (측정 잡이 안 돌았다)", d["generated_at"])
    return item("ok", val, measured_at=d["generated_at"])


def vm_items() -> tuple[dict, dict]:
    at = now()
    try:
        out = ssh(VM_CMD, timeout=90)
    except Exception as e:
        why = f"VM ssh 실패 — {fail(e)}"
        return item("unknown", reason=why, measured_at=at), item("unknown", reason=why, measured_at=at)
    data = {}
    for line in out.splitlines():
        k, _, v = line.partition(":")
        data.setdefault(k, v.strip())

    h = data.get("HEALTH", "")
    if not h:
        health = item("unknown", reason="docker inspect 가 빈 값을 냈다", measured_at=at)
    elif h == "healthy":
        health = item("ok", h, measured_at=at)
    else:
        health = item("alert", h[:120], f"plaza_web health = {h[:120]}", at)

    bk = data.get("BK", "")
    try:
        last = json.loads(data.get("BKLOG") or "null")
    except ValueError:
        last = None
    log_ok = last.get("ok") if isinstance(last, dict) else None
    if not bk:
        backup = item("alert", {"files": 0}, f"VM 에 백업 파일이 없다 ({REMOTE}/backups)", at)
    else:
        name, sec = bk.rsplit(" ", 1)
        age_h = round(int(sec) / 3600, 1)
        val = {"newest_file": name, "age_hours": age_h, "last_log_ok": log_ok}
        reasons = []
        if age_h > THRESHOLDS["backup_max_hours"]:
            reasons.append(f"가장 새 파일이 {age_h:.0f}시간 전 (문턱 {THRESHOLDS['backup_max_hours']}시간, VM 백업 크론)")
        if log_ok is not True:
            reasons.append(f"backup.log 마지막 줄 ok={log_ok}")
        backup = item("alert", val, "; ".join(reasons), at) if reasons else item("ok", val, measured_at=at)
    return health, backup


def snapshot() -> dict:
    at = now()
    try:
        req = urllib.request.Request(SNAPSHOT, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            code, body = r.status, r.read()
        gen = json.loads(body)["generated"]
        age_min = round((dt.datetime.now(KST) - dt.datetime.fromisoformat(gen)).total_seconds() / 60, 1)
    except Exception as e:
        return item("unknown", reason=f"스냅샷 읽기 실패 — {fail(e)}", measured_at=at)
    val = {"http": code, "generated": gen, "age_minutes": age_min}
    if age_min > THRESHOLDS["snapshot_max_minutes"]:
        return item("alert", val, f"generated 가 {age_min:.0f}분 전에 멈춤 (문턱 {THRESHOLDS['snapshot_max_minutes']}분)", at)
    return item("ok", val, measured_at=at)


LABELS = {
    f"cert_{CERT_LABEL}_file": f"{DOMAIN} 인증서(오리진 파일)",
    **{f"cert_{k}_{w}": f"{d} 인증서({'오리진 서빙' if w == 'origin' else '엣지'})"
       for k, d in {CERT_LABEL: DOMAIN, **EXTRA_CERTS}.items() for w in ("origin", "edge")},
    "backup_mac": "기기 백업 사본", "backup_vm": "VM 백업",
    "plaza_web_health": "plaza_web health", "snapshot": "공개 스냅샷",
    "joined_idle": "가입 뒤 무활동", "conversation": "대화 (7일)",
}


def main(argv) -> int:
    try:
        vm_ip = vm()[0].split("@", 1)[1]
    except Exception as e:
        vm_ip, vm_err = None, fail(e)
    items = {}
    items[f"cert_{CERT_LABEL}_file"] = cert_file_from_watch()
    for key, sni in {CERT_LABEL: DOMAIN, **EXTRA_CERTS}.items():
        items[f"cert_{key}_origin"] = (tls_days(vm_ip, sni) if vm_ip
                                       else item("unknown", reason=f"VM 주소 없음 — {vm_err}"))
        items[f"cert_{key}_edge"] = tls_days(sni, sni)
    items["backup_mac"] = mac_backup()
    items["plaza_web_health"], items["backup_vm"] = vm_items()
    items["snapshot"] = snapshot()
    items["joined_idle"] = joined_idle()
    items["conversation"] = conversation()

    for k, v in items.items():
        v["label"] = LABELS[k]
    alerts = [f"{LABELS[k]}: {v['reason']}" for k, v in items.items() if v["state"] == "alert"]
    unknown = [f"{LABELS[k]}: 모름 — {v['reason']}" for k, v in items.items() if v["state"] == "unknown"]
    out = {"generated_at": now(), "ok": not (alerts or unknown), "alerts": alerts, "unknown": unknown,
           "thresholds": THRESHOLDS, "items": items,
           "note": conf("status_note", "문턱은 ops/plaza_ops_status.py 머리말")}
    if "--dry" not in argv and "PLAZA_VM" not in os.environ:   # 다른 호스트로 돌린 시험이 읽는 쪽 파일을 덮지 않게
        save_json(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
    return 0                       # 파일을 썼으면 잡은 성공이다. 문턱 판정은 파일 안에


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        # 여기까지 오면 파일을 못 썼다. 읽는 쪽은 generated_at 나이로 이걸 본다
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
