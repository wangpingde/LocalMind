---
id: meeting_notes
name: 会议纪要助手
version: 1.0.0
description: 将会议内容整理为结构化纪要并保存到 outputs
triggers:
  keywords:
    - 会议纪要
    - 会议记录
    - meeting notes
  intent:
    - writing
capabilities:
  - document_write
permissions:
  file_read:
    - knowledge/**
  file_write:
    - outputs/documents/**
  scripts:
    enabled: true
  tools:
    - read_file
    - write_file
    - search_knowledge
    - list_skill_resources
    - read_skill_asset
    - run_skill_script
---

# 会议纪要助手

将用户提供的会议内容整理为结构化纪要，并保存到 `outputs/documents/`。

## 输出格式

```markdown
# 会议纪要 — {主题}

- 时间：
- 参与人：

## 议题与结论
## 待办事项（负责人 / 截止日期）
## 风险与跟进
```

需要引用历史资料时，使用 `search_knowledge` 检索。完成后用 `write_file` 保存。
