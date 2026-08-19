# ISSUE-35 — [bug] Review image buffer cleared on continue sends; no thumbnails after regeneration

## Symptoms

1. After the first review send (fresh start), clicking Send on any subsequent message
   immediately clears the `failed_gallery` buffer — even when new images were just
   generated — giving the impression that no images are being sent.
2. Chat bubbles for continue sends show no image thumbnails even after regenerating,
   so the user has no visual confirmation that new images are being analyzed.
3. From the user's perspective: "every attempt after the first one sends with no images."

## Root causes

### Bug A — `_send_start` clears buffer unconditionally for continue sends

```python
# OLD (review_mixin.py _send_start):
prior_gallery = render_gallery_html(self.generated_images or []) if not self.review_history else ""
```

When `review_history` is non-empty, `prior_gallery = ""` was returned immediately to
`failed_gallery`. This happened synchronously on the Send click — before the API call
even started — so the user watched the buffer disappear the moment they clicked Send.

### Bug B — continue `display_images` always excluded generated images

```python
# OLD:
display_images = (list(self.generated_images or []) + uploaded_clean) if not prior_api_history else uploaded_clean
```

`uploaded_clean` is empty when the user sends without an upload, so no thumbnails
appeared in the chat bubble for any continue message — including ones where new images
had been regenerated and were being analyzed.

## Fix

### `_send_start` — always show the buffer

Removed the `else ""` branch. `prior_gallery` now always equals
`render_gallery_html(self.generated_images or [])`. The buffer stays visible during the
full API call and is only cleared by `_flush_gallery` on a successful response (error
paths already preserved it).

### `_send_execute` — track `_last_send_images`, show thumbnails on image change

Added `self._last_send_images: List[str] = []` (session-only, not persisted) to
`WorkflowPanel.__init__`. Updated `display_images` logic:

- Fresh start: `current_gen + uploaded_clean` (unchanged)
- Continue, images changed since last send (`current_gen != _last_send_images`):
  `current_gen + uploaded_clean` — user sees which new images are being analyzed
- Continue, same images as last send: `uploaded_clean` — no redundant repeats

`_last_send_images` is updated to `current_gen` after every successful send (both fresh
start and continue paths).

## Key invariants

- `_last_send_images` is session-only — never serialized or deserialized.
- After a project reload, `_last_send_images = []`. On the first continue send of a
  new session, `current_gen != []` (assuming images exist) so thumbnails are shown,
  which correctly signals "these are the images being analyzed."
- The buffer (`failed_gallery`) is cleared only by `_flush_gallery` after success.
  Error paths leave it populated so the user can retry.
- `_send_start` no longer has any branch on `review_history` — the "only show buffer
  on fresh start" comment in the old code was describing the intended UX, not a
  necessary constraint; removing it fixes the perception bug without breaking anything.

## Unrelated: uploaded files in first send

When a user uploads a file to the review tab and sends it with generated images, the
uploaded file is treated as a second image to review (appended to `failed_images`),
NOT as a reference. This is the design intent (the upload field is labeled "Upload
specific images to review"). If the user expects the upload to serve as a reference
alongside the generated image, they should use the character reference field in the
Prompt tab instead.
