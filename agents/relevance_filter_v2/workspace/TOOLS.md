# TOOLS.md - Relevance Filter V2 Agent

## Files

- `/home/user1/gosb_bot/agents/relevance_filter_v2/workspace/llm_filter_v2.py` - prompt and LLM filtering logic.
- `/home/user1/gosb_bot/config/sources.txt` - regional sources.
- `/home/user1/gosb_bot/config/holdings.txt` - client holdings by GOSB.
- `/home/user1/gosb_bot/data/news_bot.db` - raw and filtered news.

## Checks

```bash
cd /home/user1/gosb_bot
PYTHONPATH=/home/user1/gosb_bot/src python3 -m py_compile agents/relevance_filter_v2/workspace/llm_filter_v2.py src/agent_news/llm_filter_v2.py
python3 scripts/compare_filters.py
```

## Notes

Do not send Telegram messages. Sending is handled by `sender.py`.
