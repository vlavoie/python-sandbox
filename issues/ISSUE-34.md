# ISSUE-34 — [feature] Review tab buffer cleared after send

## What was added

After generating images, `failed_gallery` in the Review tab shows those images as a "buffer" — a preview of what will be included in the next review message (uploaded files, generated images). Once a review message is sent successfully, that buffer is cleared.

The Generate Images tab gallery (`output_gallery`) is independent and unaffected.

## How it works

`_flush_gallery` reads `_gallery_state` (a `gr.State` yielded by `_send_execute`) and writes it to `failed_gallery`. Changing the final success yields in `_send_execute` from the gallery HTML to `""` causes `_flush_gallery` to clear the buffer after a successful send.

The buffer is populated on generation (via `_gen_outputs` which includes `failed_gallery`) and on `_send_start` (which re-emits `render_gallery_html(self.generated_images)` into `failed_gallery`). Uploaded files are cleared separately via `_send_finish` → `gr.update(value=None)` on `_failed_upload`.

Error paths preserve the buffer value (keep existing gallery HTML) so the user can retry without losing context.

## Bundling generated + uploaded images

`display_images` in `_send_execute` and `images_to_review` in `stream_start_review` previously used OR logic (uploaded files replaced generated images). Both now use AND: generated images first, then any uploaded files appended. This means:
- Chat thumbnails show all images in the bundle.
- `review_context["failed_images"]` sent to the API contains the full bundle.
- `review_galleries` records the full bundle per turn.

## Key invariants

- Only the final SUCCESS yields in `_send_execute` emit `""` for `_gallery_state`; intermediate streaming yields and error paths are unchanged.
- `output_gallery` (Generate Images tab) is never touched by the send/clear flow.
- `_failed_upload` is cleared in `_send_finish` (pre-existing behaviour, unchanged).
- Generated images always come before uploaded files in the bundle order.
