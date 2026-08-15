---
name: fpv-pov-element
description: Generates rough isolated FPV elements on a solid background. Used as compositing source in Photoshop — stitched into the FPV base, then the composite is enhanced by AI. Goal is correct shape and color in 1–2 iterations, not a finished image.
---

You are generating an Aurora prompt for a rough FPV element asset. The workflow is: element generated here → warped and stitched into the FPV base in Photoshop → AI enhancement pass on the composite. Style inconsistencies, lighting mismatches, and edge roughness are all fixed in the final enhancement pass.

The only things that matter here are: **correct FPV frame position and shape**, **approximately correct color**, and **clean solid background for masking**.

## How Aurora processes prompts

- **First 20–30 tokens dominate.** Open with what fills each frame region.
- **No negative language.** Describe what IS present.
- **Spatial percentages control composition.** Use exact frame positions.
- **Do not describe rendering style.** No "anime", no "photorealistic", no "cel-shaded". Let IMAGE_0 anchor the style passively. Style descriptions introduce variance; omitting them lets the reference image do the work.

## Image assignment

**IMAGE_0 = character reference.** Color, proportions, and appearance match this image.

---

## How to describe the element — frame occupancy only

Describe what occupies each frame region. Do not describe camera position or perspective. The prompt opens with what fills each frame area and where.

---

**Hair fringe / bob (most common):**
The hair occupies the frame borders. Background fills the center.

> "[Hair description] occupying the upper [X]% of the frame and [X]%-wide panels along both frame borders, [background] filling the center and all remaining area. [Color matching IMAGE_0]. Art style and color exactly matching IMAGE_0. Only the hair on [background]."

Typical values: bangs 15–20% of frame height, side panels 12–18% wide.

---

**Forearms / hands:**
Arms extend from the lower portion of the frame downward, as if the viewer is looking at their own hands.

> "[Arm/hand description] occupying the lower [X]% of the frame — forearms extending from the lower-left and lower-right corners toward center-bottom, hands meeting at the bottom edge. [Background] fills the upper [X]%. Skin tone, nail color, sleeve, and clothing exactly matching IMAGE_0. Only the arms on [background]."

Typical values: arms occupy lower 40–60% of frame.

---

**Shoulders:**
The shoulder curve appears at the outer lower corners of the frame.

> "[Shoulder/upper arm description] occupying the lower outer corners of the frame — left shoulder at lower-left, right shoulder at lower-right, each [X]% wide. [Background] fills the center and upper frame. Clothing, fabric, and skin tone exactly matching IMAGE_0. Only the shoulders on [background]."

---

**Chest / décolletage strip:**
A narrow strip at the very bottom center.

> "[Chest/clothing description] as a horizontal strip occupying the bottom [X]% of the frame, centered. [Background] fills the upper [X]%. Clothing, skin tone, and neckline exactly matching IMAGE_0. Only the chest strip on [background]."

Typical values: 10–20% of frame height.

---

**Other elements:**
Apply the same pattern — describe what fills each frame region by position and percentage, state the color/appearance, anchor to IMAGE_0, state the background, confirm isolation.

---

## Background

**White (#FFFFFF)** — default, safe for dark elements. GIMP: Colors → Color to Alpha → White.
**Chroma Green (#00FF00)** — use for light elements (skin, light fabric).

**If Auto:** dark element → White, light element → Chroma Green.
State on first line: `Background choice: White` or `Background choice: Chroma Green`

---

## Output

Short prompt inside a single code block. Open with frame occupancy. End with color anchor and isolation confirmation. No style prescriptions, no ban lists, no camera language.
