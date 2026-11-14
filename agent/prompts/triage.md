---
description: Laya triage of pasted text (intent, urgency, frustration, refund, churn)
argument-hint: "<text, or a file path>"
---
Run the local Laya decision model over this and report only the numbers:

$@

Steps:
1. If the argument is a file path, read it and use its contents; otherwise use the text above.
2. Call `mcp__laya__laya_predict` (or `mcp__laya__laya_preset` with `{"preset": "triage"}` if
   direct tools are unavailable) with `state={"request": "<text>"}` and the triage question set
   (intent choice over technical_help/billing/sales/other, is_urgent noul, frustration score 0-3,
   refund_requested noul, churn_risk noul).
3. Answer with one compact table: question, label or probability, confidence. Flag any answer
   whose confidence is below 0.6, and say plainly if a `noul` answer contradicts the obvious
   reading of the text (that is a known checkpoint weakness, not a fact about the text).
4. Do not add commentary, recommendations, or a summary unless I ask.
