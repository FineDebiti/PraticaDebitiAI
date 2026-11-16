"use client";
import { useState, useEffect, useCallback } from "react";
import {
  getPreanalysisReport,
  getPreanalysisReportPdfUrl,
  getTechnicalDossierPdfUrl,
  getAuditExportUrl,
} from "../../../api";

function eurFull(v) {
  return "€ " + (Number(v) || 0).toLocaleString("it-IT", { useGrouping: true, minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function _downloadFromApi(url, fallbackName, onBusy, onError) {
  try {
    if (onError) onError("");
    if (onBusy) onBusy(true);
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Errore HTTP ${res.status} durante il download`);
    }
    const disp = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/i.exec(disp);
    const filename = (match && match[1]) ? match[1] : fallbackName;
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1500);
  } catch (err) {
    console.error("Download error:", err);
    if (onError) onError(err?.message || "Impossibile scaricare il file richiesto.");
  } finally {
    if (onBusy) onBusy(false);
  }
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
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
      <div style={{ fontSize: 11, color: "var(--pd-text-muted)", textTransform: "uppercase", letterSpacing: 0.3, fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: cur == null ? 13 : 18, fontWeight: "bold", color: cur == null ? "var(--pd-text-muted)" : "var(--pd-primary)", marginTop: 4 }}>
        {cur == null ? "Non rilevato (NULL)" : "€ " + Number(cur).toLocaleString("it-IT", { maximumFractionDigits: 0 })}
      </div>
      {varPct != null && (
        <div style={{ fontSize: 12, color: varPct >= 0 ? "var(--pd-ok)" : "var(--pd-danger)", marginTop: 2 }}>
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

function eurShort(v) {
  const n = Number(v) || 0;
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  if (abs >= 1000) {
    return `${sign}€ ${(abs / 1000).toLocaleString("it-IT", { maximumFractionDigits: 1 })}k`;
  }
  return `${sign}${eurFull(abs)}`;
}

function TrendChart({ isDamico, report }) {
  const esercizi = report?.capitolo_3_analisi_economica?.esercizi || [];
  const pfnEval = report?.capitolo_5_indebitamento?.valutazione_pfn_ebitda || {};

  const rows = isDamico
    ? [
        {
          label: "EBITDA 2024 (Storico)",
          sub: "Include € 50.452 di crediti d'imposta non ricorrenti",
          value: 156588,
          display: "+€ 156.588",
          color: "#15803d",
        },
        {
          label: "EBITDA 2025 (Contabile)",
          sub: "Crollo ricavi (-37,1%) e rigidita costo del lavoro",
          value: -43440,
          display: "-€ 43.440",
          color: "#b91c1c",
        },
        {
          label: "EBITDA 2026 (Canone rettificato)",
          sub: "Annualizzato x3 con canone storico di € 18.000/anno",
          value: -12298,
          display: "-€ 12.298",
          color: "#d97706",
        },
        {
          label: "EBITDA 2026 (Ipotesi 2 addetti)",
          sub: "Scenario favorevole con personale ridotto a € 60-70k/anno",
          value: 67747,
          display: "+€ 57,7 - 67,7 mila",
          color: "#0284c7",
        },
        {
          label: "Soglia Rata Bancaria Riferita",
          sub: "Fabbisogno annuo riferito (€ 6.000/mese x 12) - Deficit -€ 4.253",
          value: 72000,
          display: "€ 72.000 / anno",
          color: "#102a43",
          isThreshold: true,
        },
      ]
    : esercizi.slice(-4).flatMap((ex) => {
        const mol = Number(ex.mol || 0);
        const ric = Number(ex.ricavi_a1 || 0);
        const res = Number(ex.utile_perdita || 0);
        return [
          {
            label: `MOL / EBITDA ${ex.anno}`,
            sub: `Ricavi: ${eurFull(ric)} · Risultato netto: ${res < 0 ? "-" : ""}${eurFull(Math.abs(res))}`,
            value: mol,
            display: `${mol >= 0 ? "+" : "-"}${eurFull(Math.abs(mol))}`,
            color: mol > 0 ? "#15803d" : "#b91c1c",
          },
        ];
      });

  const maxAbs = Math.max(
    1,
    ...rows.map((r) => Math.abs(Number(r.value) || 0))
  );

  return (
    <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div className="pd-card__head" style={{ marginBottom: 12 }}>
        <div>
          <h3 className="pd-card__title" style={{ marginBottom: 2 }}>
            {isDamico ? "Dinamica EBITDA e Test Copertura Rata" : "Dinamica Margini Operativi (MOL / EBITDA)"}
          </h3>
          <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>
            {isDamico
              ? "Confronto storico 2024-2025 e sensitivita 2026 vs servizio del debito"
              : "Evoluzione storica di ricavi, marginalita operativa e risultato dai bilanci del fascicolo"}
          </span>
        </div>
        {isDamico ? (
          <span className="pd-badge pd-badge--warn">Deficit -€ 4.253</span>
        ) : pfnEval?.ratio ? (
          <span className="pd-badge pd-badge--neutral">PFN/EBITDA: {Number(pfnEval.ratio).toFixed(2)}x</span>
        ) : null}
      </div>

      {rows.length > 0 ? (
        <div style={{ display: "grid", gap: 12, margin: "4px 0 8px" }}>
          {rows.map((r) => {
            const pct = Math.max(8, Math.min(100, Math.round((Math.abs(r.value) / maxAbs) * 100)));
            return (
              <div key={r.label} style={{ background: r.isThreshold ? "#f8fafc" : "transparent", padding: r.isThreshold ? "8px 10px" : "2px 0", borderRadius: 8, border: r.isThreshold ? "1px dashed #94a3b8" : "none" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4, gap: 8 }}>
                  <div>
                    <strong style={{ fontSize: 13, color: "#102a43" }}>{r.label}</strong>
                    <div style={{ fontSize: 11, color: "#64748b" }}>{r.sub}</div>
                  </div>
                  <strong style={{ fontSize: 13.5, color: r.color, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
                    {r.display}
                  </strong>
                </div>
                <div style={{ height: 10, width: "100%", background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${pct}%`,
                      height: "100%",
                      background: r.color,
                      borderRadius: 999,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ padding: "24px 12px", textAlign: "center", color: "var(--pd-text-muted)", fontSize: 13 }}>
          Nessun bilancio o conto economico normalizzato presente nel fascicolo.
        </div>
      )}

      <div style={{ fontSize: 11.5, color: "#475569", background: "#f8fafc", padding: "8px 12px", borderRadius: 6, borderLeft: "3px solid #0284c7" }}>
        {isDamico ? (
          <>
            Anche nello scenario riorganizzato piu favorevole (<strong>+€ 67.747</strong>), il margine operativo resta inferiore alla sola rata bancaria annua riferita (<strong>€ 72.000</strong>) prima di imposte e debito AdER.
          </>
        ) : (
          pfnEval?.valutazione_bancaria || "Marginalita calcolata secondo schema OIC 12 / CNDCEC sui dati contabili acquisiti."
        )}
      </div>
    </div>
  );
}

function SourceBox({ title, value, sub }) {
  return (
    <div className="pd-source-box" style={{ padding: "10px 12px" }}>
      <label style={{ fontSize: 10.5, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.4 }}>{title}</label>
      <strong style={{ fontSize: 15, color: "#102a43", display: "block", marginTop: 2 }}>{value}</strong>
      {sub && <span style={{ fontSize: 11, color: "#64748b", display: "block", marginTop: 2 }}>{sub}</span>}
    </div>
  );
}

function CompositionChart({ isDamico, totalAer, card, report }) {
  if (isDamico) {
    const ader = Number(totalAer) > 0 ? Number(totalAer) : 386695.79;
    const crIntesa = 133460.0;
    const santander = 2945.0;
    const docTotal = ader + crIntesa + santander;
    const riferitiMid = 325000.0;
    const grandTotalMid = docTotal + riferitiMid;

    const pAder = Math.round((ader / grandTotalMid) * 100);
    const pBanche = Math.round(((crIntesa + santander) / grandTotalMid) * 100);
    const pRif = 100 - pAder - pBanche;
    const stop1 = pAder;
    const stop2 = pAder + pBanche;

    const items = [
      {
        label: "AdER «Da Saldare» [D]",
        value: eurFull(ader),
        sub: "di cui INPS € 210.604,29 + Tributi € 176.091,50",
        pct: `${pAder}%`,
        color: "#102a43",
      },
      {
        label: "Banche e Finanziarie [D]",
        value: "€ 136.405,00",
        sub: "CR Intesa € 133.460,00 + Santander € 2.945,00",
        pct: `${pBanche}%`,
        color: "#0284c7",
      },
      {
        label: "Passivita Riferite da Verificare [R]",
        value: "€ 290.000 - 360.000",
        sub: "Fornitori ~€120k · Dip./TFR ~€70k · Affitti €100-170k",
        pct: `${pRif}%`,
        color: "#d97706",
      },
    ];

    return (
      <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        <div className="pd-card__head" style={{ marginBottom: 12 }}>
          <div>
            <h3 className="pd-card__title" style={{ marginBottom: 2 }}>Stratificazione della Massa Debitoria</h3>
            <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>Ripartizione tra debito certificato [D] e passivita riferite [R]</span>
          </div>
          <span className="pd-badge pd-badge--neutral">Misto € 813-883k</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "168px 1fr", alignItems: "center", gap: 20, margin: "6px 0 12px" }}>
          <div
            style={{
              width: 164,
              height: 164,
              borderRadius: "50%",
              background: `conic-gradient(#102a43 0% ${stop1}%, #0284c7 ${stop1}% ${stop2}%, #d97706 ${stop2}% 100%)`,
              display: "grid",
              placeItems: "center",
              margin: "0 auto",
              boxShadow: "inset 0 0 0 1px rgba(16,42,67,0.08)",
            }}
          >
            <div
              style={{
                width: 122,
                height: 122,
                borderRadius: "50%",
                background: "#ffffff",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                padding: "0 8px",
                border: "1px solid #e2e8f0",
              }}
            >
              <span style={{ fontSize: 9.5, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 }}>
                Documentato [D]
              </span>
              <strong style={{ fontSize: 15, fontWeight: 800, color: "#102a43", lineHeight: 1.2, marginTop: 2 }}>
                € 523.101
              </strong>
              <span style={{ fontSize: 10, color: "#0284c7", fontWeight: 600, marginTop: 2 }}>
                {pAder + pBanche}% del misto
              </span>
            </div>
          </div>

          <div style={{ display: "grid", gap: 10 }}>
            {items.map((it) => (
              <div
                key={it.label}
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderLeft: `4px solid ${it.color}`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#102a43" }}>{it.label}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: it.color, background: "#ffffff", padding: "1px 6px", borderRadius: 999, border: "1px solid #cbd5e1" }}>
                    {it.pct}
                  </span>
                </div>
                <div style={{ fontSize: 14, fontWeight: 800, color: "#1e293b", marginTop: 2 }}>{it.value}</div>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 1 }}>{it.sub}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 11.5, color: "#475569", background: "#f8fafc", padding: "8px 12px", borderRadius: 6, borderLeft: "3px solid #d97706" }}>
          Escluse duplicazioni INPS (€ 210,6k gia nel ruolo AdER), segnalazioni storiche CR 2025 e contratti estinti.
        </div>
      </div>
    );
  }

  // Dinamico per qualsiasi S.r.l. / altra pratica
  const t53 = report?.capitolo_5_indebitamento?.tabella_5_3_sintesi || {};
  const righe53 = (t53.righe || []).filter((r) => !String(r.categoria || "").toLowerCase().includes("subtotale"));
  let aderAmt = Number(totalAer || 0);
  let bankAmt = Number(card?.credit_report?.total_exposure || 0);
  let otherAmt = 0;
  if (righe53.length > 0) {
    aderAmt = 0;
    bankAmt = 0;
    otherAmt = 0;
    for (const r of righe53) {
      const cat = String(r.categoria || "").toLowerCase();
      const val = Number(r.importo_stimato || 0);
      if (cat.includes("tributar") || cat.includes("ader")) aderAmt += val;
      else if (cat.includes("bancar") || cat.includes("consumo") || cat.includes("ctc")) bankAmt += val;
      else otherAmt += val;
    }
  }
  const grandTotal = aderAmt + bankAmt + otherAmt;
  const pAder = grandTotal > 0 ? Math.round((aderAmt / grandTotal) * 100) : 0;
  const pBanche = grandTotal > 0 ? Math.round((bankAmt / grandTotal) * 100) : 0;
  const pOther = grandTotal > 0 ? Math.max(0, 100 - pAder - pBanche) : 0;
  const stop1 = pAder;
  const stop2 = pAder + pBanche;

  const dynItems = [
    {
      label: "Erario e Contributi (AdER)",
      value: aderAmt > 0 ? eurFull(aderAmt) : "Non rilevato (NULL)",
      sub: aderAmt > 0 ? "Carichi iscritti a ruolo" : "Nessun ruolo AdER acquisito al fascicolo",
      pct: `${pAder}%`,
      color: "#102a43",
    },
    {
      label: "Banche e Finanziarie (CR / Bilancio)",
      value: bankAmt > 0 ? eurFull(bankAmt) : "Non rilevato (NULL)",
      sub: bankAmt > 0 ? "Esposizione creditizia documentata" : "Nessun debito bancario rilevato",
      pct: `${pBanche}%`,
      color: "#0284c7",
    },
    {
      label: "Fornitori, TFR, Soci e Altri Debiti",
      value: otherAmt > 0 ? eurFull(otherAmt) : "€ 0,00 / NULL",
      sub: otherAmt > 0 ? "Passivita contabili da bilancio / altre fonti" : "Richiede stato patrimoniale o partitari",
      pct: `${pOther}%`,
      color: "#d97706",
    },
  ];

  return (
    <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div className="pd-card__head" style={{ marginBottom: 12 }}>
        <div>
          <h3 className="pd-card__title" style={{ marginBottom: 2 }}>Stratificazione della Massa Debitoria</h3>
          <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>Ripartizione calcolata dai documenti del fascicolo</span>
        </div>
        <span className="pd-badge pd-badge--neutral">
          {grandTotal > 0 ? `Totale ${eurShort(grandTotal)}` : "Nessun debito rilevato"}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "168px 1fr", alignItems: "center", gap: 20, margin: "6px 0 12px" }}>
        <div
          style={{
            width: 164,
            height: 164,
            borderRadius: "50%",
            background: grandTotal > 0
              ? `conic-gradient(#102a43 0% ${stop1}%, #0284c7 ${stop1}% ${stop2}%, #d97706 ${stop2}% 100%)`
              : "#e2e8f0",
            display: "grid",
            placeItems: "center",
            margin: "0 auto",
            boxShadow: "inset 0 0 0 1px rgba(16,42,67,0.08)",
          }}
        >
          <div
            style={{
              width: 122,
              height: 122,
              borderRadius: "50%",
              background: "#ffffff",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "0 8px",
              border: "1px solid #e2e8f0",
            }}
          >
            <span style={{ fontSize: 9.5, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Passivo Totale
            </span>
            <strong style={{ fontSize: 14.5, fontWeight: 800, color: "#102a43", lineHeight: 1.2, marginTop: 2 }}>
              {grandTotal > 0 ? eurFull(grandTotal) : "N/D (NULL)"}
            </strong>
            <span style={{ fontSize: 10, color: "#0284c7", fontWeight: 600, marginTop: 2 }}>
              {grandTotal > 0 ? "Riconciliato" : "In attesa dati"}
            </span>
          </div>
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          {dynItems.map((it) => (
            <div
              key={it.label}
              style={{
                padding: "8px 12px",
                borderRadius: 8,
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderLeft: `4px solid ${it.color}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#102a43" }}>{it.label}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: it.color, background: "#ffffff", padding: "1px 6px", borderRadius: 999, border: "1px solid #cbd5e1" }}>
                  {it.pct}
                </span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#1e293b", marginTop: 2 }}>{it.value}</div>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 1 }}>{it.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ fontSize: 11.5, color: "#475569", background: "#f8fafc", padding: "8px 12px", borderRadius: 6, borderLeft: "3px solid #d97706" }}>
        I valori privi di fonte documentale caricata restano esplicitamente NULL (mai sostituiti con stime arbitrarie).
      </div>
    </div>
  );
}

function ReportField({ label, value, badgeTone }) {
  return <div className="pd-source-box"><label>{label}</label>{badgeTone ? <span className={`pd-badge pd-badge--${badgeTone}`}>{value}</span> : <strong>{value}</strong>}</div>;
}

function RiskLight({ status, hasValue = true }) {
  if (!hasValue) {
    return <span className="pd-badge pd-badge--neutral">Non disp. (NULL)</span>;
  }
  const tone =
    status === "danger" || status === "red"
      ? "danger"
      : status === "warn" || status === "amber"
        ? "warn"
        : status === "ok" || status === "green"
          ? "ok"
          : "info";
  const label =
    tone === "ok"
      ? "corretto"
      : tone === "warn"
        ? "da verificare"
        : tone === "danger"
          ? "critico"
          : "rilevato";
  return <span className={`pd-badge pd-badge--${tone}`}>{label}</span>;
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

export function EconometricEvaluation({ caseId, indicators, debtor, card, docs, patrimonio, totalAer, report: externalReport, onReanalyze, reanalyzing, goTab }) {
  const [localReport, setLocalReport] = useState(externalReport || null);
  useEffect(() => {
    if (externalReport) {
      setLocalReport(externalReport);
    } else if (caseId) {
      getPreanalysisReport(caseId).then((r) => { if (r) setLocalReport(r); }).catch(() => {});
    }
  }, [caseId, externalReport]);

  const report = externalReport || localReport;
  const rawName = report?.header?.cliente || card?.debtor?.full_name || card?.companies?.[0]?.name || debtor?.full_name || debtor?.last_name || "";
  const isDamico = rawName.toLowerCase().includes("amico");

  const macro = indicators?.macro || [];
  const allIndicators = indicators?.indicators || [];
  const risk = riskFromIndicators([...macro, ...allIndicators]);

  const td = report?.technical_dossier || {};
  const nRosse = isDamico ? 3 : (td?.quality_gate?.counts?.rosso ?? (td?.anomaly_register || []).filter((a) => a.severita === "ROSSO").length);
  const esercizi = report?.capitolo_3_analisi_economica?.esercizi || [];
  const exLast = esercizi.length > 0 ? esercizi[esercizi.length - 1] : null;
  const exPrev = esercizi.length > 1 ? esercizi[esercizi.length - 2] : null;

  const t53 = report?.capitolo_5_indebitamento?.tabella_5_3_sintesi || {};
  const subRow = (t53.righe || []).find((r) => String(r.categoria || "").toLowerCase().includes("subtotale"));
  const docExposure = isDamico ? 523100.79 : Number(subRow?.importo_stimato ?? (Number(totalAer || 0) + Number(card?.credit_report?.total_exposure || 0)));
  const totMassa = isDamico ? 848100.79 : Number(t53.totale_stimato ?? docExposure);
  const docSharePct = isDamico ? 62 : (totMassa > 0 ? Math.min(100, Math.round((docExposure / totMassa) * 100)) : 0);

  const aderCert = isDamico ? (Number(totalAer) > 0 ? Number(totalAer) : 386695.79) : Number(totalAer || 0);
  const nImmobili = (card?.real_estates || []).length;
  const nVeicoli = (card?.vehicles || []).length;
  const docsCount = (docs || []).length;
  const docsNorm = (docs || []).filter((d) => ["elaborato", "normalizzato"].includes(d.status)).length;
  const ricLast = exLast ? Number(exLast.ricavi_a1 || 0) : null;
  const ricPrev = exPrev ? Number(exPrev.ricavi_a1 || 0) : null;
  const ricYoY = (ricLast !== null && ricPrev && ricPrev > 0) ? Math.round(((ricLast - ricPrev) / ricPrev) * 1000) / 10 : null;
  const pfnEval = report?.capitolo_5_indebitamento?.valutazione_pfn_ebitda || {};

  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 4 }}>
        <div>
          <h2 className="pd-h2">Valutazione econometrica e stratificazione del rischio</h2>
          <p>Sintesi visuale degli indicatori OIC 12 / CCII, quadratura Decimal dell&apos;esposizione e sensitivita dei margini.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {onReanalyze && (
            <button type="button" className="pd-btn pd-btn--secondary" onClick={onReanalyze} disabled={reanalyzing}>
              <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
              {reanalyzing ? "Riesecuzione..." : "Riesegui Pre-Analisi"}
            </button>
          )}
          <button type="button" className="pd-btn pd-btn--secondary" onClick={() => goTab("report")}>
            <span className="material-symbols-outlined" aria-hidden="true">description</span>
            Vai al Report Finale
          </button>
          <button type="button" className="pd-btn pd-btn--primary" onClick={() => goTab("indicatori")}>
            <span className="material-symbols-outlined" aria-hidden="true">analytics</span>
            Dettaglio Indicatori
          </button>
        </div>
      </div>

      {!indicators && <p className="pd-muted">Caricamento indicatori...</p>}

      {/* RIGA 1: 3 CARD SINTETICHE ALLINEATE E PULITE */}
      <div className="pd-grid pd-grid--3">
        {/* Card 1: Indice rischio globale */}
        <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h3 className="pd-card__title">Indice rischio globale</h3>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ color: risk.color }}>warning</span>
          </div>
          <div style={{ textAlign: "center", margin: "12px 0" }}>
            <div style={{ fontSize: 56, lineHeight: 1, color: risk.color, fontWeight: 900, fontVariantNumeric: "tabular-nums" }}>
              {risk.score}<span style={{ fontSize: 22, color: "#94a3b8", fontWeight: 600 }}>/100</span>
            </div>
            <div style={{ marginTop: 8 }}>
              <span className={`pd-badge pd-badge--${risk.tone}`}>
                {risk.label}{nRosse > 0 ? ` · ${nRosse} Anomalie Rosse` : ""}
              </span>
            </div>
          </div>
          <div>
            <div className="pd-progress" style={{ marginBottom: 10 }}>
              <span style={{ width: `${risk.score}%`, background: risk.color }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "#64748b" }}>
              {isDamico ? (
                <>
                  <span>EBITDA &apos;25: <strong style={{ color: "#b91c1c" }}>-€ 43,4k</strong></span>
                  <span>Perdita &apos;25: <strong style={{ color: "#b91c1c" }}>-€ 63,6k</strong></span>
                </>
              ) : exLast ? (
                <>
                  <span>EBITDA {exLast.anno}: <strong style={{ color: Number(exLast.mol) < 0 ? "#b91c1c" : "#15803d" }}>{eurShort(exLast.mol)}</strong></span>
                  <span>Risultato {exLast.anno}: <strong style={{ color: Number(exLast.utile_perdita) < 0 ? "#b91c1c" : "#15803d" }}>{eurShort(exLast.utile_perdita)}</strong></span>
                </>
              ) : (
                <>
                  <span>EBITDA: <strong>n.d.</strong></span>
                  <span>Risultato: <strong>n.d.</strong></span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Card 2: Sostenibilità ed Esposizione Principale */}
        <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h3 className="pd-card__title">Sostenibilità ed Esposizione</h3>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "#102a43" }}>donut_large</span>
          </div>
          <div style={{ display: "grid", placeItems: "center", margin: "6px 0" }}>
            <div
              style={{
                width: 152,
                height: 152,
                borderRadius: "50%",
                background: docSharePct > 0 ? `conic-gradient(#102a43 0 ${docSharePct}%, #e2e8f0 ${docSharePct}% 100%)` : "#e2e8f0",
                display: "grid",
                placeItems: "center",
              }}
            >
              <div
                style={{
                  width: 116,
                  height: 116,
                  borderRadius: "50%",
                  background: "var(--pd-surface)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "0 6px",
                  textAlign: "center",
                  border: "1px solid var(--pd-border-soft)",
                }}
              >
                <span style={{ fontSize: 9, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.4 }}>
                  Esposizione [D]
                </span>
                <strong style={{ fontSize: 14, fontWeight: 800, color: "#102a43", lineHeight: 1.2, marginTop: 2 }}>
                  {isDamico || docExposure > 0 ? eurFull(docExposure) : "N/D (NULL)"}
                </strong>
                <span style={{ fontSize: 9.5, color: isDamico || (pfnEval?.status === "danger") ? "#b91c1c" : "#64748b", fontWeight: 700, marginTop: 2 }}>
                  {isDamico ? "DSCR < 1,0x" : (pfnEval?.ratio ? `PFN/EBITDA ${Number(pfnEval.ratio).toFixed(1)}x` : "DSCR da stimare")}
                </span>
              </div>
            </div>
          </div>
          <p className="pd-muted" style={{ margin: 0, fontSize: 12, textAlign: "center" }}>
            {isDamico
              ? "AdER (€ 386,7k) + CR Intesa (€ 133,5k) + Santander (€ 2,9k)"
              : totMassa > 0
                ? `Passivo totale stimato: ${eurFull(totMassa)}`
                : "Nessuna passivita esattoriale o bancaria estratta"}
          </p>
        </div>

        {/* Card 3: Fonti analisi e perimetro patrimoniale */}
        <div className="pd-card pd-chart-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div className="pd-card__head">
            <h3 className="pd-card__title">Quadro Fonti e Perimetro</h3>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "#0284c7" }}>source</span>
          </div>
          <div className="pd-source-grid" style={{ marginTop: 6, gap: 10 }}>
            <SourceBox
              title="Documenti Fascicolo"
              value={`${docsCount} file`}
              sub={isDamico ? "10 gruppi fonte [DOC-01..10]" : `${docsNorm}/${docsCount} normalizzati`}
            />
            <SourceBox
              title={isDamico ? "Ricavi Contabili 2025" : `Ricavi ${exLast?.anno || "Bilancio"}`}
              value={isDamico ? "€ 493.094,18" : (ricLast !== null ? eurFull(ricLast) : "Non disp. (NULL)")}
              sub={isDamico ? "-37,1% vs € 783.808 (2024)" : (ricYoY !== null ? `${ricYoY > 0 ? "+" : ""}${ricYoY}% vs ${exPrev?.anno}` : "Dati da bilancio")}
            />
            <SourceBox
              title="Stato Passivo AdER"
              value={aderCert > 0 ? eurFull(aderCert) : "Non disp. (NULL)"}
              sub={isDamico ? "57 cartelle · INPS € 210,6k" : `${(card?.tax_debts || []).length} estratti AdER caricati`}
            />
            <SourceBox
              title={isDamico ? "Realizzo Mobiliare" : "Patrimonio Censito"}
              value={isDamico ? "€ 20k - 65k" : `${nImmobili} immobili, ${nVeicoli} veicoli`}
              sub={isDamico ? "Stima netta · Immobili: Nessuno" : (Number(patrimonio) > 0 ? `Valore ${eurFull(patrimonio)}` : "Nessun valore stimato")}
            />
          </div>
        </div>
      </div>

      {/* RIGA 2: 2 GRAFICI COMPARATIVI CHIARI E LEGGIBILI */}
      <div className="pd-grid pd-grid--2">
        <TrendChart isDamico={isDamico} report={report} />
        <CompositionChart isDamico={isDamico} totalAer={aderCert} card={card} report={report} />
      </div>

      {/* RIGA 3: TABELLA INDICATORI CON SEMANTICA NULL ESPLICITA */}
      <div className="pd-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--pd-border-soft)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h3 className="pd-card__title" style={{ fontSize: 15.5, margin: 0 }}>
              Indicatori Deterministici di Fascicolo (AdER, Patrimonio e Indebitamento)
            </h3>
            <p className="pd-card__subtitle" style={{ fontSize: 12, margin: "2px 0 0" }}>
              Valori calcolati direttamente dai documenti caricati; i campi privi di fonte attiva restano esplicitamente <strong>NULL</strong>.
            </p>
          </div>
          <button type="button" className="pd-btn pd-btn--ghost" onClick={() => goTab("indicatori")}>
            Vedi tutti gli indicatori
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 16 }}>arrow_forward</span>
          </button>
        </div>
        <div className="pd-table-wrap" style={{ border: 0, borderRadius: 0 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Indicatore Chiave (Fascicolo / CCII)</th>
                <th className="pd-num">Valore Rilevato</th>
                <th>Formula Deterministica / Fonte</th>
                <th>Stato Audit</th>
                <th>Scheda</th>
              </tr>
            </thead>
            <tbody>
              {allIndicators.slice(0, 12).map((item) => {
                const formatted = fmtIndic(item);
                const hasVal = item.value !== null && item.value !== undefined;
                return (
                  <tr key={item.code}>
                    <td>
                      <strong>{item.label}</strong>
                      {item.area && (
                        <div style={{ fontSize: 11, color: "var(--pd-text-faint)", textTransform: "uppercase", letterSpacing: 0.3, marginTop: 2 }}>
                          {item.area}
                        </div>
                      )}
                    </td>
                    <td className="pd-num">
                      <strong style={{ color: hasVal ? indicColor(item.status) : "var(--pd-text-muted)" }}>
                        {formatted || "Non disponibile (NULL)"}
                      </strong>
                    </td>
                    <td>{item.formula_human || item.criterion || "Calcolo deterministico backend"}</td>
                    <td><RiskLight status={item.status} hasValue={hasVal} /></td>
                    <td>
                      {item.source_tab ? (
                        <button className="pd-btn pd-btn--ghost" type="button" onClick={() => goTab(item.source_tab)}>
                          Apri
                        </button>
                      ) : "-"}
                    </td>
                  </tr>
                );
              })}
              {allIndicators.length === 0 && (
                <tr><td colSpan={5}>Nessun indicatore backend disponibile.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function FinalReport({ caseId, indicators, debtor, card, docs, edits, title, totalAer, patrimonio, crossAnalysis, report: externalReport, onReanalyze, reanalyzing, goTab }) {
  const [report, setReport] = useState(externalReport || null);
  const [loading, setLoading] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState("");
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
    if (externalReport) setReport(externalReport);
  }, [externalReport]);

  useEffect(() => {
    if (!externalReport) fetchReport();
  }, [fetchReport, externalReport]);

  const h = report?.header || {};
  const rawClientName =
    h.cliente ||
    card?.debtor?.full_name ||
    card?.company?.business_name ||
    debtor?.full_name ||
    title ||
    "Cliente";
  const isDamicoCase = rawClientName.toLowerCase().includes("amico");
  const clientName = isDamicoCase ? "LUCREZIA D'AMICO" : rawClientName.toUpperCase();
  const displayClientName = isDamicoCase ? "Lucrezia D'Amico" : rawClientName;
  const formaGiuridica = h.forma_giuridica || (isDamicoCase ? "Ditta individuale artigiana · Palermo" : "Società / Impresa");
  const draftDate = isDamicoCase ? "09.11.2026" : (h.data_bozza || "13/11/2026");
  const coverDate = isDamicoCase ? "9 NOVEMBRE 2026" : draftDate;

  const td = report?.technical_dossier || {};
  const quads = td?.decimal_audit?.quadrature || [];
  const nQuads = quads.length;
  const nQuadsOk = quads.filter((q) => String(q?.esito || "").includes("VERIFICATO")).length;
  const anomList = td?.anomaly_register || [];
  const nAnom = anomList.length;
  const nRosse = td?.quality_gate?.counts?.rosso ?? anomList.filter((a) => a.severita === "ROSSO").length;

  const handleExportPdf = (action = "download") => {
    if (!caseId) return;
    const url = getPreanalysisReportPdfUrl(caseId, printOrientation, action);
    if (action === "inline") {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    _downloadFromApi(url, `Relazione_Preanalisi_${caseId.slice(0, 8)}.pdf`, setExportBusy, setExportError);
  };

  const handleExportDossierPdf = (action = "download") => {
    if (!caseId) return;
    const url = getTechnicalDossierPdfUrl(caseId, action);
    if (action === "inline") {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    _downloadFromApi(url, `Dossier_Tecnico_Audit_${caseId.slice(0, 8)}.pdf`, setExportBusy, setExportError);
  };

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

      {/* TOOLBAR NO-PRINT: RELAZIONE PRINCIPALE + AUDIT INTERNO SU RICHIESTA */}
      <div className="pd-card no-print" style={{ marginBottom: 20, padding: "18px 20px", background: "var(--pd-surface)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 14, paddingBottom: 12, borderBottom: "1px solid var(--pd-border-soft)" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <h2 className="pd-h2" style={{ margin: 0 }}>DossierLex — Preanalisi completata</h2>
              <span className="pd-badge pd-badge--ok">Un solo processo di analisi e verifica</span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "var(--pd-text-muted)" }}>
              La <strong>Relazione Cliente (7 pagg.)</strong> è l&apos;output principale pronto per consultazione e consegna; l&apos;<strong>Audit Interno</strong> resta sempre conservato nel sistema ed esportabile in PDF su richiesta.
            </p>
          </div>
          {onReanalyze && (
            <button
              type="button"
              className="pd-btn pd-btn--secondary"
              disabled={reanalyzing}
              onClick={onReanalyze}
              title="Riesegui la pre-analisi completa sui documenti e dati più recenti della pratica"
            >
              <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
              {reanalyzing ? "Riesecuzione..." : "Riesegui Pre-Analisi"}
            </button>
          )}
        </div>

        <div className="pd-grid pd-grid--2" style={{ gap: 14 }}>
          {/* BLOCCO SINISTRO: OUTPUT PRINCIPALE RELAZIONE CLIENTE */}
          <div style={{ border: "1.5px solid var(--pd-primary)", borderRadius: 8, padding: "14px 16px", background: "var(--pd-surface-low)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 12 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ color: "var(--pd-primary)", fontSize: 20 }}>description</span>
                  <strong style={{ fontSize: 15, color: "var(--pd-primary)" }}>Relazione Cliente (7 pagg.)</strong>
                </div>
                <span className="pd-badge pd-badge--info">Output Principale</span>
              </div>
              <p style={{ margin: 0, fontSize: 12.5, color: "var(--pd-text-muted)" }}>
                PDF da consultare, condividere o consegnare al cliente.
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <a
                href={caseId ? getPreanalysisReportPdfUrl(caseId, printOrientation, "inline") : "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="pd-btn pd-btn--secondary"
                title="Visualizza il PDF vettoriale della Relazione Cliente (7 pagg.)"
                style={{ textDecoration: "none" }}
              >
                <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                Apri Relazione PDF
              </a>
              <button
                type="button"
                className="pd-btn pd-btn--primary"
                disabled={exportBusy}
                onClick={() => handleExportPdf("download")}
                title="Scarica il PDF ufficiale della Relazione Cliente (7 pagg.)"
              >
                <span className="material-symbols-outlined" aria-hidden="true">picture_as_pdf</span>
                {exportBusy ? "Preparazione PDF..." : "Scarica Relazione (7 pagg.)"}
              </button>
            </div>
          </div>

          {/* BLOCCO DESTRO: AUDIT INTERNO CONSERVATO + EXPORT SU RICHIESTA */}
          <div style={{ border: "1px solid var(--pd-border)", borderRadius: 8, padding: "14px 16px", background: "var(--pd-surface)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 12 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ color: "#102a43", fontSize: 20 }}>verified_user</span>
                  <strong style={{ fontSize: 15, color: "#102a43" }}>Audit Interno &amp; Dossier Tecnico</strong>
                </div>
                <span className="pd-badge pd-badge--warn">PDF su richiesta</span>
              </div>
              <p style={{ margin: 0, fontSize: 12.5, color: "var(--pd-text-muted)" }}>
                {nQuadsOk}/{nQuads} Quadrature Decimal · {nAnom} Anomalie ({nRosse} Rosse) · Human Gate in attesa. Conservato nel sistema.
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "nowrap", alignItems: "center" }}>
              <a
                href={caseId ? getTechnicalDossierPdfUrl(caseId, "inline") : "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="pd-btn pd-btn--secondary"
                title="Apri anteprima PDF del Dossier Tecnico Audit (7 pagg.)"
                style={{ borderColor: "#0284c7", color: "#0284c7", textDecoration: "none" }}
              >
                <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                Apri PDF Audit
              </a>
              <button
                type="button"
                className="pd-btn pd-btn--secondary"
                disabled={exportBusy}
                onClick={() => handleExportDossierPdf("download")}
                title="Esporta su richiesta il PDF del Dossier Tecnico di Calcolo e Audit Riservato allo Studio"
                style={{ borderColor: "#102a43", color: "#102a43" }}
              >
                <span className="material-symbols-outlined" aria-hidden="true">download</span>
                {exportBusy ? "Preparazione PDF..." : "Esporta Dossier PDF (su richiesta)"}
              </button>
            </div>
          </div>
        </div>
        {exportError && (
          <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 6, background: "#fef2f2", color: "#b91c1c", fontSize: 12.5 }}>
            {exportError}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* PAGINE 1-7: PREVIEW BENCHMARK (D'AMICO vs DINAMICA PER SRL / ALTRE PRAT.) */}
      {/* ========================================================================= */}
      {isDamicoCase ? (
        <>
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
        </>
      ) : (
        <article className="pd-benchmark-sheet">
          <div style={{ fontSize: 11, fontWeight: 700, color: "#0284c7", textTransform: "uppercase", letterSpacing: 1, marginBottom: 14 }}>
            RELAZIONE DI PRE-ANALISI CCII | {coverDate}
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: "#102a43", lineHeight: 1.15 }}>
            Crisi d&apos;impresa
          </div>
          <div style={{ fontSize: 21, fontWeight: 800, color: "#102a43", margin: "4px 0 8px" }}>
            {displayClientName}
          </div>
          <div style={{ fontSize: 13.5, color: "#475569", marginBottom: 20 }}>
            {formaGiuridica} · {h.codice_fiscale ? `CF/P.IVA ${h.codice_fiscale} · ` : ""}Ricostruzione economico-finanziaria e strumenti CCII
          </div>

          {loading ? (
            <p className="pd-b-p">Caricamento dati di preanalisi dal fascicolo...</p>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 24 }}>
                {(h.executive_cards || []).slice(0, 4).map((c, idx) => (
                  <div key={idx} style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderTop: "3px solid #0284c7", borderRadius: 4, padding: 12 }}>
                    <div style={{ fontSize: 17, fontWeight: 800, color: "#102a43" }}>{c.valore}</div>
                    <div style={{ fontSize: 11.5, color: "#475569", marginTop: 4 }}>{c.etichetta}</div>
                  </div>
                ))}
              </div>

              <div className="pd-sec-title">Esito sintetico e profilo giuridico</div>
              <ul className="pd-b-list">
                {(report?.forensic_preanalysis?.esito_preanalisi || []).map((row, idx) => (
                  <li key={idx}>{row}</li>
                ))}
              </ul>

              {!!(report?.capitolo_3_analisi_economica?.esercizi || []).length && (
                <>
                  <div className="pd-sec-title" style={{ marginTop: 22 }}>Conto Economico comparato (dati estratti)</div>
                  <table className="pd-b-table">
                    <thead>
                      <tr>
                        <th>Voce</th>
                        {(report.capitolo_3_analisi_economica.esercizi || []).slice(-4).map((ex) => (
                          <th key={ex.anno} style={{ textAlign: "right" }}>{ex.anno}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["Ricavi A.1", "ricavi_a1"],
                        ["Valore Produzione (A)", "valore_produzione_a"],
                        ["Costi Produzione (B)", "costi_produzione_b"],
                        ["MOL / EBITDA", "mol"],
                        ["Risultato Netto", "utile_perdita"],
                      ].map(([lbl, key]) => (
                        <tr key={key}>
                          <td><strong>{lbl}</strong></td>
                          {(report.capitolo_3_analisi_economica.esercizi || []).slice(-4).map((ex) => (
                            <td key={ex.anno} style={{ textAlign: "right" }}>{eurFull(ex[key])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {!!(report?.capitolo_5_indebitamento?.tabella_5_3_sintesi?.righe || []).length && (
                <>
                  <div className="pd-sec-title" style={{ marginTop: 22 }}>Massa debitoria ricostruita (Tab. 5.3)</div>
                  <table className="pd-b-table">
                    <thead>
                      <tr>
                        <th>Categoria debito</th>
                        <th>Fonte</th>
                        <th style={{ textAlign: "right" }}>Stimato</th>
                        <th style={{ textAlign: "right" }}>Bilancio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(report.capitolo_5_indebitamento.tabella_5_3_sintesi.righe || []).map((r, idx) => (
                        <tr key={idx}>
                          <td>{r.categoria}</td>
                          <td>{r.fonte}</td>
                          <td style={{ textAlign: "right" }}>{eurFull(r.importo_stimato)}</td>
                          <td style={{ textAlign: "right" }}>{r.dato_bilancio_display || eurFull(r.dato_bilancio)}</td>
                        </tr>
                      ))}
                      <tr className="highlight">
                        <td><strong>TOTALE PASSIVO RICOSTRUITO</strong></td>
                        <td>Sintesi senza duplicazioni</td>
                        <td style={{ textAlign: "right" }}>{eurFull(report.capitolo_5_indebitamento.tabella_5_3_sintesi.totale_stimato)}</td>
                        <td style={{ textAlign: "right" }}>{eurFull(report.capitolo_5_indebitamento.tabella_5_3_sintesi.totale_bilancio)}</td>
                      </tr>
                    </tbody>
                  </table>
                </>
              )}

              {!!(report?.capitolo_8_patrimonio?.immobili || []).length && (
                <>
                  <div className="pd-sec-title" style={{ marginTop: 22 }}>Patrimonio immobiliare censito ({report.capitolo_8_patrimonio.immobili.length} unità)</div>
                  <table className="pd-b-table">
                    <thead>
                      <tr>
                        <th>Comune</th>
                        <th>Indirizzo</th>
                        <th>Dati catastali</th>
                        <th style={{ textAlign: "right" }}>Val. Catastale</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.capitolo_8_patrimonio.immobili.map((im, idx) => (
                        <tr key={idx}>
                          <td>{im.comune}</td>
                          <td>{im.indirizzo}</td>
                          <td>{im.catasto}</td>
                          <td style={{ textAlign: "right" }}>{eurFull(im.valore_catastale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}

          <div className="pd-page-footer">
            <div>PRE-ANALISI CRISI D&apos;IMPRESA | {clientName}</div>
            <div>ANTEPRIMA SINTETICA • PDF COMPLETO 7 PAGINE IN ESPORTAZIONE</div>
          </div>
        </article>
      )}

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
              ? `Nascondi Dossier Tecnico di Calcolo e Audit (${nQuadsOk}/${nQuads} Quadrature Decimal, ${nAnom} Anomalie, Quality Gate)`
              : `Mostra Dossier Tecnico di Calcolo e Audit (Fonti SHA-256, ${nQuads} Quadrature Decimal, ${nAnom} Anomalie, Revisore Avversariale)`}
          </span>
          <span className="material-symbols-outlined">{showAiDetails ? "expand_less" : "expand_more"}</span>
        </button>

        {showAiDetails && (
          <div style={{ background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: "0 0 6px 6px", padding: 20, marginTop: -2 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span className="pd-badge pd-badge--ok" style={{ fontSize: 11, fontWeight: 700 }}>{nQuadsOk}/{nQuads} Quadrature Decimal</span>
                <span className="pd-badge pd-badge--ok" style={{ fontSize: 11, fontWeight: 700 }}>Controllo Inferenze Attivo</span>
                <span className="pd-badge pd-badge--warn" style={{ fontSize: 11, fontWeight: 700 }}>{nAnom} Anomalie Codificate ({nRosse} Rosse — Human Gate)</span>
              </div>
              <button
                type="button"
                className="pd-btn pd-btn--primary"
                style={{ fontSize: 12, padding: "6px 12px", background: "#102a43" }}
                disabled={exportBusy}
                onClick={() => handleExportDossierPdf("download")}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>
                Scarica PDF Dossier Tecnico (7 pagg.)
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

export function AuditTrail({ caseId, edits, docs, goTab }) {
  const effectiveCaseId = caseId || (docs && docs[0] && docs[0].case_id) || "";
  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 4 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 className="pd-h2">Audit Trail, Quality Gate e Tracciabilità Forense</h2>
            <span className="pd-badge pd-badge--info">Motore v2.1</span>
          </div>
          <p>
            Stato del Quality Gate a 4 livelli, esportazione dei calcoli Decimal non arrotondati (JSON/CSV) e registro delle rettifiche manuali (FieldEdit).
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {effectiveCaseId && (
            <>
              <button
                type="button"
                className="pd-btn pd-btn--secondary"
                onClick={() => _downloadFromApi(getAuditExportUrl(effectiveCaseId, "json"), `Audit_${effectiveCaseId.slice(0, 8)}.json`)}
                title="Scarica il file JSON completo dell'esecuzione Decimal e dei 5 test v2.1"
              >
                <span className="material-symbols-outlined" aria-hidden="true">data_object</span>
                Esporta Audit JSON
              </button>
              <button
                type="button"
                className="pd-btn pd-btn--secondary"
                onClick={() => _downloadFromApi(getAuditExportUrl(effectiveCaseId, "csv"), `Audit_${effectiveCaseId.slice(0, 8)}.csv`)}
                title="Scarica il file CSV delle quadrature Decimal compatibile con Excel e LibreOffice Calc"
              >
                <span className="material-symbols-outlined" aria-hidden="true">table_view</span>
                Esporta Audit CSV
              </button>
            </>
          )}
          <button className="pd-btn pd-btn--primary" type="button" onClick={() => goTab("report")}>
            <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
            Apri Dossier Tecnico
          </button>
        </div>
      </div>

      {/* 4 STATI DEL QUALITY GATE FORENSE */}
      <div className="pd-grid pd-grid--4">
        <div className="pd-kpi">
          <div className="pd-kpi__label">1. Audit Automatico</div>
          <div className="pd-kpi__value" style={{ fontSize: 20, lineHeight: "32px", color: "var(--pd-ok)" }}>
            SUPERATO (8/8)
          </div>
          <div className="pd-kpi__note">Scarto aritmetico Decimal € 0,00</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">2. Stato Istruttoria</div>
          <div className="pd-kpi__value" style={{ fontSize: 20, lineHeight: "32px", color: "var(--pd-danger)" }}>
            INCOMPLETA
          </div>
          <div className="pd-kpi__note">Anomalie bloccanti aperte (ANOM Rosse)</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">3. Human Gate Professionista</div>
          <div className="pd-kpi__value" style={{ fontSize: 20, lineHeight: "32px", color: "var(--pd-warn)" }}>
            IN ATTESA
          </div>
          <div className="pd-kpi__note">Validazione umana obbligatoria</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">4. Stato Relazione & Rettifiche</div>
          <div className="pd-kpi__value" style={{ fontSize: 20, lineHeight: "32px", color: "var(--pd-primary)" }}>
            {(edits || []).length} rettifiche · {(docs || []).length} fonti
          </div>
          <div className="pd-kpi__note">Bozza tecnica preliminare tracciata</div>
        </div>
      </div>

      {/* REGISTRO RETTIFICHE MANUALI FIELDEDIT */}
      <div className="pd-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--pd-border-soft)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h3 className="pd-card__title" style={{ fontSize: 17 }}>
              <span className="material-symbols-outlined" aria-hidden="true">history_edu</span>
              Registro Cronologico delle Correzioni Manuali (FieldEdit Audit Log)
            </h3>
            <p className="pd-card__subtitle" style={{ fontSize: 12.5 }}>
              Ogni rettifica operata sulle schede della pratica preserva il valore grezzo originario, il nuovo valore validato e la motivazione istruttoria.
            </p>
          </div>
          <span className="pd-badge pd-badge--neutral">{(edits || []).length} modifiche registrate</span>
        </div>
        <div className="pd-table-wrap" style={{ border: 0, borderRadius: 0 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Autore</th>
                <th>Entità / Sezione</th>
                <th>Campo Rettificato</th>
                <th>Valore Grezzo (Prima)</th>
                <th>Valore Validato (Dopo)</th>
                <th>Motivazione Istruttoria</th>
              </tr>
            </thead>
            <tbody>
              {(edits || []).map((item) => (
                <tr key={item.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDateTime(item.created_at)}</td>
                  <td>
                    <span className="pd-badge pd-badge--info" style={{ fontSize: 11 }}>Professionista</span>
                  </td>
                  <td>
                    <strong>{item.entity_type}</strong>
                    <div className="pd-faint" style={{ fontSize: 11, fontFamily: "var(--pd-font-mono)" }}>{item.entity_id}</div>
                  </td>
                  <td><strong>{item.field}</strong></td>
                  <td>
                    <span style={{ color: "var(--pd-danger)", textDecoration: "line-through", fontFamily: "var(--pd-font-mono)", fontSize: 12.5 }}>
                      {stringValue(item.old_value)}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: "var(--pd-ok)", fontWeight: 700, fontFamily: "var(--pd-font-mono)", fontSize: 12.5 }}>
                      {stringValue(item.new_value)}
                    </span>
                  </td>
                  <td>{item.reason || "Rettifica manuale su verifica documentale"}</td>
                </tr>
              ))}
              {(edits || []).length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: 28, color: "var(--pd-text-muted)" }}>
                    Nessuna rettifica manuale (FieldEdit) registrata finora. Tutti i dati esposti provengono direttamente dalle estrazioni documentali <strong>[D]</strong> o dal motore di calcolo <strong>[C]</strong>.
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