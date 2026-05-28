# Scripts

Operational entrypoints and maintenance helpers.

- `run_digest_cron.sh` - production cron runner.
- `compare_filters.py`, `compare_sent_v2.py` - diagnostics for legacy vs V2 filtering.
- `setup_regional_gosbs.py` - seed/update regional GOSB configs.
- `send_general_menu.py`, `remove_admin_menu.py` - Telegram menu utilities.
- `bot_info_prompt_card.py` - helper for rendering the bot capability card.

Scripts bootstrap `src/` themselves, so they can be run from the repository root with `python3 scripts/<name>.py`.

