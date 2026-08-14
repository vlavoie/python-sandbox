"""Project state management and persistence for FPV POV app."""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image


class ProjectState:
    """Holds all workflow state and handles persistence to disk."""

    def __init__(self):
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

        # Model preferences (persisted per project)
        self.chat_model = "grok-4.20"
        self.image_model = "grok-imagine-image-2.0"
        self.draft_image_model = "grok-imagine-image"
        self.draft_aspect_ratio = "1:1"

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

    def _get_project_display_string(self) -> str:
        """Generate the current project display string for the top bar."""
        return f"**📁 Current Project:** `{self.project_name}` | 💾 Auto-saves after each action"

    def save_uploaded_file(self, file) -> Optional[str]:
        """Save an uploaded file to a temporary location."""
        if file is None:
            return None

        try:
            # Get the source path
            if isinstance(file, str):
                source_path = file
            else:
                source_path = file.name

            # Get file extension
            suffix = Path(source_path).suffix.lower() if Path(source_path).suffix else '.jpg'

            # Create a temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_path = temp_file.name
            temp_file.close()

            if suffix == '.png':
                # Copy PNG directly — re-encoding through PIL can corrupt transparency
                shutil.copy(source_path, temp_path)
            elif suffix in ['.jpg', '.jpeg']:
                img = Image.open(source_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(temp_path, 'JPEG', quality=95, optimize=True)
            else:
                shutil.copy(source_path, temp_path)

            return temp_path
        except Exception as e:
            print(f"Warning: Could not save uploaded file: {e}")
            # Fallback to simple copy
            suffix = Path(file.name if hasattr(file, 'name') else file).suffix or '.jpg'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            source = file if isinstance(file, str) else file.name
            shutil.copy(source, temp_file.name)
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

            # Get file extension and determine format
            suffix = Path(image_path).suffix.lower()
            if not suffix:
                suffix = '.jpg'

            # Create destination path
            dest_path = references_dir / f"{image_type}{suffix}"

            if suffix == '.png':
                # Copy PNG directly — re-encoding through PIL can corrupt transparency
                shutil.copy(image_path, dest_path)
            elif suffix in ['.jpg', '.jpeg']:
                img = Image.open(image_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(dest_path, 'JPEG', quality=95, optimize=True)
            else:
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
                "chat_model": self.chat_model,
                "image_model": self.image_model,
                "draft_image_model": self.draft_image_model,
                "draft_aspect_ratio": self.draft_aspect_ratio,
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

    def load_project_state(self, project_name: str = None) -> Tuple[str, str, str, List, Optional[str], str, List, List, Optional[str], List]:
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
                    return "ℹ️ No saved project found", self._get_project_display_string(), "", [], None, "", [], [], None, [], self.chat_model, self.image_model, self.draft_image_model, self.draft_aspect_ratio

            metadata_path = self._get_project_metadata_path(project_name)

            if not metadata_path.exists():
                return f"ℹ️ No saved state found for project '{project_name}'", self._get_project_display_string(), "", [], None, "", [], [], None, [], self.chat_model, self.image_model, self.draft_image_model, self.draft_aspect_ratio

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
            self.chat_model = state.get("chat_model", "grok-4.20")
            self.image_model = state.get("image_model", "grok-imagine-image-2.0")
            self.draft_image_model = state.get("draft_image_model", "grok-imagine-image")
            self.draft_aspect_ratio = state.get("draft_aspect_ratio", "1:1")

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

            greenzone_image_to_load = self.greenzone_image_path if (self.greenzone_image_path and Path(self.greenzone_image_path).exists()) else None
            # For Phase 2 projects, show the user's original enhancement description, not the constructed scene text
            scene_to_show = self.current_phase2_description if self.review_mode == "phase2" else self.current_scene

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
🌿 Phase 2 greenzone: {'✅ Configured' if greenzone_image_to_load else 'Not set'}""", self._get_project_display_string(), self.current_prompt, images_to_display, ref_image_to_load, scene_to_show, additional_images_to_load, self.phase1_review_history, greenzone_image_to_load, images_to_display, self.chat_model, self.image_model, self.draft_image_model, self.draft_aspect_ratio

        except Exception as e:
            return f"❌ Error loading project: {str(e)}", self._get_project_display_string(), "", [], None, "", [], [], None, [], "grok-4.20", "grok-imagine-image-2.0", "grok-imagine-image", "1:1"

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

    def set_project_name(self, project_name: str) -> Tuple[str, str, str, List, Optional[str], str, List, List, Optional[str], List]:
        """Set the project name and reset iteration count."""
        if not project_name or not project_name.strip():
            return "❌ Project name cannot be empty", self._get_project_display_string(), "", [], None, "", [], [], None, [], self.chat_model, self.image_model, self.draft_image_model, self.draft_aspect_ratio

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
                [] if is_new_project else self.generated_images,
                self.chat_model,
                self.image_model,
                self.draft_image_model,
                self.draft_aspect_ratio,
            )
        return f"📁 Project: {sanitized}", self._get_project_display_string(), self.current_prompt, self.generated_images, self.reference_image_path, self.current_scene, self.additional_images_paths, self.phase1_review_history, self.greenzone_image_path, self.generated_images, self.chat_model, self.image_model, self.draft_image_model, self.draft_aspect_ratio
