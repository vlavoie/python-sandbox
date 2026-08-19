# Pasokon — Claude Code context

This is a Gradio + xAI Aurora FPV POV image generation app.

## Start of session checklist
1. Run `/pasokon` to load the full project context and architecture notes
2. Check `issues/` for any relevant known bugs before touching the review flow,
   project loading logic, or image persistence
3. Check `tuning/` for prompt/skill adjustments before editing `fpv-pov-image.md`,
   `fpv-pov-review.md`, or writing any generation prompts

## Project layout
```
src/pasokon/
  gradio_app.py       — FPVPOVApp, UI wiring, OUTPUTS_PROJECT
  workflow_panel.py   — WorkflowPanel base (generate → review loop)
  fpv_workflow.py     — FPVWorkflowPanel (phase1 + phase2)
  element_workflow.py — ElementWorkflowPanel (isolated element gen)
  project_state.py    — ProjectState (persistence, model prefs)
  grok_client.py      — xAI API client (chat + images/edits)
  gallery_widget.py   — render_gallery_html (base64 inline HTML thumbnails)

issues/               — catalogued bugs with root cause and fix notes
tuning/               — model/prompt adjustments to fpv-pov-image.md and fpv-pov-review.md
.claude/commands/
  pasokon.md          — /pasokon skill: full architecture + invariants
```

## Non-obvious invariants (quick reference)
- `gr.Chatbot` is output-only — never put it in `inputs=[]`
- All `gr.Image` uploads need `image_mode=None` to preserve PNG alpha
- `generated_images` must be permanent paths (from `_save_images_permanently`), never temp paths
- State mutations must happen BEFORE `save_project_state()`, never after
- `OUTPUTS_PROJECT` and `_build_project_outputs()` must stay in sync (count + order)
- `resolution` API param is only for `grok-imagine-image-2.0`
- `_inject_extract_buttons` replaces ` ``` ` fences with `<pre>` tags — raw backticks are gone from `_ui_history`. `_on_message_select` must guard on `"psk-extract-btn"`, NOT `"```"` (see ISSUE-32)
- Wiring `select()` on a `gr.Chatbot` makes Gradio set `cursor:pointer` on ALL messages (user + bot); override with `.psk-review-chatbot * { cursor:default !important }` in gallery.css (see ISSUE-32)
- The chatbot click blocker in `gallery.js` stops all clicks inside `.psk-review-chatbot .message` to prevent accidental extract-button triggers; any new clickable element injected into chat bubbles (buttons, thumbnails, etc.) must be added to its allowlist (`if (e.target.closest('.foo')) return;`) — and given an explicit `cursor` override in gallery.css because `cursor:default !important` blanket-suppresses everything (see ISSUE-31)
- Review chat thumbnails (`review_galleries`) are a `List[List[str]]` parallel to `review_history`; `prior_galleries` must be padded to `len(prior_api_history)` before extension — old saves lack the key entirely and would misalign gallery indices (see ISSUE-31)
