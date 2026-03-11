"""
Neural Atelier NA01 Node - Sketch to Photo Prompt Orchestrator
Main ComfyUI node implementation
"""

import json
import torch
from typing import Tuple, Optional, Dict, Any

from .gemini_client import GeminiClient, GEMINI_FLASH_MODEL, NANO_BANANA_MODEL, IMAGE_MODELS, IMAGE_MODEL_IDS, ASPECT_RATIOS, RESOLUTIONS
from .config_loader import get_prompt_packs, get_prompt_profiles, load_master_prompt
from .image_utils import tensor_to_bytes, bytes_to_tensor, collect_provided_images, get_image_dimensions
from .logger import RunLogger


SKETCH_TO_PHOTO_PACK = "NA_Sketch_to_Photo_Orchestrator"

_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def get_sketch_profiles() -> list:
    profiles = get_prompt_profiles(SKETCH_TO_PHOTO_PACK)
    if profiles and profiles != ["No profiles found"]:
        return profiles
    return ["01_Sketch_to_Photo", "02_Ghost_Mannequin", "03_Hanger", 
            "04_Photorealistic_Exploded", "05_Isometric_Schematic", "06_Grid_2x2"]


class NA01SketchToPhotoNode:
    
    CATEGORY = "Neural Atelier"
    FUNCTION = "execute"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("image", "log", "flash_request_json", "nanobana_request_json")
    
    @classmethod
    def INPUT_TYPES(cls):
        profiles = get_sketch_profiles()
        
        return {
            "required": {
                "prompt_profile": (profiles, {"default": profiles[0] if profiles else "01_Sketch_to_Photo"}),
                "brief_text": ("STRING", {"multiline": True, "default": ""}),
                "gemini_api_key": ("STRING", {"default": "", "multiline": False}),
                "api_key_status": ("STRING", {"multiline": False, "default": "Not Verified", "display": "text"}),
                "image_model": (IMAGE_MODELS, {"default": IMAGE_MODELS[0]}),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "1:1"}),
                "resolution": (RESOLUTIONS, {"default": "1K"}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.05}),
                "rerun_nonce": ("INT", {"default": 0, "min": 0, "max": 999999}),
            },
            "optional": {
                "talent_image": ("IMAGE",),
                "flat_sketch_image": ("IMAGE",),
                "material_image": ("IMAGE",),
                "pattern_image": ("IMAGE",),
                "template_master_1": ("IMAGE",),
                "template_master_2": ("IMAGE",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }
    
    @classmethod
    def IS_CHANGED(cls, rerun_nonce, **kwargs):
        return rerun_nonce
    
    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True
    
    def execute(
        self,
        prompt_profile: str,
        brief_text: str,
        gemini_api_key: str,
        api_key_status: str,
        image_model: str,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        rerun_nonce: int = 0,
        talent_image: Optional[torch.Tensor] = None,
        flat_sketch_image: Optional[torch.Tensor] = None,
        material_image: Optional[torch.Tensor] = None,
        pattern_image: Optional[torch.Tensor] = None,
        template_master_1: Optional[torch.Tensor] = None,
        template_master_2: Optional[torch.Tensor] = None,
        unique_id: str = ""
    ) -> Tuple[torch.Tensor, str, str, str]:
        
        logger = RunLogger()
        logger.log(f"Starting NA01 execution (nonce: {rerun_nonce})")
        
        client = get_gemini_client()
        if gemini_api_key:
            client.set_api_key(gemini_api_key)
        
        if not client.api_key:
            error_msg = "No API key configured. Please provide a Gemini API key."
            logger.add_error(error_msg)
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, logger.get_summary(), "{}", "{}")
        
        prompt_pack = SKETCH_TO_PHOTO_PACK
        
        logger.set_prompt_info(prompt_pack, prompt_profile, brief_text)
        
        master_prompt, load_error = load_master_prompt(prompt_pack, prompt_profile)
        if load_error:
            logger.add_error(f"Failed to load master prompt: {load_error}")
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, logger.get_summary(), "{}", "{}")
        
        logger.log("Master prompt loaded successfully")
        
        images, image_logs = collect_provided_images(
            talent=talent_image,
            flat_sketch=flat_sketch_image,
            material=material_image,
            pattern=pattern_image,
            template_1=template_master_1,
            template_2=template_master_2
        )
        
        image_info = {}
        for name, img_bytes in images.items():
            if img_bytes:
                image_info[name] = {"provided": True, "size_bytes": len(img_bytes)}
            else:
                image_info[name] = {"provided": False}
        
        logger.set_image_info(image_info)
        
        manifest = {
            "prompt_pack": prompt_pack,
            "prompt_profile": prompt_profile,
            "brief_text": brief_text,
            "images": image_info,
            "settings": {
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "top_p": top_p
            }
        }
        logger.save_request_manifest(manifest)
        
        logger.log("Calling Gemini Flash for prompt orchestration...")
        
        flash_result, flash_response, flash_latency, flash_request_payload = client.call_gemini_flash(
            system_instruction=master_prompt or "",
            brief_text=brief_text,
            images=images,
            max_retries=1
        )
        
        flash_request_json = json.dumps(flash_request_payload, indent=2, ensure_ascii=False)
        
        if flash_result is None:
            logger.set_gemini_flash_result(
                model_id=GEMINI_FLASH_MODEL,
                latency=flash_latency,
                success=False,
                error=flash_response
            )
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, logger.get_summary(), flash_request_json, "{}")
        
        logger.set_gemini_flash_result(
            model_id=GEMINI_FLASH_MODEL,
            latency=flash_latency,
            success=True
        )
        
        logger.save_gemini_flash_response(flash_response)
        
        nano_banana_prompt = flash_result.get("nano_banana_prompt", "")
        logger.save_nano_banana_prompt(nano_banana_prompt)
        
        selected_model_id = IMAGE_MODEL_IDS.get(image_model, NANO_BANANA_MODEL)
        logger.log(f"Calling {image_model} for image generation...")
        
        reference_images = [img for img in images.values() if img is not None]
        
        image_bytes, gen_status, gen_latency, nanobana_request_payload = client.generate_image(
            prompt=nano_banana_prompt,
            reference_images=reference_images if reference_images else None,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            top_p=top_p,
            image_model=image_model
        )
        
        nanobana_request_json = json.dumps(nanobana_request_payload, indent=2, ensure_ascii=False)
        
        if image_bytes is None:
            logger.set_nano_banana_result(
                model_id=selected_model_id,
                latency=gen_latency,
                success=False,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                top_p=top_p,
                error=gen_status
            )
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, logger.get_summary(), flash_request_json, nanobana_request_json)
        
        logger.set_nano_banana_result(
            model_id=selected_model_id,
            latency=gen_latency,
            success=True,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            top_p=top_p
        )
        
        try:
            output_tensor = bytes_to_tensor(image_bytes)
            logger.log(f"Output image: {get_image_dimensions(output_tensor)}")
        except Exception as e:
            logger.add_error(f"Failed to convert output image: {str(e)}")
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, logger.get_summary(), flash_request_json, nanobana_request_json)
        
        logger.finalize()
        
        return (output_tensor, logger.get_summary(), flash_request_json, nanobana_request_json)


class NA01VerifyAPIKeyNode:
    
    CATEGORY = "Neural Atelier"
    FUNCTION = "verify"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "gemini_api_key": ("STRING", {"default": "", "multiline": False}),
            }
        }
    
    def verify(self, gemini_api_key: str) -> Tuple[str]:
        client = get_gemini_client()
        
        if gemini_api_key:
            client.set_api_key(gemini_api_key)
        
        if not client.api_key:
            return ("No API Key Configured",)
        
        success, message = client.verify_api_key()
        
        return (f"{client.status}: {message}",)


class NA01GetProfilesNode:
    
    CATEGORY = "Neural Atelier"
    FUNCTION = "get_profiles"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("profiles",)
    
    @classmethod
    def INPUT_TYPES(cls):
        prompt_packs = get_prompt_packs()
        return {
            "required": {
                "prompt_pack": (prompt_packs, {"default": prompt_packs[0] if prompt_packs else ""}),
            }
        }
    
    def get_profiles(self, prompt_pack: str) -> Tuple[str]:
        profiles = get_prompt_profiles(prompt_pack)
        return (",".join(profiles),)


NODE_CLASS_MAPPINGS = {
    "NA01_SketchToPhoto": NA01SketchToPhotoNode,
    "NA01_VerifyAPIKey": NA01VerifyAPIKeyNode,
    "NA01_GetProfiles": NA01GetProfilesNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NA01_SketchToPhoto": "NA - Sketch to Photo Orchestrator",
    "NA01_VerifyAPIKey": "NA - Verify API Key",
    "NA01_GetProfiles": "NA - Get Profiles",
}
