# ISSUE-23: [bug] gr.Progress() in _send_execute causes progress overlay on review chatbot

## Root cause

`_send_execute` (the chat streaming generator in `_wire_review_events`) had `progress=gr.Progress()` as a parameter and called `progress(...)` at multiple points. Gradio attaches a loading/progress indicator to any event handler that declares `gr.Progress()` as a parameter. This indicator appears over the chatbot component **regardless of `show_progress` settings** on the event — `show_progress` only controls the loading overlay style, not whether `gr.Progress()` draws its own indicator.

Because `review_chatbot` was in the outputs, the progress indicator rendered over the conversation history on every send.

This bug resurfaced multiple times because:
1. The `progress=gr.Progress()` parameter was left in place while `show_progress` was being tuned.
2. `show_progress="hidden"` does NOT suppress `gr.Progress()` — it only suppresses the component loading overlay. These are two separate Gradio mechanisms.

## Fix

Removed `progress=gr.Progress()` from `_send_execute`'s signature entirely. Removed all `progress(...)` calls inside the function. The streaming token-by-token text is sufficient visual feedback; no `gr.Progress()` is needed.

## Key invariant

**Never add `gr.Progress()` as a parameter to any event handler that has `review_chatbot` in its outputs.** `show_progress` and `gr.Progress()` are independent mechanisms — you cannot suppress a `gr.Progress()` indicator by setting `show_progress="hidden"`. The only way to prevent it from appearing is to not declare the parameter.
