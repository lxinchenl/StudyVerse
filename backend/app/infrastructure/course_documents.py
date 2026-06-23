"""List and read course materials as plain text for agent tools."""

from __future__ import annotations

from typing import Any

from app.core.dependencies import get_chunk_repo, get_course_catalog


def list_course_catalog(*, course_id: str) -> dict[str, Any]:
    catalog = get_course_catalog()
    course = catalog.get_course(course_id)
    if course is None:
        raise ValueError(f"课程不存在: {course_id}")

    chapters_meta = {ch["id"]: ch for ch in catalog.list_chapters(course_id)}
    materials = catalog.list_materials(course_id)
    chunk_repo = get_chunk_repo()

    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for material in materials:
        chunk = chunk_repo.get_chunk(material.id)
        text = (chunk or {}).get("text") or ""
        by_chapter.setdefault(material.chapter_key, []).append(
            {
                "material_id": material.id,
                "title": material.title,
                "chapter_key": material.chapter_key,
                "chapter_title": material.chapter_title,
                "doc_type": material.doc_type,
                "char_count": len(text),
            }
        )

    chapters: list[dict[str, Any]] = []
    for key in sorted(by_chapter.keys(), key=lambda k: chapters_meta.get(k, {}).get("order", 99)):
        meta = chapters_meta.get(key, {"id": key, "title": key, "order": 99})
        files = sorted(by_chapter[key], key=lambda f: f["title"])
        chapters.append(
            {
                "chapter_key": key,
                "chapter_title": meta.get("title", key),
                "order": meta.get("order", 99),
                "material_count": len(files),
                "materials": files,
            }
        )

    return {
        "course_id": course_id,
        "course_title": course.title,
        "chapter_count": len(chapters),
        "material_count": len(materials),
        "chapters": chapters,
        "summary": f"《{course.title}》共 {len(chapters)} 章目录、{len(materials)} 个文件",
    }


def read_course_documents(
    *,
    course_id: str,
    material_id: str | None = None,
    chapter_key: str | None = None,
    max_chars_per_doc: int = 6000,
) -> dict[str, Any]:
    if not material_id and not chapter_key:
        raise ValueError("请指定 material_id 或 chapter_key 之一")

    catalog = get_course_catalog()
    if catalog.get_course(course_id) is None:
        raise ValueError(f"课程不存在: {course_id}")

    chunk_repo = get_chunk_repo()
    cap = max(500, min(int(max_chars_per_doc), 20000))
    targets: list[Any] = []

    if material_id:
        material = catalog.get_material(material_id)
        if material is None or material.course_id != course_id:
            raise ValueError(f"未找到 material_id={material_id}")
        targets = [material]
    else:
        key = str(chapter_key).strip()
        targets = [m for m in catalog.list_materials(course_id) if m.chapter_key == key]
        if not targets:
            raise ValueError(f"章节 {chapter_key} 下无课件文件")

    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for material in sorted(targets, key=lambda m: m.title):
        row = chunk_repo.get_chunk(material.id)
        if not row:
            continue
        full_text = (row.get("text") or "").strip()
        if not full_text:
            continue
        truncated = len(full_text) > cap
        text = full_text[:cap]
        documents.append(
            {
                "material_id": material.id,
                "title": material.title,
                "chapter_key": material.chapter_key,
                "char_count": len(full_text),
                "returned_chars": len(text),
                "truncated": truncated,
            }
        )
        chunks.append(
            {
                "chunk_id": material.id,
                "document_id": material.chapter_key,
                "title": material.title,
                "text": text,
                "source": material.relative_path,
                "score": 1.0,
                "source_type": "document_read",
            }
        )

    if not chunks:
        raise ValueError("未能读取到有效文本内容")

    total_chars = sum(d["returned_chars"] for d in documents)
    summary = (
        f"已阅读 {len(documents)} 个文件，共 {total_chars} 字"
        + (f"（章节 {chapter_key}）" if chapter_key else f"（{documents[0]['title']}）")
    )
    return {
        "course_id": course_id,
        "chapter_key": chapter_key,
        "material_id": material_id,
        "documents": documents,
        "chunks": chunks,
        "summary": summary,
    }
