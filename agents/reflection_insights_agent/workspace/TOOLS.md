# TOOLS.md - Reflection Insights Agent

## Files

- `/home/user1/gosb_bot/agents/reflection_insights_agent/workspace/insights.py` - insight generation, report writing and sending logic.
- `/home/user1/gosb_bot/agents/reflection_insights_agent/workspace/REFLECTION_PROTOCOL.md` - research protocol.
- `/home/user1/gosb_bot/agents/reflection_insights_agent/workspace/REPORT_FORMAT.md` - report artifact contract.
- `/home/user1/gosb_bot/data/news_bot.db` - sent news, feedback, insights and knowledge documents.
- `/home/user1/gosb_bot/plugins/openclaw-feedback` - feedback handling for insight reactions/comments.

## Checks

```bash
cd /home/user1/gosb_bot
PYTHONPATH=/home/user1/gosb_bot/src python3 -m py_compile agents/reflection_insights_agent/workspace/insights.py src/agent_news/insights.py
python3 tests/test_insights.py
```

## Notes

Do not invent metric values. Use loaded metrics and methodology as context, and mark uncertain links as hypotheses.

## Reflection Cycles

```bash
cd /home/user1/gosb_bot
PYTHONPATH=/home/user1/gosb_bot/src python3 -m agent_news.reflection_cycles --cycle weekly
PYTHONPATH=/home/user1/gosb_bot/src python3 -m agent_news.reflection_cycles --cycle strategic --no-memory-update
```

Cron entrypoint: `/home/user1/gosb_bot/scripts/run_reflection_cycle.sh weekly|strategic`.
Set `REFLECTION_REPORT_CHAT_ID` and optionally `REFLECTION_REPORT_THREAD_ID` to send reports to Telegram.
