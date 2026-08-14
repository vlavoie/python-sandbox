"""Grok API client for FPV POV image generation workflow."""

import os
import base64
import io
from typing import Optional, List, Dict, Any
from pathlib import Path
import httpx
from dataclasses import dataclass
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import time

# Load environment variables from .env file
load_dotenv()


@dataclass
class GeneratedImage:
    """Container for a generated image and its metadata."""
    image_data: bytes
    prompt: str
    iteration: int
    phase: str


class GrokClient:
    """Client for interacting with Grok and Grok Imagine APIs."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the Grok client.
        
        Args:
            api_key: Grok API key. If not provided, reads from XAI_API_KEY env var.
            base_url: API base URL. Defaults to https://api.x.ai/v1
        """
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("Grok API key must be provided or set in XAI_API_KEY environment variable")
        
        self.base_url = base_url or os.getenv("XAI_API_BASE_URL", "https://api.x.ai/v1")
        
        # Model names - can be overridden via environment variables
        # Current Grok 4.20 models support vision (images)
        # Run 'poetry run python list_models.py' to see all available models
        self.chat_model = os.getenv("XAI_CHAT_MODEL", "grok-4.20")
        # Image generation models: grok-imagine-image-quality (best), grok-imagine-image-pro, grok-imagine-image-2.0, grok-imagine-image
        self.image_model = os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image-2.0")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def list_models(self) -> dict:
        """List available models from the API.
        
        Returns:
            Dictionary containing available models.
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Error listing models: {e}")
            return {"error": str(e)}
        
    @staticmethod
    def _clean_prompt_text(text: str) -> str:
        """Clean markdown formatting from prompt text.
        
        Removes:
        - Markdown code fences (```markdown, ```, etc.)
        - Language identifiers after opening fences
        - Surrounding whitespace
        
        Args:
            text: Raw text that may contain markdown formatting.
            
        Returns:
            Cleaned prompt text, or original text if cleaning fails.
        """
        try:
            if not text or not text.strip():
                return text
            
            # Find content between ``` markers
            if "```" in text:
                parts = text.split("```")
                if len(parts) >= 3:
                    # Extract the code block content (odd indices)
                    prompt = parts[1].strip()
                    
                    # Remove common language identifiers from start of block
                    language_tags = ["markdown", "text", "prompt", "grok", "imagine"]
                    first_line = prompt.split("\n")[0].lower().strip()
                    if first_line in language_tags:
                        # Remove the first line
                        prompt = "\n".join(prompt.split("\n")[1:]).strip()
                    
                    return prompt
            
            # No code fences found, return as-is
            return text.strip()
            
        except Exception:
            # Fallback: return original text if cleaning fails
            return text.strip()
    
    def _encode_image(self, image_path: str) -> str:
        """Encode an image to base64 JPEG, flattening transparency onto white."""
        img = Image.open(image_path)
        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    
    def generate_prompt(
        self,
        reference_image: str,
        scene_description: str,
        skill_content: str,
        additional_images: Optional[List[str]] = None
    ) -> str:
        """Generate a Grok Imagine prompt using the fpv-pov-image skill.
        
        Args:
            reference_image: Path to the character reference image.
            scene_description: User's scene description.
            skill_content: Content of the fpv-pov-image.md skill.
            additional_images: Optional list of additional character images.
            
        Returns:
            Generated prompt for Grok Imagine.
        """
        # Prepare the messages with images
        content = [
            {"type": "text", "text": skill_content},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{self._encode_image(reference_image)}"
                }
            },
            {"type": "text", "text": f"\n\nScene description:\n{scene_description}"}
        ]
        
        # Add additional character images if provided
        if additional_images:
            for idx, img_path in enumerate(additional_images, start=2):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{self._encode_image(img_path)}"
                    }
                })
        
        with httpx.Client(timeout=60.0) as client:
            payload = {
                "model": self.chat_model,
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "temperature": 0.7,
            }
            
            # Debug logging
            print(f"DEBUG: Sending request to {self.base_url}/chat/completions")
            print(f"DEBUG: Model: {self.chat_model}")
            print(f"DEBUG: Content items: {len(content)}")
            
            try:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                print(f"\n❌ HTTP Error: {e.response.status_code}")
                print(f"❌ Response: {error_detail}")
                print(f"❌ Request URL: {e.request.url}")
                print(f"❌ Model used: {self.chat_model}")
                
                # Try to parse error JSON for more details
                try:
                    error_json = e.response.json()
                    print(f"❌ Error details: {error_json}")
                except:
                    pass
                
                raise Exception(
                    f"Grok API Error ({e.response.status_code}): {error_detail}\n\n"
                    f"Model: {self.chat_model}\n"
                    f"Check if the model name is correct and your API key has access to vision models."
                )
            
            # Extract and clean the prompt
            full_response = result["choices"][0]["message"]["content"]
            return self._clean_prompt_text(full_response)
    
    def generate_images(
        self,
        prompt: str,
        reference_image: str,
        num_images: int = 3,
        additional_images: Optional[List[str]] = None,
        aspect_ratio: str = "16:9",
        model: str = None
    ) -> List[bytes]:
        """Generate images using Grok Imagine API.
        
        Args:
            prompt: The prompt to use for generation.
            reference_image: Path to the character reference image.
            num_images: Number of images to generate (default: 3).
            additional_images: Optional list of additional reference images.
            aspect_ratio: Aspect ratio for the generated images (default: "16:9").
                         Common ratios: "1:1", "16:9", "9:16", "4:3", "3:4", "21:9"
            
        Returns:
            List of generated image data as bytes.
        """
        images = []
        
        # Prepare images array for /images/edits endpoint
        # Each image is an object with "url" key containing base64 data URI
        images_array = [{"url": f"data:image/jpeg;base64,{self._encode_image(reference_image)}"}]
        if additional_images:
            for img_path in additional_images:
                images_array.append({"url": f"data:image/jpeg;base64,{self._encode_image(img_path)}"})
        
        # Format payload for /images/edits endpoint
        # API uses <IMAGE_0>, <IMAGE_1>, <IMAGE_2> to reference images in prompt
        effective_model = model or self.image_model
        payload = {
            "model": effective_model,
            "prompt": prompt,
            "images": images_array,
            "aspect_ratio": aspect_ratio
        }

        print(f"\n🎨 Generating {num_images} images in parallel...")
        print(f"   Model: {effective_model}")
        print(f"   Aspect ratio: {aspect_ratio}")
        print(f"   Reference images being sent: {len(images_array)}")
        print(f"   Prompt length: {len(prompt)} characters")
        
        # DEBUG: Show prompt preview and check reference format
        print(f"\n📝 PROMPT PREVIEW (first 200 chars):")
        print(f"   {prompt[:200]}...")
        
        has_angle_brackets = "<IMAGE_" in prompt
        has_at_symbols = "@image" in prompt.lower()
        
        if has_at_symbols and not has_angle_brackets:
            print(f"\n   ⚠️  WARNING: Prompt uses '@image' syntax but API expects '<IMAGE_0>', '<IMAGE_1>', etc.!")
            print(f"   💡 Skill files need to be updated to use <IMAGE_0>, <IMAGE_1>, <IMAGE_2> format")
        elif has_angle_brackets:
            print(f"   ✅ Prompt uses correct <IMAGE_N> reference syntax")
        
        def generate_single_image(index: int) -> tuple[int, bytes]:
            """Generate a single image (for parallel execution)."""
            with httpx.Client(timeout=180.0) as client:
                try:
                    start_time = time.time()
                    print(f"   🚀 Starting image {index + 1}/{num_images}...")
                    
                    response = client.post(
                        f"{self.base_url}/images/edits",  # FIXED: Use edits endpoint for reference images
                        headers=self.headers,
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    api_time = time.time() - start_time
                    
                    # Grok returns image URLs, not base64
                    if "data" in result and len(result["data"]) > 0:
                        image_url = result["data"][0].get("url")
                        if image_url:
                            # Download the image
                            img_response = client.get(image_url)
                            img_response.raise_for_status()
                            image_data = img_response.content
                            
                            total_time = time.time() - start_time
                            print(f"   ✅ Image {index + 1}/{num_images} complete ({total_time:.1f}s)")
                            return (index, image_data)
                        else:
                            raise Exception("No image URL in response")
                    else:
                        raise Exception("Unexpected response format")
                
                except httpx.TimeoutException:
                    print(f"\n❌ Timeout generating image {index + 1}/{num_images}")
                    raise Exception(
                        f"Image {index + 1} generation timed out after 180 seconds.\n"
                        f"The Grok Imagine API might be slow or overloaded. Try again in a few minutes."
                    )
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text
                    print(f"\n❌ Image {index + 1} Generation Error: {e.response.status_code}")
                    print(f"❌ Response: {error_detail}")
                    try:
                        error_json = e.response.json()
                        print(f"❌ Error details: {error_json}")
                    except:
                        pass
                    raise Exception(
                        f"Grok Image API Error ({e.response.status_code}): {error_detail}\n\n"
                        f"Model: {self.image_model}"
                    )
        
        # Generate all images in parallel
        overall_start = time.time()
        images = [None] * num_images  # Pre-allocate list to maintain order
        errors = []
        
        with ThreadPoolExecutor(max_workers=num_images) as executor:
            # Submit all tasks
            future_to_index = {executor.submit(generate_single_image, i): i for i in range(num_images)}
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    idx, image_data = future.result()
                    images[idx] = image_data
                except Exception as e:
                    # Collect error but continue processing other images
                    error_msg = str(e)
                    errors.append((index + 1, error_msg))
                    print(f"   ⚠️ Image {index + 1} failed, continuing with others...")
        
        # Filter out None values (failed images)
        successful_images = [img for img in images if img is not None]
        
        overall_time = time.time() - overall_start
        
        if errors:
            failed_count = len(errors)
            success_count = len(successful_images)
            error_summary = "\n".join([f"  • Image {idx}: {msg.split(chr(10))[0]}" for idx, msg in errors])
            
            if success_count == 0:
                # All images failed
                raise Exception(
                    f"All {num_images} images failed to generate:\n{error_summary}"
                )
            else:
                # Partial success - return successful images with warning
                print(f"\n⚠️ {success_count}/{num_images} images generated successfully in {overall_time:.1f}s")
                print(f"❌ {failed_count} image(s) failed:\n{error_summary}\n")
                # Return successful images (caller will handle the partial result)
                return successful_images
        else:
            # All images succeeded
            print(f"\n✨ All {num_images} images generated in {overall_time:.1f}s (avg {overall_time/num_images:.1f}s per image)\n")
        
        return images
    
    def review_images(
        self,
        failed_images: List[str],
        original_prompt: str,
        scene_description: str,
        reference_image: str,
        skill_content: str,
        additional_images: Optional[List[str]] = None
    ) -> str:
        """Review failed images and generate a corrected prompt.
        
        Args:
            failed_images: List of paths to failed generated images.
            original_prompt: The prompt that produced the failed images.
            scene_description: Original scene description.
            reference_image: Path to the character reference image.
            skill_content: Content of the fpv-pov-review.md skill.
            additional_images: Optional list of additional reference images.
            
        Returns:
            Corrected prompt for Grok Imagine.
        """
        # Prepare the messages with all images
        # IMPORTANT: Character reference MUST be <IMAGE_0> for consistency with initial prompt generation
        content = [
            {"type": "text", "text": skill_content},
            {"type": "text", "text": "\n\nCharacter reference (<IMAGE_0>):"}
        ]
        
        # Add character reference FIRST (becomes <IMAGE_0>)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{self._encode_image(reference_image)}"
            }
        })
        
        # Add additional images if provided (become <IMAGE_1>, <IMAGE_2>, etc.)
        if additional_images:
            for idx, img_path in enumerate(additional_images, start=1):
                content.append({
                    "type": "text",
                    "text": f"\n\nAdditional reference (<IMAGE_{idx}>):"
                })
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{self._encode_image(img_path)}"
                    }
                })
        
        # Add failed images AFTER references (for visual comparison only, not referenced by index)
        content.append({"type": "text", "text": "\n\nFailed generated images (for diagnosis):"})
        for img_path in failed_images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{self._encode_image(img_path)}"
                }
            })
        
        # Add original prompt and scene
        content.append({
            "type": "text",
            "text": f"\n\nOriginal prompt that produced these images:\n```\n{original_prompt}\n```"
        })
        content.append({
            "type": "text",
            "text": f"\n\nOriginal scene description:\n{scene_description}"
        })
        
        with httpx.Client(timeout=60.0) as client:
            payload = {
                "model": self.chat_model,
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "temperature": 0.7,
            }
            
            print(f"DEBUG: Sending review request to {self.base_url}/chat/completions")
            print(f"DEBUG: Model: {self.chat_model}")
            
            try:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                print(f"\n❌ HTTP Error: {e.response.status_code}")
                print(f"❌ Response: {error_detail}")
                print(f"❌ Model used: {self.chat_model}")
                try:
                    error_json = e.response.json()
                    print(f"❌ Error details: {error_json}")
                except:
                    pass
                raise Exception(
                    f"Grok API Error ({e.response.status_code}): {error_detail}\n\n"
                    f"Model: {self.chat_model}\n"
                    f"Check if the model name is correct and your API key has access to vision models."
                )
            
            # Extract the corrected prompt - clean it for immediate use
            full_response = result["choices"][0]["message"]["content"]
            return self._clean_prompt_text(full_response)
