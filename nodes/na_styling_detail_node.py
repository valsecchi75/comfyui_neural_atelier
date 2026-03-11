"""
Neural Atelier NA - Styling Detail Change Node
Enables targeted styling modifications on garments without altering texture, color, or silhouette
"""

import json
import hashlib
import os
import torch
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime

from .gemini_client import GeminiClient, GEMINI_FLASH_MODEL, NANO_BANANA_MODEL, IMAGE_MODELS, IMAGE_MODEL_IDS, ASPECT_RATIOS, RESOLUTIONS
from .image_utils import tensor_to_bytes, bytes_to_tensor, get_image_dimensions
from .logger import RunLogger
from .na_styling_cache import get_styling_cache


_gemini_client: Optional[GeminiClient] = None
_garments_config_cache: Optional[Dict[str, Any]] = None
_styling_templates_cache: Optional[Dict[str, Any]] = None


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def load_garments_config() -> Dict[str, Any]:
    global _garments_config_cache
    if _garments_config_cache is not None:
        return _garments_config_cache
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "NA_Styling_Detail_Change",
        "garments.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _garments_config_cache = json.load(f)
            return _garments_config_cache
    except (IOError, json.JSONDecodeError):
        _garments_config_cache = {"version": "0.0.0", "garment_types": []}
        return _garments_config_cache


def load_prompt_templates() -> Dict[str, Any]:
    global _styling_templates_cache
    if _styling_templates_cache is not None:
        return _styling_templates_cache
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "NA_Styling_Detail_Change",
        "prompt_templates.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _styling_templates_cache = json.load(f)
            return _styling_templates_cache
    except (IOError, json.JSONDecodeError):
        _styling_templates_cache = {"version": "0.0.0"}
        return _styling_templates_cache


def get_garment_types() -> List[str]:
    config = load_garments_config()
    return [gt["value"] for gt in config.get("garment_types", [])]


def get_categories_for_garment(garment_type: str) -> List[str]:
    config = load_garments_config()
    for gt in config.get("garment_types", []):
        if gt["value"] == garment_type:
            return [cat["value"] for cat in gt.get("categories", [])]
    return []


def get_options_for_category(garment_type: str, category: str) -> List[str]:
    config = load_garments_config()
    for gt in config.get("garment_types", []):
        if gt["value"] == garment_type:
            for cat in gt.get("categories", []):
                if cat["value"] == category:
                    return [opt["value"] for opt in cat.get("options", [])]
    return []


def get_default_template(garment_type: str, category: str) -> str:
    config = load_garments_config()
    for gt in config.get("garment_types", []):
        if gt["value"] == garment_type:
            for cat in gt.get("categories", []):
                if cat["value"] == category:
                    return cat.get("default_template", "")
    return ""


def get_config_version_hash() -> str:
    garments_config = load_garments_config()
    templates_config = load_prompt_templates()
    combined = json.dumps({
        "garments": garments_config.get("version", ""),
        "templates": templates_config.get("version", "")
    }, sort_keys=True)
    return hashlib.sha256(combined.encode()).hexdigest()[:8]


class NAStylingDetailChangeNode:
    
    CATEGORY = "Neural Atelier"
    FUNCTION = "execute"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("image", "prompt", "log", "output_json")
    
    @classmethod
    def INPUT_TYPES(cls):
        garment_types = get_garment_types()
        if not garment_types:
            garment_types = ["sweater"]
        
        default_garment = garment_types[0]
        categories = get_categories_for_garment(default_garment)
        if not categories:
            categories = ["neckline"]
        
        default_category = categories[0]
        options = get_options_for_category(default_garment, default_category)
        if not options:
            options = ["crew_neck"]
        
        return {
            "required": {
                "garment_image": ("IMAGE",),
                "garment_type": (garment_types, {"default": default_garment}),
                "detail_category": (categories, {"default": default_category}),
                "detail_option": (options, {"default": options[0]}),
                "description": ("STRING", {"multiline": True, "default": ""}),
                "brief": ("STRING", {"multiline": True, "default": ""}),
                "gemini_api_key": ("STRING", {"default": "", "multiline": False}),
                "api_key_status": ("STRING", {"multiline": False, "default": "Not Verified", "display": "text"}),
                "image_model": (IMAGE_MODELS, {"default": IMAGE_MODELS[0]}),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "1:1"}),
                "resolution": (RESOLUTIONS, {"default": "1K"}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.05}),
                "rerun_nonce": ("INT", {"default": 0, "min": 0, "max": 999999}),
            },
            "optional": {
                "detail_reference_image": ("IMAGE",),
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
        garment_image: torch.Tensor,
        garment_type: str,
        detail_category: str,
        detail_option: str,
        description: str,
        brief: str,
        gemini_api_key: str,
        api_key_status: str,
        image_model: str,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        rerun_nonce: int = 0,
        detail_reference_image: Optional[torch.Tensor] = None,
        unique_id: str = ""
    ) -> Tuple[torch.Tensor, str, str, str]:
        
        logger = RunLogger()
        logger.log(f"Starting NA - Styling Detail Change (nonce: {rerun_nonce})")
        
        client = get_gemini_client()
        if gemini_api_key:
            client.set_api_key(gemini_api_key)
        
        if not client.api_key:
            error_msg = "No API key configured. Please provide a Gemini API key."
            logger.add_error(error_msg)
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            output_json = json.dumps({"error": error_msg}, indent=2)
            return (empty_image, "", logger.get_summary(), output_json)
        
        garment_bytes = tensor_to_bytes(garment_image)
        reference_bytes = tensor_to_bytes(detail_reference_image) if detail_reference_image is not None else None
        
        config_version = get_config_version_hash()
        cache = get_styling_cache()
        cache_key = cache.compute_hash(
            garment_image_bytes=garment_bytes,
            reference_image_bytes=reference_bytes,
            garment_type=garment_type,
            detail_category=detail_category,
            detail_option=detail_option,
            description=description,
            brief=brief,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            top_p=top_p,
            config_version=config_version
        )
        
        logger.log(f"Cache key: {cache_key}")
        
        cached_result = cache.get(cache_key)
        if cached_result and rerun_nonce == 0:
            logger.log("Cache HIT - returning cached result")
            logger.finalize()
            
            if cached_result.get("image_path") and os.path.exists(cached_result["image_path"]):
                with open(cached_result["image_path"], "rb") as f:
                    cached_image_bytes = f.read()
                output_tensor = bytes_to_tensor(cached_image_bytes)
            else:
                output_tensor = torch.zeros((1, 64, 64, 3))
            
            return (
                output_tensor,
                cached_result.get("prompt", ""),
                cached_result.get("log", "") + "\n[CACHE HIT]",
                json.dumps(cached_result.get("output_json", {}), indent=2)
            )
        
        logger.log("Cache MISS - executing pipeline")
        
        templates = load_prompt_templates()
        system_instruction = templates.get("system_instruction", "")
        user_template = templates.get("user_prompt_template", "")
        
        invariants = templates.get("invariants", {}).get(garment_type, [])
        invariants_text = "\n".join([f"- {inv}" for inv in invariants])
        
        reference_note = templates.get("reference_image_note", {})
        if reference_bytes:
            ref_text = reference_note.get("with_reference", "").replace("{DETAIL_CATEGORY}", detail_category)
        else:
            ref_text = reference_note.get("without_reference", "")
        
        final_description = description.strip()
        if not final_description:
            default_template = get_default_template(garment_type, detail_category)
            final_description = default_template.replace("{OPTION}", detail_option)
        
        user_prompt = user_template.replace("{GARMENT_TYPE}", garment_type)
        user_prompt = user_prompt.replace("{DETAIL_CATEGORY}", detail_category)
        user_prompt = user_prompt.replace("{DETAIL_OPTION}", detail_option)
        user_prompt = user_prompt.replace("{USER_DESCRIPTION}", final_description)
        user_prompt = user_prompt.replace("{BRIEF}", brief if brief else "No additional context provided.")
        user_prompt = user_prompt.replace("{REFERENCE_DETAIL_USED}", ref_text)
        user_prompt = user_prompt.replace("{INVARIANTS_LIST}", invariants_text)
        
        logger.log("Calling Gemini Flash for prompt generation...")
        
        images_for_flash = {"garment": garment_bytes}
        if reference_bytes:
            images_for_flash["reference_detail"] = reference_bytes
        
        flash_result, flash_response, flash_latency, flash_request_payload = client.call_gemini_flash(
            system_instruction=system_instruction,
            brief_text=user_prompt,
            images=images_for_flash,
            max_retries=1
        )
        
        if flash_result is None:
            logger.add_error(f"Gemini Flash failed: {flash_response}")
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            output_json = json.dumps({
                "error": flash_response,
                "stage": "gemini_flash",
                "cache_key": cache_key
            }, indent=2)
            return (empty_image, "", logger.get_summary(), output_json)
        
        logger.log(f"Gemini Flash completed in {flash_latency:.2f}s")
        
        nano_banana_prompt = flash_result.get("nano_banana_prompt", "")
        logger.log(f"Generated prompt length: {len(nano_banana_prompt)} chars")
        
        selected_model_id = IMAGE_MODEL_IDS.get(image_model, NANO_BANANA_MODEL)
        logger.log(f"Calling {image_model} for image editing...")
        
        reference_images = [garment_bytes]
        if reference_bytes:
            reference_images.append(reference_bytes)
        
        image_bytes, gen_status, gen_latency, nanobana_request_payload = client.generate_image(
            prompt=nano_banana_prompt,
            reference_images=reference_images,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            top_p=top_p,
            image_model=image_model
        )
        
        if image_bytes is None:
            logger.add_error(f"Nano Banana Pro failed: {gen_status}")
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            output_json = json.dumps({
                "error": gen_status,
                "stage": "nano_banana",
                "prompt": nano_banana_prompt,
                "cache_key": cache_key
            }, indent=2)
            return (empty_image, nano_banana_prompt, logger.get_summary(), output_json)
        
        logger.log(f"Nano Banana Pro completed in {gen_latency:.2f}s")
        
        try:
            output_tensor = bytes_to_tensor(image_bytes)
            logger.log(f"Output image: {get_image_dimensions(output_tensor)}")
        except Exception as e:
            logger.add_error(f"Failed to convert output image: {str(e)}")
            logger.finalize()
            empty_image = torch.zeros((1, 64, 64, 3))
            output_json = json.dumps({"error": str(e), "stage": "image_conversion"}, indent=2)
            return (empty_image, nano_banana_prompt, logger.get_summary(), output_json)
        
        output_data = {
            "change_type": detail_category,
            "detail_option": detail_option,
            "garment_type": garment_type,
            "description": final_description,
            "reference_used": reference_bytes is not None,
            "config_version_hash": config_version,
            "cache_key": cache_key,
            "cache_status": "MISS",
            "flash_latency_s": round(flash_latency, 2),
            "nanobana_latency_s": round(gen_latency, 2),
            "total_latency_s": round(flash_latency + gen_latency, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.finalize()
        log_summary = logger.get_summary()
        
        cache.set(
            cache_key=cache_key,
            prompt=nano_banana_prompt,
            log=log_summary,
            output_json=output_data,
            image_path=None
        )
        
        return (
            output_tensor,
            nano_banana_prompt,
            log_summary,
            json.dumps(output_data, indent=2)
        )


NODE_CLASS_MAPPINGS = {
    "NA_StylingDetailChange": NAStylingDetailChangeNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NA_StylingDetailChange": "NA - Styling Detail Change",
}
