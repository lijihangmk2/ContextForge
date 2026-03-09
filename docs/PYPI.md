# ctxforge

Simple context manager for AI CLI tools.

Define AI work profiles, select key files, and launch your AI CLI with project context injected automatically.

## Install

```bash
pip install ctxforge
```

Requires Python >= 3.11 and at least one AI CLI (e.g. Claude Code, Codex).

## Usage

```bash
ctxforge init          # scan project, create first profile
ctxforge run           # start AI CLI with context
```

## Commands

| Command | Description |
|---------|-------------|
| `ctxforge init` | Initialize project config and profile |
| `ctxforge run [PROFILE]` | Start AI CLI session with context |
| `ctxforge profile create NAME` | Create a new profile |
| `ctxforge profile list` | List all profiles |
| `ctxforge ctx profile` | Show profile configuration |
| `ctxforge ctx files` | List key files with size info |
| `ctxforge ctx update [--all]` | AI updates stale key files |
| `ctxforge ctx compress [--all]` | AI compresses verbose key files |
| `ctxforge tool add NAME` | Register an MCP tool (from registry, GitHub URL, or manually) |
| `ctxforge tool search KEYWORD` | Search the MCP registry |
| `ctxforge tool setup NAME` | Launch AI CLI to install/configure a tool |
| `ctxforge tool list` | List registered tools and status |
| `ctxforge tool check` | Check tool availability |
| `ctxforge tool disable NAME` | Disable a tool for a profile |
| `ctxforge tool enable NAME` | Re-enable a disabled tool |
| `ctxforge tool remove NAME` | Remove a tool from the project |
| `ctxforge clean` | Remove all ctxforge configuration |

## Links

- [GitHub](https://github.com/lijihangmk2/ContextForge)
- [Documentation](https://github.com/lijihangmk2/ContextForge#readme)

## License

MIT
