# ISSUE-26: [feature] Prompt-only review — start a review with no images generated

## What was added

`stream_start_review()` previously hard-blocked when `images_to_review` was empty, returning an error message. It now falls through to a prompt-only review path when `self.current_prompt` is set but no images exist.

The prompt-only path:
- Builds a text-only message (plus reference image and additional refs if available)
- Adds an instruction telling the reviewer to predict Aurora failure modes from the prompt text alone, using the same spatial analysis as if a failed output had been seen
- Streams the response via `client.stream_chat_completions()`
- Sets `self.review_context` with `failed_images=[]` so follow-up messages work correctly through `_build_continue_review_messages`

The only remaining hard block: no prompt AND no images → returns "❌ No prompt or images to review yet."

## Key invariants

- `_build_continue_review_messages` already handles empty `failed_images` and absent `reference_image` gracefully — no changes needed there.
- `review_context` must be set even for prompt-only reviews so the continue path works on follow-up messages.
- After generating images, a fresh review starts a new conversation and picks up the images normally.
