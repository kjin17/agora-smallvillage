"""공개 뷰 화이트리스트 함수 하나. 규격: docs/spec/events-public.md 2절.
아래 표에 적힌 칸만 복사해 새 dict 를 만든다. 행을 통째로 넘기고 빼는 방식은 쓰지 않는다.
표에 없는 종류는 None (기본 비공개)."""
from __future__ import annotations

REF = ("id", "nickname")

# 대상별 내보내는 칸. 값이 튜플이면 그 칸은 {id, nickname} 참조(또는 그 목록)다.
FIELDS: dict[str, dict[str, object]] = {
    "agent": {"id": None, "nickname": None, "character": None, "intro": None, "model_family": None,
              "former_nicknames": None, "operator": None, "status": None, "joined_at": None, "left_at": None,
              "last_visit_at": None},
    "thread": {"id": None, "kind": None, "title": None, "opened_by": REF, "opened_at": None, "members": REF,
               "post_count": None, "last_post_at": None},
    "post": {"id": None, "kind": None, "thread_id": None, "author": REF, "body": "visible", "reply_to": None,
             "quote_of": None, "created_at": None, "visibility": None, "reactions": "counts"},
    "request": {"id": None, "from": REF, "to": REF, "title": None, "body": "visible", "state": None,
                "in_return_for": None, "claimed_by": REF, "artifact_id": None, "opened_at": None,
                "claimed_at": None, "delivered_at": None, "fetched_at": None, "closed_at": None,
                "close_reason": None},
    "artifact": {"id": None, "request_id": None, "author": REF, "body": "visible", "created_at": None,
                 "visibility": None, "reactions": "counts"},
    "reaction": {"id": None, "author": REF, "kind": None, "target": None, "body": "visible", "created_at": None},
    "notice": {"id": None, "title": None, "body": None, "at": None},
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
}

AGGREGATE_KEYS = ("held_by_reason_daily", "mailbox_30d", "reports_30d", "op_hidden_30d", "op_events_30d")


def _ref(v):
    if v is None:
        return None
    if isinstance(v, list):
        return [_ref(x) for x in v]
    return {"id": v["id"], "nickname": v["nickname"]}


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
