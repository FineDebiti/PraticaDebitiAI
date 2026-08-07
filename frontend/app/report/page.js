"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { listCases, getCard, getIndicators } from "../api";

function ReportContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseIdParam = searchParams.get("caseId");

  const [cases, setCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdParam || "");
  const [card, setCard] = useState(null);
  const [indicators, setIndicators] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const list = await listCases();
        if (Array.isArray(list) && list.length > 0) {
          setCases(list);
          if (!selectedCaseId) {
            setSelectedCaseId(list[0].id);
          }
        }
      } catch (err) {
        console.error(err);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    async function loadReportData() {
      setLoading(true);
      try {
        const [cData, ind] = await Promise.all([
          getCard(selectedCaseId).catch(() => null),
          getIndicators(selectedCaseId).catch(() => null),
        ]);
        setCard(cData);
        setIndicators(ind);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadReportData();
  }, [selectedCaseId]);

  function handleCaseChange(e) {
    const id = e.target.value;
    setSelectedCaseId(id);
    router.push(`/report?caseId=${id}`);
  }

  const selectedCase = cases.find((c) => c.id === selectedCaseId);
  const debtorName = selectedCase?.client_name || "Nessuna pratica selezionata";
  const reportCode = selectedCase?.code ? `#DAP-${selectedCase.code}` : "N/D";
  const totalDebtVal = card?.debtor?.total_debt || indicators?.total_debt || 0;
  const riskScore = indicators?.risk_score ?? 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1000, margin: "0 auto" }}>
      {/* Top Action Header */}
      <div className="pd-page-head no-print">
        <div>
          <h1 className="pd-h1">Scheda Analisi Finale</h1>
          <p>Revisione e generazione del dossier sintetico istituzionale per export ed uso legale.</p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            className="pd-select"
            value={selectedCaseId}
            onChange={handleCaseChange}
            style={{ width: 240 }}
          >
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.client_name}
              </option>
            ))}
            {cases.length === 0 && <option value="">Nessuna pratica trovata</option>}
          </select>

          <button
            className="pd-btn pd-btn--secondary"
            onClick={() => router.push(`/dati-economici?caseId=${selectedCaseId}`)}
            disabled={!selectedCaseId}
          >
            <span className="material-symbols-outlined">edit</span>
            Modifica Dati
          </button>
          <button
            className="pd-btn pd-btn--primary"
            onClick={() => window.print()}
            disabled={!selectedCaseId}
          >
            <span className="material-symbols-outlined">picture_as_pdf</span>
            Esporta Scheda (PDF)
          </button>
        </div>
      </div>

      {/* DOCUMENT PREVIEW CONTAINER (Screen 4 Stitch) */}
      <div className="pd-report-paper">
        {/* Document Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 40 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  background: "var(--pd-primary)",
                  color: "#fff",
                  borderRadius: "var(--pd-radius)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span className="material-symbols-outlined">account_balance</span>
              </div>
              <span style={{ fontSize: 22, fontWeight: 700, color: "var(--pd-primary)", letterSpacing: "-0.02em" }}>
                DossierLex Istituzionale
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
              Piattaforma Istituzionale Pre-Analisi<br />
              Dossier Tecnico Legale ed Econometrico
            </p>
          </div>

          <div style={{ textAlign: "right" }}>
            <span
              className="pd-badge pd-badge--neutral"
              style={{ fontSize: 11, letterSpacing: ".04em", marginBottom: 6 }}
            >
              RISERVATO & CONFIDENZIALE
            </span>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--pd-text-muted)" }}>
              ID Report: {reportCode}
            </p>
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--pd-text-muted)" }}>
              Data: {new Date().toLocaleDateString("it-IT", { day: "2-digit", month: "long", year: "numeric" })}
            </p>
          </div>
        </div>

        {/* Document Title */}
        <div style={{ marginBottom: 32, borderBottom: "1px solid var(--pd-border)", paddingBottom: 16 }}>
          <h1 className="pd-h1" style={{ fontSize: 26, lineHeight: 1.3 }}>
            Dossier Analitico: Valutazione Strutturata della Posizione Debitoria
          </h1>
        </div>

        {/* CLIENT SUMMARY SECTION */}
        <section style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
              person
            </span>
            <h3 className="pd-h3" style={{ fontSize: 18 }}>
              Profilo Cliente & Riepilogo Posizione
            </h3>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 20,
              padding: 20,
              background: "var(--pd-surface-low)",
              border: "1px solid var(--pd-border)",
              borderRadius: "var(--pd-radius)",
            }}
          >
            <div>
              <span className="pd-kpi__label">Denominazione / Nome</span>
              <p style={{ margin: "4px 0 0", fontSize: 16, fontWeight: 700, color: "var(--pd-text)" }}>
                {debtorName}
              </p>
            </div>
            <div>
              <span className="pd-kpi__label">Esposizione Debitoria Complessiva</span>
              <p style={{ margin: "4px 0 0", fontSize: 16, fontWeight: 700, color: "var(--pd-text)" }}>
                € {(Number(totalDebtVal) || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div>
              <span className="pd-kpi__label">Codice Pratica</span>
              <p style={{ margin: "4px 0 0", fontSize: 15, color: "var(--pd-text)" }}>
                #{selectedCase?.code || "N/D"}
              </p>
            </div>
            <div>
              <span className="pd-kpi__label">Classe di Rischio Istituzionale</span>
              <span className={`pd-badge pd-badge--${riskScore > 70 ? "danger" : riskScore > 30 ? "warn" : riskScore > 0 ? "ok" : "neutral"}`} style={{ marginTop: 4 }}>
                {riskScore > 70 ? "RISCHIO ELEVATO" : riskScore > 30 ? "RISCHIO MODERATO" : riskScore > 0 ? "RISCHIO CONTENUTO" : "IN ATTESA DATI"}
              </span>
            </div>
          </div>
        </section>

        {/* ECONOMETRIC FINDINGS SECTION */}
        <section style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
              insights
            </span>
            <h3 className="pd-h3" style={{ fontSize: 18 }}>
              Risultanze dell'Analisi Econometrica
            </h3>
          </div>

          <p style={{ fontSize: 14, color: "var(--pd-text-muted)", lineHeight: 1.6, marginBottom: 16 }}>
            Valutazione ed elaborazione effettuata sui documenti e dati caricati per la pratica selezionata.
          </p>

          <div className="pd-table-wrap">
            <table className="pd-table">
              <thead>
                <tr>
                  <th>Indicatore Analizzato</th>
                  <th>Valore Calcolato</th>
                  <th>Soglia Riferimento</th>
                  <th className="pd-num">Stato</th>
                </tr>
              </thead>
              <tbody>
                {indicators?.indicators && indicators.indicators.length > 0 ? (
                  indicators.indicators.map((ind, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 700 }}>{ind.label}</td>
                      <td>{ind.value != null ? ind.value : "n.d."}</td>
                      <td>{ind.criterion || "Soglia standard"}</td>
                      <td className="pd-num">
                        <span className={`pd-badge pd-badge--${ind.status === "danger" ? "danger" : ind.status === "warn" ? "warn" : "ok"}`}>
                          {ind.status || "ok"}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", color: "var(--pd-text-muted)", padding: 18 }}>
                      Nessun indicatore calcolato. Caricare documenti nella sezione "Dati Economici".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* SUGGESTED CONSULTANCY ACTIONS SECTION */}
        <section style={{ marginBottom: 40 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
              strategy
            </span>
            <h3 className="pd-h3" style={{ fontSize: 18 }}>
              Azioni Consulenziali e Strategiche Consigliate
            </h3>
          </div>

          <div className="pd-grid pd-grid--2">
            <div style={{ padding: 20, background: "#fff", border: "1px solid var(--pd-border)", borderRadius: "var(--pd-radius)", display: "flex", gap: 16 }}>
              <div style={{ width: 44, height: 44, background: "var(--pd-accent-soft)", borderRadius: "var(--pd-radius)", display: "flex", alignItems: "center", justifyContent: "center", shrink: 0 }}>
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent-strong)" }}>balance</span>
              </div>
              <div>
                <strong style={{ fontSize: 15, color: "var(--pd-primary)", display: "block", marginBottom: 4 }}>
                  Verifica Documentale Integrativa
                </strong>
                <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
                  Completare la raccolta di estratti di ruolo e contratti per raffinare il calcolo di sostenibilità.
                </p>
              </div>
            </div>

            <div style={{ padding: 20, background: "var(--pd-primary)", color: "#fff", borderRadius: "var(--pd-radius)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <span className="material-symbols-outlined" style={{ fontSize: 28, marginBottom: 8 }}>gavel</span>
              <div>
                <strong style={{ fontSize: 15, display: "block" }}>Stato Istruttoria</strong>
                <p style={{ margin: "4px 0 0", fontSize: 13, opacity: 0.9 }}>
                  {selectedCase ? `Pratica in corso per ${selectedCase.client_name}` : "Nessuna pratica attiva"}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* SIGNATURES & SEALS */}
        <div style={{ marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--pd-border)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ height: 48, display: "flex", alignItems: "center", justifyContent: "center", fontStyle: "italic", fontSize: 18, color: "var(--pd-primary)", opacity: 0.6 }}>
              Operatore Incaricato
            </div>
            <div style={{ height: 1, background: "var(--pd-border)", marginBottom: 8 }}></div>
            <span className="pd-kpi__label">Firma Operatore Tecnico</span>
          </div>

          <div style={{ textAlign: "center" }}>
            <div style={{ height: 48, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ padding: "4px 12px", border: "2px solid var(--pd-primary)", borderRadius: 4, fontSize: 11, fontWeight: 700, color: "var(--pd-primary)", letterSpacing: ".05em" }}>
                SIGILLO DOSSIERLEX VALIDATED
              </div>
            </div>
            <div style={{ height: 1, background: "var(--pd-border)", marginBottom: 8 }}></div>
            <span className="pd-kpi__label">Validazione Istituzionale</span>
          </div>
        </div>
      </div>

      {/* ATTACHED EVIDENCE / METADATA TILES (Screen 4 Stitch) */}
      <div className="pd-grid pd-grid--3 no-print">
        <div className="pd-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 28, color: "var(--pd-accent)" }}>table_chart</span>
          <div>
            <strong style={{ fontSize: 13, display: "block", color: "var(--pd-primary)" }}>Export Dati Grezzi</strong>
            <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>XLSX • 4.2 MB</span>
          </div>
        </div>

        <div className="pd-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 28, color: "var(--pd-accent)" }}>folder_zip</span>
          <div>
            <strong style={{ fontSize: 13, display: "block", color: "var(--pd-primary)" }}>Pacchetto Prove Prodotte</strong>
            <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>ZIP • 128 MB</span>
          </div>
        </div>

        <div className="pd-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 28, color: "var(--pd-accent)" }}>verified_user</span>
          <div>
            <strong style={{ fontSize: 13, display: "block", color: "var(--pd-primary)" }}>Certificato Digitale</strong>
            <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>SHA-256 Validato</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="pd-card">Caricamento Report...</div>}>
      <ReportContent />
    </Suspense>
  );
}
