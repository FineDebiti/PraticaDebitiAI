"use client";

import { useEffect, useMemo, useState } from "react";
import { createCase, listCases } from "./api";
import { CasesTable, DocumentChecklist, Kpi, NewCaseForm, statusLabel } from "./components/PraticheHome";

function normalizeCf(v) { return (v || "").toUpperCase().replace(/\s+/g, ""); }
function isValidPersonaCf(v) { return /^[A-Z0-9]{16}$/.test(normalizeCf(v)); }
function isValidPiva(v) { return /^[0-9]{11}$/.test(normalizeCf(v)); }

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
          <NewCaseForm kind={kind} changeKind={changeKind} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} denomination={denomination} setDenomination={setDenomination} tax={tax} setTax={setTax} taxValid={taxValid} canSubmit={canSubmit} err={err} setErr={setErr} add={add} />
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
