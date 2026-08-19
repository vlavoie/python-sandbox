# ISSUE-32 — [feature] Click prompt code block button to extract prompt

## What was added

Replaced the "Extract Final Prompt" button at the bottom of the Review tab with a
small "↗ Use this prompt" button rendered directly after each prompt code block in
the assistant's messages. Clicking that button copies the prompt to the prompt box
and switches to the Generate Images tab.

## Implementation

### JS bridge pattern (JS → hidden textbox → Python handler)

`review_chatbot.select()` fires on ANY click in the chatbot, so it can't distinguish
prompt-block clicks from other clicks. Instead we use a hidden `gr.Textbox` as a bridge:
1. `_inject_extract_buttons(content)` appends a `<button class="psk-extract-btn"
   data-panel="{panel_id}" data-prompt="{escaped}">↗ Use this prompt</button>` after
   each ` ``` `block that yields a non-empty `_clean_prompt_text`.
2. `gallery.js` intercepts clicks on `.psk-extract-btn`, reads `data-prompt` and
   `data-panel`, writes the prompt into `#psk-bridge-{panel_id} textarea`, and
   dispatches an `input` event so Gradio picks it up.
3. `_prompt_bridge.input` fires `_on_bridge_input` which returns the prompt to
   `prompt_box` and switches the tab.

### Where buttons are injected

- **`_send_execute` continue path**: injects into `display_content` before the final
  `_ui_history` assignment and last yield.
- **`stream_start_review` path**: injects into the tail slice of `review_history`
  when syncing `_ui_history`.
- **`deserialize`**: injects into the copy of `review_history` used as `_ui_history`
  so restored sessions show buttons immediately on load.

### Other changes

- `_extract_btn`, `extract_prompt()`, and the separator/label UI are removed.
- `_prompt_bridge = gr.Textbox(visible=False, elem_id=f"psk-bridge-{self.panel_id}")`
  added in `_render_review_tab_content`.
- `.psk-extract-btn` button styles added to `gallery.css`.
- `_get_extract_outputs()` override contract is unchanged.
- `review_history` (the API history) is never modified — buttons are only in `_ui_history`.

## Key invariants

- `data-prompt` is `html.escape(..., quote=True)` — browser unescapes it in `dataset.prompt`.
- The bridge textbox per-panel (`psk-bridge-fpv`, `psk-bridge-element`, `psk-bridge-finalize`)
  avoids cross-panel conflicts when multiple panels are rendered simultaneously.
