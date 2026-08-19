# ISSUE-32 — [feature] "↗ Use this prompt" button in review chat

## What was added

Replaced the "Extract Final Prompt" button at the bottom of the Review tab with a small
"↗ Use this prompt" button rendered directly after each prompt code block in assistant
messages. Clicking it copies the prompt to the prompt box and switches to the
Generate Images tab.

## Implementation (current state)

### `_inject_extract_buttons(content: str) -> str`

Called on every assistant message before it enters `_ui_history`. Finds ` ``` ` fenced
blocks, runs `GrokClient._clean_prompt_text` on them, and for each non-empty result
**replaces** the raw fence block with:

1. A `<pre style="...">` rendering the prompt text (HTML-escaped body)
2. `<button class="psk-extract-btn" data-panel="{panel_id}" data-prompt="{escaped}">↗ Use this prompt</button>`

`data-prompt` is `html.escape(cleaned, quote=True)` — double-quote safe, no raw backticks.

`review_history` (the API history) is **never** touched; buttons live only in `_ui_history`.

### `_on_message_select(evt: gr.SelectData) -> Tuple[Any, Any]`

Wired to `review_chatbot.select()`. `evt.value` is the full HTML content of the clicked
message (from `_ui_history`).

Guard: `"psk-extract-btn" not in content` → no-op. This is correct because `_inject_extract_buttons`
replaced all ` ``` ` fences with `<pre>` tags — raw backticks are absent from `_ui_history`.
If the guard checked `"```"` it would always return no-op and the button would never work.

Extraction: `re.search(r'data-prompt="([^"]*)"', content)` + `html.unescape(m.group(1))`.
Returns `(prompt, gr.update(selected=f"{panel_id}_gen_images"))`.

### Cursor override (gallery.css)

Gradio sets `cursor: pointer` on **all** chatbot messages (user and bot alike) when
`select()` is wired on the chatbot. Override added:

```css
.psk-review-chatbot * {
    cursor: default !important;
}
.psk-review-chatbot .psk-extract-btn {
    cursor: pointer !important;
}
```

Scoped to `.psk-review-chatbot` so it doesn't affect the review input / send button below.

### JS guard (gallery.js)

A capture-phase `stopImmediatePropagation()` handler blocks non-button message clicks
from reaching Gradio's internal event dispatch. Note: Gradio 5 fires the chatbot `select`
event via Svelte's internal dispatch, not DOM bubbling, so this guard does **not** prevent
the select from firing on code block clicks — that's handled by the Python guard above.
The JS handler is harmless but not the primary defence.

### Where buttons are injected

- **`_send_execute` continue path** — injects into `display_content` before the final
  `_ui_history` assignment and last yield.
- **`stream_start_review` path** — injects into the tail slice of `review_history` when
  building `_ui_history`, then emits a final yield so buttons appear immediately without
  waiting for the next message.
- **`deserialize`** — builds `_ui_history` with buttons injected from the persisted
  `review_history` so restored sessions show buttons on load.
- **`fpv_workflow.py` `get_ui_restore_values()`** — passes `self._ui_history` (not
  `self.review_history`) to the chatbot update; critical for buttons to show on project load
  in the FPV panel, which reimplements this method without calling `super()`.

## Regression history

### Attempt 1
`_inject_extract_buttons` appended the button **after** raw ` ``` ` fences (did not
replace them). `_on_message_select` guarded on `"```" in content` and called
`_clean_prompt_text` to strip the fence. Worked.

### Regression
`_inject_extract_buttons` was changed to **replace** fences with `<pre>` tags (cleaner
rendering). Raw backticks no longer appear in `_ui_history` or `evt.value`. The `"```"`
guard fired immediately for every click — the button stopped working.

### Attempt 2 (current)
Guard changed to `"psk-extract-btn"`. Prompt read from `data-prompt` attribute directly
instead of re-parsing fences. Cursor override broadened from `.message` (wrong Gradio 5
class name) to `*` to cover all elements regardless of Gradio's internal class names.

## Key invariants

- **Guard must check `"psk-extract-btn"`**, not `"```"`. Code fences are gone from
  `_ui_history` — checking backticks silently disables all extractions.
- **Extract from `data-prompt`**, not by re-parsing content. `_clean_prompt_text` would
  fail because there are no fences left in `evt.value`.
- **`_inject_extract_buttons` only touches `_ui_history`** — never `review_history`.
- **Cursor override uses `*`** — Gradio applies `cursor:pointer` to every message element
  (user + bot) when `select()` is wired; Gradio 5's internal class names are not stable.
- **Final yield after `stream_start_review`** is critical — without it the chatbot shows
  the streaming version (no buttons) until the next message is sent.
- **FPV panel `get_ui_restore_values()`** must pass `self._ui_history` to the chatbot
  update. It reimplements the method without calling `super()`, so this must be explicit.
