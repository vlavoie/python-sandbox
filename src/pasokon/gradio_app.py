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
        
        # Review chat histories (Tab 3 handles both Phase 1 and Phase 2 reviews)
        self.phase1_review_history = []
        self.phase1_review_context = {}
        
        # Phase 2 context (for enhancement generation in Tab 4)
        self.greenzone_image_path = None
        self.current_phase2_description = ""
        self.review_mode = "phase1"  # or "phase2" - controls image ordering in Tab 3
        
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
    
    def _get_project_display_string(self) -> str:
        """Generate the current project display string for the top bar."""
        return f"**📁 Current Project:** `{self.project_name}` | **🎯 Mode:** `{self.review_mode}` | 💾 Auto-saves after each action"
    
    def clear_state(self):
        """Clear all project state variables."""
        self.current_prompt = ""
        self.current_scene = ""
        self.reference_image_path = None
        self.additional_images_paths = []
        self.generated_images = []
        self.iteration_count = 0
        self.phase1_review_history = []
        self.phase1_review_context = {}
        self.greenzone_image_path = None
        self.current_phase2_description = ""
        self.review_mode = "phase1"
    
    def set_project_name(self, project_name: str) -> Tuple[str, str, str, List, Optional[str], str, List, List, Optional[str], str, List]:
        """Set the project name and reset iteration count."""
        if not project_name or not project_name.strip():
            return "❌ Project name cannot be empty", self._get_project_display_string(), "", [], None, "", [], [], None, "", []
        
        # Sanitize project name (remove special characters)
        sanitized = "".join(c if c.isalnum() or c in ('-', '_', ' ') else '_' for c in project_name)
        sanitized = sanitized.strip().replace(' ', '-').lower()
        
        if sanitized != self.project_name:
            # Check if this is a new project (doesn't exist yet)
            metadata_path = self.output_dir / sanitized / ".project_metadata.json"
            is_new_project = not metadata_path.exists()
            
            if is_new_project:
                # New project - clear all state
                self.clear_state()
            
            self.project_name = sanitized
            status_msg = f"✅ Project set to: {sanitized}"
            if is_new_project:
                status_msg += " (New project - state cleared)"
            
            # Return cleared UI values for new project, or current values for existing project
            return (
                status_msg,
                self._get_project_display_string(),
                "" if is_new_project else self.current_prompt,
                [] if is_new_project else self.generated_images,
                None if is_new_project else self.reference_image_path,
                "" if is_new_project else self.current_scene,
                [] if is_new_project else self.additional_images_paths,
                [] if is_new_project else self.phase1_review_history,
                None if is_new_project else self.greenzone_image_path,
                "" if is_new_project else self.current_phase2_description,
                [] if is_new_project else self.generated_images  # output_gallery
            )
        return f"📁 Project: {sanitized}", self._get_project_display_string(), self.current_prompt, self.generated_images, self.reference_image_path, self.current_scene, self.additional_images_paths, self.phase1_review_history, self.greenzone_image_path, self.current_phase2_description, self.generated_images
    
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
    
    def _get_project_metadata_path(self, project_name: str = None) -> Path:
        """Get the path to the project metadata file."""
        proj_name = project_name or self.project_name
        project_dir = self.output_dir / proj_name
        return project_dir / ".project_metadata.json"
    
    def _copy_image_to_project(self, image_path: str, image_type: str) -> str:
        """Copy an image to the project's references directory.
        
        Args:
            image_path: Path to the source image
            image_type: Type of image (e.g., 'reference', 'additional_0', 'greenzone')
            
        Returns:
            Path to the copied image in the project directory
        """
        if not image_path or not Path(image_path).exists():
            return image_path
        
        try:
            project_dir = self.output_dir / self.project_name
            references_dir = project_dir / "references"
            references_dir.mkdir(parents=True, exist_ok=True)
            
            # Get file extension
            suffix = Path(image_path).suffix or '.jpg'
            
            # Create destination path
            dest_path = references_dir / f"{image_type}{suffix}"
            
            # Copy the file
            shutil.copy(image_path, dest_path)
            
            return str(dest_path)
        except Exception as e:
            print(f"Warning: Could not copy {image_type} to project directory: {e}")
            return image_path
    
    def save_project_state(self) -> str:
        """Save current project state to disk for persistence across sessions."""
        try:
            project_dir = self.output_dir / self.project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            
            metadata_path = self._get_project_metadata_path()
            
            # Copy reference images to project directory for persistence
            saved_reference_image_path = None
            if self.reference_image_path:
                saved_reference_image_path = self._copy_image_to_project(
                    self.reference_image_path, "character_reference"
                )
            
            saved_additional_images_paths = []
            if self.additional_images_paths:
                for idx, img_path in enumerate(self.additional_images_paths):
                    saved_path = self._copy_image_to_project(
                        img_path, f"additional_{idx}"
                    )
                    saved_additional_images_paths.append(saved_path)
            
            saved_greenzone_image_path = None
            if self.greenzone_image_path:
                saved_greenzone_image_path = self._copy_image_to_project(
                    self.greenzone_image_path, "greenzone_base"
                )
            
            state = {
                "project_name": self.project_name,
                "current_prompt": self.current_prompt,
                "current_scene": self.current_scene,
                "reference_image_path": saved_reference_image_path,
                "additional_images_paths": saved_additional_images_paths,
                "generated_images": self.generated_images,
                "iteration_count": self.iteration_count,
                "review_mode": self.review_mode,
                "greenzone_image_path": saved_greenzone_image_path,
                "current_phase2_description": self.current_phase2_description,
                "phase1_review_history": self.phase1_review_history,
                "phase1_review_context": self.phase1_review_context,
                "last_saved": datetime.now().isoformat(),
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Also save a "last project" marker
            last_project_path = self.output_dir / ".last_project.txt"
            with open(last_project_path, 'w') as f:
                f.write(self.project_name)
            
            # Count saved images
            saved_ref_count = 1 if saved_reference_image_path else 0
            saved_additional_count = len(saved_additional_images_paths)
            saved_greenzone_count = 1 if saved_greenzone_image_path else 0
            total_refs = saved_ref_count + saved_additional_count + saved_greenzone_count
            
            return f"✅ Project '{self.project_name}' saved ({total_refs} reference image(s) backed up)"
        except Exception as e:
            return f"⚠️ Could not save project: {str(e)}"
    
    def load_project_state(self, project_name: str = None) -> Tuple[str, str, str, List, Optional[str], str, List, List, Optional[str], str, List]:
        """Load project state from disk."""
        # Clear state before loading to ensure clean slate
        self.clear_state()
        
        try:
            # If no project specified, try to load the last project
            if not project_name:
                last_project_path = self.output_dir / ".last_project.txt"
                if last_project_path.exists():
                    project_name = last_project_path.read_text().strip()
                else:
                    return "ℹ️ No saved project found", self._get_project_display_string(), "", [], None, "", [], [], None, "", []
            
            metadata_path = self._get_project_metadata_path(project_name)
            
            if not metadata_path.exists():
                return f"ℹ️ No saved state found for project '{project_name}'", self._get_project_display_string(), "", [], None, "", [], [], None, "", []
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Restore state
            self.project_name = state.get("project_name", "untitled-project")
            self.current_prompt = state.get("current_prompt", "")
            self.current_scene = state.get("current_scene", "")
            self.reference_image_path = state.get("reference_image_path")
            self.additional_images_paths = state.get("additional_images_paths", [])
            self.generated_images = state.get("generated_images", [])
            self.iteration_count = state.get("iteration_count", 0)
            self.review_mode = state.get("review_mode", "phase1")
            self.greenzone_image_path = state.get("greenzone_image_path")
            self.current_phase2_description = state.get("current_phase2_description", "")
            self.phase1_review_history = state.get("phase1_review_history", [])
            self.phase1_review_context = state.get("phase1_review_context", {})
            
            last_saved = state.get("last_saved", "unknown")
            
            # Check if reference images exist
            ref_exists = self.reference_image_path and Path(self.reference_image_path).exists()
            additional_count = len([p for p in self.additional_images_paths if Path(p).exists()])
            
            # Load images for display (convert paths to list for gallery)
            images_to_display = [img for img in self.generated_images if Path(img).exists()]
            
            # Prepare reference image (return path if exists, None otherwise)
            ref_image_to_load = self.reference_image_path if (self.reference_image_path and Path(self.reference_image_path).exists()) else None
            
            # Prepare additional images (filter to only existing paths)
            additional_images_to_load = [p for p in self.additional_images_paths if Path(p).exists()]
            
            # Prepare Phase 2 greenzone image and description
            greenzone_image_to_load = self.greenzone_image_path if (self.greenzone_image_path and Path(self.greenzone_image_path).exists()) else None
            phase2_desc_to_load = self.current_phase2_description
            
            return f"""✅ Loaded project '{self.project_name}'
            
📅 Last saved: {last_saved}
🎯 Mode: {self.review_mode}
📝 Prompt: {'Set' if self.current_prompt else 'Not set'}
📄 Scene description: {'Set' if self.current_scene else 'Not set'}
🖼️ Character reference: {'✅ Available' if ref_exists else '❌ Missing'}
➕ Additional images: {additional_count}
📸 Generated images: {len(self.generated_images)}
🔄 Iterations: {self.iteration_count}
💬 Review history: {len(self.phase1_review_history)} message(s)
🎨 Phase 2: {'✅ Configured' if greenzone_image_to_load else '❌ Not set'}""", self._get_project_display_string(), self.current_prompt, images_to_display, ref_image_to_load, self.current_scene, additional_images_to_load, self.phase1_review_history, greenzone_image_to_load, phase2_desc_to_load, images_to_display
            
        except Exception as e:
            return f"❌ Error loading project: {str(e)}", self._get_project_display_string(), "", [], None, "", [], [], None, "", []
    
    def list_projects(self) -> List[str]:
        """List all available projects."""
        try:
            if not self.output_dir.exists():
                return []
            
            projects = []
            for item in self.output_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    metadata_path = item / ".project_metadata.json"
                    if metadata_path.exists():
                        # Has metadata, include with timestamp
                        try:
                            with open(metadata_path, 'r') as f:
                                state = json.load(f)
                                last_saved = state.get("last_saved", "")
                                projects.append((item.name, last_saved))
                        except:
                            projects.append((item.name, ""))
                    else:
                        # Old project without metadata
                        projects.append((item.name, ""))
            
            # Sort by last saved (most recent first)
            projects.sort(key=lambda x: x[1], reverse=True)
            return [name for name, _ in projects]
        except Exception as e:
            print(f"Error listing projects: {e}")
            return []
    
    def generate_initial_prompt(
        self,
        reference_image,
        scene_description: str,
        additional_images: Optional[List] = None
    ) -> Tuple[str, str, Any]:
        """Generate the initial Grok Imagine prompt."""
        if not self.client:
            return "❌ Please configure your API key first.", "", gr.update()
        
        if not reference_image:
            return "❌ Please upload a character reference image.", "", gr.update()
        
        if not scene_description.strip():
            return "❌ Please provide a scene description.", "", gr.update()
        
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
            
            # Auto-save project state
            self.save_project_state()
            
            return "✅ Prompt generated successfully!", self.current_prompt, gr.update(selected=2)
            
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
    
    def start_phase1_review(
        self,
        user_comment: str,
        manual_uploaded_images: Optional[List] = None
    ) -> Tuple[List, str]:
        """Start an interactive review conversation.
        
        This handles BOTH Phase 1 and Phase 2 reviews.
        The review_mode instance variable determines image ordering:
        - phase1: IMAGE_0=character, IMAGE_1+=additional characters
        - phase2: IMAGE_0=character, IMAGE_1=greenzone base
        """
        if not self.client:
            return [], "❌ Please configure your API key first.", []
        
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
            return [], "❌ No images to review. Please generate or upload images first.", []
        
        try:
            # Determine image ordering based on review mode
            if self.review_mode == "phase2":
                # Phase 2: IMAGE_0=character, IMAGE_1=greenzone
                reference_image = self.reference_image_path
                additional_images = [self.greenzone_image_path] if self.greenzone_image_path else []
                scene_description = f"""Phase 2 Enhancement Review:
{self.current_phase2_description}

Context:
- <IMAGE_0> is the character reference for style/appearance (SAME as Phase 1)
- <IMAGE_1> is the green-zoned base image marking where to add elements
- Only add inside green zones on <IMAGE_1>
- Erase all green paint afterward
- Lock style to <IMAGE_0>

Review the failed enhancement attempts."""
                mode_label = "Phase 2 Enhancement"
            else:
                # Phase 1: IMAGE_0=character, IMAGE_1+=additional characters
                reference_image = self.reference_image_path
                additional_images = self.additional_images_paths if self.additional_images_paths else None
                scene_description = self.current_scene
                mode_label = "Phase 1"
            
            # Store context for this review session
            self.phase1_review_context = {
                "failed_images": images_to_review,
                "original_prompt": self.current_prompt,
                "scene_description": scene_description,
                "reference_image": reference_image,
                "additional_images": additional_images,
                "review_mode": self.review_mode
            }
            
            # Build user's initial message
            image_ref_guide = "- <IMAGE_0> = Character reference (for style/appearance lock)"
            if self.review_mode == 'phase2':
                image_ref_guide += "\n- <IMAGE_1> = Green-zoned base (spatial guide for enhancements)"
            elif additional_images:
                image_ref_guide += f"\n- <IMAGE_1>+ = Additional characters ({len(additional_images)} provided)"
            image_ref_guide += "\n- Failed images = Analyzed by AI (refer to as 'failed image 1', 'failed image 2', etc.)"
            
            user_initial_msg = f"""[{mode_label} Review]

Here are the failed images to review:

{user_comment if user_comment.strip() else 'Please review these images and suggest corrections.'}

Image Reference Guide:
{image_ref_guide}

IMPORTANT: Always start your response with a brief 1-3 sentence explanation of what changes you're making to the prompt (what you're strengthening, what bans you're adding, etc.), then provide the corrected prompt in a code block."""
            
            # Get initial review
            initial_review = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=scene_description,
                reference_image=reference_image,
                skill_content=self.review_skill,
                additional_images=additional_images
            )
            
            # Build user's initial message with file list
            image_list = "\n".join([f"  • {Path(img).name}" for img in images_to_review])
            user_initial_msg_with_files = f"""{user_initial_msg}

Failed image files being reviewed:
{image_list}"""
            
            # Build display message for chat history (just the user's actual comment)
            user_display_msg_text = user_comment.strip() if user_comment.strip() else "Please review these images and suggest corrections."
            
            # Collect all images being sent to API for thumbnail display
            thumbnail_images = []
            if reference_image:
                thumbnail_images.append(reference_image)
            if additional_images:
                thumbnail_images.extend(additional_images)
            thumbnail_images.extend(images_to_review)
            
            # Initialize chat history with multimodal format (text + image thumbnails)
            # Show only the user's actual message in the UI, not the full system prompt
            user_display_msg = {
                "text": user_display_msg_text,
                "files": thumbnail_images
            }
            
            self.phase1_review_history = [
                (user_display_msg, initial_review)
            ]
            
            # Build instructions based on mode
            mode_specific_info = ""
            if self.review_mode == 'phase2':
                mode_specific_info = "\n🗂 <IMAGE_1> = Green-zoned base"
            elif additional_images:
                mode_specific_info = f"\n🗂 <IMAGE_1>+ = {len(additional_images)} additional character(s)"
            
            instructions = f"""✅ {mode_label} Review started!
            
🎯 Mode: {mode_label}
📸 {len(images_to_review)} failed image(s) being analyzed
🗂 <IMAGE_0> = Character reference (always){mode_specific_info}
💬 Refer to failed images as 'failed image 1', 'failed image 2', etc.
❓ Ask questions or request changes"""
            
            return self.phase1_review_history, instructions, images_to_review
            
        except Exception as e:
            return [], f"❌ Error during review: {str(e)}", []
    
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
            
            # Add conversation history EXCEPT the first exchange (already included above with images)
            for idx, (user_msg, assistant_msg) in enumerate(history):
                if idx == 0:
                    # First exchange already added above with images, but include the assistant's response
                    if assistant_msg:
                        messages.append({"role": "assistant", "content": assistant_msg})
                else:
                    # Subsequent messages: add both user and assistant
                    if user_msg:
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
    
    def extract_prompt_from_phase1_chat(self) -> Tuple[str, str, Any]:
        """Extract the final prompt from the Phase 1 review chat and send to generation tab."""
        if not self.phase1_review_history:
            return "", "❌ No review conversation found. Start a review first.", gr.update()
        
        # Get the last assistant message
        for user_msg, assistant_msg in reversed(self.phase1_review_history):
            if assistant_msg:
                # Use the same cleaning logic as the client
                from pasokon.grok_client import GrokClient
                cleaned_prompt = GrokClient._clean_prompt_text(assistant_msg)
                if cleaned_prompt:
                    return cleaned_prompt, "✅ Final prompt extracted and sent to Generation tab. Switched to Generate Images tab.", gr.update(selected=2)
        
        return "", "❌ No valid prompt found in conversation history.", gr.update()
    
    def set_phase1_mode(self) -> Tuple[str, str]:
        """Reset to Phase 1 review mode."""
        self.review_mode = "phase1"
        return "✅ Switched to Phase 1 mode - reviews will use character + additional characters", self._get_project_display_string()
    
    def set_phase2_mode_and_generate_prompt(
        self,
        greenzone_image,
        enhancement_description: str
    ) -> Tuple[str, str, str]:
        """Set Phase 2 context and generate enhancement prompt.
        
        This sets up the context for Phase 2 review (which uses Tab 3).
        After generating images in Tab 2, come back to Tab 3 to review them.
        """
        if not self.client:
            return "❌ Please configure your API key first.", "", self._get_project_display_string()
        
        if not greenzone_image:
            return "❌ Please upload the green-zoned base image.", "", self._get_project_display_string()
        
        if not self.reference_image_path:
            return "❌ No character reference found. Please upload a character reference in Tab 1 first.", "", self._get_project_display_string()
        
        if not enhancement_description.strip():
            return "❌ Please provide enhancement description.", "", self._get_project_display_string()
        
        try:
            # Save greenzone image and set Phase 2 mode
            self.greenzone_image_path = self.save_uploaded_file(greenzone_image)
            self.current_phase2_description = enhancement_description
            self.review_mode = "phase2"
            
            # Build Phase 2 scene description
            phase2_scene = f"""Phase 2 Enhancement - Green Zone Addition:
{enhancement_description}

Context:
- <IMAGE_0> is the character reference for style/appearance matching (SAME as Phase 1)
- <IMAGE_1> is the base image with green/pink zones marking where to add elements
- Only add elements inside the marked zones on <IMAGE_1>
- Completely erase all green/pink paint afterward
- Lock appearance/style to <IMAGE_0>
- Use <IMAGE_1> as the spatial base to modify"""
            
            # Generate enhancement prompt
            self.current_scene = phase2_scene
            self.current_prompt = self.client.generate_prompt(
                reference_image=self.reference_image_path,  # <IMAGE_0> = character
                scene_description=phase2_scene,
                skill_content=self.prompt_skill,
                additional_images=[self.greenzone_image_path]  # <IMAGE_1> = greenzone
            )
            
            status = """✅ Phase 2 enhancement prompt generated!

📋 Next steps:
1. Copy this prompt to Tab 2 (Generation)
2. Generate enhanced images in Tab 2
3. Review results in Tab 3 (it will automatically use Phase 2 mode)

🎯 Phase 2 mode active - Tab 3 will use:
   • <IMAGE_0> = Character reference (style lock)
   • <IMAGE_1> = Green-zoned base (spatial guide)"""
            
            # Auto-save project state
            self.save_project_state()
            
            return status, self.current_prompt, self._get_project_display_string()
            
        except Exception as e:
            return f"❌ Error: {str(e)}", "", self._get_project_display_string()
    
    
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
                with gr.Tab("💾 Project Management"):
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
                with gr.Tab("2️⃣ Generate Prompt"):
                    gr.Markdown("### Upload reference image and describe your scene")
                    
                    with gr.Row():
                        with gr.Column():
                            reference_image = gr.Image(
                                label="Character Reference Image (<IMAGE_0>)",
                                type="filepath"
                            )
                            additional_images = gr.File(
                                label="Additional Character References (optional, <IMAGE_1>, <IMAGE_2>...)",
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
                
                # Tab 3: Image Generation
                with gr.Tab("3️⃣ Generate Images"):
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
                        output_gallery = gr.Gallery(
                            label="Generated Images",
                            columns=3,
                            height="auto"
                        )
                    
                # Tab 4: Review and Correction
                with gr.Tab("4️⃣ Review & Correct"):
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
                        height=600
                    )
                    
                    gr.Markdown("💡 **Tip:** First message starts the review. In your messages, you can refer to specific failed images as 'failed image 1', 'failed image 2', etc.")
                    
                    with gr.Row():
                        review_user_input = gr.Textbox(
                            label="Your message",
                            placeholder="Start review by describing issues or just say 'review these images'. Then continue conversation to refine corrections.",
                            lines=1,
                            max_lines=5,
                            scale=10,
                            show_label=False,
                            container=False
                        )
                        send_review_btn = gr.Button("Send", variant="secondary", scale=0, size="sm", min_width=80)
                    
                    # Gallery for failed image thumbnails
                    failed_images_gallery = gr.Gallery(
                        label="Failed Images Being Reviewed",
                        columns=4,
                        height=300,
                        object_fit="contain",
                        show_label=True
                    )
                    
                    gr.Markdown("---")
                    gr.Markdown("**When you're satisfied with the conversation:**")
                    
                    extract_and_send_btn = gr.Button("📤 Extract Final Prompt & Send to Generation Tab", variant="primary")
                    
                    # Event handlers defined after unified_status is created (see bottom of UI)
                
                # Tab 5: Phase 2 - Manual Enhancement
                with gr.Tab("5️⃣ Phase 2: Enhancements"):
                    with gr.Row():
                        with gr.Column():
                            green_base_image = gr.Image(
                                label="Green-Marked Base Image (<IMAGE_1>)",
                                type="filepath"
                            )
                        
                        with gr.Column():
                            enhancement_description = gr.Textbox(
                                label="Enhancement Description",
                                placeholder="Describe what to add in the green zones (e.g., 'soft long dark curly peripheral fringe hair')",
                                lines=8
                            )
                    
                    enhance_prompt_btn = gr.Button("🎯 Generate Enhancement Prompt & Set Phase 2 Mode", variant="primary")
                    enhancement_prompt = gr.Textbox(
                        label="Enhancement Prompt (ready to use in Tab 2)",
                        lines=15,
                        interactive=True
                    )
                    
                    copy_phase2_to_gen_btn = gr.Button("📋 Copy to Generation Tab (Tab 2)")
                    reset_to_phase1_btn = gr.Button("🔄 Reset to Phase 1 Mode (for regular reviews)")
                    
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
                            "grok-imagine-image-quality",
                            "grok-imagine-image-pro", 
                            "grok-imagine-image-2.0",
                            "grok-imagine-image"
                        ],
                        value="grok-imagine-image-quality",
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
            # Tab 1: Project Management
            set_project_btn.click(
                fn=self.set_project_name,
                inputs=[project_name_input_dup],
                outputs=[project_mgmt_status, current_project_display, prompt_to_use, failed_images_gallery, reference_image, scene_description, additional_images, review_chatbot, green_base_image, enhancement_description, output_gallery]
            )
            
            project_name_input_dup.submit(
                fn=self.set_project_name,
                inputs=[project_name_input_dup],
                outputs=[project_mgmt_status, current_project_display, prompt_to_use, failed_images_gallery, reference_image, scene_description, additional_images, review_chatbot, green_base_image, enhancement_description, output_gallery]
            )
            
            load_project_btn.click(
                fn=self.load_project_state,
                inputs=[project_selector],
                outputs=[project_mgmt_status, current_project_display, prompt_to_use, failed_images_gallery, reference_image, scene_description, additional_images, review_chatbot, green_base_image, enhancement_description, output_gallery]
            )
            
            manual_save_btn.click(
                fn=self.save_project_state,
                outputs=[project_mgmt_status]
            )
            
            project_selector.focus(
                fn=lambda: gr.Dropdown(choices=self.list_projects()),
                outputs=[project_selector]
            )
            
            # Tab 2: Generate Prompt
            generate_prompt_btn.click(
                fn=self.generate_initial_prompt,
                inputs=[reference_image, scene_description, additional_images],
                outputs=[unified_status, prompt_to_use, main_tabs]
            )
            
            # Tab 3: Generate Images
            generate_images_btn.click(
                fn=self.generate_images_batch,
                inputs=[prompt_to_use, num_images_slider, aspect_ratio_dropdown],
                outputs=[unified_status, output_gallery, failed_images_gallery]
            )
            
            # Tab 4: Review & Correct
            def send_message(msg, history, uploaded_files, current_gallery):
                if not msg.strip():
                    return history, "", "", current_gallery
                
                # Check if review has been started (history is empty)
                if not history:
                    # Start the review with the message as initial comment
                    review_result = self.start_phase1_review(msg, uploaded_files)
                    return review_result[0], "", review_result[1], review_result[2]
                else:
                    # Continue existing review (preserve the gallery)
                    cont_result = self.continue_phase1_review(msg, history)
                    return cont_result[0], "", "", current_gallery
            
            send_review_btn.click(
                fn=send_message,
                inputs=[review_user_input, review_chatbot, failed_images_upload, failed_images_gallery],
                outputs=[review_chatbot, review_user_input, unified_status, failed_images_gallery]
            )
            
            review_user_input.submit(
                fn=send_message,
                inputs=[review_user_input, review_chatbot, failed_images_upload, failed_images_gallery],
                outputs=[review_chatbot, review_user_input, unified_status, failed_images_gallery]
            )
            
            extract_and_send_btn.click(
                fn=self.extract_prompt_from_phase1_chat,
                outputs=[prompt_to_use, unified_status, main_tabs]
            )
            
            # Tab 5: Phase 2 Enhancements
            enhance_prompt_btn.click(
                fn=self.set_phase2_mode_and_generate_prompt,
                inputs=[green_base_image, enhancement_description],
                outputs=[unified_status, enhancement_prompt, current_project_display]
            )
            
            copy_phase2_to_gen_btn.click(
                fn=lambda x: x,
                inputs=[enhancement_prompt],
                outputs=[prompt_to_use]
            )
            
            reset_to_phase1_btn.click(
                fn=self.set_phase1_mode,
                outputs=[unified_status, current_project_display]
            )
            
            # Model selection updates
            chat_model_dropdown.change(
                fn=self.update_chat_model,
                inputs=[chat_model_dropdown],
                outputs=[unified_status]
            )
            
            image_model_dropdown.change(
                fn=self.update_image_model,
                inputs=[image_model_dropdown],
                outputs=[unified_status]
            )
            
            # Auto-load last project on page load
            app.load(
                fn=lambda: self.load_project_state(),
                outputs=[project_mgmt_status, current_project_display, prompt_to_use, failed_images_gallery, reference_image, scene_description, additional_images, review_chatbot, green_base_image, enhancement_description, output_gallery]
            )
            
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
