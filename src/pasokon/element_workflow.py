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
        self.background_color: str = "Magenta"

        # Gradio component refs (set by render)
        self.element_reference = None
        self.element_desc_box = None
        self.element_bg_radio = None

    @property
    def panel_id(self) -> str:
        return "element"

    def get_output_subdir(self) -> str:
        return "element-outputs"

    def get_reference_image_path(self) -> Optional[str]:
        return self.element_reference_path

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        return None

    def get_review_skill(self) -> str:
        return self.app.project_state.review_skill

    def build_review_context(self, images_to_review: List[str]) -> dict:
        return {
            "failed_images": images_to_review,
            "original_prompt": self.current_prompt,
            "scene_description": f"FPV element: {self.element_description}\nBackground: {self.background_color}",
            "reference_image": self.element_reference_path,
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

        if not client or not reference_image or not element_description.strip():
            yield gr.update(), gr.update(), gr.update(value=[]), _btn_reset
            return

        # New prompt → fresh review state
        self.review_history = []
        self.review_context = {}

        yield gr.update(), gr.update(), gr.update(value=[]), _btn_loading

        try:
            progress(0, desc="Saving reference...")
            self.element_reference_path = ps.save_uploaded_file(reference_image)
            self.element_description = element_description
            self.background_color = background_color

            bg_descriptions = {
                "Magenta": "solid bright magenta (#FF00FF)",
                "Chroma Green": "solid chroma green (#00FF00)",
                "White": "solid white (#FFFFFF)",
            }
            bg_desc = bg_descriptions.get(background_color, "solid bright magenta (#FF00FF)")
            element_scene = (
                f"FPV element to generate:\n{element_description}\n\nBackground: {bg_desc}"
            )

            progress(0.5, desc="Waiting for Grok API (~30s)...")
            self.current_prompt = client.generate_prompt(
                reference_image=self.element_reference_path,
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
        self.background_color = d.get("background_color", "Magenta")

    # get_ui_outputs() and get_ui_restore_values() inherited from WorkflowPanel —
    # they include prompt_box, failed_gallery, output_gallery, review_chatbot,
    # image_model_dropdown, draft_model_dropdown, draft_aspect_ratio_dropdown.

    def get_prompt_tab_inputs(self) -> List:
        return [self.element_reference, self.element_desc_box, self.element_bg_radio]

    # ── render hooks ─────────────────────────────────────────────────────

    def render_prompt_tab_content(self) -> None:
        gr.Markdown(
            "Generate a first-person perspective element (hair fringe, arm, shoulder, etc.) "
            "isolated against a chroma background — ready to warp and composite in GIMP."
        )
        with gr.Row():
            self.element_reference = gr.Image(
                label="Character Reference (IMAGE_0)",
                type="filepath",
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
                    choices=["Magenta", "Chroma Green", "White"],
                    value="Magenta",
                    label="Background Color",
                    info="Magenta for dark elements, Chroma Green for light/skin, White as fallback",
                )

    def _wire_events(self) -> None:
        super()._wire_events()

        self.element_reference.change(
            fn=self._on_reference_change, inputs=[self.element_reference]
        )

    def _on_reference_change(self, ref_image) -> None:
        if ref_image:
            self.element_reference_path = self.app.project_state.save_uploaded_file(ref_image)
        else:
            self.element_reference_path = None
