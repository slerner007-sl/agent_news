# Project Structure

The repository is organized after the `open_claw_dispatcher` pattern:

- `agents/` stores reproducible OpenClaw agent workspaces and role files.
- `workspace/` stores the main OpenClaw workspace materials.
- `src/agent_news/` contains the Python application package.
- `plugins/openclaw-feedback/` contains the OpenClaw Telegram feedback plugin.
- `scripts/` contains cron and manual operational entrypoints.
- `config/` contains operator-editable registries and source lists.
- `deploy/` contains examples and host integration files.
- `tests/` contains smoke checks.
- `changelogs/` contains branch handoff notes.

Compatibility wrappers remain in the old root paths so existing VPS automation can keep running during the transition.

