# TUNING-5: Deep reasoning parity — element and finalize review skills

**Skills affected:** `fpv-pov-element.md`, `finalize_workflow.py` prefix

## Problem

The element and finalize review loops were night-and-day inferior to FPV review. Both exhibited:
- **No iteration discipline:** submitting functionally identical prompts (±10% frame tweaks, rephrasing) without escalating structurally
- **Gaps filled by hallucination:** sparse descriptions left regions undescribed, which Aurora filled with its strongest prior (centered wig, reinterpreted scene)
- **No response to vague requests:** "Review these" produced generic or repeated diagnoses rather than identifying the most significant concrete failure
- **No pre-submission gate:** no check preventing the reviewer from submitting the same approach twice

FPV review had four mechanisms that element and finalize lacked:
1. Functional identity check (prevents functionally identical prompt resubmission)
2. Correction rules with the density-matters rule (Aurora hallucinates into gaps — describe every region)
3. "When user provides no specific feedback" section (concrete failure identification, not generic)
4. Pre-submission check sequence (ban list scan → functional identity check → deadlock check)

FPV review also had the explicit Aurora behavior model ("single correction principle", "repetition and length do not help") as a prominent leading section. Element had a brief version; finalize had nothing.

## Fix applied

### fpv-pov-element.md

Added four new sections inside the "Reviewing element generations" area, between the failure diagnosis and the Phase 2 mode section:

1. **Functional identity check** — element-specific structural change criteria (switching Phase 1 → Phase 2 template mode, adding/removing interior-viewpoint reasoning clause, split generation, reordering)
2. **Correction rules** — first-person pronouns, no ban lists, no repetition, preserve what's working, density matters
3. **When the user provides no specific feedback** — concrete failure identification, never repeat same fix, escalate if previous fix had no visible effect
4. **Review output format** — ban list scan, functional identity check, deadlock check as pre-submission steps; short blurb + background choice + code block as output structure

### finalize_workflow.py prefix

Expanded the prefix string with:
1. **Aurora behavior model** — leading section on the single correction principle, negative language, repetition
2. **When no feedback** — concrete failure identification adapted for finalize (composition drift, lighting, identity shift)
3. **Functional identity check** — finalize-specific structural change criteria (reordering opening, removing/rebuilding scene description, changing which light sources are foregrounded, adding/removing spatial reproduction clause)
4. **Correction rules** — first-person pronouns, no ban lists, density matters (adapted: sparse scene description = Aurora reinterprets the scene)
5. **Pre-submission checks** — ban list scan, functional identity check, deadlock check explicitly stated before output
6. **Output format** — blurb + code block with opening/closing structure spelled out

## Key Rule

Every review loop requires:
- An Aurora behavior model section (negative language, single correction principle, density)
- A functional identity check before every submission
- A "when no feedback" handler
- Explicit pre-submission checks as a numbered sequence

These four mechanisms together are what makes FPV review iterate structurally rather than incrementally. Absence of any one of them causes regression to minor tweaks that Aurora cannot distinguish.
