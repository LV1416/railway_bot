import time
import logging
from typing import Dict, Tuple, Any

import config

logger = logging.getLogger(__name__)

class SheetsCache:
    """
    A simple in-memory cache for Google Sheets data to avoid rate limits.
    Data is cached for CACHE_TTL seconds.
    Writes should invalidate the cache.
    """
    def __init__(self, ttl_seconds: int = config.CACHE_TTL):
        self.ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        if key in self._store:
            timestamp, data = self._store[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self._store[key]
        return None

    def set(self, key: str, data: Any):
        self._store[key] = (time.time(), data)

    def invalidate(self, key: str):
        if key in self._store:
            del self._store[key]

    def invalidate_all(self):
        self._store.clear()

# Global cache instance
sheets_cache = SheetsCache()
