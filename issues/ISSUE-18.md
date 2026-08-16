# ISSUE-18: Review chat input not locking, no progress bar, input not clearing after send

**Type:** Bug  
**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `_wire_events` → `send_message`

## Root Cause 1 — Duplicate component in outputs blocked locking

`review_input` appeared twice in the `outputs` list:

```python
outputs=[self.review_chatbot, self.review_input, self.failed_gallery, self.review_input, self._send_btn]
#                              ^ clear value                            ^ toggle interactive
```

In Gradio 5, when the same component appears multiple times in `outputs`, only the last update for that component is applied. The conflict meant neither the clear nor the lock was reliably applied.

**Fix:** Merge value and interactive into a single `gr.update` per yield. `review_input` now appears exactly once in `outputs`.

## Root Cause 2 — No progress indicator

Gradio's built-in loading spinner disappears after the first yield of a generator (Gradio considers the event "loaded" once the first chunk is delivered). The `"..."` placeholder in the chat was not visually prominent enough.

**Fix:** Added `self._chat_loading`, a `gr.HTML` component placed between the chatbot and the input row. On the first yield it becomes visible with an animated CSS indeterminate progress bar; on every exit path (success, error, no-images) it hides itself. The animation runs client-side — no polling.

## Root Cause 3 — Input not clearing after response

`_input_unlock` was `gr.update(interactive=True)` — no `value` set. When Gradio re-enables the textbox, it can restore the previously submitted value. The textbox appeared cleared on lock (first yield sets `value=""`), but the old text reappeared on unlock.

**Fix:** `_input_unlock = gr.update(value="", interactive=True)` — value is explicitly cleared on every unlock path.

## Key Invariants

- Never list the same Gradio component twice in an `outputs` list — combine all property changes into one `gr.update(...)` per yield.
- Gradio's generator loading spinner disappears after the first yield. Use an explicit `gr.HTML` component for persistent in-flight indicators.
- Always set `value=""` on both lock AND unlock updates for input components that should clear on send.
