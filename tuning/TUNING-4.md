# TUNING-4: Review skill — prior attempt inventory step

**Skills affected:** `fpv-pov-review.md`

## Problem

The review skill had a "deadlock check" that triggered only after 2 consecutive same-result prompts, but no instruction to proactively enumerate what had already been tried across the whole session. The model has full conversation history but doesn't synthesize it before proposing — it reads the most recent exchange and produces an incremental variation rather than asking "what structural approaches have I already exhausted?"

Result: across 5+ review iterations, the model drifts through minor tweaks (±10% frame percentages, minor phrasing changes) without escalating structurally, even when the same failure persists across many rounds.

## Fix applied

### fpv-pov-review.md

Added a mandatory **Step 0 — Prior attempt inventory** at the top of the Output format section (before the existing ban list scan and deadlock check).

The step requires:
1. Write a "Tried so far:" block listing each prior round's structural approach
2. Identify the result pattern (no change / partial change / persistent failure)
3. The new proposal must use an approach NOT in the tried list, or escalate to a different technique from the escalation list
4. If all listed approaches have failed → deadlock escalation immediately, no further variations

## Key Rule

The model has access to full conversation history but does not synthesize it without explicit instruction. A proactive inventory step — written out as part of the response — forces the model to consult the full trial record before proposing, rather than anchoring on the most recent exchange alone.
