# ISSUE-18: Review chat input not locking, no progress bar, input not clearing after send

**Type:** Bug  
**Status:** Fixed (attempt 5)  
**Files:** `src/pasokon/workflow_panel.py` → `_wire_events` → `send_message`

## Root Cause 1 — Duplicate component in outputs blocked locking

`review_input` appeared twice in the `outputs` list:

```python
outputs=[self.review_chatbot, self.review_input, self.failed_gallery, self.review_input, self._send_btn]
```

In Gradio 5, only the last update per component is applied. Neither the clear nor the lock was reliably applied.

**Fix:** Merged value and interactive into a single `gr.update` per yield. `review_input` now appears exactly once in `outputs`.

## Root Cause 2 — No progress indicator (three attempts)

Gradio's built-in loading spinner disappears after the first yield of a generator (Gradio considers the event "loaded" once the first chunk is delivered).

**Attempt 1:** Added `self._chat_loading` `gr.HTML` component with `visible=False` initial state, toggled via `gr.update(visible=True/False)`. Did not work — `visible` toggling on `gr.HTML` is unreliable in Gradio 5.

**Attempt 2:** Kept `_chat_loading` always present in DOM, toggled content between `""` (hidden) and the loading HTML string. Did not produce the expected progress overlay — rendered as a 1px bar above the chatbox, not an overlay.

**Attempt 3 (current):** Removed `_chat_loading` entirely. Added `progress=gr.Progress()` to `send_message` and call `progress(0, desc="Waiting for response...")` after the first yield. `gr.Progress()` is the same mechanism used by `_do_generate` for image generation and produces the native Gradio "GENERATING..." overlay on the output component.

## Root Cause 3 — Input not clearing / not locking (three attempts)

**Attempt 1:** Added `value=""` to `_input_unlock` — did not reliably clear.

**Attempt 2:** Replaced `gr.update(value="", interactive=False/True)` with plain `""` string returns and dropped interactive locking on the textbox entirely. Text still did not clear; input remained typeable during API call.

**Attempt 3 (current):** Reverted to `gr.update(value="", interactive=False)` on first yield and `gr.update(value="", interactive=True)` on final yield. Now that the duplicate-outputs bug (Root Cause 1) is fully resolved and `_chat_loading` is gone from the outputs list, the `gr.update` dict is applied cleanly with no conflicts.

## Root Cause 4 — Progress bar on all outputs + double "..." (attempt 4 regression)

`progress=gr.Progress()` in `send_message` attaches the GENERATING overlay to every component
in the `outputs` list — chatbot, input, gallery, AND button all showed a progress bar.

Separately, the first yield included a manual `{"role": "assistant", "content": "..."}` pending
message. Gradio 5's `gr.Chatbot` also renders its own native loading indicator for running
generators. This produced two "..." at once.

**Fix (attempt 5):** Removed `progress=gr.Progress()` from the function signature entirely.
Removed the manual "..." from the first yield — Gradio's native chatbot pending indicator
handles loading state on its own. The first yield now contains only the user message plus
the input lock and button lock. No custom progress mechanism needed.

## Key Invariants

- Never list the same Gradio component twice in an `outputs` list — combine all property changes into one `gr.update(...)` per yield.
- Do NOT use `progress=gr.Progress()` in `send_message` — it attaches the GENERATING overlay to every component in `outputs`, flooding the UI with progress bars.
- Do NOT add a manual `{"role": "assistant", "content": "..."}` to the first yield — Gradio 5's `gr.Chatbot` already shows its own native pending indicator for running generators. Adding one manually produces two "..." at once.
- Do NOT use a custom `gr.HTML` bar as a progress substitute — it renders below the chatbox, not as an overlay, and the `visible` toggle is unreliable in Gradio 5.
- `gr.update(value="", interactive=False)` works correctly once the outputs list has no duplicate components and no extra HTML component competing for output slots.
