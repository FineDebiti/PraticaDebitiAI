"""
Astrazione OCR. Tre implementazioni:
- paddleocr: 100% locale/offline (default raccomandato, alta precisione su tabelle e documenti inclinati/scansionati)
- tesseract: 100% locale/offline (fallback legacy)
- docai: Google Document AI (cloud, opzionale in produzione su doc anonimizzati)

Distingue PDF nativi (testo selezionabile -> nessun OCR, gratis) da scansioni.
"""
import io
import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> tuple[str, int]:
    """Ritorna (testo, numero_pagine)."""
    # 1) Prova parser PDF nativo: se c'e testo, niente OCR (e gratis)
    native_text, pages = _try_native_pdf(file_path)
    if native_text and len(native_text.strip()) > 40:
        return native_text, pages

    # 2) Altrimenti OCR vero, secondo il provider scelto
    if settings.ocr_provider == "docai":
        return _ocr_docai(file_path)
    if settings.ocr_provider == "tesseract":
        return _ocr_tesseract(file_path)
    return _ocr_paddle(file_path)


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


def _ocr_paddle(file_path: str) -> tuple[str, int]:
    """OCR con PaddleOCR (PP-OCR), ideale per tabelle, scansioni, timbri e testi ruotati.
    100% offline e locale, senza bisogno di GPU."""
    try:
        os.environ["FLAGS_use_mkldnn"] = "0"
        os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
        from paddleocr import PaddleOCR
        import numpy as np

        ocr = PaddleOCR(lang="it", enable_mkldnn=False)

        if file_path.lower().endswith(".pdf"):
            from pdf2image import convert_from_path
            images = convert_from_path(file_path, dpi=200)
            pages_text = []
            for img in images:
                res = ocr.predict(np.array(img))
                page_lines = []
                for r in res:
                    page_lines.extend(r.get("rec_texts", []))
                pages_text.append("\n".join(page_lines))
            return "\n\n".join(pages_text), len(images)

        res = ocr.predict(file_path)
        page_lines = []
        for r in res:
            page_lines.extend(r.get("rec_texts", []))
        return "\n".join(page_lines), 1
    except Exception as e:
        logger.warning(f"PaddleOCR fallito ({e}), fallback a Tesseract")
        return _ocr_tesseract(file_path)


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
