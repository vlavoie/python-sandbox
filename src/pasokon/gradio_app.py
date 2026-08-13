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
from datetime import datetime
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
        self.project_name = "untitled-project"
        
        # Review chat histories
        self.phase1_review_history = []
        self.phase2_review_history = []
        self.phase1_review_context = {}
        self.phase2_review_context = {}
        
        # Model lists
        self.available_chat_models = []
        self.available_image_models = []
        self.all_models = []
        
        # Output directory for saved images
        self.output_dir = Path(__file__).parent.parent.parent / "fpv-pov-outputs"
        self.output_dir.mkdir(exist_ok=True)
        
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
    
    def set_project_name(self, project_name: str) -> str:
        """Set the project name and reset iteration count."""
        if not project_name or not project_name.strip():
            return "❌ Project name cannot be empty"
        
        # Sanitize project name (remove special characters)
        sanitized = "".join(c if c.isalnum() or c in ('-', '_', ' ') else '_' for c in project_name)
        sanitized = sanitized.strip().replace(' ', '-').lower()
        
        if sanitized != self.project_name:
            self.project_name = sanitized
            self.iteration_count = 0
            return f"✅ Project set to: {sanitized} (Iteration counter reset)"
        return f"📁 Project: {sanitized}"
    
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
            error_msg = str(e)
            print(f"\n{'='*60}")
            print(f"ERROR IN PROMPT GENERATION:")
            print(f"{'='*60}")
            print(error_msg)
            print(f"{'='*60}\n")
            return f"❌ Error generating prompt: {error_msg}", ""
    
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
            img.save(img_path, 'PNG')
        
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
                additional_images=self.additional_images_paths if self.additional_images_paths else None,
                aspect_ratio=aspect_ratio
            )
            
            # Check if we got any images
            if not image_data_list or len(image_data_list) == 0:
                return "❌ No images were successfully generated. Check console for errors.", []
            
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
                img.save(temp_file.name, 'PNG')
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
            
            return status_msg, images
            
        except Exception as e:
            return f"❌ Error generating images: {str(e)}", []
    
    def start_phase1_review(
        self,
        manual_uploaded_images: Optional[List] = None
    ) -> Tuple[List, str]:
        """Start an interactive review conversation for Phase 1."""
        if not self.client:
            return [], "❌ Please configure your API key first."
        
        # Determine which images to review
        images_to_review = []
        
        if manual_uploaded_images:
            for img in manual_uploaded_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        images_to_review.append(path)
        elif self.generated_images:
            images_to_review = self.generated_images
        
        if not images_to_review:
            return [], "❌ No images to review. Please generate or upload images first."
        
        try:
            # Store context for this review session
            self.phase1_review_context = {
                "failed_images": images_to_review,
                "original_prompt": self.current_prompt,
                "scene_description": self.current_scene,
                "reference_image": self.reference_image_path,
                "additional_images": self.additional_images_paths
            }
            
            # Get initial review
            initial_review = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=self.current_scene,
                reference_image=self.reference_image_path,
                skill_content=self.review_skill,
                additional_images=self.additional_images_paths if self.additional_images_paths else None
            )
            
            # Initialize chat history
            self.phase1_review_history = [
                ("Please review these failed images and suggest corrections.", initial_review)
            ]
            
            return self.phase1_review_history, "✅ Review started! You can now ask questions or request changes."
            
        except Exception as e:
            return [], f"❌ Error during review: {str(e)}"
    
    def continue_phase1_review(self, user_message: str, history: List) -> Tuple[List, str]:
        """Continue the Phase 1 review conversation."""
        if not self.client:
            return history, "❌ Client not initialized"
        
        if not user_message.strip():
            return history, ""
        
        try:
            # Build conversation context with images
            messages = [{"role": "system", "content": self.review_skill}]
            
            # Add image context to first message
            if self.phase1_review_context:
                content = []
                
                # Add reference image
                if self.phase1_review_context.get("reference_image"):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(self.phase1_review_context['reference_image'])}"
                        }
                    })
                
                # Add failed images
                for img_path in self.phase1_review_context.get("failed_images", []):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(img_path)}"
                        }
                    })
                
                content.append({
                    "type": "text",
                    "text": f"Original prompt: {self.phase1_review_context.get('original_prompt', '')}\n\nScene: {self.phase1_review_context.get('scene_description', '')}"
                })
                
                messages.append({"role": "user", "content": content})
            
            # Add conversation history
            for user_msg, assistant_msg in history:
                if user_msg != "Please review these failed images and suggest corrections.":
                    messages.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    messages.append({"role": "assistant", "content": assistant_msg})
            
            # Add new user message
            messages.append({"role": "user", "content": user_message})
            
            # Get response
            import httpx
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.client.base_url}/chat/completions",
                    headers=self.client.headers,
                    json={
                        "model": self.client.chat_model,
                        "messages": messages
                    }
                )
                response.raise_for_status()
                result = response.json()
                assistant_response = result["choices"][0]["message"]["content"]
            
            # Update history
            new_history = history + [(user_message, assistant_response)]
            self.phase1_review_history = new_history
            
            return new_history, ""
            
        except Exception as e:
            return history, f"❌ Error: {str(e)}"
    
    def extract_prompt_from_phase1_chat(self) -> str:
        """Extract the final prompt from the Phase 1 review chat."""
        if not self.phase1_review_history:
            return ""
        
        # Get the last assistant message
        for user_msg, assistant_msg in reversed(self.phase1_review_history):
            if assistant_msg:
                # Use the same cleaning logic as the client
                from pasokon.grok_client import GrokClient
                return GrokClient._clean_prompt_text(assistant_msg)
        
        return ""
    
    def start_phase2_review(
        self,
        green_base_image,
        enhancement_description: str,
        failed_enhancement_images: Optional[List] = None
    ) -> Tuple[List, str]:
        """Start an interactive review conversation for Phase 2 enhancements.
        
        Args:
            green_base_image: The base image with green/pink zones (@image1)
            enhancement_description: What was supposed to be added
            failed_enhancement_images: Images that failed to meet requirements
        """
        if not self.client:
            return [], "❌ Please configure your API key first."
        
        if not green_base_image:
            return [], "❌ Please upload the green-zoned base image."
        
        if not self.reference_image_path:
            return [], "❌ No character reference found. Please upload a character reference in Tab 1 first."
        
        if not enhancement_description.strip():
            return [], "❌ Please provide enhancement description."
        
        # Save the base image
        green_base_path = self.save_uploaded_file(green_base_image)
        # Use character reference from Phase 1
        char_ref_path = self.reference_image_path
        
        # Get failed images to review
        images_to_review = []
        if failed_enhancement_images:
            for img in failed_enhancement_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        images_to_review.append(path)
        elif self.generated_images:
            images_to_review = self.generated_images
        
        if not images_to_review:
            return [], "❌ No enhancement images to review. Please generate or upload images first."
        
        try:
            # Store context for this review session
            phase2_scene = f"""Phase 2 Enhancement Review - Green Zone Addition:
{enhancement_description}

Context:
- <IMAGE_0> is the character reference for style/appearance matching (SAME as Phase 1)
- <IMAGE_1> is the base image with green/pink zones marking where elements should be added
- Only add elements inside the marked zones on <IMAGE_1>
- Completely erase all green/pink paint afterward
- Lock appearance/style to <IMAGE_0>
- Use <IMAGE_1> as the spatial base to modify

Review the failed enhancement attempts and identify what went wrong."""
            
            self.phase2_review_context = {
                "green_base_path": green_base_path,
                "char_ref_path": char_ref_path,
                "failed_images": images_to_review,
                "original_prompt": self.current_prompt,
                "phase2_scene": phase2_scene,
                "enhancement_description": enhancement_description
            }
            
            # Get initial review
            # IMPORTANT: Keep character reference as <IMAGE_0> for consistency with Phase 1
            corrected_response = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=phase2_scene,
                reference_image=char_ref_path,  # <IMAGE_0> = Character reference (consistent!)
                skill_content=self.review_skill,
                additional_images=[green_base_path]  # <IMAGE_1> = Green-marked base
            )
            
            # Initialize chat history
            self.phase2_review_history = [
                ("Please review these failed enhancement attempts and suggest corrections.", corrected_response)
            ]
            
            return self.phase2_review_history, "✅ Enhancement review started! You can now ask questions or request changes."
            
        except Exception as e:
            return [], f"❌ Error during enhancement review: {str(e)}"
    
    def continue_phase2_review(self, user_message: str, history: List) -> Tuple[List, str]:
        """Continue the Phase 2 enhancement review conversation."""
        if not self.client:
            return history, "❌ Client not initialized"
        
        if not user_message.strip():
            return history, ""
        
        try:
            # Build conversation context with images
            messages = [{"role": "system", "content": self.review_skill}]
            
            # Add image context to first message
            if self.phase2_review_context:
                content = []
                
                # Add character reference FIRST (<IMAGE_0>) for consistency with Phase 1
                if self.phase2_review_context.get("char_ref_path"):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(self.phase2_review_context['char_ref_path'])}"
                        }
                    })
                
                # Add green-zoned base image (<IMAGE_1>)
                if self.phase2_review_context.get("green_base_path"):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(self.phase2_review_context['green_base_path'])}"
                        }
                    })
                
                # Add failed enhancement images (for visual comparison)
                for img_path in self.phase2_review_context.get("failed_images", []):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(img_path)}"
                        }
                    })
                
                content.append({
                    "type": "text",
                    "text": f"{self.phase2_review_context.get('phase2_scene', '')}\\n\\nOriginal prompt: {self.phase2_review_context.get('original_prompt', '')}"
                })
                
                messages.append({"role": "user", "content": content})
            
            # Add conversation history
            for user_msg, assistant_msg in history:
                if user_msg != "Please review these failed enhancement attempts and suggest corrections.":
                    messages.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    messages.append({"role": "assistant", "content": assistant_msg})
            
            # Add new user message
            messages.append({"role": "user", "content": user_message})
            
            # Get response
            import httpx
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.client.base_url}/chat/completions",
                    headers=self.client.headers,
                    json={
                        "model": self.client.chat_model,
                        "messages": messages
                    }
                )
                response.raise_for_status()
                result = response.json()
                assistant_response = result["choices"][0]["message"]["content"]
            
            # Update history
            new_history = history + [(user_message, assistant_response)]
            self.phase2_review_history = new_history
            
            return new_history, ""
            
        except Exception as e:
            return history, f"❌ Error: {str(e)}"
    
    def extract_prompt_from_phase2_chat(self) -> str:
        """Extract the final prompt from the Phase 2 review chat."""
        if not self.phase2_review_history:
            return ""
        
        # Get the last assistant message
        for user_msg, assistant_msg in reversed(self.phase2_review_history):
            if assistant_msg:
                # Use the same cleaning logic as the client
                from pasokon.grok_client import GrokClient
                return GrokClient._clean_prompt_text(assistant_msg)
        
        return ""
    
    def review_enhancement(
        self,
        green_base_image,
        character_reference,
        enhancement_description: str,
        failed_enhancement_images: Optional[List] = None
    ) -> Tuple[str, str]:
        """Review failed enhancement images and generate corrected prompt (legacy method).
        
        Args:
            green_base_image: The base image with green/pink zones (<IMAGE_1>)
            character_reference: Original character reference (<IMAGE_0>)
            enhancement_description: What was supposed to be added
            failed_enhancement_images: Images that failed to meet requirements
        """
        if not self.client:
            return "❌ Please configure your API key first.", ""
        
        if not green_base_image:
            return "❌ Please upload the green-zoned base image.", ""
        
        if not character_reference:
            return "❌ Please upload the character reference image.", ""
        
        if not enhancement_description.strip():
            return "❌ Please provide enhancement description.", ""
        
        # Save the base images
        green_base_path = self.save_uploaded_file(green_base_image)
        char_ref_path = self.save_uploaded_file(character_reference)
        
        # Get failed images to review
        images_to_review = []
        if failed_enhancement_images:
            for img in failed_enhancement_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        images_to_review.append(path)
        elif self.generated_images:
            images_to_review = self.generated_images
        
        if not images_to_review:
            return "❌ No enhancement images to review. Please generate or upload images first.", ""
        
        try:
            # Create Phase 2 specific scene description
            phase2_scene = f"""Phase 2 Enhancement Review - Green Zone Addition:
{enhancement_description}

Context:
- <IMAGE_0> is the character reference for style/appearance matching (SAME as Phase 1)
- <IMAGE_1> is the base image with green/pink zones marking where elements should be added
- Only add elements inside the marked zones on <IMAGE_1>
- Completely erase all green/pink paint afterward
- Lock appearance/style to <IMAGE_0>
- Use <IMAGE_1> as the spatial base to modify

Review the failed enhancement attempts and identify what went wrong."""
            
            # Get corrected prompt
            # IMPORTANT: Keep character reference as <IMAGE_0> for consistency with Phase 1
            corrected_response = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=phase2_scene,
                reference_image=char_ref_path,  # <IMAGE_0> = Character reference (consistent!)
                skill_content=self.review_skill,
                additional_images=[green_base_path]  # <IMAGE_1> = Green-marked base
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
            
            return "✅ Enhancement review complete! Corrected prompt generated.", corrected_prompt
            
        except Exception as e:
            return f"❌ Error during enhancement review: {str(e)}", ""
    
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
                
                with gr.Row():
                    api_key_input = gr.Textbox(
                        label="Grok API Key (XAI_API_KEY)",
                        type="password",
                        placeholder="Enter your Grok API key or set XAI_API_KEY in .env file",
                        value=existing_key or ""
                    )
                
                api_status = gr.Textbox(label="Status", interactive=False, value=initial_status)
                
                # Project name input
                with gr.Row():
                    project_name_input = gr.Textbox(
                        label="Project Name",
                        placeholder="Enter a project name (e.g., ninja-scene, pirate-ship)",
                        value="untitled-project",
                        info="Organizes your outputs by project. Changing this resets the iteration counter."
                    )
                    project_status = gr.Textbox(label="Project Status", interactive=False, value="📁 Project: untitled-project")
                
                project_name_input.change(
                    fn=self.set_project_name,
                    inputs=[project_name_input],
                    outputs=[project_status]
                )
                
                # Model selection dropdowns
                with gr.Row():
                    chat_model_dropdown = gr.Dropdown(
                        choices=["grok-4.20", "grok-2-1212", "grok-2-vision-1212", "grok-beta"],
                        value="grok-4.20",
                        label="Chat Model (for prompt generation & review)",
                        info="Used for analyzing images and generating prompts",
                        interactive=True,
                        allow_custom_value=True
                    )
                    image_model_dropdown = gr.Dropdown(
                        choices=[
                            "grok-imagine-image-quality",
                            "grok-imagine-image-pro", 
                            "grok-imagine-image-2.0",
                            "grok-imagine-image"
                        ],
                        value="grok-imagine-image-quality",
                        label="Image Generation Model",
                        info="Used for creating FPV POV images (quality recommended)",
                        interactive=True,
                        allow_custom_value=True
                    )
                
                model_status = gr.Textbox(label="Model Status", interactive=False, value="")
                
                # Update models when they change
                chat_model_dropdown.change(
                    fn=self.update_chat_model,
                    inputs=[chat_model_dropdown],
                    outputs=[model_status]
                )
                
                image_model_dropdown.change(
                    fn=self.update_image_model,
                    inputs=[image_model_dropdown],
                    outputs=[model_status]
                )
                
                # Initialize client and fetch models
                def init_and_fetch_models(api_key):
                    status = self.initialize_client(api_key)
                    chat_models, image_models = self.fetch_models()
                    
                    # Return updated choices and values
                    return (
                        status,
                        gr.Dropdown(choices=chat_models, value=chat_models[0] if chat_models else "grok-4.20"),
                        gr.Dropdown(choices=image_models, value=image_models[0] if image_models else "grok-imagine-image-2.0")
                    )
                
                api_key_input.change(
                    fn=init_and_fetch_models,
                    inputs=[api_key_input],
                    outputs=[api_status, chat_model_dropdown, image_model_dropdown]
                )
            
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
                        aspect_ratio_dropdown = gr.Dropdown(
                            choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                            value="16:9",
                            label="Aspect Ratio",
                            info="Choose the aspect ratio for generated images"
                        )
                    
                    with gr.Row():
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
                        inputs=[prompt_to_use, num_images_slider, aspect_ratio_dropdown],
                        outputs=[generation_status, output_gallery]
                    )
                
                # Tab 3: Review and Correction
                with gr.Tab("3️⃣ Review & Correct"):
                    gr.Markdown("### Interactive review with the reviewer skill")
                    gr.Markdown("Have a conversation with the reviewer to refine your prompt!")
                    
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
                    
                    start_review_btn = gr.Button("🔍 Start Review", variant="primary")
                    review_status = gr.Textbox(label="Status", interactive=False)
                    
                    # Chatbot interface for interactive review
                    review_chatbot = gr.Chatbot(
                        label="Review Conversation",
                        height=400
                    )
                    
                    with gr.Row():
                        review_user_input = gr.Textbox(
                            label="Your message",
                            placeholder="Ask questions or request changes (e.g., 'Can you explain why you changed the lighting?', 'Keep the original pose but fix the hands')",
                            lines=2
                        )
                        send_review_btn = gr.Button("Send", variant="secondary")
                    
                    gr.Markdown("---")
                    gr.Markdown("**When you're satisfied with the conversation, extract the final prompt:**")
                    
                    extract_prompt_btn = gr.Button("📄 Extract Final Prompt from Conversation")
                    corrected_prompt = gr.Textbox(
                        label="Final Corrected Prompt",
                        lines=10,
                        interactive=True
                    )
                    
                    gr.Markdown("**Use this corrected prompt in Tab 2 to regenerate images**")
                    copy_to_gen_btn = gr.Button("📋 Copy to Generation Tab")
                    
                    # Event handlers
                    start_review_btn.click(
                        fn=self.start_phase1_review,
                        inputs=[failed_images_upload],
                        outputs=[review_chatbot, review_status]
                    )
                    
                    def send_message(msg, history):
                        if not msg.strip():
                            return history, "", ""
                        return self.continue_phase1_review(msg, history)[0], "", ""
                    
                    send_review_btn.click(
                        fn=send_message,
                        inputs=[review_user_input, review_chatbot],
                        outputs=[review_chatbot, review_user_input, review_status]
                    )
                    
                    review_user_input.submit(
                        fn=send_message,
                        inputs=[review_user_input, review_chatbot],
                        outputs=[review_chatbot, review_user_input, review_status]
                    )
                    
                    extract_prompt_btn.click(
                        fn=self.extract_prompt_from_phase1_chat,
                        outputs=[corrected_prompt]
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
                    3. Upload the green-marked base as @image1 (character reference from Tab 1 will be used as @image2)
                    4. Describe what to add in the green zones
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            green_base_image = gr.Image(
                                label="Green-Marked Base Image (@image1)",
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
                    
                    # This uses the same prompt generation logic but with phase 2 context
                    enhance_prompt_btn.click(
                        fn=lambda base, desc: self.generate_initial_prompt(
                            base,
                            f"Phase 2 Enhancement - Green Zone Addition:\n{desc}\n\nOnly add elements inside the green zones. Completely erase all green paint afterward. Lock everything else to @image1. Use @image2 for style/hair lock.",
                            [self.reference_image_path] if self.reference_image_path else None
                        ),
                        inputs=[green_base_image, enhancement_description],
                        outputs=[enhance_status, enhancement_prompt]
                    )
                    
                    gr.Markdown("---")
                    gr.Markdown("### 🔍 Interactive Enhancement Review")
                    gr.Markdown("""
                    After generating enhanced images in Tab 2, review them here with an interactive conversation.
                    
                    **Upload the green-zoned base (character reference from Tab 1 will be used automatically).**
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            review_green_base = gr.Image(
                                label="Green-Zoned Base Image (@image1)",
                                type="filepath"
                            )
                        
                        with gr.Column():
                            review_enhancement_desc = gr.Textbox(
                                label="What You Tried to Add",
                                placeholder="What elements did you try to add in the zones?",
                                lines=6
                            )
                            failed_enhancements = gr.File(
                                label="Failed Enhancement Images (or leave empty to auto-use images from Tab 2)",
                                file_count="multiple",
                                type="filepath"
                            )
                    
                    start_enhance_review_btn = gr.Button("🔍 Start Enhancement Review", variant="primary")
                    review_enhance_status = gr.Textbox(label="Review Status", interactive=False)
                    
                    # Chatbot interface for interactive enhancement review
                    enhance_review_chatbot = gr.Chatbot(
                        label="Enhancement Review Conversation",
                        height=400
                    )
                    
                    with gr.Row():
                        enhance_review_user_input = gr.Textbox(
                            label="Your message",
                            placeholder="Ask questions or request changes (e.g., 'Why didn't the hair match the reference?', 'Try keeping more of the original lighting')",
                            lines=2
                        )
                        send_enhance_review_btn = gr.Button("Send", variant="secondary")
                    
                    gr.Markdown("---")
                    gr.Markdown("**When you're satisfied with the conversation, extract the final prompt:**")
                    
                    extract_enhance_prompt_btn = gr.Button("📄 Extract Final Enhancement Prompt from Conversation")
                    corrected_enhancement_prompt = gr.Textbox(
                        label="Final Corrected Enhancement Prompt",
                        lines=10,
                        interactive=True
                    )
                    
                    gr.Markdown("**Copy this corrected prompt to Tab 2 to regenerate enhanced images**")
                    copy_enhance_to_gen_btn = gr.Button("📋 Copy to Generation Tab")
                    
                    # Event handlers for Phase 2 review
                    start_enhance_review_btn.click(
                        fn=self.start_phase2_review,
                        inputs=[review_green_base, review_enhancement_desc, failed_enhancements],
                        outputs=[enhance_review_chatbot, review_enhance_status]
                    )
                    
                    def send_enhance_message(msg, history):
                        if not msg.strip():
                            return history, "", ""
                        return self.continue_phase2_review(msg, history)[0], "", ""
                    
                    send_enhance_review_btn.click(
                        fn=send_enhance_message,
                        inputs=[enhance_review_user_input, enhance_review_chatbot],
                        outputs=[enhance_review_chatbot, enhance_review_user_input, review_enhance_status]
                    )
                    
                    enhance_review_user_input.submit(
                        fn=send_enhance_message,
                        inputs=[enhance_review_user_input, enhance_review_chatbot],
                        outputs=[enhance_review_chatbot, enhance_review_user_input, review_enhance_status]
                    )
                    
                    extract_enhance_prompt_btn.click(
                        fn=self.extract_prompt_from_phase2_chat,
                        outputs=[corrected_enhancement_prompt]
                    )
                    
                    copy_enhance_to_gen_btn.click(
                        fn=lambda x: x,
                        inputs=[corrected_enhancement_prompt],
                        outputs=[prompt_to_use]
                    )
                    
                    gr.Markdown("**Generate enhanced images using the prompt above in Tab 2**")
            
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
    
    # Auto-initialize if API key exists in environment
    existing_key = os.getenv("XAI_API_KEY")
    if existing_key:
        print("🔑 Auto-initializing with API key from environment...")
        app.initialize_client(existing_key)
        # Set default to quality model
        app.client.image_model = "grok-imagine-image-quality"
        chat_models, image_models = app.fetch_models()
        if chat_models and image_models:
            print(f"✅ Loaded {len(chat_models)} chat models and {len(image_models)} image models")
            print(f"🎨 Default image model: grok-imagine-image-quality")
    
    interface.launch(share=False)


if __name__ == "__main__":
    launch()
