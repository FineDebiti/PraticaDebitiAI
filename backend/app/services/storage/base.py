"""Astrazione storage file originali. Local ora, GCS-ready domani (stesso chiamante).

Principio dati legali: il file ORIGINALE caricato non si perde, è ri-scaricabile e
tracciabile (hash sha256 per integrità/dedup).
"""
import hashlib
import re
import uuid


def make_key(case_id: str, doc_type: str, filename: str) -> str:
    """Chiave organizzata per pratica e tipo, con uuid anti-collisione:
    cases/{case_id}/{doc_type}/{uuid}_{filename_sanitizzato}."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (filename or "file")).strip("_")[:80] or "file"
    dt = (doc_type or "altro").strip() or "altro"
    return f"cases/{case_id}/{dt}/{uuid.uuid4().hex}_{safe}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StorageBackend:
    """Interfaccia comune. I chiamanti non sanno se è locale o GCS."""

    def save(self, key: str, data: bytes, content_type: str = "") -> str:
        """Salva i byte sotto `key` e ritorna lo storage_uri (la key stessa)."""
        raise NotImplementedError

    def load(self, key: str) -> bytes:
        raise NotImplementedError

    def url(self, key: str, expires_s: int = 3600) -> str | None:
        """Link temporaneo (GCS signed url); locale ritorna None (si usa lo stream)."""
        return None

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def local_path(self, key: str) -> str:
        """Percorso su filesystem per i componenti che richiedono un file vero
        (OCR, LLM multimodale). Locale: il path reale. GCS: scarica in un temp."""
        raise NotImplementedError
