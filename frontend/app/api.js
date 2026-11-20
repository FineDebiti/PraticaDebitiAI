export function getApiBase() {
  if (typeof window !== "undefined") {
    const host = window.location?.hostname;
    if (window.location?.protocol === "https:") {
      return "";
    }
    if (host && window.location?.port === "3001") {
      return `http://${host}:8000`;
    }
    return "";
  }
  return process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

let _inMemorySessionToken = "";

export function setSessionToken(token) {
  _inMemorySessionToken = (token || "").trim();
}

export function getSessionToken() {
  return _inMemorySessionToken;
}

export function apiFetch(url, options = {}) {
  const nextOptions = {
    credentials: "same-origin",
    ...options,
  };
  if (_inMemorySessionToken) {
    const headers = new Headers(options.headers || {});
    if (!headers.has("X-DossierLex-Session")) {
      headers.set("X-DossierLex-Session", _inMemorySessionToken);
    }
    nextOptions.headers = headers;
  }
  return fetch(url, nextOptions);
}

export async function listCases() {
  const r = await apiFetch(`${getApiBase()}/api/cases`, { cache: "no-store" });
  return r.json();
}

export async function listEmbedCases() {
  const r = await apiFetch("/api/embed/cases", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!r.ok) {
    let detail = "Accesso embed non autorizzato o sessione scaduta.";
    try {
      const body = await r.json();
      detail = body.detail || detail;
    } catch {}
    const err = new Error(detail);
    err.status = r.status;
    throw err;
  }
  return r.json();
}
export async function checkHealth() {
  try {
    const r = await apiFetch(`${getApiBase()}/api/health`, { cache: "no-store" });
    return r.ok;
  } catch {
    return false;
  }
}
export async function createCase(payload) {
  const r = await apiFetch(`${getApiBase()}/api/cases`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    // backend valida il codice fiscale: in caso di errore risponde 422 con { detail }
    let detail = "Errore nella creazione della pratica.";
    try {
      const body = await r.json();
      if (typeof body?.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      }
    } catch {}
    return { error: detail };
  }
  return r.json();
}
export async function getCase(id) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${id}`, { cache: "no-store" });
  return r.json();
}
export async function deleteCase(id) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${id}`, { method: "DELETE" });
  if (!r.ok) {
    let detail = "Errore durante l'eliminazione della pratica.";
    try { const body = await r.json(); detail = body.detail || detail; } catch {}
    throw new Error(detail);
  }
  return r.json();
}
export async function uploadDoc(caseId, file, docType = "") {
  const fd = new FormData();
  fd.append("file", file);
  if (docType) fd.append("doc_type", docType);   // upload mirato: tipo già noto
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/documents`, { method: "POST", body: fd });
  return r.json();
}

// ---------- Estratto di ruolo AER ----------
export async function uploadAer(caseId, file, ownerKind = "person", entityId = "") {
  const fd = new FormData();
  fd.append("file", file);
  const q = new URLSearchParams({ owner_kind: ownerKind, entity_id: entityId || "" });
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/aer/upload?${q}`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Errore upload AER");
  return r.json();
}

export async function deleteAer(caseId, stmtId) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/aer/${stmtId}`, { method: "DELETE" });
}

// ---------- Correzione tracciata dei dati estratti ----------
export async function patchRecord(caseId, entityType, entityId, changes, reason = "") {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/records/${entityType}/${entityId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ changes, reason }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Errore correzione");
  return r.json();
}

export async function getEdits(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/edits`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

export async function deleteDoc(caseId, docId) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/documents/${docId}`, { method: "DELETE" });
}

// URL del file originale di un documento (per aprirlo/scaricarlo in una nuova scheda).
export function docFileUrl(caseId, docId) {
  return `${getApiBase()}/api/cases/${caseId}/documents/${docId}/file`;
}

// Documenti di reddito della pratica con il dettaglio estratto (per il pannello dettaglio).
export async function getIncomeDocuments(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/income/documents`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

// Riepilogo reddito consolidato (fonti normalizzate a mensile + proposta).
export async function getIncomeSummary(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/income/summary`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

export async function getIndicators(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/indicators`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

// ---------- Indice CF cross-pratica (correlati) ----------
export async function relatedCases(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/related`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}

export async function openRelated(caseId, toCaseId) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/related/open`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_case_id: toCaseId }),
  });
}

// ---------- Scheda cliente ----------
export async function getCard(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/card`, { cache: "no-store" });
  return r.json();
}
export async function saveDebtor(caseId, data) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/debtor`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}
export async function addRealEstate(caseId, data) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/real-estates`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  });
  return r.json();
}
export async function createCompany(caseId, company) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/companies`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(company),
  });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nel salvataggio dell'azienda." };
  return b;
}
export async function updateCompany(caseId, cid, company) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/companies/${cid}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(company),
  });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nel salvataggio dell'azienda." };
  return b;
}
export async function deleteCompany(caseId, cid) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/companies/${cid}`, { method: "DELETE" });
}
export async function promoteCompany(caseId, cid) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/companies/${cid}/promote`, { method: "POST" });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) return { error: b.detail || "Errore nella promozione dell'azienda." };
  return b;
}
export async function delRealEstate(caseId, id) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/real-estates/${id}`, { method: "DELETE" });
}
export async function addVehicle(caseId, data) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/vehicles`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  });
  return r.json();
}
export async function delVehicle(caseId, id) {
  await apiFetch(`${getApiBase()}/api/cases/${caseId}/vehicles/${id}`, { method: "DELETE" });
}


export async function setPrimaryResidence(caseId, reId, isPrimary) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/real-estates/${reId}/primary-residence`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_primary_residence: isPrimary }),
  });
  return r.json();
}

// ---------- Ricerca Openapi asincrona (visure camerali reali) ----------
export async function openapiSearch(caseId, source, query, params = {}) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/openapi/search`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, query, params }),
  });
  return r.json();
}
export async function openapiRequests(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/openapi/requests`, { cache: "no-store" });
  return r.json();
}
export async function openapiRequest(caseId, reqId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/openapi/requests/${reqId}`, { cache: "no-store" });
  return r.json();
}

// ---------- Openapi Company (dati azienda, sincrono) ----------
export async function companyFill(caseId, identifier = "", level = "advanced") {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/company/fill`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, level }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return { error: body.detail || "Errore nel recupero dati aziendali." };
  return body; // { identifier, level, data }
}
export async function companyImport(caseId, data) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/company/import`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return { error: body.detail || "Errore nel salvataggio dell'azienda." };
  return body; // { ok, company_id }
}

// ---------- Super-Analisi Trasversale (Qwen) ----------
export async function runCrossAnalysis(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/cross-analysis`, {
    method: "POST", headers: { "Content-Type": "application/json" },
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || "Errore durante l'analisi trasversale.");
  }
  return r.json();
}

export async function getCrossAnalysis(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/cross-analysis`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

export async function getPreanalysisReport(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/preanalysis-report`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

export async function reanalyzeCase(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/reanalyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || "Errore durante la riesecuzione della pre-analisi");
  }
  return r.json();
}

export function getPreanalysisReportPdfUrl(caseId, orientation = "portrait", action = "download") {
  return `${getApiBase()}/api/cases/${caseId}/preanalysis-report/pdf?orientation=${orientation}&action=${action}`;
}

export function getTechnicalDossierPdfUrl(caseId, action = "download") {
  return `${getApiBase()}/api/cases/${caseId}/preanalysis-report/dossier-pdf?action=${action}`;
}

export function getAuditExportUrl(caseId, format = "json") {
  return `${getApiBase()}/api/cases/${caseId}/preanalysis-report/audit-export?format=${format}`;
}

// ---------- Chat e Assistente AI di Pratica ----------
export async function getCaseChat(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/chat`, { cache: "no-store" });
  if (!r.ok) return { total: 0, messages: [] };
  return r.json();
}

export async function sendCaseChatMessage(caseId, message) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    cache: "no-store",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || "Errore durante l'invio del messaggio all'AI");
  }
  return r.json();
}

export async function streamCaseChatMessage(caseId, message, { onDelta, onDone, onError }) {
  try {
    const response = await apiFetch(`${getApiBase()}/api/cases/${caseId}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      cache: "no-store",
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Errore HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          const jsonStr = trimmed.slice(6).trim();
          if (!jsonStr) continue;
          try {
            const data = JSON.parse(jsonStr);
            if (data.type === "delta" && data.delta) {
              onDelta(data.delta);
            } else if (data.type === "done") {
              onDone(data);
            } else if (data.type === "error") {
              onError(new Error(data.error));
            }
          } catch (e) {
            console.warn("Parse error SSE chunk:", e);
          }
        }
      }
    }
  } catch (err) {
    onError(err);
  }
}

export async function clearCaseChat(caseId) {
  const r = await apiFetch(`${getApiBase()}/api/cases/${caseId}/chat`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!r.ok) return { success: false };
  return r.json();
}
