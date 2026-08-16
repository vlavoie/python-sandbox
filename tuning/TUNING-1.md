# TUNING-1: Standing FPV horizon defaults to frame top — must pin at vertical center

**Skills affected:** `fpv-pov-image.md`, `fpv-pov-review.md`

## Problem
Aurora defaults to placing the perspective horizon (vanishing-point horizon) near the top
of the frame for standing FPV shots. "Eye level" language alone does not anchor it.
Result: anything above the viewer's eye level (e.g. a slightly-taller character's face)
fills a disproportionately large portion of the frame and reads as towering.

A compounding error: setting the ceiling to a narrow strip (e.g. "upper 18% of frame")
forces the character's head into the space between that strip and the frame center,
which can be 32% of the frame height — the face of a "slightly taller" character
ends up the size of a close-up portrait.

## Fix applied

### fpv-pov-image.md
- Updated the "Looking forward" template to include explicit horizon anchoring:
  `"camera horizon — the vanishing-point horizon — at the exact vertical center of the frame"`
- Added **Standing FPV horizon rule** section explaining Aurora's default bias and the fix
- Added **Height and scale** section with correct proportions for a slightly-taller character:
  - Viewer eye level = exact vertical center
  - Slightly-taller character's chin = at or just above center
  - Character's face = narrow 10–15% band above center
  - Character's head top = ~one-third from the top
  - Ceiling = upper third of the frame (not 15–18%)

### fpv-pov-review.md
- Added failure type #4 "Character appears disproportionately tall/towering"
- Root cause, spatial fix, and correct ceiling/face proportions documented

## Key Rule
For standing FPV, always use: **"camera horizon — the eye-level vanishing point — pinned
exactly at the vertical center of the frame"** in the opening sentence.
Never describe the ceiling as less than ~30% of the frame when the subject is
only slightly taller than the viewer.
