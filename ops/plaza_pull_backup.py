#!/usr/bin/env python3
"""광장 오프사이트 백업: VM 의 매일 백업 파일을 운영자 기기로 끌어와 검증하고 날짜 기준으로 회전한다.

VM 은 `server/tools/plaza_backup.py` 가 매일 SQLite backup API 로 만든 파일을 14세대 갖고 있다.
그건 같은 디스크 위의 사본이라 VM 이 통째로 죽으면 같이 간다. 이 잡은 그 파일을 **그대로** 가져온다.
살아 있는 DB 를 복사하지 않는다(WAL 이라 최신 트랜잭션이 조용히 빠진다) — 이미 일관 상태로 뜬 파일만 옮긴다.

한 세대 = <backup_dest>/<VM 백업 시각>/
  plaza-<시각>.db       VM 백업 파일 그대로 (sha256 을 VM 쪽 값과 대조)
  conf-plaza.tar.gz     VM 광장 폴더의 .env · config/ · secret/ · DEPLOYED  (가장 새 세대에만)
                        🔴 secret 은 가입 키 HMAC 비밀이다. 잃으면 DB 를 되살려도 기존 키가 안 맞는다
  <cert_archive_name>   certbot 볼륨에서 이 도메인과 extra_cert_lineages 이름들 몫만, 읽기 전용 마운트로
                        (가장 새 세대에만)
  MANIFEST.json         출처·크기·sha256·표별 행 수
전부 0700/0600. 어떤 리포에도 커밋하지 않는다.

검증 (받은 사본을 여기서 연다, immutable=1 이라 옆에 -wal 을 만들지 않는다)
  - PRAGMA integrity_check == ok
  - 표 agents·threads·posts·events·meta 가 있고 events 가 비어 있지 않다
  - VM backup.log 가 그 파일에 적은 행 수(agents·posts·events)와 같다
    크론 밖에서 손으로 뜬 백업(배포 직전 등)은 backup.log 에 줄이 없다. 그 세대는 이 대조만 빠지고
    나머지 검증은 그대로 거친다. 받은 결과의 notes 와 MANIFEST 의 vm_log_rows=null 로 남는다
  - 앞 세대보다 agents·threads·posts·events 가 줄지 않았다 (서버는 held 말고는 지우지 않는다)
하나라도 어긋나면 그 세대는 만들지 않고(반쯤 쓴 폴더 삭제) 알림 + exit 1. 회전은 전부 성공한 뒤에만.
한 세대가 실패해도 뒤 세대는 계속 받는다(「줄지 않았다」는 여기 있는 바로 앞 세대와 댄다).
실패한 세대는 여기 없으니 다음 회차에도 다시 시도되고, 실패하는 동안은 계속 errors 에 남는다.

보관 (2026-10-08 바꿈, 전엔 「세대 30」):
  - 크론 세대(시각이 backup_cron_hhmm, 기본 0440)는 최근 KEEP_CRON_DAYS(30)일
  - 크론 밖 세대(배포 직전 손 백업 등)는 가장 새 것 KEEP_OTHER(14)개
  세대 수로 세면 배포가 몰린 주에 크론 밖 세대가 칸을 먹어 30세대가 열하루치까지 줄었다.
  가장 새 세대는 어느 규칙으로도 지우지 않는다. 지울 목록만 보려면 --plan-rotate(VM 접속·삭제 없음).

빠진 날 메우기: 여기 있는 가장 오래된 세대보다 새로운 VM 파일 중 여기 없는 것은 전부 가져온다. 하루 VM 이
얼어 못 가져와도 VM 이 14세대를 들고 있으니 다음 날 같이 온다. 가장 새 VM 백업이 26시간을 넘으면 VM 크론이
멈춘 것으로 보고 알린다.

설치별 값(도메인·폴더·볼륨 이름·상태 폴더·알림)은 ops/opslib.py 의 설정 파일에서 읽는다.

    python3 ops/plaza_pull_backup.py            # 잡이 부르는 모양
    python3 ops/plaza_pull_backup.py --no-alert # 손으로 돌려 볼 때 (알림 없이 exit 코드만)
    python3 ops/plaza_pull_backup.py --plan-rotate  # 회전이 지울 세대만 출력
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import KST, conf, log, path_conf, save_json, send_telegram, ssh  # noqa: E402

DOMAIN = conf("domain")
DEST = Path(os.environ["PLAZA_BACKUP_DEST"]) if "PLAZA_BACKUP_DEST" in os.environ else path_conf("backup_dest")
STATE = path_conf("state_dir") / "plaza_backup_pull.json"
LOG_HINT = conf("backup_log_hint", "")
REMOTE = conf("remote_dir", "~/plaza")
CERTBOT_VOLUME = conf("certbot_volume", "certbot_conf")
CERT_ARCHIVE = conf("cert_archive_name", "certs.tar.gz")
KEEP_CRON_DAYS = 30
KEEP_OTHER = 14         # VM 이 14세대를 든다 — 그보다 적으면 지운 크론 밖 세대를 다음 회차 「빠진 날 메우기」가 다시 받아 온다
CRON_HHMM = str(conf("backup_cron_hhmm", "0440"))
STALE_HOURS = 26
NAME_RE = re.compile(r"^plaza-(\d{8}-\d{6})\.db$")
GEN_RE = re.compile(r"^\d{8}-\d{6}$")
MUST_TABLES = ("agents", "threads", "posts", "events", "meta")
NEVER_SHRINK = ("agents", "threads", "posts", "events")

LIST_CMD = r"""cd {remote}/backups || exit 3
for f in plaza-*.db; do [ -f "$f" ] && echo "F $f $(stat -c %s "$f") $(sha256sum < "$f" | cut -d' ' -f1)"; done
echo "L"; tail -n 60 {remote}/logs/backup.log 2>/dev/null""".replace("{remote}", REMOTE)
CONF_CMD = f"tar czf - -C {REMOTE} .env config secret DEPLOYED"
CERT_DOMAINS = [DOMAIN] + [conf("extra_cert_domains", {})[label] for label in conf("extra_cert_lineages", [])]
CERT_CMD = (f"docker run --rm -v {CERTBOT_VOLUME}:/c:ro alpine tar czf - -C /c "
            + " ".join(f"live/{d} archive/{d} renewal/{d}.conf" for d in CERT_DOMAINS))


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stamp_time(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp, "%Y%m%d-%H%M%S").replace(tzinfo=KST)


def remote_inventory():
    files, logrows, in_log = {}, {}, False
    last_log = None
    for line in ssh(LIST_CMD).splitlines():
        if line == "L":
            in_log = True
            continue
        if not in_log and line.startswith("F "):
            _, name, size, digest = line.split()
            if NAME_RE.match(name):
                files[name] = {"size": int(size), "sha256": digest}
        elif in_log and line.startswith("{"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            last_log = rec
            if rec.get("ok") and rec.get("file"):
                logrows[rec["file"]] = rec.get("rows") or {}
    return files, logrows, last_log


def local_gens() -> list[str]:
    return sorted(p.name for p in DEST.iterdir() if p.is_dir() and GEN_RE.match(p.name))


def verify_db(path: Path, vm_rows: dict, prev_rows: dict | None) -> dict:
    conn = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"integrity_check 실패: {ok}")
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        rows = {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in sorted(names)}
    finally:
        conn.close()
    missing = [t for t in MUST_TABLES if t not in rows]
    if missing:
        raise RuntimeError(f"표가 없다: {missing}")
    if rows["events"] == 0:
        raise RuntimeError("events(원장)가 비어 있다")
    diff = {k: (v, rows.get(k)) for k, v in (vm_rows or {}).items() if rows.get(k) != v}
    if diff:
        raise RuntimeError(f"VM 로그 행 수와 다르다 (VM, 맥): {diff}")
    if prev_rows:
        shrunk = {t: (prev_rows[t], rows[t]) for t in NEVER_SHRINK
                  if t in prev_rows and rows[t] < prev_rows[t]}
        if shrunk:
            raise RuntimeError(f"앞 세대보다 줄었다 (앞, 지금): {shrunk}")
    return rows


def tar_names(blob_path: Path) -> set[str]:
    with tarfile.open(blob_path, "r:gz") as t:
        return {m.name.removeprefix("./") for m in t.getmembers()}   # lstrip 은 .env 의 점까지 먹는다


def pull_one(name: str, meta: dict, vm_rows: dict | None, prev_rows: dict | None, with_extras: bool) -> dict:
    stamp = NAME_RE.match(name).group(1)
    final = DEST / stamp
    part = DEST / f".{stamp}.part"
    shutil.rmtree(part, ignore_errors=True)
    old = os.umask(0o077)
    try:
        part.mkdir()
        blob = ssh(f"cat {REMOTE}/backups/{name}", binary=True)
        if len(blob) != meta["size"] or sha256(blob) != meta["sha256"]:
            raise RuntimeError(f"전송 중 어긋남: VM {meta['size']}B/{meta['sha256'][:12]} "
                               f"맥 {len(blob)}B/{sha256(blob)[:12]}")
        db = part / name
        db.write_bytes(blob)
        rows = verify_db(db, vm_rows, prev_rows)
        files = {name: {"bytes": len(blob), "sha256": meta["sha256"]}}
        if with_extras:
            for fname, cmd, must in (("conf-plaza.tar.gz", CONF_CMD, {"secret/secret", ".env"}),
                                     (CERT_ARCHIVE, CERT_CMD,
                                      {f"live/{DOMAIN}/fullchain.pem", f"renewal/{DOMAIN}.conf"})):
                b = ssh(cmd, binary=True, timeout=300)
                (part / fname).write_bytes(b)
                lacking = must - tar_names(part / fname)
                if lacking:
                    raise RuntimeError(f"{fname} 에 빠진 것: {sorted(lacking)}")
                files[fname] = {"bytes": len(b), "sha256": sha256(b)}
        manifest = {"generation": stamp, "source": f"VM:{REMOTE}/backups/{name}",
                    "pulled_at": dt.datetime.now(KST).isoformat(timespec="seconds"),
                    "rows": rows, "vm_log_rows": vm_rows, "files": files,
                    "extras_note": None if with_extras else "빠진 날 메우기 세대 — DB 만"}
        (part / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        for p in part.iterdir():
            os.chmod(p, 0o600)
        os.chmod(part, 0o700)
        part.rename(final)
        return manifest
    except Exception:
        shutil.rmtree(part, ignore_errors=True)
        raise
    finally:
        os.umask(old)


def is_cron_gen(gen: str) -> bool:
    return gen[9:13] == CRON_HHMM


def rotate_plan(now: dt.datetime | None = None) -> list[str]:
    """지울 세대 목록. 크론 세대는 날짜(최근 KEEP_CRON_DAYS 일), 크론 밖 세대는 개수(KEEP_OTHER)."""
    gens = local_gens()
    if not gens:
        return []
    cutoff = (now or dt.datetime.now(KST)) - dt.timedelta(days=KEEP_CRON_DAYS)
    drop = [g for g in gens if is_cron_gen(g) and stamp_time(g) < cutoff]
    other = [g for g in gens if not is_cron_gen(g)]
    drop += other[:-KEEP_OTHER] if len(other) > KEEP_OTHER else []
    return sorted(g for g in drop if g != gens[-1])


def rotate() -> list[str]:
    drop = rotate_plan()
    for g in drop:
        shutil.rmtree(DEST / g)
    return drop


def prev_rows_of(gen: str | None) -> dict | None:
    if not gen:
        return None
    try:
        return json.loads((DEST / gen / "MANIFEST.json").read_text())["rows"]
    except (OSError, ValueError, KeyError):
        return None


def run() -> dict:
    DEST.mkdir(parents=True, exist_ok=True)
    os.chmod(DEST, 0o700)
    errors, pulled, notes = [], [], []
    files, logrows, last_log = remote_inventory()
    if not files:
        raise RuntimeError(f"VM 에 백업 파일이 하나도 없다 ({REMOTE}/backups)")
    names = sorted(files)
    have = local_gens()
    oldest_local = have[0] if have else None
    # 앞 회차에 실패한 세대(가운데 구멍)도 다시 잡히게 가장 새 것이 아니라 가장 오래된 것과 댄다
    todo = [n for n in names if NAME_RE.match(n).group(1) not in have
            and (oldest_local is None or NAME_RE.match(n).group(1) > oldest_local)]
    if oldest_local is None:
        todo = todo[-1:]                      # 처음엔 가장 새 것 하나만
    log(f"VM 세대 {len(names)} · 맥 세대 {len(have)} · 가져올 것 {todo or '없음'}")

    for n in todo:
        stamp = NAME_RE.match(n).group(1)
        older = [g for g in local_gens() if g < stamp]
        try:
            m = pull_one(n, files[n], logrows.get(n), prev_rows_of(older[-1] if older else None),
                         with_extras=(n == names[-1]))
            pulled.append(m["generation"])
            log(f"받음 {m['generation']}: " + ", ".join(f"{k} {v['bytes']:,}B" for k, v in m["files"].items())
                + f" · 행 agents {m['rows']['agents']} posts {m['rows']['posts']} events {m['rows']['events']}")
            if n not in logrows:
                notes.append(f"{stamp}: VM backup.log 에 줄 없음(크론 밖 백업) — 로그 행 수 대조 없이 받음")
                log(f"주의 {notes[-1]}")
        except Exception as e:
            errors.append(f"{n}: {type(e).__name__}: {e}")
            log(f"실패 {n}: {e}")

    newest_vm = NAME_RE.match(names[-1]).group(1)
    age_h = (dt.datetime.now(KST) - stamp_time(newest_vm)).total_seconds() / 3600
    if age_h > STALE_HOURS:
        errors.append(f"VM 가장 새 백업이 {age_h:.0f}시간 전({newest_vm}) — VM 백업 크론이 멈췄다")
    if last_log and not last_log.get("ok"):
        errors.append(f"VM backup.log 마지막 줄이 실패: {str(last_log.get('error'))[:200]}")

    dropped = rotate() if not errors else []
    gens = local_gens()
    return {"ok": not errors, "errors": errors, "notes": notes, "pulled": pulled, "dropped": dropped,
            "newest_local": gens[-1] if gens else None, "local_generations": len(gens),
            "newest_vm": newest_vm, "vm_generations": len(names),
            "at": dt.datetime.now(KST).isoformat(timespec="seconds")}


def main(argv) -> int:
    if "--plan-rotate" in argv:            # 지울 목록만 출력(VM 접속·삭제·상태 파일 쓰기 없음)
        gens = local_gens()
        drop = rotate_plan()
        print(json.dumps({"dest": str(DEST), "local_generations": len(gens),
                          "cron": sum(map(is_cron_gen, gens)), "other": sum(not is_cron_gen(g) for g in gens),
                          "would_drop": drop, "would_keep": len(gens) - len(drop)}, ensure_ascii=False))
        return 0
    alert = "--no-alert" not in argv
    try:
        res = run()
    except Exception as e:
        res = {"ok": False, "errors": [f"{type(e).__name__}: {e}"], "pulled": [],
               "at": dt.datetime.now(KST).isoformat(timespec="seconds")}
    if "PLAZA_BACKUP_DEST" not in os.environ and "PLAZA_VM" not in os.environ:
        save_json(STATE, res)               # 시험 실행(다른 폴더·다른 호스트)이 일일 보고를 덮지 않게
    print(json.dumps(res, ensure_ascii=False), flush=True)
    if res["ok"]:
        return 0
    if alert:
        send_telegram("🚨 광장 백업 당겨오기 실패\n"
                      + "\n".join(res["errors"])
                      + f"\n\n사본 {DEST}" + (f" · 로그 {LOG_HINT}" if LOG_HINT else ""))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
