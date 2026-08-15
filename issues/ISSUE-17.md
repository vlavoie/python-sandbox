# ISSUE-17: Duplicate prompt guard on Generate Images

**Type:** Feature  
**Status:** Implemented  
**Files:** `src/pasokon/workflow_panel.py`

## What was added

When the Generate Images button is clicked with a prompt that is identical to the last submitted prompt, generation is blocked and an inline confirmation row appears:

> ⚠️ Same prompt as last generation. [Generate anyway] [Cancel]

"Generate anyway" proceeds to generate (and updates the last-submitted tracker). "Cancel" dismisses the row without generating.

## Motivation

During yurika-dust, three exact duplicate prompts were submitted to the API — iterations 12/13 (FPV), 14/15 (FPV), and element work-item-2 iteration 3. At 2k resolution these cost roughly $0.30–0.45 with zero new output. The guard prevents this without adding friction to the normal workflow.

## Key invariants to preserve

- `_last_submitted_prompt` is session-only (never serialized) — it resets to `""` on restart. The first generation after restart always passes through without the dialog.
- `_generate_images_for_ui` returns 3 values: `(output_gallery, failed_gallery, _dup_confirm_row)` — this is a change from the previous 2-value return. The `.click()` outputs must include `self._dup_confirm_row`.
- `_force_generate_images_for_ui` skips the duplicate check and is wired to the "Generate anyway" button. Both buttons share the same `_gen_inputs` / `_gen_outputs` lists.
- `_do_generate` contains the actual API call logic, shared by both paths.
