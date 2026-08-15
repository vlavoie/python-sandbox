# ISSUE-4: Review thumbnails not shown after generating new images

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `_generate_images_for_ui`

## Root Cause
After a successful generation, `_generate_images_for_ui` returned `render_gallery_html([])`
for `failed_gallery` (the review tab thumbnail strip), clearing it. The user had to send
a review message before thumbnails appeared in the review tab.

Also, on project load, `get_ui_restore_values` always set `failed_gallery` to empty HTML
instead of restoring from saved state.

## Fix
- `_generate_images_for_ui` now returns `render_gallery_html(images)` for `failed_gallery`
  (same images as `output_gallery`), so thumbnails appear in the review tab immediately.
- `get_ui_restore_values` restores `failed_gallery` from `self.generated_images` only.
  Do NOT use `review_context["failed_images"]` on load — it may be from an older review
  cycle and is only valid during an active in-session review, not across restarts.

## Key Invariant
On project load, the review gallery always shows `self.generated_images` (the latest
permanent save). `review_context["failed_images"]` is only used during a live review
session (controlled by `send_message` → `start_review` / `continue_review`), never on load.
