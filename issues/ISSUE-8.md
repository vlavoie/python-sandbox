# ISSUE-8: start_review silently clears chatbot and gallery on failure

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `send_message`

## Root Cause
`start_review` returns `([], error_msg, [])` on any failure (missing images, dead paths,
API error). `send_message` blindly used `result[0]` as the new chatbot value, so on failure
the chatbot was set to `[]`, erasing all visible history. The gallery was set to
`render_gallery_html([])` (empty) for the same reason.

Common trigger: projects saved before the permanent-path fix (ISSUE-1) have dead temp paths
in `generated_images`. On load, `review_context = {}` (cleared by deserialize), so the first
message calls `start_review`, which tries to encode the dead paths → FileNotFoundError →
`start_review` returns `([], error, [])` → display wiped.

## Fix
`send_message` now saves `prior_history` and `prior_gallery` before calling `start_review`.
If `result[0]` is empty (failure), it returns the prior history with the error appended
as an assistant message, and keeps the gallery showing `self.generated_images`.

## Migration note
Projects saved before ISSUE-1 was fixed have dead temp paths in `generated_images`.
One re-generation is required to update them to permanent paths. After that, the project
persists correctly across restarts.

## Key Invariant
`send_message` must never produce a visible state worse than what was shown before the call.
On failure, preserve the current display and surface the error message in the chatbot.
