"""
Client per l'API COMPANY di Openapi.it (dati azienda Italia) — SINCRONO.
Diverso da Visengine: risposta immediata, niente polling.

Base: https://company.openapi.com  (sandbox: https://test.company.openapi.com)
Auth: header "Authorization: Bearer <COMPANY_TOKEN>"
Endpoint Italia usati:
  - GET /IT-advanced/{vatCode_taxCode_or_id}  -> dati completi sincroni (default)
  - GET /IT-start/{vatCode_taxCode_or_id}     -> dati base (fallback/leggero)
Doc: il PDF Company. Risposta: {data:[...], success, message, error}.
"""
import httpx
from app.config import settings


class CompanyError(Exception):
    pass


def _headers():
    if not settings.company_token:
        raise CompanyError("Token Company mancante: imposta COMPANY_TOKEN nel .env")
    return {"Authorization": f"Bearer {settings.company_token}"}


def _get(path: str) -> dict:
    with httpx.Client(base_url=settings.company_base_url, timeout=30) as c:
        r = c.get(path, headers=_headers())
        if r.status_code == 402:
            raise CompanyError("Credito Company insufficiente o limite giornaliero superato (HTTP 402)")
        if r.status_code == 404:
            raise CompanyError("Azienda non trovata per il codice fornito (404)")
        r.raise_for_status()
        body = r.json()
        data = body.get("data")
        # 'data' e sempre un array; prendiamo il primo
        if isinstance(data, list):
            return data[0] if data else {}
        return data or {}


def fetch_advanced(identifier: str) -> dict:
    """GET IT-advanced: dati azienda completi (sincrono). identifier = P.IVA o CF."""
    return _get(f"/IT-advanced/{identifier}")


def fetch_start(identifier: str) -> dict:
    """GET IT-start: dati azienda base (sincrono)."""
    return _get(f"/IT-start/{identifier}")


# ---------- Mapping risposta Company -> campi scheda (nomi REALI dalla doc) ----------
def _address_to_str(addr: dict) -> str:
    """Compone l'indirizzo della sede legale in una stringa leggibile."""
    ro = (addr or {}).get("registeredOffice") or {}
    parts = []
    street = ro.get("streetName") or ro.get("street") or ""
    num = ro.get("streetNumber") or ""
    if street:
        parts.append(f"{street} {num}".strip())
    town = ro.get("town") or ""
    zip_ = ro.get("zipCode") or ""
    prov = ro.get("province") or ""
    loc = " ".join(x for x in [zip_, town, f"({prov})" if prov else ""] if x).strip()
    if loc:
        parts.append(loc)
    return ", ".join(parts)


def map_company(x: dict) -> dict:
    """Mappa la risposta IT-advanced nei campi che usiamo nella scheda azienda.
    Nomi campi REALI dalla documentazione Company (IT-advanced)."""
    if not x:
        return {}
    bs = ((x.get("balanceSheets") or {}).get("last")) or {}
    ateco = (x.get("atecoClassification") or {}).get("ateco") or {}
    legal = x.get("detailedLegalForm") or {}
    soci = []
    for s in x.get("shareHolders", []) or []:
        nome = s.get("companyName") or f"{s.get('name','')} {s.get('surname','')}".strip()
        soci.append({
            "denominazione": nome,
            "codice_fiscale": s.get("taxCode"),
            "quota_percentuale": s.get("percentShare"),
        })
    return {
        "denominazione": x.get("companyName"),
        "partita_iva": x.get("vatCode"),
        "codice_fiscale": x.get("taxCode"),
        "pec": x.get("pec"),
        "sede_legale": _address_to_str(x.get("address")),
        "stato_attivita": x.get("activityStatus"),
        "forma_giuridica": legal.get("description"),
        "ateco": f"{ateco.get('code','')} {ateco.get('description','')}".strip(),
        "rea": x.get("reaCode"),
        "cciaa": x.get("cciaa"),
        "cessata": x.get("taxCodeCeased"),
        # bilancio essenziale (da balanceSheets.last)
        "fatturato": bs.get("turnover"),
        "dipendenti": bs.get("employees"),
        "capitale_sociale": bs.get("shareCapital"),
        "patrimonio_netto": bs.get("netWorth"),
        "anno_bilancio": bs.get("year"),
        "soci": soci,
        "_raw": x,  # diagnostica: risposta grezza completa
    }
