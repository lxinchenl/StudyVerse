from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.infrastructure.note_process import (
    apply_vision_to_process,
    extract_material_process,
)
from app.infrastructure.note_structure import analyze_process_structure
from app.llm.vision import DoubaoVisionClient


def note_material_extract(
    *,
    course_id: str,
    material_id: str | None = None,
    chapter_key: str | None = None,
) -> dict[str, Any]:
    work_root = get_settings().resources_dir / "note" / "_work"
    return extract_material_process(
        course_id=course_id,
        material_id=material_id,
        chapter_key=chapter_key,
        work_root=work_root,
    )


def note_structure_analyze(*, pages: list[dict[str, Any]]) -> dict[str, Any]:
    return analyze_process_structure(pages)


async def doubao_vision_analyze(
    *,
    image_path: str,
    page_text: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    client = DoubaoVisionClient.from_settings(user_id or None)
    if client is None:
        return {
            "ok": False,
            "error": "未配置豆包 API Key（请在设置页填写）",
            "analysis": "",
        }
    analysis = await client.analyze_image(Path(image_path), page_text=page_text)
    return {"ok": True, "analysis": analysis, "image_path": image_path}
