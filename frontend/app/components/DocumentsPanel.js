"use client";

import { useEffect, useRef, useState } from "react";
import { deleteDoc, docFileUrl, getCase, uploadDoc } from "../api";

const DOC_TYPE_LABELS = {
  busta_paga: "Busta paga / Cedolino",
  cu: "Certificazione Unica (CU)",
  isee: "Attestazione ISEE",
  estratto_conto: "Estratto conto bancario",
  dichiarazione_redditi: "Dichiarazione Redditi / Mod. PF-SC",
  visura_catastale: "Visura catastale (Sister)",
  centrale_rischi: "Centrale Rischi Banca d'Italia",
  cartella_aer: "Estratto di Ruolo / Situazione AdER",
  visura_camerale: "Visura Camerale CCIAA",
  bilancio: "Bilancio d'esercizio / Situazione Contabile",
  visura_pra: "Visura PRA / Elenco Beni Mobili",
  contratto_locazione: "Contratto di Locazione / Affitto",
  piano_ammortamento: "Piano di Ammortamento / Mutuo",
};

function formatBytes(bytes) {
  const b = Number(bytes) || 0;
  if (b <= 0) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DocumentsPanel({ caseId, onProcessed }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [notice, setNotice] = useState("");
  const [priority, setPriority] = useState("ordinaria");
  const [docType, setDocType] = useState("da_classificare");
  const prevStatuses = useRef({});
  const fileInputRef = useRef(null);

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
      if (
        before &&
        before !== "elaborato" &&
        before !== "normalizzato" &&
        ["elaborato", "normalizzato"].includes(doc.status)
      ) {
        justProcessed = true;
      }
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

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    setBusy(true);
    setNotice("");
    const duplicates = [];
    const errors = [];
    let uploadedCount = 0;

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      setUploadProgress({ current: i + 1, total: files.length, name: f.name });
      try {
        const res = await uploadDoc(caseId, f, docType);
        if (res && res.duplicate) {
          duplicates.push(f.name);
        } else if (res && res.id) {
          uploadedCount++;
        }
      } catch {
        errors.push(f.name);
      }
    }

    setBusy(false);
    setUploadProgress(null);

    const msgs = [];
    if (uploadedCount > 0) {
      msgs.push(
        `${uploadedCount} ${uploadedCount === 1 ? "documento acquisito" : "documenti acquisiti"} con impronta SHA-256.`
      );
    }
    if (duplicates.length > 0) {
      msgs.push(
        `${duplicates.length} ${duplicates.length === 1 ? "file già presente" : "file già presenti"} (deduplicazione SHA-256 attiva).`
      );
    }
    if (errors.length > 0) {
      msgs.push(`Errore sul caricamento di: ${errors.join(", ")}`);
    }
    if (msgs.length > 0) {
      setNotice(msgs.join(" · "));
    }
    refresh();
  }

  async function onFile(e) {
    if (e.target.files && e.target.files.length) {
      await handleFiles(e.target.files);
      e.target.value = "";
    }
  }

  async function onDelete(doc) {
    if (!window.confirm(`Eliminare "${doc.original_filename}" dal fascicolo? L'azione è irreversibile.`)) return;
    await deleteDoc(caseId, doc.id);
    refresh();
    if (onProcessed) onProcessed();
  }

  if (!data) return <p className="pd-muted">Caricamento inventario documentale...</p>;

  const docs = data.documents || [];
  const elaborati = docs.filter((d) => ["elaborato", "normalizzato"].includes(d.status)).length;
  const inCorso = docs.filter((d) => ["caricato", "in_elaborazione"].includes(d.status)).length;
  const review = docs.filter((d) => d.error || d.status === "errore" || (confidence(d) > 0 && confidence(d) < 70)).length;
  const totalPages = docs.reduce((acc, d) => acc + (Number(d.num_pages) || 0), 0);

  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 4 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 className="pd-h2">Inventario Documentale e Fonti Primarie</h2>
            <span className="pd-badge pd-badge--info">[D] Fonti Documentali</span>
          </div>
          <p>
            Acquisizione file, calcolo impronta crittografica SHA-256 (64 caratteri), estrazione OCR/LLM e normalizzazione nel fascicolo.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="pd-badge pd-badge--ok">{docs.length} {docs.length === 1 ? "documento" : "documenti"}</span>
          {totalPages > 0 && <span className="pd-badge pd-badge--neutral">{totalPages} pagine totali</span>}
        </div>
      </div>

      {/* KPI STRIP */}
      <div className="pd-grid pd-grid--4">
        <div className="pd-kpi">
          <div className="pd-kpi__label">Documenti nel Fascicolo</div>
          <div className="pd-kpi__value">{docs.length}</div>
          <div className="pd-kpi__note">{totalPages > 0 ? `${totalPages} pagine indicizzate` : "Fonti primarie acquisite"}</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Elaborati e Normalizzati</div>
          <div className="pd-kpi__value" style={{ color: elaborati === docs.length && docs.length > 0 ? "var(--pd-ok)" : "var(--pd-primary)" }}>
            {elaborati}/{docs.length || 0}
          </div>
          <div className="pd-kpi__note">{inCorso > 0 ? `${inCorso} in coda di elaborazione` : "Pipeline completata"}</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Tracciabilità Crittografica</div>
          <div className="pd-kpi__value" style={{ fontSize: 22, lineHeight: "40px" }}>SHA-256 (64 hex)</div>
          <div className="pd-kpi__note">Anti-duplicazione e integrità fonte</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Controllo Qualità / Alert</div>
          <div className="pd-kpi__value" style={{ color: review > 0 ? "var(--pd-warn)" : "var(--pd-ok)" }}>
            {review}
          </div>
          <div className="pd-kpi__note">{review > 0 ? "Richiede verifica operatore" : "Nessuna anomalia d'estrazione"}</div>
        </div>
      </div>

      {/* DROPZONE DI CARICAMENTO */}
      <div
        className="pd-card"
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
          if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
          }
        }}
        style={{
          transition: "all 0.2s ease",
          border: isDragging ? "2px dashed var(--pd-accent)" : "1px solid var(--pd-border)",
          background: isDragging ? "rgba(108, 92, 66, 0.06)" : "var(--pd-surface)",
        }}
      >
        <div className="pd-card__head" style={{ flexWrap: "wrap", gap: 16 }}>
          <div>
            <h3 className="pd-card__title">
              <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "var(--pd-accent)" }}>
                cloud_upload
              </span>
              Acquisizione nuovi documenti nel fascicolo
            </h3>
            <p className="pd-card__subtitle">
              Seleziona il tipo documentale (o lascia la classificazione automatica AI) e carica uno o più file PDF/Immagini.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <div className="pd-field" style={{ minWidth: 240 }}>
              <span className="pd-field__label">Classificazione documento</span>
              <select
                className="pd-select"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                aria-label="Tipo documento"
              >
                <option value="da_classificare">✨ Classificazione automatica AI</option>
                {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="pd-field" style={{ minWidth: 165 }}>
              <span className="pd-field__label">Priorità istruttoria</span>
              <select
                className="pd-select"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                aria-label="Priorità documentale"
              >
                <option value="ordinaria">Priorità ordinaria</option>
                <option value="alta">Priorità alta</option>
                <option value="critica">Priorità critica</option>
              </select>
            </div>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={onFile}
          disabled={busy}
          accept=".pdf,.png,.jpg,.jpeg,.tiff"
          style={{ display: "none" }}
        />

        <div
          onClick={() => !busy && fileInputRef.current && fileInputRef.current.click()}
          style={{
            border: "2px dashed var(--pd-border)",
            borderRadius: 8,
            padding: "24px 20px",
            textAlign: "center",
            background: "var(--pd-surface-low)",
            cursor: busy ? "wait" : "pointer",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 36, color: "var(--pd-primary)" }}>
            upload_file
          </span>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--pd-primary)" }}>
            Trascina qui i documenti oppure clicca per sfogliare dal computer
          </div>
          <div style={{ fontSize: 12.5, color: "var(--pd-text-muted)" }}>
            Formati supportati: <strong>PDF, PNG, JPG, TIFF</strong> · Calcolo automatico hash <strong>SHA-256</strong> e blocco duplicati
          </div>
          <div style={{ marginTop: 6 }}>
            <button
              type="button"
              className="pd-btn pd-btn--primary"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                if (fileInputRef.current) fileInputRef.current.click();
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">add_circle</span>
              {busy ? "Acquisizione in corso..." : "Seleziona Documenti"}
            </button>
          </div>
        </div>

        {busy && uploadProgress && (
          <div
            style={{
              marginTop: 12,
              padding: "10px 14px",
              borderRadius: 6,
              background: "var(--pd-info-bg)",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: "var(--pd-primary)" }}>
              hourglass_top
            </span>
            <span style={{ fontSize: 13, color: "var(--pd-primary)" }}>
              Acquisizione e calcolo SHA-256 ({uploadProgress.current}/{uploadProgress.total}):{" "}
              <strong>{uploadProgress.name}</strong>...
            </span>
          </div>
        )}

        {notice && (
          <div style={{ marginTop: 12 }}>
            <span className="pd-badge pd-badge--info" style={{ fontSize: 12.5, padding: "6px 12px" }}>
              {notice}
            </span>
          </div>
        )}
      </div>

      {/* TABELLA INVENTARIO FONTI */}
      <div className="pd-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--pd-border-soft)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h3 className="pd-card__title" style={{ fontSize: 17 }}>
              <span className="material-symbols-outlined" aria-hidden="true">folder_managed</span>
              Registro Fonti Acquisite e Tracciabilità SHA-256
            </h3>
            <p className="pd-card__subtitle" style={{ fontSize: 12.5 }}>
              Ogni documento costituisce fonte primaria <strong>[D]</strong> ed è identificato univocamente nel Dossier Tecnico di Audit.
            </p>
          </div>
          <span className="pd-badge pd-badge--neutral" style={{ fontSize: 11.5 }}>
            Clicca sull&apos;hash SHA-256 per copiare i 64 caratteri completi
          </span>
        </div>

        <div className="pd-table-wrap" style={{ border: 0, borderRadius: 0 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Documento Fonte [D]</th>
                <th>Classificazione & Impronta SHA-256</th>
                <th>Stato Pipeline</th>
                <th>Qualità & Confidenza</th>
                <th>Catena di Custodia</th>
                <th className="pd-num">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => {
                const q = confidence(d);
                const shaFull = d.sha256 || "";
                const sizeLabel = formatBytes(d.size_bytes);
                return (
                  <tr key={d.id} className={d.error || (q > 0 && q < 70) ? "pd-row--review" : undefined}>
                    <td>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 20, color: "var(--pd-accent)", marginTop: 1 }}>
                          description
                        </span>
                        <div>
                          <a
                            href={docFileUrl(caseId, d.id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontWeight: 700, color: "var(--pd-primary)", fontSize: 14 }}
                          >
                            {d.original_filename}
                          </a>
                          <div className="pd-faint" style={{ fontSize: 12, marginTop: 2 }}>
                            Acquisito: {d.created_at ? String(d.created_at).slice(0, 10) : "—"}
                            {d.num_pages ? ` · ${d.num_pages} pag.` : ""}
                            {sizeLabel ? ` · ${sizeLabel}` : ""}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: "var(--pd-text)", fontSize: 13.5 }}>
                        {DOC_TYPE_LABELS[d.doc_type] || d.doc_type || "In classificazione"}
                      </div>
                    </td>
                    <td>
                      {statusBadge(d.status)}
                      {d.status === "errore" && d.error ? (
                        <div className="pd-badge pd-badge--danger" style={{ marginTop: 6, display: "inline-flex" }}>
                          {d.error}
                        </div>
                      ) : null}
                    </td>
                    <td style={{ minWidth: 140 }}>
                      <QualityBar value={q} />
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginTop: 4 }} className="pd-faint">
                        <span>{q ? `${q}% confidenza` : "Verifica"}</span>
                        <span>{d.num_pages ? `${d.num_pages} pp.` : "PDF"}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        <span className="pd-badge pd-badge--info" style={{ fontSize: 11 }}>[D] Fonte Primaria</span>
                        {shaFull && <span className="pd-badge pd-badge--ok" style={{ fontSize: 11 }}>SHA-256 OK</span>}
                        {["elaborato", "normalizzato"].includes(d.status) && (
                          <span className="pd-badge pd-badge--neutral" style={{ fontSize: 11 }}>Normalizzato DB</span>
                        )}
                      </div>
                    </td>
                    <td className="pd-num">
                      <a
                        className="pd-icon-btn"
                        href={docFileUrl(caseId, d.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Apri PDF originale: ${d.original_filename}`}
                        aria-label={`Apri ${d.original_filename}`}
                      >
                        <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                      </a>{" "}
                      <button
                        type="button"
                        onClick={() => onDelete(d)}
                        className="pd-icon-btn"
                        title={`Elimina ${d.original_filename}`}
                        aria-label={`Elimina ${d.original_filename}`}
                        style={{ color: "var(--pd-danger)" }}
                      >
                        <span className="material-symbols-outlined" aria-hidden="true">delete</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
              {docs.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 28, color: "var(--pd-text-muted)" }}>
                    Nessun documento caricato nel fascicolo. Utilizza il riquadro sopra per acquisire i PDF.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function QualityBar({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const color = pct >= 85 ? "var(--pd-ok)" : pct >= 70 ? "var(--pd-warn)" : "var(--pd-danger)";
  return (
    <div className="pd-progress" style={{ height: 6 }}>
      <span style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function confidence(doc) {
  const n = doc.classification_confidence == null ? null : Math.round(Number(doc.classification_confidence) * 100);
  if (n == null || Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

function statusBadge(s) {
  const v = {
    caricato: "neutral",
    in_elaborazione: "warn",
    elaborato: "ok",
    normalizzato: "ok",
    errore: "danger",
  }[s] || "neutral";
  return <span className={`pd-badge pd-badge--${v}`}>{String(s || "caricato").replace(/_/g, " ")}</span>;
}
