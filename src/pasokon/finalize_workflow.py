"""FinalizeWorkflowPanel: one-click lighting/color refinement on a finished image."""

from typing import List, Optional

import gradio as gr

from .workflow_panel import WorkflowPanel
from .gallery_widget import render_gallery_html


class FinalizeWorkflowPanel(WorkflowPanel):
    """
    Lightweight panel for final-quality passes on a finished image.

    The user uploads the finished image, optionally adds notes ("warmer tones"),
    and clicks Finalize. The prompt is auto-generated from fpv-pov-finalize.md —
    no user prompt drafting needed.

    IMAGE_0 = fpv_panel character reference (identity lock)
    IMAGE_1 = the finished image to refine (source_image_path)

    No review loop. Retry by clicking Finalize again.
    """

    def __init__(self, app):
        super().__init__(app)

        # Finalize-specific persistent state
        self.source_image_path: Optional[str] = None
        self.notes: str = ""

        # Gradio component refs (set by render)
        self._source_image = None
        self._notes_box = None
        self._finalize_btn = None

    @property
    def panel_id(self) -> str:
        return "finalize"

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

    # Stubs — finalize does not use the standard prompt/review loop
    def do_generate_prompt(self, *inputs):
        raise NotImplementedError

    def get_review_skill(self) -> str:
        return self.app.project_state.finalize_skill

    def build_review_context(self, images_to_review: List[str]) -> dict:
        return {}

    # ── generation ────────────────────────────────────────────────────────

    def _do_finalize(self, source_image, notes, progress=gr.Progress()):
        client = self.app.client
        ps = self.app.project_state

        if not client:
            yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="✨ Finalize Image", interactive=True)
            return
        if source_image:
            self.source_image_path = ps.save_uploaded_file(source_image)
        if not self.source_image_path:
            yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="✨ Finalize Image", interactive=True)
            return
        if not self.get_reference_image_path():
            yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="✨ Finalize Image", interactive=True)
            return

        yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="⏳ Generating prompt...", interactive=False)

        self._start_new_prompt()
        self.notes = notes or ""

        # Build scene context for the finalize LLM
        fpv = self.app.fpv_panel
        scene_ctx = (fpv.phase1_scene_description or fpv.current_scene or "").strip()
        notes_part = f"\nUser notes: {notes.strip()}" if notes and notes.strip() else ""
        prompt_input = f"Scene context: {scene_ctx}{notes_part}" if scene_ctx else (notes.strip() or "Refine lighting and color.")

        progress(0, desc="Generating finalize prompt...")
        try:
            prompt = client.generate_prompt(
                reference_image=self.get_reference_image_path(),
                scene_description=prompt_input,
                skill_content=ps.finalize_skill,
                additional_images=[self.source_image_path],
            )
        except Exception as e:
            print(f"\nERROR IN FINALIZE PROMPT GENERATION:\n{e}\n")
            yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="✨ Finalize Image", interactive=True)
            return

        self.current_prompt = prompt

        yield render_gallery_html(self.generated_images or []), gr.update(value=self._work_item_status()), gr.update(value="⏳ Generating image...", interactive=False)

        r = ps.image_resolution if ps.image_resolution != "auto" else None

        def on_done(c, t):
            progress(c / t, desc=f"Image {c}/{t} done...")

        progress(0, desc="Generating refined image...")
        _, images, _ = self.generate_images_batch(
            prompt, num_images=1, aspect_ratio="16:9",
            resolution_override=r, progress_callback=on_done,
        )

        gallery_html = render_gallery_html(images or self.generated_images or [])
        ps.save_project_state()
        progress(1.0, desc="Done")
        yield gallery_html, gr.update(value=self._work_item_status()), gr.update(value="✨ Finalize Image", interactive=True)

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
        return [
            self.output_gallery,
            self._work_item_label,
        ]

    def get_ui_restore_values(self) -> List:
        return [
            gr.update(value=render_gallery_html(self.generated_images or [])),
            gr.update(value=self._work_item_status()),
        ]

    # ── render ────────────────────────────────────────────────────────────

    def render(self) -> None:
        gr.Markdown(
            "Upload the finished image and optionally describe what to fix. "
            "The prompt is auto-generated — no drafting needed."
        )
        with gr.Row():
            self._source_image = gr.Image(
                label="Finished Image to Refine",
                type="filepath",
                image_mode=None,
                sources=["upload"],
                height=300,
            )
            self._notes_box = gr.Textbox(
                label="Optional Notes",
                lines=4,
                placeholder="e.g. warmer tones, reduce harsh shadows, richer ambient light",
            )
        self._finalize_btn = gr.Button("✨ Finalize Image", variant="primary")
        self._work_item_label = gr.Markdown(value=self._work_item_status())
        self.output_gallery = gr.HTML()

        self._wire_events()

    def _wire_events(self) -> None:
        self._finalize_btn.click(
            fn=self._do_finalize,
            inputs=[self._source_image, self._notes_box],
            outputs=[self.output_gallery, self._work_item_label, self._finalize_btn],
        )
        self._source_image.change(
            fn=self._on_source_change,
            inputs=[self._source_image],
        )

    def _on_source_change(self, img) -> None:
        if img:
            self.source_image_path = self.app.project_state.save_uploaded_file(img)
        else:
            self.source_image_path = None
