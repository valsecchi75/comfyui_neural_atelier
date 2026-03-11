"""
Neural Atelier - ComfyUI Custom Node Pack
Version: 1.2.0

A professional ComfyUI node pack for fashion visualization using Gemini AI.
Orchestrates Gemini Flash for prompt generation and Nano Banana Pro for image generation.
"""

from .nodes.na01_node import (
    NODE_CLASS_MAPPINGS as NA01_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as NA01_DISPLAY_MAPPINGS
)
from .nodes.na_styling_detail_node import (
    NODE_CLASS_MAPPINGS as STYLING_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as STYLING_DISPLAY_MAPPINGS
)
from .nodes.na_recolor_node import (
    NODE_CLASS_MAPPINGS as RECOLOR_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as RECOLOR_DISPLAY_MAPPINGS
)

__version__ = "1.2.0"
__author__ = "Neural Atelier"

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(NA01_MAPPINGS)
NODE_CLASS_MAPPINGS.update(STYLING_MAPPINGS)
NODE_CLASS_MAPPINGS.update(RECOLOR_MAPPINGS)

NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(NA01_DISPLAY_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(STYLING_DISPLAY_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(RECOLOR_DISPLAY_MAPPINGS)

WEB_DIRECTORY = "./web/extensions/comfyui_neural_atelier"

try:
    from . import api_routes
except ImportError:
    pass

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY"
]
