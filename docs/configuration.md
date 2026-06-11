# LocalMind 配置指南

> 版本：v0.1  
> 适用对象：首次使用 LocalMind 的用户与开发者  
> 最后更新：2026-06-10

本文档说明如何安装、启动并完整配置 LocalMind（本地个人 Agent 客户端），包括模型 Provider、知识库、长期记忆、Skill、隐私选项与高级文件配置。

---

## 目录

1. [快速开始](#1-快速开始)
2. [工作区与目录结构](#2-工作区与目录结构)
3. [界面配置（推荐）](#3-界面配置推荐)
4. [模型 Provider 配置](#4-模型-provider-配置)
5. [知识库配置](#5-知识库配置)
6. [长期记忆配置](#6-长期记忆配置)
7. [Skill 配置](#7-skill-配置)
8. [隐私与安全配置](#8-隐私与安全配置)
9. [配置文件参考（高级）](#9-配置文件参考高级)
10. [环境变量](#10-环境变量)
11. [验证配置](#11-验证配置)
12. [常见问题](#12-常见问题)
13. [配置检查清单](#13-配置检查清单)

---

## 1. 快速开始

### 1.1 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+、macOS 12+ |
| Python | 3.11+（推荐 3.11–3.14） |
| 内存 | 8GB+ |
| 网络 | 使用云端模型时需要可访问对应 API |

### 1.2 安装依赖

```powershell
# 进入项目目录
cd D:\jszx\project\LocalMind

# 创建虚拟环境（首次）
python -m venv .venv

# 安装依赖
.\.venv\Scripts\pip install -e ".[dev]"
```

macOS / Linux：

```bash
cd /path/to/LocalMind
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 1.3 启动应用

```powershell
.\.venv\Scripts\python main.py
```

启动后系统会自动：

1. 创建或加载工作区
2. 在后台启动本地 API 服务（默认端口 `17777`）
3. 打开 PySide6 桌面客户端
4. 安装内置 Skill（若工作区中不存在）
5. 扫描并索引 `knowledge/` 目录中的文档

### 1.4 三步完成最小配置

| 步骤 | 操作 |
|------|------|
| ① | 左侧导航 → **设置** → 填写模型 Base URL、API Key、对话模型、向量模型 → **保存设置** |
| ② | 左侧导航 → **知识库** → **打开目录** → 将 `.md` / `.pdf` 等文档放入 `work/` |
| ③ | 左侧导航 → **聊天** → 发送测试消息，确认右侧上下文区有正常响应 |

---

## 2. 工作区与目录结构

### 2.1 默认工作区路径

| 平台 | 默认路径 |
|------|----------|
| Windows | `%APPDATA%\LocalMind\` |
| macOS | `~/Library/Application Support/LocalMind/` |
| Linux | `~/.local/share/LocalMind/`（可通过环境变量覆盖） |

Windows 完整示例：

```text
C:\Users\你的用户名\AppData\Roaming\LocalMind\
```

### 2.2 工作区目录结构

首次启动后自动创建：

```text
LocalMind/
├── config/
│   ├── app.yaml                 # 应用设置
│   └── model_providers.yaml     # 模型 Provider（不含 API Key）
├── knowledge/
│   ├── inbox/                   # 待整理文档
│   ├── work/                    # 工作资料（推荐）
│   ├── personal/                # 个人笔记
│   └── projects/                # 项目资料
├── memory/
│   └── archive/                 # 归档记忆
├── skills/
│   ├── installed/               # 已安装 Skill
│   └── disabled/                # 已禁用 Skill
├── vector_store/                # LanceDB 向量库
├── database/
│   ├── app.sqlite               # 主数据库
│   └── audit.sqlite             # 审计日志
├── outputs/
│   ├── documents/
│   ├── reports/
│   └── exports/
└── logs/
    └── app.log                  # 应用日志
```

### 2.3 各目录用途

| 目录 | 用途 | 是否建议手动编辑 |
|------|------|------------------|
| `config/` | 系统与应用配置 | 可以（高级用户） |
| `knowledge/` | 用户本地知识文档 | **推荐**，直接放文件 |
| `memory/` | 长期记忆文件存储 | 主要通过界面管理 |
| `skills/installed/` | 本地 Skill 包 | 可以，按规范添加 |
| `vector_store/` | 向量索引数据 | 不建议手动编辑 |
| `database/` | SQLite 数据库 | 不建议手动编辑 |
| `outputs/` | Agent 生成输出 | 可读可写 |
| `logs/` | 运行日志 | 只读查看 |

---

## 3. 界面配置（推荐）

所有日常配置均可在客户端完成，无需手动改文件。

### 3.1 进入设置页

1. 启动 LocalMind
2. 左侧导航栏点击 **设置**
3. 填写各项配置
4. 点击 **保存设置**

### 3.2 模型配置字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| Provider | 下拉选择 | 是 | 当前使用的 Provider 名称，如 `default`、`local_ollama` |
| 类型 | 下拉选择 | 是 | `openai_compatible` 或 `ollama` |
| Base URL | 文本 | 是* | 模型服务地址；Ollama 默认 `http://localhost:11434` |
| API Key | 密码框 | 否* | 云端模型必填；Ollama 可留空 |
| 对话模型 | 文本 | 是 | 聊天使用的模型名 |
| 向量模型 | 文本 | 是** | 文档索引与检索使用的 embedding 模型 |
| Temperature | 数值 | 否 | 默认 `0.7`，越高越发散 |
| Max Tokens | 整数 | 否 | 默认 `4096`，单次回复最大 token 数 |

\* OpenAI-Compatible 类型必须填写有效的 Base URL；API Key 首次必填，之后留空表示保留已保存的 Key。  
\*\* 知识库索引与记忆向量化依赖向量模型；未正确配置会导致索引质量下降或失败。

### 3.3 API Key 保存规则

- API Key **不会**写入 `model_providers.yaml`
- 通过 `keyring` 存入系统凭据：
  - Windows：凭据管理器
  - macOS：Keychain
- 界面中 Key 以掩码显示（如 `sk-a****xyz`）
- 更新 Key 时在密码框输入新 Key 后保存即可
- 留空不修改已保存的 Key

### 3.4 隐私配置字段

| 选项 | 默认值 | 说明 |
|------|--------|------|
| 本地优先模式 | 开启 | 强调本地资料与记忆优先 |
| 向模型发送文件路径 | 关闭 | 开启后，发给模型的上下文包含完整文件路径 |
| 向模型发送记忆片段 | 开启 | 关闭后，长期记忆不会注入模型上下文 |

### 3.5 路径配置字段

| 字段 | 说明 |
|------|------|
| 工作区 | 整个 LocalMind 数据根目录 |
| 知识库 | 文档扫描与索引的根目录 |

一般情况下保持默认即可。修改后需重启应用或重新索引知识库。

### 3.6 聊天页模型切换

聊天区顶部有 **模型** 下拉框，可在已配置的 Provider 之间切换（如 `default` / `local_ollama`），仅影响当前对话请求。

---

## 4. 模型 Provider 配置

LocalMind 通过统一 `ModelGateway` 调用模型，支持两类 Provider：

| 类型 | 说明 |
|------|------|
| `openai_compatible` | 兼容 OpenAI API 格式的云端或自建服务 |
| `ollama` | 本地 Ollama 服务 |

### 4.1 OpenAI 官方

```yaml
# config/model_providers.yaml 中的 default 示例
default:
  type: openai_compatible
  base_url: "https://api.openai.com/v1"
  chat_model: "gpt-4o-mini"
  embedding_model: "text-embedding-3-small"
  temperature: 0.7
  max_tokens: 4096
```

界面填写：

| 字段 | 值 |
|------|-----|
| 类型 | openai_compatible |
| Base URL | `https://api.openai.com/v1` |
| API Key | 你的 `sk-...` |
| 对话模型 | `gpt-4o-mini` 或 `gpt-4o` |
| 向量模型 | `text-embedding-3-small` |

### 4.2 DeepSeek

| 字段 | 值 |
|------|-----|
| 类型 | openai_compatible |
| Base URL | `https://api.deepseek.com/v1` |
| API Key | DeepSeek API Key |
| 对话模型 | `deepseek-chat` |
| 向量模型 | 按 DeepSeek 官方文档选用；若无独立 embedding，可暂用 `deepseek-chat`（效果可能不如专用向量模型） |

### 4.3 通义千问（DashScope 兼容模式）

| 字段 | 值 |
|------|-----|
| 类型 | openai_compatible |
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| API Key | 阿里云 DashScope API Key |
| 对话模型 | `qwen-plus` / `qwen-turbo` 等 |
| 向量模型 | `text-embedding-v3` |

### 4.4 Moonshot（月之暗面）

| 字段 | 值 |
|------|-----|
| 类型 | openai_compatible |
| Base URL | `https://api.moonshot.cn/v1` |
| API Key | Moonshot API Key |
| 对话模型 | `moonshot-v1-8k` 等 |
| 向量模型 | 按官方文档配置 |

### 4.5 本地 Ollama

**前置条件：**

1. 安装 [Ollama](https://ollama.com/)
2. 拉取模型：

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

3. 确认服务运行：`http://localhost:11434`

**配置：**

| 字段 | 值 |
|------|-----|
| Provider | local_ollama |
| 类型 | ollama |
| Base URL | `http://localhost:11434` |
| API Key | 留空 |
| 对话模型 | `qwen2.5:14b` |
| 向量模型 | `nomic-embed-text` |

### 4.6 添加多个 Provider

在 `config/model_providers.yaml` 中可增加多个命名 Provider：

```yaml
default:
  type: openai_compatible
  base_url: "https://api.openai.com/v1"
  chat_model: "gpt-4o-mini"
  embedding_model: "text-embedding-3-small"
  temperature: 0.7
  max_tokens: 4096

deepseek:
  type: openai_compatible
  base_url: "https://api.deepseek.com/v1"
  chat_model: "deepseek-chat"
  embedding_model: "deepseek-chat"
  temperature: 0.7
  max_tokens: 4096

local_ollama:
  type: ollama
  base_url: "http://localhost:11434"
  chat_model: "qwen2.5:14b"
  embedding_model: "nomic-embed-text"
  temperature: 0.7
  max_tokens: 4096
```

在 `config/app.yaml` 中指定当前激活的 Provider：

```yaml
active_provider: deepseek
```

也可在界面 **设置** 页的 Provider 下拉框中选择并保存。

---

## 5. 知识库配置

### 5.1 支持格式

| 格式 | 扩展名 | 解析方式 |
|------|--------|----------|
| 纯文本 | `.txt` | 原文读取，按段落切块 |
| Markdown | `.md` | 优先按标题切分 |
| PDF | `.pdf` | PyMuPDF，按页切分 |
| Word | `.docx` | 按标题与段落切分 |

### 5.2 推荐目录用法

| 子目录 | 适合存放 |
|--------|----------|
| `knowledge/inbox/` | 刚下载、未整理的文档 |
| `knowledge/work/` | PRD、技术方案、会议纪要、竞品分析 |
| `knowledge/personal/` | 个人笔记、思考记录 |
| `knowledge/projects/{项目名}/` | 按项目隔离的资料 |

### 5.3 索引机制

```text
文件放入 knowledge/ 目录
  → 文件监听器检测新增/修改（约 2 秒防抖）
  → 计算文件 SHA256
  → 解析 → 切块 → 调用向量模型
  → 写入 LanceDB + SQLite 元数据
```

也可在界面 **知识库** 页手动操作：

| 按钮 | 作用 |
|------|------|
| 刷新 | 更新文档列表与统计 |
| 重新索引 | 全量重新扫描并索引 |
| 清空索引 | 删除所有索引记录（**不删除原文件**） |
| 打开目录 | 在资源管理器中打开知识库文件夹 |

### 5.4 文档索引状态

| 状态 | 含义 |
|------|------|
| `pending` | 待索引 |
| `indexing` | 索引中 |
| `indexed` | 已成功索引 |
| `failed` | 索引失败（查看错误列） |
| `outdated` | 文件已修改，索引过期 |
| `deleted` | 文件已删除 |

### 5.5 切块默认参数

| 参数 | 默认值 |
|------|--------|
| chunk_size | 800 tokens |
| chunk_overlap | 120 tokens |
| min_chunk_size | 100 tokens |
| max_chunk_size | 1200 tokens |

### 5.6 知识库使用建议

1. 文件名使用有意义的中文或英文，便于右侧来源展示
2. Markdown 文档使用清晰标题结构，检索效果更好
3. PDF 尽量为可选中文本版本，扫描件效果较差
4. 修改文档后等待自动重索引，或手动点 **重新索引**
5. 首次大量导入文档时，索引在后台进行，可在知识库页查看进度

---

## 6. 长期记忆配置

### 6.1 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `profile` | 用户身份、职业、背景 | 「我是 SaaS 产品经理」 |
| `preference` | 偏好、风格、表达习惯 | 「偏好结构化、可落地的方案」 |
| `project` | 项目长期上下文 | 「当前项目是做本地 Agent 客户端」 |
| `skill` | Skill 使用偏好 | 「写 PRD 时喜欢五段式结构」 |
| `episodic` | 事件型记忆 | 「上周评审通过了 MVP 方案」 |
| `semantic` | 概括型稳定认知 | 「公司技术栈以 Python + Vue 为主」 |

### 6.2 界面操作

路径：**记忆** 页

| 操作 | 说明 |
|------|------|
| 新增 | 选择类型，填写内容 |
| 编辑 | 选中后修改内容 |
| 删除 | 软删除，标记为 `deleted` |
| 禁用 | 标记为 `disabled`，不再召回 |
| 搜索 | 按类型筛选 + 关键词搜索 |

### 6.3 记忆如何影响回答

对话时系统会：

1. 根据用户问题检索相关记忆（向量 + 关键词）
2. 将 Top 记忆注入系统上下文（需开启「向模型发送记忆片段」）
3. 在右侧 **记忆** 标签展示本次使用的记忆
4. 更新记忆的 `last_used_at` 时间

### 6.4 记忆配置示例

**偏好类（最常用）：**

```text
类型: preference
内容: 用户偏好输出完整、结构化、可直接交给研发的方案，避免空泛概念。
标签: 回答风格, 产品规划
```

**身份类：**

```text
类型: profile
内容: 用户是 B 端 SaaS 产品架构师，主要负责技术方案与 PRD 评审。
标签: 职业, 背景
```

### 6.5 v0.1 说明

- 仅支持 **手动** 新增、编辑、删除记忆
- **自动记忆抽取** 默认关闭（`auto_memory_enabled: false`）
- 后续版本将支持对话后自动抽取与合并

---

## 7. Skill 配置

### 7.1 内置 Skill

首次启动会自动安装到 `skills/installed/`：

| ID | 名称 | 典型触发词 |
|----|------|------------|
| `local_knowledge_qa` | 本地知识问答 | 根据资料、本地文档、知识库 |
| `personal_writer` | 个人写作助手 | 写、周报、邮件、总结、方案 |
| `product_architect` | 产品架构师 | PRD、产品规划、技术方案、架构设计 |

### 7.2 界面操作

路径：**Skills** 页

| 操作 | 说明 |
|------|------|
| 启用 / 禁用 | 禁用后不参与关键词匹配 |
| 重新加载 | 扫描 `skills/installed/` 并刷新 |
| 打开目录 | 打开 Skill 安装目录 |

### 7.3 Skill 目录结构

```text
skills/installed/{skill_id}/
├── skill.yaml      # 元数据、触发词、权限（必须）
└── prompt.md       # 专业 Prompt（必须）
```

### 7.4 skill.yaml 示例

```yaml
id: my_custom_skill
name: 我的自定义 Skill
version: 1.0.0
description: 用于特定场景的能力描述。

triggers:
  keywords:
    - 关键词1
    - 关键词2
  intent:
    - custom_intent

capabilities:
  - custom_capability

permissions:
  file_read:
    - knowledge/**
  file_write:
    - outputs/**
  network:
    enabled: false
  shell:
    enabled: false
```

### 7.5 prompt.md 示例

```markdown
你是一个专注于 XX 领域的助手。

回答要求：
1. ...
2. ...
3. 优先结合本地知识库内容。
```

### 7.6 Skill 匹配规则（v0.1）

```text
用户问题
  → 与已启用 Skill 的 triggers.keywords 做关键词匹配
  → 按匹配得分排序，取 Top 3
  → 将匹配 Skill 的 prompt.md 注入系统上下文
```

示例：用户输入「帮我写一份 PRD」→ 自动匹配 `product_architect`。

### 7.7 安装自定义 Skill 步骤

1. 在 `skills/installed/` 下新建文件夹，如 `my_skill/`
2. 创建 `skill.yaml` 和 `prompt.md`
3. 打开客户端 **Skills** 页 → **重新加载**
4. 确认列表中出现新 Skill 且为 **启用** 状态
5. 用包含触发词的问题测试

---

## 8. 隐私与安全配置

### 8.1 核心原则

| 原则 | 说明 |
|------|------|
| 资料本地存储 | 文档、记忆、索引默认仅存本机 |
| 最小上下文 | 只将回答所需的片段发送给模型 |
| Key 安全存储 | API Key 不入配置文件、不写日志 |
| Skill 受限 | v0.1 仅 Prompt 注入，不执行 Shell / 网络 |

### 8.2 隐私相关配置项

| 配置项 | 配置键 | 默认值 | 说明 |
|--------|--------|--------|------|
| 本地优先模式 | `local_only_mode` | `true` | 产品级隐私倾向标识 |
| 发送文件路径 | `send_file_path_to_model` | `false` | 关闭后模型上下文只含文件名与片段 |
| 发送记忆片段 | `send_memory_to_model` | `true` | 控制记忆是否进入模型 prompt |
| 自动记忆 | `auto_memory_enabled` | `false` | v0.1 关闭 |
| Skill 网络 | `skill_network_enabled` | `false` | v0.1 关闭 |
| Shell 工具 | `shell_tool_enabled` | `false` | v0.1 关闭 |

### 8.3 发送给模型的上下文结构

```text
# System Rules
（安全规则）

# Active Skills
（匹配到的 Skill Prompt）

# User Memories
（相关长期记忆，可关闭）

# Local Knowledge
（RAG 检索片段）

# Conversation
（历史对话）

# User Input
（当前问题）
```

### 8.4 审计日志

敏感操作记录于 `database/audit.sqlite`，包括：

- 模型调用完成
- 文档索引成功/失败
- 记忆新增、修改、删除
- Skill 启用、禁用

---

## 9. 配置文件参考（高级）

### 9.1 app.yaml 完整字段

路径：`{工作区}/config/app.yaml`

```yaml
# 路径（留空则使用工作区默认值）
workspace_dir: ""
knowledge_dir: ""
memory_dir: ""
skills_dir: ""
output_dir: ""

# 服务
api_port: 17777

# 当前激活的 Provider 名称（对应 model_providers.yaml 中的 key）
active_provider: default

# 隐私
local_only_mode: true
send_file_path_to_model: false
send_memory_to_model: true
auto_memory_enabled: false
skill_network_enabled: false
shell_tool_enabled: false
```

### 9.2 model_providers.yaml 完整字段

路径：`{工作区}/config/model_providers.yaml`

```yaml
default:
  type: openai_compatible          # openai_compatible | ollama
  base_url: "https://api.openai.com/v1"
  chat_model: "gpt-4o-mini"
  embedding_model: "text-embedding-3-small"
  temperature: 0.7
  max_tokens: 4096
```

**注意：此文件不包含 `api_key`。** Key 需通过界面保存或系统凭据管理。

### 9.3 本地 API 地址

```text
http://127.0.0.1:{api_port}/api/
```

默认：

```text
http://127.0.0.1:17777/api/health
http://127.0.0.1:17777/api/settings
http://127.0.0.1:17777/api/chat
```

桌面客户端通过上述 API 与 Agent 核心通信，一般无需直接调用。

### 9.4 手动编辑配置文件后

1. 保存 YAML 文件
2. 重启 LocalMind，或在界面点 **重新加载**
3. 若修改了 `knowledge_dir` 或 Provider，建议重新索引知识库

---

## 10. 环境变量

### 10.1 LOCALMIND_DATA_DIR

覆盖默认工作区路径，适合开发与多环境隔离。

**Windows PowerShell：**

```powershell
$env:LOCALMIND_DATA_DIR="D:\localmind-dev-data"
.\.venv\Scripts\python main.py
```

**Windows CMD：**

```cmd
set LOCALMIND_DATA_DIR=D:\localmind-dev-data
python main.py
```

**macOS / Linux：**

```bash
export LOCALMIND_DATA_DIR=~/localmind-dev-data
python main.py
```

设置后，所有配置、知识库、数据库、向量库均在该目录下。

---

## 11. 验证配置

### 11.1 模型配置验证

1. **设置** → 保存配置
2. **聊天** → 发送：`你好，请用一句话介绍你自己`
3. 预期：流式返回正常文本，无报错

### 11.2 知识库验证

1. 在 `knowledge/work/` 放入 `测试.md`，内容示例：

```markdown
# 产品目标
LocalMind 的核心目标是打造本地个人 Agent 底座。
```

2. 等待自动索引，或 **知识库** → **重新索引**
3. 确认文档状态为 `indexed`
4. 提问：`LocalMind 的核心目标是什么？`
5. 预期：
   - 回答引用文档内容
   - 右侧 **文档** 显示 `测试.md`
   - 右侧 **检索片段** 有对应内容

### 11.3 记忆验证

1. **记忆** → 新增：

```text
类型: preference
内容: 用户偏好输出完整、结构化、可直接交给研发的方案。
```

2. 提问：`帮我设计一个本地 Agent 产品`
3. 预期：回答偏结构化；右侧 **记忆** 显示该条记录

### 11.4 Skill 验证

1. 确认 `product_architect` 为启用状态
2. 提问：`帮我写一份 PRD`
3. 预期：回答具备 PRD 结构；右侧 **Skills** 显示「产品架构师」

### 11.5 API 健康检查

```powershell
curl http://127.0.0.1:17777/api/health
```

预期响应：

```json
{
  "status": "ok",
  "workspace": "C:\\Users\\...\\AppData\\Roaming\\LocalMind"
}
```

---

## 12. 常见问题

### Q1：聊天报错「连接失败」或「401 Unauthorized」

**原因：** API Key 无效、Base URL 错误或模型名不存在。

**处理：**
1. 检查 **设置** 中 Base URL 与模型名是否与服务商文档一致
2. 重新输入 API Key 并保存
3. 查看 `logs/app.log` 获取详细错误

### Q2：知识库文档一直是 pending 或 failed

**原因：** 向量模型未配置、Key 无效、文件格式不支持或 PDF 损坏。

**处理：**
1. 确认 **向量模型** 已正确配置
2. 查看知识库列表中的 **错误** 列
3. 尝试将文件转为 `.md` 后重新放入
4. 点 **重新索引**

### Q3：问答不引用本地资料

**原因：** 文档未索引完成、问题与文档语义差距大、或索引为空。

**处理：**
1. 确认文档状态为 `indexed`
2. 使用更贴近文档措辞的提问，如「根据我的资料，XXX 是什么」
3. 可触发 `local_knowledge_qa` Skill 的关键词

### Q4：端口 17777 被占用

**处理：**
1. 修改 `config/app.yaml` 中 `api_port` 为其他端口（如 `17778`）
2. 重启应用
3. 或关闭占用该端口的程序

### Q5：向量库异常或检索混乱

**处理：**
1. 关闭应用
2. 删除 `{工作区}/vector_store/` 目录
3. 重启应用
4. **知识库** → **重新索引**

### Q6：Ollama 无法连接

**处理：**
1. 确认 Ollama 服务已启动：`ollama list`
2. 确认 Base URL 为 `http://localhost:11434`
3. 确认已 `ollama pull` 对话模型与 embedding 模型

### Q7：界面保存设置后未生效

**处理：**
1. 点 **重新加载** 确认已写入
2. 检查 `config/app.yaml` 与 `config/model_providers.yaml`
3. 完全退出并重启应用

---

## 13. 配置检查清单

上线使用前，可逐项确认：

- [ ] 已安装依赖并可以 `python main.py` 启动
- [ ] 工作区目录已自动创建
- [ ] 已在 **设置** 配置 Base URL、API Key、对话模型
- [ ] 已配置 **向量模型**（知识库索引必需）
- [ ] 聊天测试通过
- [ ] 已在 `knowledge/work/` 放入至少一份测试文档
- [ ] 文档索引状态为 `indexed`
- [ ] 本地知识问答测试通过
- [ ] 已添加至少一条 `preference` 类型记忆（可选）
- [ ] 内置 Skill 已加载且为启用状态
- [ ] 隐私选项已按个人需求调整
- [ ] 已知工作区路径，便于备份 `knowledge/` 与 `database/`

---

## 附录 A：推荐首次上传资料

| 类别 | 示例 |
|------|------|
| 方法类 | PRD 模板、评审 checklist、SOP、写作规范 |
| 资料类 | 项目文档、会议纪要、竞品分析 |
| 代表作 | 3–5 份认可的历史产出 |

## 附录 B：相关文档

| 文档 | 说明 |
|------|------|
| [README.md](../README.md) | 项目概览与快速入门 |
| [需求文档.md](../需求文档.md) | 完整产品与技术需求 |
| [architecture.md](./architecture.md) | 架构设计与数据流 |
| [LocalMind-PRD.md](./LocalMind-PRD.md) | 产品设计文档 |

---

如有配置问题，可先查看 `{工作区}/logs/app.log`，其中包含索引、模型调用与启动相关日志。
