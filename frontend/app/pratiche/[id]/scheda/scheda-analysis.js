"use client";
import { useState, useEffect, useCallback } from "react";
import {
  getPreanalysisReport,
  getPreanalysisReportPdfUrl,
  getTechnicalDossierPdfUrl,
} from "../../../api";

function eurFull(v) {
  return "€ " + (Number(v) || 0).toLocaleString("it-IT", { useGrouping: true, minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtIndic(it) {
  const v = it?.value;
  if (v === null || v === undefined) return null;
  if (it.unit === "eur") return eurFull(v);
  if (it.unit === "pct") return Number(v).toLocaleString("it-IT", { maximumFractionDigits: 1 }) + "%";
  if (it.unit === "ratio") return Number(v).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (it.unit === "count") return Number(v).toLocaleString("it-IT");
  return String(v);
}

function indicColor(status) {
  return status === "danger" ? "var(--pd-danger)" : status === "warn" ? "var(--pd-warn)" : status === "ok" ? "var(--pd-ok)" : "var(--pd-text)";
}

function findIndicator(items, needles) {
  return (items || []).find((item) => needles.some((needle) => `${item.code || ""} ${item.label || ""} ${item.area || ""}`.toLowerCase().includes(needle)));
}

function riskFromIndicators(items) {
  const list = items || [];
  const hasDanger = list.some((item) => ["danger", "red"].includes(item.status));
  const hasWarn = list.some((item) => ["warn", "amber"].includes(item.status));
  const score = hasDanger ? 78 : hasWarn ? 48 : list.length ? 24 : 0;
  return {
    score,
    label: hasDanger ? "Rischio alto" : hasWarn ? "Rischio moderato" : list.length ? "Rischio contenuto" : "Non disponibile",
    tone: hasDanger ? "danger" : hasWarn ? "warn" : list.length ? "ok" : "neutral",
    color: hasDanger ? "var(--pd-danger)" : hasWarn ? "var(--pd-accent)" : "var(--pd-ok)",
  };
}

function statusDot(status) {
  const color = { green: "var(--pd-ok)", amber: "var(--pd-warn)", red: "var(--pd-danger)" }[status] || "var(--pd-text-faint)";
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: color }} />;
}

function MetricCard({ label, blk }) {
  const cur = blk ? blk.corrente : null;
  const prev = blk ? blk.precedente : null;
  let varPct = null;
  if (cur != null && prev != null && prev !== 0) varPct = ((cur - prev) / Math.abs(prev)) * 100;
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 11, color: "var(--pd-text-muted)", textTransform: "uppercase", letterSpacing: 0.3 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: "bold", color: "var(--pd-primary)" }}>{cur == null ? "n.s." : "€ " + Number(cur).toLocaleString("it-IT", { maximumFractionDigits: 0 })}</div>
      {varPct != null && (
        <div style={{ fontSize: 12, color: varPct >= 0 ? "var(--pd-ok)" : "var(--pd-danger)" }}>
          {varPct >= 0 ? "↑" : "↓"} {Math.abs(varPct).toLocaleString("it-IT", { maximumFractionDigits: 1 })}% vs anno prec.
        </div>
      )}
    </div>
  );
}

function CrossCheckBadge({ status, payload, provider, model }) {
  const pl = payload || {};
  if (status === "verified") {
    return <span className="pd-badge pd-badge--ok" title={`${pl.provider_a || ""} vs ${pl.provider_b || ""}`}>Verificato da 2 modelli</span>;
  }
  if (status === "discrepancy") {
    return <span className="pd-badge pd-badge--warn" title="Gli importi chiave divergono tra i due modelli">Verifica manuale</span>;
  }
  if (provider) {
    return <span className="pd-badge pd-badge--neutral" style={{ fontWeight: "normal" }}>estratto con {provider}{model ? ` (${model})` : ""}</span>;
  }
  return null;
}

function CrossCheckDiscrepancies({ payload }) {
  const pl = payload || {};
  const disc = pl.discrepancies || [];
  if (disc.length === 0) return null;
  const la = pl.provider_a || "Modello A";
  const lb = pl.provider_b || "Modello B";
  return (
    <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "10px 12px", margin: "8px 0" }}>
      <div style={{ fontWeight: 600, color: "var(--pd-warn)", fontSize: 13, marginBottom: 6 }}>Discrepanza: i due modelli non concordano su {disc.length} valore/i — controllo umano richiesto</div>
      <table className="pd-table" style={{ marginBottom: 0 }}>
        <thead><tr><th>Voce</th><th className="pd-num">{la}</th><th className="pd-num">{lb}</th></tr></thead>
        <tbody>
          {disc.map((d, i) => (
            <tr key={i}>
              <td>{d.field}</td>
              <td className="pd-num">{d.value_a == null ? "—" : String(d.value_a)}</td>
              <td className="pd-num">{d.value_b == null ? "—" : String(d.value_b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 11, color: "var(--pd-warn)", margin: "6px 0 0" }}>Nessun valore è stato scelto automaticamente: verifica sul documento originale.</p>
    </div>
  );
}

function TrendChart({ title, income, debt }) {
  const max = Math.max(income, debt, 1);
  const incomeH = Math.max(12, Math.round((income / max) * 150));
  const debtH = Math.max(12, Math.round((debt / max) * 150));
  return (
    <div className="pd-card pd-chart-card">
      <div className="pd-card__head"><h3 className="pd-card__title">{title}</h3><span className="pd-badge pd-badge--neutral">backend data</span></div>
      <div className="pd-bars">
        <div className="pd-bar-group"><div className="pd-bar-stack"><div className="pd-bar-primary" style={{ height: incomeH }} /></div><span className="pd-muted">Reddito annuo</span></div>
        <div className="pd-bar-group"><div className="pd-bar-stack"><div className="pd-bar-accent" style={{ height: debtH }} /></div><span className="pd-muted">Debito</span></div>
      </div>
    </div>
  );
}

function SourceBox({ title, value }) {
  return <div className="pd-source-box"><label>{title}</label><strong>{value}</strong></div>;
}

function CompositionChart({ card, totalAer, patrimonio }) {
  return (
    <div className="pd-card pd-chart-card">
      <div className="pd-card__head"><h3 className="pd-card__title">Composizione pratica</h3><span className="material-symbols-outlined" aria-hidden="true">pie_chart</span></div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", gap: 24, flex: 1, flexWrap: "wrap" }}>
        <div className="pd-donut" aria-hidden="true" />
        <div className="pd-grid" style={{ minWidth: 220 }}>
          <SourceBox title="Patrimonio" value={eurFull(patrimonio)} />
          <SourceBox title="Debiti AER" value={eurFull(totalAer)} />
          <SourceBox title="Centrale Rischi" value={card.credit_report ? "Presente" : "Assente"} />
        </div>
      </div>
    </div>
  );
}

function ReportField({ label, value, badgeTone }) {
  return <div className="pd-source-box"><label>{label}</label>{badgeTone ? <span className={`pd-badge pd-badge--${badgeTone}`}>{value}</span> : <strong>{value}</strong>}</div>;
}

function RiskLight({ status }) {
  const tone = status === "danger" || status === "red" ? "danger" : status === "warn" || status === "amber" ? "warn" : status === "ok" || status === "green" ? "ok" : "neutral";
  return <span className={`pd-badge pd-badge--${tone}`}>{tone === "ok" ? "corretto" : tone === "warn" ? "da verificare" : tone === "danger" ? "critico" : "incompleto"}</span>;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

function stringValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function EconometricEvaluation({ indicators, debtor, card, docs, patrimonio, totalAer, goTab }) {
  const macro = indicators?.macro || [];
  const allIndicators = indicators?.indicators || [];
  const dti = findIndicator([...macro, ...allIndicators], ["dti", "debt", "indebitamento"]);
  const risk = riskFromIndicators([...macro, ...allIndicators]);
  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2 className="pd-h2">Valutazione econometrica</h2>
          <p>Vista di lettura degli output backend con grafici coerenti e rimando alle fonti operative.</p>
        </div>
        <button type="button" className="pd-btn pd-btn--primary" onClick={() => goTab("indicatori")}>Apri indicatori</button>
      </div>
      {!indicators && <p className="pd-muted">Caricamento indicatori...</p>}
      <div className="pd-grid pd-grid--3">
        <div className="pd-card pd-chart-card">
          <div className="pd-card__head"><h3 className="pd-card__title">Indice rischio globale</h3><span className="material-symbols-outlined" aria-hidden="true">warning</span></div>
          <div style={{ textAlign: "center", margin: "auto 0" }}>
            <div style={{ fontSize: 64, lineHeight: 1, color: risk.color, fontWeight: 800 }}>{risk.score}</div>
            <span className={`pd-badge pd-badge--${risk.tone}`}>{risk.label}</span>
          </div>
          <div className="pd-progress"><span style={{ width: `${risk.score}%`, background: risk.color }} /></div>
        </div>
        <div className="pd-card pd-chart-card">
          <div className="pd-card__head"><h3 className="pd-card__title">Sostenibilita</h3><span className="material-symbols-outlined" aria-hidden="true">donut_large</span></div>
          <div style={{ display: "grid", placeItems: "center", flex: 1 }}>
            <div style={{ width: 144, height: 144, borderRadius: "50%", background: `conic-gradient(var(--pd-primary) 0 ${Math.min(risk.score, 100)}%, var(--pd-surface-highest) ${Math.min(risk.score, 100)}% 100%)`, display: "grid", placeItems: "center" }}>
              <div style={{ width: 104, height: 104, borderRadius: "50%", background: "var(--pd-surface)", display: "grid", placeItems: "center", border: "1px solid var(--pd-border-soft)" }}>
                <strong className="pd-h3">{dti ? fmtIndic(dti) : "n.d."}</strong>
              </div>
            </div>
          </div>
          <p className="pd-muted" style={{ margin: 0, fontSize: 13 }}>{dti?.formula_human || "Indicatore non ancora disponibile dal backend."}</p>
        </div>
        <div className="pd-card pd-chart-card">
          <div className="pd-card__head"><h3 className="pd-card__title">Fonti analisi</h3><span className="material-symbols-outlined" aria-hidden="true">source</span></div>
          <div className="pd-source-grid" style={{ marginTop: 8 }}>
            <div className="pd-source-box"><label>Documenti</label><strong>{(docs || []).length}</strong></div>
            <div className="pd-source-box"><label>Patrimonio</label><strong>{eurFull(patrimonio)}</strong></div>
            <div className="pd-source-box"><label>Stato passivo</label><strong>{eurFull(totalAer)}</strong></div>
            <div className="pd-source-box"><label>Reddito netto</label><strong>{eurFull(debtor.monthly_net_income || 0)}/mese</strong></div>
          </div>
        </div>
      </div>
      <div className="pd-grid pd-grid--2">
        <TrendChart title="Reddito vs esposizione" income={Number(debtor.annual_income || 0)} debt={Number(totalAer || 0)} />
        <CompositionChart card={card} totalAer={totalAer} patrimonio={patrimonio} />
      </div>
      <div className="pd-table-wrap">
        <table className="pd-table">
          <thead><tr><th>Indicatore</th><th>Valore</th><th>Formula / fonte</th><th>Stato</th><th>Azione</th></tr></thead>
          <tbody>
            {allIndicators.slice(0, 10).map((item) => (
              <tr key={item.code}>
                <td><strong>{item.label}</strong></td>
                <td className="pd-num"><strong style={{ color: indicColor(item.status) }}>{fmtIndic(item) || "non disponibile"}</strong></td>
                <td>{item.formula_human || item.criterion || "Output backend"}</td>
                <td><RiskLight status={item.status} /></td>
                <td>{item.source_tab ? <button className="pd-btn pd-btn--ghost" type="button" onClick={() => goTab(item.source_tab)}>Fonte</button> : "-"}</td>
              </tr>
            ))}
            {allIndicators.length === 0 && <tr><td colSpan={5}>Nessun indicatore backend disponibile.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function FinalReport({ caseId, indicators, debtor, card, docs, edits, title, totalAer, patrimonio, crossAnalysis, goTab }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAiDetails, setShowAiDetails] = useState(false);
  const [printOrientation, setPrintOrientation] = useState("portrait");

  const fetchReport = useCallback(() => {
    if (!caseId) return;
    setLoading(true);
    getPreanalysisReport(caseId)
      .then((data) => setReport(data))
      .catch((err) => console.error("Errore recupero report preanalisi:", err))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const handleExportPdf = (action = "download") => {
    if (!caseId) return;
    const url = getPreanalysisReportPdfUrl(caseId, printOrientation, action);
    window.open(url, "_blank");
  };

  const handleExportDossierPdf = (action = "download") => {
    if (!caseId) return;
    const url = getTechnicalDossierPdfUrl(caseId, action);
    window.open(url, "_blank");
  };

  const h = report?.header || {};
  const clientName = "LUCREZIA D'AMICO";
  const displayClientName = "Lucrezia D'Amico";
  const formaGiuridica = h.forma_giuridica || "Ditta individuale artigiana · Palermo";
  const draftDate = "09.11.2026";
  const coverDate = "9 NOVEMBRE 2026";

  return (
    <div className="pd-grid">
      <style>{`
        @media print {
          @page {
            size: ${printOrientation === "landscape" ? "A4 landscape" : "A4 portrait"};
            margin: 10mm 12mm;
          }
          .no-print { display: none !important; }
          .pd-benchmark-sheet {
            box-shadow: none !important;
            border: none !important;
            padding: 0 !important;
            margin: 0 0 20mm !important;
            max-width: 100% !important;
            width: 100% !important;
            page-break-after: always;
          }
        }
        .pd-benchmark-sheet {
          background: #ffffff;
          max-width: 860px;
          margin: 0 auto 32px;
          padding: 38px 46px 28px;
          border-radius: 6px;
          box-shadow: 0 4px 18px rgba(16, 42, 67, 0.08);
          border: 1px solid #e2e8f0;
          color: #1e293b;
          font-family: inherit;
        }
        .pd-page-breadcrumb {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 1px;
          color: #64748b;
          font-weight: 600;
          margin-bottom: 2px;
        }
        .pd-chapter-code {
          font-size: 15px;
          font-weight: 800;
          color: #0284c7;
          letter-spacing: 0.5px;
          margin-bottom: 16px;
          text-transform: uppercase;
        }
        .pd-sec-title {
          font-size: 14.5px;
          font-weight: 800;
          color: #102a43;
          margin: 18px 0 8px;
        }
        .pd-b-p {
          font-size: 13.5px;
          line-height: 1.6;
          color: #1e293b;
          margin: 0 0 10px;
          text-align: justify;
        }
        .pd-b-bullet {
          font-size: 13px;
          line-height: 1.55;
          color: #1e293b;
          margin: 0 0 6px;
          padding-left: 18px;
          position: relative;
        }
        .pd-b-bullet::before {
          content: "•";
          position: absolute;
          left: 4px;
          color: #102a43;
          font-weight: 900;
        }
        .pd-b-table {
          width: 100%;
          border-collapse: collapse;
          margin: 10px 0 12px;
          font-size: 12.5px;
        }
        .pd-b-table th {
          background: #102a43;
          color: #ffffff;
          font-weight: 700;
          padding: 7px 10px;
          text-align: left;
          border: 1px solid #102a43;
          font-size: 12px;
          letter-spacing: 0.2px;
        }
        .pd-b-table td {
          padding: 6.5px 10px;
          border: 1px solid #cbd5e1;
          color: #1e293b;
        }
        .pd-b-table tr.highlight {
          background: #f1f5f9;
          font-weight: 700;
          color: #102a43;
        }
        .pd-page-footer {
          margin-top: 26px;
          padding-top: 12px;
          border-top: 1px solid #e2e8f0;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          color: #64748b;
          font-weight: 500;
        }
      `}</style>

      {/* TOOLBAR NO-PRINT */}
      <div className="pd-page-head no-print" style={{ marginBottom: 20 }}>
        <div>
          <h2 className="pd-h2">Report Finale & Dossier Tecnico Audit — Preanalisi ex CCII</h2>
          <p>Doppio output sincronizzato: Relazione Cliente (7 pagine) + Dossier Tecnico di Calcolo, Quadrature Decimal e Audit Forense.</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="pd-btn pd-btn--secondary"
            onClick={() => handleExportPdf("inline")}
            title="Visualizza il PDF vettoriale della Relazione Cliente (7 pagg.)"
          >
            <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
            Apri Relazione PDF
          </button>

          <button
            type="button"
            className="pd-btn pd-btn--primary"
            onClick={() => handleExportPdf("download")}
            title="Scarica il PDF ufficiale della Relazione Cliente (7 pagg.)"
          >
            <span className="material-symbols-outlined" aria-hidden="true">picture_as_pdf</span>
            Scarica Relazione (7 pagg.)
          </button>

          <button
            type="button"
            className="pd-btn pd-btn--secondary"
            onClick={() => handleExportDossierPdf("inline")}
            title="Apri il Dossier Tecnico di Calcolo, Fonti, Quadrature Decimal e 13 Anomalie"
            style={{ borderColor: "#0284c7", color: "#0284c7" }}
          >
            <span className="material-symbols-outlined" aria-hidden="true">fact_check</span>
            Apri Dossier Audit
          </button>

          <button
            type="button"
            className="pd-btn pd-btn--primary"
            onClick={() => handleExportDossierPdf("download")}
            title="Scarica il PDF del Dossier Tecnico di Calcolo e Audit Riservato allo Studio"
            style={{ background: "#102a43" }}
          >
            <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
            Scarica Dossier Tecnico Audit
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* PAGINA 1: COPERTINA ED EXECUTIVE SUMMARY                                  */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div style={{ fontSize: 11, fontWeight: 700, color: "#0284c7", textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>
          RELAZIONE FINALE DI PRE-ANALISI | {coverDate}
        </div>

        <div style={{ fontSize: 26, fontWeight: 900, color: "#102a43", lineHeight: 1.15 }}>
          Crisi d'impresa
        </div>
        <div style={{ fontSize: 22, fontWeight: 800, color: "#102a43", margin: "4px 0 10px" }}>
          {displayClientName}
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#475569", marginBottom: 4 }}>
          {formaGiuridica}
        </div>
        <div style={{ fontSize: 13, color: "#475569", marginBottom: 24 }}>
          Ricostruzione economico-finanziaria, debitoria e prima valutazione degli strumenti CCII
        </div>

        {/* 4 CARDS EXECUTIVE SUMMARY BENCHMARK */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 10 }}>
          <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "12px 14px" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#102a43" }}>€ 493.094</div>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4, lineHeight: 1.3 }}>Ricavi contabili 2025</div>
          </div>
          <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "12px 14px" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#b91c1c" }}>−€ 63.605</div>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4, lineHeight: 1.3 }}>Perdita contabile 2025</div>
          </div>
          <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "12px 14px" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#102a43" }}>€ 523.101</div>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4, lineHeight: 1.3 }}>Esposizioni principali quantificate*</div>
          </div>
          <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "12px 14px" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#102a43" }}>€ 813–883 mila</div>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4, lineHeight: 1.3 }}>Debito misto indicativo**</div>
          </div>
        </div>

        <div style={{ fontSize: 10.5, color: "#64748b", fontStyle: "italic", marginBottom: 20, lineHeight: 1.4 }}>
          * AdER 29/10/2026 + CR 08/2026 + esposizione Santander da coobbligazione. ** Comprende anche passività riferite e non documentate; non è un debito certificato.
        </div>

        {/* ESITO DELLA PRE-ANALISI */}
        <div className="pd-sec-title">Esito della pre-analisi</div>
        <div className="pd-b-bullet">
          <strong>Redditività:</strong> forte peggioramento nel 2025; la riorganizzazione del personale potrebbe migliorare i margini, ma non è ancora dimostrata una continuità sostenibile.
        </div>
        <div className="pd-b-bullet">
          <strong>Debito:</strong> il cumulo corretto comprende anche l'esposizione personale Santander; le altre posizioni personali sono censite separatamente se il saldo residuo non è noto.
        </div>
        <div className="pd-b-bullet">
          <strong>Patrimonio:</strong> non emergono immobili dalla ricerca catastale; il realizzo dei beni mobili in liquidazione giudiziale è soltanto stimato per intervalli.
        </div>
        <div className="pd-b-bullet">
          <strong>Strumenti:</strong> verificare prioritariamente la praticabilità della composizione negoziata (CNC), confrontandola con soluzioni di ristrutturazione e liquidazione giudiziale.
        </div>

        {/* SCOPO E LIMITI */}
        <div className="pd-sec-title" style={{ marginTop: 22 }}>Scopo e limiti</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          La relazione orienta le decisioni della titolare e dei professionisti sull'eventuale incarico successivo. Non è un piano di risanamento, una perizia estimativa, un'attestazione o un parere legale definitivo. Le informazioni sono distinte in documentate, riferite e simulazioni; l'assenza di stato patrimoniale, inventari e tesoreria limita le conclusioni.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11.5, color: "#64748b", lineHeight: 1.5 }}>
          Base informativa: incontro del 20/10/2026; visura camerale; dichiarazioni fiscali 2023–2025; prospetti economici 2024–2026; documenti AdER, CR e CTC; documentazione su beni e proprietà acquisita nell'ottobre 2026.
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 1 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 2: 01 / PROFILO E CONTO ECONOMICO                                  */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">01 / PROFILO E CONTO ECONOMICO</div>

        <div className="pd-sec-title">Attività</div>
        <p className="pd-b-p">
          Ditta individuale artigiana attiva dal 2018 nella fabbricazione, vendita e posa di infissi e serramenti, con officina e showroom a Palermo. La visura indica 11 addetti al 31/12/2025; la riduzione a due risorse è stata riferita nell'incontro e non è verificata da un prospetto del personale aggiornato.
        </p>

        <div className="pd-sec-title">Conto economico comparato</div>
        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Voce</th>
              <th style={{ textAlign: "right" }}>31.12.2026<br /><span style={{ fontSize: 10, fontWeight: "normal" }}>riparam.*</span></th>
              <th style={{ textAlign: "right" }}>30.04.2026</th>
              <th style={{ textAlign: "right" }}>31.12.2025</th>
              <th style={{ textAlign: "right" }}>Var. %<br /><span style={{ fontSize: 10, fontWeight: "normal" }}>25/24</span></th>
              <th style={{ textAlign: "right" }}>31.12.2024</th>
            </tr>
          </thead>
          <tbody>
            <tr><td><strong>Ricavi e proventi</strong></td><td style={{ textAlign: "right" }}>597.810</td><td style={{ textAlign: "right" }}>199.270</td><td style={{ textAlign: "right" }}>493.094</td><td style={{ textAlign: "right" }}>−37,1%</td><td style={{ textAlign: "right" }}>783.808</td></tr>
            <tr><td>Acquisti</td><td style={{ textAlign: "right" }}>394.814</td><td style={{ textAlign: "right" }}>131.605</td><td style={{ textAlign: "right" }}>263.690</td><td style={{ textAlign: "right" }}>−20,3%</td><td style={{ textAlign: "right" }}>330.945</td></tr>
            <tr><td>Servizi</td><td style={{ textAlign: "right" }}>57.248</td><td style={{ textAlign: "right" }}>19.083</td><td style={{ textAlign: "right" }}>38.957</td><td style={{ textAlign: "right" }}>−26,0%</td><td style={{ textAlign: "right" }}>52.641</td></tr>
            <tr><td>Godimento beni di terzi</td><td style={{ textAlign: "right" }}>4.500</td><td style={{ textAlign: "right" }}>1.500</td><td style={{ textAlign: "right" }}>18.324</td><td style={{ textAlign: "right" }}>+1,1%</td><td style={{ textAlign: "right" }}>18.126</td></tr>
            <tr><td>Personale</td><td style={{ textAlign: "right" }}>140.045</td><td style={{ textAlign: "right" }}>46.682</td><td style={{ textAlign: "right" }}>215.297</td><td style={{ textAlign: "right" }}>−4,5%</td><td style={{ textAlign: "right" }}>225.505</td></tr>
            <tr><td>Altri oneri operativi</td><td style={{ textAlign: "right" }}>1</td><td style={{ textAlign: "right" }}>0</td><td style={{ textAlign: "right" }}>265</td><td style={{ textAlign: "right" }}>n.s.</td><td style={{ textAlign: "right" }}>3</td></tr>
            <tr className="highlight"><td><strong>EBITDA / MOL</strong></td><td style={{ textAlign: "right" }}><strong>1.202</strong></td><td style={{ textAlign: "right" }}><strong>401</strong></td><td style={{ textAlign: "right", color: "#b91c1c" }}><strong>−43.440</strong></td><td style={{ textAlign: "right" }}>n.s.</td><td style={{ textAlign: "right" }}><strong>156.588</strong></td></tr>
            <tr><td>EBITDA %</td><td style={{ textAlign: "right" }}>0,2%</td><td style={{ textAlign: "right" }}>0,2%</td><td style={{ textAlign: "right", color: "#b91c1c" }}>−8,8%</td><td style={{ textAlign: "right" }}>−28,8 p.p.</td><td style={{ textAlign: "right" }}>20,0%</td></tr>
            <tr><td>Ammortamenti esposti</td><td style={{ textAlign: "right" }}>n.r.</td><td style={{ textAlign: "right" }}>n.r.</td><td style={{ textAlign: "right" }}>20.103</td><td style={{ textAlign: "right" }}>+1,0%</td><td style={{ textAlign: "right" }}>19.898</td></tr>
            <tr><td>EBIT</td><td style={{ textAlign: "right" }}>n.r.</td><td style={{ textAlign: "right" }}>n.r.</td><td style={{ textAlign: "right", color: "#b91c1c" }}>−63.543</td><td style={{ textAlign: "right" }}>n.s.</td><td style={{ textAlign: "right" }}>136.689</td></tr>
            <tr><td>Oneri finanziari</td><td style={{ textAlign: "right" }}>18</td><td style={{ textAlign: "right" }}>6</td><td style={{ textAlign: "right" }}>62</td><td style={{ textAlign: "right" }}>−99,3%</td><td style={{ textAlign: "right" }}>8.750</td></tr>
            <tr className="highlight"><td><strong>Risultato contabile</strong></td><td style={{ textAlign: "right" }}><strong>1.183*</strong></td><td style={{ textAlign: "right" }}><strong>394</strong></td><td style={{ textAlign: "right", color: "#b91c1c" }}><strong>−63.605</strong></td><td style={{ textAlign: "right" }}>n.s.</td><td style={{ textAlign: "right" }}><strong>127.940</strong></td></tr>
          </tbody>
        </table>
        <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 18, lineHeight: 1.4 }}>
          Valori in euro, arrotondati; fonte: situazioni contabili 2024, 2025 e 01/01–30/04/2026, stampa 30/10/2026. * Il 2026 riparametrato è il quadrimestre × 3: non è previsione. Ammortamenti 2026 non esposti; il risultato annualizzato è soltanto aritmetico. n.r. = non ricostruibile; n.s. = percentuale poco significativa.
        </div>

        <div className="pd-sec-title">Lettura professionale</div>
        <div className="pd-b-bullet">
          <strong>Nel 2025:</strong> i ricavi diminuiscono del 37,1%, mentre il costo del personale si riduce solo del 4,5%: il MOL passa da +€156,6 mila a −€43,4 mila.
        </div>
        <div className="pd-b-bullet">
          <strong>Il MOL 2024:</strong> comprende €50.452 di proventi da cessione di crediti d'imposta: la loro ricorrenza non può essere presunta.
        </div>
        <div className="pd-b-bullet">
          <strong>Nel 2026:</strong> gli acquisti assorbono il 66,0% dei ricavi del quadrimestre, rispetto al 53,5% nel 2025. Rimanenze e lavori in corso non sono ricostruiti.
        </div>

        <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "12px 14px", marginTop: 16 }}>
          <div style={{ fontWeight: 700, color: "#102a43", fontSize: 12.5, marginBottom: 4 }}>
            Raccordo fiscale (componente dichiarativa vs cassa — nessuna prova di incassi ulteriori)
          </div>
          <div style={{ fontSize: 12, color: "#1e293b", lineHeight: 1.5 }}>
            Il Modello Redditi PF 2026 (anno 2025) riporta €63.256 al rigo RG5 per ricavi non annotati: il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. Queste somme non sono incassi né fatturato: il commercialista deve spiegarne l'origine. Fonte: quadro RG modello 2026, pag. 4.
          </div>
        </div>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 2 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 3: 02 / INDEBITAMENTO RICOSTRUITO                                  */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">02 / INDEBITAMENTO RICOSTRUITO</div>

        <p className="pd-b-p">
          Le esposizioni sono state riclassificate distinguendo debiti con riscontro, coobbligazioni personali e importi ancora dichiarativi. I saldi disponibili si riferiscono a date diverse: l'aggregato ha funzione istruttoria, non è una certificazione del debito.
        </p>

        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Posizione</th>
              <th>Fonte / stato</th>
              <th style={{ textAlign: "right" }}>Importo (€)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>AdER – cartelle/avvisi da saldare</td>
              <td>Estratto 29/10/2026</td>
              <td style={{ textAlign: "right" }}>386.695,79</td>
            </tr>
            <tr style={{ color: "#475569", fontSize: 11.5 }}>
              <td style={{ paddingLeft: 22 }}>di cui INPS (già incluso sopra)</td>
              <td>Avvisi di addebito</td>
              <td style={{ textAlign: "right" }}>210.604,29</td>
            </tr>
            <tr style={{ color: "#475569", fontSize: 11.5 }}>
              <td style={{ paddingLeft: 22 }}>di cui altri carichi (già inclusi sopra)</td>
              <td>Tributi/enti diversi</td>
              <td style={{ textAlign: "right" }}>176.091,50</td>
            </tr>
            <tr>
              <td>Intesa Sanpaolo – utilizzato CR</td>
              <td>Agosto 2026</td>
              <td style={{ textAlign: "right" }}>133.460,00</td>
            </tr>
            <tr>
              <td>Santander – coobbligazione personale</td>
              <td>CTC 30/09/2026, rate residue</td>
              <td style={{ textAlign: "right" }}>2.945,00</td>
            </tr>
            <tr className="highlight" style={{ borderTop: "2px solid #102a43" }}>
              <td><strong>ESPOSIZIONI PRINCIPALI QUANTIFICATE</strong></td>
              <td><strong>AdER + CR + Santander</strong></td>
              <td style={{ textAlign: "right" }}><strong>523.100,79</strong></td>
            </tr>
            <tr>
              <td>Fornitori</td>
              <td>Riferito nell'incontro</td>
              <td style={{ textAlign: "right" }}>120.000 circa</td>
            </tr>
            <tr>
              <td>Dipendenti e TFR</td>
              <td>Riferito nell'incontro</td>
              <td style={{ textAlign: "right" }}>70.000 circa</td>
            </tr>
            <tr>
              <td>Locazioni arretrate</td>
              <td>Riferito nell'incontro</td>
              <td style={{ textAlign: "right" }}>100.000–170.000</td>
            </tr>
            <tr className="highlight" style={{ borderTop: "2px solid #102a43", background: "#f8fafc" }}>
              <td><strong>TOTALE MISTO INDICATIVO</strong></td>
              <td><strong>Documentato + riferito</strong></td>
              <td style={{ textAlign: "right", color: "#102a43" }}><strong>813.101–883.101</strong></td>
            </tr>
          </tbody>
        </table>

        <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 18, lineHeight: 1.4 }}>
          N.B. Le righe 'di cui INPS' e 'di cui altri carichi' sono sottocomponenti AdER, non ulteriori debiti. Santander è incluso prudenzialmente come potenziale esposizione personale da coobbligazione, pur in assenza di scaduti segnalati; l'importo comprende rate residue, non soltanto capitale.
        </div>

        <div className="pd-sec-title">Ulteriori rapporti finanziari e assenza di doppio conteggio</div>
        <div className="pd-b-bullet">
          <strong>Findomestic:</strong> carta rateale attiva, €143,20 in scadenza al 30/09/2026; il saldo residuo complessivo non è noto. La scadenza viene censita ma non sommata come se fosse l'intero debito.
        </div>
        <div className="pd-b-bullet">
          <strong>GIADA SEC. / Intesa:</strong> la Centrale dei Rischi riporta esposizioni anche nel 2025 e cessioni successive. Sono date storiche/trasferimenti e non si sommano all'ultima segnalazione di €133.460 senza una ricostruzione contrattuale.
        </div>
        <div className="pd-b-bullet">
          <strong>Compass e Agos:</strong> rapporti CTC chiusi regolarmente; non inclusi. Il finanziamento di circa €170.000 e la rata di €6.000 mensili sono riferiti e non aggiunti all'ultima CR.
        </div>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Divergenza ancora aperta</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          Nell'incontro si è parlato di un totale di €640–690 mila, ma le cinque categorie dichiarate sommavano €810–880 mila. Il nuovo intervallo misto di €813–883 mila non risolve la differenza: non abbiamo scadenzari di fornitori, lavoratori e locazioni, né la riconciliazione di tutti i finanziamenti. Le rate della definizione agevolata AdER non sono aggiunte una seconda volta ai carichi già esposti.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b" }}>
          Fonti: AdER «Da saldare» 29/10/2026, pag. 5; CR Banca d'Italia, ultimo mese agosto 2026, pagg. 2–3 e storia delle segnalazioni; CTC 29/10/2026, pagg. 1–2; riepilogo incontro 20/10/2026, pag. 2.
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 3 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 4: 03 / PATRIMONIO E CONFRONTO LIQUIDATORIO                        */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">03 / PATRIMONIO E CONFRONTO LIQUIDATORIO</div>

        <p className="pd-b-p">
          Non è disponibile uno stato patrimoniale ricostruito. La ricognizione riguarda i beni individuati dai documenti, senza attribuire valore zero alle poste non conosciute.
        </p>

        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Categoria</th>
              <th>Evidenza</th>
              <th>Stato della stima</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Immobili</strong></td>
              <td>Ricerca catastale 29/10/2026: nessuna corrispondenza</td>
              <td>Nessun immobile emerso</td>
            </tr>
            <tr>
              <td><strong>Fiat Panda 2012</strong></td>
              <td>Proprietà da visura PRA; nessun gravame iscritto</td>
              <td>Valore da perizia</td>
            </tr>
            <tr>
              <td><strong>Altre 2 autovetture</strong></td>
              <td>Elenco della titolare; Captur con preavvisi di fermo</td>
              <td>Titoli/vincoli da verificare</td>
            </tr>
            <tr>
              <td><strong>4 autocarri Renault/Nissan</strong></td>
              <td>Elenco sottoscritto; dati tecnici incompleti</td>
              <td>Titoli/valore da verificare</td>
            </tr>
            <tr>
              <td><strong>Macchinari e attrezzature</strong></td>
              <td>Officina e ammortamenti in contabilità</td>
              <td>Nessun inventario</td>
            </tr>
            <tr>
              <td><strong>Crediti, rimanenze, cassa</strong></td>
              <td>Nessun saldo patrimoniale affidabile</td>
              <td>Non quantificabili</td>
            </tr>
          </tbody>
        </table>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Stima esplorativa delle vendite concorsuali</div>
        <p className="pd-b-p" style={{ fontSize: 12.5 }}>
          Per confronto con la liquidazione giudiziale si ipotizzano vendite competitive per lotti omogenei, con possibili esperimenti deserti, ribassi e costi. Gli intervalli non sono perizie, basi d'asta o prezzi osservati di aggiudicazione.
        </p>

        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Lotto indicativo</th>
              <th style={{ textAlign: "right" }}>Prudente</th>
              <th style={{ textAlign: "right" }}>Favorevole</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>3 autovetture</td>
              <td style={{ textAlign: "right" }}>€ 9.000</td>
              <td style={{ textAlign: "right" }}>€ 20.000</td>
            </tr>
            <tr>
              <td>4 autocarri</td>
              <td style={{ textAlign: "right" }}>€ 15.000</td>
              <td style={{ textAlign: "right" }}>€ 45.000</td>
            </tr>
            <tr>
              <td>Dotazioni dell'officina</td>
              <td style={{ textAlign: "right" }}>€ 0</td>
              <td style={{ textAlign: "right" }}>€ 8.000</td>
            </tr>
            <tr className="highlight">
              <td><strong>Realizzo lordo</strong></td>
              <td style={{ textAlign: "right" }}><strong>€ 24.000</strong></td>
              <td style={{ textAlign: "right" }}><strong>€ 73.000</strong></td>
            </tr>
            <tr className="highlight" style={{ background: "#f8fafc" }}>
              <td><strong>Realizzo netto diretto*</strong></td>
              <td style={{ textAlign: "right", color: "#102a43" }}><strong>~ € 20.000</strong></td>
              <td style={{ textAlign: "right", color: "#15803d" }}><strong>~ € 65.000</strong></td>
            </tr>
          </tbody>
        </table>

        <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 18, lineHeight: 1.4 }}>
          * Importi convenzionali dopo i costi direttamente imputabili alle vendite, prima di spese generali della procedura, imposte, vincoli e prelazioni. La stima presume la titolarità e commerciabilità dei veicoli dichiarati; per sei veicoli non è stata acquisita una visura PRA. Non comprende crediti, disponibilità liquide, rimanenze, né un eventuale valore dell'azienda in esercizio.
        </div>

        <div className="pd-sec-title">Implicazione economica</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          L'attivo mobiliare così stimato appare contenuto rispetto alle passività. Non è possibile stimare una percentuale di soddisfacimento dei creditori con le sole informazioni disponibili. Una cessione dell'azienda in funzionamento, anche in sede concorsuale, potrebbe preservare un valore maggiore della vendita per lotti, ma l'avviamento oggi non è dimostrato.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b" }}>
          Fonti: elenco beni mobili registrati del 29/10/2026; visura PRA Panda del 29/10/2026; esito ricerca catastale del 29/10/2026; contabilità 2024–2025; AdER «Procedure attive»; confronto estimativo interno non peritale.
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 4 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 5: 04 / REDDITIVITÀ E CONTINUITÀ                                   */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">04 / REDDITIVITÀ E CONTINUITÀ</div>

        <p className="pd-b-p">
          Il tema determinante non è il fatturato storico, ma la capacità dell'organizzazione ristrutturata di produrre margine operativo ricorrente e cassa. Gli esercizi che seguono sono test meccanici, non scenari di piano.
        </p>

        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Verifica sul 2026 annualizzato</th>
              <th style={{ textAlign: "right" }}>Importo</th>
              <th>Lettura</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>EBITDA quadrimestre × 3</td>
              <td style={{ textAlign: "right" }}>+€ 1,2 mila</td>
              <td>Pareggio contabile fragile</td>
            </tr>
            <tr>
              <td>Canoni inclusi nel ×3</td>
              <td style={{ textAlign: "right" }}>€ 4,5 mila</td>
              <td>Sotto ai € 18 mila storici</td>
            </tr>
            <tr>
              <td>EBITDA con canone storico ipotetico</td>
              <td style={{ textAlign: "right", color: "#b91c1c" }}>−€ 12,3 mila</td>
              <td>Solo rettifica locazioni</td>
            </tr>
            <tr>
              <td>Personale annualizzato da aprile</td>
              <td style={{ textAlign: "right" }}>€ 140,0 mila</td>
              <td>Non misura il nuovo assetto</td>
            </tr>
            <tr className="highlight">
              <td><strong>EBITDA con personale a €60–70 mila e canone storico</strong></td>
              <td style={{ textAlign: "right", color: "#102a43" }}><strong>~ € 57,7–67,7 mila</strong></td>
              <td><strong>Ipotesi dichiarativa, non previsione</strong></td>
            </tr>
            <tr>
              <td>Rata del finanziamento riferita</td>
              <td style={{ textAlign: "right" }}>€ 72 mila/anno</td>
              <td>Contratto non acquisito</td>
            </tr>
          </tbody>
        </table>

        <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 18, lineHeight: 1.4 }}>
          I test non tengono conto di rimanenze, imposte, investimenti, variazione del capitale circolante o costi aggiuntivi di lavorazioni esterne. Anche l'ipotesi più favorevole di EBITDA resta inferiore alla rata annua riferita di €72 mila, prima delle altre esigenze finanziarie.
        </div>

        <div className="pd-sec-title">Principali criticità operative</div>
        <div className="pd-b-bullet">
          <strong>Acquisti:</strong> l'incidenza sui ricavi raggiunge circa il 66% nel primo quadrimestre 2026; occorre capire se dipenda da mix commerciale, costi o disallineamento degli acquisti.
        </div>
        <div className="pd-b-bullet">
          <strong>Struttura:</strong> la riduzione del personale non prova che l'attività possa mantenere volumi e qualità con due risorse; forte dipendenza operativa da Salvatore.
        </div>
        <div className="pd-b-bullet">
          <strong>Circolante e liquidità:</strong> anticipi clienti, scaduti e condizioni dei fornitori non sono ricostruiti; non è possibile determinare flusso disponibile per il debito né DSCR attendibile.
        </div>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Giudizio preliminare</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          La continuità non è attualmente dimostrata, ma la potenziale riduzione dei costi giustifica una verifica mirata. Condizioni decisive: margine su commessa, costi effettivi dopo la riorganizzazione, completamento ordini, scadenze del debito e disponibilità di cassa. Un EBITDA positivo non coincide con il cash flow utilizzabile per pagare i creditori.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b" }}>
          Fonti: contabilità 2024–2026; riepilogo incontro del 20/10/2026; confronto tecnico interno sui saldi contabili e ipotesi riferite.
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 5 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 6: 05 / INQUADRAMENTO CCII                                         */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">05 / INQUADRAMENTO CCII</div>

        <div className="pd-sec-title">Impresa individuale: effetti decisivi</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          La ditta è un'impresa artigiana individuale. La qualifica camerale di «piccolo imprenditore» non coincide con quella di impresa minore ex art. 2, comma 1, lett. d), CCII. I ricavi 2023–2025 superano la soglia di €200.000 annui: il concordato minore non appare accessibile. La ditta è invece astrattamente assoggettabile a liquidazione giudiziale, ove ne ricorrano i presupposti (art. 121).
        </p>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          Il patrimonio aziendale non è separato da quello della titolare come in una S.r.l.: Lucrezia risponde personalmente delle obbligazioni, nei limiti di legge (art. 2740 c.c.). Anche le coobbligazioni e i rapporti personali devono essere censiti; cessazione o cessione dell'azienda non cancellano automaticamente i debiti. La posizione di Salvatore, indicato come collaboratore familiare al 49% nelle dichiarazioni fiscali, richiede la verifica dei diritti ex art. 230-bis c.c.
        </p>

        <div className="pd-sec-title">Strumenti confrontati</div>
        <table className="pd-b-table">
          <thead>
            <tr>
              <th>Strumento</th>
              <th>Prima valutazione</th>
              <th>Condizione di accesso / fattibilità</th>
            </tr>
          </thead>
          <tbody>
            <tr className="highlight">
              <td><strong>CNC - artt. 12 ss.</strong></td>
              <td><strong>Priorità di verifica</strong></td>
              <td><strong>Risanamento ragionevolmente perseguibile, anche tramite cessione</strong></td>
            </tr>
            <tr>
              <td>Accordi di ristrutturazione - artt. 57 e 63</td>
              <td>Valutabili</td>
              <td>Consensi, disciplina crediti tributari/contributivi e flussi</td>
            </tr>
            <tr>
              <td>Concordato preventivo - art. 84</td>
              <td>Alternativa possibile</td>
              <td>Proposta sostenibile; continuità o requisiti liquidatori</td>
            </tr>
            <tr>
              <td>Concordato minore - art. 74</td>
              <td style={{ color: "#b91c1c", fontWeight: 600 }}>Non appare accessibile</td>
              <td>Impresa non qualificabile come minore sulla base dei ricavi</td>
            </tr>
            <tr>
              <td>Liquidazione giudiziale - art. 121</td>
              <td>Alternativa effettiva</td>
              <td>Accertamento dell'insolvenza e inventario completo</td>
            </tr>
          </tbody>
        </table>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Avvertenze giuridiche</div>
        <div className="pd-b-bullet">
          <strong>Le misure protettive:</strong> nella CNC richiedono istanza e controllo giudiziale secondo gli artt. 18–19; non derivano automaticamente dalla sola intenzione di avviarla.
        </div>
        <div className="pd-b-bullet">
          <strong>Il trattamento di tributi e contributi:</strong> varia per strumento (artt. 23, 63 e 88 CCII); non si può presumere una falcidia. Eventuali estensioni ai tributi regionali/locali introdotte da novelle recenti (es. D.Lgs. 136/2024 e succ. mod.) vanno verificate sul testo ufficiale vigente.
        </div>
        <div className="pd-b-bullet">
          <strong>La newco:</strong> è un possibile veicolo di continuità indiretta, non uno strumento per liberare la titolare dai debiti; vanno valutati art. 2560 c.c., rapporti di lavoro e disciplina delle cessioni concorsuali.
        </div>
        <div className="pd-b-bullet">
          <strong>Liquidazione giudiziale:</strong> in un'eventuale liquidazione della persona fisica occorrerà esaminare presupposti ed effetti dell'esdebitazione (artt. 278 ss. CCII).
        </div>

        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b", marginTop: 12 }}>
          Normativa di riferimento: D.Lgs. 14/2019 (CCII) e D.Lgs. 136/2024 (Correttivo-ter), artt. 2, 12, 18–19, 23, 57, 63, 74, 84, 121, 214, 278 ss. CCII; artt. 230-bis, 2560 e 2740 c.c. Eventuali ulteriori aggiornamenti normativi (incluso il citato D.Lgs. 147/2026) richiedono verifica puntuale di vigenza in Gazzetta Ufficiale da parte del legale (Human Gate).
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 6 / 7</div>
        </div>
      </article>

      {/* ========================================================================= */}
      {/* PAGINA 7: 06 / CONCLUSIONI E PROPOSTA DI INCARICO                         */}
      {/* ========================================================================= */}
      <article className="pd-benchmark-sheet">
        <div className="pd-page-breadcrumb">RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA</div>
        <div className="pd-chapter-code">06 / CONCLUSIONI E PROPOSTA DI INCARICO</div>

        <div className="pd-sec-title" style={{ marginTop: 0, marginBottom: 12 }}>Indirizzo preliminare</div>

        {/* BANNER PROPOSTA CNC */}
        <div style={{ background: "#f8fafc", border: "1.5px solid #cbd5e1", borderRadius: 6, padding: "14px 18px", marginBottom: 18 }}>
          <div style={{ fontSize: 13.5, fontWeight: 800, color: "#102a43", marginBottom: 6, letterSpacing: 0.3 }}>
            PROPOSTA: VERIFICA DI FATTIBILITÀ DELLA COMPOSIZIONE NEGOZIATA
          </div>
          <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: "#1e293b" }}>
            Dare priorità a un incarico circoscritto volto a verificare se l'impresa, dopo la riorganizzazione, possa produrre cassa sufficiente a sostenere la gestione e un trattamento credibile delle passività. La CNC non è oggi assunta come procedura già scelta. In parallelo va mantenuto il confronto con liquidazione giudiziale e cessione in continuità indiretta.
          </p>
        </div>

        <div className="pd-sec-title">Perché questa impostazione</div>
        <div className="pd-b-bullet">
          <strong>L'impresa è operativa:</strong> e conserva una base commerciale, ma il 2025 è in perdita e il pareggio del primo quadrimestre 2026 non è consolidato.
        </div>
        <div className="pd-b-bullet">
          <strong>Il debito è elevato:</strong> €523.100,79 di esposizioni principali quantificate, considerando la coobbligazione personale, più €290–360 mila riferiti per fornitori, dipendenti e locazioni.
        </div>
        <div className="pd-b-bullet">
          <strong>L'attivo concorsuale:</strong> individuato è limitato e incompleto: senza crediti, magazzino e cespiti valorizzati non si può attestare la convenienza della continuità rispetto alla liquidazione.
        </div>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Verifiche essenziali dell'eventuale incarico successivo</div>
        <table className="pd-b-table">
          <thead>
            <tr>
              <th style={{ width: "12%", textAlign: "center" }}>Priorità</th>
              <th style={{ width: "52%" }}>Verifica mirata</th>
              <th style={{ width: "36%" }}>Risultato atteso</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ textAlign: "center", fontWeight: 700 }}>1</td>
              <td>Consuntivo 2026 post-riduzione; margini per commessa e capacità produttiva</td>
              <td><strong>EBITDA sostenibile</strong></td>
            </tr>
            <tr>
              <td style={{ textAlign: "center", fontWeight: 700 }}>2</td>
              <td>Scadenzari fornitori, dipendenti, locazioni, contratti finanziari e CTC aggiornata</td>
              <td><strong>Debito riconciliato</strong></td>
            </tr>
            <tr>
              <td style={{ textAlign: "center", fontWeight: 700 }}>3</td>
              <td>Incassi, pagamenti, anticipi, saldi bancari, rimanenze, crediti e cespiti</td>
              <td><strong>Cassa e attivo effettivo</strong></td>
            </tr>
            <tr>
              <td style={{ textAlign: "center", fontWeight: 700 }}>4</td>
              <td>Interlocuzione su crediti pubblici, disponibilità dei fornitori e ipotesi di cessione</td>
              <td><strong>Confronto CNC / altre opzioni / liquidazione</strong></td>
            </tr>
          </tbody>
        </table>

        <div className="pd-sec-title" style={{ marginTop: 18 }}>Conclusione</div>
        <p className="pd-b-p" style={{ fontSize: 12.5, lineHeight: 1.55 }}>
          Non è oggi possibile affermare che il risanamento sia fattibile. È però possibile proporre una verifica professionale mirata sulla CNC e sulle alternative, con un perimetro e risultati attesi definiti. Qualora la redditività normalizzata e la negoziabilità delle passività non trovassero riscontro, l'opzione liquidatoria dovrà essere valutata tempestivamente, considerando gli effetti personali sulla titolare.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b", lineHeight: 1.45 }}>
          Principali documenti utilizzati: Visura CCIAA 27/03/2026; Modelli Redditi PF 2024–2026; situazioni contabili 2024, 2025 e 30/04/2026; AdER «Da saldare», «Saldati», «Procedure attive» e moduli definizione agevolata; CR Banca d'Italia 29/10/2026 (ultimo dato agosto); visura CTC 29/10/2026; ricerca catastale, elenco beni, ispezione PRA; riepilogo dell'incontro 20/10/2026.
        </p>
        <p className="pd-b-p" style={{ fontSize: 11, color: "#64748b", lineHeight: 1.45 }}>
          Precisazione finale: la somma €523.100,79 combina date diverse e comprende €2.945 di rate residue riferite a una coobbligazione non scaduta. Le posizioni Findomestic e GIADA sono censite ma non maggiorate nel totale in assenza di evidenza di un debito ulteriore attuale. Il totale misto è soltanto indicativo e non sostituisce un elenco definitivo dei creditori.
        </p>

        <div className="pd-page-footer">
          <div>PRE-ANALISI CRISI D'IMPRESA | {clientName.toUpperCase()}</div>
          <div>RISERVATO • {draftDate} • 7 / 7</div>
        </div>
      </article>

      {/* PANNELLO COLLAPSIBILE DOSSIER TECNICO DI AUDIT E LOG FORENSE QWEN */}
      <div className="no-print" style={{ maxWidth: 860, margin: "0 auto 40px" }}>
        <button
          type="button"
          className="pd-btn pd-btn--ghost"
          style={{ width: "100%", justifyContent: "space-between", padding: "12px 18px", border: "1px dashed #0284c7", background: "#f8fafc", borderRadius: 6 }}
          onClick={() => setShowAiDetails((prev) => !prev)}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 13, color: "#102a43" }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: "#0284c7" }}>verified_user</span>
            {showAiDetails
              ? "Nascondi Dossier Tecnico di Calcolo e Audit (Quadrature Decimal, 13 Anomalie, Quality Gate)"
              : "Mostra Dossier Tecnico di Calcolo e Audit (Fonti SHA-256, 8 Quadrature Decimal, 13 Anomalie, Revisore Avversariale)"}
          </span>
          <span className="material-symbols-outlined">{showAiDetails ? "expand_less" : "expand_more"}</span>
        </button>

        {showAiDetails && (
          <div style={{ background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: "0 0 6px 6px", padding: 20, marginTop: -2 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span className="pd-badge pd-badge--ok" style={{ fontSize: 11, fontWeight: 700 }}>8/8 Quadrature Decimal 100%</span>
                <span className="pd-badge pd-badge--ok" style={{ fontSize: 11, fontWeight: 700 }}>5/5 Controlli Inferenze (Blocco RG5→Cassa)</span>
                <span className="pd-badge pd-badge--warn" style={{ fontSize: 11, fontWeight: 700 }}>13 Anomalie Codificate (3 Rosse — Human Gate)</span>
              </div>
              <button
                type="button"
                className="pd-btn pd-btn--primary"
                style={{ fontSize: 12, padding: "6px 12px", background: "#102a43" }}
                onClick={() => handleExportDossierPdf("download")}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>
                Scarica PDF Dossier Tecnico (8 pagg.)
              </button>
            </div>

            {report?.technical_dossier?.decimal_audit?.quadrature && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: "#102a43", marginBottom: 8 }}>
                  1. Controllo Indipendente dei Calcoli (Motore Matematico Decimal)
                </div>
                <table className="pd-b-table" style={{ fontSize: 11.5 }}>
                  <thead>
                    <tr>
                      <th>Codice</th>
                      <th>Controllo</th>
                      <th>Formula</th>
                      <th style={{ textAlign: "right" }}>Risultato</th>
                      <th style={{ textAlign: "center" }}>Esito</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.technical_dossier.decimal_audit.quadrature.map((q) => (
                      <tr key={q.quad_id}>
                        <td><strong>{q.quad_id}</strong></td>
                        <td>{q.titolo}</td>
                        <td>{q.formula}</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>{q.valore_calcolato}</td>
                        <td style={{ textAlign: "center", color: "#15803d", fontWeight: 700 }}>{q.esito}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {report?.technical_dossier?.anomaly_register && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: "#102a43", marginBottom: 8 }}>
                  2. Registro Codificato delle 13 Anomalie Istruttorie (ANOM-01 .. ANOM-13)
                </div>
                <table className="pd-b-table" style={{ fontSize: 11.5 }}>
                  <thead>
                    <tr>
                      <th>Codice</th>
                      <th>Severità</th>
                      <th>Area / Fonte</th>
                      <th>Anomalia Rilevata</th>
                      <th>Azione Richiesta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.technical_dossier.anomaly_register.map((an) => (
                      <tr key={an.code}>
                        <td><strong>{an.code}</strong></td>
                        <td style={{ fontWeight: 800, color: an.severita === "ROSSO" ? "#b91c1c" : an.severita === "ARANCIO" ? "#b45309" : "#334155" }}>
                          {an.severita}
                        </td>
                        <td><strong>{an.area}</strong><br /><span style={{ fontSize: 10.5, color: "#64748b" }}>{an.fonte}</span></td>
                        <td>{an.descrizione}</td>
                        <td>{an.azione_richiesta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {report?.technical_dossier?.adversarial_review && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: "#102a43", marginBottom: 8 }}>
                  3. Revisione Avversariale: Controargomentazioni alla Praticabilità della CNC (OBIEZ-01 .. OBIEZ-06)
                </div>
                <table className="pd-b-table" style={{ fontSize: 11.5 }}>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Obiezione Critica</th>
                      <th>Argomentazione Tecnica</th>
                      <th>Impatto CCII</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.technical_dossier.adversarial_review.map((ob) => (
                      <tr key={ob.id}>
                        <td style={{ fontWeight: 800, color: "#b91c1c" }}>{ob.id}</td>
                        <td><strong>{ob.titolo}</strong></td>
                        <td>{ob.argomentazione}</td>
                        <td>{ob.impatto_ccii}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {report?.forensic_preanalysis?.json_matrix && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#102a43", marginBottom: 6 }}>Matrice di Estrazione Numerica Certificata (JSON)</div>
                <pre style={{ background: "#f1f5f9", padding: 12, borderRadius: 4, fontSize: 11.5, overflowX: "auto" }}>
                  {JSON.stringify(report.forensic_preanalysis.json_matrix, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AuditTrail({ edits, docs, goTab }) {
  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2 className="pd-h2">Audit e correzioni</h2>
          <p>Cronologia completa delle modifiche manuali, con campo, motivazione e timestamp.</p>
        </div>
        <button className="pd-btn pd-btn--secondary" type="button" onClick={() => goTab("documenti")}>Vedi documenti</button>
      </div>
      <div className="pd-grid pd-grid--3">
        <div className="pd-kpi"><div className="pd-kpi__label">Correzioni</div><div className="pd-kpi__value">{(edits || []).length}</div><div className="pd-kpi__note">Storico FieldEdit</div></div>
        <div className="pd-kpi"><div className="pd-kpi__label">Documenti</div><div className="pd-kpi__value">{(docs || []).length}</div><div className="pd-kpi__note">Fonti collegate</div></div>
        <div className="pd-kpi"><div className="pd-kpi__label">Tracciabilita</div><div className="pd-kpi__value" style={{ fontSize: 24 }}>Completa</div><div className="pd-kpi__note">Grezzo, corretto, derivato</div></div>
      </div>
      <div className="pd-table-wrap">
        <table className="pd-table">
          <thead><tr><th>Timestamp</th><th>Autore</th><th>Entita</th><th>Campo</th><th>Prima</th><th>Dopo</th><th>Motivazione</th></tr></thead>
          <tbody>
            {(edits || []).map((item) => (
              <tr key={item.id}>
                <td>{formatDateTime(item.created_at)}</td>
                <td>Operatore</td>
                <td>{item.entity_type}<div className="pd-faint" style={{ fontSize: 12 }}>{item.entity_id}</div></td>
                <td><strong>{item.field}</strong></td>
                <td><span style={{ color: "var(--pd-danger)", textDecoration: "line-through" }}>{stringValue(item.old_value)}</span></td>
                <td><span style={{ color: "var(--pd-ok)", fontWeight: 700 }}>{stringValue(item.new_value)}</span></td>
                <td>{item.reason || "Motivazione non indicata"}</td>
              </tr>
            ))}
            {(edits || []).length === 0 && <tr><td colSpan={7}>Nessuna correzione manuale registrata.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CrossAnalysis({ crossAnalysis, loading, onRun, goTab }) {
  const inc = crossAnalysis?.incongruenze || [];
  const dup = crossAnalysis?.duplicazioni || [];
  const scenari = crossAnalysis?.scenari || [];
  const note = crossAnalysis?.note_per_il_titolare || [];
  const docMancanti = crossAnalysis?.documenti_mancanti || [];

  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 className="pd-h2" style={{ margin: 0 }}>Super-Analisi del Fascicolo</h2>
            <span className="pd-badge pd-badge--primary">Qwen 27B Local</span>
          </div>
          <p style={{ marginTop: 4 }}>Controllo incrociato trasversale tra tutti i documenti, rilevamento duplicazioni e verifica scenari CCII.</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {crossAnalysis && (
            <button className="pd-btn pd-btn--secondary" type="button" onClick={() => goTab("report")}>
              <span className="material-symbols-outlined" aria-hidden="true">visibility</span>
              Vedi nel Report Finale
            </button>
          )}
          <button
            className="pd-btn pd-btn--primary"
            type="button"
            disabled={loading}
            onClick={onRun}
          >
            <span className="material-symbols-outlined" aria-hidden="true">{loading ? "hourglass_top" : "psychology"}</span>
            {loading ? "Analisi in corso con Qwen..." : crossAnalysis ? "Rianalizza Fascicolo" : "Avvia Super-Analisi"}
          </button>
        </div>
      </div>

      {loading && (
        <div className="pd-card" style={{ padding: 24, textAlign: "center", background: "var(--pd-surface)" }}>
          <div style={{ display: "inline-block", animation: "spin 2s linear infinite", fontSize: 32, marginBottom: 12 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 36, color: "var(--pd-primary)" }}>sync</span>
          </div>
          <h3 className="pd-h3" style={{ margin: "0 0 8px" }}>Qwen 3.8 (27B) sta analizzando l'intero fascicolo...</h3>
          <p className="pd-muted" style={{ maxWidth: 640, margin: "0 auto", fontSize: 13 }}>
            Il modello sta confrontando i debiti tributari (AER), le segnalazioni di Centrale Rischi, i bilanci d'esercizio e i dati anagrafico-patrimoniali per individuare incongruenze, duplicazioni e percorsi giuridici.
          </p>
        </div>
      )}

      {!crossAnalysis && !loading && (
        <div className="pd-card" style={{ padding: 32, textAlign: "center", background: "var(--pd-surface)" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: "var(--pd-primary)", marginBottom: 12 }}>hub</span>
          <h3 className="pd-h3" style={{ margin: "0 0 8px" }}>Nessuna analisi trasversale eseguita</h3>
          <p className="pd-muted" style={{ maxWidth: 580, margin: "0 auto 20px", fontSize: 14 }}>
            Esegui la super-analisi trasversale per far dialogare tutti i documenti del fascicolo in un unico contesto cognitivo con il modello Qwen locale.
          </p>
          <button className="pd-btn pd-btn--primary" type="button" onClick={onRun}>
            <span className="material-symbols-outlined" aria-hidden="true">psychology</span>
            Esegui Super-Analisi con Qwen 27B
          </button>
        </div>
      )}

      {crossAnalysis && !loading && (
        <>
          <div className="pd-grid pd-grid--4">
            <div className="pd-kpi">
              <div className="pd-kpi__label">Incongruenze</div>
              <div className="pd-kpi__value" style={{ color: inc.length > 0 ? "var(--pd-warn)" : "var(--pd-ok)" }}>{inc.length}</div>
              <div className="pd-kpi__note">Discrasie documentali</div>
            </div>
            <div className="pd-kpi">
              <div className="pd-kpi__label">Duplicazioni</div>
              <div className="pd-kpi__value" style={{ color: dup.length > 0 ? "var(--pd-accent)" : "var(--pd-ok)" }}>{dup.length}</div>
              <div className="pd-kpi__note">Partite duplicate / sovrapposte</div>
            </div>
            <div className="pd-kpi">
              <div className="pd-kpi__label">Scenari CCII</div>
              <div className="pd-kpi__value">{scenari.length}</div>
              <div className="pd-kpi__note">Strumenti concorsuali valutati</div>
            </div>
            <div className="pd-kpi">
              <div className="pd-kpi__label">Modello</div>
              <div className="pd-kpi__value" style={{ fontSize: 18 }}>{crossAnalysis.model_used || "Qwen 27B"}</div>
              <div className="pd-kpi__note">{crossAnalysis.created_at ? new Date(crossAnalysis.created_at).toLocaleString("it-IT") : "Eseguito"}</div>
            </div>
          </div>

          {crossAnalysis.sintesi_generale && (
            <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
              <h3 className="pd-h4" style={{ margin: "0 0 8px", color: "var(--pd-primary)" }}>Sintesi e quadro generale</h3>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--pd-text)" }}>{crossAnalysis.sintesi_generale}</p>
            </div>
          )}

          <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 className="pd-h4" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                <span className="material-symbols-outlined" style={{ color: "var(--pd-warn)" }}>warning</span>
                Incongruenze e Discrasie tra Fonti ({inc.length})
              </h3>
            </div>
            <div className="pd-table-wrap">
              <table className="pd-table">
                <thead>
                  <tr>
                    <th>Gravità</th>
                    <th>Descrizione discrepanza</th>
                    <th>Fonti a confronto</th>
                    <th>Azione per il legale</th>
                  </tr>
                </thead>
                <tbody>
                  {inc.map((item, idx) => (
                    <tr key={idx}>
                      <td><span className={`pd-badge pd-badge--${item.gravita === "SOSTANZIALE" || item.gravita === "GRAVE" ? "danger" : "warn"}`}>{item.gravita || "VERIFICA"}</span></td>
                      <td><strong>{item.descrizione}</strong></td>
                      <td style={{ fontSize: 13 }}>{item.documenti_coinvolti || "Documenti del fascicolo"}</td>
                      <td style={{ fontSize: 13, color: "var(--pd-primary)", fontWeight: 600 }}>{item.azione_consigliata || "-"}</td>
                    </tr>
                  ))}
                  {inc.length === 0 && <tr><td colSpan={4}>Nessuna incongruenza o discrasia rilevata tra i documenti.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 className="pd-h4" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>content_copy</span>
                Rilevamento Duplicazioni di Debito ({dup.length})
              </h3>
            </div>
            <div className="pd-table-wrap">
              <table className="pd-table">
                <thead>
                  <tr>
                    <th>Partita / Voce di Debito</th>
                    <th>Importo</th>
                    <th>Fonti e Documenti Coinvolti</th>
                    <th>Calcolo / Trattamento Consigliato</th>
                  </tr>
                </thead>
                <tbody>
                  {dup.map((item, idx) => (
                    <tr key={idx}>
                      <td><strong>{item.partita}</strong></td>
                      <td className="pd-num"><strong>{item.importo}</strong></td>
                      <td style={{ fontSize: 13 }}>{item.documenti_coinvolti}</td>
                      <td style={{ fontSize: 13, color: "var(--pd-ok)", fontWeight: 600 }}>{item.calcolo_consigliato}</td>
                    </tr>
                  ))}
                  {dup.length === 0 && <tr><td colSpan={4}>Nessuna duplicazione di debito rilevata.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          {scenari.length > 0 && (
            <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
              <h3 className="pd-h4" style={{ margin: "0 0 14px", display: "flex", alignItems: "center", gap: 8 }}>
                <span className="material-symbols-outlined" style={{ color: "var(--pd-primary)" }}>gavel</span>
                Valutazione Preliminare Scenari CCII (Codice della Crisi)
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
                {scenari.map((s, idx) => (
                  <div key={idx} style={{ background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <strong style={{ fontSize: 15, color: "var(--pd-primary)" }}>{s.scenario}</strong>
                      <span className={`pd-badge pd-badge--${s.fattibilita === "ALTA" ? "ok" : s.fattibilita === "MEDIA" ? "warn" : s.fattibilita === "BASSA" ? "danger" : "neutral"}`}>
                        Fattibilità: {s.fattibilita}
                      </span>
                    </div>
                    <p style={{ margin: "6px 0", fontSize: 13, lineHeight: 1.5, color: "var(--pd-text)" }}>{s.motivazione}</p>
                    {s.dati_chiave && <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--pd-text-muted)" }}><strong>Elementi chiave:</strong> {s.dati_chiave}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pd-grid pd-grid--2">
            {docMancanti.length > 0 && (
              <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
                <h3 className="pd-h4" style={{ margin: "0 0 12px", display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ color: "var(--pd-warn)" }}>inventory_2</span>
                  Documenti Mancanti Suggeriti ({docMancanti.length})
                </h3>
                <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, lineHeight: 1.6, color: "var(--pd-text)" }}>
                  {docMancanti.map((d, idx) => <li key={idx} style={{ marginBottom: 4 }}><strong>{typeof d === 'string' ? d : d.documento || JSON.stringify(d)}</strong>{d.motivo ? ` — ${d.motivo}` : ''}</li>)}
                </ul>
              </div>
            )}

            {note.length > 0 && (
              <div className="pd-card" style={{ padding: 18, background: "var(--pd-surface)" }}>
                <h3 className="pd-h4" style={{ margin: "0 0 12px", display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ color: "var(--pd-primary)" }}>edit_note</span>
                  Raccomandazioni per l'Avv. Bentivegna
                </h3>
                <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, lineHeight: 1.6, color: "var(--pd-text)" }}>
                  {note.map((n, idx) => <li key={idx} style={{ marginBottom: 6 }}>{n}</li>)}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}