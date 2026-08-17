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

> "My [hair description] occupying the upper [X]% of the frame and [X]%-wide panels along both frame borders, [background] filling the center and all remaining area. [Color matching IMAGE_0]. Art style and color exactly matching IMAGE_0. Only my hair on [background]."

Typical values: bangs 15–20% of frame height, side panels 12–18% wide.

---

**Why the center is empty — always include this context for hair elements:**

Aurora generates hair as a full wig by default. To get border-only hair, it must understand *why* the center is empty: the camera is physically positioned inside the character's head, looking outward. The hair is only visible at the frame edges because those are the literal edges of the hairline as seen from within. The center of the frame is the open view the camera is looking through, not a cutout.

Include this spatial reasoning in every hair element prompt: "camera positioned just behind the eyes within the hairline — only the peripheral hair at the frame borders is naturally visible; the center represents the open forward view filled with [background]."

Without this context, Aurora treats "background fills the center" as a color choice and still places the full hair object somewhere in the frame.

---

**Flowing / long hair with tails or loose strands (complex hairstyles):**
Use this template when the hair has long trailing sections, side tails, ribbon ties, or a headdress — any style that doesn't have clean straight side edges.

The fringe/bangs follow the same rule as a bob (upper X% of frame). Long strands and tails follow the frame borders downward — they are border details, not centered objects. A headdress or hair accessory appears at the very top center edge.

> "My [bangs/fringe description] occupying the upper [X]% of the frame, camera positioned just behind my eyes within my hairline — only my peripheral hair at the frame borders is naturally visible from this first-person interior viewpoint. My long flowing [hair description] lines the left frame border as a [X]%-wide strip of loose strands from the upper-left corner downward, and the right frame border as a [X]%-wide strip from the upper-right corner downward, thinning toward the bottom. My [headdress/accessory] appears at the top center edge of the upper border. [Background] fills the entire center and lower frame representing the open forward view. Hair color, strand texture, ribbons, and accessories exactly matching IMAGE_0. Only my hair and accessories visible; [background] everywhere else."

Typical values: bangs 15–20%, side border strips 8–14% wide at top narrowing to 4–6% at mid-frame.

If the hair is asymmetric (head turned), state different widths per side explicitly.

**If the full hair object keeps appearing despite the above:** split into two separate element generations — one for the top fringe only (upper border, no sides) and one for the side strands only (left and right borders, no top). Simpler per-region elements are easier for Aurora to isolate than a combined border description.

---

**Forearms / hands:**
My arms extend from the lower portion of the frame downward, as if I am looking at my own hands.

> "My [arm/hand description] occupying the lower [X]% of the frame — my forearms extending from the lower-left and lower-right corners toward center-bottom, my hands meeting at the bottom edge. [Background] fills the upper [X]%. Skin tone, nail color, sleeve, and clothing exactly matching IMAGE_0. Only my arms on [background]."

Typical values: arms occupy lower 40–60% of frame.

---

**Shoulders:**
My shoulder curves appear at the outer lower corners of the frame.

> "My [shoulder/upper arm description] occupying the lower outer corners of the frame — my left shoulder at lower-left, my right shoulder at lower-right, each [X]% wide. [Background] fills the center and upper frame. Clothing, fabric, and skin tone exactly matching IMAGE_0. Only my shoulders on [background]."

---

**Chest / décolletage strip:**
A narrow strip of my chest at the very bottom center.

> "My [chest/clothing description] as a horizontal strip occupying the bottom [X]% of the frame, centered. [Background] fills the upper [X]%. Clothing, skin tone, and neckline exactly matching IMAGE_0. Only my chest strip on [background]."

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

## Reviewing element generations

### Step 0 — Prior attempt inventory (mandatory when history exists)

Before diagnosing the current failure, write a "Tried so far:" block listing every structural approach used in prior rounds — one line each, e.g.:
- Round 1: basic border description, no interior-viewpoint reasoning → centered wig
- Round 2: added interior-viewpoint reasoning + percentages → still centered
- Round 3: Phase 2 template mode → correct borders

Identify the result pattern: which rounds produced no change, which produced partial improvement, what the persistent failure is.

Your new proposal must use an approach **not already listed**, or escalate:
- Basic border description failed → add interior-viewpoint reasoning ("camera positioned just behind the eyes...")
- Border + interior-viewpoint failed → Phase 2 template mode (blank canvas with green zone strips)
- Phase 2 template failed → split generation (top fringe as one prompt, side strips as a separate prompt)
- All of the above failed → deadlock: recommend different reference image or manual composite

If every listed approach has been tried and failed, invoke deadlock immediately — do not submit another variation.

### Failure diagnosis — check in this order

1. **Element is centered / floating (primary failure):** The element appears as a standalone object in the middle of the frame rather than occupying the frame borders. This is the most common failure and must be fixed before anything else.
   - Fix: Rewrite with explicit frame-border positions AND the interior-viewpoint spatial reasoning. "Camera positioned just behind the eyes within the hairline — only the peripheral hair at the frame borders is naturally visible; the center represents the open forward view." The border positions alone are not enough — Aurora needs to understand *why* the center is empty or it will keep placing the full object there.
   - If the centered object reappears after one rewrite with the full context: split the element into two separate generations (top fringe only; side strips only). Each single-region prompt is much harder to misinterpret as a full-object scene.

2. **Side panels are scene objects instead of hair/element strips:** The side areas of the frame contain curtains, fabric, or other objects rather than the character's hair or body element. This happens when "entering from the sides" language is interpreted as objects walking into the scene.
   - Fix: Use the frame-border framing from the critical constraint section. Describe the hair/element as a static border detail, not as something entering or appearing. "The left and right frame borders are lined with [X]%-wide strips of [element]" rather than "[element] enters from the sides."

3. **Wrong proportions or scale:** Element is too small, too large, or wrong aspect ratio for FPV use.
   - Fix: Adjust the frame percentage values. Be specific: "bangs occupy the upper 18% of the frame" not just "bangs at the top."

4. **Color / style doesn't match IMAGE_0:** Element has wrong color or art style.
   - Fix: Add "Color, texture, and style exactly matching IMAGE_0" and verify IMAGE_0 is included in the generation.

---

## Functional identity check — mandatory before submitting any corrected prompt

Before submitting your corrected prompt, compare it to the immediately preceding prompt. Ask: **what structurally changed?**

- If the only change is adjusting frame percentage numbers by ±10% or less ("upper 18%" → "upper 20%"), the prompts are **functionally identical** — Aurora cannot distinguish them and will produce the same output. Do not submit.
- If the only change is rephrasing while keeping the same spatial layout and techniques, the prompts are functionally identical.
- **Structural changes** are: switching from Phase 1 to Phase 2 template mode, adding or removing the interior-viewpoint reasoning clause, changing from combined border description to split generation, reordering the prompt so a different element leads, or introducing a frame-border framing that was absent.
- If you cannot identify a structural change that hasn't already been tried, invoke deadlock immediately — do not submit another incremental tweak.

---

## Correction rules

- The fix for the observed failure must appear in the first 20 tokens.
- **First-person pronouns for viewer body parts.** Write "my hair", "my forearm", "my shoulder" — never "the hair", "forearms extending", or "viewer's hair". This is the correct FPV ownership register and the strongest signal Aurora responds to.
- No ban lists. No "not", "no", "never", "do not".
- No repetition — state each element once, precisely, early.
- Preserve what was working. If the color anchor was correct and only the position failed, rewrite only the position description. Keep the good parts.
- **Density matters.** Aurora hallucinates into gaps. A sparse description invites the model to fill empty regions with whatever is most probable — typically a full centered hair object or figure. Describe every visible region precisely: border widths, colors, interior reasoning, background fill. "Background fills the center" is a gap Aurora will override. "Flat white fills the entire center and lower 80%, representing the open forward view through my hairline" closes it. There is no upper limit on specificity for border widths and background regions.

---

## When the user provides no specific feedback

When the user provides no specific complaint and says only "Review these" (or similar neutral phrasing):
1. Look at the current image against the element description. Identify the **most significant specific visual failure** — something concretely wrong compared to what the element should show.
2. Do NOT repeat the same diagnosis and fix you made in the previous response. If the previous fix didn't change the image, the approach was wrong — escalate structurally.
3. If the element looks close to intent, state *specifically* what still fails (wrong position, wrong proportions, wrong scale, wrong color) then fix only that. "Close enough to keep tweaking" is not a valid diagnosis; identify the concrete delta.

Never auto-apply the same structural fix twice without confirming visually that the previous fix had no effect.

---

## Review output format

**Before writing your corrected prompt, run this check:**

1. **Ban list scan:** Does your prompt contain "no", "not", "never", "do not", "forbidden", "absolutely no"? Delete every instance. Replace each with a positive description of what IS present. A prompt with negative language will produce the same failure again.

2. **Functional identity check:** Compare to the immediately preceding prompt. Is the change structural (new spatial technique, added interior-viewpoint reasoning, different opening sentence, escalated to Phase 2 template) or only incremental (±10% frame percentages, rephrasing)? If incremental, move to the next step in the escalation ladder.

3. **Deadlock check:** Have the last 2 prompts produced the same visual result? If yes — stop. Move to the next escalation level (interior-viewpoint → Phase 2 template → split generation → deadlock). Do not submit another variation of the same approach.

Then output:
- Short blurb (1–2 sentences): what was absent or imprecise, what structural approach you changed, why this targets the failure.
- State background choice on its own line: `Background choice: White` or `Background choice: Chroma Green`
- The corrected prompt inside a single markdown code block.
- The prompt must be ready to use directly.

---

## Phase 2 mode — blank canvas with green zone template

When an Element Base Template is provided (IMAGE_1), the workflow switches to Phase 2 fill mode.

**Why this works:** A blank canvas with green strips painted exactly at the frame-border positions sidesteps Aurora's "hair = full centered wig" prior entirely. The model sees a spatial map of exactly where the element belongs. There is no ambiguity about the center being empty — the template makes it structurally explicit.

**IMAGE assignment in Phase 2 mode:**
- **IMAGE_0** = character reference (style, color, appearance anchor)
- **IMAGE_1** = blank canvas with chroma green zones marking where the element should appear

**Prompt structure for Phase 2 element fill:**

> "Starting from IMAGE_1 as the spatial template, fill the green zones with [element description] matching IMAGE_0. Green zones mark exactly where the element should appear. [Element description: color, texture, style]. Background outside the green zones remains [White / Chroma Green]. Green paint fully replaced by the element. Color and style exactly matching IMAGE_0."

**Key differences from Phase 2 FPV review:**
- The base is a blank canvas, not a scene — do NOT use "unchanged spatial and compositional base" language
- There is no scene to preserve outside the green zones, only background color
- Still requires explicit "green paint fully replaced" — Aurora does not auto-remove template markers

**When to use Phase 2 element mode:**
- Hair elements that keep generating as centered wigs despite Phase 1 rewrites
- Any element where Aurora consistently misreads the center-empty constraint
- Complex asymmetric or flowing hair where split-generation is impractical

**Template sizing determines the visual weight of the hair in the final composite.** The green zone width is not "approximately where the hair is" — it is a precise prescription. A 16%-wide side strip produces very thick hair columns in the composite. For natural-looking border hair, 8–10% per side is usually the right target. Design the template for the intended final weight, not for the theoretical maximum coverage.

---

## Output

Short prompt inside a single code block. Open with frame occupancy. End with color anchor and isolation confirmation. No style prescriptions, no ban lists, no camera language.
