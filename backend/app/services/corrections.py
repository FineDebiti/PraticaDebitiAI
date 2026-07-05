"""Correzione tracciata dei dati estratti.

Principio (dati legali): l'AI/API propone, l'operatore corregge, ma:
- la FONTE (raw_extraction/raw_response) resta immutabile;
- ogni modifica è AUDITATA in FieldEdit (chi, campo, prima->dopo, quando, motivo);
- le REGOLE deterministiche a valle si ricalcolano sul dato corretto (indici di
  bilancio, quadrature AER, valore catastale, totali Centrale Rischi).

Un solo punto (EDITABLE + i recompute) descrive cosa è correggibile e cosa si ricalcola.
"""
from app.models import (
    FinancialStatement, FinancialIndicator, TaxDebtStatement, TaxDebtItem,
    CreditExposure, GuaranteeGiven, CreditReportSummary, RealEstate, Vehicle, FieldEdit,
)
from app.services.indicators import compute_indicators
from app.services import aer_parser


# ---------------- whitelist campi editabili per tipo ----------------
# kind: num | str | bool ; path (solo bilancio) = percorso annidato in raw_extraction
EDITABLE = {
    "real_estate": {
        "model": RealEstate,
        "fields": {
            "kind": "str", "address": "str", "cadastral_data": "str",
            "ownership_share": "str", "ownership_right": "str", "surface_mq": "num",
            "cadastral_income": "num", "cadastral_value": "num", "commercial_value": "num",
            "category": "str", "is_primary_residence": "bool", "other_owners": "str",
            "provenance": "str", "has_mortgage": "bool", "notes": "str",
        },
    },
    "vehicle": {
        "model": Vehicle,
        "fields": {"kind": "str", "plate": "str", "make_model": "str", "year": "str",
                   "estimated_value": "num", "notes": "str"},
    },
    "credit_exposure": {
        "model": CreditExposure,
        "fields": {"intermediary": "str", "category": "str", "accordato": "num",
                   "utilizzato": "num", "importo_garantito": "num", "status": "str",
                   "is_critical": "bool", "reference_month": "str"},
    },
    "guarantee_given": {
        "model": GuaranteeGiven,
        "fields": {"intermediary": "str", "guaranteed_subject": "str", "valore_garanzia": "num",
                   "importo_garantito": "num", "status": "str"},
    },
    "credit_report_summary": {
        "model": CreditReportSummary,
        "fields": {"period_from": "str", "period_to": "str", "most_recent_month": "str",
                   "num_intermediaries": "num", "total_exposure": "num", "total_guarantees": "num",
                   "has_sofferenze": "bool", "has_criticita": "bool"},
    },
    "tax_debt_item": {
        "model": TaxDebtItem,
        "fields": {"tipo_documento": "str", "ente_creditore": "str", "ente_categoria": "str",
                   "data_notifica": "str", "carico_affidato": "num", "sgravio": "num",
                   "gia_pagato": "num", "stralcio": "num", "residuo_carico": "num",
                   "interessi_mora": "num", "oneri_diritti": "num", "totale_residuo": "num",
                   "importo_sospeso": "num", "totale_residuo_netto": "num",
                   "rateizzato": "bool", "proc_attive": "bool", "def_agevolata": "bool"},
    },
    "financial_statement": {
        "model": FinancialStatement,
        # campi annidati in raw_extraction: chiave logica -> (path, kind)
        "nested": {
            "ricavi": ("conto_economico.ricavi_vendite.corrente", "num"),
            "utile": ("conto_economico.utile_perdita.corrente", "num"),
            "oneri_finanziari": ("conto_economico.oneri_finanziari.corrente", "num"),
            "patrimonio_netto": ("stato_patrimoniale.patrimonio_netto.corrente", "num"),
            "totale_attivo": ("stato_patrimoniale.totale_attivo.corrente", "num"),
            "debiti_totali": ("stato_patrimoniale.debiti_totali.corrente", "num"),
        },
    },
}


class CorrectionError(Exception):
    pass


def _coerce(kind, v):
    if kind == "num":
        if v in (None, "", "-"):
            return 0.0
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in str(v) else float(v)
    if kind == "bool":
        return v in (True, "true", "True", 1, "1", "si", "Si", "sì")
    return "" if v is None else str(v)


def _spec(entity_type):
    spec = EDITABLE.get(entity_type)
    if not spec:
        raise CorrectionError(f"Tipo non correggibile: {entity_type}")
    return spec


def apply_corrections(db, case_id, entity_type, entity_id, changes, reason="", operator=""):
    """Applica le correzioni, scrive l'audit, ricalcola a valle. Ritorna l'oggetto aggiornato."""
    spec = _spec(entity_type)
    obj = db.get(spec["model"], entity_id)
    if not obj or not _belongs(obj, case_id, db):
        raise CorrectionError("Record non trovato in questa pratica")

    edits = []
    if entity_type == "financial_statement":
        edits = _apply_nested(obj, spec["nested"], changes)
    else:
        edits = _apply_flat(obj, spec["fields"], changes)

    if not edits:
        return obj  # nessun cambiamento reale

    for field, old, new in edits:
        db.add(FieldEdit(case_id=case_id, entity_type=entity_type, entity_id=str(entity_id),
                         field=field, old_value=str(old), new_value=str(new),
                         operator=operator, reason=reason))

    _recompute(db, entity_type, obj, {f for f, _, _ in edits})
    db.commit()
    db.refresh(obj)
    return obj


def _belongs(obj, case_id, db):
    if getattr(obj, "case_id", None) == case_id:
        return True
    # tax_debt_item: risale allo statement
    parent_id = getattr(obj, "statement_id", None)
    if parent_id:
        st = db.get(TaxDebtStatement, parent_id)
        return bool(st and st.case_id == case_id)
    return False


def _apply_flat(obj, fields, changes):
    edits = []
    for key, val in (changes or {}).items():
        if key not in fields:
            continue
        new = _coerce(fields[key], val)
        old = getattr(obj, key)
        if old != new:
            setattr(obj, key, new)
            edits.append((key, old, new))
    return edits


def _effective_raw(stmt):
    """Vista corrente del bilancio: fonte + eventuali correzioni (la fonte non si tocca)."""
    import copy
    base = copy.deepcopy(stmt.raw_extraction or {})
    over = stmt.raw_corrected or {}
    for path_kind in EDITABLE["financial_statement"]["nested"].values():
        path = path_kind[0]
        v = _get_path(over, path)
        if v is not None:
            _set_path(base, path, v)
    return base


def _apply_nested(obj, nested, changes):
    # la FONTE (raw_extraction) resta immutabile: le correzioni vivono in raw_corrected
    import copy
    eff = _effective_raw(obj)             # valori attualmente in vigore (per il confronto)
    over = copy.deepcopy(obj.raw_corrected or {})
    edits = []
    for key, val in (changes or {}).items():
        if key not in nested:
            continue
        path, kind = nested[key]
        new = _coerce(kind, val)
        old = _get_path(eff, path)
        if old != new:
            _set_path(over, path, new)
            edits.append((key, old, new))
    if edits:
        obj.raw_corrected = over          # riassegna: triggera il dirty sul JSON
    return edits


def _get_path(d, path):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _set_path(d, path, value):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


# ---------------- ricalcolo deterministico a valle ----------------
def _cur(blk, key):
    v = (blk or {}).get(key)
    return float(v.get("corrente") or 0) if isinstance(v, dict) else 0.0


def _recompute(db, entity_type, obj, changed):
    if entity_type == "financial_statement":
        _recompute_bilancio(db, obj)
    elif entity_type == "tax_debt_item":
        _recompute_aer(db, obj, changed)
    elif entity_type == "real_estate":
        _recompute_immobile(obj, changed)
    elif entity_type in ("credit_exposure", "guarantee_given"):
        _recompute_cr_totali(db, obj.case_id)


def _recompute_bilancio(db, stmt):
    raw = _effective_raw(stmt)   # fonte + correzioni: gli indici si ricalcolano sul dato corretto
    sp, ce, deb = raw.get("stato_patrimoniale") or {}, raw.get("conto_economico") or {}, raw.get("debiti_per_natura") or {}
    # denormalizzati
    stmt.total_assets = _cur(sp, "totale_attivo")
    stmt.equity = _cur(sp, "patrimonio_netto")
    stmt.total_debts = _cur(sp, "debiti_totali")
    stmt.revenues = _cur(ce, "ricavi_vendite")
    stmt.net_result = _cur(ce, "utile_perdita")
    # indici: cancella e ricalcola
    for ind in list(stmt.indicators):
        db.delete(ind)
    db.flush()
    for ind in compute_indicators(sp, ce, deb, stmt.ateco):
        db.add(FinancialIndicator(statement_id=stmt.id, **ind))


def _recompute_aer(db, item, changed):
    # categoria coerente con l'ente, se l'ente è cambiato ma non la categoria
    if "ente_creditore" in changed and "ente_categoria" not in changed:
        item.ente_categoria = aer_parser.ente_categoria(item.ente_creditore)
    # quadrature di riga
    tol = 0.01
    item.needs_review = (
        abs(item.residuo_carico - (item.carico_affidato - item.sgravio - item.gia_pagato - item.stralcio)) > tol
        or abs(item.totale_residuo - (item.residuo_carico + item.interessi_mora + item.oneri_diritti)) > tol
        or abs(item.totale_residuo_netto - (item.totale_residuo - item.importo_sospeso)) > tol
    )
    # ricalcolo statement: totali, conteggi, quadratura, aggregazioni
    st = db.get(TaxDebtStatement, item.statement_id)
    if not st:
        return
    items = list(st.items)
    st.total_residuo = round(sum(i.totale_residuo for i in items), 2)
    st.total_residuo_netto = round(sum(i.totale_residuo_netto for i in items), 2)
    st.total_carico_affidato = round(sum(i.carico_affidato for i in items), 2)
    st.count_proc_attive = sum(1 for i in items if i.proc_attive)
    st.quadrature_ok = all(not i.needs_review for i in items)
    righe = [{
        "ente_categoria": i.ente_categoria, "tipo_documento": i.tipo_documento,
        "totale_residuo": i.totale_residuo, "proc_attive": i.proc_attive,
        "rateizzato": i.rateizzato, "def_agevolata": i.def_agevolata,
        "needs_review": i.needs_review, "data_notifica": i.data_notifica,
    } for i in items]
    raw = dict(st.raw_extraction or {})
    raw["aggregazioni"] = aer_parser._aggregate(righe)
    st.raw_extraction = raw


def _recompute_immobile(re, changed):
    # se l'operatore NON ha forzato a mano il valore catastale, lo ricalcoliamo dagli input
    if "cadastral_value" in changed:
        return
    from app.workers.tasks import _valore_catastale
    re.cadastral_value = _valore_catastale(
        re.cadastral_income, re.category, re.ownership_share, re.is_primary_residence)


def _recompute_cr_totali(db, case_id):
    exps = db.query(CreditExposure).filter_by(case_id=case_id).all()
    gars = db.query(GuaranteeGiven).filter_by(case_id=case_id).all()
    summary = db.query(CreditReportSummary).filter_by(case_id=case_id).order_by(
        CreditReportSummary.id.desc()).first()
    if summary:
        summary.total_exposure = round(sum(e.utilizzato for e in exps), 2)
        summary.total_guarantees = round(sum(g.importo_garantito for g in gars), 2)
