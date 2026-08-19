"""WorkflowPanel: reusable Generate Prompt → Generate Images → Review component."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

import gradio as gr

from .gallery_widget import render_gallery_html
from .generation_mixin import GenerationMixin
from .review_mixin import ReviewMixin


class WorkflowPanel(GenerationMixin, ReviewMixin, ABC):
    """
    Reusable Gradio component that provides the three-step workflow:
    Generate Prompt → Generate Images → Review & Correct.

    Subclasses override:
      - panel_id         (property) — unique prefix for Gradio element IDs
      - do_generate_prompt(*inputs) — generator; yields (prompt, tabs_upd, chatbot_upd, btn_upd)
      - get_review_skill()          — review skill content (may prepend mode prefix)
      - build_review_context(images) — builds the review context dict

    Optional overrides:
      - render_prompt_tab_content()      — add inputs above the prompt box
      - render_images_tab_extra_controls() — add controls above the sliders
      - get_prompt_tab_inputs()          — list of components fed into do_generate_prompt
      - get_reference_image_path()       — path to IMAGE_0
      - get_additional_images_for_generation() — extra images for image gen
      - get_output_subdir()              — subdir under project/iteration folder
      - get_ui_outputs()                 — components for project load/restore
      - get_ui_restore_values()          — gr.update() values matching get_ui_outputs()
    """

    def __init__(self, app):
        self.app = app

        # Per-panel persistent state
        self.current_prompt: str = ""
        self.generated_images: List[str] = []
        self.iteration_count: int = 0
        self.work_item: int = 1
        self.review_history: List = []
        # Parallel to review_history — image paths shown with each message.
        # User messages: List[str] of paths; assistant messages: [].
        self.review_galleries: List = []
        self.review_context: dict = {}
        self.cost_log: List[Dict] = []
        # Per-panel model/quality settings — initialized from panel defaults
        self.image_model: str = self.default_image_model
        self.image_resolution: str = self.default_image_resolution
        self.aspect_ratio: str = self.default_aspect_ratio

        # Gradio component refs — populated by render()
        self.panel_tabs = None
        self.prompt_box = None
        self.output_gallery = None
        self.failed_gallery = None
        self.review_chatbot = None
        self.review_input = None
        self._gen_prompt_btn = None
        self._gen_images_btn = None
        self._send_btn = None

        self._failed_upload = None
        self._num_images_slider = None
        self._aspect_ratio_dropdown = None
        self._draft_mode_radio = None
        self.image_model_dropdown = None
        self.draft_model_dropdown = None
        self.image_resolution_dropdown = None
        self._work_item_label = None
        self._dup_confirm_row = None
        self._gen_anyway_btn = None
        self._dup_cancel_btn = None

        # Session-only (not persisted) — tracks last prompt sent to the API
        self._last_submitted_prompt: str = ""
        # Display history for the chatbot UI — parallel to review_history but may
        # include base64-embedded image thumbnails in user messages.  Never sent
        # to the API; reset to text-only review_history on project load.
        self._ui_history: List = []

    # ── abstract interface ────────────────────────────────────────────────

    @property
    @abstractmethod
    def panel_id(self) -> str:
        """Unique string prefix for all Gradio element IDs in this panel."""

    @property
    def default_image_model(self) -> str:
        return "grok-imagine-image-2.0"

    @property
    def default_image_resolution(self) -> str:
        return "1k"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @abstractmethod
    def do_generate_prompt(self, *inputs):
        """
        Generator function for prompt generation.
        Yields tuples of (prompt_text, tabs_update, chatbot_update, btn_update).
        """

    @abstractmethod
    def get_review_skill(self) -> str:
        """Return the review skill content (with any mode-specific prefix prepended)."""

    @abstractmethod
    def build_review_context(self, images_to_review: List[str]) -> dict:
        """
        Return a review context dict with at least:
          failed_images, original_prompt, scene_description,
          reference_image, additional_images, review_mode
        The caller appends user_initial_comment.
        """

    # ── optional hooks ────────────────────────────────────────────────────

    def _work_item_status(self) -> str:
        wi_ticks = sum(e["ticks"] for e in self.cost_log if e.get("work_item") == self.work_item)
        total_ticks = sum(e["ticks"] for e in self.cost_log)
        parts = [f"**Work Item {self.work_item}** · Iteration {self.iteration_count}"]
        if wi_ticks:
            parts.append(f"💰 ${wi_ticks / 10_000_000_000:.4f}")
        if total_ticks and total_ticks != wi_ticks:
            parts.append(f"total: ${total_ticks / 10_000_000_000:.4f}")
        return " · ".join(parts)

    def _start_new_prompt(self) -> None:
        """Advance work item if prior work exists, then clear per-item state.
        Call at the top of do_generate_prompt in every subclass."""
        if self.iteration_count > 0 or self.generated_images:
            self.work_item += 1
            self.iteration_count = 0
            self.generated_images = []
        self.review_history = []
        self.review_galleries = []
        self.review_context = {}

    def render_prompt_tab_content(self) -> None:
        """Add subclass-specific inputs above the shared prompt box."""

    def render_images_tab_extra_controls(self) -> None:
        """Create the model and quality dropdowns shared by all panels."""
        with gr.Row():
            self.image_model_dropdown = gr.Dropdown(
                choices=[
                    "grok-imagine-image-pro",
                    "grok-imagine-image-quality",
                    "grok-imagine-image-2.0",
                    "grok-imagine-image",
                ],
                value=self.image_model,
                label="🎨 Model",
                interactive=True,
                allow_custom_value=True,
            )
            is_aurora = self.image_model == "grok-imagine-image-2.0"
            self.image_resolution_dropdown = gr.Dropdown(
                choices=["auto", "1k", "2k"],
                value=self.image_resolution if is_aurora else "auto",
                label="Resolution (2.0 only)",
                interactive=is_aurora,
            )

    def get_prompt_tab_inputs(self) -> List:
        """Gradio components passed as inputs to do_generate_prompt."""
        return []

    def get_reference_image_path(self) -> Optional[str]:
        return None

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        return None

    def get_output_subdir(self) -> str:
        return ""

    def get_work_item_references(self) -> Dict[str, str]:
        """Return {filename_stem: path} of reference images to copy into work-item-N/references/.
        Called once on iteration 0 of each work item. Override in subclasses."""
        return {}

    def get_ui_outputs(self) -> List:
        """Components list for project load/restore outputs — override in subclass."""
        return [
            self.prompt_box,
            self.failed_gallery,
            self.output_gallery,
            self.review_chatbot,
            self.image_model_dropdown,
            self.image_resolution_dropdown,
            self._aspect_ratio_dropdown,
            self._work_item_label,
            self.panel_tabs,
        ]

    def get_ui_restore_values(self) -> List:
        """gr.update() values matching get_ui_outputs() — override in subclass."""
        is_aurora = self.image_model == "grok-imagine-image-2.0"
        review_buffer = "" if self.review_history else render_gallery_html(self.generated_images or [])
        return [
            gr.update(value=self.current_prompt),
            gr.update(value=review_buffer),
            gr.update(value=render_gallery_html(self.generated_images or [])),
            gr.update(value=self._ui_history),
            gr.update(value=self.image_model),
            gr.update(value=self.image_resolution if is_aurora else "auto", interactive=is_aurora),
            gr.update(value=self.aspect_ratio),
            gr.update(value=self._work_item_status()),
            gr.update(selected=f"{self.panel_id}_gen_prompt"),
        ]

    # ── persistence ───────────────────────────────────────────────────────

    def serialize(self, project_dir: "Path") -> dict:
        """
        Return a JSON-serializable state dict for this panel.
        Override in subclasses that own files — copy those files into
        project_dir and store the stable paths in the returned dict.
        The base implementation just captures in-memory state.
        """
        return {
            "current_prompt": self.current_prompt,
            "generated_images": self.generated_images,
            "iteration_count": self.iteration_count,
            "work_item": self.work_item,
            "review_history": self.review_history,
            "review_galleries": self.review_galleries,
            "review_context": self.review_context,
            "cost_log": self.cost_log,
            "image_model": self.image_model,
            "image_resolution": self.image_resolution,
            "aspect_ratio": self.aspect_ratio,
        }

    def deserialize(self, d: dict) -> None:
        """Restore panel state from a previously serialized dict."""
        self.current_prompt = d.get("current_prompt", "")
        self.generated_images = d.get("generated_images", [])
        self.iteration_count = d.get("iteration_count", 0)
        self.work_item = d.get("work_item", 1)
        self.cost_log = d.get("cost_log", [])
        self.image_model = d.get("image_model", self.default_image_model)
        self.image_resolution = d.get("image_resolution", self.default_image_resolution)
        self.aspect_ratio = d.get("aspect_ratio", self.default_aspect_ratio)
        self.review_history = d.get("review_history", [])
        self.review_galleries = d.get("review_galleries", [])
        # Always reset review_context on load — its failed_images may be stale.
        # The first send_message call will invoke start_review, which rebuilds
        # context from self.generated_images (permanent paths, always current).
        self.review_context = {}
        self._ui_history = self._rebuild_ui_history(self.review_history, self.review_galleries)

    # ── UI render ─────────────────────────────────────────────────────────

    def render(self) -> None:
        """Build the inner three-tab UI within the current Gradio Blocks context."""
        with gr.Tabs(elem_id=f"{self.panel_id}_tabs") as self.panel_tabs:
            with gr.Tab("📝 Generate Prompt", id=f"{self.panel_id}_gen_prompt"):
                self.render_prompt_tab_content()
                self._gen_prompt_btn = gr.Button("🎯 Generate Prompt", variant="primary")

            with gr.Tab("🖼️ Generate Images", id=f"{self.panel_id}_gen_images"):
                self.prompt_box = gr.Textbox(
                    label="Prompt (edit if needed)",
                    lines=10,
                    max_lines=10,
                    placeholder="Generated prompt will appear here...",
                )
                self.render_images_tab_extra_controls()
                with gr.Row():
                    self._num_images_slider = gr.Slider(
                        minimum=1, maximum=10, value=2, step=1, label="Number of Images"
                    )
                    self._aspect_ratio_dropdown = gr.Dropdown(
                        choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                        value=self.aspect_ratio,
                        label="Aspect Ratio",
                    )
                self._gen_images_btn = gr.Button("🖼️ Generate Images", variant="primary")
                with gr.Row(visible=False) as self._dup_confirm_row:
                    gr.Markdown("⚠️ Same prompt as last generation.")
                    self._gen_anyway_btn = gr.Button("Generate anyway", variant="secondary", size="sm")
                    self._dup_cancel_btn = gr.Button("Cancel", size="sm")
                self._work_item_label = gr.Markdown(value=self._work_item_status())
                self.output_gallery = gr.HTML(min_height=150)

            with gr.Tab("🔍 Review & Correct", id=f"{self.panel_id}_review"):
                self._render_review_tab_content()

        self._wire_events()

    def _wire_events(self) -> None:
        """Wire all Gradio events. Subclasses call super()._wire_events() then add their own."""

        def _on_model_change(model):
            self.image_model = model
            self.app.project_state.save_project_state()
            is_aurora = model == "grok-imagine-image-2.0"
            return gr.update(interactive=is_aurora, value=self.image_resolution if is_aurora else "auto")

        def _on_resolution_change(resolution):
            self.image_resolution = resolution
            self.app.project_state.save_project_state()

        def _on_aspect_change(aspect):
            self.aspect_ratio = aspect
            self.app.project_state.save_project_state()

        self.image_model_dropdown.change(
            fn=_on_model_change,
            inputs=[self.image_model_dropdown],
            outputs=[self.image_resolution_dropdown],
            show_progress="hidden",
        )
        self.image_resolution_dropdown.change(fn=_on_resolution_change, inputs=[self.image_resolution_dropdown], show_progress="hidden")
        self._aspect_ratio_dropdown.change(fn=_on_aspect_change, inputs=[self._aspect_ratio_dropdown], show_progress="hidden")

        self._gen_prompt_btn.click(
            fn=lambda: gr.update(interactive=False, value="⏳ Generating prompt..."),
            outputs=[self._gen_prompt_btn],
            show_progress="minimal",
        ).then(
            fn=self.do_generate_prompt,
            inputs=self.get_prompt_tab_inputs(),
            outputs=[self.prompt_box, self.panel_tabs, self._gen_prompt_btn],
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=[]),
            outputs=[self.review_chatbot],
            show_progress="hidden",
        )

        _gen_inputs = [self.prompt_box, self._num_images_slider, self._aspect_ratio_dropdown]
        _gen_outputs = [self.output_gallery, self.failed_gallery, self._dup_confirm_row, self._gen_images_btn, self._gen_anyway_btn]

        self._gen_images_btn.click(
            fn=self._generate_images_for_ui,
            inputs=_gen_inputs,
            outputs=_gen_outputs,
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=self._work_item_status()),
            outputs=[self._work_item_label],
            show_progress="hidden",
        )
        self._gen_anyway_btn.click(
            fn=self._force_generate_images_for_ui,
            inputs=_gen_inputs,
            outputs=_gen_outputs,
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=self._work_item_status()),
            outputs=[self._work_item_label],
            show_progress="hidden",
        )
        self._dup_cancel_btn.click(
            fn=lambda: gr.update(visible=False),
            outputs=[self._dup_confirm_row],
            show_progress="hidden",
        )

        self.review_chatbot.select(
            fn=self._on_message_select,
            outputs=self._get_extract_outputs(),
            show_progress="hidden",
        )

        self._wire_review_events()
