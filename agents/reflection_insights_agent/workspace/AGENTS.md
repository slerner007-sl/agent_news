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
- metric links when supportable.

## Quality Bar

Produce only defensible recommendations:

- tie the recommendation to specific news evidence;
- connect to metrics only when the link is explainable;
- avoid generic advice;
- prefer practical next steps for a GOSB manager;
- say when evidence is weak instead of overstating.

## Implementation

Runtime implementation lives in `/home/user1/gosb_bot/src/agent_news/insights.py`.
