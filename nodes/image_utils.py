"""
Image Utilities for Neural Atelier NA01 Node
Handles image conversion between ComfyUI tensors and bytes
"""

import io
import numpy as np
from PIL import Image
from typing import Optional, Tuple, List
import torch


def tensor_to_pil(tensor: torch.Tensor) -> Image.Image:
    if tensor.dim() == 4:
        tensor = tensor[0]
    
    if tensor.dim() == 3:
        if tensor.shape[0] in [1, 3, 4]:
            tensor = tensor.permute(1, 2, 0)
    
    np_array = tensor.cpu().numpy()
    
    if np_array.max() <= 1.0:
        np_array = (np_array * 255).astype(np.uint8)
    else:
        np_array = np_array.astype(np.uint8)
    
    if np_array.ndim == 2:
        return Image.fromarray(np_array, mode="L")
    elif np_array.shape[2] == 1:
        return Image.fromarray(np_array[:, :, 0], mode="L")
    elif np_array.shape[2] == 3:
        return Image.fromarray(np_array, mode="RGB")
    elif np_array.shape[2] == 4:
        return Image.fromarray(np_array, mode="RGBA")
    else:
        return Image.fromarray(np_array[:, :, :3], mode="RGB")


def tensor_to_bytes(tensor: torch.Tensor, format: str = "PNG") -> bytes:
    pil_image = tensor_to_pil(tensor)
    buffer = io.BytesIO()
    pil_image.save(buffer, format=format)
    return buffer.getvalue()


def bytes_to_pil(image_bytes: bytes) -> Image.Image:
    buffer = io.BytesIO(image_bytes)
    return Image.open(buffer)


def bytes_to_tensor(image_bytes: bytes) -> torch.Tensor:
    pil_image = bytes_to_pil(image_bytes)
    
    if pil_image.mode == "RGBA":
        pil_image = pil_image.convert("RGB")
    elif pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    
    np_array = np.array(pil_image).astype(np.float32) / 255.0
    
    tensor = torch.from_numpy(np_array)
    
    if tensor.dim() == 2:
        tensor = tensor.unsqueeze(2).repeat(1, 1, 3)
    
    tensor = tensor.unsqueeze(0)
    
    return tensor


def get_image_dimensions(tensor: Optional[torch.Tensor]) -> Tuple[int, int]:
    if tensor is None:
        return (0, 0)
    
    if tensor.dim() == 4:
        _, h, w, _ = tensor.shape
    elif tensor.dim() == 3:
        if tensor.shape[0] in [1, 3, 4]:
            _, h, w = tensor.shape
        else:
            h, w, _ = tensor.shape
    else:
        return (0, 0)
    
    return (w, h)


def resize_image_if_needed(
    image_bytes: bytes,
    max_dimension: int = 4096,
    quality: int = 95
) -> Tuple[bytes, bool, str]:
    pil_image = bytes_to_pil(image_bytes)
    original_size = pil_image.size
    
    if max(original_size) <= max_dimension:
        return image_bytes, False, ""
    
    ratio = max_dimension / max(original_size)
    new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
    
    resized = pil_image.resize(new_size, Image.Resampling.LANCZOS)
    
    buffer = io.BytesIO()
    if resized.mode == "RGBA":
        resized.save(buffer, format="PNG")
    else:
        resized.save(buffer, format="JPEG", quality=quality)
    
    log_msg = f"Resized from {original_size} to {new_size}"
    return buffer.getvalue(), True, log_msg


def validate_image_tensor(tensor: Optional[torch.Tensor], name: str) -> Tuple[bool, str]:
    if tensor is None:
        return True, f"{name}: not provided"
    
    if not isinstance(tensor, torch.Tensor):
        return False, f"{name}: not a valid tensor"
    
    if tensor.dim() < 2 or tensor.dim() > 4:
        return False, f"{name}: invalid dimensions ({tensor.dim()}D)"
    
    dims = get_image_dimensions(tensor)
    return True, f"{name}: {dims[0]}x{dims[1]}"


def collect_provided_images(
    talent: Optional[torch.Tensor] = None,
    flat_sketch: Optional[torch.Tensor] = None,
    material: Optional[torch.Tensor] = None,
    pattern: Optional[torch.Tensor] = None,
    template_1: Optional[torch.Tensor] = None,
    template_2: Optional[torch.Tensor] = None
) -> Tuple[dict, List[str]]:
    images = {}
    logs = []
    
    image_map = {
        "talent_image": talent,
        "flat_sketch_image": flat_sketch,
        "material_image": material,
        "pattern_image": pattern,
        "template_master_1": template_1,
        "template_master_2": template_2
    }
    
    for name, tensor in image_map.items():
        if tensor is not None:
            try:
                image_bytes = tensor_to_bytes(tensor)
                images[name] = image_bytes
                dims = get_image_dimensions(tensor)
                logs.append(f"{name}: {dims[0]}x{dims[1]} ({len(image_bytes)} bytes)")
            except Exception as e:
                logs.append(f"{name}: conversion error - {str(e)}")
                images[name] = None
        else:
            images[name] = None
            logs.append(f"{name}: not provided")
    
    return images, logs
