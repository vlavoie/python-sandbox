# ISSUE-3: Review conversation history shows only last message / corrupts on reload

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `send_message`, `continue_review`, `extract_prompt`

## Root Cause
`send_message` fed `self.review_chatbot` as a Gradio input to obtain the current history.
`gr.Chatbot` with `type="messages"` in Gradio 5 does not reliably return its full message list
when used as a function input — it may return an empty list or only recent messages.
`continue_review` then built `new_history = history + [...]` on top of a truncated list,
losing prior turns. `extract_prompt` also took `history` from the chatbot input.

## Fix
Removed `self.review_chatbot` from ALL Gradio input lists. All review methods now read
`self.review_history` directly — this is always the authoritative, complete copy.

- `send_message(msg, uploaded)` — no longer takes a `history` parameter
- `continue_review(user_message)` — no longer takes a `history` parameter; reads `self.review_history`
- `extract_prompt()` — no longer takes a `history` parameter; reads `self.review_history`

## Key Invariant
`gr.Chatbot` is OUTPUT-ONLY in this codebase. Never add it to a Gradio `inputs=[]` list.
The single source of truth for conversation history is `self.review_history` on the panel object.
