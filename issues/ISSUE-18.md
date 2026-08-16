# ISSUE-18: Review chat input not locking, no progress bar, input not clearing after send

**Type:** Bug  
**Status:** Fixed (attempt 8)  
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

## Root Cause 4 — Progress bar on all outputs + double "..." (attempts 4–5 regression)

`progress=gr.Progress()` in `send_message` attaches the GENERATING overlay to every component
in the `outputs` list — chatbot, input, gallery, AND button all showed a progress bar.

Separately, the first yield included a manual `{"role": "assistant", "content": "..."}` pending
message. Gradio 5's `gr.Chatbot` also renders its own native loading indicator for running
generators. This produced two "..." at once.

**Fix (attempt 5):** Removed `progress=gr.Progress()`. Removed the manual "..." relying on
Gradio's native chatbot pending indicator. However this removed all loading feedback (no "...")
and brought back the 1px thin bar (Gradio's built-in generator progress line).

## Root Cause 5 — gr.Progress() cannot be targeted; thin bar returned without it (attempt 6)

`gr.Progress()` attaches to ALL components in `outputs` — there is no per-component targeting.
Removing it brings back Gradio's built-in thin 1px progress line on all outputs.
The double "..." in attempt 4 was our manual `"..."` text + Gradio's streaming cursor rendering
on the same chatbot message bubble simultaneously.

**Fix (attempt 6):** Split `send_message` into three chained events via `.then()`. Progress still absent because `show_progress="hidden"` was on `_send_execute`.

## Root Cause 6 — Progress overlay needed on chatbot only (attempt 7)

`gr.Progress()` overlays ALL visual components in `outputs`. Targeting it to the chatbot alone
requires keeping `gr.State` as the only co-output, since state has no visual representation.

**Fix (attempt 7):** Four chained events, but `review_chatbot` was still in `_send_execute` outputs →
Gradio's chatbot loading state activated alongside the manual "..." (double "..."), and the progress overlay
covered the conversation instead of the chat box.

## Root Cause 7 — chatbot in _send_execute outputs activates chatbot loading state (attempt 8)

With `review_chatbot` in `_send_execute`'s outputs and `gr.Progress()` active, Gradio's chatbot
component activates its loading state, duplicating the manual "..." already placed by `_send_start`.
The progress overlay also covers the chatbot ("conversation"), not the input ("chat box").

**Fix (attempt 8):** Route BOTH chatbot result and gallery through `gr.State` in `_send_execute`.
The only visual component in `_send_execute`'s outputs is `review_input` — that gets the progress
overlay (the "chat box"), while `review_chatbot` is never in outputs during the active API call so
its loading state never activates. A hidden `_flush_results` `.then()` pushes both states to
their visual components after the call completes.

Four chained events:
1. `_send_start(msg)` — sync: "...", lock input (no clear), prior gallery, lock button
2. `_send_execute(progress=gr.Progress())` — outputs `[_chatbot_state, _gallery_state, review_input]`.
   States invisible → overlay on `review_input` only. `review_chatbot` absent → no loading state → no double "..."
3. `_flush_results` — `show_progress="hidden"`: flushes both states to chatbot + gallery
4. `_send_finish()` — clears and unlocks input and button

**Fix (attempt 6):** Split `send_message` into three chained events via `.then()`:
1. `_send_start(msg)` — sync, instant: shows "..." in chatbot, locks input WITHOUT clearing
   (so the next event can read the message), shows prior gallery, locks button.
2. `_send_execute(msg, uploaded)` — sync, `show_progress="hidden"`: does the API call.
   Outputs only `[chatbot, gallery]` — no input or button in outputs, so no progress bar
   pollution on those components. The "..." is replaced with the real response.
3. `_send_finish()` — sync, instant: clears and unlocks input and button.

The "..." in step 1 is the only loading indicator. It comes from a sync (non-generator)
event so Gradio's streaming cursor never activates — no duplicate.

## Key Invariants

- Never list the same Gradio component twice in an `outputs` list — combine all property changes into one `gr.update(...)` per yield.
- Do NOT use `progress=gr.Progress()` in `send_message` — it attaches the GENERATING overlay to every component in `outputs`, flooding the UI with progress bars.
- Do NOT use a single generator function for `send_message` — `gr.Progress()` attaches to all outputs and the streaming cursor doubles the "...". Use the three-event `.then()` chain instead (see above).
- The "..." must be yielded from a sync (non-generator) first event. A sync event has no streaming cursor, so the "..." appears exactly once.
- `_send_start` must lock input WITHOUT clearing it (`gr.update(interactive=False)` only) so `_send_execute` can still read the message. `_send_finish` does the clear.
- Do NOT use a custom `gr.HTML` bar as a progress substitute — it renders below the chatbox, not as an overlay, and the `visible` toggle is unreliable in Gradio 5.
- `gr.update(value="", interactive=False)` works correctly once the outputs list has no duplicate components and no extra HTML component competing for output slots.
