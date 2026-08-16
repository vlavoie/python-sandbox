"""FinalizeWorkflowPanel: one-click lighting/color refinement on a finished image."""

from typing import Any, List, Optional, Tuple

import gradio as gr

from .grok_client import GrokClient
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

    Includes the standard Review tab for diagnosing bad outputs.
    The Extract button sends the corrected prompt back to the Notes field.
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

    # Finalize does not use do_generate_prompt
    def do_generate_prompt(self, *inputs):
        raise NotImplementedError

    def get_review_skill(self) -> str:
        ps = self.app.project_state
        prefix = (
            "FINALIZE REVIEW MODE — LIGHTING AND COLOR PASS ANALYSIS\n\n"
            "You are reviewing the output of a finalization pass that was meant to improve "
            "lighting and color quality only. No structural changes should have occurred.\n\n"
            "IMAGE ASSIGNMENT:\n"
            "- <IMAGE_0> = CHARACTER REFERENCE — identity and appearance lock\n"
            "- <IMAGE_1> = SOURCE IMAGE being refined (spatial base that must be preserved)\n"
            "- Additional images shown = the finalized output(s) being reviewed\n\n"
            "Review checklist (in order):\n"
            "1. Was the spatial composition and structure preserved exactly from IMAGE_1?\n"
            "2. Were character positions, expressions, and poses maintained?\n"
            "3. Did the lighting/color quality improve as intended?\n"
            "4. Were any unintended structural changes introduced?\n\n"
            "When writing a corrected prompt, follow fpv-pov-finalize.md structure:\n"
            "- Open with: \"Starting from IMAGE_1 as the unchanged spatial and compositional base, [lighting/color changes].\"\n"
            "- Keep the prompt to 50–80 words\n"
            "- Close with: \"All character positions, expressions, clothing, spatial composition, "
            "and image structure remain exactly as in IMAGE_1.\"\n"
            "- No structural changes, no new characters, no green zones\n\n"
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

    def extract_prompt(self) -> Tuple[str, Any]:
        """Extract the corrected prompt from review and send it to the Notes box."""
        for msg in reversed(self.review_history):
            if msg["role"] == "assistant" and msg["content"]:
                cleaned = GrokClient._clean_prompt_text(msg["content"])
                if cleaned:
                    return cleaned, gr.update(selected="finalize_finalize")
        return "", gr.update()

    def _get_extract_outputs(self) -> List:
        return [self._notes_box, self.panel_tabs]

    # ── generation ────────────────────────────────────────────────────────

    def _do_finalize(self, source_image, notes, progress=gr.Progress()):
        client = self.app.client
        ps = self.app.project_state

        _noop_prompt = gr.update()
        _done_btn = gr.update(value="✨ Finalize Image", interactive=True)
        _busy_btn_prompt = gr.update(value="⏳ Generating prompt...", interactive=False)
        _busy_btn_image = gr.update(value="⏳ Generating image...", interactive=False)
        _cur_gallery = render_gallery_html(self.generated_images or [])
        _cur_status = gr.update(value=self._work_item_status())

        if not client:
            yield _cur_gallery, _cur_status, _done_btn, _noop_prompt
            return
        if source_image:
            self.source_image_path = ps.save_uploaded_file(source_image)
        if not self.source_image_path:
            yield _cur_gallery, _cur_status, _done_btn, _noop_prompt
            return
        if not self.get_reference_image_path():
            yield _cur_gallery, _cur_status, _done_btn, _noop_prompt
            return

        yield _cur_gallery, _cur_status, _busy_btn_prompt, _noop_prompt

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
            yield _cur_gallery, _cur_status, _done_btn, _noop_prompt
            return

        self.current_prompt = prompt

        yield _cur_gallery, _cur_status, _busy_btn_image, gr.update(value=prompt)

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
        yield gallery_html, gr.update(value=self._work_item_status()), _done_btn, gr.update(value=prompt)

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
            self.review_chatbot,
            self.failed_gallery,
            self.prompt_box,
        ]

    def get_ui_restore_values(self) -> List:
        review_images = self.generated_images or []
        return [
            gr.update(value=render_gallery_html(self.generated_images or [])),
            gr.update(value=self._work_item_status()),
            gr.update(value=self.review_history),
            gr.update(value=render_gallery_html(review_images)),
            gr.update(value=self.current_prompt),
        ]

    # ── render ────────────────────────────────────────────────────────────

    def render(self) -> None:
        gr.Markdown(
            "Upload the finished image and optionally describe what to fix. "
            "The prompt is auto-generated — no drafting needed. "
            "Use the Review tab to diagnose a bad output."
        )
        with gr.Tabs(elem_id="finalize_tabs") as self.panel_tabs:
            with gr.Tab("✨ Finalize", id="finalize_finalize"):
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
                self.prompt_box = gr.Textbox(
                    label="Generated Prompt",
                    lines=4,
                    max_lines=8,
                    interactive=False,
                    placeholder="The auto-generated prompt will appear here after finalization.",
                )

            with gr.Tab("🔍 Review & Correct", id="finalize_review"):
                self._render_review_tab_content()

        self._wire_events()

    def _wire_events(self) -> None:
        self._finalize_btn.click(
            fn=self._do_finalize,
            inputs=[self._source_image, self._notes_box],
            outputs=[self.output_gallery, self._work_item_label, self._finalize_btn, self.prompt_box],
        )
        self._source_image.change(
            fn=self._on_source_change,
            inputs=[self._source_image],
        )
        self._extract_btn.click(
            fn=self.extract_prompt,
            inputs=[],
            outputs=self._get_extract_outputs(),
        )
        self._wire_review_events()

    def _on_source_change(self, img) -> None:
        if img:
            self.source_image_path = self.app.project_state.save_uploaded_file(img)
        else:
            self.source_image_path = None
