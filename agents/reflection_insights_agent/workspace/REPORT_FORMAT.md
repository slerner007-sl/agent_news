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
