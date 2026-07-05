"""
Astrazione OCR. Due implementazioni:
- tesseract: 100% locale/offline (default per test senza account cloud)
- docai: Google Document AI (cloud, consigliato in produzione su doc anonimizzati)

Distingue PDF nativi (testo selezionabile -> nessun OCR, gratis) da scansioni.
"""
import io
from app.config import settings


def extract_text(file_path: str) -> tuple[str, int]:
    """Ritorna (testo, numero_pagine)."""
    # 1) Prova parser PDF nativo: se c'e testo, niente OCR (e gratis)
    native_text, pages = _try_native_pdf(file_path)
    if native_text and len(native_text.strip()) > 40:
        return native_text, pages

    # 2) Altrimenti OCR vero, secondo il provider scelto
    if settings.ocr_provider == "docai":
        return _ocr_docai(file_path)
    return _ocr_tesseract(file_path)


def _try_native_pdf(file_path: str) -> tuple[str, int]:
    if not file_path.lower().endswith(".pdf"):
        return "", 0
    try:
        import pdfplumber
        out, n = [], 0
        with pdfplumber.open(file_path) as pdf:
            n = len(pdf.pages)
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out), n
    except Exception:
        return "", 0


def _ocr_tesseract(file_path: str) -> tuple[str, int]:
    import pytesseract
    from PIL import Image
    if file_path.lower().endswith(".pdf"):
        from pdf2image import convert_from_path
        images = convert_from_path(file_path, dpi=200)
        texts = [pytesseract.image_to_string(img, lang="ita") for img in images]
        return "\n\n".join(texts), len(images)
    img = Image.open(file_path)
    return pytesseract.image_to_string(img, lang="ita"), 1


def _ocr_docai(file_path: str) -> tuple[str, int]:
    """Google Document AI. Richiede google-cloud-documentai installato e credenziali.
    Lasciato come integrazione: in Fase 0 si attiva impostando OCR_PROVIDER=docai
    e le variabili DOCAI_* nel .env."""
    try:
        from google.cloud import documentai_v1 as documentai
    except ImportError:
        raise RuntimeError(
            "google-cloud-documentai non installato. Aggiungilo a requirements.txt "
            "e configura le variabili DOCAI_* per usare OCR_PROVIDER=docai."
        )
    client = documentai.DocumentProcessorServiceClient()
    name = client.processor_path(
        settings.docai_project_id, settings.docai_location, settings.docai_processor_id
    )
    with open(file_path, "rb") as f:
        content = f.read()
    mime = "application/pdf" if file_path.lower().endswith(".pdf") else "image/png"
    raw = documentai.RawDocument(content=content, mime_type=mime)
    result = client.process_document(
        request=documentai.ProcessRequest(name=name, raw_document=raw)
    )
    doc = result.document
    return doc.text, len(doc.pages)
