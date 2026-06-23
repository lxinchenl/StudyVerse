# user-profile-gather

从用户本地记忆文件整合画像线索（**不写入**，只读）：

- `data/users/{id}/user_profile.json`
- `data/users/{id}/conversation_memory/*.json`
- `data/users/{id}/practice_attempts.json`
- `data/generated_resources/{id}.json`

返回 `suggested_updates` 供主 Agent 调用 `user-profile-update` 写入。

用户说「更新画像」时，应先 gather（或阅读 ReAct 提示中的记忆整合块），再 `user-profile-update`，禁止让用户手工填报。
