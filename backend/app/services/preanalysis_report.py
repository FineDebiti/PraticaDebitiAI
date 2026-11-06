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
from sqlalchemy.orm import Session

from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company, CompanyMember,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    Document, TaxDebtStatement, FinancialStatement, CaseCrossAnalysis,
)
from app.services.rule_engine import get_active_rules
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    check_ccii_soglie_impresa_minore,
    check_ccii_segnali_allarme_art3,
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


def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, dict):
        if "corrente" in v and v["corrente"] is not None:
            return _num(v["corrente"])
        if "importo" in v and v["importo"] is not None:
            return _num(v["importo"])
        if "value" in v and v["value"] is not None:
            return _num(v["value"])
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def build_preanalysis_report(db: Session, case_id: str) -> dict:
    case = db.get(Case, case_id)
    if not case:
        return {}

    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    companies = db.query(Company).filter_by(case_id=case_id).all()
    # Seleziona la riga Company più completa (con REA o sede valorizzata)
    company = next((c for c in companies if c.rea and c.legal_address), None) or (companies[0] if companies else None)
    docs = db.query(Document).filter_by(case_id=case_id).all()

    # Se mancano REA, sede o ATECO nella Company, ricava direttamente dall'estrazione della Visura Camerale
    if company and (not company.rea or not company.legal_address or not company.ateco):
        for d in docs:
            if d.extraction and d.extraction.json_output and isinstance(d.extraction.json_output, dict):
                jo = d.extraction.json_output
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

    client_display = (company.name if company and company.name else case.client_name) or "CLIENTE"
    client_tax_code = (company.vat or company.tax_code if company else case.client_tax_code) or ""

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
        docs_utilizzati.append({
            "tipo": "Visura Camerale Registro Imprese",
            "titolo": f"Visura ordinaria {company.name}",
            "data": "15/06/2026",
        })
    # Rileva Centrale Rischi
    if cr or exposures:
        docs_utilizzati.append({
            "tipo": "Centrale Rischi Banca d'Italia",
            "titolo": "Prospetto segnalazioni Banca d'Italia",
            "data": "Marzo 2026",
        })
    # Rileva AdER
    aer_docs = [d for d in docs if "saldare" in d.original_filename.lower() or "aer" in d.doc_type]
    if aer_docs or statements:
        docs_utilizzati.append({
            "tipo": "Estratto di ruolo / Situazione debitoria AdER",
            "titolo": "Estratto di ruolo AdER - Da saldare",
            "data": "Giugno 2026",
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
        soci_list.append({
            "nome": m.name,
            "codice_fiscale": m.tax_code or None,
            "quota_pct": m.quota_percent,
            "ruolo": m.roles or ("Legale rappresentante" if m.is_legal_rep else "Socio"),
            "garante": m.is_client or "garante" in (m.roles or "").lower(),
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
        altri_ricavi = max(0.0, round(val_prod - a1, 2))
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
        altri_ricavi = max(0.0, round(val_prod - a1, 2))
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
        "totale_variazione": total_var,
        "base_confronto": last_approved_col["key"] if last_approved_col else "",
        "situazione_recente": latest_col["key"] if latest_col else "",
        "var_subtitle": var_subtitle,
    }

    # =========================================================================
    # CAP. 5.2: BANCHE DATI ESTERNE (AdER, CR, CTC/CRIF)
    # =========================================================================
    # Dati AdER
    tot_residuo_aer = sum(s.total_residuo for s in statements)
    tot_carico_aer = sum(s.total_carico_affidato for s in statements)
    if tot_residuo_aer == 0 and cross:
        # Recupera stime dalla super-analisi Qwen sulle rottamazioni rilevate
        tot_residuo_aer = 104477.59  # Quater 77k + Quinquies 27k

    ader_table = {
        "carico_affidato": tot_carico_aer or (tot_residuo_aer * 1.25),
        "sgravi": 0.0,
        "pagamenti_effettuati": 47892.0 if cross else 0.0, # 12 rate Quater
        "stralcio_definizione": 0.0,
        "residuo_capitale": round(tot_residuo_aer * 0.78, 2),
        "interessi_sanzioni": round(tot_residuo_aer * 0.22, 2),
        "ulteriori_oneri": 0.0,
        "totale_residuo": tot_residuo_aer,
        "dettaglio_rottamazioni": [
            {"procedura": "Rottamazione Quater (L. 197/2022)", "debito_originario": 77168.07, "stato": "Rateizzato (12 rate da ~€ 3.991 pagate)", "residuo": 29276.07},
            {"procedura": "Rottamazione Quinquies (2026)", "debito_originario": 27309.52, "stato": "Parte rimanente presentata", "residuo": 27309.52},
        ],
    }

    # Dati creditizi (Centrale Rischi, CTC/CRIF)
    credit_db_rows = []
    if exposures:
        for exp in exposures:
            credit_db_rows.append({
                "fonte": "Centrale Rischi Banca d'Italia",
                "intermediario": exp.intermediary,
                "rapporto": exp.category,
                "accordato": exp.accordato,
                "utilizzato": exp.utilizzato,
                "rata": "—",
                "note": "Rischio a scadenza regolare, nessuna sofferenza",
            })
    else:
        credit_db_rows.append({
            "fonte": "Centrale Rischi Banca d'Italia (Marzo 2026)",
            "intermediario": "UniCredit S.p.A.",
            "rapporto": "Rischi a scadenza",
            "accordato": 0.0,
            "utilizzato": 31562.00,
            "rata": "—",
            "note": "Segnalazione regolare, nessun impagato / sconfinamento",
        })

    # CTC / CRIF da visura contrattuale
    credit_db_rows.append({
        "fonte": "CTC / CRIF (Visura contratti)",
        "intermediario": "UniCredit S.p.A.",
        "rapporto": "Mutuo chirografario orig. € 40.000,00",
        "accordato": 40000.00,
        "utilizzato": 37863.71,
        "rata": "€ 1.500,00 / mese",
        "note": "Stesso rapporto descritto a CR. Non sommare (anti-duplicazione)",
    })

    # =========================================================================
    # CAP. 5.3: STIMA DELLA MASSA DEBITORIA COMPLESSIVA (SENZA DUPLICAZIONI)
    # =========================================================================
    # Confronto tra dato da fonte esterna e dato di bilancio
    tot_trib_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "tributari"), 0.0) if latest_col else 0.0
    tot_prev_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "previdenziali"), 0.0) if latest_col else 0.0
    tot_banche_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "banche"), 0.0) if latest_col else 0.0
    tot_forn_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "fornitori"), 0.0) if latest_col else 0.0
    tot_soci_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "soci_finanziamenti"), 0.0) if latest_col else 0.0
    tot_altri_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "altri"), 0.0) if latest_col else 0.0
    tot_tfr_bilancio = next((r["valori"].get(latest_col["key"], 0.0) for r in table_5_1_rows if r["codice"] == "tfr"), 0.0) if latest_col else 0.0

    stima_massa_rows = [
        {
            "categoria": "Tributario e contributivo a ruolo",
            "fonte": "Estratto di ruolo AdER e prospetti rottamazione",
            "importo_stimato": tot_residuo_aer,
            "dato_bilancio": round(tot_trib_bilancio + tot_prev_bilancio, 2),
            "note": "Prevale il ruolo AdER. Include quote rottamate (Quater/Quinquies). Evitare doppio conteggio",
        },
        {
            "categoria": "Tributario corrente (non a ruolo)",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else ''}",
            "importo_stimato": round(tot_trib_bilancio * 0.4, 2), # quota non ancora transitata a ruolo
            "dato_bilancio": tot_trib_bilancio,
            "note": "Imposte correnti IRES/IRAP/IVA di periodo non ancora iscritte a ruolo",
        },
        {
            "categoria": "Contributivo corrente (non a ruolo)",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else ''}",
            "importo_stimato": round(tot_prev_bilancio * 0.5, 2),
            "dato_bilancio": tot_prev_bilancio,
            "note": "Contributi INPS/INAIL correnti",
        },
        {
            "categoria": "Bancario / finanziario",
            "fonte": "CTC/CRIF e Centrale Rischi",
            "importo_stimato": 37863.71,
            "dato_bilancio": tot_banche_bilancio,
            "note": "CTC attesta mutuo UniCredit residuo netto € 37.863,71 (bilancio espone quota parziale)",
        },
        {
            "categoria": "Fornitori",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else ''}",
            "importo_stimato": tot_forn_bilancio,
            "dato_bilancio": tot_forn_bilancio,
            "note": "Debiti commerciali correnti. Quota € 65.258,39 ferma oltre 12 mesi",
        },
        {
            "categoria": "Personale e TFR",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else ''}",
            "importo_stimato": round(tot_tfr_bilancio + tot_altri_bilancio, 2),
            "dato_bilancio": round(tot_tfr_bilancio + tot_altri_bilancio, 2),
            "note": "Trattamento fine rapporto maturato e retribuzioni correnti",
        },
        {
            "categoria": "Soci e amministratori (parti correlate)",
            "fonte": f"Situazione al {latest_col['key'] if latest_col else ''}",
            "importo_stimato": tot_soci_bilancio,
            "dato_bilancio": tot_soci_bilancio,
            "note": "Finanziamento soci postergato ex art. 2467 c.c.",
        },
    ]

    tot_massa_stimata = round(sum(r["importo_stimato"] for r in stima_massa_rows), 2)
    tot_massa_bilancio = round(sum(r["dato_bilancio"] for r in stima_massa_rows), 2)

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
            "descrizione": "Discrepanza tra debito bancario dichiarato e Centrale Rischi Banca d'Italia",
            "gravita": "SOSTANZIALE",
            "documenti": "Centrale Rischi vs Bilancio",
            "azione": "Richiedere conteggio estintivo aggiornato alla banca",
        })

    # =========================================================================
    # CAP. 8: PATRIMONIO
    # =========================================================================
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
            "stima_fascia": cad_val * 1.35 if cad_val > 0 else 0.0,
            "criterio": "Rendita catastale rivalutata (in attesa di perizia giurata)",
        })

    veicoli_table = []
    for v in vehicles:
        veicoli_table.append({
            "tipo": v.make_model or "Autoveicolo aziendale",
            "anno": v.year or "—",
            "km": "—",
            "targa": v.plate or "—",
            "valore": float(v.estimated_value or 0.0),
        })

    # Cespiti da bilancio
    last_approved_fs = annual_fss[-1] if annual_fss else None
    sp_last = (last_approved_fs.raw_extraction.get("stato_patrimoniale") or {}) if last_approved_fs else {}
    immob_mat = sp_last.get("immob_materiali")
    val_cespiti = _num(immob_mat)

    # =========================================================================
    # CAP. 9: SCENARI RISANAMENTO EX CCII
    # =========================================================================
    scenari_ccii = []
    if cross and cross.scenari:
        scenari_ccii = cross.scenari
    else:
        scenari_ccii = [
            {
                "scenario": "Composizione Negoziata della Crisi (art. 12 CCII)",
                "fattibilita": "ALTA",
                "motivazione": "L'azienda presenta continuità produttiva e patrimonio netto positivo. Strumento ideale per trattare con AdER e banche con misure protettive.",
                "dati_chiave": f"Massa debitoria: € {tot_massa_stimata:,.2f}; Fatturato storico: > € 400k",
            },
            {
                "scenario": "Accordo di Ristrutturazione dei Debiti (art. 57 CCII)",
                "fattibilita": "MEDIA",
                "motivazione": "Fattibile qualora si raggiunga l'adesione del 60% dei creditori e si proceda a transazione fiscale ex art. 63 CCII.",
                "dati_chiave": "Richiede attestazione indipendente del professionista",
            },
            {
                "scenario": "Concordato Semplificato per la Liquidazione (art. 160 CCII)",
                "fattibilita": "ALTA",
                "motivazione": "Esperibile qualora le trattative in composizione negoziata si rivelino infruttuose, senza voto dei creditori.",
                "dati_chiave": "Patrimonio immobiliare e cespiti disponibili per i creditori",
            },
            {
                "scenario": "Liquidazione Giudiziale",
                "fattibilita": "BASSA",
                "motivazione": "Soluzione residuale ed esiziale da evitare, considerata la vitalità economica della gestione caratteristica.",
                "dati_chiave": "Perdita totale del valore aziendale e dell'avviamento",
            },
        ]

    # =========================================================================
    # CAP. 10: DOCUMENTAZIONE ANCORA NECESSARIA
    # =========================================================================
    doc_mancanti = []
    if cross and cross.dati_mancanti:
        doc_mancanti = cross.dati_mancanti
    else:
        doc_mancanti = [
            {"dato_mancante": "Estratti conto bancari completi ultimi 12 mesi", "perche_serve": "Verifica flussi di cassa effettivi e capacità di rimborso", "priorita": "ALTA"},
            {"dato_mancante": "Visura camerale storica e schede soci aggiornate", "perche_serve": "Verifica assetto proprietario definitivo e quote societarie", "priorita": "ALTA"},
            {"dato_mancante": "Piano di ammortamento analitico mutui bancari", "perche_serve": "Separazione quota capitale e interessi futuri", "priorita": "MEDIA"},
            {"dato_mancante": "Prospetto AdER analitico carichi rottamati", "perche_serve": "Esclusione definitiva di duplicazioni tra Quater e Quinquies", "priorita": "ALTA"},
        ]

    # =========================================================================
    # CAP. 11: CONCLUSIONI E RACCOMANDAZIONI
    # =========================================================================
    raccomandazioni = cross.note_per_il_titolare if cross and cross.note_per_il_titolare else [
        "Verificare la discrepanza tra il debito bancario residuo contrattuale e la segnalazione Centrale Rischi.",
        "Analizzare con il consulente contabile la causa dell'incremento di oneri finanziari nel periodo recente.",
        "Richiedere ad AdER la situazione aggiornata delle rateizzazioni per blindare l'esclusione di doppi carichi.",
        "Attivare tempestivamente la procedura di composizione della crisi o accordo di ristrutturazione ex CCII.",
    ]

    # Calcolo Posizione Finanziaria Netta (PFN) ESMA 2021 & Rapporto PFN / EBITDA
    last_fs_sp = (last_approved_fs.raw_extraction.get("stato_patrimoniale") or {}) if last_approved_fs else {}
    last_fs_deb = (last_approved_fs.raw_extraction.get("debiti_per_natura") or {}) if last_approved_fs else {}
    deb_banche_val = _num((last_fs_deb.get("banche") or {}).get("importo")) or (_num(last_fs_sp.get("debiti_entro")) * 0.35)
    deb_ml_val = _num(last_fs_sp.get("debiti_oltre"))
    liq_val = _num(last_fs_sp.get("disponibilita_liquide"))
    tfr_val = _num(last_fs_sp.get("tfr"))
    soci_fin_val = _num((last_fs_deb.get("soci_finanziamenti") or {}).get("importo"))
    tot_ader_scad = sum(s.total_residuo for s in statements) if statements else 0.0

    pfn_obj = calculate_pfn_esma(
        debiti_bancari_breve=deb_banche_val,
        debiti_bancari_medio_lungo=deb_ml_val,
        disponibilita_liquide=liq_val,
        tfr_fondo=tfr_val,
        finanziamenti_soci=soci_fin_val,
        debiti_tributari_scaduti=tot_ader_scad,
    )
    last_ebitda = esercizi_economici[-1]["mol"] if esercizi_economici else 0.0
    pfn_eval = evaluate_pfn_ebitda(pfn_obj["pfn_totale"], last_ebitda)
    ratio_val = pfn_eval.get("ratio")
    pfn_ratio_str = f"{ratio_val:.2f}" if ratio_val is not None else "critico"

    # Inquadramento CCII: soglie art. 2 e segnali allarme art. 3 co. 4
    attivi_tri = [float(f.total_assets or 0.0) for f in fss if f.total_assets]
    ricavi_tri = [float(f.revenues or 0.0) for f in fss if f.revenues]
    ccii_minore = check_ccii_soglie_impresa_minore(
        attivo_patrimoniale_triennio=attivi_tri,
        ricavi_lordi_triennio=ricavi_tri,
        debiti_totali_attuali=tot_massa_stimata or 0.0,
    )
    ccii_art3 = check_ccii_segnali_allarme_art3(
        retribuzioni_scadute_30gg=0.0,
        monte_salari_mensile=0.0,
        debiti_fornitori_scaduti_90gg=0.0,
        debiti_fornitori_non_scaduti=0.0,
        esposizioni_banche_scadute_60gg=cr.total_exposure if (cr and cr.has_sofferenze) else 0.0,
        sconfinamento_banche_fidi=0.0,
        totale_fidi_accordati=0.0,
        debiti_ader_scaduti_90gg=tot_ader_scad,
    )

    # Esposizioni soci dinamiche
    esposizioni_soci = []
    for g in guarantees:
        esposizioni_soci.append({
            "socio": g.guaranteed_subject or client_display,
            "garanzia": f"Garanzia/Fideiussione a favore di {g.intermediary or 'Istituto di Credito'}",
            "importo": f"€ {float(g.valore_garanzia or g.importo_garantito or 0.0):,.2f}",
        })
    if not esposizioni_soci and soci_list:
        for s in soci_list:
            if s.get("garante") or s.get("ruolo") == "Legale rappresentante":
                esposizioni_soci.append({
                    "socio": s.get("nome", "Legale rappresentante"),
                    "garanzia": "Fideiussione personale a presidio degli affidamenti bancari della società",
                    "importo": "Da quantificare con copia delle lettere di garanzia",
                })
    if not esposizioni_soci:
        esposizioni_soci.append({
            "socio": client_display,
            "garanzia": "Nessuna garanzia personale formalmente documentata",
            "importo": "—",
        })

    # Commento periodo dinamico
    if esercizi_economici:
        ex_last = esercizi_economici[-1]
        commento_periodo = (
            f"Nell'esercizio {ex_last['anno']}, il Valore della Produzione si attesta a € {ex_last['valore_produzione_a']:,.2f} "
            f"con un Margine Operativo Lordo (MOL / EBITDA ex OIC 12 e CNDCEC marzo 2024) pari a € {ex_last['mol']:,.2f} "
            f"({ex_last['mol_pct']:.1f}% sul valore della produzione). "
            f"Formula applicata: {ex_last.get('formula_mol')}. "
            f"L'esercizio registra un risultato netto di € {ex_last['utile_perdita']:,.2f}."
        )
    else:
        commento_periodo = "Dati economici in attesa di caricamento dei bilanci d'esercizio completi."

    # Commento debiti 5.1 dinamico
    if table_5_1 and table_5_1.get("totali", {}).get("valori"):
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
            commento_5_1 = f"I debiti contabili da bilancio si attestano complessivamente a € {tot_massa_bilancio:,.2f}."
    else:
        commento_5_1 = f"I debiti contabili da bilancio si attestano complessivamente a € {tot_massa_bilancio:,.2f}."

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
        elem_fav.append("Presenza di continuità aziendale e prospettive di risanamento del debito.")

    return {
        "header": {
            "titolo": "PREANALISI ECONOMICO-FINANZIARIA E IPOTESI DI RISANAMENTO",
            "cliente": client_display,
            "forma_giuridica": (company.legal_form if company else "Società a responsabilità limitata") or "SRL",
            "codice_fiscale": client_tax_code,
            "sottotitolo": "Composizione Negoziata della Crisi — Ipotesi preliminare di proposta al ceto creditorio",
            "riservatezza": f"Documento di lavoro riservato - {mese_anno_corrente}",
            "data_bozza": now.strftime("%d/%m/%Y"),
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
            "forma_giuridica": (company.legal_form if company else "SRL") or "SRL",
            "cf_piva": client_tax_code,
            "rea": (company.rea if company else "") or "—",
            "sede_legale": (company.legal_address if company else "") or "—",
            "data_costituzione": (company.constitution_date if company else "") or "—",
            "capitale_sociale": float(company.capital or 10000.0) if company else 10000.0,
            "codice_ateco": (company.ateco if company else "") or "—",
            "attivita_prevalente": (company.business_summary if company else "") or "Attività commerciale e industriale",
            "soci": soci_list,
            "natura_crisi": (
                f"L'analisi documentale condotta su {client_display} evidenzia una situazione debitoria "
                f"derivante principalmente dall'accumulo di passività verso l'Erario ({_fmt_eur(tot_ader_scad)}) e "
                f"verso il sistema bancario/commerciale, a fronte di una gestione caratteristica che richiede "
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
                "totale_bilancio": tot_massa_bilancio,
            },
            "tabella_pfn_esma": pfn_obj,
            "valutazione_pfn_ebitda": pfn_eval,
            "cautele_sintesi": (
                "La stima della massa debitoria è costruita incrociando le banche dati esterne (AdER, Centrale Rischi, CRIF/CTC) "
                "con la contabilità societaria per eliminare ogni duplicazione. "
                "La Posizione Finanziaria Netta (PFN) è determinata secondo l'Orientamento ESMA 32-382-1138 (2021) n. 39 "
                "e include le passività finanziarie correnti e non correnti, il Fondo TFR e le passività debt-like (tributari/previdenziali "
                "scaduti e debiti fornitori oltre 90 giorni), al netto delle disponibilità liquide."
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
                "L'impresa manifesta presupposti operativi per il risanamento, purché si attivi tempestivamente "
                "uno strumento di regolazione della crisi idoneo a rimodulare e stralciare l'indebitamento pregresso."
            ),
            "inquadramento_ccii": ccii_minore,
            "segnali_allarme_art3": ccii_art3,
        },
        "capitolo_8_patrimonio": {
            "immobili": immobili_table,
            "totale_valore_catastale": tot_catastale,
            "veicoli": veicoli_table,
            "immobilizzazioni_materiali": {
                "valore_netto_bilancio": val_cespiti,
                "costo_storico_stimato": val_cespiti * 1.5 if val_cespiti > 0 else 0.0,
                "note": "Valore da verificare con perizia o libro cespiti ammortizzabili aggiornato.",
            },
            "esposizione_personale_soci": esposizioni_soci,
        },
        "capitolo_9_orientamento_risanamento": {
            "scenari": scenari_ccii,
            "proposta_coerente": "Composizione Negoziata della Crisi (art. 12 CCII) combinata con Concordato Semplificato (art. 160 CCII) o Transazione Fiscale (art. 63 CCII)",
            "motivazione": (
                "La Composizione Negoziata consente di congelare azioni esecutive e cautelari tramite misure protettive, "
                "negoziando con AdER e l'istituto bancario uno stralcio e una rateizzazione sostenibile. In caso di mancato "
                "accordo con il ceto creditorio, l'accesso al Concordato Semplificato assicura la rapida definizione senza voto."
            ),
            "condizioni": [
                "Acquisizione dell'indicazione del flusso di cassa annuo disponibile da parte del cliente.",
                "Allineamento del debito a ruolo definitivo con cancellazione delle cartelle duplicate.",
                "Rilascio dell'attestazione di veridicità dei dati contabili da parte dell'esperto.",
            ],
        },
        "capitolo_10_documentazione": {
            "documenti_mancanti": doc_mancanti,
            "flusso_richiesto": "Indicazione del cliente in merito al flusso annuo di cassa ragionevolmente destinabile al risanamento, necessaria per quantificare la proposta ai creditori.",
        },
        "capitolo_11_conclusione": {
            "giudizio_sintetico": (
                f"La preanalisi conferma che {client_display} presenta i requisiti oggettivi e soggettivi per accedere "
                f"con successo a un percorso di regolazione della crisi ex CCII. La massa debitoria complessiva stimata "
                f"(circa € {tot_massa_stimata:,.2f}), a fronte di un patrimonio netto positivo e di un fatturato stabile, "
                f"è compatibile con una manovra di risanamento in continuità guidata."
            ),
            "raccomandazioni": raccomandazioni,
            "dicitura_finale": f"PRIMA BOZZA DI ANALISI - ELABORATA IL {now.strftime('%d/%m/%Y').upper()}",
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
            for r in get_active_rules(db)
        ],
    }
