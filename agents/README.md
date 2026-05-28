# Agents

OpenClaw agent workspace templates live here. Each agent has a `workspace/` directory with the always-on files (`AGENTS.md`, `IDENTITY.md`, `TOOLS.md`, `HEARTBEAT.md`, `SOUL.md`, `USER.md`) and local memory scaffolding.

Agent-owned runtime code lives inside each agent `workspace/`. `src/agent_news/` keeps compatibility wrappers and shared services used by cron, tests, and Telegram delivery.

