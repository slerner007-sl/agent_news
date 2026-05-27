# TOOLS.md - Reflection Insights Agent

## Files

- `/home/user1/gosb_bot/src/agent_news/insights.py` - insight generation and sending logic.
- `/home/user1/gosb_bot/data/news_bot.db` - sent news, feedback, insights and knowledge documents.
- `/home/user1/gosb_bot/plugins/openclaw-feedback` - feedback handling for insight reactions/comments.

## Checks

```bash
cd /home/user1/gosb_bot
PYTHONPATH=/home/user1/gosb_bot/src python3 -m py_compile src/agent_news/insights.py
python3 tests/test_insights.py
```

## Notes

Do not invent metric values. Use loaded metrics and methodology as context, and mark uncertain links as hypotheses.
