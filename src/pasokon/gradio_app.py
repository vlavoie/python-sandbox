"""Gradio application for FPV POV image generation workflow."""

import gradio as gr
from pathlib import Path
from typing import Optional, List, Tuple
import tempfile
import shutil
from PIL import Image
import io
import os
import sys
from dotenv import load_dotenv

from .grok_client import GrokClient

# Load environment variables from .env file
load_dotenv()

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import locale
    # Set environment variable for Python UTF-8 mode
    os.environ.setdefault('PYTHONUTF8', '1')


class FPVPOVApp:
    """Gradio app for automating FPV POV image generation."""
    
    def __init__(self):
        """Initialize the app."""
        self.client = None
        self.current_prompt = ""
        self.current_scene = ""
        self.reference_image_path = None
        self.additional_images_paths = []
        self.generated_images = []
        self.iteration_count = 0
        
        # Load skill files with explicit UTF-8 encoding
        self.skill_dir = Path(__file__).parent.parent.parent
        try:
            with open(self.skill_dir / "fpv-pov-image.md", "r", encoding='utf-8', errors='replace') as f:
                self.prompt_skill = f.read()
            with open(self.skill_dir / "fpv-pov-review.md", "r", encoding='utf-8', errors='replace') as f:
                self.review_skill = f.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Skill files not found. Please ensure fpv-pov-image.md and fpv-pov-review.md "
                f"are in the project root directory: {self.skill_dir}"
            ) from e
        except Exception as e:
            raise Exception(f"Error loading skill files: {e}") from e
    
    def initialize_client(self, api_key: str) -> str:
        """Initialize the Grok client with API key."""
        try:
            self.client = GrokClient(api_key=api_key)
            return "✅ API key configured successfully!"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def save_uploaded_file(self, file) -> Optional[str]:
        """Save an uploaded file to a temporary location."""
        if file is None:
            return None
        
        # Create a temp file
        suffix = Path(file.name).suffix if hasattr(file, 'name') else '.jpg'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        
        # Copy the file
        if isinstance(file, str):
            # It's already a path
            shutil.copy(file, temp_file.name)
        else:
            # It's a file object
            shutil.copy(file.name, temp_file.name)
        
        temp_file.close()
        return temp_file.name
    
    def generate_initial_prompt(
        self,
        reference_image,
        scene_description: str,
        additional_images: Optional[List] = None
    ) -> Tuple[str, str]:
        """Generate the initial Grok Imagine prompt."""
        if not self.client:
            return "❌ Please configure your API key first.", ""
        
        if not reference_image:
            return "❌ Please upload a character reference image.", ""
        
        if not scene_description.strip():
            return "❌ Please provide a scene description.", ""
        
        try:
            # Save reference image
            self.reference_image_path = self.save_uploaded_file(reference_image)
            
            # Save additional images if provided
            self.additional_images_paths = []
            if additional_images:
                for img in additional_images:
                    if img is not None:
                        path = self.save_uploaded_file(img)
                        if path:
                            self.additional_images_paths.append(path)
            
            # Generate prompt
            self.current_scene = scene_description
            self.current_prompt = self.client.generate_prompt(
                reference_image=self.reference_image_path,
                scene_description=scene_description,
                skill_content=self.prompt_skill,
                additional_images=self.additional_images_paths if self.additional_images_paths else None
            )
            
            return "✅ Prompt generated successfully!", self.current_prompt
            
        except Exception as e:
            return f"❌ Error generating prompt: {str(e)}", ""
    
    def generate_images_batch(
        self,
        prompt: str,
        num_images: int = 3
    ) -> Tuple[str, List]:
        """Generate a batch of images using Grok Imagine."""
        if not self.client:
            return "❌ Please configure your API key first.", []
        
        if not prompt.strip():
            return "❌ Please provide a prompt.", []
        
        if not self.reference_image_path:
            return "❌ No reference image available.", []
        
        try:
            self.iteration_count += 1
            
            # Generate images
            image_data_list = self.client.generate_images(
                prompt=prompt,
                reference_image=self.reference_image_path,
                num_images=num_images,
                additional_images=self.additional_images_paths if self.additional_images_paths else None
            )
            
            # Convert to PIL Images for display
            images = []
            for img_data in image_data_list:
                img = Image.open(io.BytesIO(img_data))
                
                # Save to temp file for later use
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img.save(temp_file.name, 'PNG')
                temp_file.close()
                
                images.append(temp_file.name)
            
            self.generated_images = images
            self.current_prompt = prompt
            
            return f"✅ Generated {len(images)} images (Iteration {self.iteration_count})", images
            
        except Exception as e:
            return f"❌ Error generating images: {str(e)}", []
    
    def review_and_correct(
        self,
        manual_uploaded_images: Optional[List] = None
    ) -> Tuple[str, str]:
        """Review failed images and generate corrected prompt."""
        if not self.client:
            return "❌ Please configure your API key first.", ""
        
        # Determine which images to review
        images_to_review = []
        
        if manual_uploaded_images:
            # User uploaded specific failed images
            for img in manual_uploaded_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        images_to_review.append(path)
        elif self.generated_images:
            # Use all generated images from previous generation
            images_to_review = self.generated_images
        
        if not images_to_review:
            return "❌ No images to review. Please generate or upload images first.", ""
        
        try:
            # Get corrected prompt
            corrected_response = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=self.current_scene,
                reference_image=self.reference_image_path,
                skill_content=self.review_skill,
                additional_images=self.additional_images_paths if self.additional_images_paths else None
            )
            
            # Extract just the prompt if it's in a code block
            if "```" in corrected_response:
                parts = corrected_response.split("```")
                if len(parts) >= 3:
                    corrected_prompt = parts[1].strip()
                else:
                    corrected_prompt = corrected_response
            else:
                corrected_prompt = corrected_response
            
            return "✅ Review complete! Corrected prompt generated.", corrected_prompt
            
        except Exception as e:
            return f"❌ Error during review: {str(e)}", ""
    
    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface."""
        with gr.Blocks(title="FPV POV Image Generator", theme=gr.themes.Soft()) as app:
            gr.Markdown("# 🎨 FPV POV Image Generator")
            gr.Markdown("Automate your Grok-based first-person POV image generation workflow")
            
            # API Key configuration
            with gr.Accordion("⚙️ Configuration", open=True):
                # Check if API key is already set
                existing_key = os.getenv("XAI_API_KEY")
                initial_status = "✅ API key loaded from .env file" if existing_key else "Please enter your API key"
                
                api_key_input = gr.Textbox(
                    label="Grok API Key (XAI_API_KEY)",
                    type="password",
                    placeholder="Enter your Grok API key or set XAI_API_KEY in .env file",
                    value=existing_key or ""
                )
                api_status = gr.Textbox(label="Status", interactive=False, value=initial_status)
                api_key_input.change(
                    fn=self.initialize_client,
                    inputs=[api_key_input],
                    outputs=[api_status]
                )
                
                # Auto-initialize if key exists
                if existing_key:
                    self.initialize_client(existing_key)
            
            # Main workflow tabs
            with gr.Tabs():
                # Tab 1: Initial Prompt Generation
                with gr.Tab("1️⃣ Generate Prompt"):
                    gr.Markdown("### Upload reference image and describe your scene")
                    
                    with gr.Row():
                        with gr.Column():
                            reference_image = gr.Image(
                                label="Character Reference Image (@image1)",
                                type="filepath"
                            )
                            additional_images = gr.File(
                                label="Additional Character References (optional, @image2, @image3...)",
                                file_count="multiple",
                                type="filepath"
                            )
                        
                        with gr.Column():
                            scene_description = gr.Textbox(
                                label="Scene Description",
                                placeholder="Describe your scene in detail...",
                                lines=10
                            )
                    
                    generate_prompt_btn = gr.Button("🎯 Generate Prompt", variant="primary")
                    prompt_status = gr.Textbox(label="Status", interactive=False)
                    generated_prompt = gr.Textbox(
                        label="Generated Prompt",
                        lines=15,
                        interactive=True
                    )
                    
                    generate_prompt_btn.click(
                        fn=self.generate_initial_prompt,
                        inputs=[reference_image, scene_description, additional_images],
                        outputs=[prompt_status, generated_prompt]
                    )
                
                # Tab 2: Image Generation
                with gr.Tab("2️⃣ Generate Images"):
                    gr.Markdown("### Generate images using the prompt")
                    
                    with gr.Row():
                        prompt_to_use = gr.Textbox(
                            label="Prompt (edit if needed)",
                            lines=10,
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
                        generate_images_btn = gr.Button("🖼️ Generate Images", variant="primary")
                    
                    generation_status = gr.Textbox(label="Status", interactive=False)
                    
                    with gr.Row():
                        output_gallery = gr.Gallery(
                            label="Generated Images",
                            columns=3,
                            height="auto"
                        )
                    
                    # Copy prompt from previous tab
                    generated_prompt.change(
                        fn=lambda x: x,
                        inputs=[generated_prompt],
                        outputs=[prompt_to_use]
                    )
                    
                    generate_images_btn.click(
                        fn=self.generate_images_batch,
                        inputs=[prompt_to_use, num_images_slider],
                        outputs=[generation_status, output_gallery]
                    )
                
                # Tab 3: Review and Correction
                with gr.Tab("3️⃣ Review & Correct"):
                    gr.Markdown("### Review generated images and get corrected prompt")
                    
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("**Option A: Use generated images**")
                            gr.Markdown("Images from previous tab will be used automatically")
                        
                        with gr.Column():
                            gr.Markdown("**Option B: Upload specific failed images**")
                            failed_images_upload = gr.File(
                                label="Upload Failed Images",
                                file_count="multiple",
                                type="filepath"
                            )
                    
                    review_btn = gr.Button("🔍 Review & Generate Corrected Prompt", variant="primary")
                    review_status = gr.Textbox(label="Status", interactive=False)
                    corrected_prompt = gr.Textbox(
                        label="Corrected Prompt",
                        lines=15,
                        interactive=True
                    )
                    
                    gr.Markdown("**Use this corrected prompt in Tab 2 to regenerate images**")
                    copy_to_gen_btn = gr.Button("📋 Copy to Generation Tab")
                    
                    review_btn.click(
                        fn=self.review_and_correct,
                        inputs=[failed_images_upload],
                        outputs=[review_status, corrected_prompt]
                    )
                    
                    copy_to_gen_btn.click(
                        fn=lambda x: x,
                        inputs=[corrected_prompt],
                        outputs=[prompt_to_use]
                    )
                
                # Tab 4: Phase 2 - Manual Enhancement
                with gr.Tab("4️⃣ Phase 2: Enhancements"):
                    gr.Markdown("### Manual zoning and enhancement generation")
                    gr.Markdown("""
                    This phase is for adding elements that often hallucinate (like hair fringe).
                    
                    **Workflow:**
                    1. Take your best base image from Phase 1
                    2. Mark green zones in Photoshop/GIMP where you want elements added
                    3. Upload the green-marked base as @image1
                    4. Upload original character reference as @image2
                    5. Describe what to add in the green zones
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            green_base_image = gr.Image(
                                label="Green-Marked Base Image (@image1)",
                                type="filepath"
                            )
                            original_char_ref = gr.Image(
                                label="Original Character Reference (@image2)",
                                type="filepath"
                            )
                        
                        with gr.Column():
                            enhancement_description = gr.Textbox(
                                label="Enhancement Description",
                                placeholder="Describe what to add in the green zones (e.g., 'soft long dark curly peripheral fringe hair')",
                                lines=8
                            )
                    
                    enhance_prompt_btn = gr.Button("🎯 Generate Enhancement Prompt", variant="primary")
                    enhance_status = gr.Textbox(label="Status", interactive=False)
                    enhancement_prompt = gr.Textbox(
                        label="Enhancement Prompt",
                        lines=15,
                        interactive=True
                    )
                    
                    gr.Markdown("**Generate enhanced images using the prompt above in Tab 2**")
                    
                    # This uses the same prompt generation logic but with phase 2 context
                    enhance_prompt_btn.click(
                        fn=lambda base, ref, desc: self.generate_initial_prompt(
                            base,
                            f"Phase 2 Enhancement - Green Zone Addition:\n{desc}\n\nOnly add elements inside the green zones. Completely erase all green paint afterward. Lock everything else to @image1. Use @image2 for style/hair lock.",
                            [ref] if ref else None
                        ),
                        inputs=[green_base_image, original_char_ref, enhancement_description],
                        outputs=[enhance_status, enhancement_prompt]
                    )
            
            # Instructions footer
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
                - Either enter it in the Configuration section or set the `XAI_API_KEY` environment variable
                """)
        
        return app


def launch():
    """Launch the Gradio app."""
    app = FPVPOVApp()
    interface = app.create_interface()
    interface.launch(share=False)


if __name__ == "__main__":
    launch()
