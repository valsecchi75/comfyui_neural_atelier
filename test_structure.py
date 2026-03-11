#!/usr/bin/env python3
"""
Test script to verify the Neural Atelier custom node structure
This can be run independently to check the configuration loading
"""

import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
nodes_dir = os.path.join(base_dir, "nodes")
sys.path.insert(0, nodes_dir)

from config_loader import (
    get_configs_directory,
    get_prompt_packs,
    get_prompt_profiles,
    load_master_prompt,
    validate_config_structure
)


def main():
    print("=" * 60)
    print("Neural Atelier NA01 - Structure Verification")
    print("=" * 60)
    
    configs_dir = get_configs_directory()
    print(f"\nConfigs directory: {configs_dir}")
    print(f"Exists: {os.path.exists(configs_dir)}")
    
    is_valid, msg = validate_config_structure()
    print(f"\nConfig validation: {'PASS' if is_valid else 'FAIL'}")
    print(f"Message: {msg}")
    
    print("\n" + "-" * 40)
    print("Prompt Packs:")
    packs = get_prompt_packs()
    for pack in packs:
        print(f"\n  [{pack}]")
        profiles = get_prompt_profiles(pack)
        for profile in profiles:
            print(f"    - {profile}")
            
            content, error = load_master_prompt(pack, profile)
            if error:
                print(f"      ERROR: {error}")
            else:
                lines = content.split('\n')[:3] if content else []
                preview = ' '.join(lines)[:80] + "..."
                print(f"      Preview: {preview}")
    
    print("\n" + "=" * 60)
    print("Structure verification complete!")
    print("=" * 60)
    
    required_files = [
        "__init__.py",
        "requirements.txt",
        "README.md",
        "api_routes.py",
        "nodes/__init__.py",
        "nodes/na01_node.py",
        "nodes/na_styling_detail_node.py",
        "nodes/na_styling_cache.py",
        "nodes/na_recolor_node.py",
        "nodes/na_recolor_cache.py",
        "nodes/gemini_client.py",
        "nodes/image_utils.py",
        "nodes/config_loader.py",
        "nodes/logger.py",
        "configs/NA_Sketch_to_Photo_Orchestrator/01_Sketch_to_Photo.json",
        "configs/NA_Sketch_to_Photo_Orchestrator/02_Ghost_Mannequin.json",
        "configs/NA_Sketch_to_Photo_Orchestrator/03_Hanger.json",
        "configs/NA_Sketch_to_Photo_Orchestrator/04_Photorealistic_Exploded.json",
        "configs/NA_Sketch_to_Photo_Orchestrator/05_Isometric_Schematic.json",
        "configs/NA_Sketch_to_Photo_Orchestrator/06_Grid_2x2.json",
        "configs/NA_Styling_Detail_Change/garments.json",
        "configs/NA_Styling_Detail_Change/prompt_templates.json",
        "configs/NA_Recolor/colors.json",
        "configs/NA_Recolor/prompt_templates.json",
        "configs/NA_Recolor/recolor_rules.json",
        "web/extensions/comfyui_neural_atelier/na01_ui.js",
        "web/extensions/comfyui_neural_atelier/na_styling_ui.js",
        "web/extensions/comfyui_neural_atelier/na_recolor_ui.js"
    ]
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("\nRequired files check:")
    all_present = True
    for f in required_files:
        path = os.path.join(base_dir, f)
        exists = os.path.exists(path)
        status = "OK" if exists else "MISSING"
        print(f"  [{status}] {f}")
        if not exists:
            all_present = False
    
    print(f"\nAll required files present: {'YES' if all_present else 'NO'}")
    
    return 0 if (is_valid and all_present) else 1


if __name__ == "__main__":
    sys.exit(main())
