"""Cruscotto indicatori della pratica — pura AGGREGAZIONE di dati già persistiti.

Nessuna chiamata AI/API, nessuna tabella nuova: legge AER, Centrale Rischi, patrimonio,
reddito, impresa e ne ricava indicatori DIMOSTRABILI.

Principio (app legale): si mostra solo ciò che è dimostrabile.
- kind="det": numero certo da formula + dati.
- kind="signal": spunto per il legale con CRITERIO oggettivo esplicito, MAI un verdetto.
  La funzione NON emette giudizi: per i segnali restituisce gli elementi oggettivi + il
  criterio testuale. Niente punteggio sintetico del debitore (no scoring).
Dato mancante -> value=None, status="na" (la cella mostrerà "non disponibile", non "0").
"""
from datetime import date
from app.config import settings
from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company,
    CreditExposure, GuaranteeGiven, CreditReportSummary, TaxDebtStatement,
)
from app.services.income_summary import compute_income_summary
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    check_ccii_soglie_impresa_minore,
    check_ccii_segnali_allarme_art3,
    extract_bank_debt_split,
)
from app.services.protocols.debt_ledger import build_debt_ledger

# area -> tab di destinazione del link "→ vedi in ..."
SECTION_TAB = {
    "macro": "riepilogo", "indebitamento": "aer", "patrimonio": "patrimonio",
    "banca": "banca", "reddito": "anagrafica", "impresa": "aziende", "trasversale": "riepilogo",
}


def _ind(code, label, area, value, unit, formula, *, kind="det", status=None,
         criterion=None, section=None, detail=None):
    if status is None:
        status = "na" if value is None else "neutral"
    return {
        "code": code, "label": label, "area": area, "value": value, "unit": unit,
        "formula_human": formula, "kind": kind, "status": status,
        "criterion": criterion, "source_section": section or area,
        "source_tab": SECTION_TAB.get(section or area, "riepilogo"),
        "detail": detail,
    }


def _re_value(r):
    """Valore di un immobile: commerciale se stimato, altrimenti catastale."""
    return r.commercial_value or r.cadastral_value or r.estimated_value or 0.0


def _years_since(iso):
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def compute_case_indicators(db, case_id: str) -> dict:
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    res = db.query(RealEstate).filter_by(case_id=case_id).all()
    vehicles = db.query(Vehicle).filter_by(case_id=case_id).all()
    statements = db.query(TaxDebtStatement).filter_by(case_id=case_id).all()
    items = [i for s in statements for i in s.items]
    cr = db.query(CreditReportSummary).filter_by(case_id=case_id).order_by(
        CreditReportSummary.id.desc()).first()
    exposures = db.query(CreditExposure).filter_by(case_id=case_id).all()
    guarantees = db.query(GuaranteeGiven).filter_by(case_id=case_id).all()
    cliente = db.query(Company).filter_by(case_id=case_id, role="cliente").all()
    fs = None
    for c in cliente:
        for f in sorted(c.financial_statements, key=lambda x: x.fiscal_year_end, reverse=True):
            fs = f
            break
        if fs:
            break

    out = []

    # ---------------- AER (indebitamento) ----------------
    aer_total = round(sum(s.total_residuo for s in statements), 2)
    has_aer = len(statements) > 0
    out.append(_ind("aer_totale", "Debito erariale/esattoriale totale", "indebitamento",
                    aer_total if has_aer else None, "eur",
                    "Somma totale residuo delle cartelle AER", section="indebitamento"))
    priv = round(sum(i.totale_residuo for i in items if i.ente_categoria in ("erariale", "previdenziale")), 2)
    out.append(_ind("aer_pct_privilegiati", "% debiti privilegiati", "indebitamento",
                    round(priv / aer_total * 100, 1) if aer_total else None, "pct",
                    "(erariale + previdenziale) / totale AER", section="indebitamento"))
    n_proc = sum(1 for i in items if i.proc_attive)
    out.append(_ind("aer_proc_attive", "Cartelle con procedure attive", "indebitamento",
                    n_proc if has_aer else None, "count",
                    "conteggio cartelle con fermo/ipoteca/procedure", section="indebitamento",
                    status=("danger" if n_proc > 0 else "ok") if has_aer else "na"))
    n_rate = sum(1 for i in items if i.rateizzato)
    out.append(_ind("aer_rateizzate", "Cartelle rateizzate", "indebitamento",
                    n_rate if has_aer else None, "count", "conteggio cartelle rateizzate",
                    section="indebitamento"))
    carico = sum(i.carico_affidato for i in items)
    int_oneri = sum(i.interessi_mora + i.oneri_diritti for i in items)
    out.append(_ind("aer_peso_interessi", "Peso interessi e oneri", "indebitamento",
                    round(int_oneri / carico * 100, 1) if carico else None, "pct",
                    "(interessi di mora + oneri) / carico affidato", section="indebitamento"))
    notif = sorted([i.data_notifica for i in items if i.data_notifica])
    out.append(_ind("aer_anzianita", "Anzianità cartelle", "indebitamento",
                    (f"dal {notif[0]} al {notif[-1]}" if notif else None), "text",
                    "dalla notifica più vecchia alla più recente", section="indebitamento"))
    soglia = settings.aer_signal_anni
    datate = [i for i in items if (_years_since(i.data_notifica) or 0) >= soglia]
    out.append(_ind("aer_rischio_prescrizione", "Cartelle più datate di "
                    f"{soglia} anni", "indebitamento",
                    (len(datate) if has_aer else None), "count",
                    f"cartelle notificate da oltre {soglia} anni", kind="signal",
                    criterion=("Evidenzia le cartelle più datate: la prescrizione va verificata "
                               "caso per caso dal legale, non è automatica."),
                    section="indebitamento",
                    detail=[{"numero": i.numero_documento, "ente": i.ente_creditore,
                             "notifica": i.data_notifica, "totale_residuo": i.totale_residuo}
                            for i in datate[:20]]))

    # ---------------- Patrimonio & capienza ----------------
    has_re = len(res) > 0
    patr_cat = round(sum(r.cadastral_value for r in res), 2)
    patr_comm = round(sum(r.commercial_value for r in res), 2)
    best_tot = sum(_re_value(r) for r in res)
    prima_casa = sum(_re_value(r) for r in res if r.is_primary_residence)
    veic_tot = round(sum(v.estimated_value for v in vehicles), 2)
    aggredibile = round(sum(_re_value(r) for r in res if not r.is_primary_residence) + veic_tot, 2)
    out.append(_ind("patr_catastale", "Valore catastale totale", "patrimonio",
                    patr_cat if has_re else None, "eur", "Somma valore catastale immobili"))
    out.append(_ind("patr_commerciale", "Valore commerciale (mercato)", "patrimonio",
                    patr_comm if patr_comm else None, "eur",
                    "Somma valore commerciale immobili (se stimato)"))
    out.append(_ind("patr_netto_prima_casa", "Patrimonio netto prima casa", "patrimonio",
                    round(best_tot - prima_casa, 2) if has_re else None, "eur",
                    "valore immobili - immobili prima casa"))
    out.append(_ind("patr_count", "Immobili e veicoli intestati", "patrimonio",
                    (f"{len(res)} immobili, {len(vehicles)} veicoli" if (has_re or vehicles) else None),
                    "text", "conteggio beni intestati"))
    n_ipo = sum(1 for r in res if r.has_mortgage)
    out.append(_ind("patr_ipotecati", "Immobili gravati da ipoteca", "patrimonio",
                    n_ipo if has_re else None, "count", "immobili con ipoteca segnalata"))
    out.append(_ind("patr_veicoli_fermo", "Veicoli con fermo", "patrimonio",
                    None, "count", "veicoli con fermo amministrativo (da PRA)", status="na"))

    # ---------------- Centrale Rischi ----------------
    cr_esp = round(cr.total_exposure, 2) if cr else None
    cr_gar = round(cr.total_guarantees, 2) if cr else None
    out.append(_ind("cr_esposizione", "Esposizione bancaria", "banca",
                    cr_esp, "eur", "Somma utilizzato per intermediario"))
    out.append(_ind("cr_garanzie", "Garanzie prestate", "banca",
                    cr_gar, "eur", "Somma garanzie prestate dal cliente"))
    out.append(_ind("cr_intermediari", "Numero intermediari", "banca",
                    (cr.num_intermediaries if cr else None), "count", "conteggio intermediari segnalanti"))
    out.append(_ind("cr_sofferenze", "Sofferenze", "banca",
                    ("Sì" if cr.has_sofferenze else "No") if cr else None, "text",
                    "presenza di sofferenze nel documento",
                    status=("danger" if (cr and cr.has_sofferenze) else "ok") if cr else "na"))
    out.append(_ind("cr_criticita", "Criticità storiche", "banca",
                    ("Sì" if cr.has_criticita else "No") if cr else None, "text",
                    "eventi critici nel tempo",
                    status=("warn" if (cr and cr.has_criticita) else "ok") if cr else "na"))
    out.append(_ind("cr_rischio_garante", "Esposizione come garante", "banca",
                    (cr_gar if cr else None), "eur", "garanzie prestate attive", kind="signal",
                    criterion=("Il cliente potrebbe essere escusso come garante: l'effettiva "
                               "esposizione va valutata dal legale.")))

    # ---------------- Reddito & sostenibilità ----------------
    # Reddito mensile considerato (base della capacità di rimborso), PRIORITÀ OPERATORE:
    # se il campo "Reddito mensile netto" è valorizzato (confermato a mano o via "Applica"
    # del Riepilogo reddito) comanda quello; altrimenti il consolidato dai documenti
    # (rendite incluse); altrimenti nulla. Così campo e cruscotto non divergono mai.
    inc = compute_income_summary(db, case_id)
    manual = (debtor.monthly_net_income or 0) if debtor else 0
    if manual:
        reddito_mensile, red_formula = manual, "reddito mensile netto confermato dall'operatore"
    elif inc["has_data"]:
        reddito_mensile, red_formula = inc["proposed_monthly"], "reddito mensile consolidato dai documenti (rendite incluse)"
    else:
        reddito_mensile, red_formula = 0, "da dati economici del cliente"
    has_red = bool(debtor and (reddito_mensile or debtor.monthly_expenses))
    capacita = None
    if debtor:
        capacita = round((reddito_mensile or 0) - (debtor.monthly_expenses or 0)
                         - (debtor.rent_or_mortgage or 0), 2)
    out.append(_ind("red_mensile", "Reddito mensile considerato", "reddito",
                    (reddito_mensile if has_red else None), "eur", red_formula))
    out.append(_ind("red_capacita_rimborso", "Capacità di rimborso mensile", "reddito",
                    (capacita if has_red else None), "eur",
                    "reddito mensile considerato - spese - affitto/mutuo"))
    out.append(_ind("red_familiari", "Familiari a carico", "reddito",
                    (debtor.dependents if debtor else None), "count", "da nucleo familiare"))
    sit = []
    if debtor and debtor.has_ongoing_garnishment: sit.append("pignoramento")
    if debtor and debtor.has_salary_assignment: sit.append("cessione del quinto")
    if debtor and debtor.has_payment_delegation: sit.append("delega di pagamento")
    out.append(_ind("red_situazioni", "Situazioni in corso", "reddito",
                    (", ".join(sit) if sit else ("nessuna" if debtor else None)), "text",
                    "pignoramenti / cessione / delega attivi",
                    status=("warn" if sit else ("ok" if debtor else "na"))))
    out.append(_ind("red_sostenibilita", "Sostenibilità del debito", "reddito",
                    (capacita if (has_red) else None), "eur", "capacità di rimborso mensile vs debito",
                    kind="signal",
                    criterion=("Indica se il reddito regge un piano di rientro: è una stima, "
                               "non una garanzia; la valutazione spetta al legale.")))

    # ---------------- Impresa (se presente) ----------------
    imp_debiti = round(fs.total_debts, 2) if fs else None
    out.append(_ind("imp_indici", "Indici di bilancio", "impresa",
                    ("vedi tabella in Aziende" if fs else None), "text",
                    "current ratio, ROE, leva, ROS… (sezione Aziende)", section="impresa"))
    out.append(_ind("imp_pn", "Patrimonio netto impresa", "impresa",
                    (round(fs.equity, 2) if fs else None), "eur", "da stato patrimoniale", section="impresa"))
    out.append(_ind("imp_debiti", "Debiti impresa", "impresa",
                    imp_debiti, "eur", "debiti totali da bilancio", section="impresa"))

    # Indicatori avanzati OIC 12 / CNDCEC / CCII
    fs_raw = fs.raw_extraction if fs and getattr(fs, "raw_extraction", None) else {}
    ce_dict = fs_raw.get("conto_economico") or {}
    sp_dict = fs_raw.get("stato_patrimoniale") or {}
    deb_dict = fs_raw.get("debiti_per_natura") or {}

    eb_calc = calculate_ebitda_oic12(ce_dict) if ce_dict else None
    eb_val = eb_calc["ebitda_standard"] if eb_calc else None
    out.append(_ind("imp_ebitda", "MOL / EBITDA (OIC 12 - CNDCEC)", "impresa",
                    eb_val, "eur",
                    "(A - B) + B10a + B10b + B10c", section="impresa",
                    status=("ok" if (eb_val or 0) > 0 else "danger") if eb_val is not None else "na"))

    def _val_num(obj, key="corrente") -> float:
        if isinstance(obj, dict):
            v = obj.get(key)
            if v is None and key != "importo":
                v = obj.get("importo")
        else:
            v = obj
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _val_opt(d, key="corrente"):
        if not isinstance(d, dict):
            return None
        v = d.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    liq_num = _val_opt(sp_dict.get("disponibilita_liquide"), "corrente")
    deb_b_breve, deb_b_ml, _ = extract_bank_debt_split(sp_dict, deb_dict)
    tfr_val = _val_num(sp_dict.get("tfr"), "corrente")
    soc_fin = _val_num(deb_dict.get("soci_finanziamenti"), "importo")
    trib_bil = _val_num(deb_dict.get("tributari"), "importo")

    case_obj = db.get(Case, case_id)
    debt_ledger = build_debt_ledger(db, case_obj) if case_obj else None
    trib_reconciled = (
        float(debt_ledger["bucket_totals"].get("tributari_contributivi") or 0.0)
        if debt_ledger and has_aer
        else (aer_total if has_aer else trib_bil)
    )

    pfn_calc = calculate_pfn_esma(
        debiti_bancari_breve=deb_b_breve if deb_b_breve is not None else (0.0 if (deb_b_ml is not None or has_aer) else None),
        debiti_bancari_medio_lungo=deb_b_ml if deb_b_ml is not None else (0.0 if (deb_b_breve is not None or has_aer) else None),
        disponibilita_liquide=liq_num,
        tfr_fondo=tfr_val,
        finanziamenti_soci=soc_fin,
        debiti_tributari_scaduti=trib_reconciled,
    ) if (fs and liq_num is not None) else None

    pfn_val = pfn_calc["pfn_totale"] if pfn_calc else None
    pfn_esma_ok = bool(pfn_calc and pfn_calc.get("esma_compliant"))
    out.append(_ind("imp_pfn",
                    "Posizione finanziaria netta (ESMA 2021)" if pfn_esma_ok else "Posizione finanziaria netta gestionale (non pienamente ESMA)",
                    "impresa",
                    pfn_val, "eur",
                    "PFN conforme ESMA 32-382-1138" if pfn_esma_ok else "Saldo gestionale basato su voci disponibili (schema ESMA completo non documentato)",
                    section="impresa",
                    status=("ok" if (pfn_val or 0) <= 0 else ("warn" if (pfn_val or 0) < 500000 else "danger")) if pfn_val is not None else "na"))

    pfn_eb_eval = evaluate_pfn_ebitda(pfn_val, eb_val) if (pfn_val is not None and eb_val is not None) else None
    ratio_eb = pfn_eb_eval["ratio"] if pfn_eb_eval else None
    out.append(_ind("imp_pfn_ebitda", "PFN / EBITDA (Anni rimborso)", "impresa",
                    ratio_eb, "ratio",
                    "PFN / EBITDA (soglie bancarie: <2 solido, 2-3 fisiologico, 3-6 attenzione, >6 allarme, >12 critico)",
                    kind="signal",
                    section="impresa",
                    criterion=pfn_eb_eval["valutazione_bancaria"] if pfn_eb_eval else None,
                    status=pfn_eb_eval["status"] if pfn_eb_eval else "na"))

    debt_mass_verified = bool(debt_ledger and debt_ledger.get("stato_dato") == "VERIFICATO")
    reconciled_debt = (
        debt_ledger["totals"].get("esposizioni_per_cassa_certe")
        if debt_ledger and debt_ledger.get("stato_dato") in ("VERIFICATO", "RICONCILIAZIONE_NECESSARIA")
        else None
    )

    soc_indiv = any("individuale" in (c.legal_form or "").lower() or "ditta" in (c.legal_form or "").lower() or (c.company_type == "individuale") for c in cliente)
    soc_persone = any((c.company_type == "persone") or
                      (c.legal_form or "").lower().startswith(("s.n.c", "snc", "s.a.s", "sas", "società semplice", "ss"))
                      for c in cliente)
    legal_prof = "impresa_individuale" if soc_indiv else ("societa_persone" if soc_persone else "societa_capitali_srl")

    # Verifica soglie CCII Impresa Minore (art. 2 co. 1 lett. d) — con flag riconciliazione passivo
    all_fss = [f for c in cliente for f in c.financial_statements]
    attivi_triennio = [float(f.total_assets or 0.0) for f in all_fss if f.total_assets]
    ricavi_triennio = [float(f.revenues or 0.0) for f in all_fss if f.revenues]
    ccii_minore = check_ccii_soglie_impresa_minore(
        attivo_patrimoniale_triennio=attivi_triennio,
        ricavi_lordi_triennio=ricavi_triennio,
        debiti_totali_attuali=reconciled_debt if reconciled_debt is not None else imp_debiti,
        legal_form_profile=legal_prof,
        debt_mass_verified=debt_mass_verified if debt_ledger else False,
    ) if (all_fss or imp_debiti or aer_total) else None

    if ccii_minore:
        proc_txt = ", ".join(ccii_minore["procedure_esperibili"][:2]) if ccii_minore["procedure_esperibili"] else "Sospese (dati/riconciliazione insufficienti)"
        out.append(_ind("ccii_qualifica_impresa", "Inquadramento CCII (art. 2)", "impresa",
                        ccii_minore["qualifica_giuridica"], "text",
                        "Attivo <= 300k, Ricavi <= 200k, Debiti <= 500k",
                        kind="signal",
                        section="impresa",
                        criterion=f"Presupposti dimensionali: {ccii_minore['motivo_superamento']}. Aree di verifica: {proc_txt}.",
                        status="neutral"))

    has_art3_inputs = bool(has_aer or cr is not None or fs is not None)
    if has_art3_inputs:
        ccii_alert = check_ccii_segnali_allarme_art3(
            retribuzioni_scadute_30gg=None,
            monte_salari_mensile=None,
            debiti_fornitori_scaduti_90gg=None,
            debiti_fornitori_non_scaduti=None,
            esposizioni_banche_scadute_60gg=cr_esp if (cr and cr.has_sofferenze) else None,
            sconfinamento_banche_fidi=None,
            totale_fidi_accordati=None,
            debiti_ader_scaduti_90gg=aer_total,
            tipo_soggetto=legal_prof,
            totale_esposizioni_bancarie=cr_esp if cr_esp else None,
        )
        art3_val = "Presenti (" + str(ccii_alert["totale_segnali"]) + ")" if ccii_alert["ha_segnali_allarme_art3"] else "Parziale (NULL su voci prive di partitario/anzianità)"
        art3_crit = ccii_alert["obbligo_adeguati_assetti"]
        art3_status = "danger" if ccii_alert["ha_segnali_allarme_art3"] else "warn"
    else:
        art3_val = None
        art3_crit = "Dati contabili, retribuzioni, fornitori e AdER non disponibili per la verifica art. 3 CCII (NULL)."
        art3_status = "na"
    out.append(_ind("ccii_segnali_art3", "Segnali di allarme precoce (art. 3 CCII)", "impresa",
                    art3_val,
                    "text",
                    "Verifica art. 3 co. 4 CCII (retribuzioni, fornitori, banche, AdER)",
                    kind="signal",
                    section="impresa",
                    criterion=art3_crit,
                    status=art3_status))

    if soc_indiv:
        resp_val = "impresa individuale"
        resp_crit = "Nell'impresa individuale il titolare risponde con l'intero patrimonio personale presente e futuro (art. 2740 c.c.): responsabilità illimitata."
    elif soc_persone:
        resp_val = "società di persone"
        resp_crit = "Nelle società di persone i soci rispondono anche con i beni personali: la posizione del cliente va valutata dal legale."
    elif cliente:
        resp_val = "società di capitali"
        resp_crit = "Forma a responsabilità limitata: da confermare comunque caso per caso."
    else:
        resp_val = None
        resp_crit = None

    out.append(_ind("imp_responsabilita_soci", "Responsabilità dei soci", "impresa",
                    resp_val, "text", "forma giuridica dell'impresa del cliente", kind="signal",
                    section="impresa",
                    criterion=resp_crit,
                    status="neutral" if cliente else "na"))

    # ---------------- Trasversale / statistica ----------------
    quota_def = round(sum(i.totale_residuo for i in items if (i.def_agevolata or i.rateizzato)), 2)
    out.append(_ind("x_quota_definibile", "Quota debito AER definibile", "trasversale",
                    quota_def if has_aer else None, "eur",
                    "Somma cartelle in definizione agevolata o rateizzate", section="trasversale"))
    comp = []
    if aer_total: comp.append(f"erariale/esattoriale {_fmt(aer_total)}")
    if cr_esp: comp.append(f"bancario {_fmt(cr_esp)}")
    if imp_debiti: comp.append(f"impresa {_fmt(imp_debiti)}")
    out.append(_ind("x_composizione_debito", "Composizione del debito", "trasversale",
                    (" · ".join(comp) if comp else None), "text",
                    "ripartizione per natura: esattoriale / bancario / impresa", section="trasversale"))
    out.append(_ind("x_priorita", "Priorità d'intervento", "trasversale",
                    (n_proc if has_aer else None), "count",
                    "procedure attive in corso (da affrontare per prime)", kind="signal",
                    criterion=("Le procedure attive (fermi/ipoteche) suggeriscono cosa affrontare "
                               "prima: la priorità la decide il legale."),
                    section="trasversale"))

    # ---------------- MACRO (riconciliati senza doppie somme tramite DebtLedger) ----------------
    indeb = round(float(reconciled_debt), 2) if reconciled_debt is not None else round((aer_total or 0) + (cr_esp or 0) + (imp_debiti or 0), 2)
    has_indeb = (reconciled_debt is not None) or has_aer or cr is not None or fs is not None
    rapporto = round(indeb / aggredibile, 2) if aggredibile else None
    macro = [
        _ind("indebitamento_totale", "Indebitamento totale", "macro",
             indeb if has_indeb else None, "eur",
             "Indebitamento netto riconciliato per cassa (senza duplicazioni AdER/CR/bilancio)"),
        _ind("patrimonio_aggredibile", "Patrimonio aggredibile (stima)", "macro",
             aggredibile if (has_re or vehicles) else None, "eur",
             "valore immobili (escl. prima casa) + veicoli"),
        _ind("debito_su_patrimonio", "Debito / patrimonio", "macro",
             rapporto, "ratio", "indebitamento / patrimonio aggredibile",
             status=("danger" if (rapporto and rapporto > 1) else "ok") if rapporto is not None else "na"),
        _ind("esposizione_netta", "Esposizione netta", "macro",
             round(indeb - aggredibile, 2) if (has_indeb and (has_re or vehicles)) else None, "eur",
             "indebitamento - patrimonio aggredibile"),
    ]

    red_m = (debtor.monthly_net_income if debtor else None)
    red_sp = (debtor.monthly_expenses if debtor else None)
    dti_val = round((red_sp / red_m * 100.0), 1) if (red_m and red_m > 0 and red_sp is not None) else None
    risk = min(95.0, round(32.0 + (rapporto * 18.0 if rapporto else 10.0), 1)) if (has_indeb and indeb > 0) else (0.0 if has_indeb else None)

    return {
        "macro": macro,
        "indicators": out,
        "global_risk_score": risk,
        "risk_score": risk,
        "dti_ratio": dti_val,
        "totale_attivi": aggredibile,
        "total_assets": aggredibile,
        "totale_debiti": indeb,
        "total_debt": indeb,
    }


def _fmt(v):
    return f"€ {v:,.0f}".replace(",", ".")
