# ctxforge 开发计划 v4

## 工程原则

1. **每个能力必须是独立模块** — 单向依赖，模块可独立测试
2. **CLI 层只做编排** — 业务逻辑在 core/，IO 在 storage/
3. **所有"智能"能力都可替换** — injection / runner / enhancer 均为 Protocol
4. **渐进增强** — 核心功能无外部服务依赖

---

## 源码架构

```
src/ctxforge/
├── __init__.py
├── __main__.py                  # python -m ctxforge
├── __version__.py               # 版本号
├── exceptions.py                # 异常体系
│
├── console/                     # CLI 层
│   ├── application.py           # typer app + 命令注册
│   └── commands/
│       ├── init.py              # ctxforge init
│       ├── run.py               # ctxforge run
│       ├── profile.py           # ctxforge profile {create,list,show}
│       ├── ctx.py               # ctxforge ctx {profile,files,update,compress}
│       ├── tool.py              # ctxforge tool {search,add,setup,list,remove,check,enable,disable}
│       └── clean.py             # ctxforge clean
│
├── spec/                        # 配置模型 + 加载
│   ├── schema.py                # Pydantic 模型 (ProjectConfig + ProfileConfig)
│   └── loader.py                # TOML 加载 + 校验
│
├── core/                        # 核心业务逻辑
│   ├── project.py               # Project 类（定位 .ctxforge/，加载配置）
│   ├── profile.py               # ProfileManager（CRUD 操作）
│   ├── migration.py             # Schema 迁移（版本检测 + 交互式升级）
│   ├── injection.py             # SimpleInjection（上下文注入 + greeting）
│   ├── prompt_builder.py        # PromptBuilder（高级 API）
│   ├── toolchain.py             # 工具可用性检查 + MCP 配置生成
│   └── registry.py              # MCP Registry API 客户端（搜索 + GitHub URL 解析）
│
├── analysis/                    # 静态分析
│   ├── scanner.py               # 目录扫描 + 语言检测 + 配置文件识别
│   ├── lang_detector.py         # 文件扩展名 → 语言检测（21 种）
│   ├── cli_detector.py          # shutil.which() 检测 AI CLI（6 种）
│   └── doc_detector.py          # 文档候选文件检测（仅文件，不含目录）
│
├── runner/                      # AI CLI 包装
│   ├── base.py                  # CliRunner Protocol + RunResult (run + run_oneshot)
│   ├── claude.py                # ClaudeRunner (--append-system-prompt / -p)
│   ├── codex.py                 # CodexRunner (上下文合并到 prompt)
│   └── registry.py              # Runner 注册表
│
├── storage/                     # 文件写入
│   ├── project_writer.py        # 写 project.toml
│   ├── profile_writer.py        # 写 profile.toml
│   └── commands_writer.py       # 生成 .claude/commands/ctx-*.md
│
└── llm/                         # LLM SDK 集成（可选，非主流程）
    ├── provider.py              # 多 provider 调度 (OpenAI/Anthropic/Google)
    ├── client.py                # LLM 分析客户端
    └── cli_fallback.py          # SDK 不可用时的 CLI 回退
```

依赖方向（单向）：

```
console/ → core/ → spec/
           core/ → storage/
console/ → analysis/
console/ → runner/
console/ → storage/   (commands_writer)
llm/（独立，不被主流程依赖）
```

---

## 阶段划分与完成状态

### P0：核心骨架 ✅ 已完成

> 目标：ctxforge 能跑起来，init + run 闭环

#### P0.1 项目骨架 ✅
- [x] hatchling 构建，pyproject.toml 配置
- [x] src layout 目录结构
- [x] typer CLI 框架 + 命令注册
- [x] `ctxforge --version` 可用
- [x] 异常体系定义

#### P0.2 配置模型 ✅
- [x] `spec/schema.py`：Pydantic v2 定义 ProjectConfig + ProfileConfig
- [x] `spec/loader.py`：TOML 加载 + 校验（load_project / load_profile）
- [x] 区分 required / optional 字段

#### P0.3 静态分析 ✅
- [x] `analysis/scanner.py`：目录扫描（支持 exclude_patterns）
- [x] `analysis/lang_detector.py`：文件扩展名统计（21 种语言）
- [x] `analysis/cli_detector.py`：检测 claude/codex/aider/copilot/q/goose
- [x] `analysis/doc_detector.py`：文档候选检测（仅文件，不含目录和配置文件）

#### P0.4 存储层 ✅
- [x] `storage/project_writer.py`：写 project.toml（自动清理空值）
- [x] `storage/profile_writer.py`：写 profile.toml
- [x] `storage/commands_writer.py`：生成 .claude/commands/ctx-*.md（4 个命令）

#### P0.5 核心逻辑 ✅
- [x] `core/project.py`：Project.load() 向上查找 .ctxforge/
- [x] `core/profile.py`：ProfileManager（list/exists/load/create/resolve）
- [x] `core/migration.py`：Schema 迁移框架（v1→v2 CLI下沉、v2→v3 work_record、v3→v4 tools、v4→v5 tools disabled）
- [x] `core/injection.py`：SimpleInjection（build / build_system / build_greeting）
- [x] `core/prompt_builder.py`：PromptBuilder 高级 API
- [x] `core/toolchain.py`：工具可用性检查 + MCP config JSON 生成
- [x] `core/registry.py`：MCP Registry API 搜索 + GitHub server.json 解析

#### P0.6 Runner ✅
- [x] `runner/base.py`：CliRunner Protocol + RunResult
- [x] `runner/claude.py`：ClaudeRunner（--session-id 隔离 + --append-system-prompt + initial_prompt）
- [x] `runner/registry.py`：Runner 注册表

#### P0.7 CLI 命令 ✅
- [x] `init`：扫描 → 检测 CLI → checkbox 选 key files（token 预估 + 自定义路径）→ 创建 Profile → 写配置 → 生成 slash commands
- [x] `run`：加载 Project → 解析 Profile → 构建系统提示 → 构建 greeting → 同步 slash commands → 打印注入摘要 → 启动 Runner
- [x] `profile list/create/show`
- [x] `clean`：确认后删除 .ctxforge/ + 清理 .claude/commands/ctx-*.md
- [x] `ctx profile/files`：纯 Python 显示 profile 配置和 key files 大小
- [x] `ctx update/compress [--all]`：AI 非交互模式维护 key files（run_oneshot）
- [x] `tool search/add/setup/list/check/remove/enable/disable`：MCP 工具全生命周期管理
- [x] MCP Registry 集成：搜索 + GitHub URL 导入 + 自动 setup
- [x] 工具默认全 profile 可用（disabled 排除模型），可用工具自动注入 system prompt

**验收**：`ctxforge init` + `ctxforge run` 闭环可用，schema_version 自动迁移 ✅

---

### P1：体验优化 🔲 未开始

> 目标：提升日常使用的便利性

- [ ] **run --cli 参数**：临时切换 AI CLI
- [ ] **run --verbose**：打印完整系统提示（调试用）
- [ ] **profile edit**：交互式编辑现有 Profile
- [ ] **profile delete**：删除 Profile
- [ ] **init --non-interactive**：非交互模式，用默认值

---

### P2：更多 Runner ⏳ 部分完成

> 目标：支持主流 AI CLI

- [x] `runner/codex.py`：Codex CLI 封装（run + run_oneshot）
- [ ] `runner/aider.py`：Aider CLI 封装
- [ ] Codex slash commands：Codex 目前无自定义命令机制，slash commands 仅对 Claude 生效，待 Codex 支持后适配

---

### P3：LLM 驱动 init 🔲 未开始

> 目标：init 可选用 LLM 自动分析项目，生成更智能的 Profile

- [ ] 串联 `llm/` 模块到 init 流程
- [ ] LLM 推荐 key files
- [ ] LLM 生成角色提示词
- [ ] LLM 生成项目描述
- [ ] `ctxforge init --ai`：启用 LLM 分析（默认关闭）

---

### P4：Enhancer 插件 🔲 未开始

> 目标：可选的上下文增强能力

- [ ] Enhancer Protocol 定义
- [ ] `git-enhancer`：附带 git log / diff / branch 信息
- [ ] enhancer 注册/启用/禁用机制

---

### P5：高级功能 🔲 未开始

> 目标：精细化控制

- [ ] token 预算控制：根据 budget.max_tokens 裁剪注入内容
- [ ] 依赖解析器（dep_parser）：从 pyproject.toml/package.json 提取框架信息
- [ ] 语义匹配：embedding 驱动的上下文选择
- [ ] MCP 服务器模式

---

## 阶段总览

| 阶段 | 目标 | 依赖 LLM | 状态 | 核心产出 |
|------|------|----------|------|----------|
| P0 | 核心骨架 | -- | ✅ 完成 | init + run + ctx + tool 闭环，218 tests |
| P1 | 体验优化 | -- | 🔲 未开始 | 便利参数、profile 管理 |
| P2 | 更多 Runner | -- | 🔲 未开始 | codex/aider 支持 |
| P3 | LLM init | 可选 | 🔲 未开始 | 智能 Profile 生成 |
| P4 | Enhancer | -- | 🔲 未开始 | 上下文增强插件 |
| P5 | 高级功能 | 可选 | 🔲 未开始 | token 预算、语义匹配 |

P0 完成 = **最小可用产品** ✅
P0 ~ P2 完成 = 多 CLI 支持
P0 ~ P4 完成 = 插件生态
P0 ~ P5 完成 = **v1.0 发布**

---

## 质量指标

- 219 tests passing
- ruff clean (E/F/I/UP rules)
- mypy strict clean
- 依赖方向单向，无循环
