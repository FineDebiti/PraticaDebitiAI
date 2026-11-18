"""
Astrazione OCR pagina-per-pagina. Tre implementazioni:
- paddleocr: 100% locale/offline (default raccomandato)
- tesseract: 100% locale/offline (fallback)
- docai: Google Document AI (opzionale)

Distingue per OGNI singola pagina del PDF tra testo nativo selezionabile e scansione immagine,
restituendo metriche reali di copertura pagine e confidenza OCR media.
"""

import logging
import os
from typing import Any, Dict, List, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

MIN_NATIVE_PAGE_CHARS = 30
MIN_READABLE_PAGE_CHARS = 10


def extract_text(file_path: str) -> Tuple[str, int]:
    """Compatibile legacy: ritorna (testo, numero_pagine)."""
    text, pages, _ = extract_text_with_meta(file_path)
    return text, pages


def extract_text_with_meta(file_path: str) -> Tuple[str, int, Dict[str, Any]]:
    """Estrae il testo distinguendo per ogni pagina testo nativo vs OCR e calcola metriche reali."""
    low = file_path.lower()
    if settings.ocr_provider == "docai":
        txt, pages = _ocr_docai(file_path)
        return txt, pages, {
            "provider": "docai",
            "total_pages": pages,
            "pages_native": 0,
            "pages_ocr": pages,
            "unreadable_pages": 0 if len((txt or "").strip()) >= MIN_READABLE_PAGE_CHARS else pages,
            "page_coverage_pct": 100.0 if pages > 0 else 0.0,
            "ocr_mean_confidence": None,
            "page_errors": [],
        }

    if not low.endswith(".pdf"):
        txt, pages, conf = _ocr_single_image(file_path)
        unreadable = 0 if len((txt or "").strip()) >= MIN_READABLE_PAGE_CHARS else 1
        return txt, pages, {
            "provider": settings.ocr_provider,
            "total_pages": pages,
            "pages_native": 0,
            "pages_ocr": 1,
            "unreadable_pages": unreadable,
            "page_coverage_pct": 100.0 if unreadable == 0 else 0.0,
            "ocr_mean_confidence": conf,
            "page_errors": [],
        }

    # PDF: ispezione pagina per pagina (gestisce correttamente anche PDF misti nativo + scansioni)
    native_pages: List[str] = []
    ocr_needed_indices: List[int] = []
    total_pages = 0
    page_errors: List[str] = []

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            for idx, page in enumerate(pdf.pages):
                try:
                    p_txt = (page.extract_text() or "").strip()
                except Exception as exc:
                    p_txt = ""
                    page_errors.append(f"pag.{idx + 1} native_err: {exc}")
                native_pages.append(p_txt)
                if len(p_txt) < MIN_NATIVE_PAGE_CHARS:
                    ocr_needed_indices.append(idx)
    except Exception as exc:
        logger.warning("pdfplumber fallito su %s (%s): passo a OCR completo", file_path, exc)
        page_errors.append(f"pdfplumber: {exc}")
        native_pages = []
        ocr_needed_indices = []
        total_pages = 0

    pages_native = 0
    pages_ocr = 0
    confs: List[float] = []
    final_pages: List[str] = []
    used_provider = "native_pdf"

    if total_pages > 0 and not ocr_needed_indices:
        final_pages = native_pages
        pages_native = total_pages
    else:
        # Esegue OCR solo sulle pagine prive di testo nativo sufficiente (o su tutto il PDF se pdfplumber non ha aperto)
        try:
            ocr_texts_by_idx, confs, ocr_prov = _ocr_pdf_pages(file_path, ocr_needed_indices if total_pages > 0 else None)
            used_provider = ocr_prov if not native_pages else f"hybrid({ocr_prov})"
        except Exception as exc:
            logger.warning("OCR PDF fallito su %s: %s", file_path, exc)
            page_errors.append(f"ocr_pdf: {exc}")
            ocr_texts_by_idx, ocr_prov = {}, settings.ocr_provider

        if total_pages == 0 and ocr_texts_by_idx:
            total_pages = max(ocr_texts_by_idx.keys()) + 1
            native_pages = [""] * total_pages

        for idx in range(total_pages):
            nat = native_pages[idx] if idx < len(native_pages) else ""
            if len(nat) >= MIN_NATIVE_PAGE_CHARS:
                final_pages.append(nat)
                pages_native += 1
            else:
                ocr_txt = (ocr_texts_by_idx.get(idx) or "").strip()
                final_pages.append(ocr_txt or nat)
                pages_ocr += 1

    unreadable_pages = sum(1 for p in final_pages if len((p or "").strip()) < MIN_READABLE_PAGE_CHARS)
    readable_pages = max(0, total_pages - unreadable_pages)
    cov_pct = round((readable_pages / total_pages) * 100.0, 1) if total_pages > 0 else 0.0
    mean_conf = round(sum(confs) / len(confs), 3) if confs else (1.0 if pages_native == total_pages and total_pages > 0 else None)

    return "\n\n".join(final_pages), total_pages, {
        "provider": used_provider,
        "total_pages": total_pages,
        "pages_native": pages_native,
        "pages_ocr": pages_ocr,
        "unreadable_pages": unreadable_pages,
        "page_coverage_pct": cov_pct,
        "ocr_mean_confidence": mean_conf,
        "page_errors": page_errors,
    }


def _ocr_pdf_pages(file_path: str, page_indices: List[int] | None) -> Tuple[Dict[int, str], List[float], str]:
    from pdf2image import convert_from_path

    texts: Dict[int, str] = {}
    confs: List[float] = []
    if page_indices is None:
        images = convert_from_path(file_path, dpi=200)
        targets = [(i, img) for i, img in enumerate(images)]
    else:
        targets = []
        for idx in page_indices:
            imgs = convert_from_path(file_path, dpi=200, first_page=idx + 1, last_page=idx + 1)
            if imgs:
                targets.append((idx, imgs[0]))

    if settings.ocr_provider != "tesseract":
        try:
            os.environ["FLAGS_use_mkldnn"] = "0"
            os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
            from paddleocr import PaddleOCR
            import numpy as np

            ocr_engine = PaddleOCR(lang="it", enable_mkldnn=False)
            for idx, img in targets:
                res = ocr_engine.predict(np.array(img))
                lines: List[str] = []
                for r in res:
                    lines.extend(r.get("rec_texts", []))
                    for sc in (r.get("rec_scores") or []):
                        if isinstance(sc, (int, float)):
                            confs.append(float(sc))
                texts[idx] = "\n".join(lines)
            return texts, confs, "paddleocr"
        except Exception as exc:
            logger.warning("PaddleOCR fallito (%s), fallback a Tesseract", exc)

    import pytesseract
    for idx, img in targets:
        texts[idx] = pytesseract.image_to_string(img, lang="ita")
    return texts, confs, "tesseract"


def _ocr_single_image(file_path: str) -> Tuple[str, int, float | None]:
    confs: List[float] = []
    if settings.ocr_provider != "tesseract":
        try:
            os.environ["FLAGS_use_mkldnn"] = "0"
            os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
            from paddleocr import PaddleOCR

            ocr_engine = PaddleOCR(lang="it", enable_mkldnn=False)
            res = ocr_engine.predict(file_path)
            lines: List[str] = []
            for r in res:
                lines.extend(r.get("rec_texts", []))
                for sc in (r.get("rec_scores") or []):
                    if isinstance(sc, (int, float)):
                        confs.append(float(sc))
            mean_c = round(sum(confs) / len(confs), 3) if confs else None
            return "\n".join(lines), 1, mean_c
        except Exception as exc:
            logger.warning("PaddleOCR immagine fallito (%s), fallback a Tesseract", exc)

    import pytesseract
    from PIL import Image
    img = Image.open(file_path)
    return pytesseract.image_to_string(img, lang="ita"), 1, None


def _try_native_pdf(file_path: str) -> Tuple[str, int]:
    """Helper retrocompatibile per estrazione testo nativo PDF."""
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


def _ocr_docai(file_path: str) -> Tuple[str, int]:
    """Google Document AI (cloud opzionale)."""
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
