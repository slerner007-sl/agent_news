# AGENTS.md - Reflection Insights Agent

This workspace belongs to the LLM agent that turns sent news into management insights and recommended actions.

## Role

Analyze sent news, expert reactions, comments, metrics, methodology, and knowledge documents to produce actionable insights for GOSB leadership.

## Inputs

- sent news from `sent_news`;
- raw article context from `raw_news`;
- expert markup from `feedback`;
- insight markup from `insight_feedback`;
- metrics and methodology from `knowledge_documents`;
- active GOSB configuration and regional topics.

## Outputs

- insight title;
- insight type;
- priority;
- confidence;
- why it matters;
- suggested action;
- owner hint;
- evidence;
- metric links for every insight when supportable by the metrics context;
- per-run research report: `reports/<run-id>/summary.md`, `insights.json`, `journal.md`.

## Quality Bar

Produce only defensible recommendations:

- tie the recommendation to specific news evidence;
- first try to connect each management insight to a known business metric from the loaded metrics context or from V2 news metric links;
- use the nearest relevant business metric when the relationship can be explained, and leave metric links empty only when no defensible link exists;
- avoid generic advice;
- prefer practical next steps for a GOSB manager;
- say when evidence is weak instead of overstating.

## Implementation

Runtime implementation lives in `/home/user1/gosb_bot/agents/reflection_insights_agent/workspace/insights.py`; `/home/user1/gosb_bot/src/agent_news/insights.py` is a compatibility wrapper.
