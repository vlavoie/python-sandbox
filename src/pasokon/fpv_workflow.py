"""FPVWorkflowPanel: FPV POV prompt generation with Phase 1 / Phase 2 support."""

from typing import Any, List, Optional

import gradio as gr

from .workflow_panel import WorkflowPanel
from .gallery_widget import render_gallery_html


class FPVWorkflowPanel(WorkflowPanel):
    """
    Extends WorkflowPanel with FPV-specific state and UI:
    - Phase 1: generate clean base image from scene description + character reference
    - Phase 2: surgical green-zone addition using a base image + greenzone mask
    - Model selection controls (production + draft)
    """

    def __init__(self, app):
        super().__init__(app)

        # FPV-specific persistent state
        self.reference_image_path: Optional[str] = None
        self.additional_images_paths: List[str] = []
        self.current_scene: str = ""
        self.review_mode: str = "phase1"
        self.greenzone_image_path: Optional[str] = None
        self.current_phase2_description: str = ""
        self.phase1_scene_description: str = ""

        # Gradio component refs (set by render)
        self.reference_image = None
        self.scene_desc = None
        self.additional_images = None
        self.greenzone_image = None

    @property
    def panel_id(self) -> str:
        return "fpv"

    def get_output_subdir(self) -> str:
        return "fpv-outputs"

    # ── WorkflowPanel overrides ───────────────────────────────────────────

    def get_reference_image_path(self) -> Optional[str]:
        return self.reference_image_path

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        if self.review_mode == "phase2":
            return [self.greenzone_image_path] if self.greenzone_image_path else None
        return self.additional_images_paths if self.additional_images_paths else None

    def get_review_skill(self) -> str:
        ps = self.app.project_state
        if self.review_mode != "phase2":
            return ps.review_skill
        prefix = """PHASE 2 REVIEW MODE — IMAGE ASSIGNMENT OVERRIDE
The image assignments below are FIXED for this session. Any conflicting convention in the skill must be IGNORED.

- <IMAGE_0> = CHARACTER REFERENCE — lock all style, appearance, hair color and identity to this image
- <IMAGE_1> = GREEN-MARKED BASE IMAGE — the spatial base to modify surgically

AURORA MODEL CONSTRAINT — applies to all corrected prompts you write:
Aurora ignores negative language entirely ("not", "no", "never", "forbidden", "do not"). Every correction must be written as a positive spatial description of what should appear and where — not as a ban of what failed. Stronger bans never fix failures. The correct fix is always a more precise spatial description placed earlier in the prompt.

When reviewing failed images, check in this order:
1. Was IMAGE_1 preserved exactly outside the green zones? (Primary failure if not — base was regenerated instead of surgically modified)
2. Were elements added only inside the green zones?
3. Was all paint erased?
4. Does the addition style match IMAGE_0?

When writing a corrected prompt, use the Phase 2 structure from the skill:
- Open with: "Starting from IMAGE_1 as the unchanged spatial and compositional base, [what appears in the green zones]."
- Describe the addition spatially: frame position, color/texture matching IMAGE_0.
- State once: "Everything outside the green-marked zones remains identical to IMAGE_1. Green paint fully removed."
- No ban lists. No repetition. Aim for 60–100 words.

---

"""
        return prefix + ps.review_skill

    def build_review_context(self, images_to_review: List[str]) -> dict:
        if self.review_mode == "phase2":
            additional = [self.greenzone_image_path] if self.greenzone_image_path else []
            scene = f"""Phase 2 Enhancement Review:
{self.current_phase2_description}

Context:
- <IMAGE_0> is the character reference for style/appearance (SAME as Phase 1)
- <IMAGE_1> is the green-zoned base image — the canvas to modify surgically
- ONLY add elements inside the green/pink zones on <IMAGE_1>
- Everything OUTSIDE the green zones in <IMAGE_1> must remain completely unchanged
- Erase all green/pink paint afterward so no trace remains
- Lock style and appearance to <IMAGE_0>

A primary failure mode is when the model regenerates the entire image instead of making a surgical local addition — watch for this in the failed images."""
            mode_info = "\n🗂 <IMAGE_1> = Green-zoned base"
        else:
            additional = self.additional_images_paths if self.additional_images_paths else None
            scene = self.current_scene
            mode_info = (
                f"\n🗂 <IMAGE_1>+ = {len(additional)} additional character(s)"
                if additional else ""
            )

        return {
            "failed_images": images_to_review,
            "original_prompt": self.current_prompt,
            "scene_description": scene,
            "reference_image": self.reference_image_path,
            "additional_images": additional,
            "review_mode": self.review_mode,
            "mode_info": mode_info,
        }

    # ── prompt generation ────────────────────────────────────────────────

    def do_generate_prompt(
        self,
        reference_image,
        scene_description: str,
        additional_images,
        greenzone_image,
        progress=gr.Progress(),
    ):
        _btn_reset = gr.update(value="🎯 Generate Prompt", interactive=True)
        _btn_loading = gr.update(value="⏳ Generating prompt...", interactive=False)

        client = self.app.client
        ps = self.app.project_state

        if not client or not reference_image or not scene_description.strip():
            yield gr.update(), gr.update(), gr.update(value=[]), _btn_reset
            return

        is_phase2 = greenzone_image is not None

        self._start_new_prompt()

        yield gr.update(), gr.update(), gr.update(value=[]), _btn_loading

        try:
            progress(0, desc="Preparing images...")
            self.reference_image_path = ps.save_uploaded_file(reference_image)

            self.additional_images_paths = []
            if additional_images:
                for img in additional_images:
                    if img is not None:
                        p = ps.save_uploaded_file(img)
                        if p:
                            self.additional_images_paths.append(p)

            if is_phase2:
                self.greenzone_image_path = ps.save_uploaded_file(greenzone_image)
                self.current_phase2_description = scene_description
                self.review_mode = "phase2"

                full_scene = f"""Phase 2 Enhancement - Green Zone Addition:
{scene_description}

Context:
- <IMAGE_0> is the character reference for style/appearance matching
- <IMAGE_1> is the base image with green/pink zones marking where to add elements
- Only add elements inside the marked zones on <IMAGE_1>
- Completely erase all green/pink paint afterward
- Lock appearance/style to <IMAGE_0>
- Use <IMAGE_1> as the spatial base to modify"""
                self.current_scene = full_scene

                scene_context_section = ""
                if self.phase1_scene_description:
                    scene_context_section = (
                        f"\nPHASE 1 SCENE CONTEXT — what IMAGE_1 shows (use this to understand the scene):\n"
                        f"{self.phase1_scene_description}\n\n"
                    )
                previous_prompt_section = ""
                if self.current_prompt:
                    previous_prompt_section = (
                        f"\nPREVIOUS PHASE 2 PROMPT — iterate from this, refining based on the updated zone description above:\n"
                        f"{self.current_prompt}\n\n"
                    )

                phase2_prefix = (
                    f"PHASE 2 ENHANCEMENT MODE — GREEN ZONE SURGICAL ADDITION\n\n"
                    f"You are generating a Grok Imagine prompt for Phase 2: a surgical local addition to an existing base image.\n\n"
                    f"AURORA MODEL RULES — apply these before generating anything:\n"
                    f"- Aurora ignores negative language (\"not\", \"no\", \"never\", \"forbidden\"). Do not use it.\n"
                    f"- Aurora's first 20–30 tokens dominate the output. Front-load the most critical instruction.\n"
                    f"- Repetition dilutes, not emphasizes. State each element once, precisely, early.\n"
                    f"- Write spatially: describe what appears where in the frame.\n"
                    f"{scene_context_section}{previous_prompt_section}"
                    f"FIXED IMAGE ASSIGNMENT:\n"
                    f"- <IMAGE_0> = CHARACTER REFERENCE — identity, style, appearance, hair color lock to this image\n"
                    f"- <IMAGE_1> = GREEN-MARKED BASE — unchanged spatial base; only the green-painted zones change\n\n"
                    f"PROMPT STRUCTURE — generate in this exact order:\n"
                    f"1. Open with: \"Starting from IMAGE_1 as the unchanged spatial and compositional base, [brief description of what appears in the green-zone areas].\"\n"
                    f"2. Describe the scene from IMAGE_1 briefly so Aurora understands the visual context.\n"
                    f"3. Spatial description of the addition: where in the frame, color/texture/style matching IMAGE_0.\n"
                    f"4. Base statement (once): \"Everything outside the green-marked zones remains identical to IMAGE_1.\"\n"
                    f"5. Paint removal (once): \"Green paint fully removed in the final image.\"\n"
                    f"6. Style anchor: \"[Element] color, texture, and style matches IMAGE_0.\"\n\n"
                    f"For hair/fringe additions at the frame edges, describe as a frame-border detail seen from inside the hairline:\n"
                    f"\"The [left/right/top] frame borders reveal a thin strip of the viewer's own [style] hair — the camera is positioned at eye level within the hairline, making the [bob/fringe/etc.] naturally visible as a narrow frame-border detail at the absolute [left/right] edge, [X]% wide on the left and [Y]% on the right.\"\n"
                    f"This framing avoids characters-at-the-edges misinterpretation. Do NOT use \"strands entering the frame\" — describe it as a static frame-border detail.\n\n"
                    f"If a solid-color exclusion zone is present (e.g. bright pink): \"The [color] area in IMAGE_1 remains exactly as shown.\"\n\n"
                    f"Fill every sentence with specific visual content — materials, lighting quality, colors, textures, atmosphere. Aurora hallucinates into gaps; describe every visible element as completely as possible. No ban lists. No repetition. No upper limit on specificity.\n\n"
                    f"---\n\n"
                )

                progress(0.5, desc="Waiting for Grok API (~30s)...")
                self.current_prompt = client.generate_prompt(
                    reference_image=self.reference_image_path,
                    scene_description=full_scene,
                    skill_content=phase2_prefix + ps.prompt_skill,
                    additional_images=[self.greenzone_image_path],
                )
            else:
                self.greenzone_image_path = None
                self.review_mode = "phase1"
                self.current_scene = scene_description
                self.phase1_scene_description = scene_description
                progress(0.5, desc="Waiting for Grok API (~30s)...")
                self.current_prompt = client.generate_prompt(
                    reference_image=self.reference_image_path,
                    scene_description=scene_description,
                    skill_content=ps.prompt_skill,
                    additional_images=self.additional_images_paths if self.additional_images_paths else None,
                )

            ps.save_project_state()
            progress(1.0, desc="Done")
            yield self.current_prompt, gr.update(selected="fpv_gen_images"), gr.update(value=[]), _btn_reset

        except Exception as e:
            print(f"\nERROR IN PROMPT GENERATION:\n{e}\n")
            yield "", gr.update(), gr.update(value=[]), _btn_reset

    # ── persistence ───────────────────────────────────────────────────────

    def serialize(self, project_dir) -> dict:
        """
        Copy reference images into project_dir/references/ and return the
        full FPV state with stable, project-relative paths.
        """
        ps = self.app.project_state

        saved_ref = (
            ps._copy_image_to_project(self.reference_image_path, "character_reference", project_dir)
            if self.reference_image_path else None
        )
        saved_additional = [
            ps._copy_image_to_project(p, f"additional_{i}", project_dir)
            for i, p in enumerate(self.additional_images_paths or [])
        ]
        saved_gz = (
            ps._copy_image_to_project(self.greenzone_image_path, "greenzone_base", project_dir)
            if self.greenzone_image_path else None
        )

        return {
            "current_prompt": self.current_prompt,
            "current_scene": self.current_scene,
            "reference_image_path": saved_ref,
            "additional_images_paths": saved_additional,
            "generated_images": self.generated_images,
            "iteration_count": self.iteration_count,
            "work_item": self.work_item,
            "review_mode": self.review_mode,
            "greenzone_image_path": saved_gz,
            "current_phase2_description": self.current_phase2_description,
            "phase1_scene_description": self.phase1_scene_description,
            "review_history": self.review_history,
            "review_context": self.review_context,
        }

    def deserialize(self, d: dict) -> None:
        """Restore FPV state from a serialized dict (supports both new and legacy key names)."""
        self.current_prompt = d.get("current_prompt", "")
        self.generated_images = d.get("generated_images", [])
        self.iteration_count = d.get("iteration_count", 0)
        self.work_item = d.get("work_item", 1)
        self.review_history = d.get("review_history") or d.get("phase1_review_history", [])
        self.review_context = d.get("review_context") or d.get("phase1_review_context", {})
        self.current_scene = d.get("current_scene", "")
        self.reference_image_path = d.get("reference_image_path")
        self.additional_images_paths = d.get("additional_images_paths", [])
        self.review_mode = d.get("review_mode", "phase1")
        self.greenzone_image_path = d.get("greenzone_image_path")
        self.current_phase2_description = d.get("current_phase2_description", "")
        self.phase1_scene_description = d.get("phase1_scene_description", "")

    def get_ui_outputs(self) -> List:
        return [
            self.prompt_box,
            self.failed_gallery,
            self.reference_image,
            self.scene_desc,
            self.additional_images,
            self.review_chatbot,
            self.greenzone_image,
            self.output_gallery,
            self.image_model_dropdown,
            self.image_resolution_dropdown,
            self._work_item_label,
        ]

    def get_ui_restore_values(self) -> List:
        ps = self.app.project_state
        is_aurora = ps.image_model == "grok-imagine-image-2.0"
        scene_to_show = (
            self.current_phase2_description if self.review_mode == "phase2"
            else self.current_scene
        )
        ref = self.reference_image_path if self.reference_image_path else None
        gz = self.greenzone_image_path if self.greenzone_image_path else None
        additional = self.additional_images_paths or []
        review_images = self.review_context.get("failed_images", []) if self.review_context else []
        return [
            gr.update(value=self.current_prompt),
            gr.update(value=render_gallery_html(review_images)),
            gr.update(value=ref),
            gr.update(value=scene_to_show),
            gr.update(value=additional),
            gr.update(value=self.review_history),
            gr.update(value=gz),
            gr.update(value=render_gallery_html(self.generated_images or [])),
            gr.update(value=ps.image_model),
            gr.update(value=ps.image_resolution if is_aurora else "auto", interactive=is_aurora),
            gr.update(value=self._work_item_status()),
        ]

    def get_prompt_tab_inputs(self) -> List:
        return [self.reference_image, self.scene_desc, self.additional_images, self.greenzone_image]

    # ── render hooks ─────────────────────────────────────────────────────

    def render_prompt_tab_content(self) -> None:
        gr.Markdown("*Upload a green-zone base image to activate Phase 2 (element addition) mode automatically.*")
        with gr.Row():
            with gr.Column():
                self.reference_image = gr.Image(
                    label="Character Reference (<IMAGE_0>)",
                    type="filepath",
                    image_mode=None,
                )
                self.additional_images = gr.File(
                    label="Additional Characters (optional, Phase 1 only — <IMAGE_1>, <IMAGE_2>…)",
                    file_count="multiple",
                    type="filepath",
                )
            with gr.Column():
                self.scene_desc = gr.Textbox(
                    label="Scene / Enhancement Description",
                    placeholder="Phase 1: describe your scene.\nPhase 2: describe what to add in the green zones.",
                    lines=8,
                )
                self.greenzone_image = gr.Image(
                    label="Green-zone Base Image (optional — triggers Phase 2, <IMAGE_1>)",
                    type="filepath",
                    image_mode=None,
                )

    def _wire_events(self) -> None:
        super()._wire_events()

        # Pre-save uploaded files immediately on change (so Save Now works before Generate Prompt)
        self.reference_image.change(fn=self._on_reference_change, inputs=[self.reference_image])
        self.additional_images.change(fn=self._on_additional_change, inputs=[self.additional_images])
        self.greenzone_image.change(fn=self._on_greenzone_change, inputs=[self.greenzone_image])

    def _on_reference_change(self, ref_image) -> None:
        if ref_image:
            self.reference_image_path = self.app.project_state.save_uploaded_file(ref_image)
        else:
            self.reference_image_path = None

    def _on_additional_change(self, additional_images) -> None:
        self.additional_images_paths = []
        if additional_images:
            for img in additional_images:
                if img is not None:
                    p = self.app.project_state.save_uploaded_file(img)
                    if p:
                        self.additional_images_paths.append(p)

    def _on_greenzone_change(self, greenzone_image) -> None:
        if greenzone_image:
            self.greenzone_image_path = self.app.project_state.save_uploaded_file(greenzone_image)
        else:
            self.greenzone_image_path = None
