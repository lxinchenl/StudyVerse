"""Persist user learning courses (workflow output)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _path_file(users_dir: Path, user_id: str) -> Path:
    user_dir = users_dir / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "learning_paths.json"


def load_courses(users_dir: Path, user_id: str) -> list[dict[str, Any]]:
    path = _path_file(users_dir, user_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        return list(data.get("courses") or [])
    if isinstance(data, list):
        return data
    return []


def save_courses(users_dir: Path, user_id: str, courses: list[dict[str, Any]]) -> None:
    path = _path_file(users_dir, user_id)
    path.write_text(
        json.dumps({"courses": courses}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_course(users_dir: Path, user_id: str, course: dict[str, Any]) -> dict[str, Any]:
    courses = load_courses(users_dir, user_id)
    courses.insert(0, course)
    save_courses(users_dir, user_id, courses)
    return course


def get_course(users_dir: Path, user_id: str, course_id: str) -> dict[str, Any] | None:
    for course in load_courses(users_dir, user_id):
        if course.get("id") == course_id:
            return course
    return None


def update_course(users_dir: Path, user_id: str, course_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    courses = load_courses(users_dir, user_id)
    for idx, course in enumerate(courses):
        if course.get("id") != course_id:
            continue
        merged = {**course, **patch}
        courses[idx] = merged
        save_courses(users_dir, user_id, courses)
        return merged
    return None


def new_course_id() -> str:
    return f"lc-{uuid4().hex[:10]}"
