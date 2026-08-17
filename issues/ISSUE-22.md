# ISSUE-22: Review chat progress bar never advances

**Type:** Bug  
**Status:** Fixed  
**Files:**
- `src/pasokon/grok_client.py` — added `_build_review_content()`, `stream_review_images()`, `stream_chat_completions()`
- `src/pasokon/workflow_panel.py` — added `_build_continue_review_messages()`, `stream_start_review()`; rewrote `_send_execute` as a streaming generator

## Root cause

`_send_execute` called `progress(0, desc="Waiting for response...")` at the start, then made a single blocking HTTP call (via `continue_review` or `start_review`). The progress bar sat at 0% for 15–60 seconds until the call completed — there was no mechanism to advance it during a single synchronous request.

Additionally, `review_chatbot` was not in `_send_execute`'s outputs (to avoid double "..." issue), so there was no visual feedback in the chatbot while waiting either.

## Fix

Converted the entire send path to streaming:

- `GrokClient.stream_chat_completions(messages)` — generic SSE streaming generator. Calls `/chat/completions` with `"stream": true` and yields partial tokens via `resp.iter_lines()`.
- `GrokClient.stream_review_images(...)` — streaming variant of `review_images()`. Shares content-building logic via the extracted `_build_review_content()` helper.
- `WorkflowPanel._build_continue_review_messages(user_message)` — extracted message-building from `continue_review()` so both the blocking and streaming paths share it.
- `WorkflowPanel.stream_start_review(user_comment, uploaded_files)` — generator version of `start_review()`. Yields `(partial_history, images_reviewed)` tuples as tokens arrive.
- `_send_execute` rewritten as a Gradio generator:
  - Outputs now include `review_chatbot` directly (not `_chatbot_state`).
  - For fresh start: delegates to `stream_start_review()`, forwarding each partial yield.
  - For continue: calls `_build_continue_review_messages()` + `stream_chat_completions()`, yields progressive chatbot updates and advances the progress bar (`min(token_count / 400, 0.95)`).
- `_send_start` no longer injects an `{"role": "assistant", "content": "..."}` pending bubble — Gradio's native typing indicator (shown automatically while a generator with `review_chatbot` in outputs runs) handles the "thinking" state.
- `_flush_results` simplified to `_flush_gallery` — only flushes `_gallery_state` → `failed_gallery`; chatbot is now updated live by `_send_execute`.

## Key invariants

- `stream_chat_completions` and `stream_review_images` both raise on HTTP errors (from `resp.raise_for_status()`); callers catch and show error in chatbot.
- If streaming yields zero tokens, `_send_execute` shows "❌ No response received." and does NOT update `self.review_history`.
- If streaming raises mid-stream (network error), partial content is preserved in the error message.
- `continue_review()` (blocking) is still available as a fallback — it now calls `_build_continue_review_messages()` internally.
- `_chatbot_state` is still created in `_render_review_tab_content` but no longer wired in `_wire_review_events` — left in place to avoid breaking subclass references.
