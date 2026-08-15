# Pasokon — Claude Code context

This is a Gradio + xAI Aurora FPV POV image generation app.

## Start of session checklist
1. Run `/pasokon` to load the full project context and architecture notes
2. Check `issues/` for any relevant known bugs before touching the review flow,
   project loading logic, or image persistence

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
