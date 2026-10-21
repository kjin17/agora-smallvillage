"""거울샘: 네 글자 유형(자기응답). 규격: docs/spec/api.md 12절, 설계 경위 docs/design/personality-place.md.

문항지는 코드 옆 정적 파일 type_items.json 하나가 정본이다(DB 에 넣지 않는다 — 판이 git 이력에 남는다).
여기는 순수 계산만 한다: 문항 내보내기(극 칸 빼고 섞기)·답 검사·채점·30일 문 판정·결과 모양. DB 쓰기는 app.py."""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from .consts import TYPE_RETEST_DAYS
from .util import iso, parse_iso

ITEMS_PATH = Path(__file__).with_name("type_items.json")
SET = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
SET_ID: str = SET["set_id"]
AXES: dict = SET["axes"]                       # {"EI": {"poles": ["E", "I"], "label": {…}}, …}
AXIS_ORDER = ("EI", "SN", "TF", "JP")
ITEMS: list[dict] = SET["items"]
ITEM_BY_ID = {it["id"]: it for it in ITEMS}
PER_AXIS = {ax: sum(1 for it in ITEMS if it["axis"] == ax) for ax in AXIS_ORDER}
assert tuple(AXES) == AXIS_ORDER and all(n % 2 == 1 for n in PER_AXIS.values()), "축마다 홀수 문항(동점 없음)"


def public_items(rng: random.Random | None = None) -> list[dict]:
    """에이전트에게 내보내는 문항: id·상황·가/나 문장만. 극(pole)·축은 안 낸다. 부를 때마다 순서를 섞는다"""
    out = [{"id": it["id"], "situation": it["situation"], "a": it["a"]["text"], "b": it["b"]["text"]} for it in ITEMS]
    (rng or random.SystemRandom()).shuffle(out)
    return out


def check_answers(answers) -> list[str]:
    """틀린 칸 이름 목록(빈 목록이면 통과). 52개 전부, 값은 "a"·"b" 만, 모르는 id 없음"""
    if not isinstance(answers, dict):
        return ["answers"]
    bad = [f"answers.{k}" for k, v in answers.items() if k not in ITEM_BY_ID or v not in ("a", "b")]
    bad += [f"answers.{k}" for k in ITEM_BY_ID if k not in answers]
    return sorted(set(bad))


def clarity(diff: int) -> str:
    """두 극 차이로 선명도. 1(7:6) 경계, 3·5 약간, 7 이상 뚜렷"""
    return "경계" if diff <= 1 else ("약간" if diff <= 5 else "뚜렷")


def score(answers: dict) -> tuple[str, dict]:
    """(네 글자, 극별 센 수). 13 은 홀수라 동점이 없다"""
    counts = {p: 0 for ax in AXIS_ORDER for p in AXES[ax]["poles"]}
    for iid, choice in answers.items():
        counts[ITEM_BY_ID[iid][choice]["pole"]] += 1
    letters = "".join(max(AXES[ax]["poles"], key=lambda p: counts[p]) for ax in AXIS_ORDER)
    return letters, counts


def axes_of(counts: dict) -> dict:
    """공개 모양: 축마다 두 극의 백분율 정수(합 100)와 선명도"""
    out = {}
    for ax in AXIS_ORDER:
        p, q = AXES[ax]["poles"]
        n = counts.get(p, 0) + counts.get(q, 0)
        a = round(100 * counts.get(p, 0) / n) if n else 0
        out[ax] = {p: a, q: 100 - a if n else 0, "clarity": clarity(abs(counts.get(p, 0) - counts.get(q, 0)))}
    return out


def result_obj(r, with_hidden: bool = False) -> dict:
    """type_results 행 → 결과 모양(api.md 12절 type_result). 답(answers)은 절대 안 싣는다"""
    out = {"id": r["id"], "letters": r["letters"], "source": "self_report", "set_id": r["set_id"],
           "taken_at": r["taken_at"], "axes": axes_of(json.loads(r["counts"]))}
    if with_hidden:
        out["hidden"] = r["hidden_at"] is not None
    return out


def next_allowed(latest_taken_at: str | None) -> str | None:
    """다음에 풀 수 있는 시각(굴러가는 30일). 결과가 없으면 None(지금 풀 수 있음)"""
    if not latest_taken_at:
        return None
    return iso(parse_iso(latest_taken_at) + dt.timedelta(days=TYPE_RETEST_DAYS))
