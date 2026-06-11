# LocalMind（智匣）

> 下载一个越来越像你的本地同事。

LocalMind 是一个跨平台桌面 AI 客户端。用户上传自己的工作资料和方法文档，配置自购 AI Key，即可在本地获得一个越来越像自己的 AI 数字分身。

**数据 100% 本地存储。无需部署任何服务。**

---

## 核心特性

- **数字分身** — 上传方法文档定义「你怎么做事」，上传资料文档提供「你知道什么」
- **双库 RAG** — 方法库优先注入 + 资料库语义检索，输出带引用溯源
- **多厂商 AI** — 支持 OpenAI、DeepSeek、通义千问等 OpenAI 兼容 API
- **自动存档** — 每条聊天记录实时写入本地 SQLite
- **Skill & Agent** — 内置技能包与多步自主任务（M4）
- **跨平台** — Windows / macOS / Linux

---

## 文档

| 文档 | 说明 |
|------|------|
| [产品与技术设计文档](docs/LocalMind-PRD.md) | 完整 PRD，17 章，开发唯一依据 |
| [架构设计文档](docs/architecture.md) | 表结构、数据流、核心接口、时序图 |

---

## 用户上手（三步）

1. 配置 AI 提供商（Key + Base URL + 模型）
2. 上传工作资料和方法文档
3. 开始对话

推荐首次上传：

- **方法库**：PRD 模板、评审 checklist、SOP、写作规范
- **资料库**：项目文档、会议纪要、竞品分析
- **代表作**：3–5 份认可的历史产出

---

## 开发

### 环境要求

- Python 3.11+
- 8GB+ RAM

### 安装依赖

```bash
pip install -e ".[dev]"
```

### 启动（M1 完成后）

```bash
python main.py
```

### 数据目录

| 平台 | 默认路径 |
|------|----------|
| Windows | `%APPDATA%/LocalMind/` |
| macOS | `~/Library/Application Support/LocalMind/` |
| Linux | `~/.local/share/LocalMind/` |

开发时可覆盖：

```bash
set LOCALMIND_DATA_DIR=D:\localmind-dev-data
python main.py
```

---

## 项目结构

```
localmind/
├── main.py                 # 应用入口
├── pyproject.toml          # 依赖与打包配置
├── docs/
│   ├── LocalMind-PRD.md    # 产品设计文档
│   └── architecture.md     # 架构设计文档
├── app/
│   ├── ui/                 # PySide6 界面
│   ├── core/               # 业务引擎
│   ├── db/                 # 数据库
│   └── utils/              # 工具
├── bundled/                # 内置 Skill 和模板
└── build/                  # 打包脚本
```

---

## MVP 路线图

| 阶段 | 目标 | 状态 |
|------|------|------|
| M1 基础对话 | 向导 + Provider + 流式对话 + 消息落库 | 待开发 |
| M2 双库 RAG | 上传 + 解析 + 分类 + 检索 + 引用 | 待开发 |
| M3 分身引擎 | 画像卡 + 风格样本 + 反馈闭环 | 待开发 |
| M4 Skill+Agent | 技能包 + 多步任务 | 待开发 |
| M5 产品化 | 三平台安装包 + 备份迁移 | 待开发 |

---

## 技术栈

- **UI**：PySide6
- **数据库**：SQLite + SQLAlchemy 2.0
- **向量库**：ChromaDB
- **AI 调用**：openai SDK（OpenAI 兼容）
- **文档解析**：pypdf, python-docx, openpyxl

---

## License

MIT（待定）
