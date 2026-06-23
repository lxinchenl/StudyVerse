---
name: explainer-video-html
description: >-
  Builds course explainer videos as HTML scene animations plus pre-generated
  local MP3 narration (edge-tts). Use for video-agent, explainer resources,
  lecture HTML animations, or HTML+audio teaching clips — not browser Azure TTS.
---

# Explainer Video：HTML + 本地音频

**运行时 skill 包**：`skills/explainer-video-html/`（manifest + 视觉规范；分镜 **system prompt 在** `video_storyboard.py`）

**核心方法**（与 `demo/2nf-animation.html` 一致）：

| 交付物 | 说明 |
|--------|------|
| `index.html` | 多分镜动画 + 全屏播放器 + 字幕条 |
| `audio/scene-01.mp3 …` | Python **edge-tts** 预生成旁白 |
| `audio/manifest.json` | 场景与音频映射 |

**不是**：浏览器 Azure SDK 实时合成、纯文字脚本、Seedance 直出。

`storyboard.json` 仅为中间结构，用于生成 HTML；最终用户打开的是 **HTML + MP3**。

参考 demo：`demo/2nf-animation.html` + `demo/audio/` + `demo/generate_narration.py`

## Pipeline（video-agent 必须走完整链路）

```
用户问题 + RAG 资料
  → LLM 输出 storyboard JSON（5–7 scenes）
  → render_explainer_html() → index.html
  → generate_scene_audio() → audio/scene-XX.mp3 + manifest.json
  → http.server 预览
```

代码入口：

- `app.infrastructure.explainer.html_renderer.render_explainer_html`
- `app.infrastructure.tts.narration.generate_scene_audio`
- `app.agents.resources.video_agent.VideoAgent`

## Bundle 目录

```
data/generated_resources/explainer/{resource_id}/
  index.html           ← 必出
  audio/scene-01.mp3   ← 必出（edge-tts 可用时）
  audio/manifest.json
  storyboard.json
```

预览：

```bash
cd data/generated_resources/explainer/{resource_id}
python -m http.server 8765
# http://localhost:8765/index.html
```

## HTML 播放器行为（从 demo 复用）

- 全屏 `#app`，每镜一个 `.scene`
- **底部 `.subtitle-bar` 显示 scene.subtitle（必填）**，播放时加 `.speaking` 高亮，与当前镜配音同步
- 播放 `audio/scene-XX.mp3`，`onended` 后自动下一镜
- 无 MP3 时回退定时切镜
- **必须用 http:// 打开**，不要用 `file://`

## 字幕（storyboard 硬性要求）

| 字段 | 用途 |
|------|------|
| `narration` | edge-tts 朗读的完整口语稿 |
| `subtitle` | 屏幕底部字幕条文字，**每镜必填、非空** |

规则：

- 每一镜 JSON 必须有 `scene.subtitle`，渲染器写入 `.subtitle-bar`
- narration 较长时，subtitle 提炼本镜核心（约 15~40 字）；较短时可与 narration 相同
- 禁止只写 narration 不写 subtitle；禁止把字幕只放在 `visual.props` 里
- 校验：`parse_storyboard()` 会补全缺失 subtitle（从 narration 截取），但 LLM 应主动输出

## 分镜与画面规范

**完整视觉规范（箭头、字号、第四页分步、标注）见 [visual-spec.md](visual-spec.md)。** 以下为摘要：

| 规则 | 说明 |
|------|------|
| 5–7 镜 | 每镜一个知识点，禁止一镜多义 |
| 顺序 | 开场 → 示例表 → 问题+依赖图 → **step_panel 分步规则** → 反例+对比依赖 → 拆表 → 总结 |
| 箭头 | **禁止**表内 SVG；用表下 `.dep-diagram` + 节点箭头，不与文字重叠 |
| 表格 | `.data-table` 大字号；全屏 ≥ 1.1rem；`.scene-content` 宽约 1080px |
| 标注 | `column_tags`：`PK` / `非主键` / `重复列`；不只靠颜色 |
| 规则镜 | 必须 `step_panel` 三步：找 PK → compare 完全/部分依赖 → 结论 |
| 对比 | 绿 `compare-card good` = 完全依赖；橙 `bad` = 部分依赖 |
| PK 列 | `pk-col` 黄色；问题列 `highlight-col`；违规 `highlight-partial` |

## storyboard JSON（生成 HTML 的输入）

```json
{
  "title": "视频标题",
  "voice": "zh-CN-XiaoxiaoNeural",
  "scenes": [
    {
      "id": 1,
      "narration": "TTS 朗读全文",
      "subtitle": "字幕条文字",
      "visual": { "type": "title_card", "props": { "heading": "…", "tag": "…" } }
    }
  ]
}
```

`visual.type`：`title_card` | `data_table` | `step_panel` | `split_tables` | `summary_list` | `dep_diagram`

表格可嵌套 `diagram`、`badge`；详见 [reference.md](reference.md)。

## 配音

```bash
pip install edge-tts
```

默认发音人 `zh-CN-XiaoxiaoNeural`。VideoAgent 自动调用，无需 Azure Key。

## video-agent 完成标准

- [ ] `index.html` 已写入 bundle
- [ ] **每镜均有非空 subtitle，且 HTML 底部字幕条可见**
- [ ] 每镜 subtitle 与 narration 一致或 narration 更长（subtitle 为精简句）
- [ ] MP3 数量 = scenes 数量
- [ ] `player_url` 已注册（`/api/explainer/play/{token}/index.html`）
- [ ] 用户资源库 `{user_id}.json` 已写入 `video_script` 条目
- [ ] 聊天响应 `explainer_videos` 可内嵌 iframe 播放
- [ ] `delivery: html+audio`

## 可选扩展

- **Seedance**：从 `visual.props` 导出每镜画面 prompt，作为附加素材；主交付仍是 HTML+音频
- **Azure SDK**：仅用于 `generate_narration.py --engine azure`，非默认

## 附加资料

- **HTML 动画视觉规范（优化经验）**：[visual-spec.md](visual-spec.md)
- 组件 JSON 示例：[reference.md](reference.md)
- 可运行样例：`demo/2nf-animation.html`
