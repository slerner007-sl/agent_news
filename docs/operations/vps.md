# VPS Operations

Production path:

```text
/home/user1/gosb_bot
```

Current cron-compatible entrypoints:

```bash
/home/user1/gosb_bot/run_digest_cron.sh
/home/user1/gosb_bot/scripts/run_digest_cron.sh
```

The cron script exports `PYTHONPATH=/home/user1/gosb_bot/src` and runs:

```bash
python3 -m agent_news.main
```

