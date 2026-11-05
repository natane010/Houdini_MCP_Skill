# Claude Code project notes

Follow the shared Houdini workflow in [AGENTS.md](AGENTS.md). For focused Houdini tasks, use the matching project skill from `.claude/skills/` when present and invoke it with `/skill-name`.

When tuning existing nodes, inspect their current parameters and wiring first, keep the change minimal, and record before/after evidence. Use the project JSONL journal for requested cross-chat continuity; it is not Claude's automatic memory. Recheck the live Houdini scene before resuming from historical records.

This repo's Claude Code MCP server is project-scoped in `.mcp.json`; review and approve the project server in Claude Code when prompted. The integration helper is dry-run by default; only `--apply` writes project settings and copies skill folders. It does not configure Claude Desktop or cloud/browser sessions.
