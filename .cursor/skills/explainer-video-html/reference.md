# Explainer Video HTML — Reference

**方法**：HTML 动画播放器 + 本地 MP3（edge-tts）。JSON 只是生成 HTML 的中间格式。

## LLM system prompt（storyboard → HTML）

Use when calling the LLM from `VideoAgent`:

```
你是课程讲解视频分镜编剧。根据用户问题和参考资料，输出一个 JSON 对象（不要 markdown 包裹）。

要求：
- 5~7 个 scenes，每 scene 含 id、narration、subtitle、visual
- narration 为口语化中文，用于 TTS；subtitle 可略短
- visual.type 只能是：title_card | data_table | dep_diagram | step_panel | split_tables | summary_list
- 若一镜同时需要表格和箭头，拆成两个 visual（先 data_table，再 dep_diagram），或在一个 scene 的 props 里用 table + diagram 字段（见 schema）
- 只能使用参考资料中的概念与例子；资料不足时在 narration 中说明
- 数据库类题目：用表格、PK 标记、完全依赖 vs 部分依赖对比
- 视觉细节见 visual-spec.md：表下 dep_diagram、step_panel 三步、column_tags、大表格

JSON schema 见项目 skill explainer-video-html。
```

## Combined scene: table + diagram

Prefer one scene object with nested props:

```json
{
  "id": 3,
  "narration": "...",
  "subtitle": "...",
  "visual": {
    "type": "data_table",
    "props": {
      "title": "冗余问题：姓名重复存储",
      "columns": ["学号", "姓名", "课程号", "课程名", "成绩"],
      "rows": [["S001", "张三", "C01", "数据库", "92"]],
      "column_styles": { "1": "highlight-col" },
      "column_tags": { "1": "重复列" },
      "diagram": {
        "title": "函数依赖关系",
        "rows": [
          {
            "from": { "label": "学号", "hint": "S001", "style": "primary" },
            "arrow_label": "决定",
            "to": { "label": "姓名", "hint": "张三", "style": "danger" }
          }
        ],
        "caption": "同一学号 → 同一姓名，却在多行重复存储"
      },
      "badge": { "text": "数据冗余", "style": "warn" }
    }
  }
}
```

## step_panel (was nf2_panel in demo)

```json
{
  "type": "step_panel",
  "props": {
    "heading": "第二范式（2NF）在检查什么？",
    "lead": "前提：已满足 1NF",
    "steps": [
      {
        "title": "先确定主键 PK",
        "body": "选课表主键是两个字段的组合。",
        "chips": ["学号", "课程号", "复合主键 PK"]
      },
      {
        "title": "再看非主键字段怎么依赖主键",
        "compare": {
          "good": { "title": "完全依赖", "body": "成绩由学号+课程号一起决定" },
          "bad": { "title": "部分依赖", "body": "课程名只由课程号决定" }
        }
      },
      {
        "title": "2NF 结论",
        "body": "消除部分依赖，否则拆表。"
      }
    ]
  }
}
```

## CSS classes (HTML renderer)

| Class | Purpose |
|-------|---------|
| `.scene-content` | Max-width wrapper (~1080px) |
| `.data-table` | Large table typography |
| `.pk-col` | Composite/primary key column |
| `.highlight-col` | Redundant/problem column |
| `.highlight-partial` | Partial dependency |
| `.highlight-ok` | Valid full dependency |
| `.dep-diagram` | Gray box below table for arrows |
| `.dep-node.primary/danger/success/warn` | Node colors |
| `.dep-arrow` + `.dep-arrow-line` | Horizontal arrow |
| `.step-panel` / `.nf2-panel` | Numbered teaching steps |
| `.compare-card.good` / `.bad` | Side-by-side contrast |
| `.split-tables` | Three-table decomposition |
| `.summary-list` | Final recap |

## manifest.json

```json
{
  "engine": "edge",
  "voice": "zh-CN-XiaoxiaoNeural",
  "scenes": [
    { "scene": 1, "file": "scene-01.mp3", "text": "..." }
  ]
}
```

## Preview commands

```bash
# Regenerate demo audio
cd demo && python generate_narration.py

# Preview demo
cd demo && python -m http.server 8765

# Preview generated resource
cd data/generated_resources/explainer/{id} && python -m http.server 8765
```
