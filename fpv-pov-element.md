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

## Critical constraint — FPV position, never centered

**The element must be generated at its actual FPV frame position. A centered, isolated object floating in the frame is always wrong.**

Hair is a border element — it occupies the edges, not the center. Hands occupy the lower frame, not the middle. If the element appears centered in the frame as a standalone object (e.g. a wig floating in space), the prompt failed. The element skill is not for generating reference art — it is for generating compositing assets at the exact screen position they will occupy in the final FPV image.

When reviewing an element generation: if the element is centered or floating, rewrite the prompt with explicit frame-border positions before trying anything else.

---

## How to describe the element — frame occupancy only

Describe what occupies each frame region. Do not describe camera position or perspective. The prompt opens with what fills each frame area and where.

---

**Hair fringe / bob (most common):**
The hair occupies the frame borders. Background fills the center.

> "[Hair description] occupying the upper [X]% of the frame and [X]%-wide panels along both frame borders, [background] filling the center and all remaining area. [Color matching IMAGE_0]. Art style and color exactly matching IMAGE_0. Only the hair on [background]."

Typical values: bangs 15–20% of frame height, side panels 12–18% wide.

---

**Flowing / long hair with tails or loose strands (complex hairstyles):**
Use this template when the hair has long trailing sections, side tails, ribbon ties, or a headdress — any style that doesn't have clean straight side edges.

The fringe/bangs follow the same rule as a bob (upper X% of frame). Long strands and tails enter from the upper corners and trail downward along the frame borders — they are border details, not centered objects. A headdress or hair accessory visible at the very top center edge anchors the top of the frame.

> "[Bangs/fringe description] occupying the upper [X]% of the frame. Long flowing [hair description] enters from the upper-left and upper-right corners, trailing downward along the left and right frame borders as [X]%-wide strips of loose strands, thinning toward the bottom. [Headdress/accessory] visible at the top center edge. [Background] fills the center and lower frame. Hair color, strand texture, ribbons, and accessories exactly matching IMAGE_0. Only the hair and accessories on [background]."

Typical values: bangs 15–20%, entering side strands 8–14% wide at the top narrowing to 4–6% at mid-frame.

If the hair is asymmetric (head turned), state different widths per side explicitly.

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

## Reviewing element generations — failure diagnosis

When reviewing a generated element, check in this order:

1. **Element is centered / floating (primary failure):** The element appears as a standalone object in the middle of the frame rather than occupying the frame borders. This is the most common failure and must be fixed before anything else.
   - Fix: Rewrite the prompt with explicit frame-border positions. State exactly which frame edges the element occupies and at what percentage widths. "Upper [X]% and [X]%-wide strips along the left and right frame borders" — not "centered", not "isolated on background."

2. **Side panels are scene objects instead of hair/element strips:** The side areas of the frame contain curtains, fabric, or other objects rather than the character's hair or body element. This happens when "entering from the sides" language is interpreted as objects walking into the scene.
   - Fix: Use the frame-border framing from the critical constraint section. Describe the hair/element as a static border detail, not as something entering or appearing. "The left and right frame borders are lined with [X]%-wide strips of [element]" rather than "[element] enters from the sides."

3. **Wrong proportions or scale:** Element is too small, too large, or wrong aspect ratio for FPV use.
   - Fix: Adjust the frame percentage values. Be specific: "bangs occupy the upper 18% of the frame" not just "bangs at the top."

4. **Color / style doesn't match IMAGE_0:** Element has wrong color or art style.
   - Fix: Add "Color, texture, and style exactly matching IMAGE_0" and verify IMAGE_0 is included in the generation.

---

## Output

Short prompt inside a single code block. Open with frame occupancy. End with color anchor and isolation confirmation. No style prescriptions, no ban lists, no camera language.
