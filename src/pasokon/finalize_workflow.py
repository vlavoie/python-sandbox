"""FinalizeWorkflowPanel: lighting/color refinement using the standard workflow."""

from typing import List, Optional

import gradio as gr

from .workflow_panel import WorkflowPanel


class FinalizeWorkflowPanel(WorkflowPanel):
    """
    Final lighting/color pass using the standard three-tab workflow.

    Tab 1 (Generate Prompt): upload source image + optional notes → auto-generate finalize prompt
    Tab 2 (Generate Images): run with the generated (or edited) prompt
    Tab 3 (Review & Correct): standard review loop

    IMAGE_0 = fpv_panel character reference
    IMAGE_1 = source_image_path (the finished image to refine)
    """

    def __init__(self, app):
        super().__init__(app)
        self.source_image_path: Optional[str] = None
        self.notes: str = ""
        self._source_image = None
        self._notes_box = None

    @property
    def panel_id(self) -> str:
        return "finalize"

    @property
    def default_image_resolution(self) -> str:
        return "2k"

    def get_output_subdir(self) -> str:
        return "finalize-outputs"

    def get_reference_image_path(self) -> Optional[str]:
        return self.app.fpv_panel.reference_image_path

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        return [self.source_image_path] if self.source_image_path else None

    def get_work_item_references(self) -> dict:
        refs = {}
        ref = self.get_reference_image_path()
        if ref:
            refs["character_reference"] = ref
        if self.source_image_path:
            refs["source_image"] = self.source_image_path
        return refs

    def get_review_skill(self) -> str:
        ps = self.app.project_state
        prefix = (
            "FINALIZE REVIEW MODE — LIGHTING AND COLOR PASS ANALYSIS\n\n"
            "You are reviewing the output of a finalization pass that was meant to improve "
            "lighting and color quality only. No structural changes should have occurred.\n\n"
            "HOW AURORA RESPONDS TO CORRECTIONS — read this before writing anything:\n\n"
            "Aurora ignores all negative language. 'Not', 'no', 'never', 'do not show', 'forbidden' — "
            "none of it works. The single correction principle: every failure is a description that was "
            "absent or imprecise. The fix is to write that description precisely and place it early in "
            "the prompt. Replace absence with presence, not bans. Repetition and length do not help — "
            "state each fix once, precisely, early.\n\n"
            "IMAGE ASSIGNMENT:\n"
            "- <IMAGE_0> = CHARACTER REFERENCE — identity and appearance lock\n"
            "- <IMAGE_1> = SOURCE IMAGE being refined (spatial base that must be preserved)\n"
            "- Additional images shown = the finalized output(s) being reviewed\n\n"
            "Review checklist (in order):\n"
            "1. Was the spatial composition and structure preserved exactly from IMAGE_1?\n"
            "2. Were character positions, expressions, and poses maintained?\n"
            "3. Did the lighting/color quality improve as intended?\n"
            "4. Were any unintended structural changes introduced?\n\n"
            "WHEN THE USER PROVIDES NO SPECIFIC FEEDBACK:\n\n"
            "When the user says only 'Review these' or gives neutral phrasing:\n"
            "1. Identify the most significant specific failure against IMAGE_1 — something concretely wrong.\n"
            "2. Do NOT repeat the same diagnosis and fix from the previous response. "
            "If the previous fix didn't change the image, the approach was wrong — escalate structurally.\n"
            "3. If the output looks close to intent, state specifically what still fails "
            "(composition drift, lighting didn't improve, identity shifted) then fix only that.\n\n"
            "STEP 0 — PRIOR ATTEMPT INVENTORY (mandatory when history exists):\n\n"
            "Before writing a corrected prompt, write a brief 'Tried so far:' block listing "
            "every structural approach used in prior rounds — one line each. Identify what "
            "changed (or didn't) after each attempt.\n\n"
            "Your new proposal must differ structurally from all prior attempts. "
            "Common finalize failure modes — escalate through these in order if a fix keeps failing:\n"
            "1. Composition drifted: front-load base preservation as the very first clause — "
            "'Starting from IMAGE_1 as the unchanged spatial and compositional base'\n"
            "2. New or wrong elements appeared: strip the prompt to scene description only, "
            "remove any instruction language that gives Aurora creative latitude\n"
            "3. Art style changed: name the art style in the first 5 words\n"
            "4. Character identity changed: strengthen the IMAGE_0 identity lock line\n"
            "5. Lighting didn't improve: add specific quality language to existing light sources only — "
            "never introduce a light source absent from IMAGE_1\n\n"
            "If the same failure persists after 2+ structurally different prompts, "
            "recommend the user try a different model or adjust the source image before retrying.\n\n"
            "FUNCTIONAL IDENTITY CHECK — mandatory before submitting any corrected prompt:\n\n"
            "Compare your corrected prompt to the immediately preceding prompt. Ask: what structurally changed?\n"
            "- If the only change is adding quality adjectives ('rich', 'luminous', 'warm glow') without "
            "changing which light sources are named or where they are described, the prompts are "
            "functionally identical — Aurora cannot distinguish them. Do not submit.\n"
            "- If the only change is rephrasing while keeping the same scene structure, functionally identical.\n"
            "- Structural changes are: reordering the opening (style first vs. scene first), "
            "removing the scene description entirely and rebuilding from scratch, changing which "
            "light sources are foregrounded, adding or removing the spatial reproduction clause, "
            "or switching to a completely different approach from the escalation list above.\n"
            "- If you cannot identify a structural change not already tried, invoke deadlock immediately.\n\n"
            "CORRECTION RULES:\n\n"
            "- The fix must appear in the first 20 tokens of the corrected prompt.\n"
            "- First-person pronouns for viewer body parts: 'my right hand', 'my forearm', 'I reach' — "
            "never 'the hand' or 'viewer's arm'.\n"
            "- No ban lists. No 'not', 'no', 'never', 'do not'.\n"
            "- No repetition — state each element once.\n"
            "- Preserve what was working. If the identity was correct and only the composition drifted, "
            "rewrite only the composition opening. Keep the good parts.\n"
            "- Density matters: Aurora hallucinates into gaps. A sparse description invites the model to "
            "reinterpret the scene. Describe every visible element completely — lighting quality, materials, "
            "character position, scene depth — even when instructing it to 'reproduce exactly'. "
            "'Warm lighting in the scene' is a gap. 'Warm amber light from the bedside lamp at the right, "
            "casting gentle fill across the white duvet and the character's face' closes it.\n\n"
            "PRE-SUBMISSION CHECKS:\n\n"
            "1. Ban list scan: Does your prompt contain 'no', 'not', 'never', 'do not', 'forbidden'? "
            "Delete every instance. Replace with a positive description of what IS present.\n"
            "2. Functional identity check: Is the change structural or only incremental? "
            "If incremental, escalate to the next item in the failure mode list.\n"
            "3. Deadlock check: Have the last 2 prompts produced the same result? "
            "If yes — stop. Switch technique entirely. Do not submit another variation.\n\n"
            "OUTPUT FORMAT:\n\n"
            "When writing a corrected prompt:\n"
            "- Short blurb (1–3 sentences): what failed, what was absent or imprecise, "
            "what you changed and why this targets the failure.\n"
            "- The corrected prompt inside a single markdown code block.\n"
            "- Open with art style + 'Starting from IMAGE_1 as the unchanged spatial and compositional base'.\n"
            "- Keep the prompt to 50–80 words.\n"
            "- Close with: 'All character positions, expressions, clothing, spatial composition, "
            "and image structure remain exactly as in IMAGE_1.'\n"
            "- No structural changes, no new characters, no green zones.\n\n"
            "---\n\n"
        )
        return prefix + ps.review_skill

    def build_review_context(self, images_to_review: List[str]) -> dict:
        fpv = self.app.fpv_panel
        scene_ctx = (fpv.phase1_scene_description or fpv.current_scene or "").strip()
        notes_part = f"\nUser notes: {self.notes.strip()}" if self.notes and self.notes.strip() else ""
        scene = (
            f"Finalize pass review: {scene_ctx}{notes_part}"
            if scene_ctx
            else (self.notes.strip() or "Lighting and color refinement pass.")
        )
        return {
            "failed_images": images_to_review,
            "original_prompt": self.current_prompt,
            "scene_description": scene,
            "reference_image": self.get_reference_image_path(),
            "additional_images": [self.source_image_path] if self.source_image_path else None,
            "review_mode": "finalize",
            "mode_info": "\n🗂 <IMAGE_1> = Source image being refined",
        }

    def do_generate_prompt(self, source_image, notes, progress=gr.Progress()):
        _btn_reset = gr.update(value="🎯 Generate Prompt", interactive=True)
        _btn_loading = gr.update(value="⏳ Generating prompt...", interactive=False)

        client = self.app.client
        ps = self.app.project_state

        if not client or not source_image or not self.get_reference_image_path():
            yield gr.update(), gr.update(), _btn_reset
            return

        self._start_new_prompt()

        yield gr.update(), gr.update(), _btn_loading

        try:
            progress(0, desc="Preparing images...")
            self.source_image_path = ps.save_uploaded_file(source_image)
            self.notes = notes or ""

            fpv = self.app.fpv_panel
            scene_ctx = (fpv.phase1_scene_description or fpv.current_scene or "").strip()
            notes_part = f"\nUser notes: {notes.strip()}" if notes and notes.strip() else ""
            prompt_input = (
                f"Scene context: {scene_ctx}{notes_part}"
                if scene_ctx
                else (notes.strip() or "Refine lighting and color.")
            )

            progress(0.5, desc="Waiting for Grok API (~30s)...")
            self.current_prompt = client.generate_prompt(
                reference_image=self.get_reference_image_path(),
                scene_description=prompt_input,
                skill_content=ps.finalize_skill,
                additional_images=[self.source_image_path],
            )

            ps.save_project_state()
            progress(1.0, desc="Done")
            yield self.current_prompt, gr.update(selected="finalize_gen_images"), _btn_reset

        except Exception as e:
            print(f"\nERROR IN FINALIZE PROMPT GENERATION:\n{e}\n")
            yield "", gr.update(), _btn_reset

    # ── persistence ───────────────────────────────────────────────────────

    def serialize(self, project_dir) -> dict:
        d = super().serialize(project_dir)
        d["source_image_path"] = self.source_image_path
        d["notes"] = self.notes
        return d

    def deserialize(self, d: dict) -> None:
        super().deserialize(d)
        self.source_image_path = d.get("source_image_path")
        self.notes = d.get("notes", "")

    def get_ui_outputs(self) -> List:
        return super().get_ui_outputs() + [self._source_image, self._notes_box]

    def get_ui_restore_values(self) -> List:
        return super().get_ui_restore_values() + [
            gr.update(value=self.source_image_path),
            gr.update(value=self.notes),
        ]

    # ── render hooks ─────────────────────────────────────────────────────

    def render_prompt_tab_content(self) -> None:
        gr.Markdown(
            "*Upload the finished image and optionally describe what to fix. "
            "The prompt is auto-generated from the finalize skill.*"
        )
        with gr.Row():
            self._source_image = gr.Image(
                label="Finished Image to Refine (<IMAGE_1>)",
                type="filepath",
                image_mode=None,
                sources=["upload"],
            )
            self._notes_box = gr.Textbox(
                label="Optional Notes",
                lines=6,
                placeholder="e.g. warmer tones, reduce harsh shadows, richer ambient light",
            )

    def get_prompt_tab_inputs(self) -> List:
        return [self._source_image, self._notes_box]

    def _wire_events(self) -> None:
        super()._wire_events()
        self._source_image.change(fn=self._on_source_change, inputs=[self._source_image], show_progress="hidden")

    def _on_source_change(self, img) -> None:
        if img:
            self.source_image_path = self.app.project_state.save_uploaded_file(img)
        else:
            self.source_image_path = None
