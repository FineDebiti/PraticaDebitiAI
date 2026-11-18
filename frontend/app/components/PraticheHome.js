"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createCase, deleteCase, listCases, listEmbedCases } from "../api";

export const STATUS_TONE = {
  completata: "ok",
  completato: "ok",
  pronto_export: "ok",
  "pronto export": "ok",
  in_lavorazione: "warn",
  "in lavorazione": "warn",
  incompleta: "warn",
  da_verificare: "warn",
  "da verificare": "warn",
  critica: "danger",
  critico: "danger",
  caricamento: "info",
};

export function statusLabel(value) {
  return String(value || "").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function StatusBadge({ status }) {
  const key = (status || "incompleta").toLowerCase();
  const tone = STATUS_TONE[key] || "neutral";
  return <span className={`pd-badge pd-badge--${tone}`}>{statusLabel(status || "incompleta")}</span>;
}

export function Kpi({ label, value, note, tone }) {
  return (
    <div className="pd-kpi">
      <div className="pd-kpi__label">{label}</div>
      <div className="pd-kpi__value" style={tone === "accent" ? { color: "var(--pd-accent)" } : undefined}>{value}</div>
      <div className="pd-kpi__note">{note}</div>
    </div>
  );
}

export function Field({ label, children }) {
  return <label className="pd-field"><span className="pd-field__label">{label}</span>{children}</label>;
}

export function NewCaseForm({
  kind,
  changeKind,
  firstName,
  setFirstName,
  lastName,
  setLastName,
  denomination,
  setDenomination,
  tax,
  setTax,
  taxValid,
  canSubmit,
  err,
  setErr,
  add,
}) {
  const taxClass = tax && !taxValid ? "pd-input" : "pd-input";

  return (
    <form onSubmit={add} className="pd-card">
      <div className="pd-card__head">
        <h2 className="pd-card__title">
          <span className="material-symbols-outlined" aria-hidden="true">add_circle</span>
          Nuova pratica
        </h2>
      </div>
      <div className="pd-segmented" role="tablist" aria-label="Tipo cliente">
        <button type="button" role="tab" aria-selected={kind === "persona"} onClick={() => changeKind("persona")}>Persona fisica</button>
        <button type="button" role="tab" aria-selected={kind === "azienda"} onClick={() => changeKind("azienda")}>Azienda</button>
      </div>
      <div className="pd-grid" style={{ marginTop: 18 }}>
        {kind === "persona" ? (
          <>
            <Field label="Nome"><input className="pd-input" value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Inserisci nome" /></Field>
            <Field label="Cognome"><input className="pd-input" value={lastName} onChange={(e) => { setLastName(e.target.value); setErr(""); }} placeholder="Inserisci cognome" /></Field>
            <Field label="Codice fiscale"><input className={taxClass} value={tax} onChange={(e) => { setTax(e.target.value); setErr(""); }} placeholder="XXXXXX00X00X000X" style={tax && !taxValid ? { borderColor: "var(--pd-danger)" } : undefined} /></Field>
          </>
        ) : (
          <>
            <Field label="Ragione sociale"><input className="pd-input" value={denomination} onChange={(e) => { setDenomination(e.target.value); setErr(""); }} placeholder="Inserisci ragione sociale" /></Field>
            <Field label="Partita IVA"><input className={taxClass} value={tax} onChange={(e) => { setTax(e.target.value); setErr(""); }} placeholder="11 cifre" style={tax && !taxValid ? { borderColor: "var(--pd-danger)" } : undefined} /></Field>
          </>
        )}
        <button className="pd-btn pd-btn--primary" type="submit" disabled={!canSubmit}>
          <span className="material-symbols-outlined" aria-hidden="true">save</span>
          Crea anagrafica
        </button>
        {err && <div className="pd-badge pd-badge--danger" style={{ justifySelf: "start" }}>{err}</div>}
      </div>
    </form>
  );
}

export function DocumentChecklist() {
  const [selectedDoc, setSelectedDoc] = useState(null);

  const docs = [
    {
      title: "Visura camerale ordinaria",
      detail: "Estratta in data recente (ultimi 6 mesi)",
      retrieval: "Scaricabile dal portale Registro Imprese (registroimprese.it) con SPID/CNS o tramite la Camera di Commercio di competenza.",
      structure: "Intestazione Registro Imprese, Sezione Anagrafica (CF, P.IVA, REA), Capitale Sociale, Sede Legale, Organi Sociali ed Esercizi.",
      ocrCheck: "Estrarre P.IVA, Codice ATECO, data costituzione, rappresentanti legali e fatturato."
    },
    {
      title: "Identità e tessera sanitaria",
      detail: "Documento di riconoscimento in corso di validità",
      retrieval: "Fornito direttamente dal debitore o dal legale rappresentante (Carta d'Identità elettronica, Patente o Passaporto + Tessera Sanitaria / Codice Fiscale).",
      structure: "Fronte/retro leggibile, nitido e privo di riflessi. Verificare corrispondenza esatta del Codice Fiscale.",
      ocrCheck: "Riconoscimento nome, cognome, luogo e data di nascita, codice fiscale e data di scadenza."
    },
    {
      title: "Dichiarazioni redditi",
      detail: "Modello 730, REDDITI PF o Modello SC/SP",
      retrieval: "Scaricabile dal cassetto fiscale dell'Agenzia delle Entrate (agenziaentrate.gov.it) tramite SPID/CIE o fornito dal commercialista.",
      structure: "Quadri RN, RB, RC e prospetto di liquidazione imposte completo delle ricevute di presentazione telematica.",
      ocrCheck: "Lettura del reddito complessivo, imponibile netto, ritenute e reddito da lavoro/fabbricati."
    },
    {
      title: "Centrale Rischi Bankitalia",
      detail: "Prospetto sintetico o analitico integrale",
      retrieval: "Richiedibile gratuitamente dal debitore sul servizio online ServizioCR di Banca d'Italia (servizicr.bancaditalia.it) con SPID.",
      structure: "Sezioni Accordato, Utilizzato, Garanzie Prestate e Posizioni a Sofferenza divise per ciascun istituto segnalante.",
      ocrCheck: "Estrazione totale accordato/utilizzato, segnalazioni a sofferenza, sconfinamenti e garanzie."
    },
    {
      title: "Estratto ADeR Riscossione",
      detail: "Estratto di ruolo / Prospetto informativo cartelle",
      retrieval: "Estrabile online dal portale Agenzia delle Entrate - Riscossione (agenziaentrateriscossione.gov.it) accedendo con SPID all'Area Riservata.",
      structure: "Elenco cartelle esattoriali e avvisi di addebito con numero documento, ente creditore, anno di ruolo, importo iniziale e debito residuo.",
      ocrCheck: "Parse tabella ruoli ADeR: ente impositore (INPS, IRPEF, Comune), codice cartella e totale a ruolo."
    },
    {
      title: "Visure catastali",
      detail: "Visura per immobile o per soggetto (immobili e terreni)",
      retrieval: "Scaricabile gratuitamente dalla Consultazione Personale dell'Agenzia delle Entrate o tramite portali catastali.",
      structure: "Prospetto immobili: Foglio, Particella, Subalterno, Categoria catastale, Classe, Consistenza (Mq/Vani) e Rendita catastale.",
      ocrCheck: "Mappatura unità immobiliari, quote di possesso, categorie abitative (A) o depositi (C) e rendite."
    }
  ];

  return (
    <div className="pd-card pd-card--primary">
      <h2 className="pd-card__title">
        <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
        Prerequisiti istruttori (D. Lgs. 14/2019)
      </h2>
      <p className="pd-card__subtitle">Checklist documentale per avvio analisi e tracciabilità delle fonti.</p>
      
      <div className="pd-grid" style={{ marginTop: 18 }}>
        {docs.map((doc) => (
          <div
            key={doc.title}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 12,
              padding: 12,
              borderRadius: "var(--pd-radius)",
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)"
            }}
          >
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start", color: "#fff" }}>
              <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "var(--pd-accent-soft)" }}>upload_file</span>
              <div>
                <strong style={{ display: "block" }}>{doc.title}</strong>
                <span style={{ color: "#b2bdaa", fontSize: 12 }}>{doc.detail}</span>
              </div>
            </div>

            <button
              type="button"
              className="pd-btn pd-btn--ghost"
              style={{ color: "var(--pd-accent-soft)", borderColor: "rgba(255,255,255,0.2)", fontSize: 12, padding: "4px 8px", whiteSpace: "nowrap" }}
              onClick={() => setSelectedDoc(doc)}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>info</span>
              Fac-simile & Guida
            </button>
          </div>
        ))}
      </div>

      {/* FAC-SIMILE & GUIDE MODAL */}
      {selectedDoc && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20
          }}
          onClick={() => setSelectedDoc(null)}
        >
          <div
            className="pd-card"
            style={{ width: 560, maxWidth: "100%", color: "var(--pd-text)", background: "#fff" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pd-card__head">
              <h3 className="pd-card__title" style={{ fontSize: 18, color: "var(--pd-primary)" }}>
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>description</span>
                {selectedDoc.title}
              </h3>
              <button className="pd-btn pd-btn--ghost" onClick={() => setSelectedDoc(null)}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 14 }}>
              <div style={{ padding: 14, background: "var(--pd-surface-low)", borderRadius: "var(--pd-radius)", borderLeft: "4px solid var(--pd-primary)" }}>
                <strong style={{ display: "block", fontSize: 12, textTransform: "uppercase", color: "var(--pd-primary)", marginBottom: 4 }}>
                  Dove recuperare il documento:
                </strong>
                <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
                  {selectedDoc.retrieval}
                </p>
              </div>

              <div>
                <strong style={{ display: "block", fontSize: 12, textTransform: "uppercase", color: "var(--pd-accent)", marginBottom: 4 }}>
                  Struttura del modello / Fac-simile:
                </strong>
                <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
                  {selectedDoc.structure}
                </p>
              </div>

              <div>
                <strong style={{ display: "block", fontSize: 12, textTransform: "uppercase", color: "var(--pd-ok)", marginBottom: 4 }}>
                  Controlli estrazione OCR Backend:
                </strong>
                <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
                  {selectedDoc.ocrCheck}
                </p>
              </div>
            </div>

            <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
              <button className="pd-btn pd-btn--primary" onClick={() => setSelectedDoc(null)}>
                Chiudi Guida
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function CasesTable({ cases, loading, onDelete, readOnly = false }) {
  const [caseToDelete, setCaseToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function handleConfirmDelete() {
    if (readOnly || !caseToDelete || !onDelete) return;
    setIsDeleting(true);
    setDeleteError("");
    try {
      await onDelete(caseToDelete.id);
      setCaseToDelete(null);
    } catch (err) {
      setDeleteError(err.message || "Errore durante l'eliminazione della pratica.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <>
      <div className="pd-table-wrap">
        <table className="pd-table">
          <thead>
            <tr>
              <th>Codice pratica</th>
              <th>Identità cliente</th>
              <th>Stato</th>
              <th>Modulo Attivo</th>
              <th className="pd-num">{readOnly ? "Accesso" : "Azioni Rapide"}</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={5}>Caricamento pratiche...</td></tr>}
            {!loading && cases.map((c) => (
              <tr key={c.id}>
                <td><strong style={{ color: "var(--pd-primary)" }}>#{c.code || c.id}</strong></td>
                <td>
                  <strong>{c.client_name || "Cliente da completare"}</strong>
                  <div className="pd-faint" style={{ fontSize: 12 }}>{c.client_tax_code || "CF/P.IVA non disponibile"}</div>
                </td>
                <td><StatusBadge status={c.status} /></td>
                <td><span className="pd-badge pd-badge--neutral">Dossier Istituzionale</span></td>
                <td className="pd-num">
                  {readOnly ? (
                    <span className="pd-badge pd-badge--neutral">Sola lettura</span>
                  ) : (
                    <div style={{ display: "inline-flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end", alignItems: "center" }}>
                      <Link
                        className="pd-btn pd-btn--ghost"
                        href={`/pratiche/${c.id}/scheda/raccolta`}
                        title="Apri Dati Economici e Raccolta"
                        style={{ fontSize: 12, padding: "4px 8px" }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>database</span>
                        Dati
                      </Link>
                      <Link
                        className="pd-btn pd-btn--ghost"
                        href={`/pratiche/${c.id}/scheda/econometria`}
                        title="Apri Valutazione Econometrica"
                        style={{ fontSize: 12, padding: "4px 8px" }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>analytics</span>
                        Valutazione
                      </Link>
                      <Link
                        className="pd-btn pd-btn--ghost"
                        href={`/pratiche/${c.id}/scheda/report`}
                        title="Apri Report di Pre-Analisi e Scheda Finale"
                        style={{ fontSize: 12, padding: "4px 8px" }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>description</span>
                        Report
                      </Link>
                      <Link
                        className="pd-btn pd-btn--secondary"
                        href={`/pratiche/${c.id}/scheda`}
                        style={{ fontSize: 12, padding: "4px 10px", minHeight: 30 }}
                        title="Apri Scheda Cliente Completa"
                      >
                        Scheda <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 16 }}>chevron_right</span>
                      </Link>
                      <button
                        type="button"
                        className="pd-btn pd-btn--ghost-danger"
                        style={{ fontSize: 12, padding: "4px 8px", minHeight: 30 }}
                        title={`Elimina pratica #${c.code || c.id} e libera il database`}
                        onClick={() => { setCaseToDelete(c); setDeleteError(""); }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                        Elimina
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!loading && cases.length === 0 && <tr><td colSpan={5}>Nessuna pratica trovata con i filtri correnti.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* MODALE CONFERMA ELIMINAZIONE PRATICA */}
      {!readOnly && caseToDelete && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(0, 0, 0, 0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
          }}
          onClick={() => !isDeleting && setCaseToDelete(null)}
        >
          <div
            className="pd-card"
            style={{
              width: 520,
              maxWidth: "100%",
              background: "#ffffff",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.25)",
              borderRadius: "var(--pd-radius-lg)",
              padding: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: "var(--pd-danger-bg)",
                  color: "var(--pd-danger)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 26 }}>warning</span>
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, color: "var(--pd-primary)", fontWeight: 700 }}>
                  Conferma eliminazione pratica
                </h3>
                <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--pd-text-muted)" }}>
                  Azione irreversibile con liberazione completa del database
                </p>
              </div>
            </div>

            <div style={{ fontSize: 14, color: "var(--pd-text)", lineHeight: 1.5, marginBottom: 16 }}>
              <p style={{ margin: "0 0 10px" }}>
                Stai per eliminare definitivamente la pratica:
              </p>
              <div
                style={{
                  padding: 12,
                  background: "var(--pd-surface-low)",
                  borderRadius: "var(--pd-radius)",
                  borderLeft: "4px solid var(--pd-danger)",
                  marginBottom: 12,
                }}
              >
                <strong style={{ color: "var(--pd-primary)", display: "block" }}>
                  #{caseToDelete.code || caseToDelete.id} — {caseToDelete.client_name || "Cliente"}
                </strong>
                <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>
                  CF / P.IVA: {caseToDelete.client_tax_code || "Non specificato"}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)" }}>
                Verranno eliminati in modo permanente tutti i documenti originali, le visure, i bilanci, i debiti tributari AER, i conti correnti, gli indici di crisi e le relazioni elaborate.
              </p>
            </div>

            {deleteError && (
              <div
                style={{
                  marginBottom: 16,
                  padding: "8px 12px",
                  background: "var(--pd-danger-bg)",
                  color: "var(--pd-danger)",
                  borderRadius: "var(--pd-radius)",
                  fontSize: 13,
                }}
              >
                {deleteError}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                type="button"
                className="pd-btn pd-btn--secondary"
                onClick={() => setCaseToDelete(null)}
                disabled={isDeleting}
              >
                Annulla
              </button>
              <button
                type="button"
                className="pd-btn pd-btn--danger"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
              >
                {isDeleting ? (
                  <>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>sync</span>
                    Eliminazione in corso...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete_forever</span>
                    Elimina definitivamente
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function normalizeCf(v) { return (v || "").toUpperCase().replace(/\s+/g, ""); }
function isValidPersonaCf(v) { return /^[A-Z0-9]{16}$/.test(normalizeCf(v)); }
function isValidPiva(v) { return /^[0-9]{11}$/.test(normalizeCf(v)); }

export function PraticheDashboard({ readOnly = false, onLoaded = null, onError = null }) {
  const [cases, setCases] = useState([]);
  const [kind, setKind] = useState("persona");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [denomination, setDenomination] = useState("");
  const [tax, setTax] = useState("");
  const [err, setErr] = useState("");
  const [loadErr, setLoadErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("tutte");

  async function refresh() {
    setLoading(true);
    setLoadErr("");
    try {
      const list = readOnly ? await listEmbedCases() : await listCases();
      if (Array.isArray(list)) {
        setCases(list);
        if (onLoaded) onLoaded(list);
      }
    } catch (e) {
      const msg = e?.message || "Impossibile caricare le pratiche.";
      setCases([]);
      setLoadErr(msg);
      if (onError) onError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, [readOnly]);

  function changeKind(k) {
    if (readOnly || k === kind) return;
    setKind(k);
    setFirstName("");
    setLastName("");
    setDenomination("");
    setTax("");
    setErr("");
  }

  const taxValid = kind === "persona" ? isValidPersonaCf(tax) : isValidPiva(tax);
  const canSubmit = kind === "persona"
    ? !!(lastName.trim() && tax.trim())
    : !!(denomination.trim() && tax.trim());

  async function add(e) {
    e.preventDefault();
    if (readOnly) return;
    setErr("");
    if (kind === "persona") {
      if (!lastName.trim()) { setErr("Il cognome e obbligatorio."); return; }
      if (!isValidPersonaCf(tax)) { setErr("Codice fiscale non valido: servono 16 caratteri."); return; }
    } else {
      if (!denomination.trim()) { setErr("La denominazione e obbligatoria."); return; }
      if (!isValidPiva(tax)) { setErr("Partita IVA non valida: servono 11 cifre."); return; }
    }

    const payload = kind === "persona"
      ? { client_kind: "persona", first_name: firstName.trim(), last_name: lastName.trim(), client_tax_code: normalizeCf(tax) }
      : { client_kind: "azienda", denomination: denomination.trim(), client_tax_code: normalizeCf(tax) };

    const res = await createCase(payload);
    if (res && res.error) {
      setErr(res.error);
      return;
    }
    setFirstName("");
    setLastName("");
    setDenomination("");
    setTax("");
    setKind("persona");
    refresh();
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      const status = (c.status || "").toLowerCase();
      const matchesStatus = statusFilter === "tutte" || status === statusFilter;
      const haystack = `${c.code || ""} ${c.client_name || ""} ${c.client_tax_code || ""} ${c.status || ""}`.toLowerCase();
      return matchesStatus && (!q || haystack.includes(q));
    });
  }, [cases, query, statusFilter]);

  const statuses = useMemo(() => Array.from(new Set(cases.map(c => (c.status || "").toLowerCase()).filter(Boolean))), [cases]);
  const inProgress = cases.filter(c => /lavor|analisi|verif|incomplet/i.test(c.status || "")).length;
  const ready = cases.filter(c => /complet|export|risolt/i.test(c.status || "")).length;

  async function handleDeleteCase(id) {
    if (readOnly) return;
    await deleteCase(id);
    await refresh();
  }

  return (
    <div>
      <div className="pd-page-head">
        <div>
          <h1 className="pd-h1">Gestione pratiche</h1>
          <p>
            {readOnly
              ? "Vista riepilogativa in sola lettura per consultazione da dashboard direzionale."
              : "Centro operativo per apertura, verifica documentale e avanzamento delle pratiche."}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {readOnly && <span className="pd-badge pd-badge--neutral">Sola lettura</span>}
          <button className="pd-btn pd-btn--secondary" type="button" onClick={refresh}>
            <span className="material-symbols-outlined" aria-hidden="true">sync</span>
            Aggiorna
          </button>
        </div>
      </div>

      {loadErr ? (
        <div className="pd-card">
          <div className="pd-badge pd-badge--danger">{loadErr}</div>
        </div>
      ) : (
        <div className="pd-workspace">
          {!readOnly && (
            <section className="pd-grid" aria-label="Nuova pratica">
              <NewCaseForm kind={kind} changeKind={changeKind} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} denomination={denomination} setDenomination={setDenomination} tax={tax} setTax={setTax} taxValid={taxValid} canSubmit={canSubmit} err={err} setErr={setErr} add={add} />
            </section>
          )}

          <section className="pd-grid" aria-label="Elenco pratiche">
            <div className="pd-grid pd-grid--3">
              <Kpi label="Pratiche totali" value={cases.length} note={loading ? "Caricamento dati" : "Archivio corrente"} />
              <Kpi label="In analisi" value={inProgress} note="Da completare o verificare" tone="accent" />
              <Kpi label="Pronte export" value={ready} note="Output revisionabile" />
            </div>

            <div className="pd-card pd-card--tight">
              <div className="pd-card__head">
                <div>
                  <h2 className="pd-card__title">
                    <span className="material-symbols-outlined" aria-hidden="true">folder_shared</span>
                    Pratiche esistenti
                  </h2>
                  <p className="pd-card__subtitle">Ricerca per codice, cliente, CF/P.IVA o stato.</p>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <input className="pd-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Cerca pratica..." style={{ width: 260 }} />
                  <select className="pd-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 170 }}>
                    <option value="tutte">Tutti gli stati</option>
                    {statuses.map(s => <option key={s} value={s}>{statusLabel(s)}</option>)}
                  </select>
                </div>
              </div>
              <CasesTable cases={filtered} loading={loading} onDelete={handleDeleteCase} readOnly={readOnly} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
