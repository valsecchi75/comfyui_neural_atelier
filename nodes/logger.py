"""
Logger for Neural Atelier NA01 Node
Handles disk logging of all prompts and execution metadata
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List


def get_output_base_directory() -> str:
    comfyui_output = os.environ.get("COMFYUI_OUTPUT_DIRECTORY", "")
    
    if comfyui_output:
        return os.path.join(comfyui_output, "neural_atelier", "NA01")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    grandparent_dir = os.path.dirname(parent_dir)
    
    if os.path.basename(grandparent_dir) == "custom_nodes":
        comfyui_dir = os.path.dirname(grandparent_dir)
        return os.path.join(comfyui_dir, "output", "neural_atelier", "NA01")
    
    return os.path.join(parent_dir, "output", "neural_atelier", "NA01")


def get_run_directory(run_id: str) -> str:
    base_dir = get_output_base_directory()
    date_str = datetime.now().strftime("%Y-%m-%d")
    run_dir = os.path.join(base_dir, date_str, run_id)
    
    os.makedirs(run_dir, exist_ok=True)
    
    return run_dir


def generate_run_id() -> str:
    return str(uuid.uuid4())


class RunLogger:
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or generate_run_id()
        self.run_dir = get_run_directory(self.run_id)
        self.start_time = datetime.now()
        self.log_entries: List[str] = []
        
        self.run_data: Dict[str, Any] = {
            "run_id": self.run_id,
            "start_timestamp": self.start_time.isoformat(),
            "end_timestamp": None,
            "prompt_pack": None,
            "prompt_profile": None,
            "brief_text": None,
            "images": {},
            "gemini_flash": {
                "model_id": None,
                "latency_seconds": None,
                "success": False,
                "error": None
            },
            "nano_banana": {
                "model_id": None,
                "latency_seconds": None,
                "aspect_ratio": None,
                "resolution": None,
                "top_p": None,
                "success": False,
                "error": None
            },
            "output_files": [],
            "errors": [],
            "retries": 0
        }
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] {message}"
        self.log_entries.append(entry)
    
    def set_prompt_info(self, pack: str, profile: str, brief: str):
        self.run_data["prompt_pack"] = pack
        self.run_data["prompt_profile"] = profile
        self.run_data["brief_text"] = brief
        self.log(f"Prompt: {pack}/{profile}")
    
    def set_image_info(self, images: Dict[str, Any]):
        self.run_data["images"] = images
        provided = [k for k, v in images.items() if v]
        self.log(f"Images provided: {len(provided)}")
    
    def set_gemini_flash_result(
        self,
        model_id: str,
        latency: float,
        success: bool,
        error: Optional[str] = None
    ):
        self.run_data["gemini_flash"]["model_id"] = model_id
        self.run_data["gemini_flash"]["latency_seconds"] = round(latency, 3)
        self.run_data["gemini_flash"]["success"] = success
        self.run_data["gemini_flash"]["error"] = error
        
        if success:
            self.log(f"Gemini Flash: success ({latency:.2f}s)")
        else:
            self.log(f"Gemini Flash: failed - {error}")
    
    def set_nano_banana_result(
        self,
        model_id: str,
        latency: float,
        success: bool,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        error: Optional[str] = None
    ):
        self.run_data["nano_banana"]["model_id"] = model_id
        self.run_data["nano_banana"]["latency_seconds"] = round(latency, 3)
        self.run_data["nano_banana"]["aspect_ratio"] = aspect_ratio
        self.run_data["nano_banana"]["resolution"] = resolution
        self.run_data["nano_banana"]["top_p"] = top_p
        self.run_data["nano_banana"]["success"] = success
        self.run_data["nano_banana"]["error"] = error
        
        if success:
            self.log(f"Nano Banana Pro: success ({latency:.2f}s)")
        else:
            self.log(f"Nano Banana Pro: failed - {error}")
    
    def add_error(self, error: str):
        self.run_data["errors"].append(error)
        self.log(f"ERROR: {error}")
    
    def increment_retries(self):
        self.run_data["retries"] += 1
    
    def save_nano_banana_prompt(self, prompt: str):
        filepath = os.path.join(self.run_dir, "nano_banana_prompt.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(prompt)
        self.run_data["output_files"].append("nano_banana_prompt.txt")
        self.log(f"Saved: nano_banana_prompt.txt")
    
    def save_gemini_flash_response(self, response: str):
        filepath = os.path.join(self.run_dir, "gemini_flash_response_raw.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response)
        self.run_data["output_files"].append("gemini_flash_response_raw.txt")
    
    def save_request_manifest(self, manifest: Dict[str, Any]):
        filepath = os.path.join(self.run_dir, "request_manifest.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        self.run_data["output_files"].append("request_manifest.json")
    
    def finalize(self) -> str:
        self.run_data["end_timestamp"] = datetime.now().isoformat()
        
        total_time = (datetime.now() - self.start_time).total_seconds()
        self.log(f"Total execution time: {total_time:.2f}s")
        
        run_json_path = os.path.join(self.run_dir, "run.json")
        
        safe_data = self.run_data.copy()
        
        with open(run_json_path, "w", encoding="utf-8") as f:
            json.dump(safe_data, f, indent=2)
        
        self.run_data["output_files"].append("run.json")
        
        return run_json_path
    
    def get_summary(self) -> str:
        lines = [
            f"Run ID: {self.run_id}",
            f"Profile: {self.run_data['prompt_pack']}/{self.run_data['prompt_profile']}",
        ]
        
        flash_data = self.run_data["gemini_flash"]
        if flash_data["success"]:
            lines.append(f"Gemini Flash: {flash_data['latency_seconds']}s")
        else:
            lines.append(f"Gemini Flash: FAILED - {flash_data['error']}")
        
        nb_data = self.run_data["nano_banana"]
        if nb_data["success"]:
            lines.append(f"Nano Banana: {nb_data['latency_seconds']}s")
        else:
            lines.append(f"Nano Banana: FAILED - {nb_data['error']}")
        
        lines.append(f"Output: {self.run_dir}")
        
        if self.run_data["errors"]:
            lines.append(f"Errors: {len(self.run_data['errors'])}")
        
        return "\n".join(lines)
