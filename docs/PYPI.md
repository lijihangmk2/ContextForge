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
| `ctxforge clean` | Remove all ctxforge configuration |

## Links

- [GitHub](https://github.com/lijihangmk2/ContextForge)
- [Documentation](https://github.com/lijihangmk2/ContextForge#readme)

## License

MIT
