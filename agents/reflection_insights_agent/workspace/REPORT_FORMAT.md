# REPORT_FORMAT.md - Reflection Report

For every run, the reflection agent can write a report directory under `reports/<run-id>/`.

## Files

- `summary.md` - human-readable research summary for managers and reviewers.
- `insights.json` - machine-readable report with scope, insight cards, feedback, data gaps and weak signals.
- `journal.md` - hypothesis/evidence/decision journal.

## Summary Sections

- Executive Summary
- Run Scope
- Insight Cards
- Metric Hypotheses
- Feedback Themes
- Data Gaps
- Not Promoted To Insight
- Next Actions

## JSON Contract

The report JSON contains:

- `run_id`
- `generated_at`
- `scope.sent_news_total`
- `scope.gosbs`
- `insights[]`
- `feedback.news_counts`
- `feedback.insight_counts`
- `data_gaps[]`
- `not_promoted_to_insight[]`

Reports must not contain secrets, tokens or private transport credentials.

## Cycle Reports

Periodic cycle reports are written under `reports/cycles/<cycle>-<timestamp>/`.

- `summary.md` - human-readable report to send/review.
- `report.json` - machine-readable meta-insights, feedback adjustments and strategic patterns.
- `journal.md` - method, observations, decisions and data gaps.

Strategic cycles may append generated lessons to `memory/runtime_memory.md`; this runtime memory is ignored by git.

## LLM Research Artifacts

Cycle folders now contain both evidence and agent research:

- `report.json` - deterministic evidence pack.
- `insights.json` - structured LLM research output.
- `summary.md` - LLM-written business research report.
- `journal.md` - LLM-written research journal.

## Delivery Bundle

Cycle report folders also mirror the colleague project delivery bundle:

- `report.md` and `report.html`
- `advisories.json`
- `causal_chains.json`
- `confirmed_findings.json`
- `rejected_hypotheses.json`
- `data_requests.md` / `data_requests.json`
- `task_candidates.json`
- `system_improvement_proposals.json`
- `methodology_proposals.md` / `methodology_proposals.json`
- `external_context.json`, `context.json`, `delivery.json`
