# ISSUE-16: Optional element base image (green zone template) for Phase 2 element fill

**Type:** Feature  
**Status:** Implemented  
**Files:** `src/pasokon/element_workflow.py`, `fpv-pov-element.md`

## What was added

An optional "Element Base Template" `gr.Image` upload in the element workflow's Generate Prompt tab.
When a base image is provided (IMAGE_1), the workflow switches to Phase 2 fill mode: the blank canvas
with green zones tells Aurora exactly where the element should appear, sidesteppng the "hair = centered
wig" generation prior that Phase 1 prompts cannot reliably override.

## API / Gradio behaviour

- `get_additional_images_for_generation()` returns `[self.element_base_path]` when set; `None` otherwise
- `do_generate_prompt()` accepts `element_base` as its second argument (from `get_prompt_tab_inputs`)
- `build_review_context()` sets `review_mode="phase2"` and includes `element_base_path` in `additional_images` when set
- Prompt generation branches: Phase 2 template fill language when `element_base_path` is set; standard Phase 1 language otherwise
- `serialize/deserialize` and `get_ui_outputs/get_ui_restore_values` include `element_base_path` / `element_base`

## Key invariants to preserve

- `element_base` must be rendered with `image_mode=None` to preserve PNG alpha (ISSUE-7)
- `get_prompt_tab_inputs()` returns `[element_reference, element_base, element_desc_box, element_bg_radio]` — `do_generate_prompt` signature must match this order exactly
- `_on_base_change` saves the file permanently and calls `save_project_state()` immediately
- Phase 2 element skill (fpv-pov-element.md) is NOT the same as Phase 2 FPV review skill — the element Phase 2 base is a blank canvas, not a scene; "unchanged spatial and compositional base" language must not be used

## Motivation

Aurora consistently generates full centered wigs for complex hairstyle elements despite Phase 1 spatial rewrites. The green zone template approach (used successfully in FPV Phase 2 enhancements) eliminates the ambiguity by providing an explicit spatial map. Particularly effective for flowing hair with tails where split-generation is impractical.
