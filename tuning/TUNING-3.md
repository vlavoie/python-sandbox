# TUNING-3: First-person pronouns for viewer body parts — "my hand" not "the hand"

**Skills affected:** `fpv-pov-image.md`, `fpv-pov-element.md`

## Problem

The skill had drifted to depersonalized language for viewer body parts:
- "forearms and hands extending from the lower center"
- "viewer arm extending downward"  
- "[Viewer arm/hand] extending from the bottom frame edge"
- "hands or forearms at the lower frame edge"

Aurora treats these as a separate character's body parts rather than the viewer's own. This caused Aurora to render disembodied or third-person hands, or to associate the body parts with another character in the scene.

Additionally, the "Critical" note in the output format section said "Do not prefix the prompt with first-person narrator framing" — this was intended to block meta-references ("I am the character from IMAGE_0") but was causing the LLM to strip first-person pronouns from body part descriptions entirely.

## Fix applied

### fpv-pov-image.md

- Updated all templates to use "my hands/forearms", "my arm", "my feet/legs"
- Updated downward tilt rule: "Arm extends downward" → "My arm extends downward — I reach"
- Updated hair template: "viewer's own [style] hair" → "my own [style] hair"
- Updated "Correct visibility by camera direction" bullet list to use "my hands/forearms/feet"
- Added explicit rule in "What body parts are visible" section:
  > "Always use first-person pronouns for viewer body parts: 'my hand', 'my forearm', 'I reach toward' — not 'the hand', 'forearms extending from the frame', or 'viewer's arm'. First-person possessives are the strongest FPV signal and match the visual novel / game CG language Aurora was trained on."
- Clarified the "Critical" note: first-person possessives for body parts ARE required; the ban is only on meta-references like "I am the character from IMAGE_0"

### fpv-pov-element.md

Same fix applied to all body part templates: arms/hands, shoulders, chest, hair. The arm template is the most impactful — "forearms extending from the lower corners" with no ownership signal caused Aurora to generate arms at wrong approach angles (reaching in from the sides, at 45°) rather than the correct straight-down hands-visible-from-above FPV orientation.

## Key Rule

Viewer body parts must always be described with first-person pronouns in both skills. "My hand reaches toward her" / "my forearms extending from the lower corners" is correct. "Hand extending from the lower frame edge" / "forearms extending from the lower corners" is wrong — Aurora has no signal that the body parts belong to the viewer, and may generate them at any angle or attribute them to a separate character.
