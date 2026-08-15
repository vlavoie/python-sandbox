"""ElementWorkflowPanel: isolated FPV element generation for GIMP compositing."""

from typing import List, Optional

import gradio as gr

from .workflow_panel import WorkflowPanel


class ElementWorkflowPanel(WorkflowPanel):
    """
    Extends WorkflowPanel for isolated FPV element generation.

    Generate Prompt tab: reference image + element description + background color.
    Generate Images tab: standard sliders.
    Review tab: standard review conversation.

    The element skill (fpv-pov-element.md) is used instead of the FPV image skill.
    """

    def __init__(self, app):
        super().__init__(app)

        # Element-specific persistent state
        self.element_reference_path: Optional[str] = None
        self.element_description: str = ""
        self.background_color: str = "Auto"

        # Gradio component refs (set by render)
        self.element_reference = None
        self.element_desc_box = None
        self.element_bg_radio = None

    @property
    def panel_id(self) -> str:
        return "element"

    def get_output_subdir(self) -> str:
        return "element-outputs"

    def _effective_reference(self) -> Optional[str]:
        """Element-specific reference, falling back to FPV panel's reference."""
        return self.element_reference_path or self.app.fpv_panel.reference_image_path

    def get_reference_image_path(self) -> Optional[str]:
        return self._effective_reference()

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        return None

    def get_review_skill(self) -> str:
        return self.app.project_state.review_skill

    def build_review_context(self, images_to_review: List[str]) -> dict:
        return {
            "failed_images": images_to_review,
            "original_prompt": self.current_prompt,
            "scene_description": f"FPV element: {self.element_description}\nBackground: {self.background_color}",
            "reference_image": self._effective_reference(),
            "additional_images": None,
            "review_mode": "phase1",
            "mode_info": "",
        }

    # ── prompt generation ────────────────────────────────────────────────

    def do_generate_prompt(
        self,
        reference_image,
        element_description: str,
        background_color: str,
        progress=gr.Progress(),
    ):
        _btn_reset = gr.update(value="🎯 Generate Prompt", interactive=True)
        _btn_loading = gr.update(value="⏳ Generating prompt...", interactive=False)

        client = self.app.client
        ps = self.app.project_state

        # Allow empty element reference — fall back to FPV panel's reference
        effective_ref = reference_image or self.app.fpv_panel.reference_image_path
        if not client or not effective_ref or not element_description.strip():
            yield gr.update(), gr.update(), gr.update(value=[]), _btn_reset
            return

        # New prompt → fresh review state
        self.review_history = []
        self.review_context = {}

        yield gr.update(), gr.update(), gr.update(value=[]), _btn_loading

        try:
            if reference_image:
                progress(0, desc="Saving reference...")
                self.element_reference_path = ps.save_uploaded_file(reference_image)
            self.element_description = element_description
            self.background_color = background_color

            bg_descriptions = {
                "White": "solid white (#FFFFFF)",
                "Chroma Green": "solid chroma green (#00FF00)",
                "Auto": (
                    "Auto — examine IMAGE_0 and the element description, then choose the "
                    "background color that is most distinct from the element's colors: "
                    "solid white (#FFFFFF) for dark elements (dark hair, dark fabric, deep shadows), "
                    "solid chroma green (#00FF00) for light elements (skin tones, light hair, light fabric). "
                    "State your choice on the first line of your response as: Background choice: [color]"
                ),
            }
            bg_desc = bg_descriptions.get(background_color, "solid white (#FFFFFF)")
            element_scene = (
                f"FPV element to generate:\n{element_description}\n\nBackground: {bg_desc}"
            )

            progress(0.5, desc="Waiting for Grok API (~30s)...")
            self.current_prompt = client.generate_prompt(
                reference_image=self._effective_reference(),
                scene_description=element_scene,
                skill_content=ps.element_skill,
            )

            ps.save_project_state()
            progress(1.0, desc="Done")
            yield self.current_prompt, gr.update(selected="element_gen_images"), gr.update(value=[]), _btn_reset

        except Exception as e:
            print(f"\nERROR IN ELEMENT PROMPT GENERATION:\n{e}\n")
            yield "", gr.update(), gr.update(value=[]), _btn_reset

    # ── persistence ───────────────────────────────────────────────────────

    def serialize(self, project_dir) -> dict:
        return {
            "current_prompt": self.current_prompt,
            "generated_images": self.generated_images,
            "iteration_count": self.iteration_count,
            "review_history": self.review_history,
            "review_context": self.review_context,
            "element_reference_path": self.element_reference_path,
            "element_description": self.element_description,
            "background_color": self.background_color,
        }

    def deserialize(self, d: dict) -> None:
        super().deserialize(d)
        self.element_reference_path = d.get("element_reference_path")
        self.element_description = d.get("element_description", "")
        self.background_color = d.get("background_color", "Auto")

    def get_ui_outputs(self) -> List:
        return super().get_ui_outputs() + [
            self.element_reference,
            self.element_desc_box,
            self.element_bg_radio,
        ]

    def get_ui_restore_values(self) -> List:
        return super().get_ui_restore_values() + [
            gr.update(value=self.element_reference_path),
            gr.update(value=self.element_description),
            gr.update(value=self.background_color),
        ]

    def get_prompt_tab_inputs(self) -> List:
        return [self.element_reference, self.element_desc_box, self.element_bg_radio]

    # ── render hooks ─────────────────────────────────────────────────────

    def render_prompt_tab_content(self) -> None:
        gr.Markdown(
            "Generate a first-person perspective element (hair fringe, arm, shoulder, etc.) "
            "isolated on a solid background — remove it in GIMP with **Colors → Color to Alpha**."
        )
        with gr.Row():
            self.element_reference = gr.Image(
                label="Character Reference (optional — uses FPV reference if empty)",
                type="filepath",
                image_mode=None,
                sources=["upload"],
                height=220,
            )
            with gr.Column():
                self.element_desc_box = gr.Textbox(
                    label="Element Description",
                    lines=5,
                    placeholder=(
                        "e.g. Short straight square dark anime bob hair fringe, seen at the top and "
                        "left-side edges of the first-person view, head slightly turned right"
                    ),
                )
                self.element_bg_radio = gr.Radio(
                    choices=["Auto", "White", "Chroma Green"],
                    value="Auto",
                    label="Background Color",
                    info="Auto → LLM picks based on element colors. White → dark hair/clothing. Chroma Green → skin tones or light elements.",
                )

    def _wire_events(self) -> None:
        super()._wire_events()

        self.element_reference.change(
            fn=self._on_reference_change,
            inputs=[self.element_reference],
        )

    def _on_reference_change(self, ref_image) -> None:
        if ref_image:
            self.element_reference_path = self.app.project_state.save_uploaded_file(ref_image)
        else:
            self.element_reference_path = None
