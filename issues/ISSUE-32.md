# ISSUE-32 — [feature] Click assistant message to extract prompt

## What was added

Replaced the "Extract Final Prompt" button at the bottom of the Review tab with direct
click-to-extract on any assistant message in the chatbot. Clicking an assistant message
that contains a prompt copies it to the prompt box and switches to the Generate Images tab.
Clicking a user message or an assistant message with no extractable prompt is a no-op.

## Implementation

- Removed `_extract_btn` field, render, and `.click()` wiring from `WorkflowPanel`.
- Removed the `---` separator and "When satisfied..." label above the old button.
- Renamed `extract_prompt()` → `_on_message_select(evt: gr.SelectData)` which receives
  the clicked message content directly via Gradio's select event data.
- Wired `review_chatbot.select(fn=self._on_message_select, ...)` using the existing
  `_get_extract_outputs()` hook (subclasses can still override the target components).
- Added `elem_classes=["psk-review-chatbot"]` to the chatbot for CSS scoping.
- Added `.psk-review-chatbot .message.bot { cursor: pointer; opacity on hover }` CSS to
  `gallery.css` so assistant bubbles visually signal they are clickable.

## Key invariants

- `_get_extract_outputs()` override contract is unchanged — subclasses that redirect to a
  different target component still work.
- The select event fires for both user and assistant messages; the handler is a no-op
  (returns `gr.update(), gr.update()`) when the content doesn't yield a cleaned prompt.
- `show_progress="hidden"` on the select event — no loading indicator on simple extraction.
