class PreviewCache:
    _cache = {}
    def get(self, key: str): return self._cache.get(key)
    def set(self, key: str, value: dict): self._cache[key] = value
    def process(self, key): return self.get(key) or {"status": "miss"}
