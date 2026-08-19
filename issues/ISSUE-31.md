# ISSUE-31 — [feature] Image thumbnails in review chat messages + upload clear

## What was added

When a message is sent in the Review & Correct chat, the user's message bubble always
shows thumbnails of the images involved:

- **Uploaded files present**: thumbnails of the uploaded images appear below the message.
- **No uploads**: thumbnails of `generated_images` appear below every message.

Thumbnails are clickable — they open the full lightbox (same filmstrip + keyboard nav as
all other galleries in the app).

On project reload, each user message's gallery is restored exactly as it was when sent,
using `review_galleries` — a list parallel to `review_history` where each entry is the
image paths shown with that message (`[]` for assistant messages and messages with no gallery).

Thumbnails use the existing `psk-gallery` / `psk-thumb` CSS classes and the
`render_gallery_html` helper, so they match the gallery styling.

After any message is sent, the upload box (`_failed_upload`) is cleared automatically.

## Key design decisions

### Separate `_ui_history` vs `review_history`

- `review_history` (List) — text-only, used for API calls. Serialised to disk and restored on project load.
- `_ui_history` (List) — display-only, used for the chatbot widget. User turns may include extra HTML gallery bubble entries. Never serialised; reset (with `_inject_extract_buttons`) on project load via `deserialize()`.

This keeps the API free of redundant image data — only the `review_context` images are sent to the model.

### `ComponentMessage` for gallery bubbles

`_build_display_user_msgs(text, images)` builds a list:
1. `{"role": "user", "content": text}` — the user's text bubble
2. `{"role": "user", "content": ComponentMessage(component="html", value=gallery_html, constructor_args={}, props={})}` — the gallery bubble (only if images exist)

**Why not `gr.HTML`**: `_postprocess_content` mutates `gr.HTML.constructor_args` in-place
(pops "value" on first yield). Since `display_user_msgs` is reused across all streaming
yields, the gallery disappears after the first frame.

**Why `ComponentMessage`**: `_postprocess_content` returns `ComponentMessage` instances
unchanged (first isinstance branch). The Pydantic model is immutable — safe across all
yields. Same frontend rendering path: `component="html"` → HTML renderer.

No markdown processing, no DOMPurify, no file serving required.

### Upload clear on send

`_send_finish` returns `gr.update(value=None)` for `_failed_upload` as a third value.
`_finish_event_kwargs` outputs: `[review_input, _send_btn, _failed_upload]`.

## Attempt history

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

**Attempt 3 — `gr.HTML` component message (FAILED — mutation bug)**
Pass `gr.HTML(value=gallery_html)` as message content. Gradio's `_postprocess_content`
dispatches `GradioComponent` instances to the component renderer, which is correct in
principle. However, `_postprocess_content` MUTATES the `gr.HTML` object's `constructor_args`
dict IN PLACE:

```python
chat_message.constructor_args["render"] = False   # adds key
chat_message.constructor_args.pop("value", None)  # removes "value"!
```

The SAME `gr.HTML` instance is stored in `display_user_msgs` and reused across all yields
in `_send_execute` (streaming is many yields). After the first yield, `constructor_args` has
no `value` key. Every subsequent yield creates `gr.HTML(render=False)` with no content →
`ComponentMessage(value=None)` → nothing renders. The gallery bubble flashes for one frame
(if that) then disappears for the rest of the stream.

Root cause: `display_user_msgs` is built once at the start of `_send_execute`, and the
`gr.HTML` instance is reused across all streaming yields. The mutation on first yield
corrupts the object for all later yields.

**Attempt 4 — `ComponentMessage` directly + wrong data condition (STILL FAILED)**
Switched from `gr.HTML` to `ComponentMessage` (fixing the mutation bug). Confirmed via
Gradio frontend JS that `pa` component instantiation sets `type: t[15].content.component`
and `value: t[15].content.value`, so `ComponentMessage(component="html")` correctly maps
to the HTML renderer (case 6 in `ba`'s switch). The rendering pipeline is correct.

Root cause of CONTINUED failure: `display_images` was guarded by `elif not self.review_history:`
which is `False` whenever a project with saved history is loaded — gallery bubble was never
created. All four approaches failed with identical symptom (no thumbnails) because the data
condition was wrong, not the rendering.

**Attempt 5 — `ComponentMessage` + always-set `display_images` (WORKING for live session)**
Removed the `not self.review_history` guard entirely.
`display_images = uploaded_clean or list(self.generated_images or [])` is always evaluated
regardless of history state. Gallery bubble created for every message.

**Attempt 6 — Reload still missing galleries (misaligned indices from old saves)**

Root cause: projects saved BEFORE the `review_galleries` feature was added have no
`review_galleries` key in the JSON → `deserialize` loads it as `[]`. When a new message
is sent in a continuation session, `prior_galleries = []` (0 entries) but
`prior_api_history` may have N > 0 entries from history. The continuation save then writes:

```
review_galleries = prior_galleries + [display_images, []] = [[imgs], []]  # only 2 entries
review_history   = prior_api_history + [new_user, new_assistant]          # N+2 entries
```

On reload, `deserialize` maps `review_galleries[i]` by index, so:
- `i=0` (first OLD user message): assigned `[imgs]` from the NEW message → wrong gallery injected
- `i=N` (the NEW user message): `N >= 2` → out of bounds → `gallery_paths = []` → no gallery

Fix: before extending `prior_galleries` in the continuation path, pad it with `[]` entries
up to `len(prior_api_history)` so indices stay aligned:

```python
while len(prior_galleries) < len(prior_api_history):
    prior_galleries.append([])
```

After padding: old messages get `[]` (no gallery, correct), new message gets `[imgs]` at
the correct index.

**Attempt 7 — Thumbnails in chat not clickable (click blocker)**

Root cause: `gallery.js` registers two capture-phase listeners on `document`:
1. The chatbot click blocker (registered first): calls `stopImmediatePropagation()` on all
   clicks inside `.psk-review-chatbot .message` except `.psk-extract-btn`.
2. The lightbox handler (registered second): opens the lightbox on `.psk-thumb` clicks.

Because both are capture-phase listeners at the same node, `stopImmediatePropagation()` in
the first handler prevents the second from firing. Thumbnails inside the chatbot were
silently swallowed by the blocker.

Fix: add `.psk-thumb` to the blocker's allowlist:
```js
if (e.target.closest('.psk-thumb')) return;  // thumbnail — let lightbox handle it
```

Also: `.psk-review-chatbot * { cursor: default !important }` suppressed the `cursor: zoom-in`
on `.psk-thumb`. Fixed by adding a scoped override in `gallery.css`:
```css
.psk-review-chatbot .psk-thumb { cursor: zoom-in !important; }
```

## Invariants to preserve

- `review_history` must stay text-only — never add component or file dicts to it.
- `_ui_history` is session-only — do not serialize it.
- Every user message always gets a gallery bubble — no session flag, no history-length guard.
- `review_galleries` is a `List[List[str]]` parallel to `review_history`. User messages hold the image paths shown; assistant messages hold `[]`. Serialized to disk with `review_history`.
- `review_galleries` must be kept in sync with `review_history` — cleared in `_start_new_prompt`, set to `[display_images, []]` after fresh start, extended with `[display_images, []]` after each continuation.
- `prior_galleries` must be padded to `len(prior_api_history)` before extension — old saves lack `review_galleries` entirely, so `prior_galleries` can be `[]` while `prior_api_history` has N entries; without padding, gallery indices become misaligned across the history.
- `deserialize()` rebuilds `_ui_history` by iterating `review_history` and injecting a gallery bubble after each user message whose `review_galleries[i]` is non-empty.
- `_build_display_user_msgs` returns a LIST; all callers must concatenate, not wrap in `[...]`.
- `_send_finish` outputs: `[review_input, _send_btn, _failed_upload]` — must stay in sync with the 3-value return tuple.
- Use `ComponentMessage` (not `gr.HTML`) for gallery bubbles — `gr.HTML` is mutated by `_postprocess_content` (value popped on first yield); `ComponentMessage` is returned as-is.
- `ComponentMessage` is a Pydantic model: `from gradio.components.chatbot import ComponentMessage`.
- `sanitize_html=False` on the chatbot is still required for `_inject_extract_buttons` HTML buttons in assistant messages — do not remove it.
- The chatbot click blocker in `gallery.js` must exempt both `.psk-extract-btn` AND `.psk-thumb` — any new clickable element injected into chatbot messages needs to be added to this allowlist.
- `.psk-review-chatbot *` has `cursor: default !important` — any interactive element inside the chatbot needs an explicit cursor override scoped to `.psk-review-chatbot`.
