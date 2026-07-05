"""Storage su filesystem locale (volume Docker dedicato e persistente)."""
import os
from app.services.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, root: str):
        self.root = root

    def _full(self, key: str) -> str:
        return os.path.join(self.root, key)

    def save(self, key: str, data: bytes, content_type: str = "") -> str:
        p = self._full(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return key

    def load(self, key: str) -> bytes:
        with open(self._full(key), "rb") as f:
            return f.read()

    def url(self, key: str, expires_s: int = 3600) -> str | None:
        return None  # locale: niente signed url, si serve via stream

    def delete(self, key: str) -> None:
        try:
            os.remove(self._full(key))
        except FileNotFoundError:
            pass

    def local_path(self, key: str) -> str:
        return self._full(key)
