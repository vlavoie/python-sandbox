# ISSUE-28: [bug] user message bubble empty until first API token arrives

## Root cause

`_send_execute` is a streaming generator attached via `.then()`. Gradio clears the output components of a streaming generator before the first yield. `_send_start` correctly set `review_chatbot` to `pending_history` (including the user's message), but `_send_execute` erased it the moment it started — before any yields — leaving an empty bubble for the full duration of the API wait.

## Fix

Added an immediate first yield at the very top of `_send_execute`, before any API call or context rebuild:

```python
yield gr.update(), prior_history + [{"role": "user", "content": msg}], prior_gallery
```

This re-establishes the user message the instant the generator starts, so the bubble is never visually empty.

## Key invariant

Any streaming generator (`.then()` with a generator function) that has a Gradio component in its outputs MUST yield that component's desired state as its very first yield, before doing any blocking work. Gradio resets outputs at generator start; only the first yield restores them.
