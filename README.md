# ctxforge

Simple context manager for AI CLI tools.

Define a profile, select key files, then run your AI CLI with project context.

## Installation

```bash
pip install ctxforge
```

Requires Python >= 3.10 and at least one AI CLI installed (for example [Claude Code](https://docs.anthropic.com/en/docs/claude-code)).

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
| `ctxforge profile edit NAME` | Edit profile name, description, or prompt |
| `ctxforge profile show NAME` | Show profile details |
| `ctxforge ctx profile [PROFILE]` | Show profile configuration |
| `ctxforge ctx files [PROFILE]` | List key files with size info |
| `ctxforge ctx update [PROFILE] [--all]` | AI updates stale key files |
| `ctxforge ctx compress [PROFILE] [--all]` | AI compresses verbose key files |
| `ctxforge cred …` | Manage system-level Claude/Codex credentials |
| `ctxforge clean [PATH]` | Remove all ctxforge configuration |

## Credential Management

`ctxforge cred` is system-level and intentionally separate from project config.
Managed credentials live under `~/.ctxforge/credentials/` and do not modify `.ctxforge/project.toml`.

```bash
ctxforge cred capture --cli claude
ctxforge cred list
ctxforge cred switch dev@example.com --cli claude
ctxforge cred clean
```

Behavior:

- `capture`, `switch`, and `remove` support explicit arguments. `switch` and `remove` also support interactive fallback when arguments are omitted.
- The first `capture` for one CLI runs an onboarding flow.
- When `capture` is called without `NAME`, ctxforge shows a default name derived from the CLI's unique identifier and lets the user rename it before storing.
- If that suggested name already exists, ctxforge keeps prompting for a new name instead of failing immediately.
- `list` shows which managed credential is currently active by comparing live auth files with stored snapshots.
- `clean` removes ctxforge-managed snapshots only. It does not delete the user's live native auth files.
- After `switch`, any currently running Claude/Codex sessions must be restarted.
- Current tracked files are `~/.claude/.credentials.json`, `~/.claude.json`, and `~/.codex/auth.json`.

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
