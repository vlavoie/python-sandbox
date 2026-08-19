# ISSUE-31 — [feature] Image thumbnails in review chat messages + upload clear

## What was added

When a message is sent in the Review & Correct chat, the user's message bubble now
shows base64-embedded thumbnails of the images involved:

- **First message** (fresh review start): thumbnails of all generated images (or uploaded
  images if the upload box is used) appear below the message text.
- **Continuation messages with uploaded files**: thumbnails of the newly uploaded images
  appear below the message text.
- **Continuation messages without uploads**: no thumbnail strip (plain text only).

Thumbnails use the existing `psk-gallery` / `psk-thumb` CSS classes and the
`render_gallery_html` helper, so they match the gallery styling.

After any message is sent, the upload box (`_failed_upload`) is cleared automatically.

## Key design decisions

### Separate `_ui_history` vs `review_history`

- `review_history` (List) — text-only, used for API calls. Serialised to disk and restored on project load.
- `_ui_history` (List) — display-only, used for the chatbot widget. User turns may include extra image-bubble entries. Never serialised; reset (with `_inject_extract_buttons`) on project load via `deserialize()`.

This keeps the API free of redundant image data — only the `review_context` images are sent to the model.

### Native Gradio file format for image bubbles

Each image is added as a **separate user message**: `{"role": "user", "content": {"path": img_path}}`. Gradio renders this natively as an image bubble via its `/file=` route — no base64, no HTML injection, no `sanitize_html` complications.

`_build_display_user_msgs(text, images)` returns a list: `[text_msg, img_msg_1, ..., img_msg_N]`. All callers in `_send_execute` concatenate this list: `prior_ui_history + display_user_msgs + [assistant_msg]`.

### `allowed_paths` in launch

`allowed_paths=[str(app.project_state.output_dir)]` added to `interface.launch()` so Gradio can serve images from `fpv-pov-outputs/` via `/file=` routes.

### Upload clear on send

`_send_finish` returns `gr.update(value=None)` for `_failed_upload` as a third value. `_finish_event_kwargs` outputs: `[review_input, _send_btn, _failed_upload]`.

## Invariants to preserve

- `review_history` must stay text-only — never add file dicts to it.
- `_ui_history` is session-only — do not serialize it.
- `_build_display_user_msgs` returns a LIST; all callers must concatenate, not wrap in `[...]`.
- `_send_finish` outputs: `[review_input, _send_btn, _failed_upload]` — must stay in sync with the 3-value return tuple.
- `allowed_paths` in `launch()` is required for image serving — do not remove it.
