"""
Config Loader for Neural Atelier NA01 Node
Loads Master Prompt JSON files from configs/NA_Sketch_to_Photo_Orchestrator/ directory
"""

import os
import json
from typing import List, Dict, Optional, Tuple


def get_base_configs_directory() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    return os.path.join(parent_dir, "configs")


def get_configs_directory() -> str:
    return os.path.join(get_base_configs_directory(), "NA_Sketch_to_Photo_Orchestrator")


def get_prompt_packs() -> List[str]:
    base_dir = get_base_configs_directory()
    
    if not os.path.exists(base_dir):
        return []
    
    packs = []
    for item in sorted(os.listdir(base_dir)):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            has_json = any(f.endswith(".json") for f in os.listdir(item_path))
            if has_json:
                packs.append(item)
    
    return packs if packs else ["No packs found"]


def get_prompt_profiles(pack_name: str) -> List[str]:
    base_dir = get_base_configs_directory()
    pack_path = os.path.join(base_dir, pack_name)
    
    if not os.path.exists(pack_path):
        return ["No profiles found"]
    
    profiles = []
    for item in sorted(os.listdir(pack_path)):
        if item.endswith(".json"):
            profiles.append(item[:-5])
    
    return profiles if profiles else ["No profiles found"]


def load_master_prompt(pack_name: str, profile_name: str) -> Tuple[Optional[str], Optional[str]]:
    base_dir = get_base_configs_directory()
    json_path = os.path.join(base_dir, pack_name, f"{profile_name}.json")
    
    if not os.path.exists(json_path):
        return None, f"Profile not found: {json_path}"
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, None
    except Exception as e:
        return None, f"Error loading profile: {str(e)}"


def get_all_configs() -> Dict[str, List[str]]:
    result = {}
    for pack in get_prompt_packs():
        if pack != "No packs found":
            profiles = get_prompt_profiles(pack)
            if profiles != ["No profiles found"]:
                result[pack] = profiles
    return result


def validate_config_structure() -> Tuple[bool, str]:
    base_dir = get_base_configs_directory()
    
    if not os.path.exists(base_dir):
        return False, f"Configs directory not found: {base_dir}"
    
    packs = get_prompt_packs()
    if not packs or packs == ["No packs found"]:
        return False, "No prompt packs found in configs directory"
    
    total_profiles = 0
    for pack in packs:
        profiles = get_prompt_profiles(pack)
        if profiles != ["No profiles found"]:
            total_profiles += len(profiles)
    
    if total_profiles == 0:
        return False, "No profile JSON files found in any pack"
    
    return True, f"Found {len(packs)} packs with {total_profiles} total profiles"
