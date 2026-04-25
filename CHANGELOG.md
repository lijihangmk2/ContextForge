# Changelog

All notable changes to this project will be documented in this file.

## [1.4.10] - 2026-04-25

### Changed

- Removed `tool` and `mempalace` feature promotion from the public README and PyPI-facing docs while those submodules remain unstable.
- Aligned internal design and development docs to mark `tool` and `mempalace` as temporarily non-public functionality.

## [1.4.9] - 2026-04-19

### Changed

- Updated Codex session startup so users can still choose `N` or `la` even when the current profile has no saved session record.

### Fixed

- Fixed the `la` flow in `ctxforge run` so listing all Codex sessions no longer depends on an existing profile-owned session.

## [1.4.8] - 2026-04-18

### Added

- Added project-level `ctxforge mempalace` commands to enable, inspect, and configure MemPalace integration.
- Added profile-scoped memory preload and MemPalace MCP server injection for new AI sessions.
- Added Claude hook syncing so ctxforge can install managed checkpoint and pre-compact memory save hooks.

### Changed

- Added schema support for project-level MemPalace config and profile memory defaults, including profile migration to schema v7.
- Updated `ctxforge run` to validate MemPalace availability before launch when memory integration is enabled.

## [1.4.7] - 2026-04-07

### Fixed

- Scoped session recovery to the active profile so `continue` and session lists no longer pull sessions from other profiles in the same project.
- Added per-profile `sessions.json` tracking to keep Claude and Codex resume behavior aligned with ctxforge profiles.

### Changed

- Lowered the minimum supported Python version to 3.10.
- Added `tomli` fallback loading and replaced Python 3.11-only `datetime.UTC` usage with 3.10-compatible timezone handling.

## [1.4.6] - 2026-04-01

### Fixed

- Unified saved-session recovery UX for Codex and Claude with `continue / new / list` choices in `ctxforge run`.
- Fixed resumed Codex sessions so both direct continue and list-selected sessions no longer receive new-session greeting prompts.
- Added readable session previews in saved-session lists to make manual selection practical.

## [1.4.5] - 2026-03-21

### Fixed

- Fixed `ctxforge run` for Codex so choosing continue now resumes the real previous Codex session instead of starting a new one.
- Updated Codex session persistence to store the actual Codex session ID discovered after launch, rather than a synthetic UUID.

## [1.4.4] - 2026-03-19

### Fixed

- Updated `CodexRunner` to use Codex CLI's current auto-approve flag: `--dangerously-bypass-approvals-and-sandbox`.
- Updated Codex runner tests to match the new CLI flag.

## [1.4.3] - 2026-03-19

### Changed

- Bumped package version to `1.4.3` for the Codex runner compatibility release.

## [1.4.2] - 2026-03-19

### Added

- Added `usermemo.md` support with schema v6 migration.
- Added scope-restricted `ctx` commands.
