"""Classificatore deterministico tridimensionale del debitore (Fase 1).

Distingue rigorosamente tre dimensioni autonome:
1. Forma giuridica (legal_form_profile)
2. Regime contabile effettivamente documentato (accounting_regime)
3. Qualificazione dimensionale CCII art. 2 co. 1 lett. d) (ccii_size_qualification)

Vincoli obbligatori:
- Mai classificare usando Case.client_name, Company.name o Debtor.first_name/last_name.
- Mai presumere il regime contabile dalla sola forma giuridica.
- S.n.c. / S.a.s. / S.s. e persone fisiche non imprenditori restano profili separati,
  mai assimilati ai protocolli A o B.
- Le soglie CCII non alterano la forma giuridica (una S.r.l. sotto soglia resta S.r.l.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    Debtor,
    Document,
    FinancialStatement,
    GuaranteeGiven,
    TaxDebtStatement,
)

LEGAL_FORM_PROFILES = {
    "impresa_individuale",
    "societa_capitali_srl",
    "persona_fisica_non_imprenditore",
    "societa_persone",
    "altra_forma_giuridica",
    "forma_incerta",
}

LEGAL_FORM_LABELS = {
    "impresa_individuale": "Impresa individuale / Ditta individuale",
    "societa_capitali_srl": "Società di capitali (S.r.l. / S.r.l.s.)",
    "persona_fisica_non_imprenditore": "Persona fisica non imprenditore (consumatore / ex-socio / fideiussore)",
    "societa_persone": "Società di persone (S.n.c. / S.a.s. / S.s.)",
    "altra_forma_giuridica": "Altra forma giuridica (S.p.A. / S.a.p.a. / Cooperativa / Consorzio)",
    "forma_incerta": "Forma giuridica incerta",
}

ACCOUNTING_REGIMES = {
    "ordinaria",
    "semplificata",
    "altro_regime",
    "non_documentato",
}

ACCOUNTING_REGIME_LABELS = {
    "ordinaria": "Contabilità ordinaria",
    "semplificata": "Contabilità semplificata",
    "altro_regime": "Altro regime contabile",
    "non_documentato": "NON DOCUMENTATO",
}

CCII_SIZE_QUALIFICATIONS = {
    "impresa_minore",
    "non_minore",
    "non_determinabile",
    "non_applicabile",
}

CCII_SIZE_LABELS = {
    "impresa_minore": "Impresa minore (art. 2 co. 1 lett. d) CCII)",
    "non_minore": "Impresa non minore / sopra soglia (art. 2 co. 1 lett. d) CCII)",
    "non_determinabile": "NON DETERMINABILE",
    "non_applicabile": "Non applicabile (persona fisica non imprenditore)",
}

DOSSIER_COMPLETENESS_STATUSES = {
    "in_raccolta",
    "fascicolo_confermato",
}

# Art. 2 co. 1 lett. d) CCII — soglie massime nei 3 esercizi antecedenti
CCII_THRESHOLDS = {
    "attivo_max": Decimal("300000"),
    "ricavi_max": Decimal("200000"),
    "debiti_max": Decimal("500000"),
    "anni_richiesti": 3,
}

_RE_SRL = re.compile(
    r"\b(?:s\.?\s*r\.?\s*l\.?\s*s\.?|srls|s\.?\s*r\.?\s*l\.?|srl"
    r"|societ[aà]\s+a\s+responsabilit[aà]\s+limitata(?:\s+semplificata)?)\b",
    re.IGNORECASE,
)
_RE_PERSONE = re.compile(
    r"\b(?:s\.?\s*n\.?\s*c\.?|snc|s\.?\s*a\.?\s*s\.?|sas|s\.?\s*s\.?"
    r"|societ[aà]\s+in\s+nome\s+collettivo"
    r"|societ[aà]\s+in\s+accomandita\s+semplice"
    r"|societ[aà]\s+semplice)\b",
    re.IGNORECASE,
)
_RE_ALTRE_SOCIETA = re.compile(
    r"\b(?:s\.?\s*p\.?\s*a\.?|spa|s\.?\s*a\.?\s*p\.?\s*a\.?|sapa"
    r"|societ[aà]\s+per\s+azioni"
    r"|societ[aà]\s+cooperativa|cooperativa|consorzio|a\.?\s*r\.?\s*l\.?)\b",
    re.IGNORECASE,
)
_RE_INDIVIDUALE = re.compile(
    r"\b(?:impresa\s+individuale|ditta\s+individuale|imprenditore\s+individuale)\b",
    re.IGNORECASE,
)

_RE_ORDINARIA = re.compile(
    r"\b(?:contabilit[aà]\s+ordinaria|regime\s+ordinario|quadro\s+rf"
    r"|bilancio\s+(?:d['\s]?esercizio|cee|civilistico|abbreviato|micro|xbrl)"
    r"|stato\s+patrimoniale)\b",
    re.IGNORECASE,
)
_RE_SEMPLIFICATA = re.compile(
    r"\b(?:contabilit[aà]\s+semplificata|regime\s+semplificato|quadro\s+rg"
    r"|art\.?\s*18\s+d\.?\s*p\.?\s*r\.?\s*600|contabilit[aà]\s+per\s+cassa)\b",
    re.IGNORECASE,
)
_RE_ALTRO_REGIME = re.compile(
    r"\b(?:regime\s+forfettari[oa]|forfettari[oa]|quadro\s+lm|regime\s+dei\s+minimi"
    r"|quadro\s+re|regime\s+di\s+vantaggio|regime\s+agricolo)\b",
    re.IGNORECASE,
)


def protocol_code_for_profile(legal_form_profile: Optional[str]) -> Optional[str]:
    """Mappa la sola forma giuridica verso il codice protocollo operativo (A/B/None)."""
    if legal_form_profile == "impresa_individuale":
        return "A"
    if legal_form_profile == "societa_capitali_srl":
        return "B"
    return None


@dataclass
class ClassificationResult:
    legal_form_profile: str
    legal_form_label: str
    legal_form_confidence: str  # alto | medio | basso
    legal_form_evidence: list[str] = field(default_factory=list)

    accounting_regime: str = "non_documentato"
    accounting_regime_label: str = ACCOUNTING_REGIME_LABELS["non_documentato"]
    accounting_regime_evidence: list[str] = field(default_factory=list)

    ccii_size_qualification: str = "non_determinabile"
    ccii_size_label: str = CCII_SIZE_LABELS["non_determinabile"]
    ccii_size_evidence: list[str] = field(default_factory=list)
    ccii_metrics_by_year: list[dict[str, Any]] = field(default_factory=list)
    ccii_required_verifications: list[str] = field(default_factory=list)
    ccii_external_breakdown: dict[str, Any] = field(default_factory=dict)

    protocol_code: Optional[str] = None
    supported_by_protocol: bool = False
    anomalies: list[str] = field(default_factory=list)
    suspended_reasons: list[str] = field(default_factory=list)


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _has_real_number(val: Any) -> bool:
    return _to_decimal(val) is not None


def _parse_year(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    m = re.search(r"(19|20)\d{2}", str(val))
    return int(m.group(0)) if m else None


def _years_since_constitution(constitution_date: Optional[str]) -> Optional[float]:
    if not constitution_date:
        return None
    text = str(constitution_date).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y"):
        try:
            dt = datetime.strptime(text[:10], fmt).date()
            return (date.today() - dt).days / 365.25
        except ValueError:
            continue
    yr = _parse_year(text)
    if yr:
        return float(max(0, date.today().year - yr))
    return None


def _classify_legal_form_token(text: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    if _RE_PERSONE.search(text):
        return "societa_persone"
    if _RE_SRL.search(text):
        return "societa_capitali_srl"
    if _RE_ALTRE_SOCIETA.search(text):
        return "altra_forma_giuridica"
    if _RE_INDIVIDUALE.search(text):
        return "impresa_individuale"
    return None


def _extract_structured_text_without_names(json_obj: Any) -> str:
    """Estrae solo campi strutturali da JSON di estrazione escludendo i nomi propri."""
    if not isinstance(json_obj, dict):
        return ""
    excluded_keys = {
        "name", "nome", "cognome", "first_name", "last_name", "client_name",
        "ragione_sociale", "denominazione", "intestatario", "nominativo",
    }
    collected: list[str] = []

    def _walk(node: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in excluded_keys:
                    continue
                if isinstance(v, str):
                    collected.append(v)
                elif isinstance(v, (dict, list)):
                    _walk(v, depth + 1)
        elif isinstance(node, list):
            for item in node[:20]:
                if isinstance(item, (dict, str)):
                    _walk(item, depth + 1)

    _walk(json_obj)
    return " ".join(collected)


def _classify_legal_form(
    debtor: Optional[Debtor],
    client_companies: list[Company],
    statements: list[FinancialStatement],
    docs: list[Document],
) -> tuple[str, str, list[str], list[str], list[str]]:
    """Restituisce (profile, confidence, evidence, anomalies, suspended_reasons)."""
    candidates: set[str] = set()
    evidence: list[str] = []
    anomalies: list[str] = []
    suspended: list[str] = []

    # 1. Segnali dalle Company con role == "cliente" (mai usare Company.name!)
    for comp in client_companies:
        lf_text = (comp.legal_form or "").strip()
        ct = (comp.company_type or "").strip().lower()
        lf_profile = _classify_legal_form_token(lf_text)
        if lf_profile:
            candidates.add(lf_profile)
            evidence.append(f"Scheda impresa: legal_form='{lf_text}' -> {lf_profile}")
        elif ct == "capitali":
            # company_type="capitali" senza legal_form specifica non distingue S.r.l. da S.p.A.
            anomalies.append(
                "Scheda impresa indica company_type='capitali' senza forma giuridica specifica (S.r.l. vs S.p.A.)."
            )
            candidates.add("forma_incerta")
        elif ct == "persone":
            candidates.add("societa_persone")
            evidence.append("Scheda impresa: company_type='persone' -> societa_persone")
        elif ct == "individuale":
            candidates.add("impresa_individuale")
            evidence.append("Scheda impresa: company_type='individuale' -> impresa_individuale")
        elif ct == "altro":
            candidates.add("altra_forma_giuridica")
            evidence.append("Scheda impresa: company_type='altro' -> altra_forma_giuridica")

    # 2. Segnali da bilanci collegati (azienda.forma_giuridica, mai azienda.denominazione)
    for fs in statements:
        raw = fs.raw_extraction if isinstance(fs.raw_extraction, dict) else {}
        az = raw.get("azienda") if isinstance(raw.get("azienda"), dict) else {}
        fg = str(az.get("forma_giuridica") or "").strip()
        if fg:
            prof = _classify_legal_form_token(fg)
            if prof:
                candidates.add(prof)
                evidence.append(f"Bilancio ({fs.fiscal_year_end or 'n/d'}): forma_giuridica='{fg}' -> {prof}")

    # 3. Segnali strutturali da estrazioni documentali (escludendo sempre i nomi)
    for doc in docs:
        ext = getattr(doc, "extraction", None)
        if not ext:
            continue
        json_out = ext.json_output if isinstance(ext.json_output, dict) else None
        if json_out:
            for key in ("forma_giuridica", "legal_form", "natura_giuridica", "tipo_societa"):
                val = json_out.get(key)
                if isinstance(val, str) and val.strip():
                    prof = _classify_legal_form_token(val)
                    if prof:
                        candidates.add(prof)
                        evidence.append(f"Documento {doc.doc_type}: {key}='{val.strip()}' -> {prof}")
            az = json_out.get("azienda")
            if isinstance(az, dict) and isinstance(az.get("forma_giuridica"), str):
                prof = _classify_legal_form_token(az["forma_giuridica"])
                if prof:
                    candidates.add(prof)
                    evidence.append(
                        f"Documento {doc.doc_type}: azienda.forma_giuridica='{az['forma_giuridica']}' -> {prof}"
                    )

    # 4. Segnali da Debtor (mai usare first_name / last_name!)
    debtor_ct = (debtor.client_type or "").strip().lower() if debtor else ""
    if debtor_ct == "ditta_individuale":
        candidates.add("impresa_individuale")
        evidence.append("Debtor.client_type='ditta_individuale' -> impresa_individuale")
    elif debtor_ct in ("privato", "garante", "coobbligato"):
        # Se esistono già imprese societarie/individuali collegate come cliente, segnaliamo ambiguità
        non_consumer_candidates = {c for c in candidates if c != "persona_fisica_non_imprenditore"}
        if non_consumer_candidates:
            has_consumer_income = bool(
                debtor
                and (
                    (debtor.employer or "").strip()
                    or _to_decimal(debtor.annual_income)
                    or _to_decimal(debtor.monthly_net_income)
                    or any(
                        (d.doc_type or "") in ("busta_paga", "cu", "isee")
                        for d in docs
                    )
                )
            )
            if has_consumer_income or debtor_ct in ("garante", "coobbligato"):
                anomalies.append(
                    f"Co-presenza di Debtor '{debtor_ct}' con redditi/garanzie personali e impresa cliente "
                    f"({sorted(non_consumer_candidates)}): chiarire se il soggetto valutato è la persona fisica o l'impresa."
                )
                candidates.add("forma_incerta")
            else:
                evidence.append(
                    f"Debtor.client_type='{debtor_ct}' senza redditi da lavoro dipendente autonomi; "
                    f"presente impresa cliente {sorted(non_consumer_candidates)}."
                )
        else:
            # Controllo indizi imprenditoriali (P.IVA / REA / bilanci) senza scheda Company
            tc = (debtor.tax_code or "").strip() if debtor else ""
            has_piva_tc = bool(re.fullmatch(r"\d{11}", tc))
            has_business_docs = any(
                (d.doc_type or "") in ("bilancio", "visura_camerale", "cr_banca_italia")
                for d in docs
            )
            if has_piva_tc or has_business_docs:
                anomalies.append(
                    f"Debtor '{debtor_ct}' ma presenti indicatori d'impresa (P.IVA/visura/bilancio/CR) "
                    "senza qualificazione formale d'impresa."
                )
                candidates.add("forma_incerta")
            else:
                candidates.add("persona_fisica_non_imprenditore")
                evidence.append(f"Debtor.client_type='{debtor_ct}' senza impresa cliente -> persona_fisica_non_imprenditore")
    elif debtor_ct == "societa":
        if not candidates:
            anomalies.append(
                "Debtor.client_type='societa' ma nessuna forma societaria specifica (S.r.l. vs S.n.c. vs S.p.A.) rilevata."
            )
            candidates.add("forma_incerta")
        else:
            evidence.append("Debtor.client_type='societa' confermato dalle evidenze societarie.")

    # 5. Risoluzione finale
    specific = {c for c in candidates if c != "forma_incerta"}
    if "forma_incerta" in candidates or len(specific) > 1:
        if len(specific) > 1:
            anomalies.append(
                f"Evidenze contrastanti sulla forma giuridica rilevate: {', '.join(sorted(specific))}."
            )
        suspended.append(
            "Inquadramento giuridico e attivazione protocollo A/B sospesi finché la forma giuridica non è confermata."
        )
        return "forma_incerta", "basso", evidence, anomalies, suspended

    if not specific:
        anomalies.append("Nessun dato strutturale sufficiente per determinare la forma giuridica del debitore.")
        suspended.append("Attivazione protocollo sospesa per assenza di forma giuridica documentata.")
        return "forma_incerta", "basso", evidence, anomalies, suspended

    profile = next(iter(specific))
    confidence = "alto" if len(evidence) >= 1 else "medio"

    if profile == "persona_fisica_non_imprenditore":
        suspended.append(
            "Profilo persona fisica non imprenditore rilevato: i Protocolli A/B non si applicano e il soggetto "
            "non viene assimilato ad impresa individuale."
        )
    elif profile == "societa_persone":
        suspended.append(
            "Profilo società di persone (S.n.c./S.a.s./S.s.) rilevato: profilo dedicato futuro, "
            "non assimilabile a S.r.l. (Protocollo B) né a impresa individuale (Protocollo A)."
        )
    elif profile == "altra_forma_giuridica":
        suspended.append(
            "Forma giuridica non inclusa nel perimetro corrente dei Protocolli A (impresa individuale) e B (S.r.l./S.r.l.s.)."
        )

    return profile, confidence, evidence, anomalies, suspended


def _classify_accounting_regime(
    client_companies: list[Company],
    statements: list[FinancialStatement],
    docs: list[Document],
) -> tuple[str, list[str], list[str]]:
    """Classifica il regime contabile SOLO su evidenze documentate, mai per presunzione da forma giuridica."""
    regimes: set[str] = set()
    evidence: list[str] = []
    anomalies: list[str] = []

    # 1. Evidenza forte dai bilanci strutturati (FinancialStatement)
    for fs in statements:
        st = (fs.statement_type or "").lower()
        raw = fs.raw_extraction if isinstance(fs.raw_extraction, dict) else {}
        sp = raw.get("stato_patrimoniale") if isinstance(raw.get("stato_patrimoniale"), dict) else {}
        ce = raw.get("conto_economico") if isinstance(raw.get("conto_economico"), dict) else {}
        is_sempl_st = any(tok in st for tok in ("semplificat", "cassa", "rg"))
        has_nonzero_sp_cols = any(
            (v is not None and float(v) != 0.0)
            for v in (fs.total_assets, fs.equity, fs.total_debts)
        )
        has_sp_json = any(
            sp.get(k) not in (None, "", 0, 0.0)
            for k in ("attivo_totale", "totale_attivo", "patrimonio_netto", "debiti", "debiti_totali")
        )
        has_sp_fields = (not is_sempl_st) and (has_sp_json or has_nonzero_sp_cols)
        if is_sempl_st and not has_sp_json:
            regimes.add("semplificata")
            evidence.append(
                f"Prospetto ({fs.fiscal_year_end or 'n/d'}, tipo='{fs.statement_type}') "
                "documenta contabilità semplificata (assenza SP)."
            )
        elif has_sp_fields or any(tok in st for tok in ("ordinari", "civilistic", "cee", "xbrl", "abbreviat", "micro")):
            regimes.add("ordinaria")
            evidence.append(
                f"Bilancio ({fs.fiscal_year_end or 'n/d'}, tipo='{fs.statement_type or 'n/d'}') "
                "documenta Stato Patrimoniale / contabilità ordinaria."
            )
        elif _has_real_number(fs.revenues) or ce:
            # Solo CE senza SP e senza tipo esplicito non prova ordinaria
            evidence.append(
                f"Prospetto ({fs.fiscal_year_end or 'n/d'}) contiene solo ricavi/CE senza Stato Patrimoniale."
            )

    # 2. Evidenza da metadato esplicito su Company.extra (se popolato da estrazioni)
    for comp in client_companies:
        extra = comp.extra if isinstance(comp.extra, dict) else {}
        explicit = str(extra.get("accounting_regime") or extra.get("regime_contabile") or "").strip().lower()
        if explicit in ("ordinaria", "ordinario", "contabilita_ordinaria"):
            regimes.add("ordinaria")
            evidence.append(f"Company.extra.regime_contabile='{explicit}' -> ordinaria")
        elif explicit in ("semplificata", "semplificato", "contabilita_semplificata"):
            regimes.add("semplificata")
            evidence.append(f"Company.extra.regime_contabile='{explicit}' -> semplificata")
        elif explicit in ("forfettario", "minimi", "altro", "altro_regime"):
            regimes.add("altro_regime")
            evidence.append(f"Company.extra.regime_contabile='{explicit}' -> altro_regime")

    # 3. Evidenza da documenti fiscali/contabili ed estrazioni (mai da nomi propri)
    for doc in docs:
        ext = getattr(doc, "extraction", None)
        pieces: list[str] = []
        if ext:
            if isinstance(ext.json_output, dict):
                raw_rc = str(
                    ext.json_output.get("regime_contabile")
                    or ext.json_output.get("accounting_regime")
                    or ext.json_output.get("quadro_fiscale")
                    or ""
                ).strip()
                if raw_rc:
                    pieces.append(raw_rc)
                pieces.append(_extract_structured_text_without_names(ext.json_output))
            if ext.raw_text:
                pieces.append(ext.raw_text[:6000])
        blob = " ".join(p for p in pieces if p)
        if not blob:
            continue

        matched_doc = False
        if _RE_SEMPLIFICATA.search(blob):
            regimes.add("semplificata")
            evidence.append(f"Documento '{doc.original_filename}' ({doc.doc_type}) cita regime semplificato / Quadro RG.")
            matched_doc = True
        if _RE_ORDINARIA.search(blob):
            regimes.add("ordinaria")
            evidence.append(f"Documento '{doc.original_filename}' ({doc.doc_type}) cita contabilità ordinaria / Quadro RF / SP.")
            matched_doc = True
        if not matched_doc and _RE_ALTRO_REGIME.search(blob):
            regimes.add("altro_regime")
            evidence.append(f"Documento '{doc.original_filename}' ({doc.doc_type}) cita altro regime (forfettario / LM / RE).")

    if not regimes:
        return "non_documentato", evidence, anomalies

    if len(regimes) > 1:
        anomalies.append(
            f"Evidenze contabili miste o non concordanti ({', '.join(sorted(regimes))}): "
            "regime contabile impostato su 'non_documentato' in attesa di conferma operatore."
        )
        return "non_documentato", evidence, anomalies

    return next(iter(regimes)), evidence, anomalies


def _is_interim_fs(fs: FinancialStatement) -> bool:
    st = str(fs.statement_type or "").lower()
    if any(tok in st for tok in ("provvisori", "infrannual", "interim", "parzial")):
        return True
    dt = str(fs.fiscal_year_end or "").strip()
    if not dt:
        return False
    # Date tipo YYYY-MM-DD non terminate al 31/12 (o YYYY-MM con mese != 12) sono infrannuali
    m_full = re.match(r"^((?:19|20)\d{2})-(\d{2})-(\d{2})$", dt)
    if m_full:
        return not (m_full.group(2) == "12" and m_full.group(3) == "31")
    m_ym = re.match(r"^((?:19|20)\d{2})-(\d{2})$", dt)
    if m_ym:
        return m_ym.group(2) != "12"
    m_it = re.match(r"^(\d{2})/(\d{2})/((?:19|20)\d{2})$", dt)
    if m_it:
        return not (m_it.group(1) == "31" and m_it.group(2) == "12")
    return False


def _is_guarantee_or_firma_exposure(exp: CreditExposure) -> bool:
    cat = f"{exp.category or ''} {exp.status or ''}".lower()
    return any(
        tok in cat
        for tok in ("firma", "garanz", "fideiuss", "avall", "cauzion")
    )


def _is_closed_or_informative_exposure(exp: CreditExposure) -> bool:
    st = str(exp.status or "").lower()
    return any(tok in st for tok in ("estint", "chius", "saldat", "informativ"))


def _classify_ccii_size(
    legal_form_profile: str,
    client_companies: list[Company],
    statements: list[FinancialStatement],
    tax_statements: list[TaxDebtStatement],
    credit_reports: list[CreditReportSummary],
    credit_exposures: Optional[list[CreditExposure]] = None,
    guarantees_given: Optional[list[GuaranteeGiven]] = None,
) -> tuple[str, list[str], list[dict[str, Any]], list[str], list[str], dict[str, Any]]:
    """Valuta i requisiti di impresa minore ex art. 2 co. 1 lett. d) CCII.

    Regole di revisione Fase 1:
    - Esclude i prospetti infrannuali dal conteggio dei 3 esercizi annuali chiusi.
    - Verifica che gli esercizi siano consecutivi e pertinenti (latest >= anno_corrente - 2).
    - Deduplica AdER per soggetto (codice_fiscale, owner_kind), distinguendo residuo netto vs sospeso.
    - Separa in CR le esposizioni effettive per cassa dalle garanzie/firma e dall'accordato non utilizzato.
    - Non somma automaticamente bilancio + AdER + CR; in caso di mancata riconciliazione -> non_determinabile.
    """
    if legal_form_profile == "persona_fisica_non_imprenditore":
        return (
            "non_applicabile",
            ["Persona fisica non imprenditore: soglie dimensionali art. 2 co. 1 lett. d) CCII non applicabili."],
            [],
            [],
            [],
            {},
        )

    evidence: list[str] = []
    anomalies: list[str] = []
    required_verifications: list[str] = []

    # 1. Separa bilanci annuali chiusi da infrannuali
    by_year: dict[int, FinancialStatement] = {}
    interim_years: list[str] = []
    undated_annual: list[FinancialStatement] = []
    for fs in statements:
        if _is_interim_fs(fs):
            interim_years.append(str(fs.fiscal_year_end or fs.statement_type or "infrannuale"))
            continue
        yr = _parse_year(fs.fiscal_year_end)
        if yr is not None:
            by_year[yr] = fs
        else:
            undated_annual.append(fs)

    if interim_years:
        evidence.append(
            f"Esclusi dal computo annuale CCII {len(interim_years)} prospetti infrannuali "
            f"({', '.join(interim_years)}): usati solo i bilanci annuali chiusi."
        )

    ordered_years = sorted(by_year.keys(), reverse=True)
    eval_list: list[tuple[str, FinancialStatement]] = [
        (str(yr), by_year[yr]) for yr in ordered_years[:3]
    ]
    if not eval_list and undated_annual:
        eval_list = [("n/d", fs) for fs in undated_annual[:3]]

    metrics_by_year: list[dict[str, Any]] = []
    any_exceeded = False
    all_complete_under_threshold = bool(eval_list)
    latest_fs_debts: Optional[Decimal] = None

    for idx_yr, (label, fs) in enumerate(eval_list):
        raw_fs = fs.raw_extraction if isinstance(fs.raw_extraction, dict) else {}
        sp_fs = raw_fs.get("stato_patrimoniale") if isinstance(raw_fs.get("stato_patrimoniale"), dict) else {}
        st_lower = str(fs.statement_type or "").lower()
        is_sempl_without_sp = any(tok in st_lower for tok in ("semplificat", "cassa", "rg")) and not sp_fs
        if is_sempl_without_sp and (fs.total_assets or 0.0) == 0.0 and (fs.total_debts or 0.0) == 0.0:
            att = None
            deb = None
        elif (fs.total_assets or 0.0) == 0.0 and (fs.equity or 0.0) == 0.0 and (fs.total_debts or 0.0) == 0.0 and not sp_fs:
            att = None
            deb = None
        else:
            att = _to_decimal(fs.total_assets)
            deb = _to_decimal(fs.total_debts)
        ric = _to_decimal(fs.revenues)
        if idx_yr == 0:
            latest_fs_debts = deb

        exceeded_fields: list[str] = []
        if att is not None and att > CCII_THRESHOLDS["attivo_max"]:
            exceeded_fields.append(f"attivo={att:,.2f} > 300.000")
        if ric is not None and ric > CCII_THRESHOLDS["ricavi_max"]:
            exceeded_fields.append(f"ricavi={ric:,.2f} > 200.000")
        if deb is not None and deb > CCII_THRESHOLDS["debiti_max"]:
            exceeded_fields.append(f"debiti={deb:,.2f} > 500.000")

        if exceeded_fields:
            any_exceeded = True
            evidence.append(f"Esercizio {label}: superamento soglia ({', '.join(exceeded_fields)}).")

        if att is None or ric is None or deb is None:
            all_complete_under_threshold = False

        metrics_by_year.append(
            {
                "year": label,
                "attivo": float(att) if att is not None else None,
                "ricavi": float(ric) if ric is not None else None,
                "debiti": float(deb) if deb is not None else None,
                "exceeded": exceeded_fields,
                "complete_for_ccii": att is not None and ric is not None and deb is not None,
            }
        )

    # 2. Analisi AdER deduplicata per soggetto (codice_fiscale, owner_kind), distinguendo netto vs sospeso
    latest_aer_by_subject: dict[tuple[str, str], TaxDebtStatement] = {}
    superseded_aer_count = 0
    for st in sorted(
        tax_statements,
        key=lambda t: (str(t.data_elaborazione or ""), str(t.created_at or ""), str(t.id or "")),
        reverse=True,
    ):
        subj_key = ((st.codice_fiscale or "").strip().upper() or st.id, (st.owner_kind or "person").lower())
        if subj_key in latest_aer_by_subject:
            superseded_aer_count += 1
            continue
        latest_aer_by_subject[subj_key] = st

    if superseded_aer_count:
        anomalies.append(
            f"Rilevati {superseded_aer_count} estratti di ruolo AdER duplicati/precedenti sullo stesso CF: "
            "utilizzato solo il prospetto più recente per evitare somme multiple."
        )

    aer_net_total = Decimal("0")
    aer_suspended_total = Decimal("0")
    for st in latest_aer_by_subject.values():
        items = list(getattr(st, "items", None) or [])
        items_susp = sum((_to_decimal(it.importo_sospeso) or Decimal("0")) for it in items)
        res_netto = _to_decimal(st.total_residuo_netto)
        res_lordo = _to_decimal(st.total_residuo)
        if res_netto is not None and (res_netto > 0 or items_susp > 0):
            aer_net_total += res_netto
        elif res_lordo is not None:
            aer_net_total += max(Decimal("0"), res_lordo - items_susp)
        aer_suspended_total += items_susp

    if aer_suspended_total > 0:
        required_verifications.append(
            f"AdER presenta {aer_suspended_total:,.2f} EUR in carichi sospesi/contestati: "
            "esclusi dal debito certo ma da verificare in vista di eventuale revoca sospensione."
        )

    # 3. Analisi Centrale Rischi distinguendo cassa vs garanzie/firma vs accordato informativo
    cr_exposures = list(credit_exposures or [])
    cr_guarantees = list(guarantees_given or [])
    cr_cash_total = Decimal("0")
    cr_guarantees_total = Decimal("0")
    cr_accordato_unused = Decimal("0")

    if cr_exposures:
        active_cash = [
            e for e in cr_exposures
            if not _is_guarantee_or_firma_exposure(e) and not _is_closed_or_informative_exposure(e)
        ]
        firma_exps = [
            e for e in cr_exposures
            if _is_guarantee_or_firma_exposure(e) and not _is_closed_or_informative_exposure(e)
        ]
        for e in active_cash:
            ut = _to_decimal(e.utilizzato) or Decimal("0")
            acc = _to_decimal(e.accordato) or Decimal("0")
            cr_cash_total += ut
            if acc > ut:
                cr_accordato_unused += (acc - ut)
        for e in firma_exps:
            cr_guarantees_total += (_to_decimal(e.utilizzato) or _to_decimal(e.accordato) or Decimal("0"))
    elif credit_reports:
        latest_cr = sorted(
            credit_reports,
            key=lambda c: (c.most_recent_month or "", c.id or ""),
            reverse=True,
        )[0]
        cr_cash_total = _to_decimal(latest_cr.total_exposure) or Decimal("0")
        cr_guarantees_total = _to_decimal(latest_cr.total_guarantees) or Decimal("0")

    if cr_guarantees:
        gar_sum = sum(
            (_to_decimal(g.valore_garanzia) or _to_decimal(g.importo_garantito) or Decimal("0"))
            for g in cr_guarantees
            if not any(tok in str(g.status or "").lower() for tok in ("estint", "liberat", "chius"))
        )
        if gar_sum > cr_guarantees_total:
            cr_guarantees_total = gar_sum

    if cr_guarantees_total > 0:
        evidence.append(
            f"Garanzie e rischi di firma CR ({cr_guarantees_total:,.2f} EUR) mantenuti separati dal debito per cassa."
        )
        required_verifications.append(
            f"Verificare eventuale rischio di escussione delle garanzie/fideiussioni prestate ({cr_guarantees_total:,.2f} EUR)."
        )
    if cr_accordato_unused > 0:
        evidence.append(
            f"Margine accordato non utilizzato in CR ({cr_accordato_unused:,.2f} EUR) trattato come dato informativo, non come debito."
        )

    external_breakdown = {
        "aer_netto_effettivo": float(aer_net_total),
        "aer_sospeso_contestato": float(aer_suspended_total),
        "cr_cassa_effettiva": float(cr_cash_total),
        "cr_garanzie_e_firma": float(cr_guarantees_total),
        "cr_accordato_informativo": float(cr_accordato_unused),
    }

    # 4. Superamento soglia da fonti certe vs mancata riconciliazione con il bilancio
    external_direct_combined = aer_net_total + cr_cash_total
    single_external_over = aer_net_total > CCII_THRESHOLDS["debiti_max"] or cr_cash_total > CCII_THRESHOLDS["debiti_max"]

    if any_exceeded:
        return "non_minore", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown

    if single_external_over:
        if latest_fs_debts is not None and latest_fs_debts <= CCII_THRESHOLDS["debiti_max"]:
            anomalies.append(
                f"Mancata riconciliazione debitoria: il bilancio espone debiti per {latest_fs_debts:,.2f} EUR (<= 500k) "
                f"mentre una fonte esterna diretta (AdER={aer_net_total:,.2f}, CR cassa={cr_cash_total:,.2f}) supera 500.000 EUR."
            )
            required_verifications.append(
                "Riconciliare i debiti risultanti dal bilancio rispetto a AdER e Centrale Rischi prima di qualificare le soglie art. 2 CCII."
            )
            return "non_determinabile", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown

        if aer_net_total > CCII_THRESHOLDS["debiti_max"]:
            evidence.append(f"Debito fiscale netto AdER ({aer_net_total:,.2f} EUR) > 500.000 EUR.")
        if cr_cash_total > CCII_THRESHOLDS["debiti_max"]:
            evidence.append(f"Esposizione bancaria per cassa CR ({cr_cash_total:,.2f} EUR) > 500.000 EUR.")
        return "non_minore", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown

    # 5. Verifica periodo pertinente art. 2 co. 1 lett. d) CCII (ultimi 3 esercizi consecutivi)
    current_year = date.today().year
    youngest_years: Optional[float] = None
    for comp in client_companies:
        yrs = _years_since_constitution(comp.constitution_date)
        if yrs is not None:
            youngest_years = yrs if youngest_years is None else min(youngest_years, yrs)

    min_years_required = 3
    if youngest_years is not None and youngest_years < 3.0 and len(ordered_years) >= 1:
        min_years_required = len(ordered_years)
        evidence.append(
            f"Impresa costituita da {youngest_years:.1f} anni (< 3 anni): valutati {min_years_required} esercizi disponibili."
        )

    years_pertinent = True
    years_consecutive = True
    if ordered_years:
        if ordered_years[0] < (current_year - 2):
            years_pertinent = False
            anomalies.append(
                f"Ultimo bilancio annuale chiuso ({ordered_years[0]}) antecedente al triennio pertinente (atteso >= {current_year - 2})."
            )
            required_verifications.append(
                f"Acquisire i bilanci degli esercizi più recenti (>= {current_year - 2}) per il test triennale art. 2 CCII."
            )
        top_n = ordered_years[:min_years_required]
        if len(top_n) >= 2:
            for idx in range(len(top_n) - 1):
                if top_n[idx] - top_n[idx + 1] != 1:
                    years_consecutive = False
                    anomalies.append(
                        f"Triennio non consecutivo nei bilanci acquisiti ({', '.join(str(y) for y in top_n)})."
                    )
                    required_verifications.append(
                        "Integrare l'esercizio mancante per ottenere 3 bilanci annuali consecutivi."
                    )
                    break

    if (
        len(eval_list) >= min_years_required
        and all_complete_under_threshold
        and len(eval_list) >= 1
        and years_pertinent
        and years_consecutive
    ):
        if external_direct_combined > CCII_THRESHOLDS["debiti_max"]:
            anomalies.append(
                f"La somma AdER netto ({aer_net_total:,.2f}) + CR cassa ({cr_cash_total:,.2f}) supera 500.000 EUR mentre "
                "i bilanci registrano debiti sotto soglia: riconciliazione esposizioni necessaria."
            )
            required_verifications.append(
                "Eseguire riconciliazione tra debiti di bilancio e posizioni AdER + CR prima di attestare l'impresa minore."
            )
            return "non_determinabile", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown

        evidence.append(
            f"Tutti i {len(eval_list)} esercizi annuali pertinenti rispettano attivo <= 300k, ricavi <= 200k e debiti <= 500k."
        )
        return "impresa_minore", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown

    missing_parts: list[str] = []
    if len(eval_list) < min_years_required:
        missing_parts.append(
            f"disponibili {len(eval_list)}/{min_years_required} esercizi annuali chiusi con dati patrimoniali/economici completi"
        )
    if eval_list and not all_complete_under_threshold:
        missing_parts.append(
            "uno o più esercizi non riportano tutti e tre i valori (attivo patrimoniale, ricavi, debiti)"
        )
    if not years_pertinent:
        missing_parts.append("esercizi non aggiornati al triennio di riferimento art. 2 CCII")
    if not years_consecutive:
        missing_parts.append("esercizi non consecutivi")
    if not eval_list:
        missing_parts.append("nessun bilancio annuale chiuso con attivo, ricavi e debiti caricato")

    summary_msg = "Qualificazione dimensionale CCII NON DETERMINABILE: " + "; ".join(missing_parts) + "."
    evidence.append(summary_msg)
    if not required_verifications:
        required_verifications.append("Completare la serie dei 3 bilanci annuali chiusi pertinenti per verificare l'art. 2 co. 1 lett. d) CCII.")
    return "non_determinabile", evidence, metrics_by_year, anomalies, required_verifications, external_breakdown


def classify_case_dimensions(
    db: Session,
    case: Case,
    *,
    effective_profile_override: Optional[str] = None,
    effective_regime_override: Optional[str] = None,
) -> ClassificationResult:
    """Esegue la classificazione tridimensionale autonoma del fascicolo senza effetti sul DB."""
    debtor: Optional[Debtor] = case.debtor
    all_companies: list[Company] = list(case.companies or [])
    client_companies = [c for c in all_companies if (c.role or "cliente") == "cliente"]
    company_ids = [c.id for c in client_companies]

    statements: list[FinancialStatement] = []
    if company_ids:
        statements = (
            db.query(FinancialStatement)
            .filter(FinancialStatement.company_id.in_(company_ids))
            .all()
        )
    docs: list[Document] = list(case.documents or [])
    tax_statements: list[TaxDebtStatement] = list(case.tax_debt_statements or [])
    credit_reports: list[CreditReportSummary] = list(case.cr_summaries or [])
    credit_exposures: list[CreditExposure] = list(case.credit_exposures or [])
    guarantees_given: list[GuaranteeGiven] = list(case.guarantees_given or [])

    lf_profile, lf_conf, lf_ev, lf_anom, lf_susp = _classify_legal_form(
        debtor, client_companies, statements, docs
    )
    reg_code, reg_ev, reg_anom = _classify_accounting_regime(
        client_companies, statements, docs
    )

    profile_for_ccii = effective_profile_override or lf_profile
    ccii_code, ccii_ev, ccii_metrics, ccii_anom, ccii_verifs, ccii_ext_breakdown = _classify_ccii_size(
        profile_for_ccii,
        client_companies,
        statements,
        tax_statements,
        credit_reports,
        credit_exposures=credit_exposures,
        guarantees_given=guarantees_given,
    )

    anomalies = lf_anom + reg_anom + ccii_anom
    suspended = list(lf_susp)
    if ccii_code == "non_determinabile":
        suspended.append(
            "Valutazione di accessibilità agli strumenti CCII dipendente dalle soglie ex art. 2 co. 1 lett. d) "
            "sospesa: qualificazione dimensionale 'NON DETERMINABILE'."
        )
    if (effective_regime_override or reg_code) == "non_documentato":
        suspended.append(
            "Regime contabile 'NON DOCUMENTATO': l'analisi economico-finanziaria completa richiede l'acquisizione "
            "dei documenti contabili/fiscali o la conferma manuale."
        )

    eff_profile = effective_profile_override or lf_profile
    p_code = protocol_code_for_profile(eff_profile)

    return ClassificationResult(
        legal_form_profile=lf_profile,
        legal_form_label=LEGAL_FORM_LABELS.get(lf_profile, lf_profile),
        legal_form_confidence=lf_conf,
        legal_form_evidence=lf_ev,
        accounting_regime=reg_code,
        accounting_regime_label=ACCOUNTING_REGIME_LABELS.get(reg_code, reg_code),
        accounting_regime_evidence=reg_ev,
        ccii_size_qualification=ccii_code,
        ccii_size_label=CCII_SIZE_LABELS.get(ccii_code, ccii_code),
        ccii_size_evidence=ccii_ev,
        ccii_metrics_by_year=ccii_metrics,
        ccii_required_verifications=ccii_verifs,
        ccii_external_breakdown=ccii_ext_breakdown,
        protocol_code=p_code,
        supported_by_protocol=p_code in ("A", "B"),
        anomalies=anomalies,
        suspended_reasons=suspended,
    )
