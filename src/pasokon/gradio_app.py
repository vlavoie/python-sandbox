"""Gradio application for FPV POV image generation workflow."""

import os
import sys
from typing import List, Optional, Tuple

import gradio as gr
from pathlib import Path
from dotenv import load_dotenv

from .grok_client import GrokClient
from .project_state import ProjectState
from .fpv_workflow import FPVWorkflowPanel
from .element_workflow import ElementWorkflowPanel
from .finalize_workflow import FinalizeWorkflowPanel
_ASSETS = Path(__file__).parent
_GALLERY_CSS = (_ASSETS / "gallery.css").read_text(encoding="utf-8")
_GALLERY_JS  = (_ASSETS / "gallery.js").read_text(encoding="utf-8")

_THEME = gr.themes.Soft(
    font=["ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
    font_mono=["ui-monospace", "Cascadia Code", "Consolas", "Fira Code", "Droid Sans Mono", "monospace"],
    text_size=gr.themes.sizes.text_lg,
)

load_dotenv()

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")


class FPVPOVApp:
    """Gradio app for automating FPV POV image generation."""

    def __init__(self):
        self.client: Optional[GrokClient] = None
        self.available_chat_models: List[str] = []
        self.available_image_models: List[str] = []

        self.project_state = ProjectState()
        self.fpv_panel = FPVWorkflowPanel(self)
        self.element_panel = ElementWorkflowPanel(self)
        self.finalize_panel = FinalizeWorkflowPanel(self)
        self.project_selector = None  # set during create_interface

        self.project_state.register_panel("fpv", self.fpv_panel)
        self.project_state.register_panel("element", self.element_panel)
        self.project_state.register_panel("finalize", self.finalize_panel)

        # Auto-load last project
        try:
            status, _ = self.project_state.load_project_state()
            if "Loaded project" in status:
                print(f"\n{status}\n")
        except Exception as e:
            print(f"Note: Could not auto-load last project: {e}")

    # ── client / model management ─────────────────────────────────────────

    def initialize_client(self, api_key: str) -> str:
        try:
            self.client = GrokClient(api_key=api_key)
            self.client.chat_model = self.project_state.chat_model
            self.client.image_model = self.project_state.image_model
            self.fetch_models()
            return "✅ API key configured successfully!"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def fetch_models(self) -> Tuple[List[str], List[str]]:
        if not self.client:
            return [], []
        try:
            data = self.client.list_models()
            if "data" not in data:
                raise ValueError("No data in response")
            chat_models, image_models = [], []
            for m in data["data"]:
                if not isinstance(m, dict) or "id" not in m:
                    continue
                mid = m["id"]
                if "video" in mid.lower():
                    continue
                if "imagine" in mid.lower() or "image" in mid.lower():
                    image_models.append(mid)
                else:
                    chat_models.append(mid)
            self.available_chat_models = chat_models or ["grok-4.20"]
            self.available_image_models = image_models or ["grok-imagine-image-2.0"]
            return self.available_chat_models, self.available_image_models
        except Exception as e:
            print(f"⚠️ Could not fetch models: {e}")
            self.available_chat_models = ["grok-4.20"]
            self.available_image_models = ["grok-imagine-image-2.0"]
            return self.available_chat_models, self.available_image_models

    def update_chat_model(self, model_name: str) -> None:
        self.project_state.chat_model = model_name
        if self.client:
            self.client.chat_model = model_name
        self.project_state.save_project_state()

    def update_image_model(self, model_name: str) -> None:
        self.project_state.image_model = model_name
        if self.client:
            self.client.image_model = model_name
        self.project_state.save_project_state()

    def update_image_resolution(self, resolution: str) -> None:
        self.project_state.image_resolution = resolution
        self.project_state.save_project_state()

    # ── UI wrappers for project load/set ──────────────────────────────────

    def _build_project_outputs(self, status: str, display: str) -> tuple:
        """Combine app-level + all panel restore values into OUTPUTS_PROJECT tuple."""
        return (
            status,
            display,
            gr.update(choices=self.project_state.list_projects(), value=None),
            *self.fpv_panel.get_ui_restore_values(),
            *self.element_panel.get_ui_restore_values(),
            *self.finalize_panel.get_ui_restore_values(),
            gr.update(value=self.project_state.chat_model),
        )

    def _load_project_for_ui(self, project_name=None) -> tuple:
        try:
            status, display = self.project_state.load_project_state(project_name)
            return self._build_project_outputs(status, display)
        except Exception as e:
            print(f"\nERROR IN PROJECT LOAD:\n{e}\n")
            return self._build_project_outputs(f"❌ Failed to load project: {e}", "")

    def _set_project_for_ui(self, project_name: str) -> tuple:
        try:
            status, display = self.project_state.set_project_name(project_name)
            return self._build_project_outputs(status, display)
        except Exception as e:
            print(f"\nERROR IN SET PROJECT:\n{e}\n")
            return self._build_project_outputs(f"❌ Failed to set project: {e}", "")

    # ── Gradio interface ──────────────────────────────────────────────────

    def create_interface(self) -> gr.Blocks:
        with gr.Blocks(title="FPV POV Image Generator", theme=_THEME, css=_GALLERY_CSS, js=_GALLERY_JS) as app:
            gr.Markdown("# 🎨 FPV POV Image Generator")
            gr.Markdown("Automate your Grok-based first-person POV image generation workflow")

            with gr.Accordion("📖 Instructions", open=False):
                gr.Markdown("""
                ### Workflow Overview

                **Phase 1: Base Image Generation**
                1. **Generate Prompt**: Upload your character reference and describe the scene
                2. **Generate Images**: Create variations using the prompt
                3. **Review & Correct**: If images have errors, get a corrected prompt

                **Phase 2: Enhancements** (Optional)
                - Mark zones in an image editor, upload as the green-zone base image
                - Generate surgical addition prompts

                **Element Generator** — for GIMP compositing
                - Generate isolated FPV elements against chroma backgrounds
                - Same Generate → Review workflow as FPV

                ### API Key
                Get your key from x.ai and set `XAI_API_KEY` in your environment.
                """)

            with gr.Row():
                current_project_display = gr.Markdown(self.project_state._get_project_display_string())
                manual_save_btn = gr.Button("💾 Save Now", scale=0, size="sm")

            main_tabs = gr.Tabs()
            with main_tabs:
                # ── Tab 1: Project Management ──────────────────────────────
                with gr.Tab("💾 Project Management", id="tab_project"):
                    gr.Markdown("### Load & Save Projects")
                    gr.Markdown("""
                    **Project Persistence:** Your work is automatically saved.
                    Close and reopen to resume where you left off.
                    """)

                    with gr.Row():
                        with gr.Column():
                            project_name_input = gr.Textbox(
                                label="Project Name",
                                value=self.project_state.project_name,
                                placeholder="my-fpv-project",
                            )
                            set_project_btn = gr.Button("💾 Set Project Name")
                        with gr.Column():
                            self.project_selector = gr.Dropdown(
                                label="Load Existing Project",
                                choices=self.project_state.list_projects(),
                                value=None,
                            )
                            load_project_btn = gr.Button("📂 Load Selected Project")

                    gr.Markdown("### Model Selection")
                    with gr.Row():
                        chat_model_dropdown = gr.Dropdown(
                            choices=["grok-4.20", "grok-2-1212", "grok-2-vision-1212", "grok-beta"],
                            value=self.project_state.chat_model,
                            label="💬 Chat Model",
                            info="For prompt generation & review",
                            interactive=True,
                            allow_custom_value=True,
                        )

                    project_mgmt_status = gr.Textbox(
                        label="Project Status", interactive=False, lines=12
                    )

                # ── Tab 2: FPV Workflow ────────────────────────────────────
                with gr.Tab("🎯 FPV Workflow", id="tab_fpv"):
                    gr.Markdown("### First-Person POV image generation — Phase 1 & Phase 2")
                    self.fpv_panel.render()

                # ── Tab 3: Element Generator ───────────────────────────────
                with gr.Tab("✨ Element Generator", id="tab_element"):
                    gr.Markdown("### Generate isolated FPV elements for GIMP compositing")
                    self.element_panel.render()

                # ── Tab 4: Finalize ────────────────────────────────────────
                with gr.Tab("🏁 Finalize", id="tab_finalize"):
                    gr.Markdown("### Final lighting & color pass — no structural changes")
                    self.finalize_panel.render()

            # OUTPUTS_PROJECT must match what _build_project_outputs returns exactly.
            OUTPUTS_PROJECT = [
                project_mgmt_status,
                current_project_display,
                self.project_selector,
                *self.fpv_panel.get_ui_outputs(),
                *self.element_panel.get_ui_outputs(),
                *self.finalize_panel.get_ui_outputs(),
                chat_model_dropdown,
            ]

            # Tab 1 events
            set_project_btn.click(
                fn=self._set_project_for_ui,
                inputs=[project_name_input],
                outputs=OUTPUTS_PROJECT,
            )
            project_name_input.submit(
                fn=self._set_project_for_ui,
                inputs=[project_name_input],
                outputs=OUTPUTS_PROJECT,
            )
            load_project_btn.click(
                fn=self._load_project_for_ui,
                inputs=[self.project_selector],
                outputs=OUTPUTS_PROJECT,
            )
            manual_save_btn.click(
                fn=self.project_state.save_project_state,
                outputs=[project_mgmt_status],
            )
            chat_model_dropdown.change(
                fn=self.update_chat_model,
                inputs=[chat_model_dropdown],
            )

            # Auto-load on page load
            app.load(
                fn=lambda: self._load_project_for_ui(),
                outputs=OUTPUTS_PROJECT,
            )

        return app


def launch():
    """Launch the Gradio app."""
    app = FPVPOVApp()
    interface = app.create_interface()

    existing_key = os.getenv("XAI_API_KEY")
    if existing_key:
        print("🔑 Auto-initializing with API key from environment...")
        app.initialize_client(existing_key)
        app.client.image_model = "grok-imagine-image-pro"
        chat_models, image_models = app.fetch_models()
        if chat_models and image_models:
            print(f"✅ Loaded {len(chat_models)} chat models and {len(image_models)} image models")

    interface.launch(share=False)


if __name__ == "__main__":
    launch()
