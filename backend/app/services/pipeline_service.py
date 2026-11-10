"""Pipeline documentale modulare ed idempotente.

Separa le fasi di elaborazione in stati espliciti:
1. caricato: file registrato in storage e DB.
2. in_elaborazione: acquisizione testo (OCR/Parser/Multimodale).
3. analizzato: testo ed estrazione JSON salvati in DB (Extraction).
4. normalizzato: entità di dominio (Immobili, Aziende, Centrale Rischi, Bilanci, Debiti)
   mappate e salvate in DB all'interno di una transazione isolata.
5. errore: cattura selettiva delle eccezioni con tracciamento sintetico dell'errore.
"""

import time
import logging
from typing import Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.models import (
    Case, Document, Extraction, Creditor, DebtPosition, RealEstate,
    Company, CompanyMember, FinancialStatement, FinancialIndicator,
    CreditExposure, GuaranteeGiven, CreditReportSummary, Debtor,
    TaxDebtStatement, TaxDebtItem,
)
from app.services import ocr, llm
from app.services import estratto_conto_parser as ecp
from app.services import fiscal_code as fc
from app.services.case_indicators import compute_case_indicators
from app.services.indicators import compute_indicators as compute_fs_indicators
from app.config import settings

logger = logging.getLogger("dossierlex.pipeline")

MULTIMODAL_TYPES = {
    "visura_catastale", "visura_camerale", "centrale_rischi", "bilancio",
    "dichiarazione_redditi", "busta_paga"
}


def process_document_pipeline(db: Session, document_id: str) -> Document:
    """Esegue l'intera pipeline di elaborazione per un documento."""
    t0 = time.time()
    doc = db.get(Document, document_id)
    if not doc:
        logger.warning("Documento %s non trovato in DB.", document_id)
        return None

    # Step 1: aggiorna stato a in_elaborazione
    doc.status = "in_elaborazione"
    doc.error = ""
    db.commit()

    try:
        case = db.get(Case, doc.case_id)
        client_cf = case.client_tax_code if case else ""

        # Step 2: Estrazione testo / OCR
        text, pages = ocr.extract_text(doc.storage_path)

        # Step 3: Classificazione tipo documento se non forzato
        forced = doc.doc_type and doc.doc_type != "da_classificare"
        if forced:
            doc_type, conf = doc.doc_type, 1.0
        else:
            cls = llm.classify(text)
            doc_type, conf = cls.get("doc_type", "da_classificare"), float(cls.get("confidence", 0.0))

        # Step 4: Estrazione strutturata dei dati
        data = _extract_structured_data(doc.storage_path, text, doc_type, client_cf)
        data = _unwrap_confidence(data)

        # Aggiorna metadati documento e salva Extraction (stato -> analizzato)
        doc.doc_type = doc_type
        doc.classification_confidence = conf
        doc.num_pages = pages

        # Pulizia estrazioni precedenti per idempotenza su re-processing
        for old_ext in db.query(Extraction).filter_by(document_id=doc.id).all():
            db.delete(old_ext)
        db.flush()

        ext = Extraction(
            document_id=doc.id,
            ocr_provider=settings.ocr_provider,
            llm_provider=settings.llm_provider,
            raw_text=text[:20000],
            json_output=data,
            duration_ms=int((time.time() - t0) * 1000),
        )
        db.add(ext)
        doc.status = "analizzato"
        db.commit()

        # Step 5: Normalizzazione e persistenza entità di dominio
        _normalize_and_save_entities(db, doc, data, client_cf)
        compute_case_indicators(db, doc.case_id)

        doc.status = "normalizzato"
        doc.error = ""
        db.commit()
        db.refresh(doc)
        return doc

    except Exception as e:
        db.rollback()
        logger.exception("Errore nella pipeline documentale per doc %s: %s", document_id, e)
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "errore"
            doc.error = str(e)[:500]
            db.commit()
        raise


def _extract_structured_data(storage_path: str, text: str, doc_type: str, client_cf: str) -> Dict[str, Any]:
    """Esegue l'estrazione dai dati usando il parser deterministico o LLM in base al tipo."""
    res = {}
    if doc_type == "cartella_aer":
        try:
            from app.services import aer_parser
            res = aer_parser.parse_pdf(storage_path)
            res["_extraction_method"] = "parser"
        except Exception as e:
            logger.info("[cartella_aer] Parser deterministico non applicabile (%s) -> fallback LLM", e)
            res = llm.extract(text, doc_type, client_cf)
            res["_extraction_method"] = "ai"

    elif doc_type == "estratto_conto":
        try:
            res = ecp.parse_pdf(storage_path)
        except ecp.EstrattoContoParseError as e:
            logger.info("[estratto_conto] Parser tabellare fallito (%s) -> fallback LLM", e)
            res = llm.extract(text, doc_type, client_cf)
            if not res.get("aggregazioni"):
                mov = []
                for m in (res.get("movimenti") or []):
                    d = m.get("data")
                    if d:
                        mov.append({
                            "data": d,
                            "dare": abs(_num(m.get("dare"))),
                            "avere": abs(_num(m.get("avere"))),
                        })
                if mov:
                    res["aggregazioni"] = ecp._aggregate(mov, res.get("saldo_finale"))

    elif doc_type in MULTIMODAL_TYPES and settings.llm_provider == "gemini":
        res = llm.extract_from_file(storage_path, doc_type, client_cf)
    else:
        res = llm.extract(text, doc_type, client_cf)

    # Se LLM ha restituito stub o nessun dato di dominio, applica l'estrazione deterministica da testo OCR
    if not res or res.get("document_type") == "stub" or not any(k in res for k in ("immobili", "impresa", "esposizione_attuale", "stato_patrimoniale", "credit_positions", "reddito_annuo")):
        det = _parse_ocr_text_deterministic(text, doc_type, client_cf)
        if det:
            res.update(det)

    return res


def _parse_ocr_text_deterministic(text: str, doc_type: str, client_cf: str) -> Dict[str, Any]:
    import re
    out = {"document_type": doc_type}
    text_lower = text.lower()

    if doc_type in ("dichiarazione_redditi", "cu", "busta_paga"):
        m_inc = re.search(r'(?:reddito\s+complessivo|totale\s+redditi|imponibile|netto\s+annuo)[^\d]*([\d\.,]+)', text, re.I)
        if m_inc:
            val_str = m_inc.group(1).replace(".", "").replace(",", ".")
            try:
                ann = float(val_str)
                out["reddito_annuo"] = ann
                out["reddito_mensile"] = round(ann / 12.0, 2)
            except ValueError:
                pass

    elif doc_type == "visura_catastale":
        immobili = []
        for m in re.finditer(r'(?:foglio|fg\.?)\s*(\d+).*?(?:particella|part\.?|mappale|p\.lla)\s*(\d+|[A-Z0-9]+)', text, re.I):
            immobili.append({
                "indirizzo": "",
                "foglio": m.group(1),
                "particella": m.group(2),
                "subalterno": "",
                "categoria": "",
                "rendita_catastale": 0.0,
                "superficie_mq": 0.0,
                "quota_soggetto": "100%",
                "diritto_soggetto": "Proprietà"
            })
        out["immobili"] = immobili

    elif doc_type == "centrale_rischi":
        m_acc = re.search(r'(?:totale\s+accordato|accordato)[^\d]*([\d\.,]+)', text, re.I)
        m_ut = re.search(r'(?:totale\s+utilizzato|utilizzato)[^\d]*([\d\.,]+)', text, re.I)
        m_soff = re.search(r'sofferenze[^\d]*([\d\.,]+)', text, re.I)
        m_int = re.search(r'(?:numero\s+intermediari|intermediari|segnalanti)[^\d]*(\d+)', text, re.I)

        def _pnum_simple(match):
            if not match:
                return 0.0
            try:
                return float(match.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                return 0.0

        accordato = _pnum_simple(m_acc)
        utilizzato = _pnum_simple(m_ut)
        sofferenze = _pnum_simple(m_soff)
        num_int = int(m_int.group(1)) if m_int else (1 if (accordato or utilizzato) else 0)

        out["totali"] = {
            "numero_intermediari": num_int,
            "esposizione_totale_utilizzata": utilizzato,
            "totale_garanzie_prestate": 0.0,
            "presenza_sofferenze": sofferenze > 0,
            "presenza_criticita": sofferenze > 0,
        }
        if accordato or utilizzato or sofferenze:
            out["esposizione_attuale"] = [{
                "intermediario": "Sintesi da prospetto CR",
                "categoria": "sofferenze" if sofferenze > 0 else "esposizione_complessiva",
                "accordato": accordato,
                "utilizzato": utilizzato,
                "importo_garantito": 0.0,
                "stato_rapporto": "sofferenza" if sofferenze > 0 else "regolare",
                "e_critico": sofferenze > 0,
                "confidence": 0.7,
            }]
        else:
            out["esposizione_attuale"] = []

    elif doc_type == "visura_camerale":
        piva_match = re.search(r'(?:partita\s+iva|p\.?\s*i\.?|p\.?\s*iva)[^\d]*(\d{11})', text, re.I)
        cf_match = re.search(r'(?:codice\s+fiscale|c\.?\s*f\.?)[^\d]*([a-z0-9]{11,16})', text, re.I)
        rea_match = re.search(r'(?:n\.?\s*rea|rea)[^\d]*([A-Z]{2}\s*\d+|\d+)', text, re.I)
        denom_match = re.search(r'(?:denominazione|ragione\s+sociale)[^\w\n]*([A-Z0-9\s\.\'\,\-]+(?:S\.?R\.?L\.?|S\.?P\.?A\.?|S\.?N\.?C\.?|S\.?A\.?S\.?|SOCIET[AÀ]))', text, re.I)
        sede_match = re.search(r'(?:sede\s+legale|sede\s+in)[^\w\n]*([^\n]+)', text, re.I)
        cap_match = re.search(r'(?:capitale\s+sociale|capitale\s+conferimenti)[^\d]*([\d\.,]+)', text, re.I)

        def _pnum_simple2(match):
            if not match:
                return 0.0
            try:
                return float(match.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                return 0.0

        piva = piva_match.group(1) if piva_match else ""
        cf = cf_match.group(1).upper() if cf_match else piva
        denom = denom_match.group(1).strip() if denom_match else ""
        sede = sede_match.group(1).strip() if sede_match else ""
        cap = _pnum_simple2(cap_match)

        if denom or piva or cf:
            out["impresa"] = {
                "denominazione": denom or "Impresa",
                "forma_giuridica": "S.R.L." if "s.r.l" in text_lower else "",
                "tipo_societa": "capitale",
                "codice_fiscale": cf or client_cf,
                "partita_iva": piva,
                "numero_rea": rea_match.group(1).strip() if rea_match else "",
                "cciaa": "",
                "sede_legale": sede,
                "stato_attivita": "ATTIVA",
                "capitale_conferimenti": cap
            }
            out["soci"] = []

    elif doc_type == "bilancio":
        m_anno = re.search(r'(?:31-12-|esercizio\s+)(202\d)', text, re.I)
        anno = int(m_anno.group(1)) if m_anno else 2024
        out["doc_type"] = "bilancio"

        piva_match = re.search(r'(?:partita\s+iva|p\.?\s*i\.?|p\.?\s*iva)[^\d]*(\d{11})', text, re.I)
        cf_match = re.search(r'(?:codice\s+fiscale|c\.?\s*f\.?)[^\d]*([a-z0-9]{11,16})', text, re.I)
        ateco_match = re.search(r'ateco[^\d]*(\d{6})', text, re.I)
        denom_match = re.search(r'([A-Z0-9\s\.\'\,\-]+(?:S\.?R\.?L\.?|S\.?P\.?A\.?|S\.?N\.?C\.?|S\.?A\.?S\.?))', text[:400], re.I)

        piva = piva_match.group(1) if piva_match else ""
        cf = cf_match.group(1).upper() if cf_match else piva
        denom = denom_match.group(1).strip() if denom_match else ""
        ateco = ateco_match.group(1) if ateco_match else ""

        out["azienda"] = {
            "denominazione": denom,
            "partita_iva": piva,
            "codice_fiscale": cf,
            "forma_giuridica": "",
            "ateco": ateco,
            "sede": "",
            "capitale_sociale": 0.0,
        }
        # Data chiusura: controlla prima "SITUAZIONE ECONOMICA DAL ... AL GG/MM/AAAA"
        sit_m = re.search(r'SITUAZIONE\s+ECONOMICA\s+DAL\s+[\d/]+\s+AL\s+(\d{2})/(\d{2})/(\d{4})', text, re.I)
        if sit_m:
            data_chiusura = f"{sit_m.group(3)}-{sit_m.group(2)}-{sit_m.group(1)}"
        else:
            data_chiusura = f"{anno}-12-31"

        out["esercizio"] = {
            "data_chiusura": data_chiusura,
            "tipo": "abbreviato" if "abbreviato" in text_lower else "ordinario"
        }

        def _pnum(s: str) -> float:
            if not s or s.strip() in ("-", "—"):
                return 0.0
            s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return 0.0

        def _extract_pair(pat: str):
            m = re.search(pat, text, re.I)
            if m:
                c = _pnum(m.group(1))
                p = _pnum(m.group(2)) if len(m.groups()) >= 2 and m.group(2) else 0.0
                return {"corrente": c, "precedente": p}
            return None

        tot_att = _extract_pair(r'Totale\s+attivo\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        tot_imm = _extract_pair(r'Totale\s+immobilizzazioni\s*(?:\(B\))?\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        tot_cir = _extract_pair(r'Totale\s+attivo\s+circolante\s*(?:\(C\))?\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        disp_l = _extract_pair(r'Disponibilit[àa]\s+liquide\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        pn = _extract_pair(r'Totale\s+patrimonio\s+netto\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        tot_d = _extract_pair(r'Totale\s+debiti\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        deb_e = _extract_pair(r'esigibili\s+entro\s+l[\'\’]esercizio\s+successivo\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        deb_o = _extract_pair(r'esigibili\s+oltre\s+l[\'\’]esercizio\s+successivo\s+([\d\.,]+)(?:\s+([\d\.,]+))?')

        # Ricavi e Costi (standard CEE e mastrino contabile)
        ric_v = _extract_pair(r'ricavi\s+delle\s+vendite\s+e\s+delle\s+prestazioni\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        val_p = _extract_pair(r'Totale\s+valore\s+della\s+produzione\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        tot_ric = _extract_pair(r'TOTALE\s+RICAVI\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        tot_cos = _extract_pair(r'TOTALE\s+COSTI\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        amm_alt = _extract_pair(r'AMMORTAMENTI\s+E\s+SVALUTAZIONI\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        on_fin_alt = _extract_pair(r'ONERI\s+FINANZIARI\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        dif_vc = _extract_pair(r'Differenza\s+tra\s+valore\s+e\s+costi\s+della\s+produzione[^\d]*([\d\.,]+)(?:\s+([\d\.,]+))?')
        ut_per = _extract_pair(r'21\)\s*Utile\s+\(perdita\)\s+dell[\'\’]esercizio\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        on_fin = _extract_pair(r'Totale\s+interessi\s+e\s+altri\s+oneri\s+finanziari\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        ut_alt = _extract_pair(r'(?:^|\n)\s*UTILE\s+([\d\.,]+)(?:\s+([\d\.,]+))?')
        per_alt = _extract_pair(r'(?:^|\n)\s*PERDITA\s+([\d\.,]+)(?:\s+([\d\.,]+))?')

        final_val_p = val_p or tot_ric or {"corrente": 0.0, "precedente": 0.0}
        final_ric_v = ric_v or final_val_p
        final_costi_p = tot_cos or {"corrente": 0.0, "precedente": 0.0}
        final_amm = amm_alt or {"corrente": 0.0, "precedente": 0.0}
        final_on_fin = on_fin or on_fin_alt or {"corrente": 0.0, "precedente": 0.0}

        if per_alt and per_alt.get("corrente", 0.0) > 0:
            final_ut = {"corrente": -abs(per_alt["corrente"]), "precedente": -abs(per_alt.get("precedente", 0.0))}
        elif ut_per:
            final_ut = ut_per
        elif ut_alt:
            final_ut = ut_alt
        elif final_val_p.get("corrente", 0.0) or final_costi_p.get("corrente", 0.0):
            diff = final_val_p.get("corrente", 0.0) - final_costi_p.get("corrente", 0.0)
            final_ut = {"corrente": round(diff, 2), "precedente": 0.0}
        else:
            final_ut = {"corrente": 0.0, "precedente": 0.0}

        final_dif_vc = dif_vc or {
            "corrente": round(final_val_p.get("corrente", 0.0) - final_costi_p.get("corrente", 0.0), 2),
            "precedente": round(final_val_p.get("precedente", 0.0) - final_costi_p.get("precedente", 0.0), 2),
        }

        out["stato_patrimoniale"] = {
            "totale_attivo": tot_att or {"corrente": 0.0, "precedente": 0.0},
            "totale_immobilizzazioni": tot_imm or {"corrente": 0.0, "precedente": 0.0},
            "totale_attivo_circolante": tot_cir or {"corrente": 0.0, "precedente": 0.0},
            "disponibilita_liquide": disp_l or {"corrente": 0.0, "precedente": 0.0},
            "rimanenze": {"corrente": 0.0, "precedente": 0.0},
            "patrimonio_netto": pn or {"corrente": 0.0, "precedente": 0.0},
            "debiti_totali": tot_d or {"corrente": 0.0, "precedente": 0.0},
            "debiti_entro": deb_e or {"corrente": 0.0, "precedente": 0.0},
            "debiti_oltre": deb_o or {"corrente": 0.0, "precedente": 0.0},
        }
        out["conto_economico"] = {
            "ricavi_vendite": final_ric_v,
            "valore_produzione": final_val_p,
            "costi_produzione": final_costi_p,
            "ammortamenti": final_amm,
            "differenza_valore_costi": final_dif_vc,
            "oneri_finanziari": final_on_fin,
            "utile_perdita": final_ut,
        }
        out["debiti_per_natura"] = {
            "tributari": {"importo": 0.0, "entro": 0.0, "oltre": 0.0, "di_cui_privilegi": 0.0},
            "previdenziali": {"importo": 0.0, "entro": 0.0, "oltre": 0.0, "di_cui_privilegi": 0.0},
            "banche": {"importo": 0.0, "entro": 0.0, "oltre": 0.0, "di_cui_ipoteche": 0.0},
            "fornitori": {"importo": 0.0, "entro": 0.0, "oltre": 0.0},
        }

    elif doc_type == "cartella_aer":
        out["credit_positions"] = []

    return out


def _unwrap_confidence(obj: Any) -> Any:
    """Srotola oggetti incapsulati col pattern {value, confidence, page}."""
    _wrap_keys = {"value", "confidence", "page", "source_page", "conf", "pagina"}
    if isinstance(obj, dict):
        if "value" in obj and set(obj.keys()) <= _wrap_keys:
            return _unwrap_confidence(obj["value"])
        return {k: _unwrap_confidence(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unwrap_confidence(x) for x in obj]
    return obj


def _num(v: Any) -> float:
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _normalize_and_save_entities(db: Session, doc: Document, data: Dict[str, Any], client_cf: str) -> None:
    """Mappa i dati strutturati estratto nelle relative tabelle di dominio."""
    if not isinstance(data, dict):
        return

    # 1. Immobili (da Visura Catastale)
    imm_raw = data.get("immobili")
    imm_list = imm_raw if isinstance(imm_raw, list) else []
    for imm in imm_list:
        if not isinstance(imm, dict):
            continue
        rendita = _num(imm.get("rendita_catastale"))
        quota = imm.get("quota_soggetto") or ""
        cat = imm.get("categoria") or ""
        db.add(RealEstate(
            case_id=doc.case_id,
            kind=_imm_kind(imm),
            address=imm.get("indirizzo") or "",
            cadastral_data=_cadastral(imm),
            ownership_share=quota,
            ownership_right=imm.get("diritto_soggetto") or "",
            surface_mq=_num(imm.get("superficie_mq")),
            cadastral_income=rendita,
            cadastral_value=_valore_catastale(rendita, cat, quota),
            category=cat,
            commercial_value=0.0,
            other_owners=_altri_intestatari(imm),
            provenance=imm.get("provenienza") or "",
            notes=_imm_notes(imm),
            source="documento",
        ))

    # 2. Impresa e Soci (da Visura Camerale)
    if data.get("impresa"):
        _save_company(db, doc, data, client_cf)

    # 3. Centrale Rischi
    if data.get("document_type") == "centrale_rischi" or data.get("esposizione_attuale"):
        _save_credit_report(db, doc, data)

    # 4. Bilancio
    if data.get("doc_type") == "bilancio" or data.get("stato_patrimoniale"):
        _save_financial_statement(db, doc, data, client_cf)

    # 5. Documenti reddituali
    if doc.doc_type in ("busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi"):
        _apply_income_to_debtor(db, doc.case_id, doc.doc_type, data)

    # 6. Posizioni debitorie
    pos_raw = data.get("credit_positions")
    pos_list = pos_raw if isinstance(pos_raw, list) else []
    for pos in pos_list:
        if not isinstance(pos, dict):
            continue
        name = (pos.get("creditor") or "").strip()
        if name and not db.query(Creditor).filter_by(case_id=doc.case_id, name=name).first():
            db.add(Creditor(case_id=doc.case_id, name=name, source_document_id=doc.id))
        db.add(DebtPosition(
            case_id=doc.case_id,
            creditor_name=name,
            debt_type=pos.get("debt_type") or "",
            original_amount=_num(pos.get("original_amount")),
            residual_amount=_num(pos.get("residual_amount")),
            overdue_amount=_num(pos.get("overdue_amount")),
            monthly_installment=_num(pos.get("monthly_installment")),
            status=pos.get("status") or "",
            confidence=_num(pos.get("confidence")),
            source_document_id=doc.id,
            source_page=int(pos.get("source_page") or 0),
        ))

    # 7. Cartella AER / Estratto di Ruolo
    if doc.doc_type == "cartella_aer" or "righe" in data or "totale_residuo" in str(data):
        _save_tax_debt_statement(db, doc, data, client_cf)


def _save_tax_debt_statement(db: Session, doc: Document, data: Dict[str, Any], client_cf: str) -> None:
    """Salva la situazione debitoria AdER estratta da cartella_aer."""
    existing = db.query(TaxDebtStatement).filter_by(source_document_id=doc.id).first()
    if existing:
        return

    from app.services import aer_parser

    debtor = db.query(Debtor).filter_by(case_id=doc.case_id).first()
    debtor_id = debtor.id if debtor else None
    owner_cf = debtor.tax_code if debtor else client_cf

    intest = data.get("intestatario") or {}
    doc_cf = intest.get("codice_fiscale") or ""
    cf_mismatch = bool(doc_cf and owner_cf and not fc.same(doc_cf, owner_cf))

    agg = data.get("aggregazioni") or {}
    totali = data.get("totali") or {}
    righe = data.get("righe") or []

    tot_res = _num(totali.get("totale_residuo"))
    tot_carico = _num(totali.get("carico_affidato"))
    if tot_res == 0.0 and righe:
        tot_res = sum(_num(r.get("residuo")) for r in righe)
    if tot_carico == 0.0 and righe:
        tot_carico = sum(_num(r.get("carico_affidato")) for r in righe)

    # Non creare statement se non ci sono importi né righe
    if tot_res == 0.0 and tot_carico == 0.0 and not righe:
        return

    stmt = TaxDebtStatement(
        case_id=doc.case_id,
        owner_kind="person",
        debtor_id=debtor_id,
        company_id=None,
        codice_fiscale=doc_cf or owner_cf,
        denominazione=intest.get("denominazione") or "",
        data_elaborazione=data.get("data_elaborazione") or "",
        total_residuo=tot_res,
        total_residuo_netto=_num(totali.get("totale_residuo_netto")) or tot_res,
        total_carico_affidato=tot_carico,
        count_proc_attive=int(agg.get("count_proc_attive") or sum(1 for r in righe if r.get("proc_attive"))),
        quadrature_ok=bool(data.get("quadrature_ok")),
        extraction_method=data.get("_extraction_method", "parser"),
        cf_mismatch=cf_mismatch,
        raw_extraction=data,
        source_document_id=doc.id,
    )
    db.add(stmt)
    db.flush()

    for r in righe:
        db.add(TaxDebtItem(
            statement_id=stmt.id,
            numero_documento=r.get("numero_documento") or "",
            tipo_documento=r.get("tipo_documento") or "",
            ente_creditore=r.get("ente_creditore") or "",
            ente_categoria=r.get("ente_categoria") or aer_parser.ente_categoria(r.get("ente_creditore") or ""),
            data_notifica=r.get("data_notifica") or "",
            carico_affidato=_num(r.get("carico_affidato")),
            sgravio=_num(r.get("sgravio")),
            gia_pagato=_num(r.get("gia_pagato")),
            stralcio=_num(r.get("stralcio_def_agevolata") or r.get("stralcio")),
            residuo_carico=_num(r.get("residuo_carico")),
            interessi_mora=_num(r.get("interessi_mora")),
            oneri_diritti=_num(r.get("oneri_diritti")),
            totale_residuo=_num(r.get("totale_residuo")),
            importo_sospeso=_num(r.get("importo_sospeso")),
            totale_residuo_netto=_num(r.get("totale_residuo_netto") or r.get("totale_residuo")),
            rateizzato=bool(r.get("rateizzato") or r.get("rateazione_attiva")),
            proc_attive=bool(r.get("proc_attive")),
            def_agevolata=bool(r.get("def_agevolata")),
            needs_review=bool(r.get("needs_review")),
        ))
    logger.info("TaxDebtStatement salvato per doc %s: totale residuo=€ %.2f (%d righe)", doc.original_filename, tot_res, len(righe))



def _save_company(db: Session, doc: Document, data: Dict[str, Any], client_cf: str) -> None:
    imp = data.get("impresa") if isinstance(data.get("impresa"), dict) else {}
    soci_raw = data.get("soci")
    soci = [s for s in soci_raw if isinstance(s, dict)] if isinstance(soci_raw, list) else []

    for s in soci:
        s["e_cliente"] = bool(s.get("e_cliente")) or fc.same(s.get("codice_fiscale", ""), client_cf)

    has_client = any(s.get("e_cliente") for s in soci) or fc.same(imp.get("codice_fiscale", ""), client_cf)
    company = Company(
        case_id=doc.case_id,
        role="cliente" if has_client else "controparte",
        name=imp.get("denominazione") or "",
        legal_form=imp.get("forma_giuridica") or "",
        company_type=imp.get("tipo_societa") or "",
        tax_code=imp.get("codice_fiscale") or "",
        vat=imp.get("partita_iva") or "",
        rea=imp.get("numero_rea") or "",
        cciaa=imp.get("cciaa") or "",
        pec=imp.get("pec") or "",
        legal_address=imp.get("sede_legale") or "",
        status=imp.get("stato_attivita") or "",
        constitution_date=imp.get("data_costituzione") or "",
        capital=_num(imp.get("capitale_conferimenti")),
        business_summary=imp.get("oggetto_sociale_sintesi") or "",
        extra=data.get("dati_secondari") if isinstance(data.get("dati_secondari"), dict) else {},
        source_document_id=doc.id,
    )
    db.add(company)
    db.flush()
    for s in soci:
        db.add(CompanyMember(
            company_id=company.id,
            name=s.get("denominazione") or "",
            tax_code=s.get("codice_fiscale") or "",
            is_client=bool(s.get("e_cliente")),
            roles=", ".join(s.get("cariche", []) or []) if isinstance(s.get("cariche"), list) else "",
            is_legal_rep=bool(s.get("rappresentante_legale")),
            quota_value=_num(s.get("quota_valore")),
            quota_percent=_num(s.get("quota_percentuale")),
        ))


def _save_credit_report(db: Session, doc: Document, data: Dict[str, Any]) -> None:
    rec = str(data.get("data_riferimento_piu_recente") or "")

    # Normalizzazione difensiva di esposizione_attuale (supporta list di dict, list di str, o dict di totali/intermediari)
    esp_raw = data.get("esposizione_attuale")
    esp_list = []
    if isinstance(esp_raw, list):
        for e in esp_raw:
            if isinstance(e, dict):
                esp_list.append(e)
            elif isinstance(e, str) and e.strip():
                esp_list.append({"intermediario": e.strip()})
    elif isinstance(esp_raw, dict):
        has_subdicts = any(isinstance(v, dict) for v in esp_raw.values())
        if has_subdicts:
            for k, v in esp_raw.items():
                if isinstance(v, dict):
                    row = dict(v)
                    row.setdefault("intermediario", k)
                    esp_list.append(row)
        else:
            tot_acc = _num(esp_raw.get("totale_accordato") or esp_raw.get("accordato"))
            tot_ut = _num(esp_raw.get("totale_utilizzato") or esp_raw.get("utilizzato"))
            soff = _num(esp_raw.get("sofferenze"))
            if tot_acc or tot_ut or soff:
                esp_list.append({
                    "intermediario": "Sintesi da prospetto CR",
                    "categoria": "sofferenze" if soff > 0 else "esposizione_complessiva",
                    "accordato": tot_acc,
                    "utilizzato": tot_ut,
                    "stato_rapporto": "sofferenza" if soff > 0 else "regolare",
                    "e_critico": soff > 0,
                })

    for e in esp_list:
        if not isinstance(e, dict):
            continue
        db.add(CreditExposure(
            case_id=doc.case_id,
            intermediary=str(e.get("intermediario") or ""),
            category=str(e.get("categoria") or ""),
            accordato=_num(e.get("accordato")),
            utilizzato=_num(e.get("utilizzato")),
            importo_garantito=_num(e.get("importo_garantito")),
            status=str(e.get("stato_rapporto") or ""),
            is_critical=bool(e.get("e_critico")),
            reference_month=rec,
            source_document_id=doc.id,
        ))

    # Normalizzazione difensiva di garanzie_prestate
    gar_raw = data.get("garanzie_prestate")
    gar_list = []
    if isinstance(gar_raw, list):
        for g in gar_raw:
            if isinstance(g, dict):
                gar_list.append(g)
            elif isinstance(g, str) and g.strip():
                gar_list.append({"intermediario": g.strip()})
    elif isinstance(gar_raw, dict):
        for k, v in gar_raw.items():
            if isinstance(v, dict):
                row = dict(v)
                row.setdefault("intermediario", k)
                gar_list.append(row)

    for g in gar_list:
        if not isinstance(g, dict):
            continue
        db.add(GuaranteeGiven(
            case_id=doc.case_id,
            intermediary=str(g.get("intermediario") or ""),
            guaranteed_subject=str(g.get("soggetto_garantito") or ""),
            valore_garanzia=_num(g.get("valore_garanzia")),
            importo_garantito=_num(g.get("importo_garantito")),
            status=str(g.get("stato") or ""),
            source_document_id=doc.id,
        ))

    tot = data.get("totali") if isinstance(data.get("totali"), dict) else {}
    periodo = data.get("periodo") if isinstance(data.get("periodo"), dict) else {}
    cc = data.get("_crosscheck") if isinstance(data.get("_crosscheck"), dict) else {}
    crit_raw = data.get("criticita")
    crit_list = crit_raw if isinstance(crit_raw, list) else []

    db.add(CreditReportSummary(
        case_id=doc.case_id,
        period_from=str(periodo.get("da") or ""),
        period_to=str(periodo.get("a") or ""),
        most_recent_month=rec,
        num_intermediaries=int(tot.get("numero_intermediari") or len(esp_list)),
        total_exposure=_num(tot.get("esposizione_totale_utilizzata")) or sum(_num(x.get("utilizzato")) for x in esp_list),
        total_guarantees=_num(tot.get("totale_garanzie_prestate")) or sum(_num(x.get("importo_garantito")) for x in gar_list),
        has_sofferenze=bool(tot.get("presenza_sofferenze")) or any(bool(x.get("e_critico")) or "sofferenza" in str(x.get("categoria", "")).lower() for x in esp_list),
        has_criticita=bool(tot.get("presenza_criticita")) or bool(crit_list),
        criticita=crit_list,
        source_document_id=doc.id,
        llm_provider=str(data.get("_llm_provider") or ""),
        llm_model=str(data.get("_llm_model") or ""),
        crosscheck_status=str(cc.get("status") or ""),
        crosscheck_payload=cc if isinstance(cc, dict) else {},
    ))


def _save_financial_statement(db: Session, doc: Document, data: Dict[str, Any], client_cf: str) -> None:
    az = data.get("azienda") if isinstance(data.get("azienda"), dict) else {}
    sp = data.get("stato_patrimoniale") if isinstance(data.get("stato_patrimoniale"), dict) else {}
    ce = data.get("conto_economico") if isinstance(data.get("conto_economico"), dict) else {}
    deb = data.get("debiti_per_natura") if isinstance(data.get("debiti_per_natura"), dict) else {}
    piva = az.get("partita_iva") or ""
    cf = az.get("codice_fiscale") or ""
    ateco = az.get("ateco") or ""

    company = None
    for c in db.query(Company).filter_by(case_id=doc.case_id).all():
        if (piva and fc.same(c.vat, piva)) or (cf and fc.same(c.tax_code, cf)):
            company = c
            break
    if not company:
        existing = db.query(Company).filter_by(case_id=doc.case_id).all()
        for c in existing:
            if c.role == "cliente" or (az.get("denominazione") and c.name and az["denominazione"].lower() in c.name.lower()):
                company = c
                break
        if not company and existing:
            company = existing[0]

    if not company:
        is_client = fc.same(cf, client_cf) or fc.same(piva, client_cf)
        company = Company(
            case_id=doc.case_id, role="cliente" if is_client else "controparte",
            name=az.get("denominazione") or "Azienda", vat=piva, tax_code=cf, ateco=ateco,
            legal_form=az.get("forma_giuridica") or "", legal_address=az.get("sede") or "",
            capital=_num(az.get("capitale_sociale")), source_document_id=doc.id,
        )
        db.add(company)
        db.flush()
    elif ateco and not company.ateco:
        company.ateco = ateco

    def _num_or_sub(obj, key="importo"):
        if isinstance(obj, dict):
            return _num(obj.get(key) if obj.get(key) is not None else obj.get("valore"))
        return _num(obj)

    priv = _num_or_sub(deb.get("tributari")) + _num_or_sub(deb.get("previdenziali"))
    cc = data.get("_crosscheck") if isinstance(data.get("_crosscheck"), dict) else {}

    stmt = db.query(FinancialStatement).filter_by(source_document_id=doc.id).first()
    if not stmt:
        stmt = FinancialStatement(
            company_id=company.id, case_id=doc.case_id,
            source_document_id=doc.id,
        )
        db.add(stmt)

    stmt.company_id = company.id
    stmt.case_id = doc.case_id
    es_dict = data.get("esercizio") if isinstance(data.get("esercizio"), dict) else {}
    raw_date = str(es_dict.get("data_chiusura") or stmt.fiscal_year_end or "").strip()
    if "/" in raw_date:
        dp = raw_date.split("/")
        if len(dp) == 3:
            if len(dp[2]) == 4:
                raw_date = f"{dp[2]}-{dp[1].zfill(2)}-{dp[0].zfill(2)}"
            elif len(dp[0]) == 4:
                raw_date = f"{dp[0]}-{dp[1].zfill(2)}-{dp[2].zfill(2)}"
    stmt.fiscal_year_end = raw_date
    stmt.statement_type = es_dict.get("tipo") or stmt.statement_type or "abbreviato"
    stmt.ateco = ateco or company.ateco or ""
    stmt.raw_extraction = data
    stmt.total_assets = _cur(sp, "totale_attivo")
    stmt.equity = _cur(sp, "patrimonio_netto")
    stmt.total_debts = _cur(sp, "debiti_totali")
    stmt.revenues = _cur(ce, "ricavi_vendite")
    stmt.net_result = _cur(ce, "utile_perdita")
    stmt.debts_secured = bool(data.get("debiti_assistiti_garanzie_reali"))
    stmt.privileged_debts = priv
    stmt.llm_provider = data.get("_llm_provider") or "stub"
    stmt.llm_model = data.get("_llm_model") or ""
    stmt.crosscheck_status = cc.get("status") or ""
    stmt.crosscheck_payload = cc if cc else {}

    # Aggiorna sintesi azienda con ultimo bilancio disponibile
    year_str = stmt.fiscal_year_end[-4:] if len(stmt.fiscal_year_end) >= 4 else ""
    if year_str and (not company.anno_bilancio or year_str >= company.anno_bilancio):
        company.anno_bilancio = year_str
        if stmt.revenues:
            company.fatturato = stmt.revenues
        if stmt.equity:
            company.patrimonio_netto = stmt.equity
    if stmt.ateco and not company.ateco:
        company.ateco = stmt.ateco

    db.flush()
    db.query(FinancialIndicator).filter_by(statement_id=stmt.id).delete()
    for ind in compute_fs_indicators(sp, ce, deb, stmt.ateco):
        db.add(FinancialIndicator(statement_id=stmt.id, **ind))


def _apply_income_to_debtor(db: Session, case_id: str, doc_type: str, data: Dict[str, Any]) -> None:
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    if not debtor:
        return

    ann = _num(data.get("reddito_annuo")) or _num(data.get("reddito_complessivo"))
    mens = _num(data.get("reddito_mensile")) or (round(ann / 12.0, 2) if ann else 0.0)
    if ann:
        debtor.annual_income = ann
    if mens:
        debtor.monthly_net_income = mens

    if doc_type == "busta_paga":
        netto = _num(data.get("retribuzione_netta"))
        datore = data.get("datore_lavoro") or ""
        if datore and not debtor.employer:
            debtor.employer = datore
        periodo = data.get("periodo") or ""
        _set_income_note(debtor, "[Busta paga]",
                         f"netto {_eur(netto)}/mese" + (f" · {periodo}" if periodo else "")
                         + (f" · {datore}" if datore else ""))

    elif doc_type == "cu":
        annuo = _num(data.get("reddito_complessivo"))
        anno = data.get("anno") or ""
        _set_income_note(debtor, "[CU]",
                         f"reddito complessivo {_eur(annuo)}" + (f" · anno {anno}" if anno else ""))

    elif doc_type == "isee":
        isee = _num(data.get("isee_ordinario"))
        anno = data.get("anno") or ""
        scad = data.get("scadenza") or ""
        nucleo = data.get("componenti_nucleo")
        nota = f"ISEE {_eur(isee)}"
        if anno:
            nota += f" · anno {anno}"
        if nucleo:
            nota += f" · nucleo {int(_num(nucleo))}"
        if scad:
            nota += f" · scad. {scad}"
        _set_income_note(debtor, "[ISEE]", nota)

    elif doc_type == "estratto_conto":
        agg = data.get("aggregazioni") or {}
        entrate = _num(agg.get("entrate_medie_mensili"))
        uscite = _num(agg.get("uscite_medie_mensili"))
        _set_income_note(debtor, "[Estratto conto]",
                         f"entrate medie {_eur(entrate)}/mese · uscite {_eur(uscite)}/mese")

    elif doc_type == "dichiarazione_redditi":
        rn = data.get("riepilogo_RN") if isinstance(data.get("riepilogo_RN"), dict) else {}
        quadri = data.get("quadri") if isinstance(data.get("quadri"), dict) else {}
        annual = _num(rn.get("reddito_complessivo"))
        fonti = []
        for key, label, amount_key in [
            ("RB_fabbricati", "affitti", "canoni_percepiti"),
            ("RE_lavoro_autonomo", "lavoro autonomo", "reddito"),
            ("RF_RG_impresa", "impresa", "reddito"),
            ("RH_partecipazioni", "partecipazioni", "reddito"),
            ("RC_lavoro_dipendente", "lavoro dipendente", "reddito"),
            ("RA_terreni", "terreni", "reddito"),
            ("RL_altri_redditi", "altri redditi", "reddito"),
        ]:
            q = quadri.get(key)
            if not isinstance(q, dict):
                continue
            if not q.get("presente"):
                continue
            val = _num(q.get(amount_key)) or _num(q.get("reddito"))
            extra = ""
            if key == "RB_fabbricati":
                n = int(_num(q.get("n_immobili_locati")))
                extra = f" ({n} immobil{'e' if n == 1 else 'i'} locat{'o' if n == 1 else 'i'})" if n else ""
            fonti.append(f"{label} {_eur(val)}/anno{extra}")
        anno = data.get("anno_imposta") or ""
        modello = "Mod. 730" if data.get("modello") == "730" else "Mod. Redditi PF"
        nota = f"complessivo {_eur(annual)}/anno"
        if fonti:
            nota += " · " + "; ".join(fonti)
        if anno:
            nota += f" · anno {anno}"
        nota += f" · {modello}"
        _set_income_note(debtor, "[Dichiarazione redditi]", nota)


def _set_income_note(debtor: Debtor, tag: str, text: str) -> None:
    lines = [l for l in (debtor.income_sources or "").split("\n")
             if l.strip() and not l.startswith(tag)]
    lines.append(f"{tag} {text}".strip())
    debtor.income_sources = "\n".join(lines)


def _cur(blk: Any, key: str) -> float:
    if not isinstance(blk, dict):
        return 0.0
    v = blk.get(key)
    return _num(v.get("corrente")) if isinstance(v, dict) else _num(v)


def _eur(v: Any) -> str:
    return f"€ {(_num(v)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _imm_kind(imm: dict) -> str:
    cat = imm.get("categoria")
    tipo = imm.get("tipo_immobile") or ""
    return f"{tipo} {cat}".strip() if cat else (tipo or "immobile")


def _cadastral(imm: dict) -> str:
    parts = []
    for label, key in [("Sez", "sezione_urbana"), ("Fg", "foglio"),
                       ("Part", "particella"), ("Sub", "subalterno")]:
        v = imm.get(key)
        if v:
            parts.append(f"{label} {v}")
    com = imm.get("comune")
    head = f"{com} - " if com else ""
    return head + " ".join(parts)


def _imm_notes(imm: dict) -> str:
    bits = []
    if imm.get("consistenza"):
        bits.append(f"Consistenza: {imm['consistenza']}")
    if imm.get("piano"):
        bits.append(f"Piano: {imm['piano']}")
    if imm.get("classe"):
        bits.append(f"Classe: {imm['classe']}")
    return " | ".join(bits)


def _altri_intestatari(imm: dict) -> str:
    out = []
    intestatari = imm.get("altri_intestatari") if isinstance(imm, dict) else []
    for o in (intestatari if isinstance(intestatari, list) else []):
        if not isinstance(o, dict):
            continue
        nome = o.get("denominazione") or "?"
        quota = o.get("quota") or ""
        diritto = o.get("diritto") or ""
        out.append(f"{nome} ({diritto} {quota})".strip())
    return "; ".join(out)


_MOLT = {
    "A": 120, "A/10": 60, "B": 140,
    "C": 120, "C/1": 40, "C/6": 120, "C/7": 120,
    "D": 60, "E": 40,
}


def _moltiplicatore(categoria: str) -> int:
    if not categoria:
        return 0
    cat = categoria.upper().strip()
    if cat in _MOLT:
        return _MOLT[cat]
    gruppo = cat.split("/")[0]
    return _MOLT.get(gruppo, 0)


def _quota_frazione(quota: str) -> float:
    if not quota:
        return 1.0
    q = quota.strip()
    if "/" in q:
        try:
            n, d = q.split("/")
            return float(n) / float(d) if float(d) else 1.0
        except (ValueError, ZeroDivisionError):
            return 1.0
    return 1.0


def _valore_catastale(rendita: float, categoria: str, quota: str, prima_casa: bool = False) -> float:
    molt = _moltiplicatore(categoria)
    if prima_casa and categoria:
        gruppo = categoria.upper().split("/")[0]
        if gruppo == "A" and categoria.upper() != "A/10":
            molt = 110
    if not rendita or not molt:
        return 0.0
    valore_pieno = rendita * 1.05 * molt
    return round(valore_pieno * _quota_frazione(quota), 2)
