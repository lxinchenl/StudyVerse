# HTML 讲解动画视觉规范

来自 `demo/2nf-animation.html` 的迭代经验。**生成 storyboard 与渲染 HTML 时必须遵守。**

## 总体原则

1. **一镜一义**：每 scene 只讲一个点，不要「定义 + 反例 + 拆表」挤在一镜。
2. **先示例后抽象**：示例表 → 发现问题 → 规则分步 → 反例 → 解法 → 总结。
3. **可读性优先于炫技**：大屏/全屏观看，字要大、对比要强、结构要疏。
4. **动画是辅助**：CSS 淡入/高亮即可；不依赖复杂 SVG 路径动画。

## 布局与尺寸

| 元素 | 要求 |
|------|------|
| 内容区 | `.scene-content`，宽约 1080px（全屏 1200px），居中 |
| 表格 | 必须用 `data-table`；字号 `clamp(1rem, 1.8vw, 1.28rem)`，全屏 ≥ 1.1rem |
| 单元格 | padding 充足（全屏约 18×20px），避免挤成一团 |
| 字幕条 | 底部固定 `.subtitle-bar`，**每镜 scene.subtitle 必填**；朗读时加 `.speaking` 高亮 |
| 拆表页 | 三表用 `.split-tables`，每表字号与主表同级，不要「迷你表」 |

## 字幕内容

- **narration**：TTS 完整朗读稿，可口语化、可较长
- **subtitle**：观众在画面底部看到的字幕，**每镜必须有、非空**
- narration 超过约 40 字时，subtitle 提炼一句核心（建议 15~40 字）；否则可与 narration 相同
- 禁止省略 subtitle，或只把文字写在 `visual.props.tag` / `lead` 里而不写 `scene.subtitle`

## 依赖箭头（最容易翻车）

### 禁止

- ❌ 在 `<table>` 内或表头上画 SVG 箭头
- ❌ `preserveAspectRatio="none"` 拉伸 SVG（箭头变形、压字）
- ❌ 箭头与列标题/单元格文字重叠
- ❌ 一镜里多条依赖线交叉缠在一起

### 正确做法

- ✅ 表格在上，**独立** `.dep-diagram` 灰底区块在**表格下方**（`margin-top: 22px`）
- ✅ 用 **节点 + 水平箭头** 三件套：

```
.dep-node（学号） → .dep-arrow + .dep-arrow-line → .dep-node（姓名）
```

- ✅  diagram 上方加 `.dep-diagram-title` 说明这条线「与上表分开显示」
- ✅  diagram 下方 `.dep-caption` 一句话点题
- ✅ 需要警示时用 `.badge.warn` / `.badge.ok` 放在 diagram 行末，不要压在文字上

### 节点配色语义

| style | 含义 | 典型用途 |
|-------|------|----------|
| `primary` | 主键/决定因素 | 学号、课程号、完整 PK |
| `danger` | 冗余/问题 | 重复姓名列 |
| `warn` | 部分依赖/违反 | 课程名 ← 仅课程号 |
| `success` | 完全依赖/正确 | 成绩 ← 学号+课程号 |

## 表格高亮与标注

列/单元格样式（`column_styles` 用列索引字符串 `"0"`, `"1"` …）：

| class | 用途 |
|-------|------|
| `pk-col` | 复合主键列，黄色底 + 内边框 |
| `highlight-col` | 问题列（冗余），红色脉冲 |
| `highlight-partial` | 部分依赖列，橙色 |
| `highlight-ok` | 符合 2NF 的列，绿色 |

列头必须配 **文字标签**（`column_tags`），例如：

- `PK` — 主键组成部分
- `非主键` — 普通字段
- `重复列` — 冗余字段

**不要**只靠颜色，色盲/投影看不清时标签是唯一依据。

## 规则讲解镜（原第四页经验）

抽象规则（如 2NF）**不要**用左右两卡片草草带过。必须用 `step_panel`：

1. **Step 1 — 找主键**：`pk-group` + `pk-chip` 列出「学号 + 课程号 = 复合主键」
2. **Step 2 — 查依赖**：`compare-grid` 并排
   - 左 `compare-card good`：✓ 完全依赖（举例：成绩）
   - 右 `compare-card bad`：✗ 部分依赖（举例：课程名）
3. **Step 3 — 结论**：一句话 + 动作（拆表 / 消除部分依赖）

每步带 `.step-num` 圆圈序号，逐步 `fadeUp` 动画。

## 反例镜（违反规则）

- 表头标 PK + 非主键
- diagram 里**两行对比**：先「部分依赖 ✕」，再「完全依赖 ✓」
- 右上角可选 `.cross-mark` 红叉
- 底部 `.partial-label` 用**整行说明框**（橙底边框），不要一行小字

## 拆表 / 总结镜

- **split_tables**：学生表 | 课程表 | 选课表，三表同大
- 可选 diagram 说明「部分依赖被拆到各自表中」
- **summary_list**：3 条 bullet + `.summary-footer` 金句

## 配色与风格

- 背景：浅蓝渐变 `#eef6ff → #f8fbff`
- 主色：`#2563eb`（标题、表头）
- 卡片：白底圆角 16–18px，轻阴影
- 全屏时 top-bar / controls 半透明深色，保证字幕可读

## Storyboard 编写检查（生成前自检）

- [ ] **每镜是否都有非空 subtitle（底部字幕条）？**
- [ ] 含表格的镜，若讲依赖，props 里是否有 `diagram` 且 title/caption 清晰？
- [ ] 规则镜是否用 `step_panel` + 3 步 + compare？
- [ ] 是否给 PK/问题列加了 `column_tags`？
- [ ] 是否避免一镜超过 2 个 visual 重点？
- [ ] narration 能否在 8–15 秒内读完？（约 30–60 字/镜）

## 反模式速查

| 反模式 | 改法 |
|--------|------|
| 箭头压表头 | diagram 移到表下 |
| 表格太小 | data-table + 全屏字号 |
| 第四页只有一句定义 | 改 step_panel 三步 |
| 只有颜色没有标签 | 加 column_tags |
| 没有底部字幕 | 每镜补 scene.subtitle，渲染为 .subtitle-bar |
| 纯 prose 脚本 | 必须出 HTML + MP3 bundle |

## 参考文件

- 达标样例：`demo/2nf-animation.html`（尤其第 3–5 镜）
- 渲染实现：`backend/app/infrastructure/explainer/html_renderer.py`
