"""Copy extracted course images into note bundles and finalize Markdown embeds."""

from __future__ import annotations

import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

FIGURE_PLACEHOLDER = re.compile(r"【图】([^\n【】]+)")


def build_image_catalog_from_process(process: dict[str, Any] | None) -> str:
    if not process:
        return ""
    lines = ["## 可用插图资源"]
    count = 0
    for page in process.get("pages") or []:
        pnum = page.get("page")
        for img in page.get("images") or []:
            if _should_skip_image(img):
                continue
            src = Path(str(img.get("path") or ""))
            if not src.name:
                continue
            keep = str(img.get("keep") or "B").upper()
            desc = str(img.get("description") or "课件插图").strip()
            count += 1
            lines.append(f"- 第{pnum}页 `images/{src.name}` keep={keep}：{desc[:120]}")
            if keep == "A":
                caption = desc[:60] or src.stem
                lines.append(f"  **须嵌入**：`![{caption}](images/{src.name})`")
            elif keep == "B" and desc:
                lines.append("  用文字概括即可，不必嵌入图片")
    if count == 0:
        return ""
    lines.insert(1, "keep=A 的流程图/架构图/模型图必须用 `![说明](images/文件名)` 嵌入，禁止只写【图】文字占位。")
    return "\n".join(lines)


def prepare_note_image_assets(
    process: dict[str, Any] | None,
    images_dir: Path,
) -> list[dict[str, Any]]:
    if not process:
        return []
    images_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in process.get("pages") or []:
        pnum = page.get("page")
        for img in page.get("images") or []:
            if _should_skip_image(img):
                continue
            src = Path(str(img.get("path") or ""))
            if not src.is_file():
                continue
            filename = src.name
            if filename in seen:
                continue
            seen.add(filename)
            dest = images_dir / filename
            if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dest)
            keep = str(img.get("keep") or "B").upper()
            desc = str(img.get("description") or "").strip()
            assets.append(
                {
                    "id": str(img.get("id") or filename),
                    "filename": filename,
                    "rel_path": f"images/{filename}",
                    "page": pnum,
                    "keep": keep,
                    "description": desc,
                    "embed": keep == "A" or (keep == "B" and not desc),
                }
            )
    return assets


def finalize_note_markdown(markdown: str, assets: list[dict[str, Any]]) -> str:
    text = markdown.strip()
    if not text:
        return text
    used: set[str] = set()
    text = FIGURE_PLACEHOLDER.sub(lambda m: _replace_figure_placeholder(m, assets, used), text)
    for asset in assets:
        if not asset.get("embed") or asset["filename"] in used:
            continue
        rel = asset["rel_path"]
        if rel in text or asset["filename"] in text:
            continue
    return text


def _should_skip_image(img: dict[str, Any]) -> bool:
    status = str(img.get("status") or "")
    if status.startswith("跳过"):
        return True
    if str(img.get("keep") or "").upper() == "C":
        return True
    return False


def _replace_figure_placeholder(
    match: re.Match[str],
    assets: list[dict[str, Any]],
    used: set[str],
) -> str:
    caption = match.group(1).strip()
    asset = _match_asset_for_caption(caption, assets, used)
    if asset is None:
        return match.group(0)
    used.add(asset["filename"])
    alt = caption or asset.get("description") or asset["filename"]
    return f"\n\n![{alt}]({asset['rel_path']})\n\n"


def _match_asset_for_caption(
    caption: str,
    assets: list[dict[str, Any]],
    used: set[str],
) -> dict[str, Any] | None:
    candidates = [a for a in assets if a.get("embed") and a["filename"] not in used]
    if not candidates:
        return None

    best: dict[str, Any] | None = None
    best_score = 0.0
    for asset in candidates:
        desc = str(asset.get("description") or "")
        score = _caption_similarity(caption, desc)
        if asset.get("keep") == "A":
            score += 0.15
        if score > best_score:
            best_score = score
            best = asset

    if best is not None and best_score >= 0.2:
        return best
    return candidates[0] if candidates else None


def _caption_similarity(caption: str, description: str) -> float:
    if not caption or not description:
        return 0.0
    if caption in description or description in caption:
        return 1.0
    ratio = SequenceMatcher(None, caption, description).ratio()
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", caption)
    if not tokens:
        return ratio
    hit = sum(1 for t in tokens if t in description)
    return max(ratio, hit / len(tokens))
