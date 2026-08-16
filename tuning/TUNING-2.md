# TUNING-2: Finalize prompt strategy — full scene description, not delta

## Problem observed

`shima-backside` finalize across 3 work items produced dramatically wrong outputs: art style shifted between semi-anime → 3D photorealistic CG → anime, lingerie color changed, room geometry changed, mirror angle changed. The source image was a semi-anime mirror dressing room scene.

`yurika-shima` finalize worked on the first attempt: composition, art style, character, and scene all preserved faithfully.

## Why yurika-shima worked

The successful prompt said:
> "Starting from IMAGE_1 as the unchanged spatial and compositional base, bathed in warm radiant light from multiple ornate crystal chandeliers producing rich golden hues and elegant sparkling reflections across the champagne flutes and polished surfaces…"

Two accidental properties made this work:
1. The chandeliers were already **large and dominant** in the source frame — the prompt amplified something that was already visually dominant, so Aurora didn't need to invent a new lighting concept.
2. The scene was **simple and direct** (character facing viewer, single depth layer, no reflections) — less creative latitude for Aurora to reinterpret.

## Why shima-backside failed

The finalize prompts used language like "warm golden lighting from the elegant lamps" — but the bedside lamp was a small, dim element in a complex mirror reflection scene. Aurora interpreted the lighting instruction as a full creative brief. The mirror-plus-reflection spatial arrangement (three depth layers) also gave Aurora more surface area to reinterpret.

## Root cause (Aurora model behavior)

Aurora regenerates images — it does not edit them pixel-by-pixel. A finalize prompt using "Starting from IMAGE_1… [describe the improvement]" signals a delta, which gives Aurora creative latitude to reinterpret the unchanged portions. Style drift, color shift, and composition changes are all downstream of this.

## Fix applied to fpv-pov-finalize.md

**Old approach**: "describe the delta" — anchor to IMAGE_1, then describe lighting/color improvements.

**New approach**: "describe the full scene" — write a complete scene description as IMAGE_1 already is, with quality improvements embedded within the description rather than described as changes. Name the art style explicitly in the first 10 words.

### Key rules now in skill:
1. **Name the art style first** — "Semi-anime illustration, FPV POV..." — this is the single most important drift prevention
2. **No "Starting from IMAGE_1 as unchanged base…"** — that phrase signals a delta and gives creative latitude
3. **Only existing light sources** — never introduce a light source not already visible in IMAGE_1
4. **Full scene description** — leave no major element unnamed; Aurora hallucinates into gaps

### Example of correct structure:
```
Semi-anime illustration, FPV POV luxury dressing room, viewer's dark hair fringe
visible at frame edges, ornate gilded mirror centered in frame reflecting a 
dark-haired woman in black lace lingerie and garter belt with arms spread, elegant 
chandelier in the reflected bedroom casting soft warm illumination across polished 
marble floors, deep purple velvet curtains flanking the mirror. Character appearance 
locked to IMAGE_0. IMAGE_1 spatial composition, character position, clothing, and 
scene structure reproduced exactly with superior rendering fidelity.
```

## Key rule going forward

> Finalize prompts must name the art style first and describe the full scene as it already is. Never describe what should change — describe what already exists, with quality improvements embedded in the description of existing elements.
