# User Note-Taking Pattern Analysis

This file documents the user's specific note-taking style observed from comparing the original tutorial material
("02 知识表示.pdf" — 57 slides) with their resulting notes ("知识工程.docx").

Use this as a reference when applying the tutorial-to-notes skill for this user. The patterns below are concrete
examples of what the skill's "Four-Question Filter" and "Compress and Rewrite" steps look like in practice.

---

## Compression Ratio

| Material | Content | Size Estimate | Result |
|----------|---------|---------------|--------|
| Original PDF | "02 知识表示.pdf" | ~57 slides, ~8000 words | ~800 words in notes |
| Ratio | ~10:1 | | |

---

## What Gets Kept (with original→note examples)

### 1. Core Definitions (Q1)

| Original (PDF) | User's Note |
|----------------|-------------|
| "知识是人类通过观察、学习和思考有关客观世界的各种现象而获得并总结出的所有事实、概念、规则或原则的集合。知识的三要素：合理性、真实性、被相信" | `知识三要素：合理性，真实性，被相信` |
| "知识表示（KR）就是用易于计算机处理的方式来描述人脑的知识的方法。KR不是数据格式...KR支持推理" | `核心：用机器可用的方式处理人脑知识，核心是可推理` |

### 2. Classification/Spectrum (Q2)

| Original (PDF) | User's Note |
|----------------|-------------|
| "属性图 vs RDF vs OWL" (full page of comparison) | `表达能力：朴素图-RDF/属性图-OWL` then `朴素图：语义网络；属性图：节点边带属性；RDF：主谓宾三元组；RDFS：模式层，定义类；OWL：RDFS拓展，加互反/传递/等价/对称等` |
| "一阶谓词逻辑 / Horn Logic / 产生式规则 / 框架系统 / 语义网络" (5 separate slides) | `传统方法：一阶谓词、霍恩逻辑、产生式系统、框架系统、语义网络` (each with 1-2 line essence) |

### 3. Process/Workflow (Q3)

| Original (PDF) | User's Note |
|----------------|-------------|
| Knowledge fusion flow across multiple slides | `流程：实体识别→关系抽取→知识融合` |
| Knowledge fusion sub-flow | `分块→负载均衡→记录连接` |

### 4. One-Line Pros/Cons (Q4)

| Original (PDF) — full table with advantages/disadvantages | User's Note |
|------------------------------------------------------------|-------------|
| "一阶谓词逻辑 优点：自然性、严密性、易实现性；缺点：表达能力有限、组合爆炸、效率低" | `推理高效，表达能力弱，组合爆炸` |
| "产生式系统 优点：自然性、模块性、有效性、清晰性；缺点：效率不高、组合爆炸、不能表达结构性知识" | `直观，效率低，非结构化` |
| "框架系统 优点：描述完整全面、知识库质量高、允许数值计算；缺点：构建成本高、不灵活" | `知识完整，支持计算；构建复杂` |
| "语义网络 优点：结构性、联想性、自然性；缺点：非严格性、处理复杂性" | (absorbed into one-line listing) |

---

## What Gets Dropped

| Category | Examples from this session |
|----------|---------------------------|
| Historical background | "1968 年 J.R.Quillian 在其博士论文中最先提出语义网络" |
| Detailed motivation | "RDF allows to express facts... But we'd like to be able to express more generic knowledge" |
| Visual content | Diagrams, arrows, example images from slides |
| Code listings | The entire Lisp `defun *database*` code block |
| Redundant re-explanation | Multiple slides repeating "什么是知识表示" |
| Full paragraphs of comparison | The 3-page comparison of 属性图 vs RDF vs OWL |
| Mathematical formulas | Detailed vector/embedding math from TransE/DistMult slides |
| Table layouts | Pros/cons tables reformatted into inline text |

---

## Information Restructuring Patterns

| PDF Structure | Note Structure |
|---------------|----------------|
| Chapters & slides | Hierarchical bullet: `主题→子主题→方法→细节` |
| Scattered across slides | Grouped by topic: all 符号表示 together, all 向量表示 together |
| Paragraphs → sentences | Key-value pairs: `概念：定义`, `流程：步骤`, etc. |
| Full evaluation text | Compact inline: `优点XX，缺点XX` |
| Multiple slides on one method | 1-2 bullet points covering definition + example + note |

---

## Signal Words Consistently Used in Notes

- `是什么` — marks definition content
- `本质` — marks core essence
- `核心` — marks key insight
- `分为` / `类型` — marks classification
- `流程` — marks process steps
- `如` — marks example insertion
- `优点` / `缺点` — marks evaluation
- `本质还是...` — marks distilled insight (often the most valuable signal)

---

## Consistent Convention: Prefix Ordering

When listing multiple items under the same parent, the user consistently uses the order:
1. What is it (是什么/本质/定义)
2. How is it classified (分为)
3. What is the process (流程/步骤/方法)
4. What are the pros/cons (优点/缺点)
5. Concrete example (如)

This convention should be followed when generating new notes.
