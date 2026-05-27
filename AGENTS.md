## Repository Policy

This repository follows the same broad shape as `open_claw_dispatcher`: reproducible agent/workspace configuration at the top level, runtime code isolated from operational state, and one changelog handoff per branch.

### Branch Policy

- Do not push directly to `main` unless the operator explicitly asks for it.
- Use `codex/<task-name>` for Codex changes.
- Never force-push.

### Safe Editing

Avoid committing secrets, local runtime databases, logs, caches or generated private state.

Prefer editing:
- `src/agent_news/`
- `scripts/`
- `plugins/openclaw-feedback/`
- `agents/`
- `config/`
- `deploy/`
- `docs/`
- `tests/`

### Changelog

Every branch should add `changelogs/<branch-suffix>.md` with:

- What
- Where
- Verify
- Issues
- Next

