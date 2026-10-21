"use client";
import { useState, useEffect, useCallback } from "react";
import {
  getPreanalysisReport,
  getPreanalysisReportPdfUrl,
  learnStudioRule,
  synthesizeStudioRule,
  createStudioRule,
  listStudioRules,
  updateStudioRule,
  deleteStudioRule,
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

// ============================================================================
// MODULO REVISIONE E ADDESTRAMENTO CONTINUO (STILE DOSSIERLEX)
// ============================================================================

function AntigravityReviewDropdown({
  isOpen,
  onClose,
  caseId,
  clientName,
  onInstructionSaved,
}) {
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!comment.trim()) {
      setError("Inserisci un messaggio o istruzione.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await learnStudioRule({
        case_id: caseId,
        client_name: clientName,
        scope: "global",
        scope_title: "Direttive Generali Fascicolo & Studio",
        user_comment: comment.trim(),
        current_context_text: `Fascicolo ${clientName || ""}`,
        author: "Responsabile Analisi",
      });
      setMsg("✓ Istruzione appresa da DossierLex!");
      setComment("");
      if (onInstructionSaved) onInstructionSaved(res);
      setTimeout(() => {
        setMsg(null);
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || "Errore durante il salvataggio.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="no-print"
      style={{
        position: "absolute",
        top: "calc(100% + 6px)",
        right: 0,
        width: 360,
        background: "var(--pd-surface)",
        border: "1px solid var(--pd-border)",
        borderTop: "3.5px solid var(--pd-primary)",
        borderRadius: "var(--pd-radius-lg)",
        padding: "16px 18px",
        boxShadow: "0 10px 28px rgba(45, 54, 40, 0.16)",
        zIndex: 1000,
        textAlign: "left",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <strong style={{ fontSize: 13.5, color: "var(--pd-primary)", fontWeight: 700 }}>
          Submit comment
        </strong>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "none", border: "none", color: "var(--pd-text-muted)", cursor: "pointer", padding: 0 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
        </button>
      </div>

      <p style={{ margin: "0 0 10px", fontSize: 12, color: "var(--pd-text-muted)", lineHeight: 1.4 }}>
        Istruzioni generali sull'intero report o seleziona un paragrafo con [+] per commentare.
      </p>

      {error && (
        <div style={{ background: "var(--pd-danger-bg)", border: "1px solid var(--pd-danger)", color: "var(--pd-danger)", padding: "6px 8px", borderRadius: 6, fontSize: 12, marginBottom: 8 }}>
          {error}
        </div>
      )}
      {msg && (
        <div style={{ background: "var(--pd-ok-bg)", border: "1px solid var(--pd-ok)", color: "var(--pd-ok)", padding: "6px 8px", borderRadius: 6, fontSize: 12, marginBottom: 8 }}>
          {msg}
        </div>
      )}

      <textarea
        rows={3}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Add a message..."
        style={{
          width: "100%",
          background: "var(--pd-surface-low)",
          border: "1px solid var(--pd-border)",
          borderRadius: "var(--pd-radius)",
          color: "var(--pd-text)",
          padding: "8px 10px",
          fontSize: 13,
          resize: "vertical",
          boxSizing: "border-box",
          outline: "none",
          marginBottom: 10,
        }}
      />

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading}
          style={{
            background: "var(--pd-accent)",
            color: "#ffffff",
            border: "none",
            borderRadius: "var(--pd-radius)",
            padding: "6px 16px",
            fontSize: 13,
            fontWeight: 600,
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            transition: "background 0.12s",
          }}
        >
          {loading ? "Salvataggio..." : "Submit"}
        </button>
      </div>
    </div>
  );
}

function AntigravitySectionPlus({ scopeKey, scopeTitle, isOpen, onToggle }) {
  return (
    <button
      type="button"
      className="pd-antigravity-plus no-print"
      onClick={onToggle}
      title={`Aggiungi commento o istruzione per ${scopeTitle}`}
      style={{
        width: 22,
        height: 22,
        minWidth: 22,
        background: isOpen ? "var(--pd-accent)" : "var(--pd-primary)",
        color: "#ffffff",
        border: "none",
        borderRadius: 4,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        fontSize: 16,
        fontWeight: 700,
        lineHeight: 1,
        boxShadow: isOpen ? "0 0 0 2px var(--pd-accent-soft)" : "none",
        transition: "all 0.15s ease",
      }}
    >
      {isOpen ? "−" : "+"}
    </button>
  );
}

function AntigravitySectionCommentBox({
  scopeKey,
  scopeTitle,
  contextSnippet,
  caseId,
  clientName,
  onClose,
  onCommentAdded,
}) {
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);

  const handleAddComment = async () => {
    if (!comment.trim()) {
      setError("Inserisci un commento o istruzione.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await learnStudioRule({
        case_id: caseId,
        client_name: clientName,
        scope: scopeKey,
        scope_title: scopeTitle,
        user_comment: comment.trim(),
        current_context_text: typeof contextSnippet === "string" ? contextSnippet : JSON.stringify(contextSnippet || ""),
        author: "Responsabile Analisi",
      });
      setMsg("✓ Istruzione appresa da DossierLex!");
      setComment("");
      if (onCommentAdded) onCommentAdded(res);
      setTimeout(() => {
        setMsg(null);
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || "Errore durante il salvataggio.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="pd-antigravity-popover no-print"
      style={{
        background: "var(--pd-surface)",
        border: "1px solid var(--pd-border)",
        borderLeft: "4px solid var(--pd-primary)",
        borderRadius: "var(--pd-radius-lg)",
        padding: "12px 16px",
        boxShadow: "0 8px 24px rgba(45, 54, 40, 0.10)",
        maxWidth: 520,
        width: "100%",
        margin: "8px 0 16px",
        color: "var(--pd-text)",
        position: "relative",
        zIndex: 50,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>
          Commento per: <strong style={{ color: "var(--pd-primary)" }}>{scopeTitle}</strong>
        </span>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "none", border: "none", color: "var(--pd-text-muted)", cursor: "pointer", padding: 0 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
        </button>
      </div>

      {error && (
        <div style={{ background: "var(--pd-danger-bg)", border: "1px solid var(--pd-danger)", color: "var(--pd-danger)", padding: "6px 8px", borderRadius: 6, fontSize: 12, marginBottom: 8 }}>
          {error}
        </div>
      )}
      {msg && (
        <div style={{ background: "var(--pd-ok-bg)", border: "1px solid var(--pd-ok)", color: "var(--pd-ok)", padding: "6px 8px", borderRadius: 6, fontSize: 12, marginBottom: 8 }}>
          {msg}
        </div>
      )}

      <textarea
        rows={3}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Leave a comment..."
        style={{
          width: "100%",
          background: "var(--pd-surface-low)",
          border: "1px solid var(--pd-border)",
          borderRadius: "var(--pd-radius)",
          color: "var(--pd-text)",
          padding: "8px 10px",
          fontSize: 13,
          resize: "vertical",
          boxSizing: "border-box",
          outline: "none",
          marginBottom: 8,
        }}
      />

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8 }}>
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          style={{
            background: "transparent",
            color: "var(--pd-text-muted)",
            border: "none",
            fontSize: 13,
            cursor: "pointer",
            padding: "5px 10px",
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleAddComment}
          disabled={loading}
          style={{
            background: "var(--pd-accent)",
            color: "#ffffff",
            border: "none",
            borderRadius: "var(--pd-radius)",
            padding: "6px 16px",
            fontSize: 13,
            fontWeight: 600,
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            transition: "background 0.12s",
          }}
        >
          {loading ? "Salvataggio..." : "Add Comment"}
        </button>
      </div>
    </div>
  );
}

function ProceedModal({ isOpen, onClose, learnedCount, onPrint }) {
  if (!isOpen) return null;

  return (
    <div
      className="no-print"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(45, 54, 40, 0.45)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        style={{
          background: "var(--pd-surface)",
          border: "1px solid var(--pd-border)",
          borderTop: "4px solid var(--pd-primary)",
          borderRadius: "var(--pd-radius-lg)",
          maxWidth: 480,
          width: "100%",
          padding: 24,
          boxShadow: "0 20px 25px -5px rgba(45, 54, 40, 0.2)",
          color: "var(--pd-text)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--pd-primary)", display: "flex", alignItems: "center", gap: 8 }}>
            <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)", fontSize: 24 }}>
              verified
            </span>
            Report Aggiornato
          </h3>
          <button
            type="button"
            onClick={onClose}
            style={{ background: "none", border: "none", color: "var(--pd-text-muted)", cursor: "pointer", fontSize: 18 }}
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <p style={{ margin: "0 0 16px", fontSize: 14, color: "var(--pd-text-muted)", lineHeight: 1.55 }}>
          {learnedCount > 0 ? (
            <>
              Tutte le <strong>{learnedCount} istruzioni</strong> inserite sono state acquisite da DossierLex. I dati del report sono stati ricaricati automaticamente in base alle nuove regole apprese.
            </>
          ) : (
            <>
              Nessuna istruzione correttiva aggiunta: il report è convalidato. Puoi procedere direttamente alla stampa o esportazione in formato PDF.
            </>
          )}
        </p>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
          <button
            type="button"
            onClick={onClose}
            className="pd-btn pd-btn--secondary"
            style={{ minHeight: 36, padding: "6px 14px", fontSize: 13 }}
          >
            Chiudi
          </button>

          <button
            type="button"
            onClick={() => {
              onClose();
              onPrint();
            }}
            className="pd-btn pd-btn--primary"
            style={{ minHeight: 36, padding: "6px 16px", fontSize: 13 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>picture_as_pdf</span>
            Stampa / Esporta PDF
          </button>
        </div>
      </div>
    </div>
  );
}

export function FinalReport({ caseId, indicators, debtor, card, docs, edits, title, totalAer, patrimonio, crossAnalysis, goTab }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [printOrientation, setPrintOrientation] = useState("portrait");
  const [activeCommentScope, setActiveCommentScope] = useState(null);
  const [isReviewDropdownOpen, setIsReviewDropdownOpen] = useState(false);
  const [isProceedModalOpen, setIsProceedModalOpen] = useState(false);
  const [sessionLearnedCount, setSessionLearnedCount] = useState(0);

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

  const renderPlusButton = (scopeKey, scopeTitle) => {
    const isOpen = activeCommentScope === scopeKey;
    return (
      <AntigravitySectionPlus
        scopeKey={scopeKey}
        scopeTitle={scopeTitle}
        isOpen={isOpen}
        onToggle={() => setActiveCommentScope(isOpen ? null : scopeKey)}
      />
    );
  };

  const renderSectionCommentBox = (scopeKey, scopeTitle, contextSnippet = "") => {
    if (activeCommentScope !== scopeKey) return null;
    return (
      <AntigravitySectionCommentBox
        scopeKey={scopeKey}
        scopeTitle={scopeTitle}
        contextSnippet={contextSnippet}
        caseId={caseId}
        clientName={title}
        onClose={() => setActiveCommentScope(null)}
        onCommentAdded={() => {
          setSessionLearnedCount((c) => c + 1);
          fetchReport();
        }}
      />
    );
  };

  const h = report?.header || {};
  const c1 = report?.capitolo_1_premessa || {};
  const c2 = report?.capitolo_2_profilo || {};
  const c3 = report?.capitolo_3_analisi_economica || {};
  const c4 = report?.capitolo_4_dato_corrente || {};
  const c5 = report?.capitolo_5_indebitamento || {};
  const c6 = report?.capitolo_6_punti_verificare || [];
  const c7 = report?.capitolo_7_diagnosi_crisi || {};
  const c8 = report?.capitolo_8_patrimonio || {};
  const c9 = report?.capitolo_9_orientamento_risanamento || {};
  const c10 = report?.capitolo_10_documentazione || {};
  const c11 = report?.capitolo_11_conclusione || {};

  const t51 = c5.tabella_5_1 || {};
  const t52A = c5.tabella_5_2_ader || {};
  const t52C = c5.tabella_5_2_credito || [];
  const t53 = c5.tabella_5_3_sintesi || {};

  return (
    <div className="pd-grid">
      <style>{`
        @media print {
          @page {
            size: ${printOrientation === "landscape" ? "A4 landscape" : "A4 portrait"};
            margin: 8mm 10mm;
          }
          .no-print { display: none !important; }
          .pd-report-paper {
            box-shadow: none !important;
            border: none !important;
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
            background: transparent !important;
          }
          body {
            background: #fff !important;
            color: #000 !important;
            font-size: ${printOrientation === "landscape" ? "9pt" : "8pt"} !important;
          }
          .pd-chapter {
            page-break-inside: avoid;
            margin-bottom: 18pt !important;
          }
          .pd-table-wrap {
            overflow: visible !important;
            box-shadow: none !important;
          }
          table {
            page-break-inside: avoid;
            width: 100% !important;
            table-layout: auto !important;
            font-size: ${printOrientation === "landscape" ? "8.5pt" : "7.2pt"} !important;
          }
          .pd-table th, .pd-table td {
            padding: 2.5px 3.5px !important;
          }
          .sticky-col {
            position: static !important;
            box-shadow: none !important;
          }
          .pd-review-btn, .pd-review-box, .pd-general-review-card, .pd-antigravity-plus, .pd-antigravity-popover {
            display: none !important;
          }
          h1, h2, h3, h4 {
            page-break-after: avoid;
          }
        }
        .pd-antigravity-plus:hover {
          background: var(--pd-accent) !important;
          transform: scale(1.08);
        }
        .sticky-col {
          position: sticky;
          left: 0;
          background: #fff;
          z-index: 2;
          box-shadow: 2px 0 4px rgba(0,0,0,0.06);
        }
        .pd-table-compact th, .pd-table-compact td {
          padding: 6px 8px;
        }
        .pd-chapter {
          margin-bottom: 34px;
        }
        .pd-chapter-title {
          font-size: 18px;
          font-weight: 700;
          color: var(--pd-primary);
          border-bottom: 1.5px solid var(--pd-border);
          padding-bottom: 8px;
          margin-bottom: 14px;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .pd-chapter-title .num {
          background: var(--pd-primary);
          color: #fff;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          font-weight: 700;
        }
        .pd-report-text {
          font-size: 14px;
          line-height: 1.65;
          color: var(--pd-text);
          margin-bottom: 12px;
          text-align: justify;
        }
        .pd-subchapter-title {
          font-size: 15px;
          font-weight: 700;
          color: var(--pd-text);
          margin: 18px 0 8px;
        }
        .pd-highlight-box {
          border-left: 4px solid var(--pd-primary);
          background: var(--pd-surface-low);
          padding: 12px 16px;
          border-radius: 0 6px 6px 0;
          margin: 12px 0 18px;
          font-size: 13.5px;
          line-height: 1.55;
        }
      `}</style>

      {/* TOOLBAR NO-PRINT */}
      <div className="pd-page-head no-print" style={{ marginBottom: 18 }}>
        <div>
          <h2 className="pd-h2">Report Finale — Preanalisi ex CCII</h2>
          <p>Dossier completo conforme al template dello studio legale Avv. Aurelio Bentivegna.</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* REVIEW DROPDOWN (STILE DOSSIERLEX) */}
          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={() => setIsReviewDropdownOpen((v) => !v)}
              title="Aggiungi istruzioni generali per l'intero report"
              style={{
                background: isReviewDropdownOpen ? "var(--pd-primary-600)" : "var(--pd-primary)",
                color: "#ffffff",
                border: "1px solid var(--pd-primary-600)",
                borderRadius: "var(--pd-radius)",
                padding: "7px 14px",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                boxShadow: "var(--pd-shadow)",
                transition: "all 0.15s ease",
              }}
            >
              <span>Review</span>
              <span style={{ fontSize: 11, opacity: 0.85 }}>▼</span>
              {sessionLearnedCount > 0 && (
                <span
                  style={{
                    background: "var(--pd-accent)",
                    color: "#ffffff",
                    borderRadius: "50%",
                    fontSize: 10.5,
                    fontWeight: 700,
                    width: 18,
                    height: 18,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginLeft: 2,
                  }}
                >
                  {sessionLearnedCount}
                </span>
              )}
            </button>

            <AntigravityReviewDropdown
              isOpen={isReviewDropdownOpen}
              onClose={() => setIsReviewDropdownOpen(false)}
              caseId={caseId}
              clientName={title}
              onInstructionSaved={() => {
                setSessionLearnedCount((c) => c + 1);
                fetchReport();
              }}
            />
          </div>

          {/* PROCEED BUTTON (STILE DOSSIERLEX) */}
          <button
            type="button"
            onClick={() => {
              fetchReport();
              setIsProceedModalOpen(true);
            }}
            disabled={loading}
            title="Convalida le modifiche, ricarica i dati con le nuove regole e procedi con la stampa"
            style={{
              background: "var(--pd-accent)",
              color: "#ffffff",
              border: "none",
              borderRadius: "var(--pd-radius)",
              padding: "7px 18px",
              fontSize: 13,
              fontWeight: 600,
              cursor: loading ? "default" : "pointer",
              opacity: loading ? 0.7 : 1,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              boxShadow: "var(--pd-shadow)",
              transition: "all 0.15s ease",
            }}
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>sync</span>
                <span>Ricarica...</span>
              </>
            ) : (
              <span>Proceed</span>
            )}
          </button>

          <span style={{ height: 20, width: 1, background: "var(--pd-border)", margin: "0 4px" }} />

          <button
            type="button"
            className="pd-btn pd-btn--secondary"
            onClick={() => setPrintOrientation((prev) => (prev === "portrait" ? "landscape" : "portrait"))}
            title="Alterna formato del PDF tra Verticale e Orizzontale"
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              {printOrientation === "landscape" ? "stay_primary_landscape" : "stay_primary_portrait"}
            </span>
            Formato: {printOrientation === "landscape" ? "Orizzontale" : "Verticale"}
          </button>

          <button
            type="button"
            className="pd-btn pd-btn--secondary"
            onClick={() => handleExportPdf("inline")}
            title="Visualizza il PDF vettoriale in una nuova scheda del browser"
          >
            <span className="material-symbols-outlined" aria-hidden="true">open_in_new</span>
            Apri PDF
          </button>

          <button
            type="button"
            className="pd-btn pd-btn--primary"
            onClick={() => handleExportPdf("download")}
            title="Scarica il file PDF ufficiale generato da DossierLex"
          >
            <span className="material-symbols-outlined" aria-hidden="true">picture_as_pdf</span>
            Esporta PDF
          </button>
        </div>
      </div>

      <article className="pd-report-paper" style={{ padding: "36px 44px", background: "#fff", maxWidth: 1140, margin: "0 auto", boxShadow: "var(--pd-shadow-md)", borderRadius: 8 }}>
        {/* HEADER FORMALE DEL TEMPLATE */}
        <header style={{ borderBottom: "2px solid var(--pd-primary)", paddingBottom: 24, marginBottom: 36 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: 1.5, fontWeight: 700, color: "var(--pd-primary)" }}>
                DossierLex — Crisi d'Impresa e Sovraindebitamento
              </div>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--pd-text-muted)" }}>
                Studio Legale Avv. Aurelio Bentivegna & Partners
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <span className="pd-badge pd-badge--danger" style={{ fontSize: 11, fontWeight: 700 }}>
                {h.riservatezza || "DOCUMENTO DI LAVORO RISERVATO"}
              </span>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--pd-text-muted)" }}>
                Data bozza: {h.data_bozza || new Date().toLocaleDateString("it-IT")}
              </p>
            </div>
          </div>

          <h1 style={{ fontSize: 24, fontWeight: 800, color: "var(--pd-primary)", margin: "0 0 6px", lineHeight: 1.25 }}>
            {h.titolo || "PREANALISI ECONOMICO-FINANZIARIA E IPOTESI DI RISANAMENTO"}
          </h1>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--pd-text)", margin: "0 0 6px" }}>
            {h.cliente || title} {h.forma_giuridica ? `(${h.forma_giuridica})` : ""}
          </div>
          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "var(--pd-text-muted)" }}>
            {h.sottotitolo || "Composizione Negoziata della Crisi — Ipotesi preliminare di proposta al ceto creditorio"}
          </p>
        </header>

        {/* 1. PREMESSA E FINALITÀ */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">1</span>
              Premessa e finalità della preanalisi
            </div>
            {renderPlusButton("cap_1", "1. Premessa e finalità")}
          </div>
          {renderSectionCommentBox("cap_1", "1. Premessa e finalità", c1.scopo || "")}
          <p className="pd-report-text">
            {c1.scopo || `La presente preanalisi ha lo scopo di fotografare, sulla base della documentazione allo stato disponibile, la situazione economica, patrimoniale e debitoria di ${title}, al fine di comprendere se sussistano i presupposti per un percorso di risanamento e quale, tra gli strumenti previsti dal Codice della Crisi d'Impresa e dell'Insolvenza (CCII), appaia in prima battuta più coerente con il caso specifico.`}
          </p>
          <p className="pd-report-text">
            Il presente documento è stato predisposto sulla base dei seguenti documenti effettivamente acquisiti ed esaminati:
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>Documento / Fonte</th><th>Tipologia rilevata</th><th>Data / Riferimento</th></tr></thead>
              <tbody>
                {(c1.documenti_utilizzati || []).map((doc, idx) => (
                  <tr key={idx}>
                    <td><strong>{doc.titolo}</strong></td>
                    <td>{doc.tipo}</td>
                    <td style={{ fontSize: 13 }}>{doc.data}</td>
                  </tr>
                ))}
                {(c1.documenti_utilizzati || []).length === 0 && (
                  <tr><td colSpan={3}>Nessun documento strutturato registrato.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="pd-highlight-box">
            <strong>Riserva metodologica:</strong> La conclusione della presente analisi deve essere intesa come giudizio preliminare, destinato a essere verificato e sviluppato in un piano industriale e in un piano di risanamento definitivi solo dopo l'acquisizione dei dati ancora mancanti (elencati al par. 10) e il chiarimento dei punti aperti evidenziati nel corso del documento (par. 6).
          </div>
          <p className="pd-report-text" style={{ fontStyle: "italic", color: "var(--pd-text-muted)" }}>
            {c1.flusso_annuo_destinabile || "La preanalisi si arresta allo stato al giudizio di fattibilità e all'indicazione dello strumento più coerente, senza formulare una proposta quantificata ai creditori, in attesa dell'indicazione del flusso finanziario annuo da parte del cliente."}
          </p>
        </section>

        {/* 2. PROFILO DELL'IMPRESA E NATURA DELLA CRISI */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">2</span>
              Profilo dell'impresa e natura della crisi
            </div>
            {renderPlusButton("cap_2", "2. Profilo dell'impresa e soci")}
          </div>
          {renderSectionCommentBox("cap_2", "2. Profilo dell'impresa e soci", c2.denominazione || title)}
          <div className="pd-grid pd-grid--2" style={{ marginBottom: 16 }}>
            <ReportField label="Denominazione" value={c2.denominazione || title} />
            <ReportField label="Forma giuridica" value={c2.forma_giuridica || "SRL"} />
            <ReportField label="Codice Fiscale / P.IVA" value={c2.cf_piva || "—"} />
            <ReportField label="Numero REA" value={c2.rea || "—"} />
            <ReportField label="Sede legale" value={c2.sede_legale || "—"} />
            <ReportField label="Capitale sociale deliberato" value={eurFull(c2.capitale_sociale)} />
            <ReportField label="Codice ATECO" value={c2.codice_ateco || "—"} />
            <ReportField label="Attività prevalente" value={c2.attivita_prevalente || "—"} />
          </div>

          <h3 className="pd-subchapter-title">Composizione societaria e titolari di cariche</h3>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>Nominativo</th><th>Quota %</th><th>Ruolo / Carica</th><th>Garanzie prestate</th></tr></thead>
              <tbody>
                {(c2.soci || []).map((s, idx) => (
                  <tr key={idx}>
                    <td><strong>{s.nome}</strong></td>
                    <td className="pd-num">{s.quota_pct ? `${s.quota_pct}%` : "—"}</td>
                    <td>{s.ruolo}</td>
                    <td>{s.garante ? <span className="pd-badge pd-badge--warn">Fideiussore personale</span> : "Nessuna segnalata"}</td>
                  </tr>
                ))}
                {(c2.soci || []).length === 0 && (
                  <tr><td colSpan={4}>Nessun socio o amministratore censito in visura.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <h3 className="pd-subchapter-title">Diagnosi preliminare sulla natura della crisi</h3>
          <p className="pd-report-text">
            {c2.natura_crisi || "L'analisi evidenzia una crisi di natura prevalentemente finanziaria e debitoria generata dal peso delle passività pregresse erariali e bancarie, a fronte di una gestione caratteristica storicamente redditizia ma oggi rallentata."}
          </p>
        </section>

        {/* 3. ANALISI ECONOMICA PLURIENNALE */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">3</span>
              Analisi economica pluriennale
            </div>
            {renderPlusButton("cap_3", "3. Analisi economica pluriennale")}
          </div>
          {renderSectionCommentBox("cap_3", "3. Analisi economica pluriennale", JSON.stringify(c3.esercizi || []))}
          <p className="pd-report-text">
            I risultati economici degli ultimi tre esercizi approvati evidenziano l'andamento della produzione, dei costi operativi e della marginalità (MOL):
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(270px, 1fr))", gap: 16, marginBottom: 18 }}>
            {(c3.esercizi || []).map((ex, idx) => (
              <div key={idx} style={{ background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
                <h4 style={{ margin: "0 0 10px", fontSize: 15, color: "var(--pd-primary)", borderBottom: "1px solid var(--pd-border)", paddingBottom: 6 }}>
                  3.{idx + 1} Esercizio {ex.anno} ({ex.data_chiusura})
                </h4>
                <table className="pd-table" style={{ fontSize: 13 }}>
                  <tbody>
                    <tr><td>Ricavi vendite/prest. (A1)</td><td className="pd-num">{eurFull(ex.ricavi_a1)}</td></tr>
                    <tr><td>Altri ricavi (A2-A5)</td><td className="pd-num">{eurFull(ex.altri_ricavi_a2_a5)}</td></tr>
                    <tr><td><strong>Valore produzione (A)</strong></td><td className="pd-num"><strong>{eurFull(ex.valore_produzione_a)}</strong></td></tr>
                    <tr><td>Costi produzione (B)</td><td className="pd-num">{eurFull(ex.costi_produzione_b)}</td></tr>
                    <tr style={{ background: "rgba(37, 99, 235, 0.06)" }}>
                      <td><strong>MOL (A-B+Amm.)</strong></td>
                      <td className="pd-num" style={{ color: ex.mol >= 0 ? "var(--pd-ok)" : "var(--pd-danger)", fontWeight: 700 }}>
                        {eurFull(ex.mol)} ({ex.mol_pct}%)
                      </td>
                    </tr>
                    <tr>
                      <td><strong>Utile / Perdita d'esercizio</strong></td>
                      <td className="pd-num" style={{ color: ex.utile_perdita >= 0 ? "var(--pd-ok)" : "var(--pd-danger)", fontWeight: 700 }}>
                        {eurFull(ex.utile_perdita)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ))}
          </div>

          <div className="pd-highlight-box">
            <strong>Commento sul triennio:</strong> {c3.commento_periodo}
          </div>
          <p className="pd-report-text">
            <strong>Riscontro con dichiarazioni fiscali:</strong> {c3.riscontro_dichiarazioni_redditi}
          </p>
          {(c3.anomalie_contabili || []).length > 0 && (
            <div style={{ marginTop: 10 }}>
              <strong style={{ fontSize: 13, textTransform: "uppercase", color: "var(--pd-warn)" }}>Anomalie contabili riscontrate da verificare:</strong>
              <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 13, color: "var(--pd-text)" }}>
                {c3.anomalie_contabili.map((an, idx) => <li key={idx} style={{ marginBottom: 4 }}>{an}</li>)}
              </ul>
            </div>
          )}
        </section>

        {/* 4. IL DATO DELL'ANNO CORRENTE E PRUDENZA */}
        {c4.dato && (
          <section className="pd-chapter">
            <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="num">4</span>
                Il dato {c4.dato.periodo?.slice(0, 4) || "infrannuale"} e la necessità di prudenza
              </div>
              {renderPlusButton("cap_4", "4. Il dato dell'anno corrente")}
            </div>
            {renderSectionCommentBox("cap_4", "4. Il dato dell'anno corrente", JSON.stringify(c4.dato || {}))}
            <div className="pd-table-wrap" style={{ maxWidth: 540, marginBottom: 14 }}>
              <table className="pd-table">
                <thead><tr><th>Voce Conto Economico ({c4.dato.periodo})</th><th className="pd-num">Importo</th></tr></thead>
                <tbody>
                  <tr><td>Ricavi vendite/prestazioni (periodo)</td><td className="pd-num">{eurFull(c4.dato.ricavi_a1)}</td></tr>
                  <tr><td>Altri ricavi e proventi (periodo)</td><td className="pd-num">{eurFull(c4.dato.altri_ricavi_a2_a5)}</td></tr>
                  <tr><td><strong>Valore della produzione (periodo)</strong></td><td className="pd-num"><strong>{eurFull(c4.dato.valore_produzione_a)}</strong></td></tr>
                  <tr><td>Costi della produzione (periodo)</td><td className="pd-num">{eurFull(c4.dato.costi_produzione_b)}</td></tr>
                  <tr><td>Oneri finanziari di periodo</td><td className="pd-num" style={{ color: "var(--pd-danger)" }}>{eurFull(c4.dato.oneri_finanziari)}</td></tr>
                  <tr style={{ background: "rgba(239, 68, 68, 0.06)" }}>
                    <td><strong>MOL del periodo</strong></td>
                    <td className="pd-num" style={{ color: c4.dato.mol >= 0 ? "var(--pd-ok)" : "var(--pd-danger)", fontWeight: 700 }}>{eurFull(c4.dato.mol)}</td>
                  </tr>
                  <tr style={{ background: "rgba(239, 68, 68, 0.08)" }}>
                    <td><strong>Utile / Perdita del periodo</strong></td>
                    <td className="pd-num" style={{ color: c4.dato.utile_perdita >= 0 ? "var(--pd-ok)" : "var(--pd-danger)", fontWeight: 800 }}>{eurFull(c4.dato.utile_perdita)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="pd-highlight-box" style={{ borderLeftColor: "var(--pd-warn)" }}>
              <strong>Avvertenza di prudenza:</strong> {c4.prudenza}
            </div>
          </section>
        )}

        {/* 5. ANALISI DELL'INDEBITAMENTO */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">5</span>
              Analisi dell'indebitamento
            </div>
            {renderPlusButton("cap_5", "5. Analisi dell'indebitamento")}
          </div>
          {renderSectionCommentBox("cap_5", "5. Analisi dell'indebitamento", "Ponte debitorio complessivo")}
          <p className="pd-report-text">
            L'indagine procede in tre passaggi: i debiti risultanti dalla contabilità sociale (5.1), i debiti censiti dalle banche dati esterne (5.2) e la stima di sintesi della massa debitoria senza duplicazioni (5.3).
          </p>

          {/* 5.1 DEBITI DA BILANCIO DINAMICA EFFETTIVA */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20, marginBottom: 6 }}>
            <h3 className="pd-subchapter-title" style={{ margin: 0 }}>5.1 I debiti risultanti dai bilanci (struttura effettiva da bilancio)</h3>
            {renderPlusButton("cap_5_1", "5.1 Debiti risultanti dai bilanci")}
          </div>
          {renderSectionCommentBox("cap_5_1", "5.1 Debiti risultanti dai bilanci", JSON.stringify(t51.righe || []))}
          <p className="pd-report-text" style={{ fontSize: 13, color: "var(--pd-text-muted)" }}>
            La tabella che segue è strutturata a partire dalle voci di debito effettive estratte dai bilanci e dalle situazioni contabili disponibili. La variazione è calcolata tra la situazione più recente ({t51.situazione_recente}) e l'ultimo bilancio approvato ({t51.base_confronto}). Restano rigorosamente esclusi patrimonio netto, fondi ammortamento e risconti passivi.
          </p>

          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead>
                <tr>
                  <th className="sticky-col" style={{ minWidth: 200 }}>Voce di debito effettiva</th>
                  {(t51.colonne || []).map((col) => (
                    <th key={col.key} className="pd-num" style={{ whiteSpace: "nowrap", minWidth: 92 }}>
                      <div style={{ fontWeight: 700, fontSize: "12px", color: col.is_interim ? "var(--pd-primary)" : "inherit" }}>
                        {col.title || col.label}
                      </div>
                      <div style={{ fontSize: "10px", color: "var(--pd-text-muted)", fontWeight: 400, marginTop: 1 }}>
                        {col.date || ""}
                      </div>
                    </th>
                  ))}
                  <th className="pd-num" style={{ color: "var(--pd-primary)", minWidth: 98, whiteSpace: "nowrap" }}>
                    <div style={{ fontWeight: 700, fontSize: "12px" }}>Variazione</div>
                    <div style={{ fontSize: "10px", color: "var(--pd-text-muted)", fontWeight: 400, marginTop: 1 }}>
                      {t51.var_subtitle || "Netta"}
                    </div>
                  </th>
                  <th style={{ minWidth: 125, whiteSpace: "nowrap" }}>Note</th>
                </tr>
              </thead>
              <tbody>
                {(t51.righe || []).map((r, idx) => (
                  <tr key={idx}>
                    <td className="sticky-col"><strong>{r.voce}</strong></td>
                    {(t51.colonne || []).map((col) => (
                      <td key={col.key} className="pd-num" style={{ whiteSpace: "nowrap" }}>
                        {eurFull(r.valori?.[col.key])}
                      </td>
                    ))}
                    <td className="pd-num" style={{ whiteSpace: "nowrap", fontWeight: 700, color: r.variazione > 0 ? "var(--pd-danger)" : r.variazione < 0 ? "var(--pd-ok)" : "inherit" }}>
                      {r.variazione > 0 ? `+${eurFull(r.variazione)}` : eurFull(r.variazione)}
                    </td>
                    <td style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                      {r.note ? (
                        <span style={{ background: "rgba(37,99,235,0.08)", color: "var(--pd-primary)", padding: "2px 6px", borderRadius: 4, fontWeight: 600, fontSize: 11, display: "inline-block" }}>
                          {r.note}
                        </span>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
                {/* RIGA TOTALE DEBITI */}
                <tr style={{ background: "var(--pd-surface-low)", fontWeight: 800, borderTop: "2px solid var(--pd-border)" }}>
                  <td className="sticky-col" style={{ background: "var(--pd-surface-low)" }}><strong>TOTALE DEBITI DA BILANCIO</strong></td>
                  {(t51.colonne || []).map((col) => (
                    <td key={col.key} className="pd-num" style={{ fontWeight: 800, whiteSpace: "nowrap" }}>
                      {eurFull(t51.totali?.[col.key])}
                    </td>
                  ))}
                  <td className="pd-num" style={{ fontWeight: 800, whiteSpace: "nowrap", color: t51.totale_variazione > 0 ? "var(--pd-danger)" : "var(--pd-ok)" }}>
                    {t51.totale_variazione > 0 ? `+${eurFull(t51.totale_variazione)}` : eurFull(t51.totale_variazione)}
                  </td>
                  <td style={{ fontSize: 11, whiteSpace: "nowrap" }}>Escluso PN e risconti</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="pd-report-text">
            <strong>Commento al ponte debitorio:</strong> {c5.commento_5_1}
          </p>

          {/* 5.2 BANCHE DATI ESTERNE */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 8 }}>
            <h3 className="pd-subchapter-title" style={{ margin: 0 }}>5.2 I debiti risultanti dalle banche dati esterne</h3>
            {renderPlusButton("cap_5_2", "5.2 Banche dati AdER e Centrale Rischi")}
          </div>
          {renderSectionCommentBox("cap_5_2", "5.2 Banche dati AdER e Centrale Rischi", JSON.stringify(t52A))}
          <p className="pd-report-text">
            <strong>Posizione Agenzia delle Entrate-Riscossione (AdER):</strong>
          </p>
          <div className="pd-table-wrap" style={{ maxWidth: 540, marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>Voce estratto AdER</th><th className="pd-num">Importo</th></tr></thead>
              <tbody>
                <tr><td>Carico originariamente affidato</td><td className="pd-num">{eurFull(t52A.carico_affidato)}</td></tr>
                <tr><td>Sgravi</td><td className="pd-num">{eurFull(t52A.sgravi)}</td></tr>
                <tr><td>Pagamenti effettuati (rate rottamazione)</td><td className="pd-num" style={{ color: "var(--pd-ok)" }}>{eurFull(t52A.pagamenti_effettuati)}</td></tr>
                <tr><td>Stralcio / definizione agevolata</td><td className="pd-num">{eurFull(t52A.stralcio_definizione)}</td></tr>
                <tr><td>Residuo quota capitale</td><td className="pd-num">{eurFull(t52A.residuo_capitale)}</td></tr>
                <tr><td>Interessi e somme aggiuntive</td><td className="pd-num">{eurFull(t52A.interessi_sanzioni)}</td></tr>
                <tr style={{ background: "rgba(239, 68, 68, 0.08)", fontWeight: 800 }}>
                  <td><strong>TOTALE RESIDUO ADER</strong></td>
                  <td className="pd-num" style={{ color: "var(--pd-danger)", fontWeight: 800 }}>{eurFull(t52A.totale_residuo)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="pd-report-text">
            <strong>Banche dati creditizie (Centrale Rischi Banca d'Italia, CTC, CRIF):</strong>
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead>
                <tr>
                  <th>Fonte e data</th>
                  <th>Intermediario</th>
                  <th>Rapporto</th>
                  <th className="pd-num">Utilizzato / Residuo</th>
                  <th>Rata</th>
                  <th>Note e anti-duplicazione</th>
                </tr>
              </thead>
              <tbody>
                {t52C.map((crRow, idx) => (
                  <tr key={idx}>
                    <td style={{ fontSize: 13 }}>{crRow.fonte}</td>
                    <td><strong>{crRow.intermediario}</strong></td>
                    <td>{crRow.rapporto}</td>
                    <td className="pd-num"><strong>{eurFull(crRow.utilizzato)}</strong></td>
                    <td>{crRow.rata}</td>
                    <td style={{ fontSize: 12, color: "var(--pd-primary)" }}>{crRow.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 5.3 SINTESI MASSA DEBITORIA SENZA DUPLICAZIONI */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 8 }}>
            <h3 className="pd-subchapter-title" style={{ margin: 0 }}>5.3 Sintesi: stima della massa debitoria complessiva (senza duplicazioni)</h3>
            {renderPlusButton("cap_5_3", "5.3 Stima sintetica massa debitoria")}
          </div>
          {renderSectionCommentBox("cap_5_3", "5.3 Stima sintetica massa debitoria", JSON.stringify(t53.righe || []))}
          <p className="pd-report-text">
            La stima che segue è costruita incrociando le banche dati esterne (par. 5.2) con i dati di bilancio (par. 5.1). Ogni debito è computato una sola volta evitando duplicazioni tra ruoli esattoriali e debiti contabili, e tra banche dati creditizie sullo stesso rapporto:
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead>
                <tr>
                  <th>Categoria di debito</th>
                  <th>Fonte utilizzata</th>
                  <th className="pd-num">Importo stimato</th>
                  <th className="pd-num">Dato da bilancio (5.1)</th>
                  <th>Note / incertezza</th>
                </tr>
              </thead>
              <tbody>
                {(t53.righe || []).map((sRow, idx) => (
                  <tr key={idx}>
                    <td><strong>{sRow.categoria}</strong></td>
                    <td style={{ fontSize: 13 }}>{sRow.fonte}</td>
                    <td className="pd-num"><strong>{eurFull(sRow.importo_stimato)}</strong></td>
                    <td className="pd-num" style={{ color: "var(--pd-text-muted)" }}>{eurFull(sRow.dato_bilancio)}</td>
                    <td style={{ fontSize: 12 }}>{sRow.note}</td>
                  </tr>
                ))}
                <tr style={{ background: "var(--pd-surface-low)", fontWeight: 800, borderTop: "2px solid var(--pd-border)" }}>
                  <td><strong>TOTALE MASSA DEBITORIA INDICATIVA</strong></td>
                  <td>Consolidamento trasversale</td>
                  <td className="pd-num" style={{ color: "var(--pd-danger)", fontWeight: 800, fontSize: 15 }}>
                    {eurFull(t53.totale_stimato)}
                  </td>
                  <td className="pd-num" style={{ fontWeight: 800 }}>
                    {eurFull(t53.totale_bilancio)}
                  </td>
                  <td style={{ fontSize: 12 }}>Massa debitoria netta stimata</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="pd-highlight-box">
            <strong>Cautele e riserve metodologiche:</strong> {c5.cautele_sintesi}
          </div>
        </section>

        {/* 6. PUNTI DA VERIFICARE */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">6</span>
              Punti da verificare
            </div>
            {renderPlusButton("cap_6", "6. Punti da verificare")}
          </div>
          {renderSectionCommentBox("cap_6", "6. Punti da verificare", JSON.stringify(c6 || []))}
          <p className="pd-report-text">
            Punti emersi dai documenti che non risultano chiariti e che vanno sciolti prima di consolidare il piano industriale e di risanamento:
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>Gravità</th><th>Descrizione discrepanza / anomalia</th><th>Fonti a confronto</th><th>Cosa occorre chiarire / verificare</th></tr></thead>
              <tbody>
                {c6.map((pt, idx) => (
                  <tr key={idx}>
                    <td><span className={`pd-badge pd-badge--${pt.gravita === "SOSTANZIALE" || pt.gravita === "GRAVE" ? "danger" : "warn"}`}>{pt.gravita || "VERIFICA"}</span></td>
                    <td><strong>{pt.descrizione}</strong></td>
                    <td style={{ fontSize: 13 }}>{pt.documenti}</td>
                    <td style={{ fontSize: 13, color: "var(--pd-primary)", fontWeight: 600 }}>{pt.azione}</td>
                  </tr>
                ))}
                {c6.length === 0 && (
                  <tr><td colSpan={4}>Nessuna anomalia contabile o incongruenza documentale aperta.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* 7. DIAGNOSI PRELIMINARE DELLA CRISI */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">7</span>
              Diagnosi preliminare della crisi
            </div>
            {renderPlusButton("cap_7", "7. Diagnosi preliminare della crisi")}
          </div>
          {renderSectionCommentBox("cap_7", "7. Diagnosi preliminare della crisi", c7.diagnosi || c7.sintesi_vitalita || "")}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, marginBottom: 16 }}>
            <div style={{ background: "rgba(16, 185, 129, 0.06)", border: "1px solid var(--pd-ok)", borderRadius: 8, padding: 14 }}>
              <h4 style={{ margin: "0 0 8px", color: "var(--pd-ok)", fontSize: 14, textTransform: "uppercase" }}>
                ✓ Elementi favorevoli al risanamento
              </h4>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.55 }}>
                {(c7.elementi_favorevoli || []).map((el, idx) => <li key={idx} style={{ marginBottom: 4 }}>{el}</li>)}
              </ul>
            </div>
            <div style={{ background: "rgba(239, 68, 68, 0.06)", border: "1px solid var(--pd-danger)", borderRadius: 8, padding: 14 }}>
              <h4 style={{ margin: "0 0 8px", color: "var(--pd-danger)", fontSize: 14, textTransform: "uppercase" }}>
                ⚠️ Principale criticità
              </h4>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>
                {c7.principale_criticita}
              </p>
            </div>
          </div>
          <div className="pd-highlight-box">
            <strong>Giudizio di vitalità:</strong> {c7.sintesi_vitalita}
          </div>
        </section>

        {/* 8. PATRIMONIO */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">8</span>
              Patrimonio
            </div>
            {renderPlusButton("cap_8", "8. Patrimonio e garanzie")}
          </div>
          {renderSectionCommentBox("cap_8", "8. Patrimonio e garanzie", JSON.stringify(c8 || {}))}

          <h3 className="pd-subchapter-title">8.1 Patrimonio immobiliare</h3>
          <p className="pd-report-text">
            Dati desunti da visura catastale aggiornata. I valori indicati costituiscono una stima preliminare e non sostituiscono una perizia giurata:
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>N.</th><th>Comune / Indirizzo</th><th>Identificativo Catastale</th><th>Cat.</th><th className="pd-num">Rendita</th><th className="pd-num">Valore Catastale</th><th className="pd-num">Fascia Valore Stima</th></tr></thead>
              <tbody>
                {(c8.immobili || []).map((imm) => (
                  <tr key={imm.numero}>
                    <td>{imm.numero}</td>
                    <td>{imm.comune} — {imm.indirizzo}</td>
                    <td style={{ fontSize: 12 }}>{imm.catasto}</td>
                    <td><span className="pd-badge pd-badge--neutral">{imm.categoria}</span></td>
                    <td className="pd-num">{eurFull(imm.rendita)}</td>
                    <td className="pd-num"><strong>{eurFull(imm.valore_catastale)}</strong></td>
                    <td className="pd-num">{eurFull(imm.stima_fascia)}</td>
                  </tr>
                ))}
                <tr style={{ background: "var(--pd-surface-low)", fontWeight: 800 }}>
                  <td colSpan={5}><strong>TOTALE VALORE CATASTALE RIVALUTATO</strong></td>
                  <td className="pd-num" style={{ color: "var(--pd-primary)", fontWeight: 800 }}>{eurFull(c8.totale_valore_catastale)}</td>
                  <td className="pd-num">—</td>
                </tr>
                {(c8.immobili || []).length === 0 && (
                  <tr><td colSpan={7}>Nessun immobile censito in visura catastale.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <h3 className="pd-subchapter-title">8.2 Patrimonio mobiliare (autoveicoli)</h3>
          <div className="pd-table-wrap" style={{ marginBottom: 14 }}>
            <table className="pd-table">
              <thead><tr><th>Tipo autoveicolo / mezzo</th><th>Anno immatricolazione</th><th>Targa</th><th className="pd-num">Valore stimato</th></tr></thead>
              <tbody>
                {(c8.veicoli || []).map((v, idx) => (
                  <tr key={idx}>
                    <td><strong>{v.tipo}</strong></td>
                    <td>{v.anno}</td>
                    <td><span className="pd-badge pd-badge--neutral">{v.targa}</span></td>
                    <td className="pd-num">{eurFull(v.valore)}</td>
                  </tr>
                ))}
                {(c8.veicoli || []).length === 0 && (
                  <tr><td colSpan={4}>Nessun veicolo aziendale registrato al PRA o dichiarato.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <h3 className="pd-subchapter-title">8.3 Immobilizzazioni materiali e cespiti di bilancio</h3>
          <div className="pd-grid pd-grid--2" style={{ marginBottom: 14 }}>
            <ReportField label="Valore netto contabile cespiti (bilancio)" value={eurFull(c8.immobilizzazioni_materiali?.valore_netto_bilancio)} />
            <ReportField label="Costo storico stimato" value={eurFull(c8.immobilizzazioni_materiali?.costo_storico_stimato)} />
          </div>

          <h3 className="pd-subchapter-title">8.4 Esposizione personale del socio/garante</h3>
          <div className="pd-table-wrap">
            <table className="pd-table">
              <thead><tr><th>Soggetto garante</th><th>Garanzia prestata / Beneficiario</th><th className="pd-num">Importo</th></tr></thead>
              <tbody>
                {(c8.esposizione_personale_soci || []).map((esp, idx) => (
                  <tr key={idx}>
                    <td><strong>{esp.socio}</strong></td>
                    <td>{esp.garanzia}</td>
                    <td className="pd-num"><strong>{esp.importo}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 9. ORIENTAMENTO VERSO UNA SOLUZIONE DI RISANAMENTO */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">9</span>
              Orientamento verso una soluzione di risanamento ex CCII
            </div>
            {renderPlusButton("cap_9", "9. Orientamento per il risanamento CCII")}
          </div>
          {renderSectionCommentBox("cap_9", "9. Orientamento per il risanamento CCII", c9.proposta_coerente || "")}
          <p className="pd-report-text">
            Valutazione comparativa degli strumenti previsti dal Codice della Crisi d'Impresa e dell'Insolvenza alla luce delle caratteristiche dimensionali, debitorie e patrimoniali dell'impresa:
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, marginBottom: 18 }}>
            {(c9.scenari || []).map((sc, idx) => (
              <div key={idx} style={{ background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <strong style={{ fontSize: 14, color: "var(--pd-primary)" }}>{sc.scenario}</strong>
                  <span className={`pd-badge pd-badge--${sc.fattibilita === "ALTA" ? "ok" : sc.fattibilita === "MEDIA" ? "warn" : "danger"}`}>
                    {sc.fattibilita}
                  </span>
                </div>
                <p style={{ margin: "6px 0", fontSize: 12.5, lineHeight: 1.5, color: "var(--pd-text)" }}>{sc.motivazione}</p>
                {sc.dati_chiave && <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "var(--pd-text-muted)" }}><strong>Dati chiave:</strong> {sc.dati_chiave}</p>}
              </div>
            ))}
          </div>

          <div className="pd-highlight-box">
            <h4 style={{ margin: "0 0 6px", fontSize: 15, color: "var(--pd-primary)" }}>
              👉 Strumento più coerente in prima battuta: {c9.proposta_coerente}
            </h4>
            <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6 }}>{c9.motivazione}</p>
          </div>
          <div style={{ marginTop: 10 }}>
            <strong style={{ fontSize: 13, textTransform: "uppercase", color: "var(--pd-text-muted)" }}>Condizioni e riserve a cui l'indicazione è subordinata:</strong>
            <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 13, color: "var(--pd-text)" }}>
              {(c9.condizioni || []).map((cd, idx) => <li key={idx} style={{ marginBottom: 4 }}>{cd}</li>)}
            </ul>
          </div>
        </section>

        {/* 10. DOCUMENTAZIONE ANCORA NECESSARIA */}
        <section className="pd-chapter">
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">10</span>
              Documentazione ancora necessaria prima di procedere
            </div>
            {renderPlusButton("cap_10", "10. Documentazione necessaria")}
          </div>
          {renderSectionCommentBox("cap_10", "10. Documentazione necessaria", JSON.stringify(c10.documenti_mancanti || []))}
          <p className="pd-report-text">
            Per consentire il passaggio dalla presente preanalisi alla redazione del piano attestato o della proposta formale ai creditori, è indispensabile acquisire:
          </p>
          <div className="pd-table-wrap" style={{ marginBottom: 16 }}>
            <table className="pd-table">
              <thead><tr><th>Priorità</th><th>Documento o dato necessario</th><th>Motivazione giuridico-contabile</th></tr></thead>
              <tbody>
                {(c10.documenti_mancanti || []).map((dm, idx) => (
                  <tr key={idx}>
                    <td><span className={`pd-badge pd-badge--${dm.priorita === "ALTA" ? "danger" : "warn"}`}>{dm.priorita || "MEDIA"}</span></td>
                    <td><strong>{dm.dato_mancante || dm.documento}</strong></td>
                    <td style={{ fontSize: 13 }}>{dm.perche_serve || dm.motivo}</td>
                  </tr>
                ))}
                <tr>
                  <td><span className="pd-badge pd-badge--danger">ALTA</span></td>
                  <td><strong>Flusso finanziario annuo disponibile</strong></td>
                  <td style={{ fontSize: 13 }}>{c10.flusso_richiesto}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 11. CONCLUSIONE PROVVISORIA */}
        <section className="pd-chapter" style={{ borderTop: "2px solid var(--pd-primary)", paddingTop: 20 }}>
          <div className="pd-chapter-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num">11</span>
              Conclusione (provvisoria)
            </div>
            {renderPlusButton("cap_11", "11. Conclusione e raccomandazioni")}
          </div>
          {renderSectionCommentBox("cap_11", "11. Conclusione e raccomandazioni", c11.giudizio_sintetico || "")}
          <p className="pd-report-text" style={{ fontSize: 14.5, lineHeight: 1.7, fontWeight: 500 }}>
            {c11.giudizio_sintetico}
          </p>
          <div style={{ background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 16, marginTop: 14 }}>
            <h4 style={{ margin: "0 0 10px", fontSize: 13.5, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--pd-primary)" }}>
              Note e raccomandazioni operative per l'Avv. Aurelio Bentivegna
            </h4>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, lineHeight: 1.6, color: "var(--pd-text)" }}>
              {(c11.raccomandazioni || []).map((rc, idx) => <li key={idx} style={{ marginBottom: 6 }}>{rc}</li>)}
            </ul>
          </div>
          <footer style={{ marginTop: 28, paddingTop: 16, borderTop: "1px solid var(--pd-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase", color: "var(--pd-text-muted)" }}>
              {c11.dicitura_finale || `PRIMA BOZZA DI ANALISI - ELABORATA IL ${new Date().toLocaleDateString("it-IT").toUpperCase()}`}
            </span>
            <span className="pd-badge pd-badge--neutral">DossierLex AI</span>
          </footer>
        </section>
      </article>

      {/* MODALE CONFERMA E PROCEDIMENTO (PROCEED) */}
      <ProceedModal
        isOpen={isProceedModalOpen}
        onClose={() => setIsProceedModalOpen(false)}
        learnedCount={sessionLearnedCount}
        onPrint={() => handleExportPdf("download")}
      />
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