"""Doubao (Volcengine ARK) multimodal vision — replaces PaddleOCR in tutorial-to-notes."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from openai import AsyncOpenAI

VISION_PROMPT_V2 = """识别这张图的类型并提取内容：

类型选项：公式 | 文字段落 | 流程图 | 对比/分类表 | 架构图 | 示例图 | 代码截图 | 装饰性

内容提取：
- 公式 → LaTeX 或文字描述
- 文字 → 原文
- 流程图 → 描述节点关系和步骤走向
- 对比表 → 按"A是XX，B是XX，区别XX"格式输出
- 代码截图 → 完整代码文本
- 其他 → 一句话概括

最后给出保留判定：A-核心需保留 B-辅助可用文字代替 C-可跳过

输出格式（纯文本）：
类型: ...
内容描述: ...
保留判定: A|B|C"""


def _media_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")


def _image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{_media_type(path)};base64,{encoded}"


class DoubaoVisionClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str | None = None,
    ):
        self.model = model or os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-2-0-mini-260428")
        self.client = AsyncOpenAI(base_url=base_url.rstrip("/"), api_key=api_key, timeout=120.0)

    @classmethod
    def from_settings(cls) -> "DoubaoVisionClient | None":
        from app.core.dependencies import get_llm_config_service

        cfg = get_llm_config_service().get_config()
        api_key = str(cfg.get("api_key") or os.getenv("DOUBAO_API_KEY") or os.getenv("ARK_API_KEY") or "").strip()
        if not api_key:
            return None
        return cls(
            base_url=str(cfg.get("base_url") or "https://ark.cn-beijing.volces.com/api/v3"),
            api_key=api_key,
            model=os.getenv("DOUBAO_VISION_MODEL"),
        )

    async def analyze_image(
        self,
        image_path: Path,
        *,
        page_text: str = "",
        prompt: str | None = None,
    ) -> str:
        if not image_path.is_file():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        user_prompt = prompt or VISION_PROMPT_V2
        if page_text.strip():
            user_prompt = f"该图所在页的课件文本（供上下文参考）：\n{page_text[:1200]}\n\n{user_prompt}"

        data_url = _image_data_url(image_path)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
