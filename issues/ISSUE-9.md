# ISSUE-9: Review conversation history wiped on every image generation

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `_generate_images_for_ui`, `_wire_events`

## Root Cause
`_generate_images_for_ui` returned a 3-tuple and `review_chatbot` was included in the
`_gen_images_btn.click` outputs list. The success path returned `gr.update(value=[])` for
the chatbot, explicitly clearing all conversation history every time images were generated.

## Fix
- Removed `self.review_chatbot` from `_gen_images_btn.click` outputs.
- `_generate_images_for_ui` now returns 2 values: `(output_gallery, failed_gallery)`.
- The `review_chatbot` is now only written by `send_message` (review flow) and project load.

## Key Invariant
Image generation must never modify `review_chatbot`. The chatbot is output-only and its
authoritative source is `self.review_history`. Only `send_message`, `do_generate_prompt`
(to clear it), and the project restore path (`get_ui_restore_values`) should write to it.
