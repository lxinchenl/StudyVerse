"""Load skill manifests and prompts from project ``skills/`` directory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def skill_dir(self, skill_id: str) -> Path:
        path = self.skills_dir / skill_id
        if not path.is_dir():
            raise FileNotFoundError(f"Skill not found: {skill_id} ({path})")
        return path

    def load_manifest(self, skill_id: str) -> dict[str, Any]:
        manifest_path = self.skill_dir(skill_id) / "skill.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"skill.json missing for {skill_id}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def load_prompt(self, skill_id: str, prompt_key: str) -> str:
        manifest = self.load_manifest(skill_id)
        prompts = manifest.get("prompts") or {}
        rel = prompts.get(prompt_key)
        if not rel:
            raise KeyError(f"Prompt '{prompt_key}' not in skill {skill_id}")
        path = self.skill_dir(skill_id) / rel
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file missing: {path}")
        return path.read_text(encoding="utf-8").strip()

    def load_doc(self, skill_id: str, doc_key: str) -> str:
        manifest = self.load_manifest(skill_id)
        docs = manifest.get("docs") or {}
        rel = docs.get(doc_key)
        if not rel:
            raise KeyError(f"Doc '{doc_key}' not in skill {skill_id}")
        path = self.skill_dir(skill_id) / rel
        return path.read_text(encoding="utf-8")

    def list_skills(self) -> list[dict[str, Any]]:
        if not self.skills_dir.is_dir():
            return []
        items: list[dict[str, Any]] = []
        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest_path = child / "skill.json"
            if manifest_path.is_file():
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                data.setdefault("id", child.name)
                items.append(data)
        return items

    def skill_ref(self, skill_id: str) -> str:
        """Relative path for trace payloads (e.g. skills/foo/SKILL.md)."""
        manifest = self.load_manifest(skill_id)
        docs = manifest.get("docs") or {}
        rel = docs.get("skill") or "SKILL.md"
        return str(Path("skills") / skill_id / rel).replace("\\", "/")


@lru_cache
def get_skill_loader() -> SkillLoader:
    settings = get_settings()
    return SkillLoader(settings.skills_dir)
