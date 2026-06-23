from __future__ import annotations

from typing import Any

from app.services.app_services import ResourceService


def register_explainer_video(
    resource_service: ResourceService,
    *,
    user_id: str,
    resource_id: str,
    play_token: str,
    title: str,
    summary: str,
    topic: str,
    scene_count: int,
) -> Any:
    return resource_service.register_explainer_video(
        user_id,
        resource_id=resource_id,
        play_token=play_token,
        title=title,
        summary=summary,
        topic=topic,
        scene_count=scene_count,
    )
