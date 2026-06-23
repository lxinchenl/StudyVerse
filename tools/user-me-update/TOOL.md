# user-me-update

更新 `data/users/{user_id}/me.json` 的工具。

## 用法

- `action=add|merge`：把 `updates` 合并写入 me（新增或覆盖）
- `action=delete|remove`：删除 `remove_keys` 指定字段
- `action=rewrite|replace`：用 `rewrite` 整体重写 me

## 示例

```json
{
  "action": "add",
  "updates": {
    "assistant_nickname": "贾维斯",
    "user_name": "昕宸"
  }
}
```

```json
{
  "action": "delete",
  "remove_keys": ["assistant_nickname"]
}
```

```json
{
  "action": "rewrite",
  "rewrite": {
    "role": "高校课程学习助手",
    "tone": "冷静、简洁",
    "boundaries": "基于课程资料回答"
  }
}
```

