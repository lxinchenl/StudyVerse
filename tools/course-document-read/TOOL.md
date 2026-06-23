# course-document-read

按 `material_id` 或 `chapter_key` 读取课件纯文本，结果会合并进会话的 `retrieval.chunks`，供回答与资源专家使用。

- 整章/思维导图/本章总结：优先 `chapter_key`（如 ch2）
- 单讲精读：使用 catalog 中的 `material_id`
