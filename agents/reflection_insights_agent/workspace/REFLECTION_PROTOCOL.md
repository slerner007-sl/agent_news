# REFLECTION_PROTOCOL.md - Reflection Insights Agent

This agent is a research layer over the news pipeline. It does not operate Telegram runtime by itself; it turns sent news, feedback, metrics and methodology into evidence-backed management reflection.

## Research Loop

1. Form a hypothesis from sent news: client signal, risk, LPR/GR, competitor, metric context or no action.
2. Check evidence: raw article, sent summary, classifier context, expert reactions, known metrics and methodology documents.
3. Decide whether the signal becomes an insight card, a weak/rejected signal, or a data gap.
4. Write a report artifact so the next run can be audited.

## Evidence Standard

- Every insight must point to concrete news evidence.
- Metric links are hypotheses, not invented facts. Use a known metric only when the relationship is explainable.
- Confidence should reflect evidence strength and specificity.
- Weak signals are useful: keep them in the journal instead of overstating them.
- Feedback from news and insight reactions should calibrate future recommendations.

## Output Classes

- INSIGHT: a defensible recommendation for a GOSB manager.
- ACTION ADVISORY: the practical next step and likely owner.
- METRIC LINK: a hypothesis about which business metric may move or provide context.
- DATA GAP: missing evidence, absent feedback or missing methodology.
- REJECTED / WEAK SIGNAL: sent news that was not promoted to an insight.

## Journal Entry

Use this structure in `journal.md`:

- Hypothesis
- Method
- Evidence
- Metric check
- Interpretation
- Decision
