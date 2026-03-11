"""
Neural Atelier NA - Recolor Node
Cache system for deterministic input hashing and LRU result caching
Supports "re-run from here" functionality
"""

import hashlib
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from collections import OrderedDict


class RecolorCache:
    
    def __init__(self, max_size: int = 50, cache_dir: Optional[str] = None):
        self.max_size = max_size
        
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base_dir, ".cache", "recolor")
        
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    
    def compute_hash(
        self,
        garment_image_bytes: bytes,
        reference_image_bytes: Optional[bytes],
        pantone_color: str,
        brief: str,
        aspect_ratio: str,
        resolution: str,
        top_p: float,
        config_version: str
    ) -> str:
        hasher = hashlib.sha256()
        
        hasher.update(garment_image_bytes[:10000])
        hasher.update(str(len(garment_image_bytes)).encode())
        
        if reference_image_bytes:
            hasher.update(reference_image_bytes[:10000])
            hasher.update(str(len(reference_image_bytes)).encode())
        
        hasher.update(pantone_color.encode())
        hasher.update(brief.strip().lower().encode())
        hasher.update(aspect_ratio.encode())
        hasher.update(resolution.encode())
        hasher.update(str(round(top_p, 2)).encode())
        hasher.update(config_version.encode())
        
        return hasher.hexdigest()[:16]
    
    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if cache_key in self._memory_cache:
            self._memory_cache.move_to_end(cache_key)
            return self._memory_cache[cache_key]
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._add_to_memory(cache_key, data)
                    return data
            except (json.JSONDecodeError, IOError):
                return None
        
        return None
    
    def _add_to_memory(self, cache_key: str, data: Dict[str, Any]) -> None:
        if len(self._memory_cache) >= self.max_size:
            self._memory_cache.popitem(last=False)
        
        self._memory_cache[cache_key] = data
    
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
        
        self._add_to_memory(cache_key, cache_data)
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
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
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                    count += 1
                except IOError:
                    pass
        return count


_recolor_cache: Optional[RecolorCache] = None


def get_recolor_cache() -> RecolorCache:
    global _recolor_cache
    if _recolor_cache is None:
        _recolor_cache = RecolorCache()
    return _recolor_cache
