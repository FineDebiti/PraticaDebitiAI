"use client";

import { useEffect, useRef, useState } from "react";
import { deleteDoc, docFileUrl, getCase, uploadDoc } from "../api";

const DOC_TYPE_LABELS = {
  busta_paga: "Busta paga",
  cu: "CU",
  isee: "ISEE",
  estratto_conto: "Estratto conto",
  dichiarazione_redditi: "Dichiarazione redditi",
  visura_catastale: "Visura catastale",
  centrale_rischi: "Centrale Rischi",
  cartella_aer: "Estratto AER",
  visura_camerale: "Visura camerale",
  bilancio: "Bilancio",
};

export default function DocumentsPanel({ caseId, onProcessed }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [priority, setPriority] = useState("ordinaria");
  const prevStatuses = useRef({});

  async function refresh() {
    let c;
    try {
      c = await getCase(caseId);
    } catch {
      return;
    }
    if (!c || c.error) return;
    let justProcessed = false;
    for (const doc of c.documents || []) {
      const before = prevStatuses.current[doc.id];
      if (before && before !== "elaborato" && before !== "normalizzato" && ["elaborato", "normalizzato"].includes(doc.status)) justProcessed = true;
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

  async function onFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    setNotice("");
    const res = await uploadDoc(caseId, file).catch(() => null);
    setBusy(false);
    e.target.value = "";
    if (res && res.duplicate) setNotice(`"${res.original_filename}" e gia presente: deduplicazione applicata.`);
    refresh();
  }

  async function onDelete(doc) {
    if (!window.confirm(`Eliminare "${doc.original_filename}"? L'azione e irreversibile.`)) return;
    await deleteDoc(caseId, doc.id);
    refresh();
  }

  if (!data) return <p className="pd-muted">Caricamento documenti...</p>;

  const docs = data.documents || [];
  const elaborati = docs.filter(d => ["elaborato", "normalizzato"].includes(d.status)).length;
  const review = docs.filter(d => d.error || d.status === "errore" || confidence(d) < 70).length;

  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2 className="pd-h2">Pannello documentale</h2>
          <p>Upload, stato elaborazione, fonte, qualita estrazione, deduplicazione e priorita istruttoria.</p>
        </div>
        <span className="pd-badge pd-badge--info">{docs.length} documenti</span>
      </div>

      <div className="pd-grid pd-grid--3">
        <DocumentKpi label="Elaborati" value={`${elaborati}/${docs.length || 0}`} />
        <DocumentKpi label="Da verificare" value={review} tone={review ? "warn" : "ok"} />
        <DocumentKpi label="Deduplicazione" value="SHA-256" note="Controllo backend" />
      </div>

      <div className="pd-card">
        <div className="pd-card__head">
          <div>
            <h3 className="pd-card__title">
              <span className="material-symbols-outlined" aria-hidden="true">upload_file</span>
              Carica documento
            </h3>
            <p className="pd-card__subtitle">PDF o immagine. OCR ed estrazione vengono gestiti dal backend.</p>
          </div>
          <select className="pd-select" value={priority} onChange={e => setPriority(e.target.value)} style={{ width: 180 }} aria-label="Priorita documentale">
            <option value="ordinaria">Priorita ordinaria</option>
            <option value="alta">Priorita alta</option>
            <option value="critica">Priorita critica</option>
          </select>
        </div>
        <input className="pd-input" type="file" onChange={onFile} disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.tiff" />
        {busy && <p className="pd-muted">Upload in corso...</p>}
        {notice && <div className="pd-badge pd-badge--warn" style={{ marginTop: 10 }}>{notice}</div>}
      </div>

      <div className="pd-table-wrap">
        <table className="pd-table">
          <thead>
            <tr>
              <th>Documento</th>
              <th>Tipo / fonte</th>
              <th>Stato</th>
              <th>Qualita</th>
              <th>Tracciabilita dato</th>
              <th className="pd-num">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => {
              const q = confidence(d);
              return (
                <tr key={d.id} className={d.error || q < 70 ? "pd-row--review" : undefined}>
                  <td>
                    <a href={docFileUrl(caseId, d.id)} target="_blank" rel="noopener noreferrer"><strong>{d.original_filename}</strong></a>
                    <div className="pd-faint" style={{ fontSize: 12 }}>{d.created_at ? String(d.created_at).slice(0, 10) : "Data non disponibile"}</div>
                  </td>
                  <td>
                    <strong>{DOC_TYPE_LABELS[d.doc_type] || d.doc_type || "Non classificato"}</strong>
                    <div className="pd-faint" style={{ fontSize: 12 }}>{d.storage_uri || d.storage_path || "Archivio backend"}</div>
                  </td>
                  <td>{statusBadge(d.status)}{d.error ? <div className="pd-badge pd-badge--danger" style={{ marginTop: 6 }}>{d.error}</div> : null}</td>
                  <td>
                    <QualityBar value={q} />
                    <span className="pd-faint" style={{ fontSize: 12 }}>{q ? `${q}% confidenza` : "Non stimata"}</span>
                  </td>
                  <td>
                    <div className="pd-source-grid" style={{ gridTemplateColumns: "repeat(3, minmax(90px, 1fr))" }}>
                      <Trace label="Grezzo" value="File" />
                      <Trace label="Corretto" value="Audit" />
                      <Trace label="Derivato" value="Backend" />
                    </div>
                  </td>
                  <td className="pd-num">
                    <a className="pd-icon-btn" href={docFileUrl(caseId, d.id)} target="_blank" rel="noopener noreferrer" aria-label={`Apri ${d.original_filename}`}>
                      <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                    </a>{" "}
                    <button type="button" onClick={() => onDelete(d)} className="pd-icon-btn" aria-label={`Elimina ${d.original_filename}`} style={{ color: "var(--pd-danger)" }}>
                      <span className="material-symbols-outlined" aria-hidden="true">delete</span>
                    </button>
                  </td>
                </tr>
              );
            })}
            {docs.length === 0 && <tr><td colSpan={6}>Nessun documento caricato.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DocumentKpi({ label, value, note, tone }) {
  return (
    <div className="pd-kpi">
      <div className="pd-kpi__label">{label}</div>
      <div className="pd-kpi__value" style={tone === "warn" ? { color: "var(--pd-warn)" } : tone === "ok" ? { color: "var(--pd-ok)" } : undefined}>{value}</div>
      <div className="pd-kpi__note">{note || "Stato documentale"}</div>
    </div>
  );
}

function Trace({ label, value }) {
  return <div className="pd-source-box"><label>{label}</label><strong>{value}</strong></div>;
}

function QualityBar({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const color = pct >= 85 ? "var(--pd-ok)" : pct >= 70 ? "var(--pd-warn)" : "var(--pd-danger)";
  return <div className="pd-progress" style={{ height: 6 }}><span style={{ width: `${pct}%`, background: color }} /></div>;
}

function confidence(doc) {
  const n = doc.classification_confidence == null ? null : Math.round(Number(doc.classification_confidence) * 100);
  if (n == null || Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

function statusBadge(s) {
  const v = { caricato: "neutral", in_elaborazione: "warn", elaborato: "ok", normalizzato: "ok", errore: "danger" }[s] || "neutral";
  return <span className={`pd-badge pd-badge--${v}`}>{String(s || "caricato").replace(/_/g, " ")}</span>;
}
