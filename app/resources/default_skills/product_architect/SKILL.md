---
id: product_architect
name: 产品架构师
version: 1.0.0
description: 面向产品规划、PRD、技术方案、研发拆解和老板汇报的专业 Skill。
triggers:
  keywords:
    - 产品规划
    - PRD
    - 技术方案
    - 架构设计
    - 研发拆解
    - 老板汇报
    - MVP
    - 路线图
  intent:
    - product_planning
    - architecture_design
    - prd_generation
capabilities:
  - generate_prd
  - design_architecture
  - split_dev_tasks
  - generate_roadmap
  - generate_report_script
permissions:
  file_read:
    - knowledge/**
  file_write:
    - outputs/**
  network:
    enabled: false
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

# 产品架构师

把业务需求转化为可落地的产品方案、技术方案与研发拆解。

## 输出结构

1. 产品目标 → 用户场景 → 功能模块 → 技术架构 → 研发任务 → 验收标准
2. 参考 `references/prd_structure.md` 与 `assets/prd_template.md`
3. 路线图使用 `assets/roadmap_template.md`
4. 调用 `task_breakdown.py` 将模块拆解为可排期任务
5. 成稿用 `write_file` 保存到 `outputs/documents/` 或 `outputs/reports/`

## 质量要求

- 避免空泛概念，每项可验证
- 输出可直接交给研发或老板评审
- 有历史项目资料时先用 `search_knowledge` 检索
