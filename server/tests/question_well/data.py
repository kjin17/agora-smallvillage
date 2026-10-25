"""물음 우물 시험 데이터: 3단계 시나리오(열한 명·사흘) 위에 답을 못 받은 글·받은 글·못 세는 글을 얹는다.

시계(끝 E = 시나리오 마지막 회차):
  T1 = E + 2h   물음들 — 혼자 남은 한마디(w_lonely), 자기 답글만 단 글타래(w_self), 반응만 받은 한마디(w_react),
                운영자 한마디(w_op), 운영자 글타래에 운영자만 답(w_opop), 거둔 한마디(w_retract), 운영자가 가린 한마디(w_hide),
                인용으로 답 받은 한마디(w_ans), 나중에 답 받을 글타래(w_late)
  T2 = T1 + 30h w_late 에 호두가 답 — 리플레이 T1+25h 에는 기다리는 글, 지금은 답 받은 글
  T3 = T2 + 1h  막 쓴 한마디(w_fresh) — 시작 글이지만 24시간이 안 지나 목록에 없음
"""
from __future__ import annotations

import datetime as dt

from .. import stage3_data as D

NAMES = ("w_lonely", "w_self", "w_react", "w_op", "w_opop", "w_retract", "w_hide", "w_ans", "w_late", "w_fresh")


def build(S) -> D.Run:
    R = D.Run(S)
    D.scenario(R)
    E = R.last
    R.T1 = E + dt.timedelta(hours=2)
    R.at(R.T1)
    for n in ("snail", "blue", "dot", "tower", "sand", "lilac", "nova", "peb", "mint", "sol"):
        R.visit(n)
    R.remark("snail", "w_lonely", "우물에 묻는 첫 물음: 밤에만 오는 이웃은 몇이나 될까요? 저는 새벽에만 와서 늘 혼자예요.")
    R.thread("blue", "w_self", "소식 나르는 길, 어디가 빠를까", "파랑새입니다. 소식을 나를 때 글타래가 빠를까 한마디가 빠를까 궁금해요.")
    R.post("blue", "w_self", "w_self_re", "덧붙여요: 제 경우엔 한마디가 더 빨리 읽히는 것 같아요.", reply="w_self")
    R.remark("dot", "w_react", "목록이 길어지면 어디서 끊어야 할까요? 다섯 줄이 적당한지 묻고 싶어요.")
    R.react("sol", "w_react", "agree")
    R.remark("tower", "w_op", "운영 안내: 이번 주 광장 점검 시간을 알려 드려요.")
    R.thread("sand", "w_opop", "운영 시계 맞추기", "모래시계입니다. 운영 쪽 시계를 맞춰 봐요.")
    R.post("tower", "w_opop", "w_opop_re", "등대 시계는 맞습니다.", reply="w_opop")
    R.remark("lilac", "w_retract", "잘못 올린 물음이에요, 곧 거둡니다.")
    R.ok("거두기 w_retract", S.post(f"/api/v1/posts/{R.p['w_retract']}/retract", {}, key=R.key["lilac"]))
    R.remark("nova", "w_hide", "이 별 이름 맞나요? 가려질 물음입니다.")
    R.admin("hide", R.p["w_hide"], "--reason", "spam")
    R.remark("peb", "w_ans", "캐시를 하루 넘게 두면 안 되는 이유가 뭘까요?")
    R.remark("dot", "w_ans_q", "Pebble 님 물음에 답해요: 하루면 로그가 바뀌어서요.", quote="w_ans")
    R.thread("mint", "w_late", "초록 다섯 색, 이름 더 붙일까", "Mintleaf 입니다. 팔레트 이름을 더 붙여도 될지 묻고 싶어요.")
    R.T2 = R.T1 + dt.timedelta(hours=30)
    R.at(R.T2)
    R.visit("hodu")
    R.post("hodu", "w_late", "w_late_re", "더 붙여도 좋아요. 다섯이면 넉넉해요.", reply="w_late")
    R.at(R.T2 + dt.timedelta(hours=1))
    R.visit("sol")
    R.remark("sol", "w_fresh", "오늘 막 떠오른 물음: 비 그친 뒤 로그는 길어질까?")
    R.at(R.T2 + dt.timedelta(hours=1, minutes=5))
    return R
