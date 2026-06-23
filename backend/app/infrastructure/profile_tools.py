"""Tools for updating per-user learning profile (user_profile.json)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings

_MAX_LIST_ITEMS = 10
_DEFAULT_COURSE_TITLE = "数据库系统原理"


def _memory():
    from app.core.dependencies import get_memory_service

    return get_memory_service()


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [_clean_str(item) for item in value]
        return "、".join(p for p in parts if p)
    return str(value).strip()


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean_str(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out[:_MAX_LIST_ITEMS]


def _load_user_meta(user_id: str) -> dict[str, str]:
    path = _memory()._user_dir(user_id) / "user.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _load_generated_resources(user_id: str) -> list[dict[str, Any]]:
    path = get_settings().resources_dir / f"{user_id}.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else []
    except json.JSONDecodeError:
        return []


def _infer_course_title(*, profile: dict[str, Any], course_id: str) -> str:
    existing = _clean_str(profile.get("course"))
    if existing:
        return existing
    if course_id:
        from app.core.dependencies import get_course_catalog

        course = get_course_catalog().get_course(course_id)
        if course and course.title:
            return str(course.title)
    return _DEFAULT_COURSE_TITLE


def _topics_from_conversation(messages: list[dict[str, Any]]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for msg in messages:
        content = _clean_str(msg.get("content"))
        if not content:
            continue
        for title in re.findall(r"《([^》]{2,80})》", content):
            if title not in seen:
                seen.add(title)
                topics.append(title)
        if msg.get("role") == "user" and len(content) <= 100:
            snippet = content.replace("\n", " ")[:100]
            if snippet not in seen:
                seen.add(snippet)
                topics.append(snippet)
    return topics[:12]


def _weak_topics_from_attempts(user_id: str) -> list[str]:
    from app.core.dependencies import get_code_lab_repo, get_question_repo

    memory = _memory()
    attempts = memory.get_practice_attempts(user_id)
    q_index = {q["id"]: q for q in get_question_repo().list_questions()}
    lab_index = {c["id"]: c for c in get_code_lab_repo().list_challenges()}
    topics: list[str] = []
    seen: set[str] = set()
    for _resource_id, bucket in attempts.items():
        if not isinstance(bucket, dict):
            continue
        for qid, row in bucket.items():
            if not isinstance(row, dict) or float(row.get("score", 0)) >= 60:
                continue
            item = q_index.get(qid) or lab_index.get(qid)
            if not item:
                continue
            topic = _clean_str(item.get("topic"))
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
    return topics


def gather_profile_context(*, user_id: str, course_id: str = "") -> dict[str, Any]:
    """Aggregate signals from user_profile, conversation, practice, resources for profile sync."""
    memory = _memory()
    profile = memory.get_profile(user_id)
    user_meta = _load_user_meta(user_id)
    conv = memory.get_recent_conversation(user_id, limit=30)
    resources = _load_generated_resources(user_id)
    resource_topics = _clean_list(
        [str(r.get("topic") or "") for r in resources] + [str(r.get("title") or "") for r in resources]
    )
    conv_topics = _topics_from_conversation(conv)
    practice_weak = _weak_topics_from_attempts(user_id)
    frequent_errors = _clean_list(profile.get("frequent_errors") or [])
    inferred_course = _infer_course_title(profile=profile, course_id=course_id)

    recent_topics = _clean_list([*conv_topics, *resource_topics])
    weak_points = _clean_list(
        [
            *(profile.get("weak_points") or []),
            *frequent_errors,
            *practice_weak,
        ]
    )

    suggested = {
        "course": inferred_course,
        "goal": _clean_str(profile.get("goal")) or "系统备考数据库课程核心考点与实操",
        "recent_topics": recent_topics,
        "weak_points": weak_points,
        "list_mode": "replace",
    }

    summary_parts = [
        f"专业={user_meta.get('major') or profile.get('major') or '未知'}",
        f"推断课程={inferred_course}",
        f"近期主题 {len(recent_topics)} 条",
        f"薄弱/常错 {len(weak_points)} 条",
    ]
    return {
        "ok": True,
        "summary": "；".join(summary_parts),
        "current_profile": {
            "course": profile.get("course", ""),
            "goal": profile.get("goal", ""),
            "recent_topics": profile.get("recent_topics", []),
            "weak_points": profile.get("weak_points", []),
            "frequent_errors": frequent_errors,
        },
        "memory_signals": {
            "major": user_meta.get("major") or profile.get("major", ""),
            "recent_user_messages": [
                _clean_str(m.get("content"))[:160]
                for m in conv
                if m.get("role") == "user"
            ][-8:],
            "conversation_topics": conv_topics,
            "generated_resource_topics": resource_topics,
            "practice_weak_topics": practice_weak,
            "frequent_errors": frequent_errors,
        },
        "suggested_updates": suggested,
    }


def format_profile_memory_digest(
    *,
    user_id: str,
    course_id: str = "",
    gather: dict[str, Any] | None = None,
) -> str:
    data = gather or gather_profile_context(user_id=user_id, course_id=course_id)
    signals = data.get("memory_signals") or {}
    suggested = data.get("suggested_updates") or {}
    current = data.get("current_profile") or {}
    lines = [
        "【记忆整合 — 更新画像时必读，勿向用户索要已存在于记忆中的信息】",
        f"- 当前画像：course={current.get('course') or '空'}；goal={current.get('goal') or '空'}",
        f"- 近期主题(已存)：{', '.join(current.get('recent_topics') or []) or '无'}",
        f"- 薄弱点(已存)：{', '.join(current.get('weak_points') or []) or '无'}",
        f"- 练习常错(frequent_errors)：{', '.join(current.get('frequent_errors') or []) or '无'}",
        f"- 近期用户消息：{' | '.join(signals.get('recent_user_messages') or []) or '无'}",
        f"- 对话/交付主题：{', '.join(signals.get('conversation_topics') or []) or '无'}",
        f"- 已生成资源主题：{', '.join(signals.get('generated_resource_topics') or []) or '无'}",
        f"- 练习低分知识点：{', '.join(signals.get('practice_weak_topics') or []) or '无'}",
        "【建议写入 user-profile-update 的 input（可微调，禁止空口索要用户重填）】",
        json.dumps(suggested, ensure_ascii=False),
    ]
    return "\n".join(lines)


def update_user_profile(
    *,
    user_id: str,
    course: str | None = None,
    goal: str | None = None,
    recent_topics: list[str] | None = None,
    weak_points: list[str] | None = None,
    list_mode: str = "merge",
) -> dict[str, Any]:
    """Update course / goal / recent_topics / weak_points in data/users/{id}/user_profile.json."""
    memory = _memory()
    profile = memory.get_profile(user_id)
    updated_fields: list[str] = []
    replace_lists = _clean_str(list_mode).lower() == "replace"

    if course is not None:
        profile["course"] = _clean_str(course)
        updated_fields.append("course")

    if goal is not None:
        profile["goal"] = _clean_str(goal)
        updated_fields.append("goal")

    if recent_topics is not None:
        incoming = _clean_list(recent_topics)
        if replace_lists:
            profile["recent_topics"] = incoming
        else:
            merged = _clean_list([*(profile.get("recent_topics") or []), *incoming])
            profile["recent_topics"] = merged
        updated_fields.append("recent_topics")

    if weak_points is not None:
        incoming = _clean_list(weak_points)
        if replace_lists:
            profile["weak_points"] = incoming
        else:
            merged = _clean_list([*(profile.get("weak_points") or []), *incoming])
            profile["weak_points"] = merged
        updated_fields.append("weak_points")

    if not updated_fields:
        return {
            "ok": False,
            "summary": "未提供可更新字段（course / goal / recent_topics / weak_points）",
            "profile": {
                "course": profile.get("course", ""),
                "goal": profile.get("goal", ""),
                "recent_topics": profile.get("recent_topics", []),
                "weak_points": profile.get("weak_points", []),
            },
        }

    memory.save_profile(user_id, profile)
    summary = f"已更新用户画像：{', '.join(updated_fields)}"
    return {
        "ok": True,
        "summary": summary,
        "updated_fields": updated_fields,
        "profile": {
            "course": profile.get("course", ""),
            "goal": profile.get("goal", ""),
            "recent_topics": profile.get("recent_topics", []),
            "weak_points": profile.get("weak_points", []),
        },
    }
