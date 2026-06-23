# 课程资料目录

每门课程对应一个子文件夹，系统启动时自动扫描并注册。

## 目录结构

```text
data/courses/
  {course-id}/                 # 课程 ID，建议使用英文 slug
    course.json                # 课程元数据（可选）
    materials/                 # 推荐：课件放这里
      第1章 xxx.pptx
      第2章 xxx.docx
      ...
```

## course.json（可选）

```json
{
  "title": "数据库系统原理",
  "description": "课程简介"
}
```

若不提供 `course.json`，系统将使用文件夹名作为课程标题。

## 支持的文件格式

- `.pptx` / `.pptx`
- `.docx` / `.doc`
- `.pdf`
- `.md` / `.markdown`
- `.txt`

## 章节分组规则

系统根据文件名中的 **「第X章」** 自动分组，例如：

- `第2章 关系运算 第2讲_传统集合运算.pptx` → 归入「第2章 关系运算」
- 不含章节前缀的文件 → 归入「实验与其他资料」

## 新增课程

1. 在 `data/courses/` 下新建文件夹，如 `machine-learning/`
2. 写入 `course.json`（可选）
3. 在 `materials/` 中放入课件
4. 重启后端，或删除 `data/cache/course_material_chunks.json` 后刷新

## 练习题（可选）

在课程目录下放置 `questions.json`，练习页会自动加载：

```json
[
  {
    "id": "q1",
    "topic": "关系运算",
    "difficulty": "medium",
    "question": "并运算和交运算的区别是什么？",
    "answer": "并运算取两集合所有元组，交运算只取同时属于两集合的元组。"
  }
]
```

未提供该文件时，练习页为空。也可在学习对话中触发 Agent 生成练习题（写入资源库后接入）。

## 示例

当前已内置：

- `db-principles/` — 数据库系统原理（从 kg_rag_demo 课件迁移）
