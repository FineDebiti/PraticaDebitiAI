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
    Debtor, RealEstate, Vehicle, Company, FinancialStatement,
    CreditExposure, GuaranteeGiven, CreditReportSummary, TaxDebtStatement,
)
from app.services.income_summary import compute_income_summary

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
                    "Σ totale residuo delle cartelle AER", section="indebitamento"))
    priv = round(sum(i.totale_residuo for i in items if i.ente_categoria in ("erariale", "previdenziale")), 2)
    out.append(_ind("aer_pct_privilegiati", "% debiti privilegiati", "indebitamento",
                    round(priv / aer_total * 100, 1) if aer_total else None, "pct",
                    "(erariale + previdenziale) ÷ totale AER", section="indebitamento"))
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
                    "(interessi di mora + oneri) ÷ carico affidato", section="indebitamento"))
    notif = sorted([i.data_notifica for i in items if i.data_notifica])
    out.append(_ind("aer_anzianita", "Anzianità cartelle", "indebitamento",
                    (f"{notif[0]} → {notif[-1]}" if notif else None), "text",
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
                    patr_cat if has_re else None, "eur", "Σ valore catastale immobili"))
    out.append(_ind("patr_commerciale", "Valore commerciale (mercato)", "patrimonio",
                    patr_comm if patr_comm else None, "eur",
                    "Σ valore commerciale immobili (se stimato)"))
    out.append(_ind("patr_netto_prima_casa", "Patrimonio netto prima casa", "patrimonio",
                    round(best_tot - prima_casa, 2) if has_re else None, "eur",
                    "valore immobili − immobili prima casa"))
    out.append(_ind("patr_count", "Immobili e veicoli intestati", "patrimonio",
                    (f"{len(res)} immobili · {len(vehicles)} veicoli" if (has_re or vehicles) else None),
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
                    cr_esp, "eur", "Σ utilizzato per intermediario"))
    out.append(_ind("cr_garanzie", "Garanzie prestate", "banca",
                    cr_gar, "eur", "Σ garanzie prestate dal cliente"))
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
                    "reddito mensile considerato − spese − affitto/mutuo"))
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
    soc_persone = any((c.company_type == "persone") or
                      (c.legal_form or "").lower().startswith(("s.n.c", "snc", "s.a.s", "sas", "società semplice", "ss"))
                      for c in cliente)
    out.append(_ind("imp_responsabilita_soci", "Responsabilità dei soci", "impresa",
                    ("società di persone" if soc_persone else ("società di capitali" if cliente else None)),
                    "text", "forma giuridica dell'impresa del cliente", kind="signal",
                    section="impresa",
                    criterion=("Nelle società di persone i soci rispondono anche con i beni "
                               "personali: la posizione del cliente va valutata dal legale.")
                    if soc_persone else
                    ("Forma a responsabilità limitata: da confermare comunque caso per caso." if cliente else None),
                    status="neutral" if cliente else "na"))

    # ---------------- Trasversale / statistica ----------------
    quota_def = round(sum(i.totale_residuo for i in items if (i.def_agevolata or i.rateizzato)), 2)
    out.append(_ind("x_quota_definibile", "Quota debito AER definibile", "trasversale",
                    quota_def if has_aer else None, "eur",
                    "Σ cartelle in definizione agevolata o rateizzate", section="trasversale"))
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

    # ---------------- MACRO (calcolati dagli aggregati sopra) ----------------
    indeb = round((aer_total or 0) + (cr_esp or 0) + (imp_debiti or 0), 2)
    has_indeb = has_aer or cr is not None or fs is not None
    rapporto = round(indeb / aggredibile, 2) if aggredibile else None
    macro = [
        _ind("indebitamento_totale", "Indebitamento totale", "macro",
             indeb if has_indeb else None, "eur",
             "AER + esposizione bancaria + debiti impresa"),
        _ind("patrimonio_aggredibile", "Patrimonio aggredibile (stima)", "macro",
             aggredibile if (has_re or vehicles) else None, "eur",
             "valore immobili (escl. prima casa) + veicoli"),
        _ind("debito_su_patrimonio", "Debito / patrimonio", "macro",
             rapporto, "ratio", "indebitamento ÷ patrimonio aggredibile",
             status=("danger" if (rapporto and rapporto > 1) else "ok") if rapporto is not None else "na"),
        _ind("esposizione_netta", "Esposizione netta", "macro",
             round(indeb - aggredibile, 2) if (has_indeb and (has_re or vehicles)) else None, "eur",
             "indebitamento − patrimonio aggredibile"),
    ]

    return {"macro": macro, "indicators": out}


def _fmt(v):
    return f"€ {v:,.0f}".replace(",", ".")
