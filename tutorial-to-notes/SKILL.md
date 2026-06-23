---
name: tutorial-to-notes
description: >-
  Extract core knowledge from tutorial materials (PDF, PPT slides, video transcripts, web articles) across any discipline
  into structured .docx notes. Supports incremental appending across sessions (Day 1 Ch1 → Day 2 Ch2 appended).
  The method is discipline-agnostic — relies on universal signals (definitions, classifications, processes, pros/cons)
  rather than domain vocabulary. Before any docx operation, load the docx skill for implementation details.
license: Proprietary. LICENSE.txt has complete terms
---

# Tutorial-to-Notes: Structured Note-Taking from Tutorial Materials

## 重要：加载 docx skill

在执行任何 docx 操作（创建、读取、编辑、追加笔记）前，必须先加载 docx skill：

```python
skill_view(name='docx')
```

docx skill 提供了 python-docx 的具体实现代码（设置中文字体、段落缩进、OMML 数学公式等）。本 skill 只定义排版约束和逻辑流程，不重复实现细节。

## Overview

This skill converts tutorial content (course PPTs, textbook PDFs, lecture transcripts, documentation) into clean,
hierarchical notes in .docx format. It is designed for the **user-specific note-taking style** documented in this session:
concise Chinese + English technical terms, hierarchical bullet structure, classification-first, no decorative formatting,
and incremental append across sessions.

**Key principles:**
- **Discipline-agnostic**: Works for CS, math, physics, biology, engineering, social sciences — relies on universal structural signals, not domain vocabulary
- **Incremental**: Day 1 materials → Chapter 1 in docx; Day 2 materials → Chapter 2 appended to the same file
- **Output**: `.docx` only (python-docx), with fixed formatting constraints (宋体, hierarchical indentation, no decorative fluff)
- **Compression ratio**: ~10:1 from original material to final notes

### When to Activate

- User sends a PDF, PPT, video transcript, or web article and says "写笔记" / "做笔记" / "extract notes"
- User sends tutorial material and says "加到之前的笔记里" / "append to existing notes"
- User shares course material and the context is clearly study/note-taking

### Prerequisites

- `python-docx` installed (`pip install python-docx`)
- `pymupdf` installed for PDF text + image extraction (`pip install pymupdf`)
- `paddlepaddle==3.2.0` + `paddleocr[all]` for OCR (optional but recommended — see Step 3 for install commands)
- The user's existing notes file (if appending)
- **必须先加载 docx skill**：`skill_view(name='docx')` — 获取 python-docx 排版实现代码

---

## Step-by-Step Workflow

本流程分四阶段：
  1. 原始提取 → 过程文件（.md + images/）
  2. 结构分析 → 章节结构清单（scripts/analyze_structure.py）
  3. 逐节提取与压缩 → 按清单遍历每个小节
  4. 生成与校验 → docx + 完整性自查

---
### 第一阶段：提取与理解（产出过程文件）

#### Step 1: 逐页扫描，提取文字 + 图片

对每页 PDF，使用 `fitz` 的 dict 模式获取 block 列表，区分文字和图片：

```python
page = doc[i]
blocks = page.get_text("dict")["blocks"]
for b in blocks:
    if b["type"] == 0:      # 文字块
        # 提取文本
    elif b["type"] == 1:    # 图片块
        # 记录位置和后续提取路径
```

**重要：对比 pymupdf 文本与图片包含的文字**
pymupdf 的 text block 提取（type=0）已经覆盖了 PDF 中绝大多数文字内容。很多"图片"（type=1）实际上是公式截图、代码截图、或带样式的文字块——这些内容 pymupdf 可能通过其 text block 已经提取了。在决定是否分析图片前，先比较：

- 该页 pymupdf 文本长度 > 50 字 → 大部分信息已获取，图片可能是装饰性的
- 该页 pymupdf 文本长度 < 30 字 → 信息密集的图（流程图、架构图），需重点分析
- **图内容与文本内容重叠检测**：OCR/vision 结果中，如果 80%+ 的文字已存在于 pymupdf 文本中 → 该图属于冗余，跳过

#### Step 2: 生成过程文件（.md）

创建一个临时 markdown 文件，路径：`~/.hermes/笔记过程/[课程名]/[材料名]-过程.md`

每页格式：

```markdown
## 第X页

### 文本

[提取出的纯文本，合并所有文本块到一个段落]

### 图片1
![IMG:课程_第X页_图1](/绝对路径/到/图片.png)
状态: 待理解
文件大小: 168KB

### 图片2
![IMG:课程_第X页_图2](/绝对路径/到/图片.png)
状态: 跳过（小图标 <5KB）
```

**规则：**
- **合并同一页的所有文本块**到同一个 `### 文本` 下方，不要每个 span 单独成段
- 文本按原始顺序保留，**不做压缩或筛选**（这是原始信息，四问筛料在第二阶段做）
- 图片用 `page.get_images(full=True)` + `doc.extract_image(xref)` 提取
- **保存前先过滤**：`os.path.getsize(img_path)` < 5KB → 跳过，标记为"跳过（小图标）"；5-10KB → 可能装饰性
- 占位符格式：`![IMG:唯一标识](绝对路径)`
- 图片按顺序编号，反映其在页面中的上下位置
- 记录文件大小字段，帮助后续判断是否有分析价值

#### Step 3: 图片内容提取（OCR）

**⚠️ 硬性规则：不 OCR 不写笔记。** 必须完成此步骤才能进入下一阶段。即使 pymupdf 已提取了部分文字，也需确认图片中是否有遗漏内容（公式、代码、表格）。数学/公式型 PDF 的 pymupdf 文本提取往往非常稀疏（可能只提取到标题和页码）。

**推荐方案：PaddleOCR** — 运行 `batch_paddle_ocr.py`（实时保存，不跳过大图，无 API 费用）

```bash
python3 scripts/batch_paddle_ocr.py 第X章-过程.md
```

首次运行会下载模型文件（约 200MB，CPU 首次加载约 30 秒），缓存到 `~/.paddlex/official_models/`，后续秒级。安装和环境变量等细节见脚本注释和 `references/vision-provider-setup.md`。

**备用方案：Doubao 视觉 API** — `batch_vision.py`（需 `DOUBAO_API_KEY` 环境变量）

**回退方案**（OCR 和视觉 API 都不可用时）：
- 跳过图片分析，过程文件中保持 `状态: 跳过（无视觉模型）`
- 依赖 pymupdf 已提取的文本完成笔记

---

### 第二阶段：结构分析（产出章节结构清单）

**这是防止小节遗漏和图片错放的关键环节。** 在开始提取之前，必须全面了解材料的章节结构。

#### Step 4: 扫描过程文件，构建章节结构清单

运行结构分析脚本：

```bash
python3 scripts/analyze_structure.py 第X章-过程.md
```

输出示例：

```
=== 7.1 数据库设计概述  (p.3-p.14) ===
  7.1.1 数据库设计的特点 (p.3-p.5)
    ├─ p5图1  [keep=A]
  7.1.2 数据库设计方法 (p.6-p.8)
  7.1.3 数据库设计的基本步骤 (p.9-p.12)
    ├─ p11图1  [keep=A]
    ├─ p12图1  [keep=A]

=== 7.3 概念结构设计  (p.28-p.60) ===
  7.3.1 概念模型 (p.30-p.31)
  7.3.2 E-R模型 (p.32-p.39)
  7.3.5 用E-R图进行概念结构设计 (p.40-p.60)
    ├─ p42图1  [keep=A]
```

**关键改进（V2）：** 本脚本已修复两个已知问题：
- 不再只取每页第一个标题，现在捕获同一页上的所有标题（适用于目录页列出多个子节的情况）
- 不再硬编码"7."前缀，自动检测章节号（适用于第5章、第10章等任意章节）

**结构分析清单的用途：**
1. **防止漏小节** — 写每个大节前先看清单，确认所有子节编号一列排开，逐个处理
2. **图片基于页码归属** — 图片放在它所在页码对应的节下，**不看 OCR/vision 的语义内容决定归属**
3. **逐节处理** — 每个小节作为独立的提取单元，不从大节层面做概览式提取

#### Step 5: 手动修正脚本输出

结构分析脚本的标题检测可能有遗漏（例如页面编号前有特殊字符、标题被换行截断）。在开始逐节提取前，手动核对：
- 章节头部页（列出子节标题的目录页）是否都被识别了
- 有编号但脚本漏检的小节手动补充到清单中
- 确认页面范围推断正确（特别是跨大节时不要重叠）

#### Step 6: 过程文件自优化（手动步骤）

在进入逐节提取之前，先用上下文理解能力优化过程文件，提高后续提取质量：

**优化目标：**

1. **公式复原**：OCR 对数学公式的识别效果差（可能只认出零散的符号和数字）。结合该页的上下文文字（规则名称、变量说明等），推断并复原正确的公式。**复原后的公式必须写入最终笔记**，不能只留在过程文件中。

2. **代码块复原**：OCR 识别代码截图时可能丢失缩进和特殊字符。结合上下文推断并复原为结构正确的代码。**SQL 等可执行代码片段必须完整写入笔记**（例如 `SELECT * FROM Student, SC WHERE Student.Sno = SC.Sno;`）。

3. **与 pymupdf 文本去重**：对比 OCR/vision 结果和 pymupdf text block 文本。如果 80%+ 的内容已在 pymupdf 文本中出现 → 该图内容是冗余的，在过程中降级标记，最终笔记中不重复出现。

4. **语义连贯性检查**：对语义不连贯的图描述（多个碎片化的 OCR 文本），根据上下文判断其整体含义。碎片化内容不单独写入笔记，仅保留推断后的要点。

5. **图描述合并**：相邻页面多张图描述同一概念时，合并为一条笔记要点。

**产出：** 更新后的过程文件，图片描述已优化，冗余已清除。

---

### 第三阶段：逐节提取与压缩

#### Step 7: 按结构清单逐节处理

拿着结构分析清单，**逐条遍历每个小节**，不能跳过：

**对每个小节：**
1. 读过程文件中该小节页面范围的所有文本
2. 用"四问筛料"提取该小节的独立要点
3. 把小节页面范围内的图片（根据结构清单）分配到相应位置

**核心区别（vs 旧方法）：**
- ❌ 旧方法：读一个大节的页面区间，整体提取 → 先看到第一节内容就写，后面的漏了
- ✅ 新方法：结构清单列出所有小节，逐个处理，一个不漏

#### Step 8: 将图片描述合并回文本流

在四问筛料之前，将优化后的图片理解为 inline 内容合并到文本中：

- **A 级（核心图示）**：
  - 公式图 → 将复原后的公式直接写入笔记（如 `E1 × E2 ≡ E2 × E1`）
  - 代码截图 → 将完整代码写入笔记（如 `SELECT * FROM Student, SC WHERE Student.Sno = SC.Sno;`）
  - 流程图/架构图 → 将结构描述以 `【图】` 标记写入（如 `【图】查询处理走向：查询分析→查询检查→查询优化→查询执行`）
  - 只有流程图/架构图这类**结构信息无法用文字替代的**才嵌入实际 PNG 图片到 docx
- **B 级（辅助理解）** → 直接压缩为文字要点，不保留图，不嵌入图片
- **C 级（装饰性）** → 丢弃

#### Step 9: 四问筛料

对合并后的内容（原文 + 图描述）做四问筛料：

| 条件 | 保留 |
|------|------|
| 核心定义 | 概念是什么、本质、三要素 |
| 分类/谱系 | 分为A/B/C、谱系递进 |
| 操作流程 | 步骤链、流程 |
| 一句话优劣 | 优缺点1-2行 |
| ✅ **例子示例** | **每个概念条目必须附带一个例子（`例：`），见Step 10例子规则** |

#### Step 10: 压缩重写与层级组织

应用固定模板：

| 类型 | 模板 | 示例 |
|------|------|------|
| 定义 | `XX：一句话本质` | `知识三要素：合理性、真实性、被相信` |
| 分类 | `分为：A（XX）、B（XX）` | `分为：术语匹配（文字）、结构匹配（图）` |
| 流程 | `流程：Step1→Step2→Step3` | `流程：实体识别→关系抽取→知识融合` |
| 图信息 | `【图】XX描述` | `【图】查询处理走向：查询分析→查询检查（语法树）→查询优化→查询执行` |
| 优缺点 | 行内 | `优点实现简单，缺点可能误判` |
| **例子** | **每个陌生概念后紧跟一个例子，格式 `例：XXX`** | **`视图是虚表→例：CREATE VIEW IS_Student AS SELECT ...` / `LIKE通配符→例：WHERE Sname LIKE '刘%'`** |

**例子规则（关键质量要求）：**
- 每个核心定义/分类/流程条目后必须跟一个具体例子
- 优先使用教材中的例题、插图说明、SQL语句
- 教材无合适例子时，由 Agent 根据上下文自己构造一个典型例子
- 例子写在概念之后，另起一行或行内均可，格式统一用 `例：` 前缀
- SQL相关章节：每个SQL语法结构必须配一个执行例子（SELECT/CREATE/INSERT等）

4 级层次结构：

```
主题 (Heading 1, center, 18pt)
  └ 子主题/方法 (Heading 2, left, 15pt)
      └ 具体方法/分类 (Heading 3, left, 13pt, indent 0.75cm)
          └ 要点、例子、流程 (Normal, 12pt, indent 1.5cm)
```

### 第四阶段：生成与校验

#### Step 11: 生成后完整性校验（关键质量门）

在交付 final docx 前，必须对照结构分析清单执行以下自查：

**1. 小节覆盖率检查**
- 拿出结构分析清单（Phase 2产出），逐一核对每个小节是否在 docx 中出现了
- 特别注意：清单中的每个小节编号都必须有对应的内容
- **如果发现有小节没写 → 回到 Step 6 补写，不以"内容太少不值得写"为由跳过**

**2. 图片归属检查**
- 对照结构分析清单，确认每张嵌入 docx 的图片，它的页码落在当前小节的页面范围内
- 方法：记下该节在清单中的页面范围，检查所用图片的来源页号是否在此区间
- 常见错误：不小心用了同章之前或之后节的图（页码接近容易混）

**3. 内容与标题一致性检查**
- 快速浏览输出笔记，确认每节的标题和实际内容匹配
- 例如标题是"数据模型的优化"，内容必须讲的是规范化理论和方法，而不是其他话题

发现问题立即修正，不要等用户指出。

#### Step 12: 处理增量追加

**First use (no existing file):**
- Create new docx file named `[课程名]-笔记.docx`
- Use full formatting (see Formatting Constraints below)

**Subsequent use (existing file exists):**
- Load existing docx with `python-docx`
- 扫描所有包含章节标记的段落文本（如"第N章"、"Chapter N"等），不只是 Heading 样式
- 从新材料的标题推断章节号，确定插入位置
- 插入逻辑：
  - 如果新章节号 < 已有第一个章节号 → 插在最前面
  - 如果新章节号介于两个已有章节之间 → 插在对应位置
  - 如果新章节号 > 所有已有章节 → 追加到末尾
  - 如果新章节与已有章节相同 → 追加到该章节末尾
- 插入方式：`ref_element.addprevious(new_element)`，**必须按正序依次插入**
- 标题解析：支持"第N章"、"Chapter N"、"N."、"N.N"等格式
- **DO NOT** modify or reorganize existing content other than inserting

**File naming:**
- User can specify a filename explicitly
- Otherwise infer: "知识工程-笔记.docx", "数据库-笔记.docx", etc.

#### 过程文件清理

最终 docx 输出后，询问用户是否删除过程文件（`.md` 和 `images/` 目录）。

---

## Pitfalls

1. **PaddleOCR 版本兼容性（最重要的坑）。** PaddleOCR 3.x 必须配合 `paddlepaddle==3.2.0`。装最新版 `3.3.1` 会报 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute`。pip安装时必须明确指定版本号，且用飞桨官方源：`pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/`。

2. **OCR：pymupdf 已覆盖大部分文字 + 不 OCR 不写笔记。** 很多"图片"只是渲染成图片的文字/公式/代码。先用 pymupdf 判断：文本 > 50 字 → 大概率不需要 OCR；< 30 字 → 信息密集图需重点分析。**但硬性规则：不 OCR 不写笔记。** 先跑 `batch_paddle_ocr.py`，再基于 OCR 结果写笔记。大图（>200KB）也要处理，**不要跳过**。进程被外部 SIGTERM 杀死时，脚本已内置 `_do_save()` 实时保存最多丢一张。

3. **PDF extraction may lose hierarchy.** pymupdf's `get_text()` flattens slide structure. Always manually reconstruct heading hierarchy from slide titles, font sizes, and numbering.

4. **图片尺寸过滤。** `page.get_images()` 会提取页码图标、装饰圆点等微图。<5KB 直接跳过；5-10KB 很可能装饰性；>50KB 可能是流程图/大图，优先分析。

5. **`addprevious` 顺序陷阱.** `ref.addprevious(new_elem)` 插入到 ref 紧前。插入多个元素时**必须按正序依次插入**：`for pe in new_content: ref.addprevious(pe)`。

6. **XML 文本转义.** `parse_xml()` 中的文本内容必须转义 `<`、`>`、`&`。使用 `text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')`。

7. **章节号检测.** 支持"第N章"、"Chapter N"、"N."、"N.N"、"Module N"等格式。用正则提取数字。失败则回退到文本匹配，再失败则追加到末尾。

8. **优先使用复用脚本.** `scripts/insert_chapter_into_docx.py` 封装了章节定位和插入逻辑。

9. **Incremental append: preserve existing formatting.** 追加到已有 docx 时，先读其样式参数再匹配，不要假设第一次创建的参数。

10. **User's note style is their own.** Do NOT introduce new structural elements or embellishments the user has not approved.

11. **Compression is the goal.** If draft is more than 20% of original material length, compress further. Aim for ~10%.

12. **Avoid mid-session creation gaps.** If user sends materials across multiple messages in one session, collect all before writing output.

13. **不能自动化的步骤：** 公式/代码复原、冗余图判断、语义连贯性检查（Step 6 过程文件自优化）需要上下文理解能力，不能写成自动化脚本。

14. **图片归属错误（常见且隐蔽）。** 嵌入 docx 前确认图片来源页号在该节的页面范围内，**图片按页码归属，不按语义内容归属**。使用结构分析清单作为核对标准。

15. **小节遗漏（最容易被忽略的错误）。** 必须做结构分析（Phase 2）拿到完整小节清单后逐条处理，不要跳过任何条目。

16. **不能跳过"内容太少"的小节。** 所有子节都必须有对应输出，内容少的一两句话概括即可。

17. **逐节提取 vs 整体提取。** 必须对**每个小节**独立做四问筛料，不能对大节做一次整体筛料再拆分。

18. **.jpeg 扩展名兼容问题。** python-docx 的 add_picture() 只识别 .jpg 和 .png。嵌入前用 PIL 将 .jpeg 转为 .png。

19. **跨 docx 追加时图片会丢失。** 一次性生成包含所有章节的完整 docx，不要跨文档拷贝含图段落。若需重写已存在的章节，删除原段落后再插入新内容。

20. **analyze_structure.py 无法正确处理目录页。** TOC 页列多个小节标题时页面范围计算崩溃。手动推断页面范围，脚本输出仅作参考。

21. **重置 OCR 状态时需同步清理旧行。** 重新运行 OCR 前，`类型:` / `内容描述:` / `保留判定:` 行也必须一并删除。
---

## Reference Files

- `references/notes-format.md` — Notes output format specification: fonts, sizes, hierarchy, example rules, highlight rules, and prohibited items. The single source of truth for docx formatting.
- `references/user-note-pattern-analysis.md` — Concrete examples of the user's extraction pattern, comparing original PDF with resulting notes.
- `references/vision-provider-setup.md` — Configuring vision support (Doubao, OpenRouter, or other). Includes fallback chain and image size heuristics.

## Reusable Scripts

- `scripts/analyze_structure.py` — Scan process .md file and generate section structure report (Phase A). Use BEFORE extraction to identify all subsections and image-by-page assignments.
- `scripts/insert_chapter_into_docx.py` — Insert chapter content into existing notes docx at correct position. Reads from stdin, auto-detects chapter number, inserts by order.
- `scripts/generate_notes_docx.py` — Generate formatted .docx from a process markdown file (text + vision descriptions). Bridge between process file and final output.
- `scripts/vision_analyze_doubao.py` — Single-image analysis via Doubao (Volcengine) multimodal model. Uses V2 prompt. Requires DOUBAO_API_KEY env var. Fallback when PaddleOCR unavailable.
- `scripts/batch_vision.py` — Batch process all "待理解" images via Doubao API. Calls vision_analyze_doubao.py on each, writes results back.
- `scripts/batch_paddle_ocr.py` — Batch OCR all &#34;待理解&#34; images via PaddleOCR. Saves to process file after EVERY image (real-time — crash-safe). No API cost. Handles all image sizes, no skipping.
- `scripts/example_generate_chapter.py` — Reference script for generating a chapter with images from a process file. Demonstrates the full Phase B+C workflow with correct image-by-page assignment and subsection coverage.

## Related Skills

- `docx` / `productivity/docx` — DOCX formatting and python-docx API patterns
- `ocr-and-documents` / `productivity/ocr-and-documents` — Text extraction from scanned PDFs
- `chinese-latex-report` — For when user requests LaTeX PDF output instead of docx
