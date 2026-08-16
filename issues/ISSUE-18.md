# ISSUE-18: Review chat input not locking during API call (duplicate component in outputs)

**Type:** Bug  
**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `_wire_events` → `send_message`

## Root Cause

`review_input` appeared twice in the `outputs` list of `_send_btn.click` and `review_input.submit`:

```python
outputs=[self.review_chatbot, self.review_input, self.failed_gallery, self.review_input, self._send_btn]
#                              ^ clear value                            ^ toggle interactive
```

In Gradio 5, when the same component appears multiple times in `outputs`, only the last update for that component is applied. The interactive toggle (position 4) would win, but the first yield sent `_input_locked` at position 4 and `""` at position 2 — the conflict meant neither effect was reliably applied, so the input box was neither cleared nor locked.

## Fix

Merged value and interactive into a single `gr.update` per yield:

- First yield: `gr.update(value="", interactive=False)` — clears and locks in one update
- Final yield: `gr.update(interactive=True)` — unlocks (value already empty)

`review_input` now appears exactly once in `outputs`.

## Key Invariant

Never list the same Gradio component twice in an `outputs` list. Combine all property changes for a component into a single `gr.update(...)` call per yield.
