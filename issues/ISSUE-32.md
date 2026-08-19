# ISSUE-32 — [feature] Click prompt code block button to extract prompt

## What was added

Replaced the "Extract Final Prompt" button at the bottom of the Review tab with a
small "↗ Use this prompt" button rendered directly after each prompt code block in
the assistant's messages. Clicking that button copies the prompt to the prompt box
and switches to the Generate Images tab.

## Implementation

### Pattern: button visual affordance + chatbot select event

`review_chatbot.select()` fires on any click in the chatbot with `evt.value` = the full
message content. The guard `"```" not in content` makes it a no-op for analysis messages.
Only messages that contain a prompt code block (with ` ``` ` fences) trigger extraction:

1. `_inject_extract_buttons(content)` appends
   `<button class="psk-extract-btn" ...>↗ Use this prompt</button>` after each
   ` ``` ` block that `_clean_prompt_text` returns non-empty for. This makes the
   button visible but clicking it or anywhere else in the message both work.
2. `review_chatbot.select` → `_on_message_select(evt)` checks for ` ``` ` in
   `evt.value`, calls `_clean_prompt_text`, and if the result differs from the raw
   content (meaning it extracted from a fence), returns the prompt + tab switch.

No JS bridge is needed — the click bubbles naturally to the chatbot's Gradio select handler.

### Where buttons are injected

- **`_send_execute` continue path**: injects into `display_content` before the final
  `_ui_history` assignment and last yield.
- **`stream_start_review` path**: injects into the tail slice of `review_history` when
  syncing `_ui_history`, then emits a final yield so the chatbot shows the buttons
  immediately (without waiting for the next message).
- **`deserialize`**: injects into the copy of `review_history` used as `_ui_history`
  so restored sessions show buttons on existing messages immediately on load.

### Guard in `_on_message_select`

```
if "```" not in content: return no-op
cleaned = _clean_prompt_text(content)
if cleaned and cleaned != content.strip(): return cleaned + tab switch
```

`cleaned != content.strip()` ensures we only extract when the fence was actually
stripped — if the whole message is plain text, `_clean_prompt_text` returns it
unchanged, which would be a false positive.

### Other changes

- `_extract_btn`, `extract_prompt()`, separator/label UI, JS bridge, and offscreen
  components are all removed.
- `.psk-extract-btn` button styles in `gallery.css`.
- `_get_extract_outputs()` override contract is unchanged.
- `review_history` (the API history) is never modified — buttons only in `_ui_history`.

## Attempt 2 — regression fix (button broken + code blocks look clickable)

### Root cause

`_inject_extract_buttons` was changed to replace ` ``` ` fences with `<pre>` tags, so
`_ui_history` messages no longer contain backticks. `_on_message_select` guarded on
`"```" not in content` — which was now always true — so every select event returned
no-op, including button clicks.

### Fixes

1. **`_on_message_select`**: changed guard from `"```"` check to `"psk-extract-btn"` check;
   reads the prompt from the `data-prompt` HTML attribute via `re.search` + `html.unescape`
   instead of `_clean_prompt_text`. The attribute is already `html.escape(quote=True)` encoded.

2. **`gallery.css`**: added cursor overrides — Gradio sets `cursor:pointer` on the whole
   message bubble when `select()` is wired; override it to `default` for `.psk-review-chatbot
   .message` and restore `pointer` only on `.psk-extract-btn`.

## Key invariants

- `data-prompt` attr uses `html.escape(..., quote=True)` — extraction reads it directly
  via `data-prompt="([^"]*)"` regex + `html.unescape`. Do not use `_clean_prompt_text` here.
- `_on_message_select` must guard on `"psk-extract-btn"`, NOT `"```"` — code fences are
  replaced by `<pre>` tags in `_ui_history` and are absent from `evt.value`.
- The final yield after `stream_start_review` is critical: without it the chatbot
  stays on the streaming version (no buttons) until the next message is sent.
