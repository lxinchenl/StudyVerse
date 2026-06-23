# Explainer HTML 渲染

将 storyboard JSON 渲染为全屏多分镜 `index.html`（CSS/JS 与 demo 一致）。

## 实现

- `app.infrastructure.explainer.html_renderer.render_explainer_html`

## 输入

| 字段 | 说明 |
|------|------|
| storyboard | 分镜 JSON（见 `skills/explainer-video-html/reference.md`） |
| output_path | 通常为 bundle 根目录下的 `index.html` |

## 视觉规范

见 `skills/explainer-video-html/visual-spec.md`
