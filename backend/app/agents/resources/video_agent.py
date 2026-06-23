from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from pathlib import Path
from typing import Any

from app.agents.resources._helpers import retrieval_basis
from app.agents.resources.video_storyboard import (
    STORYBOARD_SYSTEM,
    build_storyboard_prompt,
    extract_narrations,
    parse_storyboard,
)
from app.core.config import get_settings
from app.infrastructure.tts.narration import edge_tts_available, generate_scene_audio
from app.interfaces.contracts import BaseAgent, LLMProvider
from app.services.app_services import ResourceService

DEMO_REF = "demo/2nf-animation.html"


async def _background_tts(
    *,
    audio_dir: Path,
    narrations: list[str],
    voice: str,
    event_sink: Any | None,
) -> None:
    async def on_scene(current: int, total: int) -> None:
        if event_sink is None:
            return
        await event_sink(
            {
                "type": "status",
                "message": f"后台生成配音 {current}/{total}…",
            }
        )

    try:
        await generate_scene_audio(
            narrations,
            audio_dir,
            voice=voice,
            on_scene=on_scene,
        )
        if event_sink is not None:
            await event_sink({"type": "status", "message": "讲解视频配音已全部生成"})
    except Exception as exc:
        if event_sink is not None:
            await event_sink({"type": "status", "message": f"配音生成失败：{exc}"})


class VideoAgent(BaseAgent):
    """
    讲解视频 Agent — HTML + 本地 MP3 bundle，并注册到用户资源库。
    """

    name = "video-agent"
    role = "多模态讲解视频 Agent"
    skill_id = "explainer-video-html"

    def __init__(
        self,
        llm: LLMProvider,
        resource_service: ResourceService,
        resources_dir: Path | None = None,
    ):
        self.llm = llm
        self.resource_service = resource_service
        self.resources_dir = resources_dir or get_settings().resources_dir

    def tool_context(self) -> dict[str, Any]:
        return {"resource_service": self.resource_service}

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        basis = retrieval_basis(context, max_chars=2000)
        prompt = build_storyboard_prompt(context["message"], basis)

        system = STORYBOARD_SYSTEM
        raw = await self.llm.complete(prompt, system=system)
        try:
            storyboard = parse_storyboard(raw)
        except ValueError:
            raw = await self.llm.complete(
                prompt + "\n\n上次 JSON 无效，请严格输出合法 JSON，scenes 5~7 条。",
                system=system,
            )
            storyboard = parse_storyboard(raw)

        resource_id = f"explainer-{uuid.uuid4().hex[:10]}"
        play_token = secrets.token_urlsafe(18)
        bundle_dir = self.resources_dir / "explainer" / resource_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        audio_dir = bundle_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        await self.invoke_tool(
            "explainer-html-render",
            storyboard=storyboard,
            output_path=bundle_dir / "index.html",
        )

        (bundle_dir / "storyboard.json").write_text(
            json.dumps(storyboard, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        narrations = extract_narrations(storyboard)
        voice = str(storyboard.get("voice") or "zh-CN-XiaoxiaoNeural")
        tts_note = "未生成音频：请在后端环境 pip install edge-tts"
        if not edge_tts_available():
            context.setdefault("expert_outputs", []).append(
                "讲解视频 HTML 已生成；未安装 edge-tts，跳过配音。"
            )
        elif narrations:
            tts_note = f"HTML 已就绪，配音后台生成中（{len(narrations)} 镜，约 1 分钟）"
            asyncio.create_task(
                _background_tts(
                    audio_dir=audio_dir,
                    narrations=narrations,
                    voice=voice,
                    event_sink=context.get("event_sink"),
                )
            )

        title = str(storyboard.get("title") or "讲解视频")
        topic = str(storyboard.get("topic") or context["message"][:40])
        summary = f"HTML 讲解动画 {len(narrations)} 镜 · {tts_note}"
        resource_item = await self.invoke_tool(
            "explainer-play",
            user_id=user_id,
            resource_id=resource_id,
            play_token=play_token,
            title=title,
            summary=summary,
            topic=topic,
            scene_count=len(narrations),
        )

        payload = {
            "resource_id": resource_id,
            "bundle_dir": str(bundle_dir),
            "html_path": str(bundle_dir / "index.html"),
            "player_url": resource_item.player_url,
            "play_token": play_token,
            "storyboard": storyboard,
            "skill": self.skill_ref(),
            "skill_id": self.skill_id,
            "demo_reference": DEMO_REF,
            "delivery": "html+audio",
            "title": title,
            "summary": summary,
            "scene_count": len(narrations),
        }
        context.setdefault("generated_resources", []).append(
            {"type": "video_script", "content": storyboard, **payload}
        )
        context.setdefault("expert_outputs", []).append(
            f"《{title}》HTML 已生成；配音在后台合成，完成后刷新播放器即可听到。"
        )

        trace_summary = (
            f"《{title}》HTML 已就绪（{len(narrations)} 镜），配音后台生成中。"
            f" player={resource_item.player_url}"
        )
        return {
            "content": storyboard,
            "resource_type": "video_script",
            "trace": self.trace(trace_summary),
            **payload,
        }
