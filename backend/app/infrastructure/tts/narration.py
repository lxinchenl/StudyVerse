"""Local scene narration via edge-tts (explainer-video-html pipeline)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
SCENE_TIMEOUT_SEC = 25.0


async def _synthesize_one(text: str, out_path: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(out_path))


async def generate_scene_audio(
    narrations: list[str],
    output_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    engine: str = "edge",
    on_scene: Callable[[int, int], Awaitable[None]] | None = None,
    scene_timeout: float = SCENE_TIMEOUT_SEC,
) -> dict[str, Any]:
    """
    Write scene-XX.mp3 + manifest.json under output_dir.
    Must be awaited from async code (VideoAgent / FastAPI).
    """
    if engine != "edge":
        raise ValueError("Only engine='edge' is supported in narration helper")

    output_dir.mkdir(parents=True, exist_ok=True)
    scenes_meta: list[dict[str, Any]] = []
    total = len(narrations)

    for i, text in enumerate(narrations, start=1):
        if on_scene is not None:
            await on_scene(i, total)
        filename = f"scene-{i:02d}.mp3"
        await asyncio.wait_for(
            _synthesize_one(text.strip(), output_dir / filename, voice),
            timeout=scene_timeout,
        )
        scenes_meta.append({"scene": i, "file": filename, "text": text.strip()})

    manifest = {"engine": engine, "voice": voice, "scenes": scenes_meta}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def generate_scene_audio_sync(
    narrations: list[str],
    output_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    engine: str = "edge",
) -> dict[str, Any]:
    """CLI / script entry — safe when no event loop is running."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(
        generate_scene_audio(narrations, output_dir, voice=voice, engine=engine)
    )


def edge_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False
