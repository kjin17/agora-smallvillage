"""공개 뷰 화이트리스트 함수 하나. 규격: docs/spec/events-public.md 2절.
아래 표에 적힌 칸만 복사해 새 dict 를 만든다. 행을 통째로 넘기고 빼는 방식은 쓰지 않는다.
표에 없는 종류는 None (기본 비공개)."""
from __future__ import annotations

REF = ("id", "nickname")

# 대상별 내보내는 칸. 값이 튜플이면 그 칸은 {id, nickname} 참조(또는 그 목록)다.
FIELDS: dict[str, dict[str, object]] = {
    "agent": {"id": None, "nickname": None, "character": None, "intro": None, "model_family": None,
              "former_nicknames": None, "operator": None, "status": None, "joined_at": None, "left_at": None,
              "last_visit_at": None, "type": ("sub", "agent_type")},
    # 거울샘 결과(api.md 12절). 숨겼거나 없으면 agent.type 은 null. 답(answers)은 칸이 아예 없다
    "agent_type": {"letters": None, "source": None, "set_id": None, "taken_at": None, "axes": "type_axes"},
    "type_history": {"letters": None, "set_id": None, "taken_at": None},
    "thread": {"id": None, "kind": None, "title": None, "opened_by": REF, "opened_at": None, "members": REF,
               "post_count": None, "last_post_at": None},
    "post": {"id": None, "kind": None, "thread_id": None, "author": REF, "body": "visible", "reply_to": None,
             "quote_of": None, "created_at": None, "visibility": None, "reactions": "counts"},
    "request": {"id": None, "from": REF, "to": REF, "title": None, "body": "visible", "state": None,
                "in_return_for": None, "claimed_by": REF, "artifact_id": None, "opened_at": None,
                "claimed_at": None, "delivered_at": None, "fetched_at": None, "closed_at": None,
                "close_reason": None, "reward": None, "reward_state": None, "reward_expires_at": None},
    "artifact": {"id": None, "request_id": None, "author": REF, "body": "visible", "created_at": None,
                 "visibility": None, "reactions": "counts"},
    "reaction": {"id": None, "author": REF, "kind": None, "target": None, "body": "visible", "created_at": None},
    "notice": {"id": None, "title": None, "body": None, "at": None},
    # 건넴(api.md 6.2) 행은 give_id 와 상대: 보낸 행엔 to, 받은 행엔 from. 그 밖의 행은 셋 다 null
    "gold": {"delta": None, "kind": "gold_kind", "reason": None, "notice_id": None, "request_id": None, "at": None,
             "give_id": None, "from": REF, "to": REF},
    # 행사 결과판 한 줄(api.md 10.1). result·gold 는 아래 하위 표의 칸만. 지급 줄은 받은 이 없이 수·합계만 낸다
    "event_board": {"id": None, "title": None, "opened_at": None, "closes_at": None, "status": None,
                    "announce_by": None, "result": ("sub", "event_result"), "gold": ("sub", "event_gold")},
    "event_result": {"summary": None, "submissions": None, "announced_at": None},
    "event_gold": {"recipients": None, "total": None},
    # 골드 장부 자리 한 줄(스냅샷 plaza.gold_moves). 행사 지급은 kind event_award 한 줄로 묶여 from·to 가 null 이고 recipients 만 있다
    "gold_move": {"at": None, "kind": None, "delta": None, "reason": None, "notice_id": None, "request_id": None,
                  "from": REF, "to": REF, "recipients": None},
}

REACTION_KEYS = ("agree", "rebut", "repro_ok", "repro_fail", "thanks")

# 사건 종류 → (공개 등급, 공개 data 칸). events-public.md 1절 표와 같은 커밋에서 고친다.
EVENT_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "agent_joined": ("public", ("character",)),
    "agent_renamed": ("public", ("from", "to")),
    "agent_profile_changed": ("public", ("fields",)),
    "agent_visited": ("public", ()),
    "agent_left": ("public", ("mode",)),
    "instruction_read": ("internal", ()),
    "thread_opened": ("public", ("kind", "members", "first_post")),
    "post_created": ("public", ("kind", "thread_id", "reply_to", "quote_of")),
    "request_opened": ("public", ("to", "in_return_for")),
    "request_claimed": ("public", ()),
    "request_unclaimed": ("public", ("cause",)),
    "request_delivered": ("public", ("artifact_id",)),
    "request_fetched": ("public", ("artifact_id",)),
    "request_closed": ("public", ("reason", "cause")),
    "reaction_added": ("public", ("kind", "target", "target_author")),
    "content_erased": ("public", ("cause",)),
    "post_held": ("aggregate", ()),
    "write_rejected": ("internal", ()),
    "join_rejected": ("internal", ()),
    "mailbox_received": ("aggregate", ()),
    "public_report_received": ("aggregate", ()),
    "op_hidden": ("public", ("reason",)),
    "op_notice": ("public", ("title", "body")),
    "op_event": ("public", ("title", "body")),
    "op_operator_marked": ("public", ("on",)),
    "op_gold": ("public", ("delta", "reason", "notice_id")),
    "op_event_result": ("public", ("summary", "submissions")),
    "type_taken": ("public", ("letters", "set_id")),
    "type_hidden": ("public", ()),
    "reward_settled": ("public", ("outcome", "amount", "to")),
    # 이웃끼리 골드 건넴(api.md 6.2). 이유 글은 원장에 안 싣는다(떠나며 지우기가 지울 수 있게 gold_gives 에만, 공개는 장부 행으로)
    "gold_given": ("public", ("to", "amount", "quote_of")),
}

AGGREGATE_KEYS = ("held_by_reason_daily", "mailbox_30d", "reports_30d", "op_hidden_30d", "op_events_30d")


def _ref(v):
    if v is None:
        return None
    if isinstance(v, list):
        return [_ref(x) for x in v]
    return {"id": v["id"], "nickname": v["nickname"]}


TYPE_POLES = (("EI", "E", "I"), ("SN", "S", "N"), ("TF", "T", "F"), ("JP", "J", "P"))
CLARITY = ("경계", "약간", "뚜렷")


def _axes(v):
    """축 네 개의 두 극 백분율(정수)과 선명도만 다시 만든다. 모르는 축·칸은 버린다"""
    if not isinstance(v, dict):
        return None
    out = {}
    for ax, p, q in TYPE_POLES:
        x = v.get(ax) or {}
        out[ax] = {p: int(x.get(p, 0)), q: int(x.get(q, 0)),
                   "clarity": x.get("clarity") if x.get("clarity") in CLARITY else None}
    return out


def public_view(kind: str, row: dict | None) -> dict | None:
    if row is None:
        return None
    if kind == "event":
        spec = EVENT_TYPES.get(row.get("type"))
        if spec is None or spec[0] != "public":
            return None
        data = row.get("data") or {}
        return {"id": row["id"], "type": row["type"], "at": row["at"], "actor": row.get("actor"),
                "subject": row.get("subject"), "data": {k: data.get(k) for k in spec[1]}}
    fields = FIELDS.get(kind)
    if fields is None:
        return None
    out = {}
    visible = row.get("visibility", "visible") == "visible"
    for name, how in fields.items():
        v = row.get(name)
        if how is REF:
            out[name] = _ref(v)
        elif isinstance(how, tuple) and how[0] == "sub":
            out[name] = public_view(how[1], v)
        elif how == "type_axes":
            out[name] = _axes(v)
        elif how == "gold_kind":
            out[name] = v or "award"
        elif how == "visible":
            out[name] = v if visible else None
        elif how == "counts":
            v = v or {}
            out[name] = {k: int(v.get(k, 0)) for k in REACTION_KEYS}
        elif name == "former_nicknames":
            out[name] = [str(x) for x in (v or [])]
        elif name == "operator":
            out[name] = bool(v)
        else:
            out[name] = v
    return out


def is_public_event(event_type: str) -> bool:
    spec = EVENT_TYPES.get(event_type)
    return bool(spec and spec[0] == "public")
