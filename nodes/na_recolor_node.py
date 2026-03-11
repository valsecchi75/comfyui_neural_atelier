"""
Neural Atelier NA - Recolor Node
Recolors garment images to match a target Pantone color or reference image
Based on NA - Styling Detail Change V6 structure
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
from .na_recolor_cache import get_recolor_cache


_gemini_client: Optional[GeminiClient] = None
_prompt_templates_cache: Optional[Dict[str, Any]] = None
_recolor_rules_cache: Optional[Dict[str, Any]] = None
_pantone_colors_curated_cache: Optional[List[str]] = None
_pantone_colors_all_cache: Optional[List[str]] = None

PLACEHOLDER_COLOR = "-- Select a Pantone color --"


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def _load_pantone_from_file(filename: str) -> List[str]:
    """Load Pantone colors from a JSON file in configs/NA_Recolor/"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "NA_Recolor",
        filename
    )
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        colors_list = [PLACEHOLDER_COLOR]
        for family in data.get("color_families", []):
            for group in family.get("groups", []):
                for color in group.get("colors", []):
                    pantone_code = color.get("pantone_code", "")
                    common_name = color.get("common_name", "")
                    if pantone_code and common_name:
                        colors_list.append(f"{common_name.capitalize()} - Pantone {pantone_code}")
        
        if len(colors_list) <= 1:
            print(f"[NA-Recolor] WARNING: {filename} loaded but contains no valid colors!")
            colors_list.append(f"ERROR: No colors in {filename}")
        
        return colors_list
            
    except (IOError, json.JSONDecodeError, KeyError) as e:
        print(f"[NA-Recolor] ERROR: Failed to load {filename}: {e}")
        return [PLACEHOLDER_COLOR, f"ERROR: {filename} not found or invalid"]


def get_pantone_colors_curated() -> List[str]:
    """Load curated Pantone colors from colors.json (45 colors)"""
    global _pantone_colors_curated_cache
    if _pantone_colors_curated_cache is not None:
        return _pantone_colors_curated_cache
    _pantone_colors_curated_cache = _load_pantone_from_file("colors.json")
    return _pantone_colors_curated_cache


def get_pantone_colors_all() -> List[str]:
    """Load all Pantone colors from pantone_all.json (2310 colors)"""
    global _pantone_colors_all_cache
    if _pantone_colors_all_cache is not None:
        return _pantone_colors_all_cache
    _pantone_colors_all_cache = _load_pantone_from_file("pantone_all.json")
    return _pantone_colors_all_cache


def load_prompt_templates() -> Dict[str, Any]:
    global _prompt_templates_cache
    if _prompt_templates_cache is not None:
        return _prompt_templates_cache
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "NA_Recolor",
        "prompt_templates.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _prompt_templates_cache = json.load(f)
            return _prompt_templates_cache
    except (IOError, json.JSONDecodeError):
        _prompt_templates_cache = {
            "version": "1.0.0",
            "system_instruction": "You are a color expert for fashion garments. Generate a detailed prompt to recolor the garment.",
            "user_prompt_template": "Recolor this garment to {PANTONE_COLOR}. Color source: {COLOR_SOURCE}. Brief: {BRIEF}. Constraints: {INVARIANTS_LIST}"
        }
        return _prompt_templates_cache


def load_recolor_rules() -> Dict[str, Any]:
    global _recolor_rules_cache
    if _recolor_rules_cache is not None:
        return _recolor_rules_cache
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "NA_Recolor",
        "recolor_rules.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _recolor_rules_cache = json.load(f)
            return _recolor_rules_cache
    except (IOError, json.JSONDecodeError):
        _recolor_rules_cache = {
            "version": "1.0.0",
            "invariants": [
                "Preserve garment texture and fabric appearance",
                "Maintain original silhouette and shape",
                "Keep shadows and highlights consistent"
            ]
        }
        return _recolor_rules_cache


class NARecolorNode:
    
    CATEGORY = "Neural Atelier"
    FUNCTION = "execute"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("image", "prompt", "log", "output_json")
    
    @classmethod
    def INPUT_TYPES(cls):
        colors_curated = get_pantone_colors_curated()
        colors_all = get_pantone_colors_all()
        return {
            "required": {
                "garment_image": ("IMAGE",),
                "pantone_color_curated": (colors_curated, {"default": colors_curated[0]}),
                "pantone_color": (colors_all, {"default": colors_all[0]}),
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
                "color_reference_image": ("IMAGE",),
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
        pantone_color_curated: str,
        pantone_color: str,
        brief: str,
        gemini_api_key: str,
        api_key_status: str,
        image_model: str,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        rerun_nonce: int = 0,
        color_reference_image: Optional[torch.Tensor] = None,
        unique_id: str = ""
    ) -> Tuple[torch.Tensor, str, str, str]:
        
        logger = RunLogger()
        logger.log(f"Starting NA - Recolor (nonce: {rerun_nonce})")
        
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
        reference_bytes = tensor_to_bytes(color_reference_image) if color_reference_image is not None else None
        
        cache = get_recolor_cache()
        cache_key = cache.compute_hash(
            garment_image_bytes=garment_bytes,
            reference_image_bytes=reference_bytes,
            pantone_color=f"{pantone_color_curated}|{pantone_color}",
            brief=brief,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            top_p=top_p,
            config_version="v2"
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
        rules = load_recolor_rules()
        invariants = rules.get("invariants", [])
        invariants_text = "\n".join([f"- {inv}" for inv in invariants])
        
        extracted_color = None
        color_source = ""
        target_color = ""
        
        if reference_bytes:
            logger.log("Color reference image detected - extracting color with Gemini Flash...")
            color_extract_instruction = """You are a color analysis expert. Analyze the provided reference image and extract the dominant color.

Return a JSON object with the extracted color in multiple formats:
{
  "hex": "#RRGGBB",
  "rgb": "R, G, B",
  "pantone_approximate": "Pantone code if identifiable, otherwise null",
  "color_name": "Common color name (e.g., Navy Blue, Coral Red)",
  "color_description": "Brief description of the color characteristics"
}

Focus on the most prominent/dominant color in the image. If it's a fabric or material sample, extract the main color ignoring shadows or highlights."""

            color_extract_prompt = "Extract the dominant color from this reference image. Return only the JSON object."
            
            extract_result, extract_response, extract_latency, _ = client.call_gemini_flash(
                system_instruction=color_extract_instruction,
                brief_text=color_extract_prompt,
                images={"color_reference": reference_bytes},
                max_retries=1
            )
            
            if extract_result and isinstance(extract_result, dict):
                hex_color = extract_result.get("hex", "")
                rgb_color = extract_result.get("rgb", "")
                pantone_approx = extract_result.get("pantone_approximate")
                color_name = extract_result.get("color_name", "")
                color_desc = extract_result.get("color_description", "")
                
                if pantone_approx and pantone_approx != "null":
                    target_color = f"{pantone_approx} ({color_name})"
                elif hex_color:
                    target_color = f"{hex_color} {color_name}"
                elif rgb_color:
                    target_color = f"RGB({rgb_color}) {color_name}"
                else:
                    target_color = color_name if color_name else "extracted color"
                
                extracted_color = {
                    "hex": hex_color,
                    "rgb": rgb_color,
                    "pantone": pantone_approx,
                    "name": color_name,
                    "description": color_desc
                }
                color_source = "reference_image"
                logger.log(f"Extracted color: {target_color} (HEX: {hex_color})")
            else:
                logger.log("Color extraction failed, falling back to reference image analysis")
                target_color = "color from reference image"
                color_source = "reference_image"
        else:
            curated_valid = pantone_color_curated != PLACEHOLDER_COLOR and not pantone_color_curated.startswith("ERROR:")
            all_valid = pantone_color != PLACEHOLDER_COLOR and not pantone_color.startswith("ERROR:")
            
            if curated_valid:
                target_color = pantone_color_curated
                color_source = "pantone_curated"
                logger.log(f"Using curated Pantone color: {target_color}")
            elif all_valid:
                target_color = pantone_color
                color_source = "pantone_all"
                logger.log(f"Using Pantone color (all): {target_color}")
            else:
                error_msg = "Please select a Pantone color from either dropdown, or connect a color reference image."
                if pantone_color_curated.startswith("ERROR:") or pantone_color.startswith("ERROR:"):
                    error_msg = "Color configuration files are missing or invalid. Please check the configs/NA_Recolor/ folder."
                logger.add_error(error_msg)
                logger.finalize()
                empty_image = torch.zeros((1, 64, 64, 3))
                output_json = json.dumps({"error": error_msg}, indent=2)
                return (empty_image, "", logger.get_summary(), output_json)
        
        system_instruction = templates.get("system_instruction", "You are a color expert for fashion garments.")
        user_template = templates.get("user_prompt_template", "Recolor this garment to {PANTONE_COLOR}. {BRIEF}")
        
        user_prompt = user_template.replace("{PANTONE_COLOR}", target_color)
        user_prompt = user_prompt.replace("{COLOR_SOURCE}", color_source)
        user_prompt = user_prompt.replace("{BRIEF}", brief if brief else "No additional context provided.")
        user_prompt = user_prompt.replace("{INVARIANTS_LIST}", invariants_text)
        
        if extracted_color:
            user_prompt += f"\n\nExtracted color details: HEX={extracted_color.get('hex', 'N/A')}, RGB={extracted_color.get('rgb', 'N/A')}, Name={extracted_color.get('name', 'N/A')}"
        
        logger.log("Calling Gemini Flash for prompt generation...")
        
        images_for_flash = {"garment": garment_bytes}
        if reference_bytes:
            images_for_flash["color_reference"] = reference_bytes
        
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
        logger.log(f"Calling {image_model} for image recoloring...")
        
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
            "target_color": target_color,
            "pantone_dropdown": pantone_color if pantone_color != PLACEHOLDER_COLOR else None,
            "color_source": color_source,
            "extracted_color": extracted_color,
            "reference_used": reference_bytes is not None,
            "config_version_hash": "v1",
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
    "NA_Recolor": NARecolorNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NA_Recolor": "NA - Recolor",
}
