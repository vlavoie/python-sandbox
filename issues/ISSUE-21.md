# ISSUE-21: Review tab for Finalize workflow

**Type:** Feature  
**Status:** Added  
**Files:**
- `src/pasokon/workflow_panel.py` — extracted `_render_review_tab_content()`, `_wire_review_events()`, `_get_extract_outputs()` helpers
- `src/pasokon/finalize_workflow.py` — two-tab layout, `build_review_context()`, `get_review_skill()` with finalize prefix, `extract_prompt()` override

## What was added

The Finalize panel now has a **🔍 Review & Correct** tab identical in behavior to the FPV and Element review tabs. After a bad finalize output the user can:
1. Switch to the Review tab
2. Chat with the AI reviewer to diagnose what went wrong
3. Get a corrected prompt suggestion
4. Click **Extract Final Prompt** — this sends the corrected prompt text into the **Notes** field and switches back to the Finalize tab
5. Click **✨ Finalize Image** again; the Notes content influences the next auto-generated prompt

## Refactor: review helpers extracted from WorkflowPanel

`WorkflowPanel` previously had the review UI and event wiring inline inside `render()` and `_wire_events()`. Now extracted into:

- `_render_review_tab_content()` — creates `review_chatbot`, `review_input`, `_send_btn`, `failed_gallery`, `_gallery_state`, `_chatbot_state`, `_failed_upload`, `_extract_btn`. Can be called from any layout.
- `_wire_review_events()` — wires the 4-step send/submit chain (send_start → send_execute → flush → finish). Called from `_wire_events()` in the base class, and from `FinalizeWorkflowPanel._wire_events()` directly.
- `_get_extract_outputs()` — virtual method returning `[prompt_box, panel_tabs]`. Finalize overrides to return `[_notes_box, panel_tabs]` so the extracted corrected prompt lands in Notes.

## Finalize-specific review skill prefix

`get_review_skill()` prepends a finalize-specific context block to the base review skill:
- Identifies IMAGE_0 as character reference, IMAGE_1 as source image, additional images as the finalize outputs
- Review checklist: structure preserved? poses maintained? lighting improved? unintended changes?
- Corrected prompt instructions: 50–80 words, "Starting from IMAGE_1…" opener, spatial lock closer, no green zones

## Key invariants

- `extract_prompt()` in Finalize navigates to `"finalize_finalize"` tab (not `"finalize_gen_images"` which doesn't exist)
- The extracted prompt goes into `_notes_box`, not `prompt_box` — Notes feeds the next auto-generation
- `get_ui_outputs()` now includes `review_chatbot` and `failed_gallery` (added to OUTPUTS_PROJECT)
- `get_ui_restore_values()` restores review history and failed gallery on project load
