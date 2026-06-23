"""Resolve and invoke tools declared under project ``tools/`` directory."""

from __future__ import annotations

import asyncio
import importlib
import inspect
from typing import Any

from app.tools.registry import get_tool_registry


def _import_handler(handler: str):
    if ":" not in handler:
        raise ValueError(f"Invalid handler (expected module:attr): {handler}")
    module_path, attr = handler.split(":", 1)
    module = importlib.import_module(module_path)
    target = module
    for part in attr.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"Handler is not callable: {handler}")
    return target


def _filter_handler_kwargs(handler, kwargs: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(handler)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    allowed = set(sig.parameters)
    return {k: v for k, v in kwargs.items() if k in allowed}


def _merge_kwargs(manifest: dict[str, Any], agent_context: dict[str, Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(kwargs)
    for key in manifest.get("context_keys") or []:
        if key in agent_context and key not in merged:
            merged[key] = agent_context[key]
    return merged


async def invoke_tool(
    tool_id: str,
    *,
    agent_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    manifest = get_tool_registry().get_tool(tool_id)
    handler_path = manifest.get("handler")
    if not handler_path:
        raise ValueError(f"Tool {tool_id} has no handler")

    handler = _import_handler(str(handler_path))
    call_kwargs = _filter_handler_kwargs(
        handler, _merge_kwargs(manifest, agent_context or {}, kwargs)
    )

    if inspect.iscoroutinefunction(handler):
        return await handler(**call_kwargs)

    result = handler(**call_kwargs)
    if asyncio.iscoroutine(result):
        return await result
    return result
