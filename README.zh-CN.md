# ctxforge

面向 AI CLI 的简洁上下文管理工具。

定义一个 profile，选择关键文件，然后带着项目上下文启动你的 AI CLI。

## 安装

```bash
pip install ctxforge
```

需要 Python >= 3.11，并且本机已安装至少一个 AI CLI（例如 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)）。

## 快速开始（2 步）

```bash
cd your-project/

# 1) 初始化
ctxforge init

# 2) 运行
ctxforge run
```

`ctxforge init` 会创建项目配置和你的第一个 profile。

`ctxforge run` 会加载该 profile，并使用你选择的上下文启动交互式 AI CLI 会话。

## 常用命令

| 命令 | 说明 |
|------|------|
| `ctxforge init [PATH]` | 初始化项目的 ctxforge 配置 |
| `ctxforge run [PROFILE]` | 以指定 profile 启动 AI CLI 会话 |
| `ctxforge profile create NAME` | 创建新 profile |
| `ctxforge profile list` | 列出所有 profile |
| `ctxforge profile show NAME` | 显示 profile 详情 |
| `ctxforge clean [PATH]` | 删除所有 ctxforge 配置 |

## 最小示例

```bash
ctxforge profile create reviewer --desc "Code review" --prompt "You are a code reviewer..."
ctxforge run reviewer
```

## 内置斜杠命令（仅 Claude Code）

当 Claude Code 为当前 CLI 时，ctxforge 会生成 `/project:ctx-*` 斜杠命令：

| 命令 | 说明 |
|------|------|
| `/project:ctx-profile` | 查看当前 profile 配置 |
| `/project:ctx-files` | 列出 key files 及大小信息 |
| `/project:ctx-update` | AI 建议更新 key files |
| `/project:ctx-compress` | AI 压缩冗长的 key files |

这些命令对其他 CLI（如 Codex）不可用。

## 说明

ctxforge 的项目与 profile 配置文件位于 `.ctxforge/` 目录。
你可以按需手动修改这些文件。
手动修改后，请重新执行 `ctxforge run` 以应用最新上下文。

## 许可证
MIT
