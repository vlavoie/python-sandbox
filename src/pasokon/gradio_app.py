"""Gradio application for FPV POV image generation workflow."""

import gradio as gr
from pathlib import Path
from typing import Optional, List, Tuple, Any
import tempfile
import shutil
from PIL import Image
import io
import os
import json
from datetime import datetime
import sys
from datetime import datetime
from dotenv import load_dotenv

from .grok_client import GrokClient
from .review_handler import ReviewHandler
from .gallery_widget import render_gallery_html

_ASSETS = Path(__file__).parent
_GALLERY_CSS = (_ASSETS / "gallery.css").read_text(encoding="utf-8")
_GALLERY_JS  = (_ASSETS / "gallery.js").read_text(encoding="utf-8")

# Load environment variables from .env file
load_dotenv()

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import locale
    # Set environment variable for Python UTF-8 mode
    os.environ.setdefault('PYTHONUTF8', '1')


class FPVPOVApp(ReviewHandler):
    """Gradio app for automating FPV POV image generation."""

    def __init__(self):
        """Initialize the app."""
        super().__init__()

        # Model lists
        self.client = None
        self.available_chat_models = []
        self.available_image_models = []
        self.all_models = []

        # Try to auto-load the last project
        try:
            load_results = self.load_project_state()
            load_msg = load_results[0]  # First element is the status message
            if "Loaded project" in load_msg:
                print(f"\n{load_msg}\n")
        except Exception as e:
            print(f"Note: Could not auto-load last project: {e}")
    
    def initialize_client(self, api_key: str) -> str:
        """Initialize the Grok client with API key."""
        try:
            self.client = GrokClient(api_key=api_key)
            
            # Fetch available models
            self.fetch_models()
            
            return "✅ API key configured successfully!"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def fetch_models(self) -> Tuple[List[str], List[str]]:
        """Fetch available models from the API and categorize them.
        
        Returns:
            Tuple of (chat_models, image_models)
        """
        if not self.client:
            return [], []
        
        try:
            models_data = self.client.list_models()
            
            if "data" in models_data:
                self.all_models = []
                chat_models = []
                image_models = []
                
                for model in models_data.get("data", []):
                    if isinstance(model, dict) and "id" in model:
                        model_id = model["id"]
                        self.all_models.append(model_id)
                        
                        # Categorize models
                        # Image models: grok-imagine-image variants (but NOT video)
                        if ("imagine" in model_id.lower() or "image" in model_id.lower()) and "video" not in model_id.lower():
                            image_models.append(model_id)
                        # Chat models: everything else that's not image/video
                        elif "video" not in model_id.lower() and "imagine" not in model_id.lower():
                            chat_models.append(model_id)
                
                self.available_chat_models = chat_models if chat_models else ["grok-4.20"]
                self.available_image_models = image_models if image_models else ["grok-imagine-image-2.0"]
                
                print(f"✅ Loaded {len(chat_models)} chat models and {len(image_models)} image models")
                print(f"   Image models: {', '.join(image_models[:5])}{'...' if len(image_models) > 5 else ''}")
                return chat_models, image_models
            else:
                # Fallback to defaults
                self.available_chat_models = ["grok-4.20"]
                self.available_image_models = ["grok-imagine-image-2.0"]
                return self.available_chat_models, self.available_image_models
                
        except Exception as e:
            print(f"⚠️ Could not fetch models: {e}")
            # Fallback to defaults
            self.available_chat_models = ["grok-4.20"]
            self.available_image_models = ["grok-imagine-image-2.0"]
            return self.available_chat_models, self.available_image_models
    
    def update_chat_model(self, model_name: str) -> str:
        """Update the chat model used by the client."""
        if self.client:
            self.client.chat_model = model_name
            return f"✅ Chat model updated to: {model_name}"
        return "❌ Client not initialized"
    
    def update_image_model(self, model_name: str) -> str:
        """Update the image model used by the client."""
        if self.client:
            self.client.image_model = model_name
            return f"✅ Image model updated to: {model_name}"
        return "❌ Client not initialized"
    
    def generate_initial_prompt(
        self,
        reference_image,
        scene_description: str,
        additional_images: Optional[List] = None,
        greenzone_image=None
    ) -> Tuple[str, str, Any]:
        """Generate a prompt. Phase 2 mode activates automatically when a greenzone image is provided."""
        if not self.client:
            return "❌ Please configure your API key first.", "", gr.update()

        if not reference_image:
            return "❌ Please upload a character reference image.", "", gr.update()

        if not scene_description.strip():
            return "❌ Please provide a scene description.", "", gr.update()

        is_phase2 = greenzone_image is not None

        try:
            self.reference_image_path = self.save_uploaded_file(reference_image)

            self.additional_images_paths = []
            if additional_images:
                for img in additional_images:
                    if img is not None:
                        path = self.save_uploaded_file(img)
                        if path:
                            self.additional_images_paths.append(path)

            if is_phase2:
                self.greenzone_image_path = self.save_uploaded_file(greenzone_image)
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

                phase2_prefix = """PHASE 2 ENHANCEMENT MODE
You are generating a Phase 2 green-zone enhancement prompt.

CRITICAL IMAGE ASSIGNMENT — override any conflicting convention in the skill below:
- <IMAGE_0> is the CHARACTER REFERENCE — lock all style, appearance, hair color, and identity to this image
- <IMAGE_1> is the GREEN-MARKED BASE IMAGE — the spatial/compositional base to modify

The generated prompt must instruct the image model to:
- Add the specified elements ONLY inside the green/pink zones on <IMAGE_1>
- Completely erase all green/pink paint so no trace remains
- Lock all appearance and style strictly to <IMAGE_0>
- Use <IMAGE_1> as the spatial base

Do NOT swap these roles. <IMAGE_0> is always the character reference in this workflow.

---

"""
                self.current_prompt = self.client.generate_prompt(
                    reference_image=self.reference_image_path,       # IMAGE_0 = character
                    scene_description=full_scene,
                    skill_content=phase2_prefix + self.prompt_skill,
                    additional_images=[self.greenzone_image_path]    # IMAGE_1 = greenzone
                )
                status = "✅ Phase 2 enhancement prompt generated!"
            else:
                self.greenzone_image_path = None
                self.review_mode = "phase1"
                self.current_scene = scene_description
                self.current_prompt = self.client.generate_prompt(
                    reference_image=self.reference_image_path,
                    scene_description=scene_description,
                    skill_content=self.prompt_skill,
                    additional_images=self.additional_images_paths if self.additional_images_paths else None
                )
                status = "✅ Prompt generated successfully!"

            self.save_project_state()
            return status, self.current_prompt, gr.update(selected="tab_generate_images")

        except Exception as e:
            error_msg = str(e)
            print(f"\n{'='*60}")
            print(f"ERROR IN PROMPT GENERATION:")
            print(f"{'='*60}")
            print(error_msg)
            print(f"{'='*60}\n")
            return f"❌ Error generating prompt: {error_msg}", "", gr.update()
    
    def save_images_permanently(
        self,
        image_data_list: List[bytes],
        prompt: str,
        iteration: int,
        aspect_ratio: str
    ) -> Path:
        """Save generated images to permanent output directory.
        
        Args:
            image_data_list: List of image data as bytes
            prompt: The prompt used to generate images
            iteration: Iteration number
            aspect_ratio: Aspect ratio used
            
        Returns:
            Path to the output directory
        """
        # Create project folder
        project_dir = self.output_dir / self.project_name
        project_dir.mkdir(exist_ok=True)
        
        # Create timestamped folder within project
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        batch_dir = project_dir / f"{timestamp}_iteration-{iteration}"
        batch_dir.mkdir(exist_ok=True)
        
        # Save each image
        for i, img_data in enumerate(image_data_list, 1):
            img = Image.open(io.BytesIO(img_data))
            img_path = batch_dir / f"image_{i}.png"
            # Preserve transparency by ensuring RGBA mode for PNG
            if img.mode in ('RGBA', 'LA', 'P'):
                img.save(img_path, 'PNG', optimize=True)
            elif img.mode == 'RGB':
                img.save(img_path, 'PNG', optimize=True)
            else:
                # Convert to RGBA to preserve any transparency
                img = img.convert('RGBA')
                img.save(img_path, 'PNG', optimize=True)
        
        # Save prompt to text file
        prompt_file = batch_dir / "prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(f"Project: {self.project_name}\n")
            f.write(f"Iteration: {iteration}\n")
            f.write(f"Aspect Ratio: {aspect_ratio}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"\n{'='*60}\n")
            f.write(f"PROMPT:\n")
            f.write(f"{'='*60}\n\n")
            f.write(prompt)
        
        return batch_dir
    
    def generate_images_batch(
        self,
        prompt: str,
        num_images: int = 3,
        aspect_ratio: str = "16:9"
    ) -> Tuple[str, List, List]:
        """Generate a batch of images using Grok Imagine."""
        if not self.client:
            return "❌ Please configure your API key first.", [], []
        
        if not prompt.strip():
            return "❌ Please provide a prompt.", [], []
        
        if not self.reference_image_path:
            return "❌ No reference image available.", [], []
        
        try:
            self.iteration_count += 1
            
            # Generate images
            image_data_list = self.client.generate_images(
                prompt=prompt,
                reference_image=self.reference_image_path,
                num_images=num_images,
                additional_images=self.additional_images_paths if self.additional_images_paths else None,
                aspect_ratio=aspect_ratio
            )
            
            # Check if we got any images
            if not image_data_list or len(image_data_list) == 0:
                return "❌ No images were successfully generated. Check console for errors.", [], []
            
            # Save to permanent directory
            saved_dir = self.save_images_permanently(
                image_data_list=image_data_list,
                prompt=prompt,
                iteration=self.iteration_count,
                aspect_ratio=aspect_ratio
            )
            
            # Convert to PIL Images for display
            images = []
            for img_data in image_data_list:
                img = Image.open(io.BytesIO(img_data))
                
                # Save to temp file for Gradio display
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                # Preserve transparency by ensuring RGBA mode for PNG
                if img.mode in ('RGBA', 'LA', 'P'):
                    img.save(temp_file.name, 'PNG', optimize=True)
                elif img.mode == 'RGB':
                    img.save(temp_file.name, 'PNG', optimize=True)
                else:
                    # Convert to RGBA to preserve any transparency
                    img = img.convert('RGBA')
                    img.save(temp_file.name, 'PNG', optimize=True)
                temp_file.close()
                
                images.append(temp_file.name)
            
            self.generated_images = images
            self.current_prompt = prompt
            
            # Check if we got partial results
            actual_count = len(images)
            is_partial = actual_count < num_images
            
            # Build status message
            if is_partial:
                status_msg = (
                    f"⚠️ Partial success: {actual_count}/{num_images} images generated (Iteration {self.iteration_count})\n"
                    f"📁 Project: {self.project_name}\n"
                    f"💾 Saved {actual_count} successful image(s) to: {self.project_name}/{saved_dir.name}/\n"
                    f"⚠️ {num_images - actual_count} image(s) failed - check console for details"
                )
            else:
                status_msg = (
                    f"✅ Generated {len(images)} images (Iteration {self.iteration_count})\n"
                    f"📁 Project: {self.project_name}\n"
                    f"💾 Saved to: {self.project_name}/{saved_dir.name}/"
                )
            
            # Auto-save project state
            self.save_project_state()
            
            return status_msg, images, images
            
        except Exception as e:
            return f"❌ Error generating images: {str(e)}", [], []
    
    def update_greenzone_image(self, greenzone_image) -> str:
        """Pre-save greenzone image so Save Now works before Generate Prompt is clicked."""
        if greenzone_image:
            self.greenzone_image_path = self.save_uploaded_file(greenzone_image)
            return "✅ Green-zone base image updated"
        self.greenzone_image_path = None
        return ""

    def update_reference_image(self, reference_image) -> str:
        """Update the reference image path when a new image is uploaded."""
        if reference_image:
            self.reference_image_path = self.save_uploaded_file(reference_image)
            return "✅ Reference image updated (click 'Save Now' to persist)"
        return ""
    
    def update_additional_images(self, additional_images) -> str:
        """Update the additional images paths when new images are uploaded."""
        if additional_images:
            self.additional_images_paths = []
            for img in additional_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        self.additional_images_paths.append(path)
            return f"✅ {len(self.additional_images_paths)} additional image(s) updated (click 'Save Now' to persist)"
        else:
            self.additional_images_paths = []
        return ""
    
    # ── UI-layer wrappers: convert path lists → gallery HTML ─────────────

    def _generate_images_for_ui(self, prompt, num_images, aspect_ratio):
        status, images, failed = self.generate_images_batch(prompt, num_images, aspect_ratio)
        return status, render_gallery_html(images), render_gallery_html(failed)

    def _load_project_for_ui(self, project_name=None):
        result = list(self.load_project_state(project_name))
        result[3] = render_gallery_html(result[3] or [])   # failed_images_gallery slot
        result[9] = render_gallery_html(result[9] or [])   # output_gallery slot
        return tuple(result)

    def _set_project_for_ui(self, project_name):
        result = list(self.set_project_name(project_name))
        result[3] = render_gallery_html(result[3] or [])
        result[9] = render_gallery_html(result[9] or [])
        return tuple(result)

    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface."""
        with gr.Blocks(title="FPV POV Image Generator", theme=gr.themes.Soft(), css=_GALLERY_CSS, js=_GALLERY_JS) as app:
            gr.Markdown("# 🎨 FPV POV Image Generator")
            gr.Markdown("Automate your Grok-based first-person POV image generation workflow")
            
            # Instructions at the top
            with gr.Accordion("📖 Instructions", open=False):
                gr.Markdown("""
                ### Workflow Overview
                
                **Phase 1: Base Image Generation**
                1. **Generate Prompt**: Upload your character reference and describe the scene
                2. **Generate Images**: Create 3 (or more) variations using the prompt
                3. **Review & Correct**: If images have errors, upload them for analysis and get a corrected prompt
                4. Repeat steps 2-3 until you have a solid base image
                
                **Phase 2: Enhancements** (Optional)
                - For elements that hallucinate (like hair), manually mark zones in an image editor
                - Generate enhancement prompts for precise additions
                
                ### Tips
                - You can edit any generated prompt before using it
                - Save good intermediate results to your computer
                - The app remembers your reference images across tabs
                - Use Photoshop between iterations for manual corrections
                - Start with clean bases, add complex elements later
                
                ### API Key
                - Get your API key from x.ai
                - Set the `XAI_API_KEY` environment variable
                """)
            
            # Current project indicator
            with gr.Row():
                current_project_display = gr.Markdown(f"**📁 Current Project:** `{self.project_name}` | **🎯 Mode:** `{self.review_mode}` | 💾 Auto-saves after each action")
                manual_save_btn = gr.Button("💾 Save Now", scale=0, size="sm")
            
            # Main workflow tabs
            main_tabs = gr.Tabs()
            with main_tabs:
                # Tab 1: Project Management
                with gr.Tab("💾 Project Management", id="tab_project"):
                    gr.Markdown("### Load & Save Projects")
                    gr.Markdown("""
                    **Project Persistence:** Your work is automatically saved! You can close the app and resume later.
                    
                    Saved data includes: prompts, images, references, review mode, and more.
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            project_name_input_dup = gr.Textbox(
                                label="Project Name",
                                value=self.project_name,
                                placeholder="my-fpv-project"
                            )
                            set_project_btn = gr.Button("💾 Set Project Name")
                        
                        with gr.Column():
                            project_selector = gr.Dropdown(
                                label="Load Existing Project",
                                choices=self.list_projects(),
                                value=None
                            )
                            load_project_btn = gr.Button("📂 Load Selected Project")
                    
                    project_mgmt_status = gr.Textbox(
                        label="Project Status",
                        interactive=False,
                        lines=8
                    )
                
                # Tab 2: Generate Prompt
                with gr.Tab("2️⃣ Generate Prompt", id="tab_generate_prompt"):
                    gr.Markdown("### Upload reference image and describe your scene")
                    gr.Markdown("*Upload a green-zone base image to activate Phase 2 (element addition) mode automatically.*")

                    with gr.Row():
                        with gr.Column():
                            reference_image = gr.Image(
                                label="Character Reference (<IMAGE_0>)",
                                type="filepath",
                                image_mode=None
                            )
                            additional_images = gr.File(
                                label="Additional Characters (optional, Phase 1 only — <IMAGE_1>, <IMAGE_2>…)",
                                file_count="multiple",
                                type="filepath"
                            )
                            greenzone_image = gr.Image(
                                label="Green-zone Base Image (optional — triggers Phase 2, <IMAGE_1>)",
                                type="filepath",
                                image_mode=None
                            )

                        with gr.Column():
                            scene_description = gr.Textbox(
                                label="Scene / Enhancement Description",
                                placeholder="Phase 1: describe your scene.\nPhase 2: describe what to add in the green zones.",
                                lines=10
                            )

                    generate_prompt_btn = gr.Button("🎯 Generate Prompt", variant="primary")
                
                # Tab 3: Image Generation
                with gr.Tab("3️⃣ Generate Images", id="tab_generate_images"):
                    gr.Markdown("### Generate images using the prompt")
                    
                    with gr.Row():
                        prompt_to_use = gr.Textbox(
                            label="Prompt (edit if needed)",
                            lines=10,
                            max_lines=10,
                            placeholder="Paste or edit the prompt here..."
                        )
                    
                    with gr.Row():
                        num_images_slider = gr.Slider(
                            minimum=1,
                            maximum=10,
                            value=3,
                            step=1,
                            label="Number of Images"
                        )
                        aspect_ratio_dropdown = gr.Dropdown(
                            choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                            value="16:9",
                            label="Aspect Ratio",
                            info="Choose the aspect ratio for generated images"
                        )
                    
                    with gr.Row():
                        generate_images_btn = gr.Button("🖼️ Generate Images", variant="primary")
                    
                    with gr.Row():
                        output_gallery = gr.HTML()
                    
                # Tab 4: Review and Correction
                with gr.Tab("4️⃣ Review & Correct", id="tab_review"):
                    gr.Markdown("""### Review Failed Images and Get Corrections
                    
**How it works:**
1. **Send a message** to start the review (describe what's wrong or just ask to review)
2. Images are automatically pulled from the **Generate Images** tab, or you can **upload specific failed images**
3. Continue the conversation to refine the corrections
4. Extract the final prompt when satisfied

💡 **First message starts the review** - describe issues or just say "review these images"
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("**Option: Upload specific failed images**")
                            failed_images_upload = gr.File(
                                label="Upload Failed Images (or leave empty to use generated images)",
                                file_count="multiple",
                                type="filepath"
                            )
                    
                    # Chatbot interface for interactive review
                    review_chatbot = gr.Chatbot(
                        label="Review Conversation",
                        height=500,
                        show_label=False,
                        bubble_full_width=False,
                    )

                    with gr.Row(equal_height=True):
                        review_user_input = gr.Textbox(
                            placeholder="Describe issues, or just say 'review these images'. Refer to failed images as 'failed image 1', 'failed image 2', etc.",
                            lines=2,
                            max_lines=6,
                            scale=9,
                            show_label=False,
                            container=False
                        )
                        send_review_btn = gr.Button("Send", variant="primary", scale=1, min_width=90)
                    
                    # Thumbnail strip for images under review
                    failed_images_gallery = gr.HTML()
                    
                    gr.Markdown("---")
                    gr.Markdown("**When you're satisfied with the conversation:**")
                    
                    extract_and_send_btn = gr.Button("📤 Extract Final Prompt & Send to Generation Tab", variant="primary")
                    
                    # Event handlers defined after unified_status is created (see bottom of UI)
                
            
            # Unified Status Bar (bottom of UI)
            gr.Markdown("---")
            gr.Markdown("### 📊 Status & Model Selection")
            
            with gr.Row():
                with gr.Column(scale=1):
                    chat_model_dropdown = gr.Dropdown(
                        choices=["grok-4.20", "grok-2-1212", "grok-2-vision-1212", "grok-beta"],
                        value="grok-4.20",
                        label="💬 Chat Model",
                        info="For prompt generation & review",
                        interactive=True,
                        allow_custom_value=True
                    )
                
                with gr.Column(scale=1):
                    image_model_dropdown = gr.Dropdown(
                        choices=[
                            "grok-imagine-image-2.0",
                            "grok-imagine-image-quality",
                            "grok-imagine-image-pro",
                            "grok-imagine-image"
                        ],
                        value="grok-imagine-image-2.0",
                        label="🎨 Image Model",
                        info="For image generation",
                        interactive=True,
                        allow_custom_value=True
                    )
            
            unified_status = gr.Textbox(
                label="System Status",
                interactive=False,
                lines=3,
                value="Ready. Configure your API key above to get started."
            )
            
            # Wire up all event handlers that use unified_status
            OUTPUTS_PROJECT = [project_mgmt_status, current_project_display, prompt_to_use, failed_images_gallery, reference_image, scene_description, additional_images, review_chatbot, greenzone_image, output_gallery]

            # Tab 1: Project Management
            set_project_btn.click(fn=self._set_project_for_ui, inputs=[project_name_input_dup], outputs=OUTPUTS_PROJECT)
            project_name_input_dup.submit(fn=self._set_project_for_ui, inputs=[project_name_input_dup], outputs=OUTPUTS_PROJECT)
            load_project_btn.click(fn=self._load_project_for_ui, inputs=[project_selector], outputs=OUTPUTS_PROJECT)
            manual_save_btn.click(fn=self.save_project_state, outputs=[project_mgmt_status])
            project_selector.focus(fn=lambda: gr.Dropdown(choices=self.list_projects()), outputs=[project_selector])

            # Tab 2: Generate Prompt — reference image / additional images / greenzone pre-save on change
            reference_image.change(fn=self.update_reference_image, inputs=[reference_image], outputs=[unified_status])
            additional_images.change(fn=self.update_additional_images, inputs=[additional_images], outputs=[unified_status])
            greenzone_image.change(fn=self.update_greenzone_image, inputs=[greenzone_image], outputs=[unified_status])

            generate_prompt_btn.click(
                fn=self.generate_initial_prompt,
                inputs=[reference_image, scene_description, additional_images, greenzone_image],
                outputs=[unified_status, prompt_to_use, main_tabs]
            )

            # Tab 3: Generate Images
            generate_images_btn.click(
                fn=self._generate_images_for_ui,
                inputs=[prompt_to_use, num_images_slider, aspect_ratio_dropdown],
                outputs=[unified_status, output_gallery, failed_images_gallery]
            )

            # Tab 4: Review & Correct
            def send_message(msg, history, uploaded_files, current_gallery_html):
                if not msg.strip():
                    return history, "", "", current_gallery_html
                if not history:
                    review_result = self.start_phase1_review(msg, uploaded_files)
                    return review_result[0], "", review_result[1], render_gallery_html(review_result[2])
                else:
                    cont_result = self.continue_phase1_review(msg, history)
                    return cont_result[0], "", "", current_gallery_html

            send_review_btn.click(fn=send_message, inputs=[review_user_input, review_chatbot, failed_images_upload, failed_images_gallery], outputs=[review_chatbot, review_user_input, unified_status, failed_images_gallery])
            review_user_input.submit(fn=send_message, inputs=[review_user_input, review_chatbot, failed_images_upload, failed_images_gallery], outputs=[review_chatbot, review_user_input, unified_status, failed_images_gallery])
            extract_and_send_btn.click(fn=self.extract_prompt_from_phase1_chat, outputs=[prompt_to_use, unified_status, main_tabs])

            # Model selection
            chat_model_dropdown.change(fn=self.update_chat_model, inputs=[chat_model_dropdown], outputs=[unified_status])
            image_model_dropdown.change(fn=self.update_image_model, inputs=[image_model_dropdown], outputs=[unified_status])

            # Auto-load last project on page load
            app.load(fn=lambda: self._load_project_for_ui(), outputs=OUTPUTS_PROJECT)
            
        return app


def launch():
    """Launch the Gradio app."""
    app = FPVPOVApp()
    interface = app.create_interface()
    
    # Auto-initialize if API key exists in environment
    existing_key = os.getenv("XAI_API_KEY")
    if existing_key:
        print("🔑 Auto-initializing with API key from environment...")
        app.initialize_client(existing_key)
        app.client.image_model = "grok-imagine-image-2.0"
        chat_models, image_models = app.fetch_models()
        if chat_models and image_models:
            print(f"✅ Loaded {len(chat_models)} chat models and {len(image_models)} image models")
            print(f"🎨 Default image model: grok-imagine-image-2.0")
    
    interface.launch(share=False)


if __name__ == "__main__":
    launch()
