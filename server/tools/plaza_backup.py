"""운영 DB 백업: SQLite backup API → integrity_check → 행 수 대조 → 회전.

살아 있는 DB 는 WAL 이라 cp 로 뜨면 최신 트랜잭션이 조용히 빠진다.
docker 배포(deploy/)에서는 컨테이너 안에서 돈다(DB 가 볼륨 안에 있고, 호스트에 sqlite3 CLI 가 없어도 되게):

  docker exec plaza_web python -m server.tools.plaza_backup --db /data/plaza.db --out /backups --keep 14

한 줄 JSON 을 찍는다. 실패하면 exit 1 이고 반쯤 쓴 파일은 지운다. 회전은 성공한 뒤에만 한다
(실패가 이어질 때 멀쩡한 옛 세대부터 지워지지 않게).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
PREFIX = "plaza-"


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def backup(db: Path, out: Path, keep: int) -> dict:
    if not db.exists():
        raise FileNotFoundError(f"DB 가 없다: {db}")
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    dst = out / f"{PREFIX}{stamp}.db"
    tmp = out / f".{dst.name}.part"
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    try:
        old = os.umask(0o077)
        try:
            dconn = sqlite3.connect(tmp)
        finally:
            os.umask(old)
        with dconn:
            src.backup(dconn)
        # 같은 읽기 트랜잭션이 아니라 원본은 그새 늘 수 있다. 사본 행 수 ≤ 원본 행 수 인지만 본다
        got = counts(dconn)
        want = counts(src)
        ok = dconn.execute("PRAGMA integrity_check").fetchone()[0]
        dconn.close()
        short = {t: (got.get(t), n) for t, n in want.items() if got.get(t) is None or got[t] > n}
        if ok != "ok" or short:
            raise RuntimeError(f"검사 실패: integrity={ok} 어긋난 표={short}")
        os.chmod(tmp, 0o600)
        tmp.rename(dst)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        src.close()
    gens = sorted(p for p in out.glob(f"{PREFIX}*.db") if p.is_file())
    removed = [p.name for p in gens[:-keep]] if keep > 0 else []
    for name in removed:
        (out / name).unlink()
    return {"ok": True, "file": dst.name, "bytes": dst.stat().st_size, "integrity": "ok",
            "rows": {k: got[k] for k in ("agents", "posts", "events") if k in got},
            "kept": min(len(gens), keep) if keep > 0 else len(gens), "removed": removed,
            "at": dt.datetime.now(KST).isoformat(timespec="seconds")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", type=int, default=14, help="남길 세대 수 (0 이면 지우지 않는다)")
    a = ap.parse_args(argv)
    try:
        res = backup(Path(a.db), Path(a.out), a.keep)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e),
                          "at": dt.datetime.now(KST).isoformat(timespec="seconds")}, ensure_ascii=False))
        return 1
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
