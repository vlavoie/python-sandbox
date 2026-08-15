# ISSUE-11: Model-scoped resolution dropdown

**Type:** Feature  
**Status:** Implemented  
**Files:** `src/pasokon/workflow_panel.py`, `src/pasokon/fpv_workflow.py`, `src/pasokon/gradio_app.py`, `src/pasokon/project_state.py`, `src/pasokon/grok_client.py`

## What was added
Renamed `image_quality` → `image_resolution` everywhere. Added a Resolution dropdown
(`image_resolution_dropdown`) with choices `["auto", "1k", "2k"]`, label "Resolution (2.0 only)".

The dropdown is disabled and forced to `"auto"` for all models except `grok-imagine-image-2.0`.
On model change, `_on_model_change` fires and calls `gr.update(interactive=is_aurora, value=...)`
to enforce this.

`image_resolution` is persisted in `ProjectState` (default `"auto"`).

## API behaviour
`resolution` param is only sent to the xAI `/images/edits` endpoint when the value is not
`"auto"` AND the model is `grok-imagine-image-2.0`. For all other models, the param is omitted.

## Key invariants
- Only send `resolution` to the API for `grok-imagine-image-2.0`. All other models reject it.
- The dropdown must be disabled (not just hidden) for non-2.0 models — the stored value must
  always reflect what was actually sent.
- `is_aurora` = `"aurora"` in `model_id` (e.g. `grok-imagine-image-2.0`).
