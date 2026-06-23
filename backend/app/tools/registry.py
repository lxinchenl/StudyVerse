"""Discover tool manifests under project ``tools/`` directory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class ToolRegistry:
    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir

    def list_tools(self) -> list[dict[str, Any]]:
        if not self.tools_dir.is_dir():
            return []
        items: list[dict[str, Any]] = []
        for child in sorted(self.tools_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / "tool.json"
            if manifest.is_file():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data.setdefault("id", child.name)
                items.append(data)
        return items

    def get_tool(self, tool_id: str) -> dict[str, Any]:
        manifest_path = self.tools_dir / tool_id / "tool.json"
        if not manifest_path.is_file():
            raise KeyError(f"Tool not found: {tool_id}")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data.setdefault("id", tool_id)
        return data

    def tool_ref(self, tool_id: str) -> str:
        return str(Path("tools") / tool_id / "TOOL.md").replace("\\", "/")


@lru_cache
def get_tool_registry() -> ToolRegistry:
    settings = get_settings()
    return ToolRegistry(settings.tools_dir)
