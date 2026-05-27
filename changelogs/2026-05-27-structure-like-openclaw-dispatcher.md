# Structure Like OpenClaw Dispatcher

**Branch:** `codex/2026-05-27-structure-like-openclaw-dispatcher`
**Author:** codex
**Date:** 2026-05-27
**Status:** ready

## What

Reorganized the project into a dispatcher-style structure with clear runtime package, scripts, plugins, agents, workspace, docs, tests and changelog areas.

## Where

- `src/agent_news/` - Python runtime package.
- `scripts/` - cron/manual scripts.
- `plugins/openclaw-feedback/` - OpenClaw plugin.
- `agents/` - OpenClaw agent workspace templates.
- `workspace/` - main workspace materials.
- `main.py`, `run_digest_cron.sh`, `openclaw-feedback-plugin`, `openclaw_workspace`, `deploy/openclaw-workspaces/*` - compatibility entrypoints.

## Verify

- `PYTHONPATH=src python3 -m py_compile src/agent_news/*.py scripts/*.py main.py`
- `python3 tests/test_holdings_loader.py`
- `python3 tests/test_run_id.py`
- `python3 tests/test_insights.py`
- `cd plugins/openclaw-feedback && node --experimental-sqlite test.mjs`

## Issues

The referenced `open_claw_dispatcher` repository is private, so the structure was inspected through the VPS GitHub token rather than public GitHub API.

## Next

Review the branch and merge after confirming the VPS cron/OpenClaw paths are acceptable.
