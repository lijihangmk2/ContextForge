# ctxforge

Simple context manager for AI CLI tools.

Define a profile, select key files, then run your AI CLI with project context.

## Installation

```bash
pip install ctxforge
```

Requires Python >= 3.11 and at least one AI CLI installed (for example [Claude Code](https://docs.anthropic.com/en/docs/claude-code)).

## Quick Start (2 steps)

```bash
cd your-project/

# 1) Initialize
ctxforge init

# 2) Run
ctxforge run
```

`ctxforge init` creates the project config and your first profile.

`ctxforge run` loads that profile and starts an interactive AI CLI session with the selected context.

## Common Commands

| Command | Description |
|---------|-------------|
| `ctxforge init [PATH]` | Initialize ctxforge for a project |
| `ctxforge run [PROFILE]` | Start AI CLI session with context |
| `ctxforge profile create NAME` | Create a new profile |
| `ctxforge profile list` | List all profiles |
| `ctxforge profile show NAME` | Show profile details |
| `ctxforge ctx profile [PROFILE]` | Show profile configuration |
| `ctxforge ctx files [PROFILE]` | List key files with size info |
| `ctxforge ctx update [PROFILE] [--all]` | AI updates stale key files |
| `ctxforge ctx compress [PROFILE] [--all]` | AI compresses verbose key files |
| `ctxforge clean [PATH]` | Remove all ctxforge configuration |

## MCP Tool Management

ctxforge can manage MCP (Model Context Protocol) tools for your AI sessions. Registered tools are automatically available to all profiles.

```bash
# Search the MCP registry
ctxforge tool search puppeteer

# Add a tool (auto-fetches config from the MCP registry, launches setup if needed)
ctxforge tool add puppeteer

# Add from a GitHub URL (fetches server.json)
ctxforge tool add https://github.com/anthropics/mcp-server-example

# Add manually
ctxforge tool add my-tool --command npx --args "-y,my-mcp-server"

# Re-run setup for a tool
ctxforge tool setup puppeteer

# List registered tools and status
ctxforge tool list

# Check tool availability
ctxforge tool check

# Disable a tool for a specific profile
ctxforge tool disable puppeteer --profile reviewer

# Re-enable
ctxforge tool enable puppeteer --profile reviewer

# Remove a tool entirely
ctxforge tool remove puppeteer
```

| Command | Description |
|---------|-------------|
| `ctxforge tool search KEYWORD` | Search the MCP registry |
| `ctxforge tool add NAME` | Register a tool (from registry, GitHub URL, or manually) |
| `ctxforge tool setup NAME` | Launch AI CLI to install/configure a tool |
| `ctxforge tool list` | List registered tools and availability |
| `ctxforge tool check [NAME]` | Check tool availability |
| `ctxforge tool enable NAME [-p PROFILE]` | Re-enable a disabled tool for a profile |
| `ctxforge tool disable NAME [-p PROFILE]` | Disable a tool for a specific profile |
| `ctxforge tool remove NAME` | Remove a tool from the project |

## Minimal Example

```bash
ctxforge profile create reviewer --desc "Code review" --prompt "You are a code reviewer..."
ctxforge run reviewer
```

## Built-in Slash Commands (Claude Code only)

When using Claude Code as the active CLI, ctxforge generates `/project:ctx-*` slash commands:

| Command | Description |
|---------|-------------|
| `/project:ctx-profile` | View current profile configuration |
| `/project:ctx-files` | List key files with size info |
| `/project:ctx-update` | AI updates stale key files based on session changes |
| `/project:ctx-compress` | AI compresses verbose key files |

These commands are not available for other CLIs (e.g. Codex).

## Notes

ctxforge stores project and profile config files under `.ctxforge/`.
You can edit those files manually when needed.
After any manual change, run `ctxforge run` again to apply the updated context.

## License
MIT
