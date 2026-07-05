"use client";
import { useEffect, useRef, useState } from "react";
import { getCase, uploadDoc, docFileUrl, deleteDoc } from "../api";

/* Pannello documenti riutilizzabile: upload + tabella documenti (con stato)
   + tabella posizioni debitorie estratte. Si auto-aggiorna ogni 3s perché
   i documenti vengono elaborati in background (OCR + estrazione AI).
   onProcessed() viene chiamata quando un documento passa a "elaborato",
   così la pagina che ci contiene può ricaricare i dati estratti (es. immobili). */
export default function DocumentsPanel({ caseId, onProcessed }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const prevStatuses = useRef({}); // id documento -> ultimo stato visto

  async function refresh() {
    let c;
    try {
      c = await getCase(caseId);
    } catch {
      // backend non raggiungibile (es. stack fermo): ignora, riprova al prossimo giro
      return;
    }
    if (!c || c.error) return;
    // rileva i documenti appena passati a "elaborato" e notifica il genitore
    let justProcessed = false;
    for (const doc of c.documents || []) {
      const before = prevStatuses.current[doc.id];
      if (before && before !== "elaborato" && doc.status === "elaborato") justProcessed = true;
      prevStatuses.current[doc.id] = doc.status;
    }
    setData(c);
    if (justProcessed && onProcessed) onProcessed();
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [caseId]);

  const [notice, setNotice] = useState("");
  async function onFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true); setNotice("");
    const res = await uploadDoc(caseId, file).catch(() => null);
    setBusy(false);
    e.target.value = "";
    if (res && res.duplicate) setNotice(`"${res.original_filename}" è già presente: non è stato ricaricato.`);
    refresh();
  }

  async function onDelete(doc) {
    if (!window.confirm(`Eliminare "${doc.original_filename}"? L'azione è irreversibile.`)) return;
    await deleteDoc(caseId, doc.id);
    refresh();
  }

  if (!data) return <p style={{ color: "var(--pd-text-muted)" }}>Caricamento documenti…</p>;

  return (
    <div>
      <h2 style={{ color: "var(--pd-accent)", marginTop: 0, fontSize: 18 }}>📎 Documenti</h2>

      {/* Upload */}
      <div style={card}>
        <p style={{ fontSize: 13, color: "var(--pd-text-muted)", margin: "0 0 8px" }}>
          PDF o immagine. Verrà elaborato automaticamente (OCR + estrazione AI).
        </p>
        <input type="file" onChange={onFile} disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.tiff" />
        {busy && <span style={{ marginLeft: 10 }}>Upload…</span>}
        {notice && <div style={{ marginTop: 8, color: "var(--pd-warn)", fontSize: 13, background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "6px 10px" }}>⚠ {notice}</div>}
      </div>

      {/* Tabella documenti */}
      <table style={tbl}>
        <thead><tr style={trh}><th style={th}>File</th><th style={th}>Tipo</th><th style={th}>Stato</th><th style={th}></th><th style={th}></th></tr></thead>
        <tbody>
          {(data.documents || []).map(d => (
            <tr key={d.id} style={{ borderTop: "1px solid var(--pd-border)" }}>
              <td style={td}>
                <a href={docFileUrl(caseId, d.id)} target="_blank" rel="noopener noreferrer"
                  style={{ color: "var(--pd-accent)", textDecoration: "none" }}>{d.original_filename}</a>
              </td>
              <td style={td}>{d.doc_type}{d.classification_confidence ? ` (${Math.round(d.classification_confidence * 100)}%)` : ""}</td>
              <td style={td}>{statusBadge(d.status)}{d.error ? <div style={{ color: "var(--pd-danger)", fontSize: 12 }}>{d.error}</div> : null}</td>
              <td style={td}>
                <a href={docFileUrl(caseId, d.id)} target="_blank" rel="noopener noreferrer"
                  style={{ color: "var(--pd-accent)", fontSize: 13 }}>Apri ↗</a>
              </td>
              <td style={td}>
                <button type="button" onClick={() => onDelete(d)} aria-label={`Elimina ${d.original_filename}`}
                  style={{ background: "none", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "3px 9px", cursor: "pointer", color: "var(--pd-danger)", fontSize: 13 }}>🗑 Elimina</button>
              </td>
            </tr>
          ))}
          {(data.documents || []).length === 0 && <tr><td style={td} colSpan={5}>Nessun documento.</td></tr>}
        </tbody>
      </table>

      <p style={{ fontSize: 12, color: "var(--pd-text-faint)", marginTop: 12 }}>
        I dati estratti dai documenti compaiono nelle sezioni dedicate della scheda
        (Patrimonio, Posizione bancaria, Debiti AER, Aziende).
      </p>
    </div>
  );
}

function statusBadge(s) {
  const v = { caricato: "neutral", in_elaborazione: "warn", elaborato: "ok", errore: "danger" }[s] || "neutral";
  return <span className={`pd-badge pd-badge--${v}`}>{s}</span>;
}

const card = { background: "var(--pd-surface-2)", padding: 12, borderRadius: 8, border: "1px solid var(--pd-border)", marginBottom: 16 };
const tbl = { width: "100%", borderCollapse: "collapse", background: "var(--pd-surface)", border: "1px solid var(--pd-border)", marginBottom: 8 };
const trh = { background: "var(--pd-primary)", color: "var(--pd-surface)", textAlign: "left" };
const th = { padding: "8px 10px", fontSize: 13 };
const td = { padding: "8px 10px", fontSize: 13 };
