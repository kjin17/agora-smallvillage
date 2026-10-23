#!/usr/bin/env python3
"""plaza_hosts_weekly.py 판정과 plaza_ops_status.py 「옛 이름」 칸 검증 — 손으로 정한 가짜 hosts 응답으로 대조한다.

옛 이름 old.example.test, 새 이름 new.example.test, 우리 쪽 묶음 ["우리1", "ag_us2"](닉네임·id 섞어서):
  7일   우리1(옛·새)  ag_us2 "우리2"(옛)  남1(옛)  남2(새만)
  30일  위 + 남3(옛, 7일 밖)
기대: 옛 이름 others_7d = [남1], ours_7d = 2, others_30d = 2, closable = false.
대조군(자 검사): 남1 을 뺀 사본은 closable = true, 우리 쪽 묶음을 비운 사본은 우리 둘이 다른 소유주로 넘어가 closable = false.
옛 이름에 아무도 없는 이름(gone.example.test)은 closable = true(0명도 0명이다).
상태 칸: 가장 새 파일이 closable 이면 alert(「차단 가능」), 아니면 ok, 200시간 넘으면 unknown, 파일이 없으면 unknown.
main --from … --dry 를 임시 설정으로 돌려 파일을 안 쓰는지도 본다.

    python3 ops/plaza_hosts_weekly_check.py      # 전부 맞으면 exit 0
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plaza_hosts_weekly as W  # noqa: E402

OLD, NEW, GONE = "old.example.test", "new.example.test", "gone.example.test"
OURS = ["우리1", "ag_us2"]


def a(aid, nick, *hosts):
    return {"agent_id": aid, "nickname": nick,
            "hosts": [{"host": h, "requests": 3, "days": 1, "first_at": "2026-10-20T10:00:00+09:00",
                       "last_at": "2026-10-22T10:00:00+09:00"} for h in hosts]}


WEEK = {"ok": True, "since": "2026-10-17", "days": 7, "by_host": [],
        "agents": [a("ag_us1", "우리1", OLD, NEW), a("ag_us2", "우리2", OLD), a("ag_o1", "남1", OLD), a("ag_o2", "남2", NEW)]}
MONTH = {**copy.deepcopy(WEEK), "days": 30}
MONTH["agents"].append(a("ag_o3", "남3", OLD))


def main() -> int:
    bad = []

    def check(name, ok, detail=""):
        print(("  [PASS] " if ok else "  [FAIL] ") + name + (f" — {detail}" if detail else ""))
        if not ok:
            bad.append(name)

    r = W.judge(WEEK, MONTH, [OLD, GONE], OURS)["old_hosts"]
    o = r[OLD]
    check("옛 이름 others_7d = [남1]", [x["nickname"] for x in o["others_7d"]] == ["남1"], str(o["others_7d"]))
    check("옛 이름 ours_7d 둘(닉네임·id 로 묶음)", sorted(x["nickname"] for x in o["ours_7d"]) == ["우리1", "우리2"])
    check("옛 이름 others_30d = 2 (7일 밖 남3 포함)", o["others_30d"] == 2 and o["ours_30d"] == 2, str(o["others_30d"]))
    check("옛 이름 closable = false", o["closable"] is False)
    check("새 이름에만 오는 남2 는 옛 이름에 안 셈", "남2" not in json.dumps(o, ensure_ascii=False))
    check("아무도 없는 옛 이름은 closable = true", r[GONE]["closable"] is True and not r[GONE]["ours_7d"])
    w2 = copy.deepcopy(WEEK)
    w2["agents"] = [x for x in w2["agents"] if x["nickname"] != "남1"]
    check("자 검사: 남1 을 빼면 closable = true", W.judge(w2, MONTH, [OLD], OURS)["old_hosts"][OLD]["closable"] is True)
    o3 = W.judge(WEEK, MONTH, [OLD], [])["old_hosts"][OLD]
    check("자 검사: 우리 쪽 묶음이 비면 우리 둘도 다른 소유주(3명)", len(o3["others_7d"]) == 3 and o3["closable"] is False)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cfg = d / "ops.json"
        cfg.write_text(json.dumps({"state_dir": str(d / "state"), "old_hosts": [OLD.upper()], "conversation_ours": OURS,
                                   "domain": "plaza.example.test"}))
        (d / "w.json").write_text(json.dumps(WEEK))
        (d / "m.json").write_text(json.dumps(MONTH))
        env = dict(os.environ, PLAZA_OPS_CONFIG=str(cfg))
        p = subprocess.run([sys.executable, str(HERE / "plaza_hosts_weekly.py"), "--from", str(d / "w.json"),
                            str(d / "m.json"), "--dry"], capture_output=True, text=True, env=env)
        out = json.loads(p.stdout) if p.returncode == 0 else {}
        check("main --from --dry: rc 0·요약(대문자 설정도 소문자로)·파일 안 씀",
              p.returncode == 0 and out.get("summary", {}).get(OLD) == {"others_7d": 1, "ours_7d": 2, "closable": False}
              and not (d / "state").exists(), (p.stderr or str(out.get("summary")))[:200])

        # plaza_ops_status 「옛 이름」 칸 (모듈은 임시 설정으로 읽는다)
        os.environ["PLAZA_OPS_CONFIG"] = str(cfg)
        import plaza_ops_status as S
        S.STATE_DIR = d / "st"
        check("상태 칸: 파일 없으면 unknown", S.old_hosts()["state"] == "unknown")
        hd = S.STATE_DIR / "plaza_hosts"
        hd.mkdir(parents=True)
        now = dt.datetime.now(W.KST)

        def put(name, closable, age_h):
            (hd / name).write_text(json.dumps({"generated_at": (now - dt.timedelta(hours=age_h)).isoformat(timespec="seconds"),
                                               "days": 7, "summary": {OLD: {"others_7d": 0 if closable else 1, "ours_7d": 2,
                                                                            "closable": closable}}}))
        put("2026-10-01.json", True, 300)
        it = S.old_hosts()
        check("상태 칸: 200시간 넘은 파일은 unknown", it["state"] == "unknown", it.get("reason", ""))
        put("2026-10-02.json", False, 1)
        it = S.old_hosts()
        check("상태 칸: 다른 소유주가 남았으면 ok", it["state"] == "ok", str(it.get("value")))
        put("2026-10-03.json", True, 1)
        it = S.old_hosts()
        check("상태 칸: closable 이면 alert 「차단 가능」", it["state"] == "alert" and "차단 가능" in (it.get("reason") or "")
              and OLD in it["reason"], it.get("reason", ""))
    print(f"\n판정 실패 {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
