# ISSUE-2: Review thumbnails show previous generation after save/reload

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `generate_images_batch`, `_generate_images_for_ui`

## Root Cause
`generate_images_batch` called `save_project_state()` before returning. Then `_generate_images_for_ui`
updated `review_context["failed_images"]` AFTER the save had already run. So the saved state always
had the images from the previous review cycle, not the current generation.

## Fix
Moved `review_context["failed_images"] = images` into `generate_images_batch` immediately before
`save_project_state()`, and removed the duplicate update from `_generate_images_for_ui`.

## Key Invariant
Any state that must be persisted must be updated BEFORE `save_project_state()` is called.
`_generate_images_for_ui` is a UI adapter — it must not mutate state that is supposed to be saved.
