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

**Fix:** Added `self._chat_loading`, a `gr.HTML` component placed between the chatbot and the input row. The progress bar is shown by setting its `value` to an animated CSS HTML string and hidden by setting it back to `""`. The component is always present in the DOM (`visible=True`, no `visible` toggle) — toggling `visible` on a `gr.HTML` in Gradio 5 is unreliable. The animation runs client-side, no polling.

## Root Cause 3 — Input not clearing after response

Two separate fixes were needed:

**Fix attempt 1:** `_input_unlock = gr.update(value="", interactive=True)` — added `value=""` to the unlock update, since Gradio can restore the previously submitted value when re-enabling the component.

**Fix attempt 2 (final):** `gr.update(value="", interactive=False/True)` on a generator yield is unreliable in Gradio 5 — the `interactive` flag can interfere with value application. Replaced with a plain `""` string return for the textbox output on every yield. Plain string returns are applied more reliably than `gr.update()` dicts for textbox clearing in Gradio 5 generators. Interactive locking dropped from the textbox entirely; Send button disable/enable is sufficient to prevent double-sends.

## Key Invariants

- Never list the same Gradio component twice in an `outputs` list — combine all property changes into one `gr.update(...)` per yield.
- Gradio's generator loading spinner disappears after the first yield. Use an explicit `gr.HTML` component for persistent in-flight indicators.
- Toggle `gr.HTML` visibility by changing `value` (empty string = hidden, HTML string = shown), not via the `visible` property — `visible` toggling on `gr.HTML` is unreliable in Gradio 5.
- In Gradio 5 generators, yield plain `""` to clear a `gr.Textbox`, not `gr.update(value="")` — `gr.update()` dicts can fail to apply when combined with `interactive` state changes.
