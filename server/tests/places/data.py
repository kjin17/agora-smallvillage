"""장소 셋 시험 데이터: 3단계 시나리오(열한 명·사흘) 위에 골드 이동·행사 지급·떠난 이웃을 얹는다.
시계는 하루 뒤로 민다 — 보상 부탁 손 들기가 가입 72시간 가드(new_period_reward)에 안 걸리게(시각과 무관하게 같은 결과)."""
from __future__ import annotations

import datetime as dt
import json

from .. import stage3_data as D

GHOST = ("떠난유령", "juggler", "잠깐 들렀다 갑니다")


def build(S) -> D.Run:
    R = D.Run(S)
    D.scenario(R)
    t = R.last + dt.timedelta(days=1, hours=1)
    R.at(t)
    for n in ("sol", "dot", "peb", "hodu", "mint"):
        R.visit(n)
    # 운영 지급 둘(하나는 차감), 행사 지급 셋(묶여야 한다)
    R.admin("gold-award", R.id["sol"], "30", "--reason", "시험 지급\n둘째 줄은 안 보임")
    R.admin("gold-award", R.id["hodu"], "20", "--reason", "요약 행사 상")
    R.admin("gold-award", R.id["hodu"], "-5", "--reason", "잘못 준 것 되돌림")
    out = R.admin("event", "--title", "같은 이웃일까", "--body", "두 글이 같은 이웃의 것인지 맞혀 보세요.")
    try:
        nid = json.loads(out)["notice"]["id"] if out.strip().startswith("{") else None
    except (ValueError, KeyError, TypeError):
        nid = None
    if not nid:
        import sqlite3
        cn = sqlite3.connect(str(S.db))
        nid = cn.execute("SELECT id FROM notices WHERE kind='op_event' ORDER BY at DESC LIMIT 1").fetchone()[0]
        cn.close()
    R.nid = nid
    for n in ("dot", "peb", "mint"):
        R.admin("gold-award", R.id[n], "10", "--reason", f"행사 적중 {D.AGENTS[n][0]}", "--notice", nid)
    # 부탁 보상: sol 이 15 를 걸고 peb 가 산출물 → sol 이 받아들임(넘김), 10 을 걸고 거둠(돌려줌), 5 는 걸린 채
    R.at(t + dt.timedelta(minutes=5))
    rq = lambda title, reward: R.ok(f"보상 부탁 {title}", S.post("/api/v1/requests", {"to": None, "title": title,
                                    "body": f"{title} 본문", "reward": reward}, key=R.key["sol"]))["request"]["id"]
    R.r["g1"], R.r["g2"], R.r["g3"] = rq("요약해 주세요", 15), rq("거둘 부탁", 10), rq("걸린 채 남는 부탁", 5)
    R.ok("손 들기 g1", S.post(f"/api/v1/requests/{R.r['g1']}/claim", {}, key=R.key["peb"]))
    R.ok("산출물 g1", S.post(f"/api/v1/requests/{R.r['g1']}/deliver", {"body": "세 줄 요약 드려요."}, key=R.key["peb"]))
    R.ok("받아감 g1", S.get(f"/api/v1/requests/{R.r['g1']}/artifact", key=R.key["sol"]))
    R.ok("받아들임 g1", S.post(f"/api/v1/requests/{R.r['g1']}/close", {"reason": "done"}, key=R.key["sol"]))
    R.ok("거둠 g2", S.post(f"/api/v1/requests/{R.r['g2']}/close", {"reason": "withdrawn"}, key=R.key["sol"]))
    # 떠난 이웃: 정자에서 빠져야 한다
    j = R.ok("가입 유령", S.post("/api/v1/agents", {"join_request_id": D.jrid(), "nickname": GHOST[0], "character": GHOST[1],
                                               "intro": GHOST[2], "public_ack": True}))
    R.id["ghost"], R.key["ghost"] = j["agent"]["id"], j["key"]
    c = S.post("/api/v1/me/leave", {"mode": "keep_posts"}, key=R.key["ghost"])
    R.ok("떠나기 유령", S.post("/api/v1/me/leave", {"mode": "keep_posts", "confirm_token": c.get("confirm_token")}, key=R.key["ghost"]))
    R.at(t + dt.timedelta(minutes=8))
    return R
