"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { createCase, listCases } from "./api";

function normalizeCf(v) { return (v || "").toUpperCase().replace(/\s+/g, ""); }
function isValidPersonaCf(v) { return /^[A-Z0-9]{16}$/.test(normalizeCf(v)); }
function isValidPiva(v) { return /^[0-9]{11}$/.test(normalizeCf(v)); }

const STATUS_TONE = {
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

export default function Home() {
  const [cases, setCases] = useState([]);
  const [kind, setKind] = useState("persona");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [denomination, setDenomination] = useState("");
  const [tax, setTax] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("tutte");

  async function refresh() {
    setLoading(true);
    try {
      const list = await listCases();
      if (Array.isArray(list)) setCases(list);
    } catch {
      setCases([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  function changeKind(k) {
    if (k === kind) return;
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

  return (
    <div>
      <div className="pd-page-head">
        <div>
          <h1 className="pd-h1">Gestione pratiche</h1>
          <p>Centro operativo per apertura, verifica documentale e avanzamento delle pratiche.</p>
        </div>
        <button className="pd-btn pd-btn--secondary" type="button" onClick={refresh}>
          <span className="material-symbols-outlined" aria-hidden="true">sync</span>
          Aggiorna
        </button>
      </div>

      <div className="pd-workspace">
        <section className="pd-grid" aria-label="Nuova pratica e prerequisiti">
          <NewCaseForm
            kind={kind}
            changeKind={changeKind}
            firstName={firstName}
            setFirstName={setFirstName}
            lastName={lastName}
            setLastName={setLastName}
            denomination={denomination}
            setDenomination={setDenomination}
            tax={tax}
            setTax={setTax}
            taxValid={taxValid}
            canSubmit={canSubmit}
            err={err}
            setErr={setErr}
            add={add}
          />
          <DocumentChecklist />
        </section>

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
            <CasesTable cases={filtered} loading={loading} />
          </div>
        </section>
      </div>
    </div>
  );
}

function NewCaseForm(props) {
  const taxClass = props.tax && !props.taxValid ? "pd-input" : "pd-input";
  return (
    <form onSubmit={props.add} className="pd-card">
      <div className="pd-card__head">
        <h2 className="pd-card__title">
          <span className="material-symbols-outlined" aria-hidden="true">add_circle</span>
          Nuova pratica
        </h2>
      </div>
      <div className="pd-segmented" role="tablist" aria-label="Tipo cliente">
        <button type="button" role="tab" aria-selected={props.kind === "persona"} onClick={() => props.changeKind("persona")}>Persona fisica</button>
        <button type="button" role="tab" aria-selected={props.kind === "azienda"} onClick={() => props.changeKind("azienda")}>Azienda</button>
      </div>
      <div className="pd-grid" style={{ marginTop: 18 }}>
        {props.kind === "persona" ? (
          <>
            <Field label="Nome"><input className="pd-input" value={props.firstName} onChange={e => props.setFirstName(e.target.value)} placeholder="Inserisci nome" /></Field>
            <Field label="Cognome"><input className="pd-input" value={props.lastName} onChange={e => { props.setLastName(e.target.value); props.setErr(""); }} placeholder="Inserisci cognome" /></Field>
            <Field label="Codice fiscale"><input className={taxClass} value={props.tax} onChange={e => { props.setTax(e.target.value); props.setErr(""); }} placeholder="XXXXXX00X00X000X" style={props.tax && !props.taxValid ? { borderColor: "var(--pd-danger)" } : undefined} /></Field>
          </>
        ) : (
          <>
            <Field label="Ragione sociale"><input className="pd-input" value={props.denomination} onChange={e => { props.setDenomination(e.target.value); props.setErr(""); }} placeholder="Inserisci ragione sociale" /></Field>
            <Field label="Partita IVA"><input className={taxClass} value={props.tax} onChange={e => { props.setTax(e.target.value); props.setErr(""); }} placeholder="11 cifre" style={props.tax && !props.taxValid ? { borderColor: "var(--pd-danger)" } : undefined} /></Field>
          </>
        )}
        <button className="pd-btn pd-btn--primary" type="submit" disabled={!props.canSubmit}>
          <span className="material-symbols-outlined" aria-hidden="true">save</span>
          Crea anagrafica
        </button>
        {props.err && <div className="pd-badge pd-badge--danger" style={{ justifySelf: "start" }}>{props.err}</div>}
      </div>
    </form>
  );
}

function DocumentChecklist() {
  const docs = [
    ["Visura camerale ordinaria", "Estratta in data recente"],
    ["Identita e tessera sanitaria", "Documento in corso di validita"],
    ["Dichiarazioni redditi", "Ultimi esercizi disponibili"],
    ["Centrale Rischi", "Prospetto integrale"],
    ["Estratto AER", "Cartelle e avvisi"],
    ["Visure catastali", "Patrimonio immobiliare"],
  ];
  return (
    <div className="pd-card pd-card--primary">
      <h2 className="pd-card__title">
        <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
        Prerequisiti istruttori
      </h2>
      <p className="pd-card__subtitle">Checklist documentale per avvio analisi e tracciabilita delle fonti.</p>
      <div className="pd-grid" style={{ marginTop: 18 }}>
        {docs.map(([title, detail]) => (
          <div key={title} style={{ display: "flex", gap: 12, alignItems: "flex-start", color: "#fff" }}>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "var(--pd-accent-soft)" }}>upload_file</span>
            <div>
              <strong style={{ display: "block" }}>{title}</strong>
              <span style={{ color: "#b2bdaa", fontSize: 12 }}>{detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CasesTable({ cases, loading }) {
  return (
    <div className="pd-table-wrap">
      <table className="pd-table">
        <thead>
          <tr>
            <th>Codice pratica</th>
            <th>Identita cliente</th>
            <th>Stato</th>
            <th>Fonte</th>
            <th className="pd-num">Azioni</th>
          </tr>
        </thead>
        <tbody>
          {loading && <tr><td colSpan={5}>Caricamento pratiche...</td></tr>}
          {!loading && cases.map(c => (
            <tr key={c.id}>
              <td><strong style={{ color: "var(--pd-primary)" }}>{c.code || c.id}</strong></td>
              <td>
                <strong>{c.client_name || "Cliente da completare"}</strong>
                <div className="pd-faint" style={{ fontSize: 12 }}>{c.client_tax_code || "CF/P.IVA non disponibile"}</div>
              </td>
              <td><StatusBadge status={c.status} /></td>
              <td><span className="pd-badge pd-badge--neutral">Backend</span></td>
              <td className="pd-num">
                <Link className="pd-btn pd-btn--ghost" href={`/pratiche/${c.id}/scheda`}>
                  Apri <span className="material-symbols-outlined" aria-hidden="true">chevron_right</span>
                </Link>
              </td>
            </tr>
          ))}
          {!loading && cases.length === 0 && <tr><td colSpan={5}>Nessuna pratica trovata con i filtri correnti.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, children }) {
  return <label className="pd-field"><span className="pd-field__label">{label}</span>{children}</label>;
}

function Kpi({ label, value, note, tone }) {
  return (
    <div className="pd-kpi">
      <div className="pd-kpi__label">{label}</div>
      <div className="pd-kpi__value" style={tone === "accent" ? { color: "var(--pd-accent)" } : undefined}>{value}</div>
      <div className="pd-kpi__note">{note}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const key = (status || "incompleta").toLowerCase();
  const tone = STATUS_TONE[key] || "neutral";
  return <span className={`pd-badge pd-badge--${tone}`}>{statusLabel(status || "incompleta")}</span>;
}

function statusLabel(s) {
  return String(s || "").replace(/_/g, " ").replace(/\b\w/g, m => m.toUpperCase());
}
