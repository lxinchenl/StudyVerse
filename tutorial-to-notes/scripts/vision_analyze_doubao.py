#!/usr/bin/env python3
"""Analyze an image using Doubao (Volcengine) multimodal model.

This script is called when the main model doesn't support vision.
It sends the image to Doubao's API and returns the analysis text.

Usage:
  python3 vision_analyze_doubao.py <image_path> [prompt_text]

If prompt_text is omitted, uses the default V2 prompt.

Environment variables:
  DOUBAO_API_KEY    — Required: the API key from Volcengine
  DOUBAO_BASE_URL   — Optional: defaults to https://ark.cn-beijing.volces.com/api/v3
  DOUBAO_MODEL      — Optional: defaults to doubao-seed-2-0-mini-260428

Output: prints the analysis result to stdout.
"""

import os
import sys
import base64

# Default V2 prompt
PROMPT_V2 = """识别这张图的类型并提取内容：

类型选项：公式 | 文字段落 | 流程图 | 对比/分类表 | 架构图 | 示例图 | 代码截图 | 装饰性

内容提取：
- 公式 → LaTeX
- 文字 → 原文
- 流程图 → 描述节点关系和步骤走向
- 对比表 → 按"A是XX，B是XX，区别XX"格式输出
- 其他 → 一句话概括

最后给出：这张图对理解当前内容是否必要？A-核心需保留 B-辅助可用文字代替 C-可跳过"""


def image_to_base64(image_path):
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_media_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    return {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
    }.get(ext, 'image/png')


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 vision_analyze_doubao.py <image_path> [prompt]', file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else PROMPT_V2

    if not os.path.exists(image_path):
        print('Error: image not found: ' + image_path, file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get('DOUBAO_API_KEY')
    if not api_key:
        print('Error: DOUBAO_API_KEY env var not set', file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    model = os.environ.get('DOUBAO_MODEL', 'doubao-seed-2-0-mini-260428')

    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=120)

        data_url = 'data:' + get_media_type(image_path) + ';base64,' + image_to_base64(image_path)

        # Try chat completions first (most compatible)
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=1024,
        )
        print(resp.choices[0].message.content.strip())

    except Exception as e:
        # Fallback: try responses API (Doubao-specific format)
        print('chat.completions failed, trying responses API: ' + str(e), file=sys.stderr)
        try:
            from openai import OpenAI
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=120)
            data_url = 'data:' + get_media_type(image_path) + ';base64,' + image_to_base64(image_path)
            resp = client.responses.create(
                model=model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": data_url},
                        {"type": "input_text", "text": prompt},
                    ],
                }],
            )
            print(resp.output_text.strip())
        except Exception as e2:
            print('Both API formats failed. Last error: ' + str(e2), file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
