"""Tools for updating per-user assistant persona memory (me.json)."""

from __future__ import annotations

import json
from typing import Any


def _memory():
    from app.core.dependencies import get_memory_service

    return get_memory_service()


def _load_me(user_id: str) -> dict[str, Any]:
    mem = _memory()
    path = mem._user_dir(user_id) / "me.json"
    if not path.exists():
        return mem.get_me(user_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else mem.get_me(user_id)
    except json.JSONDecodeError:
        return mem.get_me(user_id)


def _save_me(user_id: str, data: dict[str, Any]) -> None:
    path = _memory()._user_dir(user_id) / "me.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_user_me(
    *,
    user_id: str,
    action: str = "add",
    updates: dict[str, Any] | None = None,
    remove_keys: list[str] | None = None,
    rewrite: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update assistant persona memory file (data/users/{id}/me.json).

    action:
      - add/merge: merge ``updates`` into current me.json
      - delete/remove: delete keys in ``remove_keys``
      - rewrite/replace: overwrite me.json with ``rewrite`` object
    """
    current = _load_me(user_id)
    mode = (action or "add").strip().lower()
    changed: list[str] = []

    if mode in {"add", "merge"}:
        payload = updates if isinstance(updates, dict) else {}
        next_me = dict(current)
        for key, value in payload.items():
            k = str(key).strip()
            if not k:
                continue
            next_me[k] = value
            changed.append(k)
        if not changed:
            return {"ok": False, "summary": "未提供可写入字段（updates）", "me": current}
        _save_me(user_id, next_me)
        return {
            "ok": True,
            "summary": f"已更新 me：{', '.join(changed)}",
            "updated_fields": changed,
            "me": next_me,
        }

    if mode in {"delete", "remove"}:
        keys = [str(k).strip() for k in (remove_keys or []) if str(k).strip()]
        if not keys:
            return {"ok": False, "summary": "未提供可删除字段（remove_keys）", "me": current}
        next_me = dict(current)
        for key in keys:
            if key in next_me:
                next_me.pop(key, None)
                changed.append(key)
        _save_me(user_id, next_me)
        return {
            "ok": True,
            "summary": f"已删除 me 字段：{', '.join(changed) if changed else '无匹配字段'}",
            "updated_fields": changed,
            "me": next_me,
        }

    if mode in {"rewrite", "replace"}:
        if not isinstance(rewrite, dict):
            return {"ok": False, "summary": "rewrite 必须是对象", "me": current}
        next_me = {str(k).strip(): v for k, v in rewrite.items() if str(k).strip()}
        _save_me(user_id, next_me)
        return {
            "ok": True,
            "summary": "已重写 me",
            "updated_fields": list(next_me.keys()),
            "me": next_me,
        }

    return {
        "ok": False,
        "summary": "未知 action，支持 add/merge/delete/remove/rewrite/replace",
        "me": current,
    }

