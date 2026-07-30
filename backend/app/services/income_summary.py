"""Riepilogo reddito della pratica — CONSOLIDA tutte le fonti reddituali estratte dai
documenti in una vista coerente, normalizzata a mensile.

Problema risolto: i campi piatti del Debtor (monthly_net_income, annual_income) venivano
riempiti da documenti eterogenei (anni e fonti diverse) producendo riepiloghi incoerenti.
Qui invece ogni fonte è esposta con periodo, base e ≈ mensile, raggruppata per natura;
si propone UN reddito mensile consolidato (rappresentante per categoria, poi somma tra categorie)
che l'operatore conferma. ISEE e flussi da estratto conto restano RIFERIMENTI, non sommati.
"""
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Debtor, Document

SUMMABLE = ("lavoro_dipendente", "pensione", "autonomo", "rendite", "altri")
REFERENCE = ("indicatore", "flusso")

CATEGORY_LABELS = {
    "lavoro_dipendente": "Lavoro dipendente",
    "pensione": "Pensione",
    "autonomo": "Lavoro autonomo / impresa",
    "rendite": "Rendite / affitti",
    "altri": "Altri redditi",
    "indicatore": "Indicatore (ISEE)",
    "flusso": "Flussi bancari",
}

INCOME_DOC_TYPES = ("busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi")
SALARY_MENSILITA = 13


def _num(v: Any) -> float:
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _year(s: Any) -> str:
    m = re.search(r"(19|20)\d{2}", str(s or ""))
    return m.group(0) if m else ""


def _annual_equiv(basis: str, amount: float, monthly: float | None, category: str) -> float | None:
    if basis == "annuo":
        return round(_num(amount), 2)
    if basis == "mensile" and monthly is not None:
        factor = SALARY_MENSILITA if category in ("lavoro_dipendente", "pensione") else 12
        return round(_num(monthly) * factor, 2)
    return None


def _src(source: str, doc: Document, *, period: str, basis: str, amount: float, monthly: float | None, category: str, note: str = "") -> dict:
    return {
        "source": source, "doc_type": doc.doc_type, "document_id": doc.id,
        "filename": doc.original_filename, "period": period or "", "year": _year(period),
        "basis": basis, "amount": round(_num(amount), 2),
        "monthly_equiv": (None if monthly is None else round(_num(monthly), 2)),
        "annual_equiv": _annual_equiv(basis, amount, monthly, category),
        "category": category, "category_label": CATEGORY_LABELS.get(category, category),
        "note": note,
    }


def _normalize(doc: Document, data: dict) -> List[dict]:
    dt = doc.doc_type
    out = []

    if dt == "busta_paga":
        netta = _num(data.get("retribuzione_netta"))
        if netta > 0:
            out.append(_src("Busta paga (netto)", doc, period=str(data.get("periodo") or ""),
                            basis="mensile", amount=netta, monthly=netta,
                            category="lavoro_dipendente", note=str(data.get("datore_lavoro") or "")))

    elif dt == "cu":
        compl = _num(data.get("reddito_complessivo"))
        if compl > 0:
            sost = str(data.get("datore_sostituto") or "")
            pensione = bool(re.search(r"INPS|pension|ente.*previd", sost, re.I))
            out.append(_src("CU (reddito complessivo)", doc, period=str(data.get("anno") or ""),
                            basis="annuo", amount=compl, monthly=compl / 12.0,
                            category="pensione" if pensione else "lavoro_dipendente", note=sost))

    elif dt == "isee":
        isee = _num(data.get("isee_ordinario"))
        if isee > 0:
            out.append(_src("ISEE ordinario", doc, period=str(data.get("anno") or ""),
                            basis="indicatore", amount=isee, monthly=None,
                            category="indicatore", note="indicatore del nucleo, non un reddito"))

    elif dt == "estratto_conto":
        agg = data.get("aggregazioni") or {}
        ent = _num(agg.get("entrate_medie_mensili"))
        if ent > 0:
            p = data.get("periodo") or {}
            period = f"{p.get('da') or ''}→{p.get('a') or ''}".strip("→")
            out.append(_src("Estratto conto (entrate medie)", doc, period=period,
                            basis="flusso", amount=ent, monthly=ent, category="flusso",
                            note="flusso lordo in entrata, non reddito netto"))

    elif dt == "dichiarazione_redditi":
        q = data.get("quadri") or {}
        anno = str(data.get("anno_imposta") or "")
        qmap = [
            ("RC_lavoro_dipendente", "lavoro_dipendente", "Dichiarazione · lavoro dipendente (RC)"),
            ("RE_lavoro_autonomo", "autonomo", "Dichiarazione · lavoro autonomo (RE)"),
            ("RF_RG_impresa", "autonomo", "Dichiarazione · impresa (RF/RG)"),
            ("RB_fabbricati", "rendite", "Dichiarazione · fabbricati/affitti (RB)"),
            ("RA_terreni", "rendite", "Dichiarazione · terreni (RA)"),
            ("RH_partecipazioni", "altri", "Dichiarazione · partecipazioni (RH)"),
            ("RL_altri_redditi", "altri", "Dichiarazione · altri redditi (RL)"),
        ]
        for key, cat, label in qmap:
            blk = q.get(key) or {}
            if not blk.get("presente"):
                continue
            reddito = _num(blk.get("reddito"))
            if reddito <= 0:
                continue
            note = ""
            if key == "RB_fabbricati":
                n = int(_num(blk.get("n_immobili_locati")))
                bits = []
                if blk.get("canoni_percepiti"):
                    bits.append(f"canoni € {_num(blk.get('canoni_percepiti')):,.0f}")
                if n:
                    bits.append(f"{n} immobil{'e' if n == 1 else 'i'} locat{'o' if n == 1 else 'i'}")
                note = " · ".join(bits)
            out.append(_src(label, doc, period=anno, basis="annuo", amount=reddito,
                            monthly=reddito / 12.0, category=cat, note=note))

    return out


ADDITIVE = ("rendite", "autonomo", "altri")


def _representative(rows: List[dict]) -> dict:
    if not rows:
        return {}
    maxyear = max((r["year"] for r in rows), default="")
    recent = [r for r in rows if r["year"] == maxyear] or rows
    cat = recent[0]["category"]
    if cat in ADDITIVE:
        chosen = recent
        monthly = round(sum(r["monthly_equiv"] or 0.0 for r in recent), 2)
        annual = round(sum(r["annual_equiv"] or 0.0 for r in recent), 2)
    else:
        mensili = [r for r in recent if r["basis"] == "mensile"]
        chosen = mensili or recent
        mvals = [r["monthly_equiv"] or 0.0 for r in chosen]
        avals = [r["annual_equiv"] or 0.0 for r in chosen]
        monthly = round(sum(mvals) / len(mvals), 2) if mvals else 0.0
        annual = round(sum(avals) / len(avals), 2) if avals else 0.0
    return {
        "category": cat,
        "category_label": recent[0]["category_label"],
        "monthly_equiv": monthly,
        "annual_equiv": annual,
        "year": maxyear,
        "from": [r["source"] for r in chosen],
    }


def _flags(summable: List[dict]) -> List[str]:
    flags = []
    years = sorted({r["year"] for r in summable if r["year"]})
    if len(years) > 1:
        flags.append(f"Fonti di anni diversi ({', '.join(years)}): il consolidato mescola periodi, verifica l'attualità.")
    if any(r["category"] == "rendite" for r in summable):
        flags.append("Le rendite/affitti sono al LORDO da dichiarazione: l'effettivo netto può differire.")
    if any(r["basis"] == "mensile" and r["category"] in ("lavoro_dipendente", "pensione") for r in summable):
        flags.append(f"Annuo stipendi/pensione stimato su {SALARY_MENSILITA} mensilità (ipotesi tredicesima): correggi a mano se 12 o 14.")
    return flags


def compute_income_summary(db: Session, case_id: str) -> dict:
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    docs = (db.query(Document)
            .filter(Document.case_id == case_id, Document.doc_type.in_(INCOME_DOC_TYPES))
            .order_by(Document.created_at.desc()).all())

    sources = []
    for d in docs:
        if d.status not in ("elaborato", "analizzato", "normalizzato") or not (d.extraction and d.extraction.json_output):
            continue
        sources.extend(_normalize(d, d.extraction.json_output))

    summable = [s for s in sources if s["category"] in SUMMABLE]
    references = [s for s in sources if s["category"] in REFERENCE]

    by_cat: Dict[str, List[dict]] = {}
    for s in summable:
        by_cat.setdefault(s["category"], []).append(s)
    representative = [_representative(rows) for rows in by_cat.values() if rows]
    proposed_monthly = round(sum(r.get("monthly_equiv", 0.0) or 0.0 for r in representative), 2)
    proposed_annual = round(sum(r.get("annual_equiv", 0.0) or 0.0 for r in representative), 2)

    return {
        "sources": sources,
        "summable": summable,
        "references": references,
        "representative": representative,
        "proposed_monthly": proposed_monthly,
        "proposed_annual": proposed_annual,
        "salary_mensilita": SALARY_MENSILITA,
        "current_monthly": round(_num(debtor.monthly_net_income), 2) if debtor else 0.0,
        "current_annual": round(_num(debtor.annual_income), 2) if debtor else 0.0,
        "flags": _flags(summable),
        "has_data": len(sources) > 0,
    }
