# ISSUE-15: Element review using FPV review skill, injecting Phase 2 language into element prompts

**Type:** Bug  
**Status:** Fixed  
**Files:** `src/pasokon/element_workflow.py` → `get_review_skill`

## Root Cause
`ElementWorkflowPanel.get_review_skill()` was returning `ps.review_skill` (the FPV review
skill, `fpv-pov-review.md`) instead of `ps.element_skill` (`fpv-pov-element.md`).

The FPV review skill contains Phase 2 instructions about chroma-green zones and
"Green paint fully removed." Element images use chroma green as their background, so the
reviewer pattern-matched on that and applied Phase 2 logic — producing prompts with
"Starting from IMAGE_1 as the unchanged spatial and compositional base" and
"Green paint fully removed" even though the element workflow is Phase 1 only.

## Fix
Changed `get_review_skill()` to return `ps.element_skill` so element review conversations
use the element generation skill, which has no Phase 2 language.

## Key Invariant
`ElementWorkflowPanel` must never use `ps.review_skill` — that skill is for FPV review only.
Element review must use `ps.element_skill` throughout.
