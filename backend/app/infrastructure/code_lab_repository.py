"""Persist generated code-lab challenge sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.infrastructure.code_lab_script import normalize_challenge_codes


class CodeLabRepository:
    def __init__(self, bundle_dir: Path):
        self.bundle_dir = bundle_dir
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        self._cache: list[dict[str, Any]] | None = None

    def invalidate_cache(self) -> None:
        self._cache = None

    def reload(self) -> None:
        self.invalidate_cache()

    def list_challenges(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        items: list[dict[str, Any]] = []
        if not self.bundle_dir.exists():
            self._cache = items
            return items
        for bundle in sorted(p for p in self.bundle_dir.iterdir() if p.is_dir()):
            items.extend(self._load_bundle(bundle))
        self._cache = items
        return items

    def _load_bundle(self, bundle_dir: Path) -> list[dict[str, Any]]:
        cpath = bundle_dir / "challenges.json"
        mpath = bundle_dir / "meta.json"
        if not cpath.exists():
            return []
        meta = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
        resource_id = str(meta.get("resource_id") or bundle_dir.name)
        title = str(meta.get("title") or "代码实操")
        topic = str(meta.get("topic") or "")
        rows = json.loads(cpath.read_text(encoding="utf-8"))
        out: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            out.append(self._normalize_row(row, i, resource_id, title, topic))
        return out

    @staticmethod
    def _normalize_row(
        row: dict[str, Any],
        index: int,
        resource_id: str,
        resource_title: str,
        resource_topic: str,
    ) -> dict[str, Any]:
        return normalize_challenge_codes(
            {
                "id": str(row.get("id") or f"{resource_id}-c{index + 1}"),
                "resource_id": resource_id,
                "resource_title": resource_title,
                "topic": str(row.get("topic") or resource_topic or resource_title),
                "difficulty": str(row.get("difficulty") or "medium"),
                "question": str(row.get("question") or ""),
                "starter_code": str(row.get("starter_code") or ""),
                "setup_code": str(row.get("setup_code") or ""),
                "solution_code": str(row.get("solution_code") or ""),
                "language": str(row.get("language") or "python"),
                "hint": str(row.get("hint") or ""),
            }
        )

    def get_by_resource(self, resource_id: str) -> list[dict[str, Any]]:
        return [c for c in self.list_challenges() if c["resource_id"] == resource_id]

    def save_generated_set(
        self,
        *,
        resource_id: str,
        user_id: str,
        title: str,
        topic: str,
        challenges: list[dict[str, Any]],
    ) -> Path:
        bundle_dir = self.bundle_dir / resource_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "meta.json").write_text(
            json.dumps(
                {
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "title": title,
                    "topic": topic,
                    "challenge_count": len(challenges),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (bundle_dir / "challenges.json").write_text(
            json.dumps(challenges, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.invalidate_cache()
        return bundle_dir
