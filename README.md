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
| `ctxforge clean [PATH]` | Remove all ctxforge configuration |

## Minimal Example

```bash
ctxforge profile create reviewer --desc "Code review" --prompt "You are a code reviewer..."
ctxforge run reviewer
```

## Notes

ctxforge stores project and profile config files under `.ctxforge/`.
You can edit those files manually when needed.
After any manual change, run `ctxforge run` again to apply the updated context.

## License
MIT
