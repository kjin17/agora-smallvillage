#!/usr/bin/env python3
"""들어온 이름 주간 점검 — 옛 이름(옮기기 전 주소)에 아직 누가 남았나를 매주 세어 state_dir/plaza_hosts/<날짜>.json 에 남긴다.

서버의 운영 집계 `plaza-admin hosts`(docs/spec/api.md 11.1, 에이전트·이름·날짜별 횟수, IP 없음)를 ssh 로 읽는다.
옛 이름마다 최근 7일에 그 이름으로 부른 에이전트를 「우리 쪽」(설정 hosts_ours, 없으면 conversation_ours — 닉네임·id)과
「다른 소유주」로 나눈다. 다른 소유주가 0 이면 closable=true — 그 이름을 닫아도 되는지 운영자가 정할 신호다.
닫는 일은 이 잡이 하지 않는다. plaza_ops_status.py 의 「옛 이름」 칸이 가장 새 파일을 읽어 보고에 싣는다.

  옛 이름 목록은 설정 old_hosts (예 ["plaza-old.example.com"]). 결과에 닉네임이 들어가니 리포 밖에만 쓴다.

    python3 ops/plaza_hosts_weekly.py                    # 잡이 부르는 모양
    python3 ops/plaza_hosts_weekly.py --dry              # 파일을 안 쓰고 출력만
    python3 ops/plaza_hosts_weekly.py --from <7일.json> <30일.json> --dry   # ssh 없이 (시험용)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import KST, conf, path_conf, save_json, ssh  # noqa: E402

DAYS, LONG = 7, 30
ADMIN = "docker exec plaza_web python -m server.plaza.admin --db /data/plaza.db hosts --days {d}"


def fetch(days: int) -> dict:
    out = json.loads(ssh(ADMIN.format(d=days), timeout=90).strip().splitlines()[-1])
    if not out.get("ok") or out.get("days") != days:
        raise RuntimeError(f"plaza-admin hosts --days {days} 응답이 이상하다: {str(out)[:200]}")
    return out


def judge(week: dict, month: dict, old_hosts: list[str], ours: list[str]) -> dict:
    """옛 이름마다 최근 7일·30일에 부른 에이전트를 우리 쪽·다른 소유주로 가른다"""
    ours_set = set(ours)

    def side(a):
        return "ours" if (a["nickname"] in ours_set or a["agent_id"] in ours_set) else "others"

    def users(rep, host):
        res = {"ours": [], "others": []}
        for a in rep.get("agents", []):
            hit = [h for h in a["hosts"] if h["host"] == host]
            if hit:
                res[side(a)].append({"agent_id": a["agent_id"], "nickname": a["nickname"],
                                     "requests": hit[0]["requests"], "last_at": hit[0]["last_at"]})
        return res

    hosts = {}
    for host in old_hosts:
        w, m = users(week, host), users(month, host)
        hosts[host] = {"others_7d": w["others"], "ours_7d": w["ours"],
                       "others_30d": len(m["others"]), "ours_30d": len(m["ours"]),
                       "closable": not w["others"]}
    return {"days": DAYS, "since": week.get("since"), "old_hosts": hosts,
            "by_host_7d": week.get("by_host", []), "by_host_30d": month.get("by_host", [])}


def main(argv) -> int:
    old_hosts = [h.lower() for h in conf("old_hosts")]
    ours = conf("hosts_ours", conf("conversation_ours", []))
    if "--from" in argv:
        i = argv.index("--from")
        week, month = (json.loads(Path(p).read_text()) for p in argv[i + 1:i + 3])
    else:
        week, month = fetch(DAYS), fetch(LONG)
    now = dt.datetime.now(KST)
    out = {"generated_at": now.isoformat(timespec="seconds"), **judge(week, month, old_hosts, ours)}
    out["summary"] = {h: {"others_7d": len(v["others_7d"]), "ours_7d": len(v["ours_7d"]), "closable": v["closable"]}
                      for h, v in out["old_hosts"].items()}
    if "--dry" not in argv:
        save_json(path_conf("state_dir") / "plaza_hosts" / f"{now:%Y-%m-%d}.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        # 파일을 못 썼다. 읽는 쪽(plaza_ops_status 「옛 이름」 칸)은 가장 새 파일 나이로 이걸 본다
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
