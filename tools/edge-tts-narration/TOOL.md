# Edge TTS 场景配音

将分镜旁白列表转为 `audio/scene-01.mp3` … 及 `manifest.json`。

## 实现

- `app.infrastructure.tts.narration.generate_scene_audio`
- 默认发音人：`zh-CN-XiaoxiaoNeural`

## 输入

| 字段 | 说明 |
|------|------|
| narrations | 字符串列表，每镜一段 |
| output_dir | bundle 内 `audio/` 目录 |
| voice | 可选，edge-tts voice id |

## 输出

- `scene-01.mp3` … `scene-NN.mp3`
- `manifest.json`（场景索引与文件名映射）
