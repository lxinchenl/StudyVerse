"""Storyboard JSON parsing helpers for explainer-video-html skill."""

from __future__ import annotations

import json
import re
from typing import Any

STORYBOARD_SYSTEM = """你是课程讲解视频分镜编剧。根据用户问题和参考资料，只输出一个 JSON 对象（不要 markdown、不要解释）。

结构：
{
  "title": "视频标题",
  "topic": "知识点",
  "voice": "zh-CN-XiaoxiaoNeural",
  "scenes": [
    {
      "id": 1,
      "narration": "TTS 口语旁白（完整朗读稿）",
      "subtitle": "底部字幕条文字（必填，屏幕可见）",
      "visual": {
        "type": "title_card | data_table | step_panel | split_tables | summary_list",
        "props": { }
      }
    }
  ]
}

字幕（硬性要求）：
- 每一镜都必须有非空的 scene.subtitle，渲染在 HTML 播放器底部 `.subtitle-bar`，与配音同步高亮
- narration 供 edge-tts 朗读；subtitle 供观众阅读——二者可以相同，也可 subtitle 为 narration 的精简句
- narration 较长（>40 字）时，subtitle 提炼本镜核心（建议 15~40 字）；narration 较短时可与 subtitle 一致
- 禁止省略 subtitle、禁止留空、禁止只写在 visual.props 里而不写 scene.subtitle

规则：
- 5~7 镜，每镜一个知识点
- visual.props 字段名必须严格使用下列 canonical 名称（不要用 table_header / main_title / desc 等别名）：
  · title_card: heading, tag
  · data_table: title, columns[], rows[][], column_styles, column_tags, diagram
  · step_panel: heading, lead, steps[{title, body, chips[]}]
  · split_tables: left_table/right_table 各含 title, columns[], rows[][]（或 tables[]）
  · summary_list: items[] 为字符串列表
- 顺序：开场 → 示例表 → 问题表+diagram → step_panel 规则三步 → 反例+双行 diagram → split_tables → summary_list
- 表格+箭头：data_table.props.diagram 在表下方独立展示；含 title、rows(from/to/arrow_label)、caption
- 列标注：column_styles（pk-col/highlight-col/highlight-partial/highlight-ok）+ column_tags（PK/非主键/重复列）
- 规则镜：step_panel 三步——①找主键 chips ②compare good/bad ③结论；禁止只用一句定义糊弄
- 反例镜：diagram 两行——部分依赖 badge warn + 完全依赖 badge ok
- 只能依据参考资料，不可编造规范条文
- narration 与 subtitle 使用简体中文
- 视觉细则见 skills/explainer-video-html/visual-spec.md
"""

VISUAL_TYPES = frozenset(
    {"title_card", "data_table", "step_panel", "split_tables", "summary_list", "dep_diagram"}
)


def build_storyboard_prompt(message: str, basis: str) -> str:
    return (
        f"用户问题：{message}\n\n"
        f"参考资料：\n{basis or '（无检索结果，请基于问题合理设计，并提醒用户补充课件）'}\n\n"
        "请输出 storyboard JSON。每一镜都必须包含非空 subtitle（HTML 底部字幕条，与配音同步显示）。"
    )


def _normalize_scene_subtitle(scene: dict[str, Any]) -> None:
    subtitle = str(scene.get("subtitle") or "").strip()
    narration = str(scene.get("narration") or "").strip()
    if subtitle:
        scene["subtitle"] = subtitle
        return
    if narration:
        scene["subtitle"] = narration if len(narration) <= 60 else narration[:57] + "…"
        return
    raise ValueError("每个 scene 必须含 subtitle 或 narration 以生成底部字幕")


def parse_storyboard(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM 输出中未找到 JSON")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("storyboard 必须是 JSON 对象")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not (5 <= len(scenes) <= 8):
        raise ValueError("scenes 数量应为 5~7（最多 8）")
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("每个 scene 必须是对象")
        visual = scene.get("visual") or {}
        vtype = visual.get("type")
        if vtype not in VISUAL_TYPES:
            raise ValueError(f"未知 visual.type: {vtype}")
        _normalize_scene_subtitle(scene)
    return data


def extract_narrations(storyboard: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for scene in storyboard.get("scenes") or []:
        text = str(scene.get("narration") or scene.get("subtitle") or "").strip()
        if text:
            lines.append(text)
    return lines
