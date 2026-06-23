"""Section structure analysis for note process (adapted from tutorial-to-notes analyze_structure.py)."""

from __future__ import annotations

import re
from typing import Any


def analyze_process_structure(pages: list[dict[str, Any]]) -> dict[str, Any]:
    headers = _find_section_headers(pages)
    top_sections, subsections = _infer_section_ranges(pages, headers)
    report_lines = _build_report(pages, top_sections, subsections)
    return {
        "top_sections": top_sections,
        "subsections": subsections,
        "report": "\n".join(report_lines),
        "section_count": len(top_sections),
        "subsection_count": len(subsections),
    }


def _find_section_headers(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    headers: list[dict[str, Any]] = []
    for page in pages:
        text = str(page.get("text") or "")
        for line in text.splitlines():
            line = line.strip()
            match = re.match(r"^(\d+\.\d+(?:\.\d+)?)\s+(.*)", line)
            if not match or not match.group(2).strip():
                continue
            headers.append(
                {
                    "page": int(page["page"]),
                    "num": match.group(1),
                    "name": match.group(2).strip(),
                    "text": line,
                }
            )
    return headers


def _infer_section_ranges(
    pages: list[dict[str, Any]], headers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not headers:
        return [], []

    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for header in headers:
        if header["num"] not in seen:
            seen.add(header["num"])
            uniq.append(header)

    chapter_prefix = uniq[0]["num"].split(".")[0] + "."
    chapter_headers = [h for h in uniq if h["num"].startswith(chapter_prefix)]
    top = [h for h in chapter_headers if len(h["num"].split(".")) == 2]
    subs = [h for h in chapter_headers if len(h["num"].split(".")) == 3]
    return top, subs


def _build_report(
    pages: list[dict[str, Any]],
    top_sections: list[dict[str, Any]],
    subsections: list[dict[str, Any]],
) -> list[str]:
    if not pages:
        return ["（未识别到章节标题，将按页序压缩）"]

    last_page = max(int(p["page"]) for p in pages)
    page_images: dict[int, list[dict[str, Any]]] = {}
    for page in pages:
        imgs = [img for img in (page.get("images") or []) if not str(img.get("status", "")).startswith("跳过")]
        if imgs:
            page_images[int(page["page"])] = imgs

    lines: list[str] = [f"总页数: {len(pages)}"]
    for i, sec in enumerate(top_sections):
        sec_num = sec["num"]
        next_page = last_page + 1
        if i + 1 < len(top_sections):
            next_page = top_sections[i + 1]["page"]
        lines.append(f"=== {sec_num} {sec['name']} (p.{sec['page']}-p.{next_page - 1}) ===")

        local_subs = [
            s
            for s in subsections
            if s["num"].startswith(sec_num) and sec["page"] <= s["page"] < next_page
        ]
        for s in local_subs:
            s_next = next_page
            for ss in local_subs:
                if ss["page"] > s["page"]:
                    s_next = ss["page"]
                    break
            lines.append(f"  {s['num']} {s['name']} (p.{s['page']}-p.{s_next - 1})")
            for sp in sorted(k for k in page_images if s["page"] <= k < s_next):
                for img in page_images[sp]:
                    keep = img.get("keep", "")
                    lines.append(f"    ├─ p{sp} {img.get('id')} [keep={keep}]")
    return lines
