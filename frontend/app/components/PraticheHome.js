import Link from "next/link";

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

export function CasesTable({ cases, loading }) {
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
          {!loading && cases.map((c) => (
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
