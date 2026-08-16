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

---

# TUNING-1b: Downward-tilt FPV (shorter character) — horizon rule does NOT apply

**Skills affected:** `fpv-pov-image.md`

## Problem
Aurora defaults to eye-level face-forward regardless of height cues. When the viewer
is meaningfully taller and looking slightly down at a shorter character, the model
still places the character's face at frame center and ignores the downward perspective.
Geometric percentage instructions ("character's eyes at 35% from bottom") have low
effectiveness on Aurora — the model prioritises its trained composition priors.

## Fix applied

### fpv-pov-image.md
- Split the "Looking slightly downward" template into two cases:
  - "Looking slightly downward at a shorter person (taller viewer)" — new template
  - "Looking straight down (floor/objects at feet)" — unchanged existing template
- Added **Shorter character / downward tilt** rules section:
  - Do NOT use "camera horizon at center" — that rule is only for straight-ahead FPV
  - Use character's gaze direction as the primary spatial anchor ("looking up at me")
  - Explicitly describe the crown of the character's head being visible from above
  - Viewer arm extends **downward** from lower frame edge, not forward
  - Floor visible at character's feet confirms the tilt
  - Character appears from head to knees/waist, NOT a tight face crop
  - Approximate frame layout percentages provided as supporting guidance (not primary anchor)

## Key Rule
The "camera horizon at center" rule from TUNING-1 applies ONLY to straight-ahead FPV.
For downward-tilt shots of shorter characters, use spatial relationship language:
- **"looking up at me"** — gaze direction is the strongest anchor
- **"top and crown of her [hair] clearly visible from above"** — confirms the downward angle
- **arm "extending downward"** — confirms viewer perspective, not eye-level reach
Never apply the horizon-at-center instruction to downward-tilt shots; it will pull the
composition back to eye-level face-forward.
