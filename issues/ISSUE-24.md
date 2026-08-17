# ISSUE-24: [bug] review_context["original_prompt"] not updated on regenerate — manual prompt edits lost

## Root cause

`generate_images_batch()` in `workflow_panel.py` updated `review_context["failed_images"]` with the new images whenever the user regenerated, but never updated `review_context["original_prompt"]`. That field was set once when the first review started and never changed.

When a user manually edited the prompt in the Generate Images tab and regenerated, the review system still sent the old first-ever prompt to the API on every subsequent message, ignoring the user's edits entirely.

## Fix

Added one line immediately after `self.review_context["failed_images"] = images`:

```python
self.review_context["original_prompt"] = prompt
```

## Key invariant

Both `failed_images` and `original_prompt` in `review_context` must be updated together whenever images are regenerated. They always describe the same generation event.
