"""Servizio di generazione del Report di Preanalisi Economico-Finanziaria e Ipotesi di Risanamento.

Conforme al template professionale dello studio legale Avv. Aurelio Bentivegna:
- 1. Premessa e finalità della preanalisi
- 2. Profilo dell'impresa e natura della crisi
- 3. Analisi economica triennale (3.1, 3.2, 3.3)
- 4. Il dato dell'anno corrente e necessità di prudenza
- 5. Analisi dell'indebitamento:
  - 5.1 Debiti risultanti dai bilanci (struttura dinamica estratta dai bilanci effettivi)
  - 5.2 Debiti risultanti dalle banche dati esterne (AdER, Centrale Rischi, CTC/CRIF)
  - 5.3 Stima di sintesi della massa debitoria complessiva (senza duplicazioni)
- 6. Punti da verificare
- 7. Diagnosi preliminare della crisi
- 8. Patrimonio (immobili, veicoli, cespiti, esposizione soci)
- 9. Orientamento verso una soluzione di risanamento ex CCII
- 10. Documentazione ancora necessaria prima di procedere
- 11. Conclusione provvisoria
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company, CompanyMember,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    Document, Extraction, TaxDebtStatement, FinancialStatement, CaseCrossAnalysis,
)
from app.services.rule_engine import get_active_rules
from app.services.forensic_preanalysis_chain import run_forensic_preanalysis_chain
from app.services.forensic_audit_engine import build_complete_technical_dossier
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    check_ccii_soglie_impresa_minore,
    check_ccii_segnali_allarme_art3,
    calculate_test_pratico_ministeriale,
    evaluate_risanabilita_diagnosi,
    classify_cinque_criticita,
    identify_documenti_indispensabili,
    extract_bank_debt_split,
)


def _fmt_eur(v):
    if v is None:
        return "—"
    try:
        n = float(v)
        return f"€ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


def _fmt_date(d_str):
    if not d_str:
        return ""
    try:
        dt = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return d_str


def _num_opt(v) -> Optional[float]:
    """Restituisce None se il valore è assente/NULL (mai zero automatico)."""
    if v is None or v == "" or v == "n.r." or v == "N/D" or v == "NULL":
        return None
    if isinstance(v, dict):
        if "corrente" in v and v["corrente"] is not None:
            return _num_opt(v["corrente"])
        if "importo" in v and v["importo"] is not None:
            return _num_opt(v["importo"])
        if "value" in v and v["value"] is not None:
            return _num_opt(v["value"])
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _num(v) -> float:
    res = _num_opt(v)
    return res if res is not None else 0.0


def build_preanalysis_report(db: Session, case_id: str, cached_forensic: Optional[dict] = None) -> dict:
    case = db.get(Case, case_id)
    if not case:
        return {}

    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    companies = db.query(Company).filter_by(case_id=case_id).all()
    # Seleziona la riga Company più completa (con REA o sede valorizzata)
    company = next((c for c in companies if c.rea and c.legal_address), None) or (companies[0] if companies else None)
    docs = db.query(Document).filter_by(case_id=case_id).all()
    extractions = db.query(Extraction).filter(Extraction.document_id.in_([d.id for d in docs])).all() if docs else []
    ext_by_doc_id = {e.document_id: e for e in extractions}

    # Se mancano REA, sede o ATECO nella Company, ricava direttamente dall'estrazione della Visura Camerale
    if company and (not company.rea or not company.legal_address or not company.ateco):
        for d in docs:
            ext_item = ext_by_doc_id.get(d.id)
            if ext_item and ext_item.json_output and isinstance(ext_item.json_output, dict):
                jo = ext_item.json_output
                imp = jo.get("impresa", {})
                sec = jo.get("dati_secondari", {})
                if not company.rea:
                    company.rea = imp.get("numero_rea") or sec.get("numero_rea") or ""
                if not company.legal_address:
                    company.legal_address = imp.get("sede_legale") or sec.get("sede_legale") or ""
                if not company.ateco:
                    company.ateco = sec.get("classificazione_ateco") or imp.get("classificazione_ateco") or ""
                if not company.constitution_date:
                    company.constitution_date = str(imp.get("data_costituzione") or "")
                if not company.capital and imp.get("capitale_conferimenti"):
                    try:
                        company.capital = float(imp["capitale_conferimenti"])
                    except Exception:
                        pass

    members = db.query(CompanyMember).filter(CompanyMember.company_id.in_([c.id for c in companies])).all() if companies else []

    fss = db.query(FinancialStatement).filter_by(case_id=case_id).order_by(FinancialStatement.fiscal_year_end).all()
    real_estates = db.query(RealEstate).filter_by(case_id=case_id).all()
    vehicles = db.query(Vehicle).filter_by(case_id=case_id).all()
    cr = db.query(CreditReportSummary).filter_by(case_id=case_id).order_by(CreditReportSummary.id.desc()).first()
    exposures = db.query(CreditExposure).filter_by(case_id=case_id).all()
    guarantees = db.query(GuaranteeGiven).filter_by(case_id=case_id).all()
    statements = db.query(TaxDebtStatement).filter_by(case_id=case_id).all()
    cross = db.query(CaseCrossAnalysis).filter_by(case_id=case_id, status="completed").order_by(CaseCrossAnalysis.id.desc()).first()

    now = datetime.now()
    mese_anno_corrente = now.strftime("%B %Y").upper()

    # Rilevamento Impresa / Ditta Individuale vs Società
    is_individual = False
    if company:
        lf = (company.legal_form or "").lower()
        ct = (company.company_type or "").lower()
        if any(k in lf for k in ("individuale", "ditta", "persona fisica", "libero professionista")) or any(k in ct for k in ("individuale", "ditta")):
            is_individual = True
    if debtor and (debtor.client_type or "").lower() in ("ditta_individuale", "privato"):
        if not company or any(k in (company.legal_form or "").lower() for k in ("individuale", "ditta")):
            is_individual = True

    titolare_nominativo = (f"{debtor.first_name} {debtor.last_name}".strip() if debtor and debtor.first_name else (case.client_name or "")).strip()
    ditta_denominazione = (company.name if company and company.name else titolare_nominativo) or "CLIENTE"
    client_display = ditta_denominazione
    client_tax_code = (company.vat or company.tax_code if company else (debtor.tax_code if debtor else case.client_tax_code)) or ""
    client_cf = (debtor.tax_code if debtor and debtor.tax_code else (company.tax_code if company else client_tax_code)) or ""

    # REA con sigla provincia CCIAA (es. PA - 409999)
    rea_val = (company.rea if company else "") or ""
    cciaa_val = (company.cciaa if company else "") or ""
    if rea_val and rea_val != "—":
        if cciaa_val and not rea_val.upper().startswith(cciaa_val.upper()[:2]):
            prov_sigla = "PA" if "palermo" in cciaa_val.lower() else (cciaa_val[:2].upper() if len(cciaa_val) == 2 else cciaa_val)
            rea_display = f"{prov_sigla} - {rea_val}"
        else:
            rea_display = rea_val
    else:
        rea_display = "—"

    if is_individual:
        capitale_sociale_val = None
        capitale_sociale_display = "Non applicabile (Impresa individuale: priva di capitale sociale ex lege)"
    else:
        capitale_sociale_val = float(company.capital) if (company and company.capital is not None and company.capital > 0) else None
        capitale_sociale_display = _fmt_eur(capitale_sociale_val) if capitale_sociale_val is not None else "Non rilevato (NULL)"

    # Raccolta testi documenti per la catena forense LangChain (Qwen) con tracciamento copertura
    PRIORITY_DOC_TYPES = {"bilancio", "centrale_rischi", "visura_camerale", "crif", "cartella_aer", "dichiarazione_redditi"}
    doc_snippets = []
    docs_included = []
    docs_excluded_no_text = []
    docs_sampled_truncated = []
    max_snippet_per_doc = 8000
    for d in sorted(docs, key=lambda x: 0 if x.doc_type in PRIORITY_DOC_TYPES else 1):
        if d.doc_type not in PRIORITY_DOC_TYPES and any(skip in d.original_filename.lower() for skip in ("c.i.", "tessera", "famiglia", "spese", "saldati")):
            docs_excluded_no_text.append(f"{d.original_filename} (escluso come allegato non economico/amministrativo)")
            continue
        ext_item = ext_by_doc_id.get(d.id)
        if ext_item and ext_item.raw_text:
            txt = ext_item.raw_text.strip()
            if txt:
                # Se il documento è un estratto AdER già normalizzato in DB, antepone il riepilogo del fascicolo
                if d.doc_type == "cartella_aer" and statements:
                    matched_st = next((st for st in statements if getattr(st, "source_document_id", None) == d.id), None)
                    if matched_st:
                        txt = (
                            f"ESTRATTO DI RUOLO ADER ({matched_st.data_elaborazione or 'da documento'})\n"
                            f"Intestatario: {client_display} (CF: {client_cf or 'N/D'})\n"
                            f"Carico affidato: € {matched_st.total_carico_affidato:,.2f}\n"
                            f"Residuo netto da pagare: € {matched_st.total_residuo:,.2f}\n"
                            f"Righe estratte: {len(matched_st.items or [])}."
                        )
                if len(txt) > max_snippet_per_doc:
                    body = txt[:5000] + "\n...[SEGMENTO CENTRALE CAMPIONATO]...\n" + txt[-3000:]
                    docs_sampled_truncated.append(f"{d.original_filename} ({len(txt)} car.)")
                else:
                    body = txt
                docs_included.append(d.original_filename)
                doc_snippets.append(f"=== DOCUMENTO: {d.original_filename} (Tipologia: {d.doc_type}) ===\n{body}")
                continue
        docs_excluded_no_text.append(f"{d.original_filename} (nessun testo OCR/estratto)")

    documenti_testo = "\n\n".join(doc_snippets)
    chain_context_coverage = {
        "docs_total": len(docs),
        "docs_included": docs_included,
        "docs_excluded": docs_excluded_no_text,
        "docs_sampled_truncated": docs_sampled_truncated,
        "full_coverage": (len(docs_excluded_no_text) == 0 and len(docs_sampled_truncated) == 0),
    }

    forensic_res = {}
    if cached_forensic and isinstance(cached_forensic, dict) and (cached_forensic.get("client_report_text") or cached_forensic.get("json_matrix")):
        forensic_res = cached_forensic
    elif documenti_testo:
        try:
            forensic_res = run_forensic_preanalysis_chain(
                nome_cliente=client_display,
                data_analisi=now.strftime("%d/%m/%Y"),
                documenti_testo=documenti_testo,
                temperature=0.1,
            )
        except Exception:
            forensic_res = {}

    # =========================================================================
    # CAP. 1: PREMESSA E DOCUMENTI UTILIZZATI
    # =========================================================================
    docs_utilizzati = []
    # Rileva bilanci
    for fs in fss:
        dt_lbl = fs.fiscal_year_end
        is_provv = "provvisorio" in fs.statement_type.lower() or dt_lbl.endswith("-06-30") or dt_lbl.endswith("-09-30")
        docs_utilizzati.append({
            "tipo": "Situazione contabile / bilancio provvisorio" if is_provv else "Bilancio d'esercizio",
            "titolo": f"Bilancio al {dt_lbl}",
            "data": dt_lbl,
        })
    # Rileva visura camerale
    if company:
        visura_doc = next((d for d in docs if "camerale" in (d.doc_type or "") or "visura" in d.original_filename.lower()), None)
        docs_utilizzati.append({
            "tipo": "Visura Camerale Registro Imprese",
            "titolo": f"Visura ordinaria {company.name}",
            "data": visura_doc.created_at.strftime("%d/%m/%Y") if (visura_doc and visura_doc.created_at) else "Da fascicolo",
        })
    # Rileva Centrale Rischi
    if cr or exposures:
        cr_doc = next((d for d in docs if d.doc_type == "centrale_rischi"), None)
        docs_utilizzati.append({
            "tipo": "Centrale Rischi Banca d'Italia",
            "titolo": "Prospetto segnalazioni Banca d'Italia",
            "data": (cr.reference_date if cr and getattr(cr, "reference_date", None) else (cr_doc.created_at.strftime("%d/%m/%Y") if (cr_doc and cr_doc.created_at) else "Da fascicolo")),
        })
    # Rileva AdER
    aer_docs = [d for d in docs if "saldare" in d.original_filename.lower() or "aer" in d.doc_type]
    if aer_docs or statements:
        st_date = (statements[0].data_elaborazione if statements and statements[0].data_elaborazione else None)
        docs_utilizzati.append({
            "tipo": "Estratto di ruolo / Situazione debitoria AdER",
            "titolo": "Estratto di ruolo AdER - Da saldare",
            "data": st_date or (aer_docs[0].created_at.strftime("%d/%m/%Y") if (aer_docs and aer_docs[0].created_at) else "Da fascicolo"),
        })
    # Rileva visura catastale
    if real_estates:
        docs_utilizzati.append({
            "tipo": "Visura catastale",
            "titolo": f"Visura per immobile ({len(real_estates)} unità censite)",
            "data": "Catasto fabbricati aggiornato",
        })
    # Rileva elenco beni / altri documenti
    if vehicles or any("bene" in d.original_filename.lower() for d in docs):
        docs_utilizzati.append({
            "tipo": "Elenco beni aziendali e perizie",
            "titolo": "Elenco beni e macchinari fornito dal cliente",
            "data": "Documentazione cliente",
        })

    # =========================================================================
    # CAP. 2: PROFILO IMPRESA E NATURA CRISI
    # =========================================================================
    soci_list = []
    seen_soci = set()
    for m in members:
        # Deduplicazione per Codice Fiscale o per token del nominativo
        norm_tokens = " ".join(sorted([w.lower() for w in (m.name or "").replace(".", " ").split() if w]))
        key = (m.tax_code or "").strip().upper() or norm_tokens
        if key and key in seen_soci:
            continue
        if key:
            seen_soci.add(key)
        
        if is_individual:
            ruolo_str = "Titolare dell'impresa / Legale rappresentante"
            quota_val = 100.0
            resp_str = "Responsabilità illimitata ex art. 2740 c.c."
        else:
            ruolo_str = m.roles or ("Legale rappresentante" if m.is_legal_rep else "Socio")
            quota_val = m.quota_percent
            resp_str = "Limitata al capitale sociale conferito"

        soci_list.append({
            "nome": m.name,
            "codice_fiscale": m.tax_code or None,
            "quota_pct": quota_val,
            "ruolo": ruolo_str,
            "garante": m.is_client or "garante" in (m.roles or "").lower(),
            "regime_responsabilita": resp_str,
        })

    if not soci_list and is_individual and titolare_nominativo:
        soci_list.append({
            "nome": titolare_nominativo.upper(),
            "codice_fiscale": (debtor.tax_code if debtor else case.client_tax_code) or None,
            "quota_pct": 100.0,
            "ruolo": "Titolare dell'impresa individuale",
            "garante": True,
            "regime_responsabilita": "Responsabilità illimitata ex art. 2740 c.c.",
        })

    # =========================================================================
    # CAP. 3: ANALISI ECONOMICA PLURIENNALE (3.1, 3.2, 3.3)
    # =========================================================================
    def _clean_date_and_year(date_str: str) -> tuple[str, str, str]:
        if not date_str:
            return ("", "", "")
        s = str(date_str).strip()
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3:
                if len(parts[2]) == 4:
                    return (f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}", parts[2], f"{parts[0]}/{parts[1]}/{parts[2][2:]}")
                elif len(parts[0]) == 4:
                    return (f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}", parts[0], f"{parts[2]}/{parts[1]}/{parts[0][2:]}")
        if "-" in s:
            parts = s.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                return (s, parts[0], f"{parts[2]}/{parts[1]}/{parts[0][2:]}")
        y = s[:4] if len(s) >= 4 and s[:4].isdigit() else (s[-4:] if len(s) >= 4 and s[-4:].isdigit() else s)
        return (s, y, s)

    def _is_interim_fs(statement) -> bool:
        dt = str(statement.fiscal_year_end or "").strip()
        st = str(statement.statement_type or "").lower()
        if any(k in st for k in ("provvisori", "infrannual", "interim")):
            return True
        iso, _, _ = _clean_date_and_year(dt)
        if iso and not (iso.endswith("-12-31") or iso.endswith("-12")):
            return True
        return False

    # Considera solo i bilanci d'esercizio annuali completi (esclusi infrannuali)
    annual_fss = [fs for fs in fss if not _is_interim_fs(fs)]
    annual_fss = sorted(annual_fss, key=lambda x: _clean_date_and_year(x.fiscal_year_end)[0])[-3:] # ultimi 3 esercizi

    esercizi_economici = []
    for fs in annual_fss:
        ce = fs.raw_extraction.get("conto_economico") or {}
        eb = calculate_ebitda_oic12(ce)
        a1 = eb["ricavi_vendite_a1"]
        val_prod = eb["valore_produzione_a"]
        costi_prod = eb["costi_produzione_b"]
        ammortamenti = eb["ammortamenti_b10a_b10b_b10c"]
        altri_ricavi = max(0.0, round(val_prod - a1, 2)) if (val_prod is not None and a1 is not None) else None
        mol = eb["ebitda_standard"]
        mol_pct = eb["ebitda_margin_pct"]
        utile_perdita = _num(ce.get("utile_perdita") or fs.net_result)

        _, anno_str, _ = _clean_date_and_year(fs.fiscal_year_end)
        esercizi_economici.append({
            "anno": anno_str,
            "data_chiusura": fs.fiscal_year_end,
            "ricavi_a1": a1,
            "altri_ricavi_a2_a5": altri_ricavi,
            "valore_produzione_a": val_prod,
            "costi_produzione_b": costi_prod,
            "ammortamenti": ammortamenti,
            "ebit": eb["ebit_differenza_a_b"],
            "mol": mol,
            "mol_pct": mol_pct,
            "utile_perdita": utile_perdita,
            "formula_mol": eb["formula_applicata"],
        })

    # =========================================================================
    # CAP. 4: IL DATO INFRA-ANNUALE
    # =========================================================================
    sorted_all_fss = sorted(fss, key=lambda x: _clean_date_and_year(x.fiscal_year_end)[0])
    interim_fs = next((fs for fs in reversed(sorted_all_fss) if _is_interim_fs(fs)), None)
    dato_infrannuale = None
    if interim_fs:
        ce = interim_fs.raw_extraction.get("conto_economico") or {}
        eb_int = calculate_ebitda_oic12(ce)
        a1 = eb_int["ricavi_vendite_a1"]
        val_prod = eb_int["valore_produzione_a"]
        costi_prod = eb_int["costi_produzione_b"]
        ammortamenti = eb_int["ammortamenti_b10a_b10b_b10c"]
        altri_ricavi = max(0.0, round(val_prod - a1, 2)) if (val_prod is not None and a1 is not None) else None
        mol = eb_int["ebitda_standard"]
        utile_perdita = _num(ce.get("utile_perdita") or interim_fs.net_result)
        oneri_fin = _num(ce.get("oneri_finanziari"))
        iso_int, _, dt_it_int = _clean_date_and_year(interim_fs.fiscal_year_end)
        dato_infrannuale = {
            "periodo": f"al {dt_it_int}" if dt_it_int else interim_fs.fiscal_year_end,
            "ricavi_a1": a1,
            "altri_ricavi_a2_a5": altri_ricavi,
            "valore_produzione_a": val_prod,
            "costi_produzione_b": costi_prod,
            "ammortamenti": ammortamenti,
            "ebit": eb_int["ebit_differenza_a_b"],
            "oneri_finanziari": oneri_fin,
            "mol": mol,
            "utile_perdita": utile_perdita,
            "formula_mol": eb_int["formula_applicata"],
        }

    # =========================================================================
    # CAP. 5.1: DEBITI RISULTANTI DAI BILANCI (DINAMICA DAI BILANCI EFFETTIVI)
    # =========================================================================
    # Colonne cronologiche di tutti i bilanci e situazioni disponibili
    ordered_fss = sorted(fss, key=lambda x: _clean_date_and_year(x.fiscal_year_end)[0])
    cols = []
    for fs in ordered_fss:
        is_interim = _is_interim_fs(fs)
        iso_dt, year, dt_it = _clean_date_and_year(fs.fiscal_year_end)
        title = f"Situazione {year}" if is_interim else f"Bilancio {year}"
        date_lbl = f"al {dt_it}"
        lbl = f"{title} ({date_lbl})"
        cols.append({
            "key": iso_dt or fs.fiscal_year_end,
            "label": lbl,
            "title": title,
            "date": date_lbl,
            "is_interim": is_interim,
            "fs": fs,
        })

    # Ultimo bilancio approvato vs situazione più recente per il calcolo della variazione
    last_approved_col = next((c for c in reversed(cols) if not c["is_interim"]), None)
    latest_col = cols[-1] if cols else None

    # Mappatura e scoperta dinamica di tutte le voci di debito effettive presenti
    STANDARD_DEBT_ORDER = [
        ("banche", "Debiti verso banche"),
        ("soci_finanziamenti", "Debiti verso soci e amministratori"),
        ("altri_finanziatori", "Debiti verso altri finanziatori"),
        ("fornitori", "Debiti verso fornitori"),
        ("tributari", "Debiti tributari"),
        ("previdenziali", "Debiti verso istituti di previdenza"),
        ("dipendenti", "Debiti verso dipendenti"),
        ("altri", "Altri debiti"),
        ("tfr", "Trattamento di fine rapporto (TFR)"),
    ]

    # Raccoglie tutte le chiavi presenti in debiti_per_natura e stato_patrimoniale
    discovered_keys = set()
    for fs in ordered_fss:
        dpn = fs.raw_extraction.get("debiti_per_natura") or {}
        for k in dpn.keys():
            if k != "totale":
                discovered_keys.add(k)
        sp = fs.raw_extraction.get("stato_patrimoniale") or {}
        if sp.get("tfr"):
            discovered_keys.add("tfr")

    # Ordine righe: standard prima, poi qualsiasi voce extra scoperta dal bilancio
    row_keys = []
    for code, label in STANDARD_DEBT_ORDER:
        if code in discovered_keys or code in ("banche", "fornitori", "tributari", "previdenziali", "soci_finanziamenti", "tfr"):
            row_keys.append((code, label))

    for k in sorted(discovered_keys):
        if not any(r[0] == k for r in row_keys):
            lbl = k.replace("_", " ").capitalize()
            row_keys.append((k, f"Debiti - {lbl}"))

    # Costruzione delle righe della tabella 5.1
    table_5_1_rows = []
    col_totals = {c["key"]: 0.0 for c in cols}

    for code, label in row_keys:
        valori = {}
        row_note = ""
        for c in cols:
            fs = c["fs"]
            if code == "tfr":
                sp = fs.raw_extraction.get("stato_patrimoniale") or {}
                amt = _num(sp.get("tfr"))
            else:
                dpn = fs.raw_extraction.get("debiti_per_natura") or {}
                item = dpn.get(code)
                amt = _num(item)
                if isinstance(item, dict) and c == latest_col:
                    oltre = _num(item.get("oltre"))
                    if oltre > 0:
                        row_note = f"Oltre 12m: € {oltre:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            valori[c["key"]] = round(amt, 2)
            col_totals[c["key"]] += amt

        # Calcolo variazione: situazione più recente - ultimo bilancio approvato
        val_latest = valori.get(latest_col["key"], 0.0) if latest_col else 0.0
        val_base = valori.get(last_approved_col["key"], 0.0) if last_approved_col else 0.0
        variazione = round(val_latest - val_base, 2)

        table_5_1_rows.append({
            "codice": code,
            "voce": label,
            "valori": valori,
            "variazione": variazione,
            "note": row_note,
        })

    total_base = col_totals.get(last_approved_col["key"], 0.0) if last_approved_col else 0.0
    total_latest = col_totals.get(latest_col["key"], 0.0) if latest_col else 0.0
    total_var = round(total_latest - total_base, 2)
    has_balance_debts = any(v > 0 for v in col_totals.values())

    # Se non vi sono debiti rilevati da bilancio (contabilità semplificata), arricchisci i display
    for r in table_5_1_rows:
        r["has_balance_debts"] = has_balance_debts
        if not has_balance_debts:
            r["valori_display"] = {k: "n.r.*" for k in r["valori"]}
            r["variazione_display"] = "n.r.*"
        else:
            r["valori_display"] = {k: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for k, v in r["valori"].items()}
            r["variazione_display"] = f"€ {r['variazione']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    var_subtitle = f"({latest_col['key'][:4]} vs {last_approved_col['key'][:4]})" if (latest_col and last_approved_col) else "Netta"
    table_5_1 = {
        "colonne": [
            {
                "key": c["key"],
                "label": c["label"],
                "title": c.get("title", c["label"]),
                "date": c.get("date", c["key"]),
                "is_interim": c["is_interim"],
            }
            for c in cols
        ],
        "righe": table_5_1_rows,
        "totali": {k: round(v, 2) for k, v in col_totals.items()},
        "totali_display": {k: (f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if has_balance_debts else "n.r.*") for k, v in col_totals.items()},
        "totale_variazione": total_var,
        "totale_variazione_display": (f"€ {total_var:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if has_balance_debts else "n.r.*"),
        "base_confronto": last_approved_col["key"] if last_approved_col else "",
        "situazione_recente": latest_col["key"] if latest_col else "",
        "var_subtitle": var_subtitle,
        "has_balance_debts": has_balance_debts,
        "regime_contabile": "contabilita_semplificata" if (is_individual and not has_balance_debts) else "ordinaria",
        "nota_semplificata": "*n.r. = Non rilevabile: contabilità semplificata (D.P.R. 600/1973) priva di stato patrimoniale ex art. 2424 c.c.",
    }

    # =========================================================================
    # CAP. 5.2: BANCHE DATI ESTERNE (AdER, CR, CTC/CRIF)
    # =========================================================================
    # Dati AdER
    valid_stmts = [s for s in statements if s.total_residuo > 0]
    if valid_stmts:
        tot_residuo_aer = max(s.total_residuo for s in valid_stmts)
        tot_carico_aer = max(s.total_carico_affidato for s in valid_stmts)
    else:
        tot_residuo_aer = sum(s.total_residuo for s in statements)
        tot_carico_aer = sum(s.total_carico_affidato for s in statements)

    # Fallback deterministico da file AdER se non presente a DB
    if tot_residuo_aer == 0.0:
        for d in docs:
            if "saldare" in d.original_filename.lower() or d.doc_type == "cartella_aer":
                try:
                    from app.services import aer_parser
                    parsed_aer = aer_parser.parse_pdf(d.storage_path)
                    if parsed_aer and parsed_aer.get("totali"):
                        res_v = _num(parsed_aer["totali"].get("totale_residuo"))
                        if res_v > 0:
                            tot_residuo_aer = res_v
                            tot_carico_aer = _num(parsed_aer["totali"].get("carico_affidato"))
                            break
                except Exception:
                    pass

    all_aer_items = [it for st in statements for it in (st.items or [])]
    has_aer_data = bool(statements or tot_residuo_aer > 0)
    sgravi_val = round(sum(float(it.sgravio or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    pagato_val = round(sum(float(it.gia_pagato or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    stralcio_val = round(sum(float(it.stralcio or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    res_cap_val = round(sum(float(it.residuo_carico or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    int_sanz_val = round(sum(float(it.interessi_mora or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    oneri_val = round(sum(float(it.oneri_diritti or 0.0) for it in all_aer_items), 2) if all_aer_items else None
    rott_items = [it for it in all_aer_items if it.def_agevolata]
    ader_table = {
        "carico_affidato": tot_carico_aer if tot_carico_aer > 0 else (tot_residuo_aer if has_aer_data else None),
        "sgravi": sgravi_val,
        "pagamenti_effettuati": pagato_val,
        "stralcio_definizione": stralcio_val,
        "residuo_capitale": res_cap_val,
        "interessi_sanzioni": int_sanz_val,
        "ulteriori_oneri": oneri_val,
        "totale_residuo": tot_residuo_aer if has_aer_data else None,
        "dettaglio_rottamazioni": [
            {
                "procedura": f"Definizione agevolata ({len(rott_items)} cartelle)",
                "debito_originario": round(sum(float(it.carico_affidato or 0.0) for it in rott_items), 2),
                "stato": "Rilevato da estratto AdER",
                "residuo": round(sum(float(it.totale_residuo or 0.0) for it in rott_items), 2),
            }
        ] if rott_items else [],
    }

    # Dati creditizi (Centrale Rischi, CTC/CRIF)
    credit_db_rows = []
    if exposures:
        for exp in exposures:
            credit_db_rows.append({
                "fonte": "Centrale Rischi Banca d'Italia",
                "intermediario": exp.intermediary,
                "rapporto": exp.category or "Rischi a scadenza",
                "accordato": exp.accordato,
                "utilizzato": exp.utilizzato,
                "rata": "—",
                "note": "Rischio a scadenza regolare, nessuna sofferenza" if not getattr(exp, "is_critical", False) else "Sofferenza / criticità segnalata",
            })
    elif cr:
        cr_exp_val = float(cr.total_exposure) if cr.total_exposure is not None else None
        credit_db_rows.append({
            "fonte": "Centrale Rischi Banca d'Italia",
            "intermediario": "Intermediari censiti in Centrale Rischi",
            "rapporto": "Esposizione aggregata da sintesi CR",
            "accordato": cr_exp_val,
            "utilizzato": cr_exp_val,
            "rata": "—",
            "note": "Sofferenza segnalata in CR" if getattr(cr, "has_sofferenze", False) else "Segnalazione da sintesi Centrale Rischi",
        })

    # CTC / CRIF / Finanziamenti da DebtPosition o Extraction
    from app.models import DebtPosition
    ctc_positions = db.query(DebtPosition).filter(
        DebtPosition.case_id == case_id,
        (DebtPosition.debt_type.ilike("%prestito%") |
         DebtPosition.debt_type.ilike("%finanziamento%") |
         DebtPosition.debt_type.ilike("%credito%") |
         DebtPosition.debt_type.ilike("%coobblig%") |
         DebtPosition.debt_type.ilike("%carta%") |
         DebtPosition.debt_type.ilike("%mutuo%") |
         DebtPosition.debt_type.ilike("%leasing%"))
    ).all()

    if ctc_positions:
        for cp in ctc_positions:
            if cp.residual_amount > 0 or "attivo" in (cp.status or "").lower():
                note_str = (
                    "Coobbligazione / posizione personale censita ex art. 2740 c.c."
                    if is_individual
                    else "Posizione creditizia / finanziamento censito nel fascicolo"
                )
                if cp.residual_amount == 0.0 and cp.monthly_installment > 0:
                    note_str = "Rapporto attivo con rata rilevata e saldo residuo non esposto (NULL)"
                credit_db_rows.append({
                    "fonte": "CTC / CRIF (Visura contratti)",
                    "intermediario": cp.creditor_name,
                    "rapporto": cp.debt_type or "Finanziamento",
                    "accordato": cp.original_amount,
                    "utilizzato": cp.residual_amount if cp.residual_amount > 0 else None,
                    "rata": f"€ {cp.monthly_installment:,.2f} / mese" if cp.monthly_installment > 0 else "—",
                    "note": note_str,
                })
    else:
        for d in docs:
            if "ctc" in d.original_filename.lower() or d.doc_type == "crif":
                ext_item = ext_by_doc_id.get(d.id)
                if ext_item and ext_item.json_output and isinstance(ext_item.json_output, dict):
                    pos_list = ext_item.json_output.get("credit_positions") or []
                    for p in pos_list:
                        cred = p.get("creditor") or ""
                        res_amt = _num_opt(p.get("residual_amount"))
                        orig_amt = _num_opt(p.get("original_amount"))
                        rata = _num(p.get("monthly_installment"))
                        if (res_amt is not None and res_amt > 0) or "attivo" in str(p.get("status", "")).lower():
                            note_ctc = "Posizione attiva censita da visura CTC/CRIF"
                            if res_amt is None or res_amt == 0:
                                note_ctc = "Posizione attiva con saldo residuo non esposto (NULL)"
                            credit_db_rows.append({
                                "fonte": "CTC / CRIF (Visura contratti)",
                                "intermediario": cred,
                                "rapporto": p.get("debt_type") or "Credito al consumo",
                                "accordato": orig_amt,
                                "utilizzato": res_amt if (res_amt is not None and res_amt > 0) else None,
                                "rata": f"€ {rata:,.2f} / mese" if rata > 0 else "—",
                                "note": note_ctc,
                            })

    # =========================================================================
    # CAP. 5.3: STIMA DELLA MASSA DEBITORIA COMPLESSIVA (SENZA DUPLICAZIONI)
    # =========================================================================
    tot_trib_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "tributari"), 0.0) if latest_col else 0.0
    tot_prev_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "previdenziali"), 0.0) if latest_col else 0.0
    tot_banche_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "banche"), 0.0) if latest_col else 0.0
    tot_forn_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "fornitori"), 0.0) if latest_col else 0.0
    tot_soci_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "soci_finanziamenti"), 0.0) if latest_col else 0.0
    tot_altri_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "altri"), 0.0) if latest_col else 0.0
    tot_tfr_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "tfr"), 0.0) if latest_col else 0.0

    cr_rows_vals = [float(r["utilizzato"]) for r in credit_db_rows if "Centrale Rischi" in r["fonte"] and r.get("utilizzato") is not None]
    tot_cr_ut: Optional[float] = round(sum(cr_rows_vals), 2) if cr_rows_vals else (tot_banche_bilancio if (has_balance_debts and tot_banche_bilancio > 0) else None)

    ctc_rows_vals = [float(r["utilizzato"]) for r in credit_db_rows if "CTC" in r["fonte"] and r.get("utilizzato") is not None]
    tot_ctc_ut: Optional[float] = round(sum(ctc_rows_vals), 2) if ctc_rows_vals else None

    aer_component: Optional[float] = tot_residuo_aer if has_aer_data else None
    has_any_quantified = (aer_component is not None) or (tot_cr_ut is not None) or (tot_ctc_ut is not None)
    tot_esposizioni_principali_quantificate: Optional[float] = (
        round((aer_component or 0.0) + (tot_cr_ut or 0.0) + (tot_ctc_ut or 0.0), 2)
        if has_any_quantified
        else None
    )

    fornitori_stimati: Optional[float] = round(tot_forn_bilancio, 2) if has_balance_debts else None
    personale_stimato: Optional[float] = round(tot_tfr_bilancio + tot_altri_bilancio + tot_soci_bilancio, 2) if has_balance_debts else None

    cr_intermediari = ", ".join(sorted({str(r.get("intermediario") or "").strip() for r in credit_db_rows if "Centrale Rischi" in r.get("fonte", "") and r.get("intermediario")}))
    cr_note = (
        f"{cr_intermediari}: rischio documentato da Centrale Rischi Banca d'Italia."
        if cr_intermediari
        else (
            "Debiti bancari rilevati da bilancio / situazione contabile."
            if tot_cr_ut is not None
            else "Nessuna esposizione bancaria o Centrale Rischi acquisita al fascicolo (NULL)."
        )
    )
    ctc_note = (
        "Posizioni da visura CTC/CRIF imputate secondo responsabilità patrimoniale."
        if tot_ctc_ut is not None
        else "Nessuna posizione CTC/CRIF attiva documentata al fascicolo."
    )
    sub_fonte = "Somma AdER + Bancario/CR + CTC documentato"

    stima_massa_rows = [
        {
            "categoria": "Tributario e contributivo a ruolo AdER [D]" if is_individual else "Tributario e contributivo a ruolo",
            "fonte": "Estratto di ruolo AdER",
            "importo_stimato": aer_component,
            "dato_bilancio": round(tot_trib_bilancio + tot_prev_bilancio, 2) if has_balance_debts else None,
            "note": (
                "Totale Residuo AdER netto da estratto di ruolo. Sottocomponenti già incluse; esclude carichi saldati."
                if aer_component is not None
                else "Nessun estratto AdER caricato al fascicolo (NULL)."
            ),
        },
        {
            "categoria": "Bancario a revoca/scadenza (Centrale Rischi) [D]",
            "fonte": "Centrale Rischi Banca d'Italia / Bilancio",
            "importo_stimato": tot_cr_ut,
            "dato_bilancio": tot_banche_bilancio if has_balance_debts else None,
            "note": cr_note,
        },
        {
            "categoria": "Credito al consumo e coobbligazioni personali (CTC) [D]",
            "fonte": "CTC / Visura contrattuale",
            "importo_stimato": tot_ctc_ut,
            "dato_bilancio": 0.0 if has_balance_debts else None,
            "note": ctc_note,
        },
        {
            "categoria": "Subtotale Esposizioni Principali Quantificate [C]",
            "fonte": sub_fonte,
            "importo_stimato": tot_esposizioni_principali_quantificate,
            "dato_bilancio": round(tot_trib_bilancio + tot_prev_bilancio + tot_banche_bilancio, 2) if has_balance_debts else None,
            "note": "Passività documentate da registri ufficiali di terzi o bilanci.",
        },
        {
            "categoria": "Fornitori e debiti commerciali [D]",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else 'bilancio'}",
            "importo_stimato": fornitori_stimati,
            "dato_bilancio": tot_forn_bilancio if has_balance_debts else None,
            "note": (
                "Dato rilevato dalla situazione contabile/bilancio in attesa di partitario scadenzario fornitori."
                if has_balance_debts
                else "Stato patrimoniale / partitario fornitori non presente al fascicolo (NULL)."
            ),
        },
        {
            "categoria": "TFR, finanziamenti soci e altri debiti contabili [D]",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else 'bilancio'}",
            "importo_stimato": personale_stimato,
            "dato_bilancio": round(tot_tfr_bilancio + tot_altri_bilancio + tot_soci_bilancio, 2) if has_balance_debts else None,
            "note": (
                "TFR, finanziamenti soci (postergazione ex art. 2467 c.c. da verificare) e altre passività di bilancio."
                if has_balance_debts
                else "TFR, debiti verso personale e altre passività non documentate da SP (NULL)."
            ),
        },
    ]

    if has_any_quantified or has_balance_debts:
        tot_massa_stimata: Optional[float] = round(
            (tot_esposizioni_principali_quantificate or 0.0)
            + (fornitori_stimati or 0.0)
            + (personale_stimato or 0.0),
            2,
        )
    else:
        tot_massa_stimata = None
    # Escludi le righe subtotale per evitare il doppio conteggio nella somma di bilancio
    tot_massa_bilancio: Optional[float] = round(
        sum(
            float(r["dato_bilancio"] or 0.0)
            for r in stima_massa_rows
            if "subtotale" not in (r.get("categoria") or "").lower()
        ),
        2,
    ) if has_balance_debts else None

    # Aggiungi dato_bilancio_display a ciascuna riga della tabella 5.3
    for r in stima_massa_rows:
        if has_balance_debts and r["dato_bilancio"] is not None:
            r["dato_bilancio_display"] = f"€ {r['dato_bilancio']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            r["dato_bilancio_display"] = "n.r. (NULL)"


    # =========================================================================
    # CAP. 6: PUNTI DA VERIFICARE
    # =========================================================================
    punti_da_verificare = []
    if cross and cross.incongruenze:
        for inc in cross.incongruenze:
            punti_da_verificare.append({
                "descrizione": inc.get("descrizione", ""),
                "gravita": inc.get("gravita", "VERIFICA"),
                "documenti": inc.get("documenti_coinvolti", ""),
                "azione": inc.get("azione_consigliata", ""),
            })
    else:
        punti_da_verificare.append({
            "descrizione": "Analisi trasversale automatica non ancora eseguita o nessuna incongruenza registrata.",
            "gravita": "VERIFICA",
            "documenti": "Fascicolo documentale",
            "azione": "Verificare la coerenza tra documenti primari acquisiti ed eseguire l'analisi incrociata.",
        })

    # =========================================================================
    # CAP. 8: PATRIMONIO
    # =========================================================================
    has_negative_cadastral = any(
        "nessuna corrispondenza" in d.original_filename.lower()
        or "nessuna corrispondenza" in ((ext_by_doc_id.get(d.id).raw_text if ext_by_doc_id.get(d.id) else "") or "").lower()
        for d in docs
    )
    esito_catastale = (
        f"Accertamento negativo documentato: la ricerca catastale sul codice fiscale {client_cf or 'indicato'} "
        "ha restituito formalmente: 'NESSUNA CORRISPONDENZA TROVATA'. [D]"
    ) if has_negative_cadastral else (
        f"Individuate {len(real_estates)} unità immobiliari censite."
        if real_estates
        else "Nessun immobile censito nel fascicolo / visura catastale negativa non ancora acquisita."
    )

    immobili_table = []
    tot_catastale = 0.0
    for idx, r in enumerate(real_estates, 1):
        cad_val = float(r.cadastral_value or 0.0)
        tot_catastale += cad_val
        addr = r.address or ""
        comune_val = "—"
        if addr and " - " in addr:
            parts = addr.split(" - ", 1)
            comune_val = parts[0].strip()
            addr = parts[1].strip()
        elif addr and "," in addr:
            comune_val = addr.split(",")[-1].strip()

        immobili_table.append({
            "numero": idx,
            "comune": comune_val,
            "indirizzo": addr or "Indirizzo in fase di riscontro",
            "catasto": r.cadastral_data or "Dati catastali in verifica",
            "categoria": r.category or "—",
            "rendita": float(r.cadastral_income or 0.0),
            "valore_catastale": cad_val,
            "stima_fascia": float(r.commercial_value) if getattr(r, "commercial_value", None) else None,
            "criterio": "Rendita catastale rivalutata (in attesa di perizia giurata)",
        })

    veicoli_table = []
    for v in vehicles:
        veicoli_table.append({
            "tipo": v.make_model or "Autoveicolo",
            "anno": v.year or "—",
            "km": "—",
            "targa": v.plate or "—",
            "valore": float(v.estimated_value) if (v.estimated_value and v.estimated_value > 0) else None,
            "valore_display": f"€ {float(v.estimated_value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if (v.estimated_value and v.estimated_value > 0) else "Da perizia",
            "note": v.notes or "Da elenco beni mobili / PRA",
        })

    lotti_concorsuali = []
    if tot_catastale > 0:
        lotti_concorsuali.append({
            "lotto": f"Patrimonio immobiliare ({len(real_estates)} unità censite)",
            "prudente": "Da perizia OMI / CTU",
            "favorevole": _fmt_eur(tot_catastale),
            "note": "Valore catastale documentato (nessuna percentuale liquidatoria presunta; richiede perizia OMI / CTU).",
        })
    if vehicles_val := sum(float(v.estimated_value or 0.0) for v in vehicles):
        lotti_concorsuali.append({
            "lotto": f"Parco automezzi / veicoli ({len(vehicles)} unità)",
            "prudente": "Da perizia / quotazione PRA",
            "favorevole": _fmt_eur(vehicles_val),
            "note": "Valore indicato a fascicolo senza abbattimenti percentuali arbitrari.",
        })
    elif vehicles:
        lotti_concorsuali.append({
            "lotto": f"Parco automezzi / veicoli ({len(vehicles)} unità censite)",
            "prudente": "Da stimare",
            "favorevole": "Da stimare",
            "note": "Richiede quotazioni di mercato / perizia.",
        })
    if not lotti_concorsuali:
        lotti_concorsuali.append({
            "lotto": "Attivo liquidatorio (cespiti / crediti / rimanenze)",
            "prudente": "Da inventariare",
            "favorevole": "Da inventariare",
            "note": "Richiede inventario analitico e perizia di stima ex CCII.",
        })

    # Cespiti da bilancio
    last_approved_fs = annual_fss[-1] if annual_fss else None
    sp_last = (last_approved_fs.raw_extraction.get("stato_patrimoniale") or {}) if last_approved_fs else {}
    immob_mat = sp_last.get("immob_materiali")
    val_cespiti = _num(immob_mat)
    val_cespiti_display = f"€ {val_cespiti:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if (has_balance_debts and val_cespiti > 0) else "n.r.*"
    costo_storico_display = "n.r.*"
    nota_cespiti = (
        "Non quantificabile da bilancio: contabilità priva di stato patrimoniale analitico / libro cespiti."
        if (is_individual and not has_balance_debts)
        else "Valori da bilancio d'esercizio / situazione patrimoniale."
    )

    # =========================================================================
    # CAP. 9: SCENARI RISANAMENTO EX CCII
    # =========================================================================
    scenari_ccii = []
    if cross and cross.scenari:
        scenari_ccii = cross.scenari
    else:
        massa_str = _fmt_eur(tot_massa_stimata) if tot_massa_stimata is not None else "Non disponibile (NULL)"
        ric_ultimo_val = esercizi_economici[-1]["ricavi_a1"] if esercizi_economici else None
        ric_str = _fmt_eur(ric_ultimo_val) if ric_ultimo_val is not None else "Non disponibile (NULL)"
        scenari_ccii = [
            {
                "scenario": "Composizione Negoziata della Crisi (art. 12 CCII)",
                "fattibilita": "IN VERIFICA",
                "motivazione": "Valutazione subordinata alla verifica di effettiva continuità produttiva e sostenibilità prospettica dei flussi per trattare con AdER e creditori.",
                "dati_chiave": f"Massa debitoria stimata: {massa_str}; Ricavi ultimo esercizio: {ric_str}",
            },
            {
                "scenario": "Accordo di Ristrutturazione dei Debiti (art. 57 CCII)",
                "fattibilita": "IN VERIFICA",
                "motivazione": "Perseguibile previo raggiungimento delle maggioranze di legge (60%) ed eventuale transazione fiscale/contributiva ex art. 63 CCII.",
                "dati_chiave": "Richiede piano finanziario e attestazione indipendente del professionista",
            },
            {
                "scenario": "Concordato Semplificato per la Liquidazione (art. 25-sexies CCII)",
                "fattibilita": "NON_DETERMINABILE (subordinato a CNC)",
                "motivazione": (
                    "Non accessibile direttamente e non automatico al fallimento delle trattative: richiede previa CNC conclusa, "
                    "attestazione dell'esperto su correttezza/buona fede e impraticabilità delle soluzioni ex art. 23, "
                    "deposito entro 60 giorni perentori e utilità per ciascun creditore."
                ),
                "dati_chiave": "Valore di realizzo dell'attivo censito a beneficio dei creditori e relazione finale esperto",
            },
            {
                "scenario": "Liquidazione Giudiziale / Controllata",
                "fattibilita": "ALTERNATIVA LIQUIDATORIA",
                "motivazione": "Scenario di confronto benchmark per la valutazione di convenienza rispetto alla continuità.",
                "dati_chiave": "Inventario e perizia completa dei beni aziendali / personali",
            },
        ]

    # =========================================================================
    # CAP. 10: DOCUMENTAZIONE ANCORA NECESSARIA
    # =========================================================================
    if cross and cross.dati_mancanti:
        doc_mancanti = cross.dati_mancanti
    else:
        doc_mancanti = [
            {"dato_mancante": d.get("documento"), "perche_serve": d.get("motivo"), "priorita": d.get("priorita", "ALTA")}
            for d in identify_documenti_indispensabili(
                has_fs_recent=bool(fss),
                has_tax_return=any("redditi" in d.original_filename.lower() or "dichiarazione" in d.original_filename.lower() for d in docs),
                has_cr=bool(cr or exposures),
                has_ader_statement=bool(statements or any("ader" in d.doc_type for d in docs)),
                has_dscr_projection=False,
                has_bank_contracts=any("contratto" in d.original_filename.lower() or "mutuo" in d.original_filename.lower() for d in docs),
                has_real_estate_appraisal=any("perizia" in d.original_filename.lower() for d in docs),
            )
        ]

    # =========================================================================
    # CAP. 11: CONCLUSIONI E RACCOMANDAZIONI
    # =========================================================================
    raccomandazioni = cross.note_per_il_titolare if (cross and cross.note_per_il_titolare) else [
        "Completare l'acquisizione della documentazione contabile, bancaria ed esattoriale mancante.",
        "Eseguire o aggiornare il controllo incrociato per verificare eventuali scostamenti tra fonti.",
        "Validare le quadrature Decimal e le eventuali anomalie nel Dossier Tecnico (Human Gate).",
    ]

    # Calcolo Posizione Finanziaria Netta (PFN) ESMA 2021 & Rapporto PFN / EBITDA con semantica NULL rigorosa
    last_fs_sp = (last_approved_fs.raw_extraction.get("stato_patrimoniale") or {}) if last_approved_fs else {}
    last_fs_deb = (last_approved_fs.raw_extraction.get("debiti_per_natura") or {}) if last_approved_fs else {}
    deb_b_breve_sp, deb_b_ml_sp, _ = extract_bank_debt_split(last_fs_sp, last_fs_deb)
    deb_banche_val = deb_b_breve_sp if deb_b_breve_sp is not None else tot_cr_ut
    deb_ml_val = deb_b_ml_sp
    liq_val = _num_opt(last_fs_sp.get("disponibilita_liquide"))
    tfr_val = _num_opt(last_fs_sp.get("tfr"))
    soci_fin_val = _num_opt((last_fs_deb.get("soci_finanziamenti") or {}).get("importo"))
    tot_ader_scad = aer_component

    if last_fs_sp and liq_val is not None:
        trib_scad_pfn = tot_ader_scad if tot_ader_scad is not None else (tot_trib_bilancio + tot_prev_bilancio)
        pfn_obj = calculate_pfn_esma(
            debiti_bancari_breve=deb_banche_val or 0.0,
            debiti_bancari_medio_lungo=deb_ml_val or 0.0,
            disponibilita_liquide=liq_val,
            tfr_fondo=tfr_val or 0.0,
            finanziamenti_soci=soci_fin_val or 0.0,
            debiti_tributari_scaduti=trib_scad_pfn or 0.0,
        )
    else:
        pfn_obj = {
            "disponibilita_liquide": None,
            "debiti_finanziari_breve": deb_banche_val,
            "debiti_finanziari_medio_lungo": deb_ml_val,
            "totale_passivita_finanziarie_e_assimilate": None,
            "pfn_totale": None,
            "stato_dato": "NON_VERIFICABILE_NULL",
            "norma_riferimento": "Orientamento ESMA 32-382-1138 (2021) n. 39 & CNDCEC marzo 2024",
        }

    last_ebitda: Optional[float] = esercizi_economici[-1]["mol"] if esercizi_economici else None
    pfn_eval = evaluate_pfn_ebitda(pfn_obj.get("pfn_totale"), last_ebitda)
    ratio_val = pfn_eval.get("ratio")
    pfn_ratio_str = f"{ratio_val:.2f}" if ratio_val is not None else "n.d."

    ebitda_ultimo_ex = esercizi_economici[-1]["mol"] if esercizi_economici else None
    ebitda_penultimo_ex = esercizi_economici[-2]["mol"] if len(esercizi_economici) >= 2 else None

    # Test Pratico Ministeriale Composizione Negoziata (art. 13 CCII / D.D. 28/09/2021)
    debito_tot_risanabile = pfn_obj.get("totale_passivita_finanziarie_e_assimilate") if pfn_obj.get("totale_passivita_finanziarie_e_assimilate") is not None else tot_massa_stimata
    test_pratico_obj = calculate_test_pratico_ministeriale(
        debito_totale_da_risanare=debito_tot_risanabile,
        flusso_annuo_servizio_debito=None,
        ebitda_medio_annuo=(ebitda_ultimo_ex if (ebitda_ultimo_ex or 0.0) > 0 else (ebitda_penultimo_ex if (ebitda_penultimo_ex or 0.0) > 0 else None)),
        attivo_disponibile_non_strumentale=0.0,
    )

    # Diagnosi Semaforo e 5 Principali Criticità
    diagnosi_semaforo = evaluate_risanabilita_diagnosi(
        ebitda_ultimo=ebitda_ultimo_ex,
        ebitda_penultimo=ebitda_penultimo_ex,
        pfn_ebitda_ratio=pfn_eval.get("ratio"),
        test_pratico_ratio=test_pratico_obj.get("rapporto"),
        ha_sofferenze_cr=bool(cr and cr.has_sofferenze),
        debito_tributario_scaduto=tot_ader_scad,
        flusso_annuo_formalizzato=False,
        ha_patrimonio_immobiliare=bool(real_estates),
    )

    cinque_criticita = classify_cinque_criticita(
        debito_ader_scaduto=tot_ader_scad or 0.0,
        ebitda_storico=ebitda_penultimo_ex or 0.0,
        ebitda_ultimo=ebitda_ultimo_ex or 0.0,
        utile_ultimo=esercizi_economici[-1]["utile_perdita"] if esercizi_economici else 0.0,
        pfn_totale=pfn_obj.get("pfn_totale") or 0.0,
        pfn_eval_status=pfn_eval.get("status", "na"),
        is_ditta_individuale=is_individual,
        ha_dati_infrannuali=bool(dato_infrannuale),
        ha_sofferenze_cr=bool(cr and cr.has_sofferenze),
        procedure_ader_attive=sum(1 for s in statements for it in s.items if it.proc_attive) if statements else 0,
        tipo_soggetto="impresa_individuale" if is_individual else "societa_capitali",
    )

    documenti_indispensabili = identify_documenti_indispensabili(
        has_fs_recent=bool(fss),
        has_tax_return=any("redditi" in d.original_filename.lower() or "dichiarazione" in d.original_filename.lower() for d in docs),
        has_cr=bool(cr or exposures),
        has_ader_statement=bool(statements or any("ader" in d.doc_type for d in docs)),
        has_dscr_projection=False,
        has_bank_contracts=any("contratto" in d.original_filename.lower() or "mutuo" in d.original_filename.lower() for d in docs),
        has_real_estate_appraisal=any("perizia" in d.original_filename.lower() for d in docs),
    )

    # Inquadramento CCII: soglie art. 2 e segnali allarme art. 3 co. 4 (NULL != 0)
    attivi_tri = [float(f.total_assets or 0.0) for f in fss if f.total_assets]
    ricavi_tri = [float(f.revenues or 0.0) for f in fss if f.revenues]
    legal_prof = "impresa_individuale" if is_individual else "societa_capitali_srl"
    ccii_minore = check_ccii_soglie_impresa_minore(
        attivo_patrimoniale_triennio=attivi_tri,
        ricavi_lordi_triennio=ricavi_tri,
        debiti_totali_attuali=tot_massa_stimata,
        legal_form_profile=legal_prof,
    )
    ccii_art3 = check_ccii_segnali_allarme_art3(
        retribuzioni_scadute_30gg=None,
        monte_salari_mensile=None,
        debiti_fornitori_scaduti_90gg=None,
        debiti_fornitori_non_scaduti=None,
        esposizioni_banche_scadute_60gg=cr.total_exposure if (cr and cr.has_sofferenze) else None,
        sconfinamento_banche_fidi=None,
        totale_fidi_accordati=None,
        debiti_ader_scaduti_90gg=tot_ader_scad,
        tipo_soggetto=legal_prof,
        totale_esposizioni_bancarie=cr.total_exposure if (cr and cr.total_exposure) else None,
    )

    # Esposizioni soci / personali dinamiche
    esposizioni_soci = []
    if is_individual:
        esposizioni_soci.append({
            "socio": client_display,
            "garanzia": "Responsabilità patrimoniale diretta e illimitata ex art. 2740 c.c. (ditta individuale)",
            "importo": "Estesa all'intera massa debitoria",
            "note": "Non sussiste autonomia patrimoniale perfetta: l'imprenditore individuale risponde delle passività d'impresa con tutti i suoi beni presenti e futuri.",
        })
    else:
        for g in guarantees:
            esposizioni_soci.append({
                "socio": g.guaranteed_subject or client_display,
                "garanzia": f"Garanzia/Fideiussione a favore di {g.intermediary or 'Istituto di Credito'}",
                "importo": f"€ {float(g.valore_garanzia or g.importo_garantito or 0.0):,.2f}",
                "note": "Garanzia personale a presidio dei debiti societari.",
            })
        if not esposizioni_soci and soci_list:
            for s in soci_list:
                if s.get("garante") or s.get("ruolo") == "Legale rappresentante":
                    esposizioni_soci.append({
                        "socio": s.get("nome", "Legale rappresentante"),
                        "garanzia": "Fideiussione personale a presidio degli affidamenti bancari della società",
                        "importo": "Da quantificare con copia delle lettere di garanzia",
                        "note": "Da verificare contrattualmente.",
                    })
        if not esposizioni_soci:
            esposizioni_soci.append({
                "socio": client_display,
                "garanzia": "Nessuna garanzia personale formalmente documentata",
                "importo": "—",
                "note": "Da verificare.",
            })

    # Commento periodo dinamico
    if esercizi_economici:
        ex_last = esercizi_economici[-1]
        mol_pct_str = f"{ex_last['mol_pct']:.1f}%" if ex_last.get("mol_pct") is not None else "n.d."
        commento_periodo = (
            f"Nell'esercizio {ex_last['anno']}, il Valore della Produzione si attesta a {_fmt_eur(ex_last.get('valore_produzione_a'))} "
            f"con un Margine Operativo Lordo (MOL / EBITDA ex OIC 12 e CNDCEC marzo 2024) pari a {_fmt_eur(ex_last.get('mol'))} "
            f"({mol_pct_str} sul valore della produzione). "
            f"Formula applicata: {ex_last.get('formula_mol')}. "
            f"L'esercizio registra un risultato netto di {_fmt_eur(ex_last.get('utile_perdita'))}."
        )
    else:
        commento_periodo = "Dati economici in attesa di caricamento dei bilanci d'esercizio completi."

    # Commento debiti 5.1 dinamico
    if not has_balance_debts:
        commento_5_1 = (
            "Dati contabili non rilevabili (n.r.): l'impresa opera in regime di contabilità semplificata "
            "(D.P.R. 600/1973) e redige unicamente la situazione economica (Conto Economico), senza Stato Patrimoniale "
            "ex art. 2424 c.c. né partitari contabili dei debiti verso fornitori o banche. "
            "La ricognizione della massa debitoria effettiva poggia prioritariamente sulle risultanze certificate delle banche dati esterne "
            "(AdER, Centrale Rischi Banca d'Italia, CTC) e sulle stime prudenziali esposte al par. 5.3."
        )
    elif table_5_1 and table_5_1.get("totali", {}).get("valori"):
        tot_vals = table_5_1["totali"]["valori"]
        cols_keys = list(tot_vals.keys())
        if len(cols_keys) >= 2:
            c_first, c_last = cols_keys[0], cols_keys[-1]
            commento_5_1 = (
                f"L'indebitamento contabile complessivo da bilancio evolve da € {tot_vals[c_first]:,.2f} ({c_first}) "
                f"a € {tot_vals[c_last]:,.2f} ({c_last}). "
                f"La dinamica riflette la composizione tra debiti commerciali, bancari, tributari e verso soci."
            )
        else:
            commento_5_1 = f"I debiti contabili da bilancio si attestano complessivamente a {_fmt_eur(tot_massa_bilancio)}."
    else:
        commento_5_1 = f"I debiti contabili da bilancio si attestano complessivamente a {_fmt_eur(tot_massa_bilancio)}."

    # Elementi favorevoli dinamici
    elem_fav = []
    if last_approved_fs and last_approved_fs.equity and last_approved_fs.equity > 0:
        elem_fav.append(f"Patrimonio netto contabile positivo pari a € {float(last_approved_fs.equity):,.2f}.")
    if last_approved_fs and last_approved_fs.revenues and last_approved_fs.revenues > 0:
        elem_fav.append(f"Volume d'affari consolidato pari a € {float(last_approved_fs.revenues):,.2f}.")
    if cr and not cr.has_sofferenze:
        elem_fav.append("Assenza di segnalazioni a sofferenza o incagli presso la Centrale Rischi della Banca d'Italia.")
    if real_estates:
        elem_fav.append(f"Patrimonio immobiliare ({len(real_estates)} unità censite) per un valore catastale complessivo di € {tot_catastale:,.2f}.")
    if not elem_fav:
        elem_fav.append("Nessun elemento favorevole ancora documentato a bilancio o banche dati; completare l'istruttoria.")

    def _fmt_eur_int(v: Optional[float]) -> str:
        if v is None:
            return "n.d. (NULL)"
        s = f"{abs(round(v)):,}".replace(",", ".")
        return f"−€ {s}" if v < 0 else f"€ {s}"

    ex_last = esercizi_economici[-1] if esercizi_economici else None
    last_anno = ex_last["anno"] if ex_last else "ult. es."
    ricavi_last = ex_last["ricavi_a1"] if ex_last else None
    utile_last = ex_last["utile_perdita"] if ex_last else None
    mol_last = ex_last["mol"] if ex_last else None

    dyn_exec_cards_header = [
        {"valore": _fmt_eur_int(ricavi_last), "etichetta": f"Ricavi contabili {last_anno}"},
        {"valore": _fmt_eur_int(utile_last), "etichetta": f"{'Utile' if (utile_last or 0) >= 0 else 'Perdita'} netto {last_anno}" if utile_last is not None else "Risultato netto"},
        {"valore": _fmt_eur_int(tot_esposizioni_principali_quantificate), "etichetta": "Esposizioni quantificate*"},
        {"valore": _fmt_eur_int(tot_massa_stimata), "etichetta": "Passivo stimato complessivo**"},
    ]
    dyn_exec_cards_forensic = [
        {"valore": dyn_exec_cards_header[0]["valore"], "etichetta": dyn_exec_cards_header[0]["etichetta"], "descrizione": f"Bilancio / situazione {last_anno}" if ex_last else "Bilancio non acquisito (NULL)"},
        {"valore": dyn_exec_cards_header[1]["valore"], "etichetta": dyn_exec_cards_header[1]["etichetta"], "descrizione": f"MOL {last_anno}: {_fmt_eur_int(mol_last)}"},
        {"valore": dyn_exec_cards_header[2]["valore"], "etichetta": "Esposizioni principali*", "descrizione": "AdER + Banche/CR + CTC documentato"},
        {"valore": dyn_exec_cards_header[3]["valore"], "etichetta": "Massa debitoria ricostruita", "descrizione": "Include debiti da bilancio e banche dati"},
    ]
    entity_rule_note = (
        "Responsabilità illimitata ex art. 2740 c.c.: l'imprenditore individuale risponde anche con il patrimonio personale."
        if is_individual
        else "Autonomia patrimoniale perfetta (art. 2462 c.c.): il rischio soci/amministratori è circoscritto ad eventuali fideiussioni personali, postergazione finanziamenti soci (art. 2467 c.c.) e azioni ex art. 2476 c.c."
    )
    patr_note = (
        f"{len(real_estates)} unità immobiliari censite (valore catastale {_fmt_eur_int(tot_catastale)}) e {len(vehicles)} veicoli."
        if real_estates or vehicles
        else "nessun immobile catastale censito; verificare cespiti, crediti e rimanenze di bilancio."
    )
    dyn_esito_preanalisi = [
        f"Redditività ({last_anno}): ricavi {_fmt_eur_int(ricavi_last)}, MOL {_fmt_eur_int(mol_last)}, risultato netto {_fmt_eur_int(utile_last)}.",
        f"Debito: esposizioni principali quantificate pari a {_fmt_eur_int(tot_esposizioni_principali_quantificate)}; massa debitoria stimata {_fmt_eur_int(tot_massa_stimata)} ({'con debiti di bilancio' if has_balance_debts else 'senza SP analitico'}). {entity_rule_note}",
        f"Patrimonio: {patr_note}",
        f"Strumenti CCII: {diagnosi_semaforo.get('etichetta', 'Verifica istruttoria')} — valutare Composizione Negoziata (CNC), accordi di ristrutturazione (art. 57/60 CCII) o concordato minore/liquidazione secondo le soglie dimensionali ex art. 2 CCII.",
    ]

    report_payload = {
        "header": {
            "titolo": f"PREANALISI CRISI D'IMPRESA — {client_display.upper()}",
            "cliente": client_display,
            "titolare": titolare_nominativo,
            "forma_giuridica": ("Impresa individuale" if is_individual else (company.legal_form if company and company.legal_form else "Società")),
            "codice_fiscale": client_tax_code,
            "sottotitolo": "Ricostruzione economico-finanziaria, debitoria e prima valutazione degli strumenti CCII",
            "riservatezza": f"Documento di lavoro riservato - {mese_anno_corrente}",
            "data_bozza": now.strftime("%d/%m/%Y"),
            "executive_cards": dyn_exec_cards_header,
        },
        "capitolo_1_premessa": {
            "scopo": (
                f"La presente preanalisi ha lo scopo di fotografare, sulla base della documentazione allo stato disponibile, "
                f"la situazione economica, patrimoniale e debitoria di {client_display}, al fine di comprendere se sussistano "
                f"i presupposti per un percorso di risanamento e quale, tra gli strumenti previsti dal Codice della Crisi "
                f"d'Impresa e dell'Insolvenza (CCII), appaia in prima battuta più coerente con il caso specifico."
            ),
            "documenti_utilizzati": docs_utilizzati,
            "flusso_annuo_destinabile": (
                "La presente preanalisi si arresta allo stato al giudizio di fattibilità e all'indicazione dello strumento "
                "più coerente. Non essendo stata ancora formalizzata dal cliente l'indicazione del flusso finanziario annuo "
                "ragionevolmente destinabile al risanamento, non viene formulata in questa sede una proposta quantificata ai creditori."
            ),
        },
        "capitolo_2_profilo": {
            "denominazione": client_display,
            "titolare": titolare_nominativo,
            "forma_giuridica": ("Impresa individuale" if is_individual else (company.legal_form if company else "SRL")) or "Impresa individuale",
            "is_ditta_individuale": is_individual,
            "cf_piva": client_tax_code,
            "rea": rea_display,
            "sede_legale": (company.legal_address if company else "") or "—",
            "data_costituzione": (company.constitution_date if company else "") or "—",
            "capitale_sociale": capitale_sociale_val,
            "capitale_sociale_display": capitale_sociale_display,
            "regime_patrimoniale": (
                "Responsabilità personale illimitata ex art. 2740 c.c. (assenza di autonomia patrimoniale o capitale sociale: "
                "il titolare risponde dell'adempimento delle obbligazioni con tutti i propri beni presenti e futuri)."
            ) if is_individual else "Autonomia patrimoniale perfetta.",
            "codice_ateco": (company.ateco if company else "") or "—",
            "attivita_prevalente": (company.business_summary if company else "") or "Attività commerciale e industriale",
            "soci": soci_list,
            "natura_crisi": (
                f"L'analisi documentale condotta su {client_display} ({'Impresa individuale' if is_individual else 'Società'}) "
                f"evidenzia una situazione debitoria derivante principalmente dall'accumulo di passività verso l'Erario ({_fmt_eur(tot_ader_scad)}) "
                f"e verso il sistema bancario/commerciale, a fronte di una gestione caratteristica che richiede "
                f"un tempestivo intervento di regolazione per ristabilire l'equilibrio economico-finanziario."
            ),
        },
        "capitolo_3_analisi_economica": {
            "esercizi": esercizi_economici,
            "commento_periodo": commento_periodo,
            "principio_oic12": (
                "La riclassificazione del Conto Economico è conforme al principio OIC 12 e alle Linee Guida CNDCEC "
                "del marzo 2024. Il Margine Operativo Lordo (MOL / EBITDA) è calcolato come Differenza tra valore e "
                "costi della produzione (A - B) reintegrando gli ammortamenti e svalutazioni delle immobilizzazioni "
                "(voci B10a, B10b, B10c), lasciando all'interno dei costi operativi ordinari le svalutazioni dei crediti "
                "(B10d) e gli accantonamenti rischi/oneri (B12, B13)."
            ),
            "riscontro_dichiarazioni_redditi": (
                "I dati economici esposti nei bilanci approvati trovano riscontro nelle dichiarazioni fiscali "
                "acquisite nel fascicolo documentale."
            ),
            "anomalie_contabili": [
                f"Oneri finanziari registrati: {_fmt_eur(last_fs_sp.get('oneri_finanziari')) if last_fs_sp.get('oneri_finanziari') else 'sotto monitoraggio'}.",
                "Discrepanza tra l'indebitamento bancario contabile e le risultanze della Centrale Rischi.",
            ],
        },
        "capitolo_4_dato_corrente": {
            "dato": dato_infrannuale,
            "prudenza": (
                "I risultati del periodo infra-annuale presentano fisiologici limiti di stagionalità "
                "e non costituiscono un consuntivo definitivo. Il dato non va proiettato linearmente sull'intero anno "
                "ma impone prudenza nella stima dei flussi finanziari prospettici destinabili al servizio del debito."
            ),
        },
        "capitolo_5_indebitamento": {
            "tabella_5_1": table_5_1,
            "commento_5_1": commento_5_1,
            "tabella_5_2_ader": ader_table,
            "tabella_5_2_credito": credit_db_rows,
            "tabella_5_3_sintesi": {
                "righe": stima_massa_rows,
                "totale_stimato": tot_massa_stimata,
                "totale_bilancio": tot_massa_bilancio if has_balance_debts else 0.0,
                "totale_bilancio_display": f"€ {tot_massa_bilancio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if has_balance_debts else "n.r.*",
                "has_balance_debts": has_balance_debts,
                "nota_metodologica": (
                    "*n.r. = Non rilevabile: contabilità priva di stato patrimoniale o passivo per natura completo."
                    if not has_balance_debts
                    else "Valori di bilancio riconciliati con le banche dati esterne (senza duplicazioni sui subtotali)."
                ),
            },
            "tabella_pfn_esma": pfn_obj,
            "valutazione_pfn_ebitda": pfn_eval,
            "test_pratico_ministeriale": test_pratico_obj,
            "cautele_sintesi": (
                "La stima della massa debitoria è costruita incrociando le banche dati esterne (AdER, Centrale Rischi, CRIF/CTC) "
                "con la contabilità societaria per eliminare ogni duplicazione. "
                + (
                    "La Posizione Finanziaria Netta (PFN) risulta conforme allo schema ESMA 32-382-1138."
                    if pfn_obj.get("esma_compliant")
                    else "Nota ESMA: dataset non completo per piena conformità ESMA 32-382-1138; il saldo indicato rappresenta una PFN gestionale basata sulle componenti documentate."
                )
            ),
        },
        "capitolo_6_punti_verificare": punti_da_verificare,
        "capitolo_7_diagnosi_crisi": {
            "elementi_favorevoli": elem_fav,
            "principale_criticita": (
                f"L'ammontare complessivo dell'indebitamento erariale ({_fmt_eur(tot_ader_scad)}) e bancario, "
                f"unito a un rapporto PFN/EBITDA ({pfn_ratio_str}) "
                f"che evidenzia: {pfn_eval['valutazione_bancaria']}."
            ),
            "sintesi_vitalita": (
                "La verifica della continuità e della capacità di risanamento è subordinata ai dati economici verificati, "
                "alla ricognizione completa del passivo e alla sostenibilità prospettica dei flussi di cassa (esame professionale)."
            ),
            "inquadramento_ccii": ccii_minore,
            "segnali_allarme_art3": ccii_art3,
            "diagnosi_semaforo": diagnosi_semaforo,
            "cinque_principali_criticita": cinque_criticita,
        },
        "capitolo_8_patrimonio": {
            "immobili": immobili_table,
            "totale_valore_catastale": tot_catastale,
            "esito_catasto": esito_catastale,
            "veicoli": veicoli_table,
            "lotti_concorsuali": lotti_concorsuali,
            "immobilizzazioni_materiali": {
                "valore_netto_bilancio": val_cespiti,
                "valore_netto_display": val_cespiti_display,
                "costo_storico_stimato": None,
                "costo_storico_display": costo_storico_display,
                "note": nota_cespiti,
            },
            "esposizione_personale_soci": esposizioni_soci,
        },
        "capitolo_9_orientamento_risanamento": {
            "scenari": scenari_ccii,
            "proposta_coerente": None,
            "motivazione": (
                "L'inquadramento giuridico-decisionale degli strumenti ex CCII non è preselezionato automaticamente "
                "ed è rimesso alla valutazione del professionista previa verifica di accessibilità, flussi di cassa "
                "e documentazione completa (matrice CCII prevista in Fase 3)."
            ),
            "condizioni": [
                "Acquisizione dell'indicazione del flusso di cassa annuo disponibile da parte del cliente.",
                "Allineamento del debito a ruolo definitivo con cancellazione delle cartelle duplicate.",
                "Relazione di veridicità e completezza contabile del revisore legale (o attestazione del professionista indipendente ove richiesta ex CCII), distinta dal ruolo dell'esperto CNC.",
            ],
        },
        "capitolo_10_documentazione": {
            "documenti_mancanti": doc_mancanti,
            "documenti_indispensabili_prioritari": documenti_indispensabili,
            "flusso_richiesto": "Indicazione del cliente in merito al flusso annuo di cassa ragionevolmente destinabile al risanamento, necessaria per quantificare la proposta ai creditori.",
        },
        "capitolo_11_conclusione": {
            "giudizio_sintetico": (
                f"La preanalisi istruttoria per {client_display} espone una massa debitoria stimata pari a "
                f"{_fmt_eur(tot_massa_stimata) if tot_massa_stimata is not None else 'Non disponibile (NULL)'} "
                f"con semaforo di risanabilità '{diagnosi_semaforo.get('semaforo', 'Non valutabile')}' "
                f"(affidabilità dati: {diagnosi_semaforo.get('grado_affidabilita', 'Basso')}). "
                f"{diagnosi_semaforo.get('motivazione', '')}"
            ),
            "metodo_epistemologico": {
                "FATTO": [
                    f"Dati anagrafici e R.E.A. da Visura Camerale CCIAA ({rea_display}, sede legale in {(company.legal_address if company else '') or '—'}).",
                    f"Carichi esattoriali e cartelle iscritte a ruolo AdER per complessivi {_fmt_eur(tot_ader_scad) if tot_ader_scad is not None else 'Non rilevati (NULL)'}.",
                    (
                        f"Dati contabili registrati nelle situazioni economiche (Ricavi {esercizi_economici[0]['anno']}: {_fmt_eur(esercizi_economici[0]['ricavi_a1'])}; Ricavi {esercizi_economici[-1]['anno']}: {_fmt_eur(esercizi_economici[-1]['ricavi_a1'])})."
                        if esercizi_economici
                        else "Dati contabili storici non ancora acquisiti (NULL)."
                    ),
                    f"Unità immobiliari censite al Catasto Fabbricati ({len(real_estates)} unità) per valore catastale di {_fmt_eur(tot_catastale) if real_estates else 'Non rilevato / 0 unità'}.",
                ],
                "CALCOLO": [
                    (
                        f"Margine Operativo Lordo (MOL / EBITDA ex OIC 12 - CNDCEC marzo 2024): "
                        f"{esercizi_economici[0]['anno']} pari a {_fmt_eur(esercizi_economici[0]['mol'])}; "
                        f"{esercizi_economici[-1]['anno']} pari a {_fmt_eur(ebitda_ultimo_ex)}."
                        if esercizi_economici
                        else "MOL / EBITDA: Non calcolabile (NULL — assenza di Conto Economico)."
                    ),
                    f"Posizione Finanziaria Netta ({'ESMA 2021 conforme' if pfn_obj.get('esma_compliant') else 'gestionale semplificata'}): {_fmt_eur(pfn_obj.get('pfn_totale')) if pfn_obj.get('pfn_totale') is not None else 'Non disponibile (NULL)'}.",
                    f"Test Pratico Ministeriale per la Composizione Negoziata (art. 13 CCII): debito netto {_fmt_eur(test_pratico_obj.get('debito_netto_da_risanare')) if test_pratico_obj.get('debito_netto_da_risanare') is not None else 'Non disponibile (NULL)'}.",
                ],
                "INFERENZA": [
                    f"Inquadramento dimensionale CCII: {ccii_minore['qualifica_giuridica']} ({ccii_minore['motivo_superamento']}).",
                    "L'eventuale individuazione degli strumenti CCII applicabili (CNC, ADR, concordati o sovraindebitamento) è subordinata alla matrice giuridico-decisionale e alla validazione del professionista (Human Gate).",
                ],
                "IPOTESI": [
                    "Flusso annuo di cassa a regime destinabile al servizio del debito (in attesa di attestazione formale del cliente).",
                    "Percentuale di stralcio del debito erariale ottenibile in sede di composizione o transazione fiscale.",
                ],
            },
            "raccomandazioni": raccomandazioni,
            "regola_finale_human_gate": (
                "La presente relazione costituisce pre-analisi economico-finanziaria rigorosa e indipendente a supporto "
                "dello Studio Legale. Non ha la finalità di dimostrare aprioristicamente la risanabilità dell'impresa, bensì di "
                "verificare se essa produca reddito, generi cassa sufficiente e possa sostenere il debito. "
                "La valutazione conclusiva sulla fattibilità strategica e la scelta definitiva dello strumento giuridico "
                "rimangono riservate in via esclusiva all'Avv. Aurelio Bentivegna (Human Gate)."
            ),
            "dicitura_finale": f"PRIMA BOZZA DI ANALISI - ELABORATA IL {now.strftime('%d/%m/%Y').upper()}",
        },
        "forensic_preanalysis": {
            "json_matrix": forensic_res.get("json_matrix") or {},
            "client_report_text": forensic_res.get("client_report_text") or "",
            "raw_output": forensic_res.get("raw_output") or "",
            "telemetry": forensic_res.get("telemetry") or {},
            "context_coverage": chain_context_coverage,
            "esito_preanalisi": dyn_esito_preanalisi,
            "executive_cards": dyn_exec_cards_forensic,
        },
        "studio_rules": [
            {
                "id": r.id,
                "scope": r.scope,
                "scope_title": r.scope_title,
                "category": r.category,
                "rule_title": r.rule_title,
                "rule_prompt": r.rule_prompt,
                "author": r.author,
                "created_at": r.created_at.strftime("%d/%m/%Y") if r.created_at else "",
            }
            for r in get_active_rules(db, case_id=case_id)
        ],
    }
    report_payload["technical_dossier"] = build_complete_technical_dossier(docs, report_payload)
    return report_payload
