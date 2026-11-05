"""Modulo di Conoscenza Integrata Giuridico-Contabile (Statutory Knowledge Engine)
per DossierLex.

Codifica in modo rigoroso, deterministico e auditabile le fonti normative primarie:
1. OIC 12 & Art. 2425 c.c. (Schemi di bilancio, riclassificazione a valore aggiunto e Conto Economico scalare).
2. CNDCEC & Il Commercialista Veneto (marzo 2024 / 2025 - Gennari & Liviero):
   - Formula standard e normalizzata di EBITDA / MOL;
   - Posizione Finanziaria Netta (PFN) secondo l'Orientamento ESMA 32-382-1138 (2021) n. 39;
   - Rapporto PFN / EBITDA (anni di rimborso) e soglie di allarme bancario (<2, 2-3, 3-6, >6, >12);
   - DSCR (Debt Service Coverage Ratio a 12 mesi con soglia 1.10).
3. Codice della Crisi d'Impresa e dell'Insolvenza (CCII - D.Lgs. 14/2019 aggiornato al 4 settembre 2024):
   - Art. 2 (definizioni di crisi, insolvenza, sovraindebitamento, consumatore e soglie impresa minore);
   - Art. 3 co. 4 (segnali di allarme tempestivi su retribuzioni, fornitori, banche, creditori pubblici qualificati);
   - Art. 25-novies (soglie di allerta creditori pubblici qualificati: INPS, INAIL, AdE, AdER);
   - Strumenti di regolazione della crisi e dell'insolvenza (Composizione negoziata, Accordi di ristrutturazione,
     PRO, Concordato preventivo, Concordato minore, Liquidazione controllata, Esdebitazione).
"""

from typing import Dict, Any, Optional, List, Tuple
import math


# =============================================================================
# 1. OIC 12 & CONTO ECONOMICO CIVILISTICO EX ART. 2425 C.C.
# =============================================================================

OIC12_CONTO_ECONOMICO_SCHEMA = {
    "A": "Valore della produzione",
    "A1": "Ricavi delle vendite e delle prestazioni",
    "A2": "Variazione delle rimanenze di prodotti in corso di lavorazione, semilavorati e finiti",
    "A3": "Variazione dei lavori in corso su ordinazione",
    "A4": "Incrementi di immobilizzazioni per lavori interni",
    "A5": "Altri ricavi e proventi (con separata indicazione dei contributi in conto esercizio)",
    "B": "Costi della produzione",
    "B6": "Materie prime, sussidiarie, di consumo e merci",
    "B7": "Servizi",
    "B8": "Godimento di beni di terzi (compresi canoni di leasing finanziario)",
    "B9": "Personale (salari, stipendi, oneri sociali, TFR, altri costi)",
    "B10": "Ammortamenti e svalutazioni",
    "B10a": "Ammortamento delle immobilizzazioni immateriali",
    "B10b": "Ammortamento delle immobilizzazioni materiali",
    "B10c": "Altre svalutazioni delle immobilizzazioni",
    "B10d": "Svalutazione dei crediti compresi nell'attivo circolante e disponibilità",
    "B11": "Variazione rimanenze materie prime, sussidiarie, di consumo e merci",
    "B12": "Accantonamenti per rischi",
    "B13": "Altri accantonamenti",
    "B14": "Oneri diversi di gestione",
    "A_minus_B": "Differenza tra valore e costi della produzione (EBIT civilistico)",
    "C": "Proventi e oneri finanziari (15 proventi partecipazioni, 16 altri proventi, 17 oneri finanziari, 17-bis utili/perdite cambi)",
    "D": "Rettifiche di valore di attività e passività finanziarie (18 rivalutazioni, 19 svalutazioni)",
    "EBT": "Risultato prima delle imposte (A - B +/- C +/- D)",
    "20": "Imposte sul reddito dell'esercizio (correnti, differite, anticipate)",
    "21": "Utile (perdita) dell'esercizio",
}


def _flt(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        return _flt(v.get("corrente") if "corrente" in v else v.get("valore", 0.0))
    try:
        s = str(v).strip().replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def calculate_ebitda_oic12(
    conto_economico: Dict[str, Any],
    leasing_b8: float = 0.0,
    poste_straordinarie: float = 0.0,
) -> Dict[str, Any]:
    """Calcola il MOL / EBITDA standard civilistico e rettificato secondo OIC 12 e CNDCEC marzo 2024.

    Formula Standard CNDCEC:
      EBITDA = (A - B) + B10a + B10b + B10c
      Le voci B10d (svalutazione crediti circolante) e B12/B13 (accantonamenti rischi e altri)
      restano all'interno dei costi operativi ordinari.

    Formula Rettificata / Gestionale:
      EBITDA Rettificato = EBITDA Standard + canoni leasing B8 +/- rettifiche non ricorrenti.
    """
    ce = conto_economico or {}

    # Valore della produzione A
    a1 = _flt(ce.get("ricavi_vendite") or ce.get("A1"))
    val_prod = _flt(ce.get("valore_produzione") or ce.get("A") or a1)

    # Costi della produzione B
    costi_prod = _flt(ce.get("costi_produzione") or ce.get("B"))

    # EBIT (A - B)
    if "differenza_valore_costi" in ce and ce.get("differenza_valore_costi") is not None:
        ebit = _flt(ce.get("differenza_valore_costi"))
    else:
        ebit = round(val_prod - costi_prod, 2)

    # Ammortamenti e svalutazioni immobilizzazioni (B10a + B10b + B10c)
    b10a = _flt(ce.get("ammortamento_immateriali") or ce.get("B10a"))
    b10b = _flt(ce.get("ammortamento_materiali") or ce.get("B10b"))
    b10c = _flt(ce.get("svalutazioni_immobilizzazioni") or ce.get("B10c"))
    b10_subtotal = round(b10a + b10b + b10c, 2)

    # Se non sono dettagliati singolarmente, usa il totale ammortamenti B10 se disponibile
    if b10_subtotal == 0.0:
        b10_generic = _flt(ce.get("ammortamenti") or ce.get("B10"))
        ammortamenti_reintegrati = b10_generic
    else:
        ammortamenti_reintegrati = b10_subtotal

    # B10d: svalutazione crediti (non va reintegrata nell'EBITDA secondo CNDCEC)
    b10d = _flt(ce.get("svalutazione_crediti") or ce.get("B10d"))

    # EBITDA Standard CNDCEC
    ebitda_standard = round(ebit + ammortamenti_reintegrati, 2)

    # EBITDA Rettificato (normalizzato con canoni leasing B8 per evitare doppio conteggio con PFN)
    b8_val = leasing_b8 or _flt(ce.get("canoni_leasing") or ce.get("B8_leasing"))
    ebitda_rettificato = round(ebitda_standard + b8_val + poste_straordinarie, 2)

    ebitda_margin_pct = round((ebitda_standard / val_prod * 100), 2) if val_prod > 0 else 0.0

    return {
        "valore_produzione_a": val_prod,
        "ricavi_vendite_a1": a1,
        "costi_produzione_b": costi_prod,
        "ebit_differenza_a_b": ebit,
        "ammortamenti_b10a_b10b_b10c": ammortamenti_reintegrati,
        "svalutazione_crediti_b10d": b10d,
        "canoni_leasing_b8": b8_val,
        "ebitda_standard": ebitda_standard,
        "ebitda_rettificato": ebitda_rettificato,
        "ebitda_margin_pct": ebitda_margin_pct,
        "formula_applicata": "EBITDA = (A - B) + B10a (Amm. Immat.) + B10b (Amm. Mat.) + B10c (Sval. Immob.) [CNDCEC marzo 2024 / OIC 12]",
    }


# =============================================================================
# 2. POSIZIONE FINANZIARIA NETTA (PFN) ESMA 2021 & RAPPORTO PFN / EBITDA
# =============================================================================

def calculate_pfn_esma(
    debiti_bancari_breve: float,
    debiti_bancari_medio_lungo: float,
    disponibilita_liquide: float,
    tfr_fondo: float = 0.0,
    finanziamenti_soci: float = 0.0,
    altri_debiti_finanziari: float = 0.0,
    debiti_tributari_scaduti: float = 0.0,
    debiti_fornitori_scaduti_90gg: float = 0.0,
    titoli_e_crediti_finanziari_correnti: float = 0.0,
) -> Dict[str, Any]:
    """Calcola la Posizione Finanziaria Netta (PFN) secondo l'Orientamento ESMA 32-382-1138 (2021) n. 39
    e il documento CNDCEC marzo 2024 / Il Commercialista Veneto 2025.

    Schema ESMA:
      A. Cassa e disponibilità liquide
      B. Mezzi equivalenti al contante
      C. Altre attività finanziarie correnti
      D. Liquidità (A + B + C)
      E. Debito finanziario corrente (banche a breve, prestiti)
      F. Parte corrente del debito non corrente
      G. Indebitamento finanziario corrente (E + F)
      H. Indebitamento finanziario netto corrente (G - D)
      I. Debito finanziario non corrente (mutui, finanziamenti M/L)
      J. Debt-like items (TFR, debiti tributari/previdenziali scaduti o rateizzati, debiti fornitori oltre 90gg, soci)
      K. PFN Complessiva = H + I + J

    Convenzione di segno:
      PFN > 0: Indebitamento finanziario netto (debito supera la liquidità)
      PFN < 0: Cassa netta (liquidità supera l'indebitamento)
    """
    liquidi_totali = round(_flt(disponibilita_liquide) + _flt(titoli_e_crediti_finanziari_correnti), 2)
    debito_fin_breve = round(_flt(debiti_bancari_breve), 2)
    debito_fin_ml = round(_flt(debiti_bancari_medio_lungo) + _flt(altri_debiti_finanziari), 2)

    debt_like_items = round(
        _flt(tfr_fondo)
        + _flt(finanziamenti_soci)
        + _flt(debiti_tributari_scaduti)
        + _flt(debiti_fornitori_scaduti_90gg),
        2,
    )

    totale_debiti_finanziari = round(debito_fin_breve + debito_fin_ml + debt_like_items, 2)
    pfn_totale = round(totale_debiti_finanziari - liquidi_totali, 2)

    return {
        "disponibilita_liquide": liquidi_totali,
        "debiti_finanziari_breve": debito_fin_breve,
        "debiti_finanziari_medio_lungo": debito_fin_ml,
        "debt_like_items": {
            "fondo_tfr": _flt(tfr_fondo),
            "finanziamenti_soci": _flt(finanziamenti_soci),
            "debiti_tributari_scaduti_o_rateizzati": _flt(debiti_tributari_scaduti),
            "debiti_fornitori_oltre_90gg": _flt(debiti_fornitori_scaduti_90gg),
            "totale_debt_like": debt_like_items,
        },
        "totale_passivita_finanziarie_e_assimilate": totale_debiti_finanziari,
        "pfn_totale": pfn_totale,
        "segno_convenzionale": "PFN > 0 = Indebitamento Netto; PFN < 0 = Cassa Netta",
        "norma_riferimento": "Orientamento ESMA 32-382-1138 (2021) n. 39 & CNDCEC marzo 2024",
    }


def evaluate_pfn_ebitda(pfn: float, ebitda: float) -> Dict[str, Any]:
    """Valuta il rapporto PFN / EBITDA (anni di rimborso del debito) e le relative soglie di allarme bancario
    secondo le Linee Guida EBA e il documento congiunto CNDCEC marzo 2024 / Il Commercialista Veneto 2025.

    Soglie Bancarie Ufficiali:
      - EBITDA <= 0 e PFN > 0: Squilibrio economico grave (non sostenibile, cassa operativa negativa)
      - PFN / EBITDA <= 2.0: Struttura solida / ottima capacità di rimborso (basso rischio)
      - 2.0 < PFN / EBITDA <= 3.0: Fisiologico (ordinaria sostenibilità per imprese produttive)
      - 3.0 < PFN / EBITDA <= 6.0: Indebitamento significativo (tensione finanziaria, richiede monitoraggio)
      - 6.0 < PFN / EBITDA <= 12.0: Campanello d'allarme bancario (crediti sotto osservazione / UTP, limite tolleranza)
      - PFN / EBITDA > 12.0: Allerta grave / Sofferenza imminente (incapacità di rimborso con margini caratteristici)
    """
    pfn_val = round(_flt(pfn), 2)
    ebitda_val = round(_flt(ebitda), 2)

    if pfn_val <= 0:
        return {
            "ratio": 0.0,
            "anni_rimborso": 0.0,
            "classe_merito": "cassa_netta",
            "livello_allerta": "nessuna",
            "valutazione_bancaria": "Cassa netta positiva: le disponibilità liquide superano i debiti finanziari. Struttura finanziaria eccellente.",
            "status": "ok",
        }

    if ebitda_val <= 0:
        return {
            "ratio": None,
            "anni_rimborso": None,
            "classe_merito": "squilibrio_grave",
            "livello_allerta": "massima",
            "valutazione_bancaria": "EBITDA negativo o nullo a fronte di PFN positiva: la gestione caratteristica distrugge liquidità. Squilibrio economico-finanziario strutturale, debito non rimborsabile con flussi operativi.",
            "status": "danger",
        }

    ratio = round(pfn_val / ebitda_val, 2)

    if ratio <= 2.0:
        return {
            "ratio": ratio,
            "anni_rimborso": ratio,
            "classe_merito": "solida",
            "livello_allerta": "fisiologica",
            "valutazione_bancaria": f"PFN/EBITDA pari a {ratio:.2f} (< 2.0): Indebitamento sostenibile e fisiologico. Rimborso stimato in circa {ratio:.1f} anni con l'attuale generazione di cassa lorda.",
            "status": "ok",
        }
    elif ratio <= 3.0:
        return {
            "ratio": ratio,
            "anni_rimborso": ratio,
            "classe_merito": "fisiologica",
            "livello_allerta": "ordinaria",
            "valutazione_bancaria": f"PFN/EBITDA pari a {ratio:.2f} (2.0 - 3.0): Livello fisiologico per investimenti e capex operativi. Piena conformità con i covenant bancari standard.",
            "status": "ok",
        }
    elif ratio <= 6.0:
        return {
            "ratio": ratio,
            "anni_rimborso": ratio,
            "classe_merito": "attenzione",
            "livello_allerta": "moderata",
            "valutazione_bancaria": f"PFN/EBITDA pari a {ratio:.2f} (3.0 - 6.0): Indebitamento significativo. Richiede circa {ratio:.1f} anni di intero MOL operativo per estinguere il debito. Sostenibilità sotto tensione.",
            "status": "warn",
        }
    elif ratio <= 12.0:
        return {
            "ratio": ratio,
            "anni_rimborso": ratio,
            "classe_merito": "allarme_bancario",
            "livello_allerta": "elevata",
            "valutazione_bancaria": f"PFN/EBITDA pari a {ratio:.2f} (6.0 - 12.0): Campanello d'allarme per il sistema bancario. Superata la soglia di tolleranza prudenziale (6.0). Posizione a rischio classificazione UTP (Inadempienza Probabile).",
            "status": "danger",
        }
    else:
        return {
            "ratio": ratio,
            "anni_rimborso": ratio,
            "classe_merito": "sofferenza",
            "livello_allerta": "critica",
            "valutazione_bancaria": f"PFN/EBITDA pari a {ratio:.2f} (> 12.0): Allerta grave. Incapacità strutturale di sostenere il debito con i flussi operativi ({ratio:.1f} anni teorici). Presupposto oggettivo per accesso a strumenti di regolazione della crisi ex CCII.",
            "status": "danger",
        }


# =============================================================================
# 3. CODICE DELLA CRISI D'IMPRESA E DELL'INSOLVENZA (CCII - D.LGS. 14/2019 AGG. 2024)
# =============================================================================

def check_ccii_soglie_impresa_minore(
    attivo_patrimoniale_triennio: List[float],
    ricavi_lordi_triennio: List[float],
    debiti_totali_attuali: float,
) -> Dict[str, Any]:
    """Verifica se il debitore rientra nei parametri dimensionali di 'Impresa Minore' ex art. 2 co. 1 lett. d) CCII.

    Soglie cumulative di non fallibilità:
      1. Attivo patrimoniale annuo non superiore a € 300.000 nei tre esercizi antecedenti;
      2. Ricavi lordi annui non superiori a € 200.000 nei tre esercizi antecedenti;
      3. Ammontare di debiti anche non scaduti non superiore a € 500.000.

    Effetto giuridico:
      - Se TUTTI i parametri sono rispettati: Debitore Minore (assoggettabile a Concordato Minore,
        Liquidazione Controllata, o Ristrutturazione debiti del consumatore).
      - Se ANCHE UNO SOLO dei parametri è superato: Impresa Sopra Soglia (assoggettabile a Liquidazione
        Giudiziale, Concordato Preventivo ordinario, PRO, Accordi di ristrutturazione ex art. 57 CCII).
    """
    max_attivo = max(attivo_patrimoniale_triennio) if attivo_patrimoniale_triennio else 0.0
    max_ricavi = max(ricavi_lordi_triennio) if ricavi_lordi_triennio else 0.0
    debiti = _flt(debiti_totali_attuali)

    supera_attivo = max_attivo > 300000.0
    supera_ricavi = max_ricavi > 200000.0
    supera_debiti = debiti > 500000.0

    is_minore = not (supera_attivo or supera_ricavi or supera_debiti)

    violazioni = []
    if supera_attivo:
        violazioni.append(f"Attivo massimo triennio (€ {max_attivo:,.2f}) > soglia di € 300.000")
    if supera_ricavi:
        violazioni.append(f"Ricavi massimi triennio (€ {max_ricavi:,.2f}) > soglia di € 200.000")
    if supera_debiti:
        violazioni.append(f"Debiti complessivi attuali (€ {debiti:,.2f}) > soglia di € 500.000")

    return {
        "e_impresa_minore": is_minore,
        "qualifica_giuridica": "Impresa Minore (ex art. 2 co. 1 lett. d CCII)" if is_minore else "Impresa Sopra Soglia (art. 2 co. 1 lett. d CCII superato)",
        "soglia_attivo_300k": {"valore": max_attivo, "superata": supera_attivo},
        "soglia_ricavi_200k": {"valore": max_ricavi, "superata": supera_ricavi},
        "soglia_debiti_500k": {"valore": debiti, "superata": supera_debiti},
        "motivo_superamento": "; ".join(violazioni) if violazioni else "Tutti i parametri dimensionali sono rispettati",
        "procedure_esperibili": [
            "Concordato Minore (art. 74 CCII)",
            "Liquidazione Controllata del Sovraindebitato (art. 268 CCII)",
            "Esdebitazione del debitore incapiente (art. 283 CCII se privo di utilità)",
        ] if is_minore else [
            "Composizione Negoziata della Crisi (artt. 12-25 CCII)",
            "Accordi di Ristrutturazione dei Debiti (art. 57, 60, 61 CCII)",
            "Transazione Fiscale e Previdenziale (art. 63 CCII con cram-down)",
            "Piano di Ristrutturazione Omologato (PRO, art. 64-bis CCII)",
            "Concordato Preventivo in continuità o liquidatorio (art. 84 CCII)",
        ],
    }


def check_ccii_segnali_allarme_art3(
    retribuzioni_scadute_30gg: float,
    monte_salari_mensile: float,
    debiti_fornitori_scaduti_90gg: float,
    debiti_fornitori_non_scaduti: float,
    esposizioni_banche_scadute_60gg: float,
    sconfinamento_banche_fidi: float,
    totale_fidi_accordati: float,
    debiti_ader_scaduti_90gg: float,
    tipo_soggetto: str = "societa_capitali",
) -> Dict[str, Any]:
    """Rileva i segnali di allarme precoce della crisi previsti dall'art. 3 comma 4 CCII:

    a) Debiti per retribuzioni scaduti da almeno 30 giorni pari a oltre il 50% dell'ammontare mensile;
    b) Debiti verso fornitori scaduti da almeno 90 giorni di ammontare superiore a quelli non scaduti;
    c) Esposizioni bancarie scadute da oltre 60 giorni o sconfinamenti superiori al 5% degli affidamenti;
    d) Creditori pubblici qualificati: superamento soglie art. 25-novies CCII (AdER, AdE, INPS, INAIL).
    """
    signals = []

    # a) Dipendenti
    if monte_salari_mensile > 0 and retribuzioni_scadute_30gg > (monte_salari_mensile * 0.5):
        signals.append({
            "codice": "art3_co4_lett_a_retribuzioni",
            "gravita": "alta",
            "descrizione": f"Debiti per stipendi scaduti > 30gg (€ {retribuzioni_scadute_30gg:,.2f}) pari a oltre la metà del monte salari mensile (€ {monte_salari_mensile:,.2f})",
        })

    # b) Fornitori
    if debiti_fornitori_scaduti_90gg > 0 and debiti_fornitori_scaduti_90gg > debiti_fornitori_non_scaduti:
        signals.append({
            "codice": "art3_co4_lett_b_fornitori",
            "gravita": "alta",
            "descrizione": f"Debiti verso fornitori scaduti > 90gg (€ {debiti_fornitori_scaduti_90gg:,.2f}) superiori all'ammontare dei debiti a fornitore non scaduti (€ {debiti_fornitori_non_scaduti:,.2f})",
        })

    # c) Banche
    sconfinamento_pct = (sconfinamento_banche_fidi / totale_fidi_accordati * 100) if totale_fidi_accordati > 0 else 0.0
    if esposizioni_banche_scadute_60gg > 0 or sconfinamento_pct > 5.0:
        signals.append({
            "codice": "art3_co4_lett_c_banche",
            "gravita": "alta",
            "descrizione": f"Esposizioni bancarie scadute da oltre 60gg (€ {esposizioni_banche_scadute_60gg:,.2f}) o sconfinamento persistente pari al {sconfinamento_pct:.1f}% (> 5% degli affidamenti)",
        })

    # d) AdER (art. 25-novies)
    soglia_ader = 500000.0 if "capitali" in tipo_soggetto.lower() else (200000.0 if "persone" in tipo_soggetto.lower() else 100000.0)
    if debiti_ader_scaduti_90gg > soglia_ader:
        signals.append({
            "codice": "art25_novies_ader",
            "gravita": "critica",
            "descrizione": f"Crediti AdER affidati e scaduti > 90gg pari a € {debiti_ader_scaduti_90gg:,.2f}, oltre la soglia di segnalazione art. 25-novies (€ {soglia_ader:,.2f})",
        })

    has_alert = len(signals) > 0
    return {
        "ha_segnali_allarme_art3": has_alert,
        "totale_segnali": len(signals),
        "segnali": signals,
        "obbligo_adeguati_assetti": "L'imprenditore e gli organi societari hanno l'obbligo (art. 2086 c.c. e art. 3 CCII) di attivarsi senza indugio per l'adozione tempestiva di uno strumento di composizione della crisi." if has_alert else "Nessun segnale di allarme ex art. 3 co. 4 CCII attualmente conclamato.",
    }
