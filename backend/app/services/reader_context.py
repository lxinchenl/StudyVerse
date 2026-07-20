"""Preload course reader context for in-document Agent questions."""

from __future__ import annotations

from typing import Any

from app.services.material_context import apply_document_read


def preload_reader_context(context: dict[str, Any]) -> dict[str, Any]:
    """Attach reader metadata and preload the active document into material context."""
    document_id = str(context.get("document_id") or "").strip() or None
    course_id = str(context.get("course_id") or "").strip() or None
    selected_text = str(context.get("selected_text") or "").strip()

    reader_context: dict[str, Any] = {
        "document_id": document_id,
        "document_title": "",
        "course_id": course_id,
        "selected_text": selected_text,
    }

    if document_id and course_id:
        try:
            from app.core.dependencies import get_course_service, get_memory_service
            from app.infrastructure.course_documents import read_course_documents

            memory = get_memory_service()
            doc = get_course_service().get_document(document_id, str(context["user_id"]), memory)
            if doc is not None:
                reader_context["document_title"] = str(doc.title or "")
                reader_context["document_type"] = str(doc.type or "")

            result = read_course_documents(
                course_id=course_id,
                material_id=document_id,
                max_chars_per_doc=8000,
            )
            apply_document_read(context, result)
            if not reader_context["document_title"]:
                chunks = result.get("chunks") or []
                if chunks and isinstance(chunks[0], dict):
                    reader_context["document_title"] = str(chunks[0].get("title") or "")
        except Exception as exc:
            reader_context["preload_error"] = str(exc)[:240]

    context["reader_context"] = reader_context
    return reader_context


def reader_context_summary(context: dict[str, Any]) -> str:
    reader = context.get("reader_context")
    if not isinstance(reader, dict):
        return ""

    lines = ["【阅读器上下文】"]
    title = str(reader.get("document_title") or "").strip()
    if title:
        lines.append(f"- 当前文档：《{title}》")
    if reader.get("document_id"):
        lines.append(f"- document_id={reader.get('document_id')}")
    selected = str(reader.get("selected_text") or "").strip()
    if selected:
        lines.append("- 用户选中文段：")
        lines.append(selected[:4000])
    lines.append("- 请结合已加载文档资料与用户选段回答；若与选段无关，先说明再作答。")
    if reader.get("preload_error"):
        lines.append(f"- 文档预加载提示：{reader['preload_error']}")
    return "\n".join(lines)
