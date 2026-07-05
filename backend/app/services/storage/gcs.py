"""Storage su Google Cloud Storage (bucket UE). FUTURO: attivo con STORAGE_BACKEND=gcs.

Richiede `google-cloud-storage` (non installato di default) e GOOGLE_APPLICATION_CREDENTIALS.
Stesso contratto di LocalStorage: il chiamante non cambia.
"""
import os
import tempfile
from app.services.storage.base import StorageBackend


class GCSStorage(StorageBackend):
    def __init__(self, bucket: str):
        from google.cloud import storage as gcs  # import lazy: dipendenza opzionale
        self._client = gcs.Client()
        self._bucket = self._client.bucket(bucket)

    def _blob(self, key: str):
        return self._bucket.blob(key)

    def save(self, key: str, data: bytes, content_type: str = "") -> str:
        self._blob(key).upload_from_string(data, content_type=content_type or "application/octet-stream")
        return key

    def load(self, key: str) -> bytes:
        return self._blob(key).download_as_bytes()

    def url(self, key: str, expires_s: int = 3600) -> str | None:
        from datetime import timedelta
        return self._blob(key).generate_signed_url(expiration=timedelta(seconds=expires_s))

    def delete(self, key: str) -> None:
        self._blob(key).delete()

    def local_path(self, key: str) -> str:
        # GCS non è un filesystem: scarica in un file temporaneo per OCR/LLM.
        suffix = os.path.splitext(key)[1] or ".bin"
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(self.load(key))
        return path
