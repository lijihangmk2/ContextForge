# ctxforge 设计文档 v6

> 注：`tool` 与 `mempalace` 子模块目前存在已知问题，公开文档暂不作为主推能力；本设计文档保留实现层信息，供后续修复时参考。

## 一句话定位

ctxforge 是 AI 角色矩阵上下文管理器 — 定义 AI 工作角色，向任何 AI CLI 注入项目上下文。

## 核心理念

1. **角色即配置** — 每个 AI 工作场景是一个 Profile，有独立的角色提示词、关键文件、注入策略
2. **透明代理** — ctxforge 包装上下文后启动实际 AI CLI，用户无感知
3. **上下文可控** — 用户显式选择哪些文件作为 AI 的知识输入，不做黑盒推断

---

# 第一部分：配置规范

## 目录结构

```
.ctxforge/                              # ctxforge 配置根目录
├── project.toml                        # [必须] 项目级配置
│
└── profiles/                           # [必须] AI 角色目录
    ├── default/
    │   ├── profile.toml                # 默认角色配置
    │   ├── journal.md                  # [work_record] 工作日志
    │   └── pitfalls.md                 # [work_record] 踩坑记录
    ├── architect/
    │   └── profile.toml
    └── reviewer/
        └── profile.toml

.claude/commands/                       # [自动生成] Claude Code 自定义命令
├── ctx-profile.md                      # /project:ctx-profile
├── ctx-files.md                        # /project:ctx-files
├── ctx-update.md                       # /project:ctx-update
└── ctx-compress.md                     # /project:ctx-compress

~/.ctxforge/credentials/                # [系统级] 凭证托管仓库（与 project 解耦）
├── manifest.json                       # 已托管凭证索引 / 当前选中项
├── claude/
│   └── <name>/...
└── codex/
    └── <name>/...
```

## project.toml Schema

`ctxforge cred` 不写入 `project.toml`。凭证切换是系统级能力，独立存储在 `~/.ctxforge/credentials/`。

```toml
schema_version = 2

[project]
name = "my-app"                         # 项目名称（auto-detected）
description = ""                        # 项目描述（可选）

[cli]
detected = ["claude", "codex"]          # 静态检测到的 AI CLI
active = "claude"                       # legacy — 已迁移到 profile 级别，保留用于迁移

[defaults]
language = "Chinese"                    # 输出语言偏好
model = ""                              # LLM 模型（可选，预留）

[mempalace]
enabled = false                         # 是否启用项目级 MemPalace
palace_path = ""                        # 为空时默认 .ctxforge/memory/mempalace
autoload = true                         # 保留位；当前主要影响状态展示
checkpoint_interval = 1                 # Claude checkpoint hook 间隔
save_on_precompact = true               # Claude PreCompact hook 是否启用

[tools.browser-puppet]                  # MCP 工具注册表
description = "Browser automation"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-puppeteer"]
env = []
setup = "npm install -g @modelcontextprotocol/server-puppeteer"
```

### Pydantic 模型

```python
class ProjectSection(BaseModel):
    name: str = ""
    description: str = ""

class CliConfig(BaseModel):
    detected: list[str] = []
    active: str | None = None  # legacy — now per-profile; kept for migration

class DefaultsConfig(BaseModel):
    language: str | None = None
    model: str | None = None

class ToolDefinition(BaseModel):
    description: str = ""
    command: str
    args: list[str] = []
    env: list[str] = []
    setup: str = ""

class MempalaceSection(BaseModel):
    enabled: bool = False
    palace_path: str = ""
    autoload: bool = True
    checkpoint_interval: int = 1
    save_on_precompact: bool = True

class ProjectConfig(BaseModel):
    schema_version: int = 2
    project: ProjectSection
    cli: CliConfig
    defaults: DefaultsConfig
    tools: dict[str, ToolDefinition] = {}
    mempalace: MempalaceSection
```

## profile.toml Schema

每个角色一个目录，内含 `profile.toml` 和 work record 文件。

```toml
schema_version = 5                      # 配置版本（自动迁移）

[profile]
name = "default"                        # 角色名（required）
description = "通用开发助手"             # 角色描述

[role]
prompt = "你是一个资深后端开发工程师..."   # 角色系统提示词

[work_record.files]                     # AI 工作记录文件（相对于 profile 目录）
"journal.md" = "work journal — completed tasks, in-progress, TODOs"
"pitfalls.md" = "pitfalls — gotchas, lessons learned, warnings"

[key_files]
paths = [                               # 注入的关键文件（相对于项目根）
    "README.md",
    "design/DESIGN.md",
    "src/main.py",
]

[injection]
strategy = "simple"                     # 注入策略（v1 仅 simple）
order = "role_first"                    # "role_first" | "files_first"
greeting = true                         # 启动时 AI 确认上下文已加载

[cli]
name = "claude"                         # 此 profile 使用的 CLI
auto_approve = false                    # 跳过权限确认

[budget]
max_tokens = 24000                      # token 预算上限（预留）

[enhancers]
enabled = []                            # 启用的增强器（预留）

[tools]
disabled = []                           # 排除的 MCP 工具（默认所有项目工具可用）

[memory]
provider = "mempalace"                  # 预留/迁移字段；当前 run 不读取此段
enabled = false
scope = "profile"
namespace = ""
palace_path = ""
autoload = true
save_on_checkpoint = true
checkpoint_interval = 15
save_on_precompact = true
save_on_exit = false
cross_profile_search = false
```

### Pydantic 模型

```python
class ProfileSection(BaseModel):
    name: str                           # required
    description: str = ""

class RoleSection(BaseModel):
    prompt: str = ""

class WorkRecordSection(BaseModel):
    files: dict[str, str] = DEFAULT_WORK_RECORD  # filename → description

class KeyFilesSection(BaseModel):
    paths: list[str] = []

class InjectionSection(BaseModel):
    strategy: str = "simple"
    order: str = "role_first"
    greeting: bool = True

class ProfileCliSection(BaseModel):
    name: str | None = None             # "claude" | "codex"
    auto_approve: bool = False

class BudgetSection(BaseModel):
    max_tokens: int = 24000

class EnhancersSection(BaseModel):
    enabled: list[str] = []

class ToolsSection(BaseModel):
    disabled: list[str] = []             # opt-out: all project tools active by default

class MemorySection(BaseModel):
    provider: str = "mempalace"
    enabled: bool = False
    scope: str = "profile"
    namespace: str = ""
    palace_path: str = ""
    autoload: bool = True
    save_on_checkpoint: bool = True
    checkpoint_interval: int = 15
    save_on_precompact: bool = True
    save_on_exit: bool = False
    cross_profile_search: bool = False

class ProfileConfig(BaseModel):
    schema_version: int = 1
    profile: ProfileSection
    role: RoleSection
    work_record: WorkRecordSection
    key_files: KeyFilesSection
    injection: InjectionSection
    cli: ProfileCliSection
    budget: BudgetSection
    enhancers: EnhancersSection
    tools: ToolsSection
    memory: MemorySection
```

### MemPalace 当前设计状态

- **真实启用开关在 project.toml 的 `[mempalace]`**。`ctxforge run` 目前从项目级配置解析 palace path、namespace binding 和 checkpoint interval。
- `profile.toml` 中的 `[memory]` 仍保留在 schema 中，主要用于兼容和后续设计；**当前 `run` 主流程不读取它**。
- 新会话时，ctxforge 会：
  1. 追加 `[Memory Namespace]` 指令到 system prompt
  2. 尝试用 `mempalace search` 预加载该 profile 的历史记忆
  3. 为 MCP config 附加 MemPalace server 定义
- 自动保存目前只在 **Claude** 路径落地，通过 `.claude/settings.local.json` 写入 `Stop` / `PreCompact` hooks。
- **Codex 支持未闭环**：当前 `CodexRunner` 不透传 `mcp_config`，也没有等效的自动 checkpoint hook。
- 新增 `ctxforge mempalace debug [PROFILE]` 和 `ctxforge run --debug-memory` 用于追踪 runtime、hook、preload、palace 目录和 CLI 支持差异。

---

# 第二部分：CLI 实现

## 运作流程

```
┌──────┐               ┌──────────────────────────┐              ┌──────────┐
│      │  ctxforge run  │         ctxforge          │  系统提示    │          │
│ 用户 │ ────────────→ │                           │ ───────────→ │  AI CLI  │
│      │               │  1. 加载 project.toml      │              │ (claude) │
│      │               │  2. 解析 Profile           │              │          │
│      │  交互式会话    │  3. 读取 key files         │  交互式会话  │          │
│      │ ←───────────→ │  4. 构建系统提示           │ ←──────────→ │          │
│      │               │  5. 同步 slash commands    │              │          │
│      │               │  6. 启动 AI CLI            │              │          │
└──────┘               └──────────────────────────┘              └──────────┘
                             ↕ 读取
                       ┌────────────┐
                       │ .ctxforge/ │
                       │  profiles  │
                       └────────────┘
```

## 命令清单

| 命令 | 作用 |
|------|------|
| `ctxforge init [PATH]` | 扫描项目，交互式创建 .ctxforge/ 和首个 Profile |
| `ctxforge run [PROFILE] [--debug-memory]` | 加载 Profile 上下文，启动 AI CLI 交互式会话 |
| `ctxforge profile create NAME` | 创建新角色 |
| `ctxforge profile list` | 列出所有角色 |
| `ctxforge profile show NAME` | 显示角色详情 |
| `ctxforge ctx profile [PROFILE]` | 显示 profile 配置详情 |
| `ctxforge ctx files [PROFILE]` | 列出 key files 及大小 |
| `ctxforge ctx update [PROFILE] [--all]` | AI 更新过时的 key files |
| `ctxforge ctx compress [PROFILE] [--all]` | AI 压缩冗余 key files |
| `ctxforge tool search KEYWORD` | 搜索 MCP Registry |
| `ctxforge tool add NAME` | 注册 MCP 工具（Registry / GitHub URL / 手动） |
| `ctxforge tool setup NAME` | 启动 AI CLI 安装配置工具 |
| `ctxforge tool list` | 列出所有已注册工具及可用状态 |
| `ctxforge tool remove NAME` | 从 project.toml 删除工具 |
| `ctxforge tool check [NAME]` | 检查工具可用性（command + env） |
| `ctxforge tool enable NAME [-p PROFILE]` | 重新启用被排除的工具 |
| `ctxforge tool disable NAME [-p PROFILE]` | 为 profile 排除工具 |
| `ctxforge mempalace enable/status/disable/set interval/debug` | 管理并诊断 MemPalace |
| `ctxforge clean [PATH]` | 删除 .ctxforge/ 和生成的 slash commands |

### 1. ctxforge init

```
ctxforge init [path]
    │
    ▼
[阶段 1] 静态分析
    ├── 扫描目录树（排除 node_modules/.venv/.git 等）
    ├── 检测语言（文件扩展名统计，≥2 个文件才认定）
    ├── 识别配置文件（pyproject.toml, package.json, go.mod 等）
    └── 检测可用 AI CLI（shutil.which: claude, codex, aider, copilot, q, goose）
    │
    ▼
[阶段 2] 用户交互
    ├── 展示检测结果（语言、配置文件）
    ├── 选择默认 CLI（单个则自动选定）
    ├── 选择输出语言
    ├── 检测文档候选文件 → 交互式 checkbox 选择 key files
    │     ├── 每个候选文件标注预估 token 数
    │     ├── 默认不选中，用户手动勾选
    │     ├── checkbox 后可粘贴自定义文件路径（仅文件，不允许目录）
    │     └── 选完后展示汇总，超预算则提示重选
    └── 输入 Profile 名称和描述
    │
    ▼
[阶段 3] 写入配置
    ├── 创建 .ctxforge/project.toml
    ├── 创建 .ctxforge/profiles/<name>/profile.toml
    └── 生成 .claude/commands/ctx-*.md（slash commands）
```

reinit 行为：若 .ctxforge/ 已存在且有 Profile，提示是否创建新 Profile 还是只更新 project.toml。

### 2. ctxforge run

```bash
ctxforge run                  # 使用默认 Profile
ctxforge run architect        # 指定 Profile
```

流程：
```
ctxforge run [profile_name]
    │
    ▼
加载 project.toml
    │
    ▼
解析 Profile（显式指定 > 唯一 Profile > 报错）
    │
    ▼
迁移检查（schema_version < CURRENT → 交互式升级 → 写回）
    │
    ▼
构建系统提示 (SimpleInjection.build_system):
    ├── [Role: name] + role.prompt     ← 角色提示词
    ├── [Work Record]                   ← work_record.files 路径引用
    ├── [Key Files]                     ← key_files.paths 路径引用
    └── [Language]                      ← defaults.language
    │
    注入顺序由 injection.order 控制:
    ├── role_first: Role → Work Record → Key Files → Language
    └── files_first: Key Files → Work Record → Role → Language
    │
    ▼
构建 Greeting (SimpleInjection.build_greeting):
    └── 首条消息，请 AI 确认已加载的角色和文件
    │
    ▼
解析工具链 (toolchain.resolve_tools):
    ├── 取 project.tools 全部工具，减去 profile.tools.disabled
    ├── 检查 command 可用性 + env 变量
    ├── 可用工具 → 生成临时 MCP config JSON
    └── 可用工具描述 → 追加到 system prompt [Available MCP Tools]
    │
    ▼
同步 slash commands (.claude/commands/ctx-*.md)
    │
    ▼
打印注入摘要（角色、文件数、字符数、工具状态）
    │
    ▼
调用 Runner（ClaudeRunner）:
    claude --session-id <uuid> --mcp-config <mcp.json> --append-system-prompt "<系统提示>" "<greeting>"
    │   （每次生成新 UUID，确保跨 profile 会话隔离）
    │
    ▼
进入交互式会话（用户直接与 AI CLI 交互）
```

注入后的系统提示示例：
```
[Role: architect]
你是一个资深系统架构师，擅长分析代码结构和设计模式...

[Work Record]
IMPORTANT: Read these files first. They contain the AI's working memory for this profile and take priority over key files:
- .ctxforge/profiles/architect/journal.md  (work journal)
- .ctxforge/profiles/architect/pitfalls.md  (pitfalls)

[Key Files]
Read the following files to understand the project context:
- README.md
- src/main.py

[Language]
Please respond in Chinese.
```

### 3. ctxforge profile

```bash
ctxforge profile list                              # 列出所有角色
ctxforge profile create reviewer --desc "代码审查" --prompt "..." --files "src/main.py"
ctxforge profile show default                      # 显示角色详情
```

### 4. ctxforge clean

```bash
ctxforge clean          # 确认后删除 .ctxforge/ + .claude/commands/ctx-*.md
```

删除 `.ctxforge/` 目录后，额外清理 `.claude/commands/` 下由 ctxforge 生成的 4 个命令文件，不影响用户自己的 slash commands。

### 5. ctxforge ctx

从 bash 直接执行上下文维护操作（等同于 Claude Code 会话内的 slash commands）。

```bash
ctxforge ctx profile [PROFILE]              # 显示 profile 配置（纯 Python）
ctxforge ctx files   [PROFILE]              # 列出 key files 及大小（纯 Python）
ctxforge ctx update  [PROFILE] [--all]      # AI 更新过时的 key files
ctxforge ctx compress [PROFILE] [--all]     # AI 压缩冗余 key files
```

Profile 解析逻辑（4 个命令通用）：
- 显式指定 PROFILE → 使用该 profile
- 单 profile 项目 → 自动选择
- 多 profile 且未指定 → questionary 交互选择

update/compress 额外逻辑：
- 多 profile 交互选择时，增加 "* all" 选项
- `--all` 标志 → 遍历所有 profiles，逐个调用项目 active CLI 的 `run_oneshot`

`ctx profile` / `ctx files` 为纯 Python 输出，无需 AI CLI。`ctx update` / `ctx compress` 构建 prompt 后调用 AI CLI 非交互模式（`claude -p` / `codex`）。

### 6. Slash Commands（仅 Claude Code）

仅当 `cli.active` 为 `"claude"` 时，`ctxforge init` 和 `ctxforge run` 会在 `.claude/commands/` 下生成/同步命令文件。其他 CLI（如 Codex）不生成。

用户在 Claude Code 会话中可通过 `/project:ctx-*` 触发：

| 命令 | 功能 |
|------|------|
| `/project:ctx-profile` | 读取并展示当前 profile 配置 |
| `/project:ctx-files` | 列出 key files 及存在状态和大小 |
| `/project:ctx-update` | AI 根据当前 session 变更，更新过时的 key files 内容 |
| `/project:ctx-compress` | AI 读取 key files 内容，分析并压缩冗余信息 |

命令内容中嵌入当前 profile 的路径（如 `.ctxforge/profiles/default/profile.toml`），支持 `$ARGUMENTS` 传参。

---

## 技术方案

| 组件 | 选型 | 理由 |
|------|------|------|
| CLI 框架 | typer | 现代 Python CLI，类型提示友好 |
| 配置格式 | TOML (tomllib/tomli + tomli-w) | 人类可读，兼容 Python 3.10+ |
| 数据模型 | Pydantic v2 | 校验 + 序列化 |
| 交互 UI | questionary + rich | checkbox 选择 + 美化输出 |
| CLI 包装 | subprocess | 跨平台，不用 pty |
| 进程标题 | setproctitle | 终端 tab 显示 "ctxforge" 而非 "python" |
| 构建后端 | hatchling | 轻量，纯 PEP 621 |

---

## 异常体系

```
CForgeError                 # 基类
├── ProjectNotFoundError    # .ctxforge/ 未找到
├── InvalidProjectError     # project.toml 格式错误
├── ProfileNotFoundError    # 角色不存在
├── InvalidProfileError     # profile.toml 无效
├── CliNotFoundError        # Runner 未注册
└── RunnerError             # Runner 执行失败
```

---

## 未来扩展方向

- **更多 Runner**: aider, copilot 等 AI CLI 的 runner 实现
- **Codex slash commands**: Codex 目前无自定义命令机制，待其支持后适配
- **Enhancer 插件**: git-enhancer（附带 git log/diff）、migration-enhancer 等
- **语义匹配**: 基于 embedding 的上下文选择（替代手动 key_files）
- **token 预算控制**: 根据 budget.max_tokens 自动裁剪注入内容
- **LLM 驱动 init**: 用 LLM 分析项目自动生成角色提示词和推荐 key files
- **MCP 服务器**: 作为 MCP server 被 AI 工具直接调用
- **团队共享**: .ctxforge/ 进版本控制，团队共享角色配置
