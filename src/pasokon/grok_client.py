"""Grok API client for FPV POV image generation workflow."""

import os
import base64
from typing import Optional, List, Dict, Any
from pathlib import Path
import httpx
from dataclasses import dataclass
from dotenv import load_dotenv

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
        self.image_model = os.getenv("XAI_IMAGE_MODEL", "grok-4.20")
        
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
        
    def _encode_image(self, image_path: str) -> str:
        """Encode an image to base64.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Base64 encoded image string.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
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
            
            # Extract the prompt from the code block
            full_response = result["choices"][0]["message"]["content"]
            # Find content between ``` markers
            if "```" in full_response:
                parts = full_response.split("```")
                if len(parts) >= 3:
                    return parts[1].strip()
            return full_response.strip()
    
    def generate_images(
        self,
        prompt: str,
        reference_image: str,
        num_images: int = 3,
        additional_images: Optional[List[str]] = None
    ) -> List[bytes]:
        """Generate images using Grok Imagine API.
        
        Args:
            prompt: The prompt to use for generation.
            reference_image: Path to the character reference image.
            num_images: Number of images to generate (default: 3).
            additional_images: Optional list of additional reference images.
            
        Returns:
            List of generated image data as bytes.
        """
        images = []
        
        # Prepare image URLs
        image_urls = [f"data:image/jpeg;base64,{self._encode_image(reference_image)}"]
        if additional_images:
            for img_path in additional_images:
                image_urls.append(f"data:image/jpeg;base64,{self._encode_image(img_path)}")
        
        with httpx.Client(timeout=120.0) as client:
            for i in range(num_images):
                payload = {
                    "model": self.image_model,
                    "prompt": prompt,
                    "images": image_urls,
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json"
                }
                
                print(f"DEBUG: Generating image {i+1}/{num_images}")
                print(f"DEBUG: Model: {self.image_model}")
                
                try:
                    response = client.post(
                        f"{self.base_url}/images/generations",
                        headers=self.headers,
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text
                    print(f"\n❌ Image Generation Error: {e.response.status_code}")
                    print(f"❌ Response: {error_detail}")
                    print(f"❌ Model used: {self.image_model}")
                    try:
                        error_json = e.response.json()
                        print(f"❌ Error details: {error_json}")
                    except:
                        pass
                    raise Exception(
                        f"Grok Image API Error ({e.response.status_code}): {error_detail}\n\n"
                        f"Model: {self.image_model}\n"
                        f"Check if the model name is correct and your API key has access to image generation."
                    )
                
                # Decode the base64 image
                image_b64 = result["data"][0]["b64_json"]
                image_data = base64.b64decode(image_b64)
                images.append(image_data)
        
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
        content = [
            {"type": "text", "text": skill_content},
            {"type": "text", "text": "\n\nFailed generated images:"}
        ]
        
        # Add failed images
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
        
        # Add character reference
        content.append({"type": "text", "text": "\n\nCharacter reference (@image1):"})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{self._encode_image(reference_image)}"
            }
        })
        
        # Add additional images if provided
        if additional_images:
            for idx, img_path in enumerate(additional_images, start=2):
                content.append({
                    "type": "text",
                    "text": f"\n\nAdditional reference (@image{idx}):"
                })
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
            
            # Extract the corrected prompt
            full_response = result["choices"][0]["message"]["content"]
            # Find content between ``` markers (skip the blurb)
            if "```" in full_response:
                parts = full_response.split("```")
                if len(parts) >= 3:
                    # Return both blurb and corrected prompt
                    blurb = parts[0].strip()
                    corrected_prompt = parts[1].strip()
                    return f"{blurb}\n\n```\n{corrected_prompt}\n```"
            return full_response.strip()
