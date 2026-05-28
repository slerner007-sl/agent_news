# Seed Prompt - Reflection Cycle LLM Research

The cycle runner first builds an evidence pack from sent news, saved insights, feedback and metric links.
The LLM reflection agent then writes `summary.md` and `journal.md`.

Required report style:

- `## Короткий вывод`
- `## Что можно сказать по фактам`
- `## Quality sanity`
- `## Ключевые находки`
- `## Причинно-следственные цепочки`
- `## Advisory`
- `## Data gaps`
- `## Rejected hypotheses`
- `## Open questions`

The agent must separate facts from interpretation, keep rejected hypotheses visible, and avoid inventing metrics or feedback.
