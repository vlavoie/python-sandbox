# ISSUE-10: Review conversation history wiped on first message after session restart

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `send_message`

## Root Cause
`send_message` checked `if not self.review_history or not self.review_context` to decide
between `start_review` and `continue_review`. After a session restart, `deserialize()` always
clears `review_context = {}` (session-only), so `not self.review_context` was always True
even when `review_history` had a full conversation restored from disk.

This caused `start_review` to be called, which unconditionally overwrites `self.review_history`
with a fresh 2-message list — wiping all prior conversation history on the first message after
every restart.

## Fix
`send_message` now checks the two conditions independently:

1. If `review_history` exists but `review_context` is empty (restart recovery): silently call
   `build_review_context(generated_images)` to rebuild context, then fall through to
   `continue_review`. History is preserved.
2. If `review_history` is empty: call `start_review` as before (genuine fresh start).

If `generated_images` is also empty during restart recovery, show an error in the chat and
preserve display rather than wiping it.

## Key Invariant
`start_review` must only be called when `review_history` is empty (no prior conversation).
Never call it when history exists — it unconditionally replaces `review_history`.
`review_context` being empty is not a signal to start fresh; it only means the session was
restarted and context needs to be rebuilt from `generated_images`.
