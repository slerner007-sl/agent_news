# Handoff Package

This branch contains the runnable project plus transfer assets for a colleague.

Included in git:
- `src/agent_news/` runtime code;
- `config/` source and holdings config;
- `data/` SQLite databases, collected news, insights/feedback state and bot card asset;
- `workspace/`, `agents/`, `plugins/` project-side OpenClaw structure;
- `handoff/openclaw-runtime/` sanitized export of `/home/user1/.openclaw`.

Not included:
- passwords, Telegram bot token, gateway tokens, API keys, device/identity credentials;
- OpenClaw `npm/node_modules`, logs, media, session dumps and caches.

To run on a new host, restore credentials into that host-owned OpenClaw config and replace `<REDACTED>` placeholders in `handoff/openclaw-runtime/openclaw.json` before using it as a live config.
