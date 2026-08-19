# ISSUE-23: [bug] gr.Progress() causes progress overlay on review chatbot

## The invariant

**Never declare `progress=gr.Progress()` as a parameter in any function whose event is wired with `review_chatbot` in `outputs`.** `show_progress` and `gr.Progress()` are completely independent Gradio mechanisms. `show_progress="hidden"` cannot suppress a `gr.Progress()` indicator. The only fix is to not declare the parameter in that function.

---

## Instance 1 — _send_execute

### Root cause

`_send_execute` (the chat streaming generator in `_wire_review_events`) had `progress=gr.Progress()` as a parameter. Because `review_chatbot` was in the event outputs, the indicator rendered over the conversation history on every message send.

The bug resurfaced multiple times because `show_progress="hidden"` was tuned repeatedly while the `gr.Progress()` parameter was left in place — these two mechanisms do not interact.

### Fix

Removed `progress=gr.Progress()` from `_send_execute`'s signature and all `progress(...)` calls. Streaming token-by-token text is sufficient visual feedback.

---

## Instance 2 — do_generate_prompt (all subclasses)

### Root cause

`do_generate_prompt` in `FPVWorkflowPanel`, `FinalizeWorkflowPanel`, and `ElementWorkflowPanel` all declared `progress=gr.Progress()`. The event wiring in `workflow_panel.py` listed `review_chatbot` as the third output:

```python
outputs=[self.prompt_box, self.panel_tabs, self.review_chatbot, self._gen_prompt_btn]
```

This caused a progress overlay on the chatbot any time "Generate Prompt" was clicked, even though the user is on a different tab.

### Fix

Split the event chain: removed `review_chatbot` from `do_generate_prompt`'s outputs and appended a separate `.then()` step to clear it:

```python
.then(
    fn=self.do_generate_prompt,
    inputs=self.get_prompt_tab_inputs(),
    outputs=[self.prompt_box, self.panel_tabs, self._gen_prompt_btn],
    show_progress="minimal",
).then(
    fn=lambda: gr.update(value=[]),
    outputs=[self.review_chatbot],
    show_progress="hidden",
)
```

`_start_new_prompt()` already clears `self.review_history` — so the chatbot clear in the new `.then()` is consistent with internal state. All four yields in each subclass's `do_generate_prompt` removed the third position `gr.update(value=[])`.

---

## Instance 3 — show_progress="hidden" on _send_execute kills all visual feedback

### Root cause

After Instance 1 removed `gr.Progress()` from `_send_execute`, `show_progress="hidden"` was left in place and was also incorrectly codified in `pasokon.md` as the rule for ALL event handlers. With `show_progress="hidden"` and no `gr.Progress()`, there is NO loading indicator at all during streaming — the input locks but the UI looks frozen.

The bug resurfaces whenever a contributor reads the pasokon invariant "all event handlers use `show_progress='hidden'`" and applies it literally to `_send_execute`.

### Fix

Changed `_send_execute`'s event kwargs from `show_progress="hidden"` to `show_progress="minimal"`. This is safe because:
- `show_progress` controls the native Gradio loading overlay style — it is NOT `gr.Progress()`
- `show_progress="minimal"` does NOT declare a `gr.Progress()` parameter, so it does not cause the GENERATING overlay on the chatbot
- The loading indicator persists for the full duration of the streaming generator
- Updated `pasokon.md` invariant to explicitly state `_send_execute` uses `"minimal"`, not `"hidden"`

### Note on gr.MultimodalTextbox

`gr.MultimodalTextbox` (Gradio 5) combines text input + file upload + submit button into one component. It was evaluated as a potential "better integrated input" but is not the right fit: the existing `gr.File` is a deliberate pre-chat image-upload flow (separate from message text), and switching would change the input format and interaction model without improving the progress indicator situation.

---

## Full chatbox progress history

This is the canonical reference for all progress-bar-over-chatbot incidents. Complete history of every attempt across ISSUE-14, 18, 22, 23:

| Session | Change | Effect |
|---|---|---|
| ISSUE-14 | Made send_message a generator to show user message immediately | Introduced streaming generator pattern |
| ISSUE-18 attempt 1–7 | Various show_progress tweaks, duplicate in outputs | Did not fix; show_progress cannot suppress gr.Progress() |
| ISSUE-18 attempt 8 | Routed chatbot through gr.State; review_chatbot absent from _send_execute outputs | Fixed by REMOVING chatbot from outputs entirely |
| ISSUE-22 | Refactored to streaming SSE; put review_chatbot back in _send_execute outputs WITH gr.Progress() | Broke attempt-8 invariant; progress bar returned |
| ISSUE-23 instance 1 | Removed gr.Progress() from _send_execute | Fixed for chat send path |
| ISSUE-23 instance 2 | Removed review_chatbot from do_generate_prompt outputs | Fixed for generate prompt path |
| ISSUE-23 instance 3 | show_progress left as "hidden" after removing gr.Progress() → no indicator. Fixed: show_progress="minimal" | Fixed: loading indicator restored without gr.Progress() |

**The pattern that keeps breaking this:** a refactor puts `review_chatbot` in new event outputs OR adds `gr.Progress()` to a function that already had `review_chatbot` in its outputs. Both are violations of the same invariant. A secondary failure mode: removing `gr.Progress()` without switching `show_progress` from `"hidden"` to `"minimal"` silently removes all visual feedback.
