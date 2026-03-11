# Neural Atelier - ComfyUI Custom Node Pack

## Overview

Neural Atelier NA01 is a professional ComfyUI node for fashion visualization and product photography. It orchestrates Google's Gemini AI models to transform sketches, materials, and briefs into photorealistic product images.

### Architecture

```
User Input → Gemini 3 Flash (Prompt Orchestration) → Nano Banana Pro (Image Generation) → Output
```

1. **Gemini 3 Flash** (`gemini-3-flash-preview`): Analyzes your inputs and generates an optimized prompt
2. **Nano Banana Pro** (`gemini-3-pro-image-preview`): Generates the final high-quality image

## Installation

1. Copy the entire `comfyui_neural_atelier` folder to your ComfyUI custom nodes directory:
   ```
   ComfyUI/custom_nodes/comfyui_neural_atelier/
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Restart ComfyUI

## Nodes

### NA01 Sketch to Photo Orchestrator

The main node that handles the complete workflow.

**Inputs:**

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| prompt_pack | Dropdown | Yes | Select a prompt pack from configs/ |
| brief_text | Text | Yes | Your creative brief |
| gemini_api_key | String | Yes | Your Gemini API key |
| api_key_status | Display | Yes | Shows API key verification status |
| aspect_ratio | Dropdown | Yes | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 |
| resolution | Dropdown | Yes | 1K, 2K, 4K (image quality) |
| top_p | Float | Yes | Creativity parameter (0.0-1.0) |
| talent_image | Image | No | Reference talent/model image |
| flat_sketch_image | Image | No | Technical sketch |
| material_image | Image | No | Material/texture reference |
| pattern_image | Image | No | Pattern reference |
| template_master_1 | Image | No | Template image 1 |
| template_master_2 | Image | No | Template image 2 |

**Outputs:**

- `image`: Generated image
- `log`: Execution summary with run_id, timings, and file paths

### NA01 Verify API Key

Utility node to verify your Gemini API key.

### NA01 Get Profiles

Utility node to list available profiles for a prompt pack.

## Prompt Packs

Located in `configs/`, organized by use case:

- **01_Senior_Technical_Fashion_Designer**: Sketch-to-photo translation
- **02_Physics_Simulation**: Ghost mannequin and hanger presentations
- **03_Macro_Details**: 2x2 detail grid compositions
- **04_Technical_Illustration**: Isometric schematic diagrams
- **05_Exploded_View**: Photorealistic exploded view infographics

## Output Logging

All executions are logged to:
```
ComfyUI/output/neural_atelier/NA01/YYYY-MM-DD/[run_id]/
```

Files per run:
- `run.json`: Complete execution metadata
- `nano_banana_prompt.txt`: Generated prompt
- `gemini_flash_response_raw.txt`: Raw API response
- `request_manifest.json`: Input configuration

## API Key Configuration

You can provide your API key in two ways:

1. **Node Input**: Enter directly in the `gemini_api_key` field
2. **Environment Variable**: Set `GEMINI_API_KEY` in your environment

## Security

- API keys are never written to disk
- All logs automatically redact authentication data
- Keys can be verified without exposing them

## Requirements

- ComfyUI (latest version recommended)
- Python 3.10+
- google-genai >= 1.0.0
- Pillow >= 9.0.0
- torch >= 2.0.0

## Version

1.0.0

## License

MIT License
