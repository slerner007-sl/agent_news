# Agent News

Поиск потенциала для Управляющего ГОСБ: сбор региональных новостей, LLM-фильтрация, Telegram-дайджесты, обратная связь и управленческие инсайты.

## Project Map

| Path | Purpose |
|---|---|
| `src/agent_news/` | Runtime Python package: parser, filters, database, sender, insights. |
| `scripts/` | Cron entrypoints and manual maintenance/diagnostic scripts. |
| `plugins/openclaw-feedback/` | OpenClaw plugin for Telegram callbacks, feedback, comments and knowledge intake. |
| `agents/` | Reproducible OpenClaw agent workspaces and role instructions. |
| `workspace/` | Main OpenClaw workspace materials, memory and generated planning artifacts. |
| `config/` | Sources, holdings and explicit LLM agent registry. |
| `deploy/` | Deployment examples and systemd helpers. |
| `tests/` | Smoke tests for holdings, run IDs and insight flow. |
| `docs/` | Architecture and operations notes. |
| `changelogs/` | Branch handoff notes, following the OpenClaw dispatcher pattern. |

Compatibility wrappers are kept at `main.py`, `run_digest_cron.sh`, `openclaw-feedback-plugin`, `openclaw_workspace` and `deploy/openclaw-workspaces/*` so existing VPS commands keep working while the repo layout is cleaner.

## Run

```bash
PYTHONPATH=src python3 -m agent_news.main
```

Existing deployment command is still supported:

```bash
python3 main.py
```

Cron uses:

```bash
scripts/run_digest_cron.sh
```

## Verify

```bash
PYTHONPATH=src python3 -m py_compile src/agent_news/*.py scripts/*.py main.py
python3 tests/test_holdings_loader.py
python3 tests/test_run_id.py
python3 tests/test_insights.py
cd plugins/openclaw-feedback && node --experimental-sqlite test.mjs
```
