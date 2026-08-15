# ISSUE-14: Review chat message not shown until API response received

**Type:** Feature  
**Status:** Implemented  
**Files:** `src/pasokon/workflow_panel.py` → `send_message`

## What was added
`send_message` was converted from a plain function to a generator. It now yields twice:

1. **Immediately** — appends the user's message plus an `"..."` placeholder assistant bubble
   to the chatbot history and clears the input box. This replaces the Gradio spinner (which
   disappears on the first yield) with an explicit in-chat loading indicator.
2. **After the API call** — yields the full history with the real assistant response (or an
   error message), replacing the placeholder.

The input box is cleared on the first yield so the UI feels responsive regardless of API latency.

## Key invariant
Error paths use `yield ... ; return` (not `return ...`) since the function is now a generator.
Converting any error `return` back to a plain `return` will raise `StopIteration` silently and
Gradio will receive no update — use `yield` + `return` for all early exits.
