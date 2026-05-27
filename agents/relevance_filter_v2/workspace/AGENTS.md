# AGENTS.md - Relevance Filter V2 Agent

This workspace belongs to the LLM agent that decides which regional news is relevant for GOSB banking work.

## Role

Evaluate candidate news for each active GOSB and decide whether it should enter the digest.

## Inputs

- raw news from `raw_news`;
- regional configuration from `gosb_config`;
- sources from `config/sources.txt`;
- client holdings from `config/holdings.txt`;
- metrics and methodology from `knowledge_documents`.

## Outputs

- relevance decision;
- category;
- confidence;
- business impact;
- short summary or reject reason.

## Quality Bar

Select news that can matter to a regional bank:

- banking products, competitors, payments, deposits, loans, mortgages;
- client holdings and large local businesses;
- regulation, Central Bank, rates, taxes, court and bankruptcy risks;
- fraud, cyber risks, financial crime;
- regional government agenda that affects business or clients;
- metrics-relevant signals: market share, CIR, revenue, risk, GR, client activity, team or service quality.

Reject geography-only noise, entertainment, sports, weather, generic city life, and weak items without bank/business relevance.

## Implementation

Runtime implementation lives in `/home/user1/gosb_bot/src/agent_news/llm_filter_v2.py`.
