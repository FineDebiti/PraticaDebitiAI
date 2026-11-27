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
from decimal import Decimal, ROUND_HALF_UP


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


def _flt_opt(v: Any) -> Optional[float]:
    """Converte in float preservando None (NULL epistemico, mai zero automatico)."""
    if v is None or v == "" or v == "n.r." or v == "N/D" or v == "NULL":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        if "corrente" in v:
            return _flt_opt(v.get("corrente"))
        if "valore" in v:
            return _flt_opt(v.get("valore"))
        if "value" in v:
            return _flt_opt(v.get("value"))
        return None
    try:
        s = str(v).strip().replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return None


def _flt(v: Any) -> float:
    res = _flt_opt(v)
    return res if res is not None else 0.0


def extract_bank_debt_split(
    sp: Dict[str, Any],
    deb: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float], str]:
    """Estrae (debiti_bancari_breve, debiti_bancari_medio_lungo, nota_metodo) evitando
    il doppio conteggio tra aggregato deb['banche'] e generico sp['debiti_oltre']."""
    sp = sp or {}
    deb = deb or {}

    def _d_val(blk: Dict[str, Any], k: str) -> Optional[float]:
        v = blk.get(k)
        if isinstance(v, dict):
            for sub in ("corrente", "importo", "valore", "value"):
                if v.get(sub) is not None and v.get(sub) != "":
                    return _flt_opt(v.get(sub))
            return None
        return _flt_opt(v)

    b_breve = _d_val(deb, "banche_breve")
    b_oltre = _d_val(deb, "banche_oltre")
    if b_breve is not None or b_oltre is not None:
        return b_breve, b_oltre, "split_esplicito_banche"

    banche_agg = _d_val(deb, "banche")
    fin_ml = _d_val(sp, "debiti_finanziari_oltre") or _d_val(deb, "debiti_finanziari_ml")
    if banche_agg is not None:
        # Non sommare automaticamente il generico sp['debiti_oltre'] sopra deb['banche']
        # perché deb['banche'] include già l'esposizione bancaria complessiva del prospetto.
        return banche_agg, (fin_ml if fin_ml is not None else 0.0), "aggregato_banche_senza_duplicazione"

    gen_oltre = _d_val(sp, "debiti_oltre")
    if gen_oltre is not None or fin_ml is not None:
        return None, (fin_ml if fin_ml is not None else gen_oltre), "solo_oltre_esercizio_sp"

    return None, None, "non_documentato"


def calculate_ebitda_oic12(
    conto_economico: Dict[str, Any],
    leasing_b8: float = 0.0,
    poste_straordinarie: float = 0.0,
) -> Dict[str, Any]:
    """Calcola il MOL / EBITDA standard civilistico e rettificato secondo OIC 12 e CNDCEC marzo 2024.

    Formula ordinaria: EBITDA = (A - B) + B10a + B10b + B10c.
    B10d, B12 e B13 restano esplicitamente visibili nel raccordo e NON vengono neutralizzati automaticamente.
    Se i dati di Conto Economico (Valore della produzione A e Costi della produzione B / EBIT) sono assenti,
    restituisce esplicitamente None (NULL) e stato_dato='NON_VERIFICABILE_NULL' invece di 0.0.
    """
    ce = conto_economico or {}

    a1_opt = _flt_opt(ce.get("ricavi_vendite") if "ricavi_vendite" in ce else ce.get("A1"))
    val_prod_opt = _flt_opt(ce.get("valore_produzione") if "valore_produzione" in ce else ce.get("A"))
    if val_prod_opt is None:
        val_prod_opt = a1_opt
    costi_prod_opt = _flt_opt(ce.get("costi_produzione") if "costi_produzione" in ce else ce.get("B"))
    ebit_direct_opt = _flt_opt(ce.get("differenza_valore_costi"))
    b10d_opt = _flt_opt(ce.get("svalutazione_crediti") if "svalutazione_crediti" in ce else ce.get("B10d"))
    b12_opt = _flt_opt(ce.get("accantonamenti_rischi") if "accantonamenti_rischi" in ce else ce.get("B12"))
    b13_opt = _flt_opt(ce.get("altri_accantonamenti") if "altri_accantonamenti" in ce else ce.get("B13"))

    if ebit_direct_opt is None and (val_prod_opt is None or costi_prod_opt is None):
        return {
            "valore_produzione_a": val_prod_opt,
            "ricavi_vendite_a1": a1_opt,
            "costi_produzione_b": costi_prod_opt,
            "ebit_differenza_a_b": None,
            "ammortamenti_b10a_b10b_b10c": None,
            "svalutazione_crediti_b10d": b10d_opt,
            "accantonamenti_rischi_b12": b12_opt,
            "altri_accantonamenti_b13": b13_opt,
            "b10_dettaglio_disponibile": False,
            "canoni_leasing_b8": leasing_b8 or _flt_opt(ce.get("canoni_leasing") or ce.get("B8_leasing")),
            "ebitda_standard": None,
            "ebitda_rettificato": None,
            "ebitda_margin_pct": None,
            "raccordo_bilancio": None,
            "stato_dato": "NON_VERIFICABILE_NULL",
            "formula_applicata": "EBITDA non calcolabile: assenza di Conto Economico normalizzato (NULL) [OIC 12]",
        }

    def _dec2(v: Optional[float]) -> Decimal:
        return Decimal(str(v or 0.0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    a1 = a1_opt if a1_opt is not None else 0.0
    val_prod = val_prod_opt if val_prod_opt is not None else 0.0
    costi_prod = costi_prod_opt if costi_prod_opt is not None else 0.0

    # EBIT (A - B) in aritmetica Decimal esatta
    ebit_dec = _dec2(ebit_direct_opt) if ebit_direct_opt is not None else (_dec2(val_prod) - _dec2(costi_prod))
    ebit = float(ebit_dec)

    # Ammortamenti e svalutazioni immobilizzazioni (B10a + B10b + B10c)
    b10a_opt = _flt_opt(ce.get("ammortamento_immateriali") if "ammortamento_immateriali" in ce else ce.get("B10a"))
    b10b_opt = _flt_opt(ce.get("ammortamento_materiali") if "ammortamento_materiali" in ce else ce.get("B10b"))
    b10c_opt = _flt_opt(ce.get("svalutazioni_immobilizzazioni") if "svalutazioni_immobilizzazioni" in ce else ce.get("B10c"))
    b10a_dec = _dec2(b10a_opt)
    b10b_dec = _dec2(b10b_opt)
    b10c_dec = _dec2(b10c_opt)
    b10_subtotal_dec = b10a_dec + b10b_dec + b10c_dec

    b10_gen_opt = _flt_opt(ce.get("ammortamenti") if "ammortamenti" in ce else ce.get("B10"))
    if b10_subtotal_dec == Decimal("0.00"):
        ammortamenti_dec = _dec2(b10_gen_opt)
    else:
        ammortamenti_dec = b10_subtotal_dec

    ammortamenti_reintegrati = float(ammortamenti_dec)
    b10d = _flt(b10d_opt)
    ebitda_dec = ebit_dec + ammortamenti_dec
    ebitda_standard = float(ebitda_dec)

    b8_val = leasing_b8 or _flt(ce.get("canoni_leasing") or ce.get("B8_leasing"))
    ebitda_rettificato = float(ebitda_dec + _dec2(b8_val) + _dec2(poste_straordinarie))
    ebitda_margin_pct = round((ebitda_standard / val_prod * 100), 2) if val_prod > 0 else None

    b10_dettaglio = any(x is not None for x in (b10a_opt, b10b_opt, b10c_opt, b10_gen_opt))

    return {
        "valore_produzione_a": val_prod,
        "ricavi_vendite_a1": a1,
        "costi_produzione_b": costi_prod,
        "ebit_differenza_a_b": ebit,
        "ammortamenti_b10a_b10b_b10c": ammortamenti_reintegrati,
        "svalutazione_crediti_b10d": b10d,
        "accantonamenti_rischi_b12": b12_opt,
        "altri_accantonamenti_b13": b13_opt,
        "b10_dettaglio_disponibile": b10_dettaglio,
        "canoni_leasing_b8": b8_val,
        "ebitda_standard": ebitda_standard,
        "ebitda_rettificato": ebitda_rettificato,
        "ebitda_margin_pct": ebitda_margin_pct,
        "raccordo_bilancio": {
            "A_valore_produzione": val_prod_opt,
            "B_costi_produzione": costi_prod_opt,
            "EBIT_A_meno_B": ebit,
            "B10a_ammortamenti_immateriali": b10a_opt,
            "B10b_ammortamenti_materiali": b10b_opt,
            "B10c_svalutazioni_immobilizzazioni": b10c_opt,
            "EBITDA_ordinario_CNDCEC_2024": ebitda_standard,
            "voci_visibili_non_neutralizzate": {
                "B10d_svalutazione_crediti": b10d_opt,
                "B12_accantonamenti_rischi": b12_opt,
                "B13_altri_accantonamenti": b13_opt,
            },
        },
        "stato_dato": "VERIFICATO",
        "formula_applicata": "EBITDA = (A - B) + B10a (Amm. Immat.) + B10b (Amm. Mat.) + B10c (Sval. Immob.) [CNDCEC marzo 2024 / OIC 12]",
    }


# =============================================================================
# 2. POSIZIONE FINANZIARIA NETTA (PFN) ESMA 2021 & RAPPORTO PFN / EBITDA
# =============================================================================

def calculate_pfn_esma(
    debiti_bancari_breve: Optional[float],
    debiti_bancari_medio_lungo: Optional[float],
    disponibilita_liquide: Optional[float],
    tfr_fondo: float = 0.0,
    finanziamenti_soci: float = 0.0,
    altri_debiti_finanziari: float = 0.0,
    debiti_tributari_scaduti: float = 0.0,
    debiti_fornitori_scaduti_90gg: float = 0.0,
    titoli_e_crediti_finanziari_correnti: float = 0.0,
) -> Dict[str, Any]:
    """Calcola la Posizione Finanziaria Netta (PFN) secondo ESMA 32-382-1138 (2021) e CNDCEC marzo 2024.
    Se disponibilita_liquide o entrambi i debiti finanziari primari sono None (NULL), impedisce lo zero silenzioso.
    """
    liq_opt = _flt_opt(disponibilita_liquide)
    deb_breve_opt = _flt_opt(debiti_bancari_breve)
    deb_ml_opt = _flt_opt(debiti_bancari_medio_lungo)

    if liq_opt is None or (deb_breve_opt is None and deb_ml_opt is None):
        return {
            "disponibilita_liquide": liq_opt,
            "debiti_finanziari_breve": deb_breve_opt,
            "debiti_finanziari_medio_lungo": deb_ml_opt,
            "debt_like_items": {
                "fondo_tfr": _flt_opt(tfr_fondo),
                "finanziamenti_soci": _flt_opt(finanziamenti_soci),
                "debiti_tributari_scaduti_o_rateizzati": _flt_opt(debiti_tributari_scaduti),
                "debiti_fornitori_oltre_90gg": _flt_opt(debiti_fornitori_scaduti_90gg),
                "totale_debt_like": None,
            },
            "totale_passivita_finanziarie_e_assimilate": None,
            "pfn_finanziaria_pura_esma": None,
            "pfn_gestionale_con_debt_like": None,
            "pfn_totale": None,
            "riconciliazione_pfn": None,
            "stato_dato": "NON_VERIFICABILE_NULL",
            "segno_convenzionale": "PFN non calcolabile per assenza di disponibilità liquide o stato patrimoniale (NULL)",
            "norma_riferimento": "Orientamento ESMA 32-382-1138 (2021) n. 39 & CNDCEC marzo 2024",
        }

    liquidi_totali = round(liq_opt + _flt(titoli_e_crediti_finanziari_correnti), 2)
    debito_fin_breve = round(deb_breve_opt or 0.0, 2)
    debito_fin_ml = round((deb_ml_opt or 0.0) + _flt(altri_debiti_finanziari), 2)

    debt_like_items = round(
        _flt(tfr_fondo)
        + _flt(finanziamenti_soci)
        + _flt(debiti_tributari_scaduti)
        + _flt(debiti_fornitori_scaduti_90gg),
        2,
    )

    pfn_finanziaria_pura = round((debito_fin_breve + debito_fin_ml) - liquidi_totali, 2)
    totale_debiti_finanziari = round(debito_fin_breve + debito_fin_ml + debt_like_items, 2)
    pfn_totale = round(totale_debiti_finanziari - liquidi_totali, 2)

    debt_like_dict = {
        "fondo_tfr": _flt(tfr_fondo),
        "finanziamenti_soci": _flt(finanziamenti_soci),
        "debiti_tributari_scaduti_o_rateizzati": _flt(debiti_tributari_scaduti),
        "debiti_fornitori_oltre_90gg": _flt(debiti_fornitori_scaduti_90gg),
        "totale_debt_like": debt_like_items,
    }

    return {
        "disponibilita_liquide": liquidi_totali,
        "debiti_finanziari_breve": debito_fin_breve,
        "debiti_finanziari_medio_lungo": debito_fin_ml,
        "debt_like_items": debt_like_dict,
        "totale_passivita_finanziarie_e_assimilate": totale_debiti_finanziari,
        "pfn_finanziaria_pura_esma": pfn_finanziaria_pura,
        "pfn_gestionale_con_debt_like": pfn_totale,
        "pfn_totale": pfn_totale,
        "riconciliazione_pfn": {
            "pfn_finanziaria_pura_esma": pfn_finanziaria_pura,
            "totale_debt_like": debt_like_items,
            "pfn_gestionale_con_debt_like": pfn_totale,
            "delta_riconciliazione": round(pfn_totale - pfn_finanziaria_pura, 2),
            "componenti_debt_like": debt_like_dict,
        },
        "stato_dato": "VERIFICATO",
        "segno_convenzionale": "PFN > 0 = Indebitamento Netto; PFN < 0 = Cassa Netta",
        "norma_riferimento": "Orientamento ESMA 32-382-1138 (2021) n. 39 & CNDCEC marzo 2024",
    }


def evaluate_pfn_ebitda(pfn: Optional[float], ebitda: Optional[float]) -> Dict[str, Any]:
    """Valuta il rapporto PFN / EBITDA con semantica rigorosa NULL vs Zero documentato."""
    pfn_val_opt = _flt_opt(pfn)
    ebitda_val_opt = _flt_opt(ebitda)
    if pfn_val_opt is None or ebitda_val_opt is None:
        return {
            "ratio": None,
            "anni_rimborso": None,
            "classe_merito": "non_verificabile",
            "livello_allerta": "non_verificabile",
            "valutazione_bancaria": "Non verificabile (NULL): PFN o EBITDA non disponibili dai documenti acquisiti.",
            "status": "na",
        }
    pfn_val = round(pfn_val_opt, 2)
    ebitda_val = round(ebitda_val_opt, 2)

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
    debiti_totali_attuali: Optional[float],
) -> Dict[str, Any]:
    """Verifica i parametri dimensionali di 'Impresa Minore' ex art. 2 co. 1 lett. d) CCII.
    Evita di qualificare 'Impresa Minore' in assenza di dati contabili completi.
    """
    max_attivo: Optional[float] = max(attivo_patrimoniale_triennio) if attivo_patrimoniale_triennio else None
    max_ricavi: Optional[float] = max(ricavi_lordi_triennio) if ricavi_lordi_triennio else None
    debiti_opt = _flt_opt(debiti_totali_attuali)

    supera_attivo = (max_attivo is not None) and (max_attivo > 300000.0)
    supera_ricavi = (max_ricavi is not None) and (max_ricavi > 200000.0)
    supera_debiti = (debiti_opt is not None) and (debiti_opt > 500000.0)

    violazioni = []
    if supera_attivo:
        violazioni.append(f"Attivo massimo triennio (€ {max_attivo:,.2f}) > soglia di € 300.000")
    if supera_ricavi:
        violazioni.append(f"Ricavi massimi triennio (€ {max_ricavi:,.2f}) > soglia di € 200.000")
    if supera_debiti:
        violazioni.append(f"Debiti complessivi attuali (€ {debiti_opt:,.2f}) > soglia di € 500.000")

    dati_incompleti = (max_attivo is None) or (max_ricavi is None) or (debiti_opt is None)
    if violazioni:
        is_minore: Optional[bool] = False
        qualifica = "Impresa Sopra Soglia (art. 2 co. 1 lett. d CCII superato)"
        motivo = "; ".join(violazioni)
    elif dati_incompleti:
        is_minore = None
        qualifica = "Non verificabile (dati dimensionali assenti o parziali - NULL)"
        motivo = "Impossibile attestare il rispetto cumulativo di tutte e 3 le soglie art. 2 CCII per mancanza di bilanci/attivo triennale."
    else:
        is_minore = True
        qualifica = "Impresa Minore (ex art. 2 co. 1 lett. d CCII)"
        motivo = "Tutti i parametri dimensionali sono rispettati"

    return {
        "e_impresa_minore": is_minore,
        "qualifica_giuridica": qualifica,
        "soglia_attivo_300k": {"valore": max_attivo, "superata": supera_attivo},
        "soglia_ricavi_200k": {"valore": max_ricavi, "superata": supera_ricavi},
        "soglia_debiti_500k": {"valore": debiti_opt, "superata": supera_debiti},
        "motivo_superamento": motivo,
        "procedure_esperibili": (
            [
                "Concordato Minore (art. 74 CCII)",
                "Liquidazione Controllata del Sovraindebitato (art. 268 CCII)",
                "Esdebitazione del debitore incapiente (art. 283 CCII se privo di utilità)",
            ]
            if is_minore is True
            else [
                "Composizione Negoziata della Crisi (artt. 12-25 CCII)",
                "Accordi di Ristrutturazione dei Debiti (art. 57, 60, 61 CCII)",
                "Transazione Fiscale e Previdenziale (art. 63 CCII con cram-down)",
                "Piano di Ristrutturazione Omologato (PRO, art. 64-bis CCII)",
                "Concordato Preventivo in continuità o liquidatorio (art. 84 CCII)",
            ]
        ),
    }


def check_ccii_segnali_allarme_art3(
    retribuzioni_scadute_30gg: Optional[float],
    monte_salari_mensile: Optional[float],
    debiti_fornitori_scaduti_90gg: Optional[float],
    debiti_fornitori_non_scaduti: Optional[float],
    esposizioni_banche_scadute_60gg: Optional[float],
    sconfinamento_banche_fidi: Optional[float],
    totale_fidi_accordati: Optional[float],
    debiti_ader_scaduti_90gg: Optional[float],
    tipo_soggetto: str = "societa_capitali",
) -> Dict[str, Any]:
    """Rileva i segnali di allarme precoce della crisi previsti dall'art. 3 comma 4 CCII con supporto NULL."""
    signals = []
    ret_scad = _flt_opt(retribuzioni_scadute_30gg) or 0.0
    monte_sal = _flt_opt(monte_salari_mensile) or 0.0
    forn_scad = _flt_opt(debiti_fornitori_scaduti_90gg) or 0.0
    forn_non_scad = _flt_opt(debiti_fornitori_non_scaduti) or 0.0
    banche_scad = _flt_opt(esposizioni_banche_scadute_60gg) or 0.0
    sconf_fidi = _flt_opt(sconfinamento_banche_fidi) or 0.0
    tot_fidi = _flt_opt(totale_fidi_accordati) or 0.0
    ader_scad_opt = _flt_opt(debiti_ader_scaduti_90gg)
    ader_scad = ader_scad_opt or 0.0

    # a) Dipendenti
    if monte_sal > 0 and ret_scad > (monte_sal * 0.5):
        signals.append({
            "codice": "art3_co4_lett_a_retribuzioni",
            "gravita": "alta",
            "descrizione": f"Debiti per stipendi scaduti > 30gg (€ {ret_scad:,.2f}) pari a oltre la metà del monte salari mensile (€ {monte_sal:,.2f})",
        })

    # b) Fornitori
    if forn_scad > 0 and forn_scad > forn_non_scad:
        signals.append({
            "codice": "art3_co4_lett_b_fornitori",
            "gravita": "alta",
            "descrizione": f"Debiti verso fornitori scaduti > 90gg (€ {forn_scad:,.2f}) superiori all'ammontare dei debiti a fornitore non scaduti (€ {forn_non_scad:,.2f})",
        })

    # c) Banche
    sconfinamento_pct = (sconf_fidi / tot_fidi * 100) if tot_fidi > 0 else 0.0
    if banche_scad > 0 or sconfinamento_pct > 5.0:
        signals.append({
            "codice": "art3_co4_lett_c_banche",
            "gravita": "alta",
            "descrizione": f"Esposizioni bancarie scadute da oltre 60gg (€ {banche_scad:,.2f}) o sconfinamento persistente pari al {sconfinamento_pct:.1f}% (> 5% degli affidamenti)",
        })

    # d) AdER (art. 25-novies)
    soglia_ader = 500000.0 if "capitali" in tipo_soggetto.lower() else (200000.0 if "persone" in tipo_soggetto.lower() else 100000.0)
    if ader_scad_opt is not None and ader_scad > soglia_ader:
        signals.append({
            "codice": "art25_novies_ader",
            "gravita": "critica",
            "descrizione": f"Crediti AdER affidati e scaduti > 90gg pari a € {ader_scad:,.2f}, oltre la soglia di segnalazione art. 25-novies (€ {soglia_ader:,.2f})",
        })

    has_alert = len(signals) > 0
    return {
        "ha_segnali_allarme_art3": has_alert,
        "totale_segnali": len(signals),
        "segnali": signals,
        "obbligo_adeguati_assetti": "L'imprenditore e gli organi societari hanno l'obbligo (art. 2086 c.c. e art. 3 CCII) di attivarsi senza indugio per l'adozione tempestiva di uno strumento di composizione della crisi." if has_alert else "Nessun segnale di allarme ex art. 3 co. 4 CCII attualmente rilevato sulle fonti disponibili.",
    }


# =============================================================================
# 4. TEST PRATICO MINISTERIALE COMPOSIZIONE NEGOZIATA (D.D. 28/09/2021 & AGG.)
# =============================================================================

def calculate_test_pratico_ministeriale(
    debito_totale_da_risanare: Optional[float],
    flusso_annuo_servizio_debito: Optional[float] = None,
    ebitda_medio_annuo: Optional[float] = None,
    attivo_disponibile_non_strumentale: float = 0.0,
) -> Dict[str, Any]:
    """Calcola il Test Pratico per la ragionevole perseguibilita del risanamento (D.D. 28/09/2021, art. 13 CCII).
    Se il debito totale da risanare è None (NULL), impedisce la classificazione ingannevole come 'Agevole'.
    """
    deb_opt = _flt_opt(debito_totale_da_risanare)
    if deb_opt is None:
        return {
            "rapporto": None,
            "debito_netto_da_risanare": None,
            "flusso_annuo_considerato": flusso_annuo_servizio_debito if flusso_annuo_servizio_debito is not None else ebitda_medio_annuo,
            "flusso_tipo": "non_verificabile",
            "esito_codice": "non_verificabile_null",
            "fascia_risanabilita": "Non verificabile (NULL)",
            "descrizione_esito": "Test pratico non calcolabile: esposizione debitoria da risanare non rilevata (NULL).",
            "status": "na",
            "normativa": "D.D. Ministero della Giustizia per la Composizione Negoziata (art. 13 CCII)",
        }

    debito_lordo = round(deb_opt, 2)
    attivo_deducibile = round(_flt(attivo_disponibile_non_strumentale), 2)
    debito_netto = max(0.0, round(debito_lordo - attivo_deducibile, 2))

    flusso = None
    flusso_tipo = "non_formalizzato"
    if flusso_annuo_servizio_debito is not None and flusso_annuo_servizio_debito > 0:
        flusso = round(_flt(flusso_annuo_servizio_debito), 2)
        flusso_tipo = "dichiarato_cliente"
    elif ebitda_medio_annuo is not None:
        flusso = round(_flt(ebitda_medio_annuo), 2)
        flusso_tipo = "stimato_da_ebitda"

    if debito_netto == 0.0:
        return {
            "rapporto": 0.0,
            "debito_netto_da_risanare": 0.0,
            "flusso_annuo_considerato": flusso,
            "flusso_tipo": flusso_tipo,
            "esito_codice": "assenza_debito",
            "fascia_risanabilita": "Agevole",
            "descrizione_esito": "Assenza di debito netto da ristrutturare: risanamento pienamente perseguibile.",
            "status": "ok",
            "normativa": "D.D. Ministero della Giustizia per la Composizione Negoziata (art. 13 CCII)",
        }

    if flusso is None or flusso <= 0.0:
        return {
            "rapporto": None,
            "debito_netto_da_risanare": debito_netto,
            "flusso_annuo_considerato": flusso,
            "flusso_tipo": flusso_tipo,
            "esito_codice": "flusso_negativo_o_assente",
            "fascia_risanabilita": "Non perseguibile in continuita diretta",
            "descrizione_esito": (
                "Flusso annuo a servizio del debito nullo o negativo. La gestione ordinaria non genera cassa "
                "sufficiente a rimborsare il debito (€ {:,.2f}). Il risanamento richiede una profonda ristrutturazione "
                "industriale, apporto di finanza esterna, o strumenti liquidatori/concordatari (es. Concordato Semplificato)."
            ).format(debito_netto),
            "status": "danger",
            "normativa": "D.D. Ministero della Giustizia per la Composizione Negoziata (art. 13 CCII)",
        }

    ratio = round(debito_netto / flusso, 2)

    if ratio <= 1.0:
        esito = "Agevole (R <= 1.0): Debito riassorbibile in meno di un anno di flussi operativi."
        fascia = "Favorevole"
        st = "ok"
    elif ratio <= 2.0:
        esito = f"Contenuta (R={ratio:.2f}): Debito riassorbibile in circa {ratio:.1f} anni mediante dilazioni ordinarie."
        fascia = "Favorevole"
        st = "ok"
    elif ratio <= 3.0:
        esito = f"Tensione significativa (R={ratio:.2f}): Necessita di moratorie o accordi di ristrutturazione a medio termine (3-4 anni)."
        fascia = "Incerta"
        st = "warn"
    elif ratio <= 5.0:
        esito = f"Crisi conclamata (R={ratio:.2f}): Risanamento complesso. Richiede misure protettive, transazione fiscale ex art. 63 CCII o dilazione a lungo termine (5-8 anni)."
        fascia = "Critica"
        st = "danger"
    else:
        esito = f"Squilibrio strutturale grave (R={ratio:.2f} > 5.0): Risanamento possibile solo previa rilevante falcidia del debito (stralcio fiscale/bancario) o finanza straordinaria/esterna."
        fascia = "Critica"
        st = "danger"

    return {
        "rapporto": ratio,
        "debito_netto_da_risanare": debito_netto,
        "flusso_annuo_considerato": flusso,
        "flusso_tipo": flusso_tipo,
        "esito_codice": f"fascia_{ratio:.1f}",
        "fascia_risanabilita": fascia,
        "descrizione_esito": esito,
        "status": st,
        "normativa": "D.D. Ministero della Giustizia per la Composizione Negoziata (art. 13 CCII)",
    }


# =============================================================================
# 5. DIAGNOSI DI RISANABILITA: SEMAFORO, 5 CRITICITA E DOCUMENTI INDISPENSABILI
# =============================================================================

def evaluate_risanabilita_diagnosi(
    ebitda_ultimo: Optional[float],
    ebitda_penultimo: Optional[float],
    pfn_ebitda_ratio: Optional[float],
    test_pratico_ratio: Optional[float],
    ha_sofferenze_cr: bool,
    debito_tributario_scaduto: Optional[float],
    flusso_annuo_formalizzato: bool,
    ha_patrimonio_immobiliare: bool = False,
) -> Dict[str, Any]:
    """Determina il Semaforo di Risanabilita (Favorevole, Incerta, Critica, Non valutabile)
    e il relativo Grado di Affidabilita (Basso, Medio, Alto)."""

    if ebitda_ultimo is None:
        return {
            "semaforo": "Non valutabile",
            "grado_affidabilita": "Basso",
            "motivazione": (
                "Dati economici e di bilancio non ancora acquisiti (NULL): impossibile esprimere una diagnosi "
                "affidabile sulla continuità e sulla risanabilità senza situazioni contabili normalizzate."
            ),
            "motivo_affidabilita": "Fascicolo privo di conti economici e/o stato patrimoniale normalizzati.",
        }

    # Valutazione Semaforo
    if ebitda_ultimo <= 0.0 or (pfn_ebitda_ratio is not None and pfn_ebitda_ratio > 10.0):
        if ha_patrimonio_immobiliare or (ebitda_penultimo is not None and ebitda_penultimo > 0):
            semaforo = "Incerta"
            motivazione = (
                "Marginalita operativa dell'ultimo esercizio negativa o fortemente compressa, "
                "ma compensata da patrimonio immobiliare aggredibile e da pregressa capacita storica "
                "di generare reddito. Il risanamento dipende da un accordo di ristrutturazione del debito erariale."
            )
        else:
            semaforo = "Critica"
            motivazione = (
                "Marginalita operativa negativa, assenza di cassa libera prospettica e squilibrio "
                "finanziario grave. Prospettive di risanamento in continuita diretta altamente problematiche "
                "in assenza di nuova finanza o radicale ristrutturazione debitoria."
            )
    elif pfn_ebitda_ratio is not None and pfn_ebitda_ratio <= 3.0 and not ha_sofferenze_cr:
        semaforo = "Favorevole"
        motivazione = "Parametri di redditivita e indebitamento ampiamente sostenibili nei limiti ordinari."
    elif pfn_ebitda_ratio is not None and pfn_ebitda_ratio <= 6.0:
        semaforo = "Incerta"
        motivazione = "Indebitamento significativo che richiede monitoraggio e rimodulazione del debito a medio termine."
    else:
        semaforo = "Critica"
        motivazione = "Rapporto debito/redditivita critico con elevata esposizione erariale scaduta."

    # Grado di Affidabilita
    if flusso_annuo_formalizzato and ebitda_ultimo is not None and ebitda_penultimo is not None:
        affidabilita = "Alto"
        motivo_aff = "Disponibilita di bilanci pluriennali comparabili e flusso di cassa validato."
    elif ebitda_ultimo is not None:
        affidabilita = "Medio"
        motivo_aff = (
            "Dati contabili ed estratti debitori disponibili, ma in assenza di quantificazione formale "
            "del flusso prospettico a 12 mesi da parte dell'imprenditore (DSCR da stimare)."
        )
    else:
        affidabilita = "Basso"
        motivo_aff = "Dati frammentari o lacunosi che impongono verifiche contabili integrative."

    return {
        "semaforo": semaforo,
        "grado_affidabilita": affidabilita,
        "motivazione": motivazione,
        "motivo_affidabilita": motivo_aff,
    }


def classify_cinque_criticita(
    debito_ader_scaduto: float,
    ebitda_storico: float,
    ebitda_ultimo: float,
    utile_ultimo: float,
    pfn_totale: float,
    pfn_eval_status: str,
    is_ditta_individuale: bool,
    ha_dati_infrannuali: bool,
    ha_sofferenze_cr: bool,
    procedure_ader_attive: int = 0,
) -> List[Dict[str, Any]]:
    """Identifica e ordina rigorosamente per gravita decrescente le 5 Principali Criticita della posizione."""
    items = []

    # 1. Debito Fiscale / AdER
    if debito_ader_scaduto > 50000.0 or procedure_ader_attive > 0:
        desc = (
            f"Esposizione debitoria tributaria ed esattoriale verso Agenzia delle Entrate - Riscossione "
            f"pari a € {debito_ader_scaduto:,.2f}"
        )
        if procedure_ader_attive > 0:
            desc += f", con {procedure_ader_attive} procedure esecutive/cautelari (fermi/ipoteche) formalizzate"
        desc += ". Tale passivita supera le soglie di allarme ex art. 25-novies CCII e richiede un intervento di regolazione immediato."
        items.append({
            "priorita": 1,
            "titolo": "Esposizione debitoria erariale e procedure AdER",
            "gravita": "Critica",
            "descrizione": desc,
            "rimedio_consigliato": "Accesso tempestivo a misure protettive ex art. 18 CCII e formulazione di Transazione Fiscale con rateizzazione straordinaria ex art. 63 CCII.",
        })

    # 2. Inversione Marginalita / Perdita d'Esercizio
    if ebitda_ultimo <= 0.0 or utile_ultimo < 0.0:
        desc = (
            f"Flessione della redditivita operativa nell'ultimo esercizio con Margine Operativo Lordo (MOL/EBITDA) "
            f"pari a € {ebitda_ultimo:,.2f} (a fronte di € {ebitda_storico:,.2f} dell'esercizio precedente) "
            f"e perdita netta pari a € {utile_ultimo:,.2f}. La gestione caratteristica recente assorbe liquidita anziche generarla."
        )
        items.append({
            "priorita": 2,
            "titolo": "Inversione della redditivita operativa e perdita d'esercizio",
            "gravita": "Alta",
            "descrizione": desc,
            "rimedio_consigliato": "Intervento di riequilibrio dei costi operativi (B) e verifica della tenuta dei margini commerciali sui dati infra-annuali correnti.",
        })

    # 3. Sostenibilita Debito Finanziario / PFN
    desc_pfn = (
        f"Posizione Finanziaria Netta complessiva stimata in € {pfn_totale:,.2f}. "
        "A fronte di un EBITDA recente compresso o negativo, il debito complessivo non puo essere riassorbito "
        "tramite i soli flussi ordinari di cassa nei tempi standard di tolleranza bancaria (PFN/EBITDA > soglie ordinarie)."
    )
    items.append({
        "priorita": 3,
        "titolo": "Tensione finanziaria e sostenibilita del debito complessivo",
        "gravita": "Alta" if pfn_eval_status in ("danger", "warn") else "Media",
        "descrizione": desc_pfn,
        "rimedio_consigliato": "Consolidamento e allungamento delle scadenze bancarie e rimodulazione dell'indebitamento a medio/lungo termine.",
    })

    # 4. Profilo Giuridico: Responsabilita Patrimoniale Illimitata
    if is_ditta_individuale:
        desc_resp = (
            "Forma giuridica di Impresa Individuale priva di autonomia patrimoniale perfetta e di capitale sociale: "
            "ai sensi dell'art. 2740 c.c., il titolare risponde dell'adempimento di tutte le obbligazioni d'impresa "
            "con il proprio patrimonio personale presente e futuro, esponendo ad aggressione esecutiva i beni immobili censiti."
        )
        items.append({
            "priorita": 4,
            "titolo": "Responsabilita patrimoniale personale illimitata (art. 2740 c.c.)",
            "gravita": "Alta",
            "descrizione": desc_resp,
            "rimedio_consigliato": "Attivazione di misure protettive del patrimonio individuale tramite la Composizione Negoziata della Crisi o istituti CCII a tutela del patrimonio personale.",
        })
    else:
        items.append({
            "priorita": 4,
            "titolo": "Impegni di garanzia personale e fideiussioni",
            "gravita": "Media",
            "descrizione": "Esposizione degli organi sociali o garanti a fideiussioni e garanzie personali a supporto degli affidamenti bancari.",
            "rimedio_consigliato": "Rinegoziazione contestuale delle garanzie fideiussorie in sede di accordo con il ceto bancario.",
        })

    # 5. Asimmetria Informativa e Documentazione Infra-annuale
    items.append({
        "priorita": 5,
        "titolo": "Asimmetria informativa contabile e necessita di attestazione flussi",
        "gravita": "Media",
        "descrizione": (
            "I dati economici infra-annuali piu recenti costituiscono risultanze contabili provvisorie non asseverate, "
            "e manca allo stato l'indicazione formalizzata del flusso di cassa prospettico a 12 mesi (DSCR) "
            "che il debitore puo ragionevolmente destinare al risanamento."
        ),
        "rimedio_consigliato": "Formalizzazione del budget di cassa prospettico e asseverazione contabile della situazione economico-patrimoniale aggiornata.",
    })

    # Ordina per priorita
    items.sort(key=lambda x: x["priorita"])
    return items[:5]


def identify_documenti_indispensabili(
    has_fs_recent: bool = True,
    has_tax_return: bool = False,
    has_cr: bool = True,
    has_ader_statement: bool = True,
    has_dscr_projection: bool = False,
    has_bank_contracts: bool = False,
    has_real_estate_appraisal: bool = False,
) -> List[Dict[str, Any]]:
    """Elenca i documenti integrativi indispensabili per la conclusione della diagnosi, ordinati per priorita."""
    docs = []

    if not has_tax_return:
        docs.append({
            "priorita": 1,
            "documento": "Dichiarazione dei redditi (Modello Redditi PF / SC / SP) ultimo esercizio con ricevuta telematica Entratel",
            "finalita": "Riscontro ufficiale del fatturato, dei costi deducibili e delle perdite fiscali riportabili.",
            "urgenza": "Massima",
        })

    if not has_dscr_projection:
        docs.append({
            "priorita": 2,
            "documento": "Budget di cassa previsionale a 12 mesi e stima del flusso annuo destinabile al piano",
            "finalita": "Calcolo rigoroso del DSCR (Debt Service Coverage Ratio) e quantificazione della proposta ai creditori ex CCII.",
            "urgenza": "Massima",
        })

    docs.append({
        "priorita": 3,
        "documento": "Situazione contabile aggiornata con mastrini clienti/fornitori ed estratti conto bancari ultimi 6 mesi",
        "finalita": "Verifica del capitale circolante netto (CCN), liquidita effettiva e debiti fornitore scaduti da oltre 90 giorni.",
        "urgenza": "Alta",
    })

    if not has_bank_contracts:
        docs.append({
            "priorita": 4,
            "documento": "Copia integrale contratti di mutuo/finanziamento bancario e lettere di fideiussione personale",
            "finalita": "Accertamento clausole di decadenza dal beneficio del termine, tassi applicati e garanzie personali dei soci/titolare.",
            "urgenza": "Media",
        })

    if not has_real_estate_appraisal:
        docs.append({
            "priorita": 5,
            "documento": "Perizia di stima asseverata o relazione tecnica aggiornata sul valore venale del compendio immobiliare",
            "finalita": "Valutazione della capienza patrimoniale per il ceto creditorio nel test di convenienza rispetto alla liquidazione giudiziale.",
            "urgenza": "Media",
        })

    docs.sort(key=lambda x: x["priorita"])
    return docs


