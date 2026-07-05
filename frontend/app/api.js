const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listCases() {
  const r = await fetch(`${BASE}/api/cases`, { cache: "no-store" });
  return r.json();
}
export async function createCase(payload) {
  const r = await fetch(`${BASE}/api/cases`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    // backend valida il codice fiscale: in caso di errore risponde 422 con { detail }
    let detail = "Errore nella creazione della pratica.";
    try { const body = await r.json(); detail = body.detail || detail; } catch {}
    return { error: detail };
  }
  return r.json();
}
export async function getCase(id) {
  const r = await fetch(`${BASE}/api/cases/${id}`, { cache: "no-store" });
  return r.json();
}
export async function uploadDoc(caseId, file, docType = "") {
  const fd = new FormData();
  fd.append("file", file);
  if (docType) fd.append("doc_type", docType);   // upload mirato: tipo già noto
  const r = await fetch(`${BASE}/api/cases/${caseId}/documents`, { method: "POST", body: fd });
  return r.json();
}

// ---------- Estratto di ruolo AER ----------
export async function uploadAer(caseId, file, ownerKind = "person", entityId = "") {
  const fd = new FormData();
  fd.append("file", file);
  const q = new URLSearchParams({ owner_kind: ownerKind, entity_id: entityId || "" });
  const r = await fetch(`${BASE}/api/cases/${caseId}/aer/upload?${q}`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Errore upload AER");
  return r.json();
}

export async function deleteAer(caseId, stmtId) {
  await fetch(`${BASE}/api/cases/${caseId}/aer/${stmtId}`, { method: "DELETE" });
}

// ---------- Correzione tracciata dei dati estratti ----------
export async function patchRecord(caseId, entityType, entityId, changes, reason = "") {
  const r = await fetch(`${BASE}/api/cases/${caseId}/records/${entityType}/${entityId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ changes, reason }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Errore correzione");
  return r.json();
}

export async function getEdits(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/edits`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

export async function deleteDoc(caseId, docId) {
  await fetch(`${BASE}/api/cases/${caseId}/documents/${docId}`, { method: "DELETE" });
}

// URL del file originale di un documento (per aprirlo/scaricarlo in una nuova scheda).
export function docFileUrl(caseId, docId) {
  return `${BASE}/api/cases/${caseId}/documents/${docId}/file`;
}

// Documenti di reddito della pratica con il dettaglio estratto (per il pannello dettaglio).
export async function getIncomeDocuments(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/income/documents`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

// Riepilogo reddito consolidato (fonti normalizzate a mensile + proposta).
export async function getIncomeSummary(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/income/summary`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

export async function getIndicators(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/indicators`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

// ---------- Indice CF cross-pratica (correlati) ----------
export async function relatedCases(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/related`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

export async function openRelated(caseId, toCaseId) {
  await fetch(`${BASE}/api/cases/${caseId}/related/open`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_case_id: toCaseId }),
  });
}

// ---------- Scheda cliente ----------
export async function getCard(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/card`, { cache: "no-store" });
  return r.json();
}
export async function saveDebtor(caseId, data) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/debtor`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}
export async function addRealEstate(caseId, data) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/real-estates`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  });
  return r.json();
}
export async function saveCompany(caseId, company) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/company`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(company),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return { error: body.detail || "Errore nel salvataggio dell'azienda." };
  return body;
}
export async function createCompany(caseId, company) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/companies`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(company),
  });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nel salvataggio dell'azienda." };
  return b;
}
export async function updateCompany(caseId, cid, company) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/companies/${cid}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(company),
  });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nel salvataggio dell'azienda." };
  return b;
}
export async function deleteCompany(caseId, cid) {
  await fetch(`${BASE}/api/cases/${caseId}/companies/${cid}`, { method: "DELETE" });
}
export async function promoteCompany(caseId, cid) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/companies/${cid}/promote`, { method: "POST" });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nella promozione dell'azienda." };
  return b;
}
export async function delRealEstate(caseId, id) {
  await fetch(`${BASE}/api/cases/${caseId}/real-estates/${id}`, { method: "DELETE" });
}
export async function addVehicle(caseId, data) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/vehicles`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  });
  return r.json();
}
export async function delVehicle(caseId, id) {
  await fetch(`${BASE}/api/cases/${caseId}/vehicles/${id}`, { method: "DELETE" });
}


export async function setPrimaryResidence(caseId, reId, isPrimary) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/real-estates/${reId}/primary-residence`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_primary_residence: isPrimary }),
  });
  return r.json();
}

// ---------- Ricerca Openapi asincrona (visure camerali reali) ----------
export async function openapiSearch(caseId, source, query, params = {}) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/openapi/search`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, query, params }),
  });
  return r.json();
}
export async function openapiRequests(caseId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/openapi/requests`, { cache: "no-store" });
  return r.json();
}
export async function openapiRequest(caseId, reqId) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/openapi/requests/${reqId}`, { cache: "no-store" });
  return r.json();
}

// ---------- Openapi Company (dati azienda, sincrono) ----------
export async function companyFill(caseId, identifier = "", level = "advanced") {
  const r = await fetch(`${BASE}/api/cases/${caseId}/company/fill`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, level }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return { error: body.detail || "Errore nel recupero dati aziendali." };
  return body; // { identifier, level, data }
}
export async function companyImport(caseId, data) {
  const r = await fetch(`${BASE}/api/cases/${caseId}/company/import`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return { error: body.detail || "Errore nel salvataggio dell'azienda." };
  return body; // { ok, company_id }
}
