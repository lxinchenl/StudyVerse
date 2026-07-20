# user-profile-gather

从用户本地记忆文件**只读加载原始材料**（**不写入**，**不解析主题**）：

- `data/users/{id}/user_profile.json` — 当前已存画像
- `data/users/{id}/conversation_memory/*.json` — 近期对话原文
- `data/users/{id}/practice_attempts.json` — 练习低分记录
- `data/generated_resources/{id}.json` — 已生成资源原文

## 返回内容

返回 `raw_materials`，包括：

- `conversation_records`：用户/助手对话原文（role、content、time）
- `generated_resources`：资源 title/topic/type 原文
- `practice_low_scores`：低分练习记录原文

**不会**返回 `suggested_updates`，也不会把用户原话拼成 `recent_topics`。

## 主 Agent 用法

用户说「更新画像」时：

1. 先 `user-profile-gather` 读取原始材料
2. **由主 Agent 自己阅读对话与记录**，提炼知识点/章节/薄弱点
3. 再 `user-profile-update` 写入画像

禁止让用户手工填报；也禁止把对话原句整句抄进 `recent_topics`。
