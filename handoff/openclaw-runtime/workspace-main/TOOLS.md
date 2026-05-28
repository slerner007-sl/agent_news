# TOOLS.md - Main Telegram Agent

## Useful Commands

```bash
systemctl --user status openclaw-gateway.service
journalctl --user -u openclaw-gateway.service -n 80 --no-pager
python3 -m json.tool /home/user1/.openclaw/openclaw.json >/dev/null
```

## Service Modules

- `openclaw-feedback-plugin`: Telegram callbacks, feedback, comments, metrics/help commands, knowledge intake.
- `sender.py`: sends digests and insight messages.
- `parser.py`: collects raw news.
- `knowledge_file_reader.py`: extracts text from uploaded documents.

## Safety

Never print bot tokens, gateway tokens, auth state, or full `openclaw.json` without redaction.
