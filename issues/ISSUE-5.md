# ISSUE-5: Project state not saved after review LLM responses

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `start_review`, `continue_review`

## Root Cause
`generate_images_batch` called `save_project_state()` after generation, but neither
`start_review` nor `continue_review` did. Closing the program after receiving a review
response but before the next user action lost the entire conversation turn.

## Fix
Added `self.app.project_state.save_project_state()` at the end of both:
- `start_review` — saves after setting `self.review_history` with the first exchange
- `continue_review` — saves after appending the new exchange to `self.review_history`

## Key Invariant
Any method that mutates persistent state (review_history, generated_images, current_prompt,
etc.) must call `save_project_state()` before returning. State changes are not durable until saved.
