# ISSUE-31 — [feature] Image thumbnails in review chat messages + upload clear

## What was added

When a message is sent in the Review & Correct chat, the user's message bubble now
shows thumbnails of the images involved:

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
- `_ui_history` (List) — display-only, used for the chatbot widget. User turns may include extra HTML gallery bubble entries. Never serialised; reset (with `_inject_extract_buttons`) on project load via `deserialize()`.

This keeps the API free of redundant image data — only the `review_context` images are sent to the model.

### `gr.HTML` component message for gallery bubbles

`_build_display_user_msgs(text, images)` builds a list:
1. `{"role": "user", "content": text}` — the user's text bubble
2. `{"role": "user", "content": gr.HTML(value=render_gallery_html(images))}` — the gallery bubble (only if images exist)

Gradio's chatbot `_postprocess_content` handles `GradioComponent` instances by converting
them to `ComponentMessage(component="html", value=html_content, ...)`. The frontend renders
the embedded HTML component directly — no markdown processing, no DOMPurify, no file
serving required.

This is the same rendering path used by `failed_gallery` and `output_gallery` (`gr.HTML`
components), so the visual output and CSS classes are identical and proven to work.

### Why three attempts were needed

**Attempt 1 — base64 HTML in message content string (FAILED)**
Embedded `render_gallery_html()` output as a raw string in the message content, with
`sanitize_html=False`. The intent was for DOMPurify to be skipped, leaving the HTML intact.
Root cause of failure: `render_markdown=True` causes marked.js to process the content.
In marked.js v4+, raw HTML blocks in GFM Markdown ARE passed through as-is; however
DOMPurify strips `data:` URIs in `src` attributes by default — and even with
`sanitize_html=False`, there may be other factors. Result: no thumbnails.

**Attempt 2 — Gradio native `{"path": img_path}` content dict (FAILED)**
Passed `{"role": "user", "content": {"path": img_path}}` per image. Gradio's
`_postprocess_content` converts these to `FileMessage(file=FileData(path=img_path))`, then
`async_move_files_to_cache` copies the file to cache and sets the `url` field. Requires
`allowed_paths=[str(output_dir)]` in `launch()` for `_check_allowed` to pass.
Root cause of failure: unknown — the full Gradio file-serving pipeline has multiple silent
failure points (path permissions, cache errors, URL generation edge cases), and debugging
without running the code is infeasible. Result: no thumbnails.

**Attempt 3 — `gr.HTML` component message (WORKING)**
Pass `gr.HTML(value=gallery_html)` as message content. Gradio's `_postprocess_content`
dispatches `GradioComponent` instances directly to the component renderer, bypassing all
markdown/DOMPurify/file-serving machinery. Same rendering path as `gr.HTML` components
elsewhere in the app.

### Upload clear on send

`_send_finish` returns `gr.update(value=None)` for `_failed_upload` as a third value.
`_finish_event_kwargs` outputs: `[review_input, _send_btn, _failed_upload]`.

## Invariants to preserve

- `review_history` must stay text-only — never add component or file dicts to it.
- `_ui_history` is session-only — do not serialize it.
- `_build_display_user_msgs` returns a LIST; all callers must concatenate, not wrap in `[...]`.
- `_send_finish` outputs: `[review_input, _send_btn, _failed_upload]` — must stay in sync with the 3-value return tuple.
- `gr.HTML` is a supported chatbot component type (documented in Gradio 5 as: "Image, Plot, Video, Gallery, Audio, HTML, and Model3D are supported").
- `sanitize_html=False` on the chatbot is still required for `_inject_extract_buttons` HTML buttons in assistant messages — do not remove it.
