"""
ComfyUI Custom Node - Neural Atelier API Routes
Backend routes for API verification and configuration
"""

import os
import json
from server import PromptServer
from aiohttp import web
from google import genai

@PromptServer.instance.routes.post("/neural_atelier/verify_api")
async def verify_api_key(request):
    try:
        data = await request.json()
        api_key = data.get("api_key", "").strip()
        
        if not api_key:
            return web.json_response({"status": "error", "message": "API Key Missing"})
        
        try:
            client = genai.Client(api_key=api_key)
            models = client.models.list()
            model_list = list(models)
            if len(model_list) > 0:
                return web.json_response({"status": "success", "message": f"API Key Valid ({len(model_list)} models available)"})
            else:
                return web.json_response({"status": "error", "message": "No models available"})
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "UNAUTHENTICATED" in error_msg:
                return web.json_response({"status": "error", "message": "Invalid API Key"})
            elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                return web.json_response({"status": "error", "message": "Rate limit exceeded. Try again later."})
            elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                return web.json_response({"status": "error", "message": "Permission denied. Check API key permissions."})
            else:
                return web.json_response({"status": "error", "message": f"API Error: {str(e)[:80]}"})

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Server Error: {str(e)[:50]}"})


@PromptServer.instance.routes.get("/neural_atelier/styling/garments_config")
async def get_garments_config(request):
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "configs",
            "NA_Styling_Detail_Change",
            "garments.json"
        )
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return web.json_response(config)
        else:
            return web.json_response({"garment_types": []})
    except Exception as e:
        return web.json_response({"error": str(e), "garment_types": []})


@PromptServer.instance.routes.get("/neural_atelier/recolor/colors_config")
async def get_colors_config(request):
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "configs",
            "NA_Recolor",
            "colors.json"
        )
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return web.json_response(config)
        else:
            return web.json_response({"color_families": []})
    except Exception as e:
        return web.json_response({"error": str(e), "color_families": []})


print("[Neural Atelier] API Routes registered successfully")
