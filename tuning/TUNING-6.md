# TUNING-6: Vehicle-adjacent rear-side perspective + style/lighting front-loading

**Skills affected:** `fpv-pov-image.md`

---

## Problem 1 — Style anchor drift causes immediate lighting corruption

When complex lighting language appeared anywhere in the prompt ("warm amber interior light", "cool blue and magenta neon reflections", "dramatic shadows and highlights"), it overrode the simple anime style anchor regardless of position. Even when the style clause was front-loaded, one complex lighting sentence downstream was enough to corrupt the render into a semi-realistic high-contrast look.

The style clause **must be the absolute first clause** — before any spatial description — AND the prompt must contain **zero complex lighting descriptions**. "Nighttime city street" is fine as a scene element. "Cool blue neon signs reflect across the car's glossy paint and wet asphalt" is a lighting instruction that conflicts with flat cel-shading. Leave the lighting implicit once the style anchor is set.

**Rule:** Front-load the style clause. Then never describe lighting effects — only scene elements that carry light (neon signs, streetlamps). Let the style clause own all lighting.

---

## Problem 2 — Rear-side-of-window perspective: what works, what doesn't, in order of failure

This took 25+ iterations. The root issue: Aurora has a deeply trained "canonical car window approach" — camera in front of the open window, person looking straight out. Vague language about "rear side" is not enough to override it.

### What failed

| Approach | Why it failed |
|---|---|
| `"from the rear side of the car"` / `"from the backside"` | Too vague — Aurora ignores it and renders frontal |
| `"diagonal from lower left to upper right"` | This is the **front-side** perspective diagonal. Keeping it while claiming rear-side produces contradictory geometry |
| `"A-pillar and windshield visible to the right"` | Triggers right-hand-drive / passenger-side scene — Aurora reads directional windshield language as a side-selector |
| `"camera horizon at exact vertical center"` | Horizon rule is for standing/walking scenes, not vehicle lean-in compositions |
| `"turned in his seat, cranked over shoulder"` placed before man's description | Character substitution — Aurora pulls the reference IMAGE_0 character into the driver's seat |

### What works — the full anchor set

All four must be present together. Any one alone is insufficient:

1. **Explicit side of car:** `"standing on the left side of the sleek black sedan at the rear edge of the open driver's window"` — "left side" is the critical pin. Do not say "rear side of the window" (ambiguous), do not specify directional elements like A-pillar to orient the car.

2. **Seatback visible in the foreground:** `"the back of the driver's black leather seat plus the steering wheel and dashboard visible in the near-left and central foreground past which I am looking"` — the seatback being visible proves the camera is behind the seat. Impossible from the front of the window.

3. **Driver's body orientation AFTER his description:** `"the light-skinned average-looking 40-year-old man... turned in his seat with head and neck cranked sharply over his left shoulder looking back at me"` — encodes rear-side through the driver's body. Must appear after the full physical description or Aurora substitutes the reference character.

4. **Driver's hands pinned:** `"driver's left hand on the steering wheel and his right hand on the gear shift"` — without this, Aurora hallcinates dramatic arm poses (reaching through window, leaning out, etc.).

---

## Problem 3 — Foreground arm positions in car-window lean-in scenes

Aurora's canonical "lean" default: the most visually identified arm (the braceleted arm) gravitates to the upper contact point (roof, top of door frame). `"lower portion of the frame"` alone does not override this.

**To anchor an arm to the window sill (low position):**
- Describe the lower arm **first** in the prompt
- Use an absolute physical height reference: `"at hip height"` — this is a hard anchor Aurora cannot reinterpret as shoulder height
- Add a directional vector: `"angled down toward the lower-left corner"`

**To anchor the upper arm to the roof:**
- Describe it as `"coming from the [left/right] side of the frame resting on the car roof just above the window"` — the entry direction disambiguates it from the lower arm

**Pattern that works:**

```
my left gold-braceleted tanned wrist and forearm resting on the bottom sill of the open window at hip height in the lower-left portion of the frame angled down toward the lower-left corner, my right forearm coming from the right side of the frame resting on the car roof just above the window at the upper portion of the frame
```

---

## Key rules going forward

1. **Style clause first, always. Zero complex lighting language anywhere in the prompt.**
2. **Rear-side perspective requires all four anchors:** left-side-of-car, seatback-visible, driver-body-orientation-after-description, driver-hands-pinned.
3. **No diagonal for rear-side scenes.** The "lower-left to upper-right" diagonal belongs to frontal/side car-window scenes. Rear-side geometry is established through interior contents, not diagonal line descriptions.
4. **Arm positions in lean-in scenes:** lower arm first, hip height, angled-down vector; upper arm "coming from the [side] of the frame."
5. **"Turned in seat / cranked over shoulder" must follow the full man description**, never precede it.
6. **Drop the man's description = character substitution.** Even for structural rewrites, keep it verbatim every iteration.
