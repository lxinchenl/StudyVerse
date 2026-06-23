# Explainer 静态播放

注册 bundle 并生成 iframe 可嵌入的 `player_url`。

## 实现

- `ResourceService.register_explainer_video` — 写入用户资源库 + 生成 play_token
- `GET /api/explainer/play/{play_token}/{file_path}` — 提供 index.html / MP3

## Bundle 布局

```
data/generated_resources/explainer/{resource_id}/
  index.html
  storyboard.json
  audio/scene-XX.mp3
  audio/manifest.json
  meta.json
```

## 注意

必须用 HTTP 访问（`/api/explainer/play/...`），不要用 `file://`。
