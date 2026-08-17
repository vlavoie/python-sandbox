# ISSUE-25: [feature] Disable generate buttons during image generation

## What was added

`_generate_images_for_ui` and `_force_generate_images_for_ui` converted from regular functions to generators. Both `_gen_images_btn` and `_gen_anyway_btn` added to `_gen_outputs`. The generators yield `gr.update(interactive=False)` for both buttons on entry and `gr.update(interactive=True)` on exit (normal or exception).

The duplicate-prompt detection path keeps buttons interactive since it only shows the confirm row without doing any generation work.

## Key invariants

- `_gen_outputs` must include both `_gen_images_btn` and `_gen_anyway_btn` so both are disabled during any generation path.
- Both functions must be generators (use `yield`, not `return`) so the initial disable fires before the blocking API call.
- The duplicate-prompt early-return path must yield `gr.update()` (no change) for the buttons — not `interactive=False` — since it returns immediately without doing work.
