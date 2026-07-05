"""Factory dello storage. Cambiare backend = cambiare una variabile d'ambiente."""
from app.config import settings
from app.services.storage.base import StorageBackend, make_key, sha256_bytes
from app.services.storage.local import LocalStorage

_cache = {}


def get_storage() -> StorageBackend:
    backend = (settings.storage_backend or "local").lower()
    if backend in _cache:
        return _cache[backend]
    if backend == "gcs":
        from app.services.storage.gcs import GCSStorage
        store = GCSStorage(settings.gcs_bucket)
    else:
        store = LocalStorage(settings.storage_local_path)
    _cache[backend] = store
    return store
