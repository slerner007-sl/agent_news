# Sanitized OpenClaw Runtime Export

This folder is a portable, secret-free snapshot of `/home/user1/.openclaw` for handoff.

Included:
- redacted `openclaw.json`;
- OpenClaw workspaces and memory;
- flows, tasks, plugins and plugin skills;
- agent model files with auth fields redacted.

Excluded on purpose:
- credentials, identity, devices, telegram runtime state;
- node_modules/npm cache;
- logs, media, completions and session dumps;
- large sqlite/log/runtime files.

The live VPS config backup remains outside git. Replace `<REDACTED>` placeholders with colleague-owned credentials on the target host.
