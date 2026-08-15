# ISSUE-6: Project selector dropdown collapses after loading a project with no saved state

**Status:** Fixed  
**Files:** `src/pasokon/gradio_app.py`, `src/pasokon/project_state.py`

## Root Cause
Two separate bugs combined:

1. `project_selector` (the load dropdown) was not included in `OUTPUTS_PROJECT`. After a load
   operation, Gradio updated all outputs EXCEPT the selector, leaving it in a stale state.
   Selecting a second project would briefly populate the list, then collapse to one entry.

2. `_clear_all_panels()` was called unconditionally at the top of `load_project_state()`,
   before checking whether the state file exists. If the file was missing, panels were cleared
   and the function returned early with inconsistent state (project_name not updated, selector stale).

## Fix
- `gradio_app.py`: stored `project_selector` as `self.project_selector`, added it to
  `OUTPUTS_PROJECT`, and made `_build_project_outputs()` return fresh `choices` for it.
- `project_state.py`: moved `_clear_all_panels()` inside the try block, AFTER confirming
  the metadata file exists. No-state projects now set `project_name` and create the directory
  without touching panel state prematurely.
- Wrapped `_load_project_for_ui` and `_set_project_for_ui` in try/except to prevent
  Gradio from freezing outputs on unexpected errors.

## Key Invariant
Every component in `OUTPUTS_PROJECT` must be a stored reference (`self.xyz`), not a local
variable. `_build_project_outputs()` must return exactly as many values as `OUTPUTS_PROJECT`
has entries, in the same order.
