"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listCases, createCase } from "./api";

// Normalizza CF/P.IVA: maiuscolo, niente spazi.
function normalizeCf(v) { return (v || "").toUpperCase().replace(/\s+/g, ""); }
// Persona: 16 caratteri alfanumerici. Azienda: 11 cifre.
function isValidPersonaCf(v) { return /^[A-Z0-9]{16}$/.test(normalizeCf(v)); }
function isValidPiva(v) { return /^[0-9]{11}$/.test(normalizeCf(v)); }

export default function Home() {
  const [cases, setCases] = useState([]);
  const [kind, setKind] = useState("persona");   // "persona" | "azienda"
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [denomination, setDenomination] = useState("");
  const [tax, setTax] = useState("");
  const [err, setErr] = useState("");

  async function refresh() {
    try {
      const list = await listCases();
      if (Array.isArray(list)) setCases(list);
    } catch {
      // backend non raggiungibile: lascia la lista corrente, niente crash
    }
  }
  useEffect(() => { refresh(); }, []);

  // cambiando tipo, svuota i campi non pertinenti (per non inviare dati sbagliati)
  function changeKind(k) {
    if (k === kind) return;
    setKind(k);
    setFirstName(""); setLastName(""); setDenomination(""); setTax(""); setErr("");
  }

  const taxValid = kind === "persona" ? isValidPersonaCf(tax) : isValidPiva(tax);
  const canSubmit = kind === "persona"
    ? !!(lastName.trim() && tax.trim())
    : !!(denomination.trim() && tax.trim());

  async function add(e) {
    e.preventDefault();
    setErr("");
    // validazione client
    if (kind === "persona") {
      if (!lastName.trim()) { setErr("Il cognome è obbligatorio."); return; }
      if (!isValidPersonaCf(tax)) { setErr("Codice fiscale non valido: servono 16 caratteri."); return; }
    } else {
      if (!denomination.trim()) { setErr("La denominazione è obbligatoria."); return; }
      if (!isValidPiva(tax)) { setErr("Partita IVA non valida: servono 11 cifre."); return; }
    }
    // payload coi soli campi del tipo scelto
    const payload = kind === "persona"
      ? { client_kind: "persona", first_name: firstName.trim(), last_name: lastName.trim(), client_tax_code: normalizeCf(tax) }
      : { client_kind: "azienda", denomination: denomination.trim(), client_tax_code: normalizeCf(tax) };

    const res = await createCase(payload);
    if (res && res.error) {
      // errore dal backend (es. 422): mostra il messaggio, NON svuotare i campi
      setErr(res.error);
      return;
    }
    // successo: reset e torna a "persona"
    setFirstName(""); setLastName(""); setDenomination(""); setTax(""); setErr("");
    setKind("persona");
    refresh();
  }

  // border completo (no mix shorthand/borderColor, evita warning React)
  const taxInputStyle = { ...inp, border: tax && !taxValid ? "1px solid var(--pd-danger)" : "1px solid var(--pd-border-strong)" };

  return (
    <div>
      <h1 style={{ color: "var(--pd-primary)" }}>Pratiche</h1>
      <form onSubmit={add} style={{ background: "var(--pd-surface)", padding: 16, borderRadius: 8, marginBottom: 24, border: "1px solid var(--pd-border)" }}>
        <strong>Nuova pratica</strong>

        {/* Selettore tipo cliente */}
        <div style={{ marginTop: 12, display: "flex", gap: 0, border: "1px solid var(--pd-accent)", borderRadius: 6, overflow: "hidden", width: "fit-content" }}>
          <button type="button" onClick={() => changeKind("persona")} style={kind === "persona" ? tabActive : tab}>Persona fisica</button>
          <button type="button" onClick={() => changeKind("azienda")} style={kind === "azienda" ? tabActive : tab}>Azienda</button>
        </div>

        {/* Campi condizionali */}
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {kind === "persona" ? (
            <>
              <input aria-label="Nome" placeholder="Nome" value={firstName} onChange={e => setFirstName(e.target.value)} style={inp} />
              <input aria-label="Cognome (obbligatorio)" placeholder="Cognome *" value={lastName} onChange={e => { setLastName(e.target.value); setErr(""); }} style={inp} />
              <input aria-label="Codice fiscale (obbligatorio)" placeholder="Codice fiscale *" value={tax} onChange={e => { setTax(e.target.value); setErr(""); }} style={taxInputStyle} />
            </>
          ) : (
            <>
              <input aria-label="Denominazione (obbligatorio)" placeholder="Denominazione *" value={denomination} onChange={e => { setDenomination(e.target.value); setErr(""); }} style={{ ...inp, minWidth: 220 }} />
              <input aria-label="Partita IVA (obbligatorio)" placeholder="Partita IVA *" value={tax} onChange={e => { setTax(e.target.value); setErr(""); }} style={taxInputStyle} />
            </>
          )}
          <button type="submit" style={canSubmit ? btn : btnDisabled} disabled={!canSubmit}>Crea pratica</button>
        </div>

        {err && <p style={{ color: "var(--pd-danger)", fontSize: 13, margin: "8px 0 0" }}>{err}</p>}
        <p style={{ color: "var(--pd-text-muted)", fontSize: 12, margin: "8px 0 0" }}>* campi obbligatori</p>
      </form>

      <table style={{ width: "100%", borderCollapse: "collapse", background: "var(--pd-surface)", border: "1px solid var(--pd-border)" }}>
        <thead>
          <tr style={{ background: "var(--pd-primary)", color: "var(--pd-surface)", textAlign: "left" }}>
            <th style={th}>Codice</th><th style={th}>Cliente</th><th style={th}>Stato</th><th style={th}></th>
          </tr>
        </thead>
        <tbody>
          {cases.map(c => (
            <tr key={c.id} style={{ borderTop: "1px solid var(--pd-border)" }}>
              <td style={td}>{c.code}</td>
              <td style={td}>{c.client_name}</td>
              <td style={td}>{c.status}</td>
              <td style={td}><Link href={`/pratiche/${c.id}/scheda`} style={{ color: "var(--pd-accent)" }}>Apri →</Link></td>
            </tr>
          ))}
          {cases.length === 0 && <tr><td style={td} colSpan={4}>Nessuna pratica. Creane una sopra.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

const inp = { padding: "8px 10px", border: "1px solid var(--pd-border-strong)", borderRadius: 6, fontSize: 14 };
const btn = { padding: "8px 16px", background: "var(--pd-accent)", color: "var(--pd-surface)", border: "none", borderRadius: 6, cursor: "pointer" };
const btnDisabled = { ...btn, opacity: 0.5, cursor: "not-allowed" };
const tab = { padding: "8px 16px", background: "var(--pd-surface)", color: "var(--pd-accent)", border: "none", cursor: "pointer", fontSize: 14 };
const tabActive = { ...tab, background: "var(--pd-accent)", color: "var(--pd-surface)", fontWeight: "bold" };
const th = { padding: "10px 12px", fontSize: 14 };
const td = { padding: "10px 12px", fontSize: 14 };
