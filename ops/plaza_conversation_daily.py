#!/usr/bin/env python3
"""대화 측정기를 매일 한 번 돌려 시계열로 남긴다 — 설정의 state_dir/plaza_conversation/<날짜>.json.

손으로만 돌리던 ops/plaza_conversation_meter.py 를 기기 백업 사본 가장 새 세대에 돌린다(백업 당겨오기 뒤에 건다).
창 끝 = 그 세대의 시각이라 같은 세대를 두 번 돌려도 같은 값이 나온다. 문안을 바꾼 효과를 회차마다 숫자로 보려는 것
(굴러가는 창에선 증거가 만료된다 — 그날 찍어 두지 않으면 다음 날엔 다시 못 낸다).

  같은 소유주 묶음(--ours)은 설정 conversation_ours (닉네임·id 목록). 결과에 닉네임이 들어가니 리포 밖에만 쓴다.
  요약 한 줄(summary)은 plaza_ops_status.py 가 읽어 「대화」 칸에 싣는다.

    python3 ops/plaza_conversation_daily.py          # 잡이 부르는 모양
    python3 ops/plaza_conversation_daily.py --dry    # 파일을 안 쓰고 출력만
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import KST, conf, path_conf, save_json  # noqa: E402
import plaza_conversation_meter as M  # noqa: E402

DAYS = 7
OUT_DIR = path_conf("state_dir") / "plaza_conversation"


def newest_copy() -> tuple[Path, dt.datetime]:
    gens = sorted(p for p in path_conf("backup_dest").iterdir() if p.is_dir() and p.name[:1].isdigit())
    if not gens:
        raise SystemExit("백업 사본 세대가 없다")
    db = next(iter(gens[-1].glob("plaza-*.db")), None)
    if db is None:
        raise SystemExit(f"세대 {gens[-1].name} 에 DB 가 없다")
    return db, dt.datetime.strptime(gens[-1].name, "%Y%m%d-%H%M%S").replace(tzinfo=KST)


def summary(res: dict) -> dict:
    w = res[f"last_{DAYS}d"]
    r = w["response"]
    p = w["pairs"]
    out = {"roots": w["roots"], "answered": r["all"]["rate"]["n"],
           "out_roots": r["out"]["rate"]["of"], "out_answered": r["out"]["rate"]["n"],
           "mutual_pairs": p["all"]["mutual"], "out_out_mutual": p["out_out"]["mutual"],
           "depth_max": r["all"]["depth"]["max"], "first_answer_hours_median": r["all"]["first_answer_hours"]["median"]}
    out["line"] = (f"답 받은 글 {out['answered']}/{out['roots']} · 밖 글 응답 {out['out_answered']}/{out['out_roots']}"
                   f" · 쌍방 {out['mutual_pairs']}쌍(밖↔밖 {out['out_out_mutual']}) · 사슬 최대 {out['depth_max']}")
    return out


def main(argv) -> int:
    db, at = newest_copy()
    ours = conf("conversation_ours", [])
    res = M.run(str(db), ",".join(ours) if ours else None, None, DAYS, at)
    out = {"generated_at": dt.datetime.now(KST).isoformat(timespec="seconds"), "copy_at": at.isoformat(timespec="seconds"),
           "days": DAYS, "summary": summary(res), "meter": res}
    if "--dry" not in argv:
        save_json(OUT_DIR / f"{at:%Y-%m-%d}.json", out)
    print(json.dumps(out["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
