"""
Neural Atelier NA - Styling Detail Change
Cache system for deterministic input hashing and result caching
"""

import hashlib
import json
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class StylingCache:
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base_dir, ".cache", "styling")
        
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def compute_hash(
        self,
        garment_image_bytes: Optional[bytes],
        reference_image_bytes: Optional[bytes],
        garment_type: str,
        detail_category: str,
        detail_option: str,
        description: str,
        brief: str,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        config_version: str
    ) -> str:
        hash_input = {
            "garment_image_hash": hashlib.sha256(garment_image_bytes).hexdigest() if garment_image_bytes else None,
            "reference_image_hash": hashlib.sha256(reference_image_bytes).hexdigest() if reference_image_bytes else None,
            "garment_type": garment_type,
            "detail_category": detail_category,
            "detail_option": detail_option,
            "description": description.strip().lower(),
            "brief": brief.strip().lower(),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "top_p": round(top_p, 2),
            "config_version": config_version
        }
        
        hash_string = json.dumps(hash_input, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()[:16]
    
    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    self._memory_cache[cache_key] = data
                    return data
            except (json.JSONDecodeError, IOError):
                return None
        
        return None
    
    def set(
        self,
        cache_key: str,
        prompt: str,
        log: str,
        output_json: Dict[str, Any],
        image_path: Optional[str] = None
    ) -> None:
        cache_data = {
            "cache_key": cache_key,
            "prompt": prompt,
            "log": log,
            "output_json": output_json,
            "image_path": image_path,
            "cached_at": datetime.now().isoformat()
        }
        
        self._memory_cache[cache_key] = cache_data
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass
    
    def invalidate(self, cache_key: str) -> bool:
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                return True
            except IOError:
                return False
        return False
    
    def clear_all(self) -> int:
        count = 0
        self._memory_cache.clear()
        
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.cache_dir, filename))
                        count += 1
                    except IOError:
                        pass
        return count


_styling_cache: Optional[StylingCache] = None


def get_styling_cache() -> StylingCache:
    global _styling_cache
    if _styling_cache is None:
        _styling_cache = StylingCache()
    return _styling_cache
