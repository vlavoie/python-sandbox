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

### serialize / deserialize contract (workflow_panel.py)
Panel `serialize()` overrides must call `super().serialize(project_dir)` and extend the returned dict — never reimplement the base fields. The base saves: `current_prompt`, `generated_images`, `iteration_count`, `work_item`, `review_history`, `review_context`, `cost_log`, `image_model`, `image_resolution`, `aspect_ratio`. `deserialize()` must call `super().deserialize(d)` (all subclasses already do this). See ISSUE-30.

### get_ui_outputs / get_ui_restore_values contract (workflow_panel.py)
Each panel exposes these two methods. `get_ui_outputs()` returns the component list;
`get_ui_restore_values()` returns matching `gr.update(...)` values. Subclasses call
`super().get_ui_outputs() + [...]` and `super().get_ui_restore_values() + [...]`.
Count and order must match exactly between the two methods.

### Duplicate component in outputs
Never list the same Gradio component twice in an `outputs` list — Gradio 5 applies only the last update per component. Combine all property changes into a single `gr.update(...)` per yield. For example, clearing value and locking interactive must be one `gr.update(value="", interactive=False)`, not two separate entries.

### Gradio output-only components
`gr.Chatbot` and `gr.HTML` are OUTPUT-ONLY in this codebase.
- Never add `self.review_chatbot` or any gallery to a Gradio `inputs=[]` list.
- The authoritative history is `self.review_history` on the panel object.
- The authoritative images are `self.generated_images` on the panel object.

### gr.Progress() vs show_progress — do not confuse these
`show_progress` on an event controls the loading overlay style. `gr.Progress()` as a function parameter is a completely separate mechanism that draws its own indicator regardless of `show_progress`. **`show_progress="hidden"` does NOT suppress `gr.Progress()`.**

**The invariant that has broken 8+ times — read this before touching event wiring:**
A function that declares `progress=gr.Progress()` MUST NOT have `review_chatbot` in the event's `outputs` list. This has two failure modes:
1. Adding `gr.Progress()` to a function whose event already lists `review_chatbot` in outputs.
2. Adding `review_chatbot` to an event's outputs when the function already has `gr.Progress()`.

Current functions that declare `gr.Progress()`: `generate_images_batch`, `_do_force_generate`, `do_generate_prompt` (all subclasses).
- `generate_images_batch` / `_do_force_generate` outputs: `[output_gallery, failed_gallery, _dup_confirm_row, _gen_images_btn, _gen_anyway_btn]` — no chatbot ✓
- `do_generate_prompt` outputs: `[prompt_box, panel_tabs, _gen_prompt_btn]` — chatbot cleared by a separate `.then()` with no `gr.Progress()` ✓

- `_send_execute` (chat handler) uses `show_progress="full", show_progress_on=self.review_input` — Gradio 5 param that targets the loading overlay to the input only. CRITICAL: `review_input` must NOT be in `_send_execute`'s `outputs` list. Any component in `outputs` that receives a yield gets its loading overlay cleared. `review_input` stays in `inputs` and in `_send_start`/`_send_finish` outputs only. This is the EVENT KWARG mechanism, NOT `gr.Progress()` — `gr.Progress()` is banned. The `generating` CSS state uses `pulseStart` which fades opacity from 0→1 over 1s; `gallery.css` overrides it to start at full opacity.
- `gallery.css` has a `.gradio-container .wrap.generating` override that makes the generating overlay immediately visible (solid background + pulsing opacity). `gallery.js` drives `--psk-timer` on `:root` via `MutationObserver` + `setInterval`; `::after { content: var(--psk-timer, "0s") }` shows the elapsed seconds. CSS-only (@property integer → counter-reset) does NOT work because counter-reset does not re-evaluate on custom-property animation. Do not remove either the CSS or the JS timer block.
- `_send_execute` yields a `{"role": "assistant", "content": "..."}` placeholder immediately before each API call (both start_review and continue paths) to show a thinking indicator in the chatbot during the API wait.
- Generate buttons use `show_progress="minimal"` + `gr.Progress()` (no chatbot in their outputs — safe).
- All other event handlers use `show_progress="hidden"`.
- See ISSUE-23 for full history (8+ attempts, 3 confirmed instances).

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

## Tuning workflow
Create a `tuning/TUNING-N.md` (next number in sequence) for **every prompt or skill adjustment** — changes to `fpv-pov-image.md`, `fpv-pov-review.md`, or prompt-engineering rules.

For each tuning entry, include: the problem observed, what failed and why (root cause in Aurora's behavior), the fix applied (exact skill changes), and the key rule going forward.

**When the same failure resurfaces**, update the existing tuning file in place — append the new observation under a new section. A tuning file is a living record of how to handle a specific model behavior.

After writing or updating the file, add or update the one-line entry in the **Known tuning log** below.

## Known tuning log
Before editing `fpv-pov-image.md` or `fpv-pov-review.md`, read:
- `tuning/TUNING-1.md` — standing FPV horizon defaults to frame top; must use "camera horizon — vanishing-point horizon — at exact vertical center". **TUNING-1b (appended):** downward-tilt FPV of shorter characters — horizon-at-center rule does NOT apply; use gaze direction ("looking up at me") and crown-of-head visibility as primary anchors instead
- `tuning/TUNING-2.md` — finalize prompts must name art style first and describe the full scene as-is; "Starting from IMAGE_1 as unchanged base…" signals a delta and causes style drift
- `tuning/TUNING-3.md` — viewer body parts must use first-person pronouns ("my hand", "I reach"); depersonalized language ("forearms extending", "viewer's arm") causes Aurora to treat them as a separate character's hands
- `tuning/TUNING-4.md` — prior attempt inventory step added to ALL review loops (fpv-pov-review.md, fpv-pov-element.md, finalize prefix); forces model to synthesize full trial record before proposing. **TUNING-4b:** extended to element and finalize after observing same anchoring failure there
- `tuning/TUNING-5.md` — deep reasoning parity for element and finalize: added functional identity check, correction rules (density matters), when-no-feedback handler, and pre-submission check sequence to fpv-pov-element.md and finalize_workflow.py prefix

## Issue workflow
Create an `issues/ISSUE-N.md` (next number in sequence) for **every bug fix AND every new feature**.
This is mandatory — do not skip it, even for small changes.

For a **bug fix**, include: root cause, fix, key invariant.
For a **feature**, include: what was added, API/Gradio behaviour, key invariants to preserve.

**When a fix takes multiple attempts** (bug persists after first fix, approach changes, new root cause found), update the existing issue file in place — do not create a new one. The issue file is a living record: append the new root cause and fix under a new numbered section, and update the key invariants. This is especially important for iterative UI bugs where the first fix is incomplete.

After writing or updating the file:
1. Add or update the one-line entry in the **Known issues log** below (type prefix: bug or feature).
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
- `issues/ISSUE-14.md` — [feature] send_message is a generator; yields user message immediately, then API response
- `issues/ISSUE-15.md` — [bug] element review used FPV review skill; Phase 2 green-paint language leaked into element prompts
- `issues/ISSUE-11.md` — [feature] model-scoped resolution dropdown; resolution param only sent for grok-imagine-image-2.0
- `issues/ISSUE-12.md` — [feature] generation cost display from cost_in_usd_ticks (÷10B → USD)
- `issues/ISSUE-16.md` — [feature] optional element base image (green zone template) for Phase 2 element fill
- `issues/ISSUE-17.md` — [feature] duplicate prompt guard on Generate Images — inline confirm row blocks same-prompt resubmission
- `issues/ISSUE-18.md` — [bug] review chat input not locking — duplicate component in outputs list; Gradio 5 only applies last update per component
- `issues/ISSUE-19.md` — [feature] Finalize tab: one-click lighting/color pass via fpv-pov-finalize.md skill; no green zones, no review loop
- `issues/ISSUE-20.md` — [feature] per-work-item reference snapshots: references/ folder created inside work-item-N/ on iteration 0
- `issues/ISSUE-21.md` — [feature] Review tab for Finalize; extracted _render_review_tab_content/_wire_review_events/_get_extract_outputs helpers to WorkflowPanel
- `issues/ISSUE-22.md` — [bug] review chat progress bar stuck at 0%; fixed by streaming API response token-by-token via stream_chat_completions/stream_review_images/stream_start_review
- `issues/ISSUE-23.md` — [bug] progress indicator on review input; fix: show_progress="full" + show_progress_on + CSS override for .generating overlay (starts at opacity 0; overridden in gallery.css); "..." placeholder yield before API calls; never declare gr.Progress() in handlers with review_chatbot in outputs (4 instances)
- `issues/ISSUE-24.md` — [bug] review_context["original_prompt"] not updated on regenerate; manual prompt edits lost in review
- `issues/ISSUE-25.md` — [feature] disable generate buttons during image generation; _generate_images_for_ui/_force_generate_images_for_ui converted to generators
- `issues/ISSUE-26.md` — [feature] prompt-only review with no images; stream_start_review falls through to text-only API call when current_prompt set
- `issues/ISSUE-27.md` — [feature] content moderation warning bubble; gr.Warning() toast on imagine:content-moderated response code
- `issues/ISSUE-28.md` — [bug] user message bubble empty until first token; Gradio clears generator outputs before first yield — always re-emit desired state as first yield
- `issues/ISSUE-29.md` — [feature] per-prompt and aggregate project cost tracking; cost_log persisted in panel state, shown in work item label
- `issues/ISSUE-30.md` — [bug] FPV and Element serialize() reimplemented base fields; cost_log never saved or loaded for those panels (FPV also missing super().deserialize())
- `issues/ISSUE-31.md` — [feature] image thumbnails in review chat user messages; separate _ui_history (display) from review_history (API); upload box cleared after send
- `issues/ISSUE-32.md` — [feature] "↗ Use this prompt" button injected after prompt code blocks; JS bridge (hidden textbox) → _on_bridge_input; removed Extract button
- `issues/ISSUE-33.md` — [bug] prompt code blocks in review chat render as single line; fix: _inject_extract_buttons converts ``` blocks to inline-styled <pre> — static CSS and JS observers can't reliably beat Gradio's lazily-loaded MarkdownCode component CSS

## Work item / iteration model
- `work_item` increments when `_start_new_prompt()` is called with prior work present
- `iteration_count` resets to 0 on new work item
- Output path: `<project>/<subdir>/work-item-N/<timestamp>_iteration-M/image_X.png`
- FPV outputs: `fpv-outputs/`, element outputs: `element-outputs/`
