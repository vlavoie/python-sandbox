# Pasokon project context

Load this at the start of any session working on this project.

## What this project is
Gradio + xAI Aurora image generation app for FPV POV image workflows.
Entry point: `src/pasokon/gradio_app.py` → `FPVPOVApp` → `launch()`

## Architecture

```
FPVPOVApp (gradio_app.py)
├── ProjectState (project_state.py)   — persistence, model prefs, skill files
├── FPVWorkflowPanel (fpv_workflow.py) — phase1/phase2 FPV image generation
└── ElementWorkflowPanel (element_workflow.py) — isolated element generation
```

Both panels inherit from `WorkflowPanel` (workflow_panel.py).

## Key contracts — read before touching panel code

### OUTPUTS_PROJECT contract (gradio_app.py)
`OUTPUTS_PROJECT` is a list of Gradio components that receive updates on every project
load/set operation. `_build_project_outputs()` must return exactly the same number of values
in the same order. Any component added to one must be added to both.
Every component must be stored as `self.xyz` — local variables become stale.

### get_ui_outputs / get_ui_restore_values contract (workflow_panel.py)
Each panel exposes these two methods. `get_ui_outputs()` returns the component list;
`get_ui_restore_values()` returns matching `gr.update(...)` values. Subclasses call
`super().get_ui_outputs() + [...]` and `super().get_ui_restore_values() + [...]`.
Count and order must match exactly between the two methods.

### Gradio output-only components
`gr.Chatbot` and `gr.HTML` are OUTPUT-ONLY in this codebase.
- Never add `self.review_chatbot` or any gallery to a Gradio `inputs=[]` list.
- The authoritative history is `self.review_history` on the panel object.
- The authoritative images are `self.generated_images` on the panel object.

### review_context is session-only
`review_context` is NEVER restored from disk. `deserialize()` always sets it to `{}`.
On the first message of a new session, `send_message` detects `review_history` present but
`review_context` empty and silently rebuilds context via `build_review_context(generated_images)`,
then calls `continue_review` — history is preserved.
`start_review` is ONLY called when `review_history` is empty (genuine fresh conversation).
Never call `start_review` when history exists — it unconditionally replaces `review_history`.

### Persistent paths
`self.generated_images` and `review_context["failed_images"]` must always contain
paths that survive a program restart. Use paths from `_save_images_permanently()` output
(`saved_dir / "image_N.png"`). Never store `tempfile.NamedTemporaryFile` paths in
any state that gets serialized.

### Save discipline
Any method that mutates persistent state must call `save_project_state()` before returning.
State mutations not followed by a save are silently lost on program exit.
The save must happen AFTER all state mutations — never before.

## API notes (xAI Aurora)

- Endpoint: `POST /images/edits` (always, even without reference images)
- `resolution: "1k" | "2k"` — only supported by `grok-imagine-image-2.0`; omit for all other models
- `cost_in_usd_ticks` in response `usage`: divide by 10,000,000,000 for USD
- Images referenced in prompts as `<IMAGE_0>`, `<IMAGE_1>`, etc.

## Issue workflow
Create an `issues/ISSUE-N.md` (next number in sequence) for **every bug fix AND every new feature**.
This is mandatory — do not skip it, even for small changes.

For a **bug fix**, include: root cause, fix, key invariant.
For a **feature**, include: what was added, API/Gradio behaviour, key invariants to preserve.

After writing the file:
1. Add a one-line entry to the **Known issues log** below (type prefix: bug or feature).
2. Update `CLAUDE.md` if the change introduces or changes a non-obvious invariant.

## Known issues log
Before making changes to review flow, project loading, or image persistence, read:
- `issues/ISSUE-1.md` — temp paths in generated_images vanish after restart
- `issues/ISSUE-2.md` — save called before review_context update → stale thumbnails
- `issues/ISSUE-3.md` — gr.Chatbot as input truncates history in Gradio 5
- `issues/ISSUE-4.md` — failed_gallery cleared after generation instead of showing new images
- `issues/ISSUE-5.md` — start_review / continue_review didn't save state
- `issues/ISSUE-6.md` — project selector dropdown collapse bug
- `issues/ISSUE-7.md` — gr.Image without image_mode=None strips PNG alpha
- `issues/ISSUE-8.md` — start_review failure silently wiped chatbot and gallery
- `issues/ISSUE-9.md` — review chatbot cleared on every image generation (gr.update(value=[]) in _generate_images_for_ui)
- `issues/ISSUE-10.md` — [bug] start_review called on first post-restart message, wiping history (review_context empty ≠ fresh start)
- `issues/ISSUE-13.md` — [bug] prompt_box was in Generate Prompt tab; moved to top of Generate Images tab
- `issues/ISSUE-11.md` — [feature] model-scoped resolution dropdown; resolution param only sent for grok-imagine-image-2.0
- `issues/ISSUE-12.md` — [feature] generation cost display from cost_in_usd_ticks (÷10B → USD)

## Work item / iteration model
- `work_item` increments when `_start_new_prompt()` is called with prior work present
- `iteration_count` resets to 0 on new work item
- Output path: `<project>/<subdir>/work-item-N/<timestamp>_iteration-M/image_X.png`
- FPV outputs: `fpv-outputs/`, element outputs: `element-outputs/`
