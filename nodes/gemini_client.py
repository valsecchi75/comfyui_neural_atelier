"""
Gemini API Client for Neural Atelier NA01 Node
Handles both Gemini Flash (text orchestration) and Nano Banana Pro (image generation)
"""

import os
import base64
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from google import genai
from google.genai import types


GEMINI_FLASH_MODEL = "gemini-3-flash-preview"
NANO_BANANA_MODEL = "gemini-3-pro-image-preview"

IMAGE_MODELS = [
    "Nano Banana Pro (gemini-3-pro-image-preview)",
    "Nano Banana 2 (gemini-3.1-flash-image-preview)",
]

IMAGE_MODEL_IDS = {
    "Nano Banana Pro (gemini-3-pro-image-preview)": "gemini-3-pro-image-preview",
    "Nano Banana 2 (gemini-3.1-flash-image-preview)": "gemini-3.1-flash-image-preview",
}

ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
RESOLUTIONS = ["1K", "2K", "4K"]


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.client = None
        self._status = "Not Configured"
        
        if self.api_key:
            self._init_client()
    
    def _init_client(self):
        try:
            self.client = genai.Client(api_key=self.api_key)
            self._status = "Configured"
        except Exception as e:
            self._status = f"Error: {str(e)}"
            self.client = None
    
    def set_api_key(self, api_key: str):
        self.api_key = api_key
        self._init_client()
    
    @property
    def status(self) -> str:
        return self._status
    
    def verify_api_key(self) -> Tuple[bool, str]:
        if not self.api_key:
            self._status = "No API Key"
            return False, "No API key provided"
        
        if not self.client:
            self._init_client()
            if not self.client:
                return False, self._status
        
        try:
            models = self.client.models.list()
            model_list = list(models)
            if len(model_list) > 0:
                self._status = "Valid"
                return True, "API key verified successfully"
            else:
                self._status = "Invalid Response"
                return False, "API key verification failed: no models available"
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "invalid" in error_msg.lower() or "UNAUTHENTICATED" in error_msg:
                self._status = "Invalid Key"
            elif "429" in error_msg or "quota" in error_msg.lower() or "RESOURCE_EXHAUSTED" in error_msg:
                self._status = "Quota Exceeded"
            elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                self._status = "Permission Denied"
            else:
                self._status = "Error"
            return False, f"API key verification failed: {error_msg}"
    
    def _encode_image_to_base64(self, image_bytes: bytes) -> str:
        return base64.standard_b64encode(image_bytes).decode("utf-8")
    
    def _create_image_part(self, image_bytes: bytes, mime_type: str = "image/png") -> types.Part:
        return types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )
    
    def call_gemini_flash(
        self,
        system_instruction: str,
        brief_text: str,
        images: Dict[str, bytes],
        max_retries: int = 1
    ) -> Tuple[Optional[Dict[str, Any]], str, float, Dict[str, Any]]:
        if not self.client:
            return None, "Client not initialized", 0.0, {}
        
        manifest_items = []
        for name, img_bytes in images.items():
            if img_bytes:
                manifest_items.append(f"- {name}: provided")
            else:
                manifest_items.append(f"- {name}: not provided")
        
        manifest_text = "Asset Manifest:\n" + "\n".join(manifest_items)
        
        user_content = f"""
{manifest_text}

User Brief:
{brief_text if brief_text else "No brief provided."}

Based on the provided assets and brief, generate the nano_banana_prompt following your system instructions.
You MUST respond with ONLY a valid JSON object in this exact format:
{{"nano_banana_prompt": "your generated prompt here"}}

Do not include any other text, explanation, or markdown formatting.
"""
        
        contents = []
        images_info = []
        
        for name, img_bytes in images.items():
            if img_bytes:
                contents.append(self._create_image_part(img_bytes))
                images_info.append({"name": name, "size_bytes": len(img_bytes), "mime_type": "image/png"})
        
        contents.append(user_content)
        
        request_payload = {
            "model": GEMINI_FLASH_MODEL,
            "system_instruction": system_instruction[:500] + "..." if len(system_instruction) > 500 else system_instruction,
            "user_content": user_content,
            "images": images_info,
            "config": {
                "temperature": 0.7,
                "max_output_tokens": 2048
            }
        }
        
        start_time = time.time()
        last_error = ""
        
        for attempt in range(max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_FLASH_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=2048
                    )
                )
                
                latency = time.time() - start_time
                
                if not response or not response.text:
                    last_error = "Empty response from Gemini Flash"
                    continue
                
                response_text = response.text.strip()
                
                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    response_text = "\n".join(lines)
                
                try:
                    parsed = json.loads(response_text)
                except json.JSONDecodeError as e:
                    last_error = f"Invalid JSON response: {e}"
                    continue
                
                if "nano_banana_prompt" not in parsed:
                    last_error = "Response missing 'nano_banana_prompt' key"
                    continue
                
                allowed_keys = {"nano_banana_prompt"}
                extra_keys = set(parsed.keys()) - allowed_keys
                if extra_keys:
                    last_error = f"Response contains extra keys: {extra_keys}"
                    continue
                
                return parsed, response_text, latency, request_payload
                
            except Exception as e:
                last_error = str(e)
                latency = time.time() - start_time
        
        return None, last_error, time.time() - start_time, request_payload
    
    def generate_image(
        self,
        prompt: str,
        reference_images: Optional[List[bytes]] = None,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        top_p: float = 0.95,
        image_model: str = NANO_BANANA_MODEL
    ) -> Tuple[Optional[bytes], str, float, Dict[str, Any]]:
        if not self.client:
            return None, "Client not initialized", 0.0, {}
        
        model_id = IMAGE_MODEL_IDS.get(image_model, image_model)
        
        if aspect_ratio not in ASPECT_RATIOS:
            aspect_ratio = "1:1"
        
        if resolution not in RESOLUTIONS:
            resolution = "1K"
        
        ref_images_info = []
        if reference_images:
            for i, img_bytes in enumerate(reference_images):
                if img_bytes:
                    ref_images_info.append({"index": i, "size_bytes": len(img_bytes), "mime_type": "image/png"})
        
        request_payload = {
            "model": model_id,
            "prompt": prompt,
            "reference_images_count": len(ref_images_info),
            "reference_images": ref_images_info,
            "config": {
                "response_modalities": ["IMAGE", "TEXT"],
                "top_p": top_p,
                "image_config": {
                    "aspect_ratio": aspect_ratio,
                    "image_size": resolution
                }
            }
        }
        
        start_time = time.time()
        
        try:
            contents = []
            
            if reference_images:
                for img_bytes in reference_images:
                    if img_bytes:
                        contents.append(self._create_image_part(img_bytes))
            
            contents.append(prompt)
            
            response = self.client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    top_p=top_p,
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=resolution
                    )
                )
            )
            
            latency = time.time() - start_time
            
            if not response or not response.candidates:
                return None, "No response from Nano Banana Pro", latency, request_payload
            
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                return None, "No content parts in response", latency, request_payload
            
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
                    image_data = part.inline_data.data
                    return image_data, "Success", latency, request_payload
            
            return None, "No image in response", latency, request_payload
            
        except Exception as e:
            error_msg = str(e)
            latency = time.time() - start_time
            
            if "safety" in error_msg.lower():
                return None, f"Safety filter triggered: {error_msg}", latency, request_payload
            elif "quota" in error_msg.lower():
                return None, f"Quota exceeded: {error_msg}", latency, request_payload
            else:
                return None, f"Generation error: {error_msg}", latency, request_payload
