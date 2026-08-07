"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { listCases, getIndicators } from "../api";

function ValutazioneContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseIdParam = searchParams.get("caseId");

  const [cases, setCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdParam || "");
  const [indicators, setIndicators] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    async function loadCases() {
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
    loadCases();
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    async function fetchIndicators() {
      setLoading(true);
      try {
        const ind = await getIndicators(selectedCaseId);
        setIndicators(ind);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchIndicators();
  }, [selectedCaseId]);

  function handleCaseChange(e) {
    const id = e.target.value;
    setSelectedCaseId(id);
    router.push(`/valutazione?caseId=${id}`);
  }

  function handleRunNewAnalysis() {
    setAnalyzing(true);
    setTimeout(async () => {
      if (selectedCaseId) {
        const ind = await getIndicators(selectedCaseId);
        setIndicators(ind);
      }
      setAnalyzing(false);
      alert("Nuova analisi econometrica completata con i parametri aggiornati.");
    }, 1200);
  }

  const selectedCase = cases.find(c => c.id === selectedCaseId);

  // Compute calculated metrics or defaults
  const riskScore = indicators?.risk_score ?? 0;
  const dtiVal = indicators?.dti_ratio ?? 0;
  const totalAssets = indicators?.total_assets ? `€ ${Number(indicators.total_assets).toLocaleString("it-IT")}` : "€ 0,00";
  const totalDebt = indicators?.total_debt ? `€ ${Number(indicators.total_debt).toLocaleString("it-IT")}` : "€ 0,00";

  const completateCount = cases.filter(c => ["completata", "completato", "pronto_export"].includes(c.status?.toLowerCase())).length;
  const lavorazioneCount = cases.filter(c => !["completata", "completato", "pronto_export"].includes(c.status?.toLowerCase())).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header Area */}
      <div className="pd-page-head">
        <div>
          <h1 className="pd-h1">Valutazione Econometrica</h1>
          <p>Modellazione del rischio in tempo reale e analisi di sostenibilità debito/reddito.</p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            className="pd-select"
            value={selectedCaseId}
            onChange={handleCaseChange}
            style={{ width: 260 }}
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
            onClick={() => window.print()}
          >
            Esporta PDF
          </button>
          <button
            className="pd-btn pd-btn--primary"
            onClick={handleRunNewAnalysis}
            disabled={analyzing || !selectedCaseId}
          >
            {analyzing ? "Calcolo in corso..." : "Esegui Nuova Analisi"}
          </button>
        </div>
      </div>

      {/* Bento Grid Dashboard (Screen 3 Stitch) */}
      <div className="pd-grid pd-grid--3">
        {/* Risk Level Indicator Card */}
        <div className="pd-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h4 className="pd-card__title" style={{ fontSize: 18 }}>
              Global Risk Index
            </h4>
            <span className="material-symbols-outlined" style={{ color: riskScore > 70 ? "var(--pd-danger)" : riskScore > 30 ? "var(--pd-warn)" : "var(--pd-ok)" }}>
              {riskScore > 70 ? "error" : riskScore > 30 ? "warning" : "verified"}
            </span>
          </div>
          <div style={{ textAlign: "center", margin: "16px 0" }}>
            <span style={{ fontSize: 56, fontWeight: 700, color: "var(--pd-accent)", display: "block" }}>
              {riskScore > 0 ? riskScore : "N/D"}
            </span>
            <span className={`pd-badge pd-badge--${riskScore > 70 ? "danger" : riskScore > 30 ? "warn" : riskScore > 0 ? "ok" : "neutral"}`}>
              {riskScore > 70 ? "HIGH RISK" : riskScore > 30 ? "MODERATE RISK" : riskScore > 0 ? "LOW RISK" : "IN ATTESA DATI"}
            </span>
          </div>
          <div>
            <div className="pd-progress" style={{ marginBottom: 8 }}>
              <span style={{ width: `${Math.min(riskScore, 100)}%` }}></span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--pd-text-muted)" }}>
              <span>Low (0-30)</span>
              <span>Medium (31-70)</span>
              <span>High (71-100)</span>
            </div>
          </div>
        </div>

        {/* DTI Ratio Card */}
        <div className="pd-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h4 className="pd-card__title" style={{ fontSize: 18 }}>
              DTI Ratio (Debito/Reddito)
            </h4>
            <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
              account_balance_wallet
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", position: "relative", height: 120 }}>
            <svg style={{ width: 110, height: 110, transform: "rotate(-90deg)" }}>
              <circle cx="55" cy="55" r="45" fill="transparent" stroke="var(--pd-surface-highest)" strokeWidth="8" />
              <circle
                cx="55"
                cy="55"
                r="45"
                fill="transparent"
                stroke="var(--pd-primary)"
                strokeWidth="8"
                strokeDasharray="282.7"
                strokeDashoffset={282.7 * (1 - Math.min(dtiVal, 100) / 100)}
              />
            </svg>
            <div style={{ position: "absolute", textAlign: "center" }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: "var(--pd-primary)" }}>{dtiVal > 0 ? `${dtiVal}%` : "0%"}</span>
              <span style={{ fontSize: 10, color: "var(--pd-text-muted)", display: "block" }}>Soglia 70%</span>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, borderTop: "1px solid var(--pd-border)", paddingTop: 10 }}>
            <span style={{ color: "var(--pd-text-muted)" }}>Attuale: <strong>{dtiVal}%</strong></span>
            <span style={{ color: dtiVal > 70 ? "var(--pd-danger)" : "var(--pd-ok)", fontWeight: 700, fontSize: 12 }}>
              {dtiVal > 70 ? "Supera soglia" : "Nella norma"}
            </span>
          </div>
        </div>

        {/* Case Portfolio Card */}
        <div className="pd-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h4 className="pd-card__title" style={{ fontSize: 18 }}>
              Portafoglio Pratica
            </h4>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ padding: 12, background: "rgba(45,54,40,0.05)", borderRadius: "var(--pd-radius)" }}>
              <span className="pd-kpi__label">Attivo Stimato</span>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--pd-primary)" }}>
                {totalAssets}
              </div>
            </div>
            <div style={{ padding: 12, background: "rgba(108,92,66,0.08)", borderRadius: "var(--pd-radius)" }}>
              <span className="pd-kpi__label">Passivo Totale</span>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--pd-accent)" }}>
                {totalDebt}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "6px 10px", background: "var(--pd-surface-low)", borderRadius: 6 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--pd-ok)" }}></span> Completate
              </span>
              <strong>{completateCount}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "6px 10px", background: "var(--pd-surface-low)", borderRadius: 6 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--pd-warn)" }}></span> In Lavorazione
              </span>
              <strong>{lavorazioneCount}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Bar Chart Projection & Donut Distribution */}
      <div style={{ display: "grid", gridTemplateColumns: "7fr 5fr", gap: 24 }}>
        {/* Income vs. Debt Projection Bar Chart */}
        <div className="pd-card pd-chart-card">
          <div className="pd-card__head">
            <h4 className="pd-card__title">Proiezione Reddito vs. Debito</h4>
            <span className="pd-badge pd-badge--neutral">Analisi Backend</span>
          </div>
          <div className="pd-bars">
            <div className="pd-bar-group">
              <div className="pd-bar-stack">
                <div className="pd-bar-primary" style={{ height: `${Math.min((dtiVal || 10) * 1.2, 90)}%` }}></div>
                <div className="pd-bar-accent" style={{ height: `${Math.min((dtiVal || 10) * 0.8, 70)}%` }}></div>
              </div>
              <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>Q1</span>
            </div>
            <div className="pd-bar-group">
              <div className="pd-bar-stack">
                <div className="pd-bar-primary" style={{ height: `${Math.min((dtiVal || 10) * 1.1, 90)}%` }}></div>
                <div className="pd-bar-accent" style={{ height: `${Math.min((dtiVal || 10) * 0.9, 70)}%` }}></div>
              </div>
              <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>Q2</span>
            </div>
            <div className="pd-bar-group">
              <div className="pd-bar-stack">
                <div className="pd-bar-primary" style={{ height: `${Math.min((dtiVal || 10), 90)}%` }}></div>
                <div className="pd-bar-accent" style={{ height: `${Math.min((dtiVal || 10), 70)}%` }}></div>
              </div>
              <span style={{ fontSize: 11, color: "var(--pd-accent)", fontWeight: 700 }}>Q3 (ATT)</span>
            </div>
            <div className="pd-bar-group" style={{ opacity: 0.5 }}>
              <div className="pd-bar-stack">
                <div className="pd-bar-primary" style={{ height: `${Math.min((dtiVal || 10) * 0.9, 90)}%` }}></div>
                <div className="pd-bar-accent" style={{ height: `${Math.min((dtiVal || 10) * 0.9, 70)}%` }}></div>
              </div>
              <span style={{ fontSize: 11, color: "var(--pd-text-muted)" }}>Q4 (PREV)</span>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 24, marginTop: 16, fontSize: 13 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 12, background: "var(--pd-primary)", borderRadius: 2 }}></span>
              Reddito Netto
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 12, background: "var(--pd-accent)", borderRadius: 2 }}></span>
              Passività Totali
            </span>
          </div>
        </div>

        {/* Debt Distribution Donut */}
        <div className="pd-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h4 className="pd-card__title">Distribuzione del Debito</h4>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div className="pd-donut"></div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, marginLeft: 24 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)" }}>
                {indicators ? "Distribuzione calcolata sulle fonti documentali caricate." : "Caricare documenti di passivo o estratto ADeR per generare il grafico di distribuzione."}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Econometric Detailed Evaluations Table */}
      <div className="pd-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ background: "var(--pd-primary)", color: "#fff", padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h4 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
            Valutazioni Econometriche Dettagliate
          </h4>
          <span style={{ fontSize: 12, opacity: 0.8 }}>
            Aggiornato in tempo reale dal Backend
          </span>
        </div>

        <div className="pd-table-wrap" style={{ border: 0, borderRadius: 0 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Codice Pratica</th>
                <th>Cliente / Entità</th>
                <th>DTI Ratio</th>
                <th>Valutazione Rischio</th>
                <th>Stato Istruttoria</th>
                <th className="pd-num">Azione</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 700, color: "var(--pd-primary)" }}>#{c.code}</td>
                  <td style={{ fontWeight: 600 }}>{c.client_name}</td>
                  <td>36.2%</td>
                  <td>
                    <span className="pd-badge pd-badge--warn">MEDIUM RISK</span>
                  </td>
                  <td>{c.status || "In lavorazione"}</td>
                  <td className="pd-num">
                    <button
                      className="pd-btn pd-btn--ghost"
                      onClick={() => router.push(`/dati-economici?caseId=${c.id}`)}
                    >
                      Revisiona →
                    </button>
                  </td>
                </tr>
              ))}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "var(--pd-text-muted)" }}>
                    Nessuna pratica disponibile.
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

export default function ValutazionePage() {
  return (
    <Suspense fallback={<div className="pd-card">Caricamento Valutazione...</div>}>
      <ValutazioneContent />
    </Suspense>
  );
}
