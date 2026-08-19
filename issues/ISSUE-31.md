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

- `review_history` (List) — text-only, used for API calls. Never contains HTML or base64 data. Serialised to disk and restored on project load.
- `_ui_history` (List) — display-only, used for the chatbot widget. User messages may contain the gallery HTML. Never serialised; reset to a text-only copy of `review_history` on project load via `deserialize()`.

This separation ensures the API never receives large base64 payloads for historical messages — only the images in the current `review_context` are sent (existing behaviour unchanged).

### `sanitize_html=False` on `gr.Chatbot`

Required so Gradio 5 does not strip `<img src="data:...">` tags from message content. The app is local-only, so this is safe.

### Upload clear on send

`_send_finish` now returns `gr.update(value=None)` for `_failed_upload` as a third value. `_finish_event_kwargs` includes `_failed_upload` in its outputs list.

## Invariants to preserve

- `review_history` must always be text-only — never add image data to it.
- `_ui_history` is session-only — do not serialize it; `deserialize()` resets it.
- `_send_finish` outputs: `[review_input, _send_btn, _failed_upload]` — must stay in sync with the return tuple.
- `sanitize_html=False` is intentional — do not revert without re-evaluating thumbnail rendering.
