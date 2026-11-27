"use client";
import { useEffect, useState } from "react";
import { confirmCaseProtocol, getProtocolAssessment } from "../api";

const PROFILE_OPTIONS = [
  { value: "impresa_individuale", label: "Impresa individuale (Protocollo A)" },
  { value: "societa_capitali_srl", label: "Società di capitali S.r.l. / S.r.l.s. (Protocollo B)" },
  { value: "persona_fisica_non_imprenditore", label: "Persona fisica non imprenditore (escluso da A/B)" },
  { value: "societa_persone", label: "Società di persone — S.n.c. / S.a.s. / S.s. (escluso da A/B)" },
  { value: "altra_forma_giuridica", label: "Altra forma giuridica — S.p.A. / Coop. / Altro (escluso da A/B)" },
  { value: "forma_incerta", label: "Forma giuridica incerta" },
];

const REGIME_OPTIONS = [
  { value: "", label: "Usa rilevato automaticamente" },
  { value: "ordinaria", label: "Contabilità ordinaria" },
  { value: "semplificata", label: "Contabilità semplificata" },
  { value: "altro_regime", label: "Altro regime contabile" },
  { value: "non_documentato", label: "NON DOCUMENTATO" },
];

const COMPLETENESS_OPTIONS = [
  { value: "in_raccolta", label: "In raccolta (Diagnosi preliminare delimitata)" },
  { value: "fascicolo_confermato", label: "Fascicolo confermato" },
];

function badgeColors(kind) {
  if (kind === "ok") return { bg: "#ecfdf5", fg: "#065f46", bd: "#a7f3d0" };
  if (kind === "warn") return { bg: "#fffbeb", fg: "#92400e", bd: "#fde68a" };
  if (kind === "err") return { bg: "#fef2f2", fg: "#991b1b", bd: "#fecaca" };
  return { bg: "#f3f4f6", fg: "#374151", bd: "#d1d5db" };
}

function Pill({ text, kind = "neutral" }) {
  const c = badgeColors(kind);
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 600,
      background: c.bg,
      color: c.fg,
      border: `1px solid ${c.bd}`,
    }}>
      {text}
    </span>
  );
}

export default function ProtocolGate0Card({ caseId, docsCount = 0, onConfirmed }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const [profile, setProfile] = useState("forma_incerta");
  const [regime, setRegime] = useState("");
  const [completeness, setCompleteness] = useState("in_raccolta");
  const [operatorRef, setOperatorRef] = useState("operatore_non_autenticato");
  const [reason, setReason] = useState("");

  async function refresh() {
    if (!caseId) return;
    setLoading(true);
    setErr("");
    try {
      const res = await getProtocolAssessment(caseId);
      setData(res);
      setProfile(res.confirmed?.debtor_profile_confirmed || res.detected?.legal_form_profile || "forma_incerta");
      setRegime(res.confirmed?.accounting_regime_confirmed || "");
      setCompleteness(res.confirmed?.dossier_completeness_status || "in_raccolta");
    } catch (e) {
      setErr(e?.message || "Errore nel caricamento Gate 0");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [caseId, docsCount]);

  async function handleConfirm(e) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      const res = await confirmCaseProtocol(caseId, {
        debtor_profile_confirmed: profile,
        accounting_regime_confirmed: regime || null,
        dossier_completeness_status: completeness,
        operator: operatorRef.trim() || "operatore_non_autenticato",
        reason: reason.trim() || "Conferma inquadramento metodologico e Gate 0",
      });
      setData(res);
      setReason("");
      setMsg("Inquadramento metodologico registrato in FieldEdit (operatore non autenticato).");
      if (typeof onConfirmed === "function") onConfirmed();
    } catch (e2) {
      setErr(e2?.message || "Errore salvataggio conferma");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !data) {
    return (
      <div className="pd-card" style={{ marginBottom: 14, padding: "12px 16px", fontSize: 13 }}>
        Verifica classificazione debitore e Gate 0 in corso...
      </div>
    );
  }

  if (!data) {
    return err ? (
      <div className="pd-card" style={{ marginBottom: 14, padding: "12px 16px", color: "#991b1b", fontSize: 13 }}>
        {err}
      </div>
    ) : null;
  }

  const eff = data.effective || {};
  const det = data.detected || {};
  const gate0 = data.gate0 || {};
  const p0Items = gate0.documenti_indispensabili_p0 || [];
  const p0Missing = p0Items.filter(i => i.status !== "presente").length;
  const dupCount = (gate0.duplicate_groups || []).length;
  const isFullPreanalysis = gate0.conclusivity_level === "PREANALISI_SU_FASCICOLO_CONFERMATO";
  const protoLabel = eff.protocol_code ? `Protocollo ${eff.protocol_code}` : "Nessun protocollo A/B attivo";

  return (
    <div className="pd-card" style={{
      marginBottom: 16,
      padding: "14px 16px",
      border: "1px solid var(--pd-border, #e5e7eb)",
      borderRadius: 10,
      background: "var(--pd-surface, #ffffff)",
    }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
            Inquadramento Metodologico (3 Dimensioni) & Gate 0
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <Pill
              text={`Forma: ${eff.legal_form_label || eff.legal_form_profile}`}
              kind={eff.supported_by_protocol ? "ok" : "warn"}
            />
            <Pill
              text={`Regime: ${eff.accounting_regime_label || eff.accounting_regime}`}
              kind={eff.accounting_regime === "non_documentato" ? "warn" : "neutral"}
            />
            <Pill
              text={`CCII: ${eff.ccii_size_label || eff.ccii_size_qualification}`}
              kind={
                eff.ccii_size_qualification === "non_determinabile" ? "warn"
                : eff.ccii_size_qualification === "non_minore" ? "err"
                : "neutral"
              }
            />
            <Pill
              text={protoLabel}
              kind={eff.protocol_code ? "ok" : "warn"}
            />
            <Pill
              text={isFullPreanalysis ? "PREANALISI SU FASCICOLO CONFERMATO" : "DIAGNOSI PRELIMINARE DELIMITATA"}
              kind={isFullPreanalysis ? "ok" : "warn"}
            />
          </div>
        </div>
        <button
          type="button"
          className="pd-btn-secondary"
          onClick={() => setExpanded(v => !v)}
          style={{ fontSize: 12, padding: "6px 10px" }}
        >
          {expanded ? "Comprimi Gate 0" : `Dettagli & Conferma (${p0Missing} P0 mancanti${dupCount ? `, ${dupCount} duplicati` : ""})`}
        </button>
      </div>

      {err && <div style={{ marginTop: 8, color: "#991b1b", fontSize: 13 }}>{err}</div>}
      {msg && <div style={{ marginTop: 8, color: "#065f46", fontSize: 13, fontWeight: 600 }}>{msg}</div>}

      {expanded && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--pd-border, #e5e7eb)" }}>
          <form onSubmit={handleConfirm} style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 10,
            marginBottom: 14,
            background: "var(--pd-bg, #f9fafb)",
            padding: 12,
            borderRadius: 8,
          }}>
            <label style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 4 }}>
              <strong>1. Forma giuridica confermata</strong>
              <select value={profile} onChange={e => setProfile(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6 }}>
                {PROFILE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <span style={{ color: "#6b7280" }}>Rilevata: {det.legal_form_profile} ({det.legal_form_confidence})</span>
            </label>

            <label style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 4 }}>
              <strong>2. Regime contabile confermato</strong>
              <select value={regime} onChange={e => setRegime(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6 }}>
                {REGIME_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <span style={{ color: "#6b7280" }}>Rilevato: {det.accounting_regime_label}</span>
            </label>

            <label style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 4 }}>
              <strong>3. Stato completezza fascicolo</strong>
              <select value={completeness} onChange={e => setCompleteness(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6 }}>
                {COMPLETENESS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <span style={{ color: "#6b7280" }}>Qualificazione CCII: {eff.ccii_size_label}</span>
            </label>

            <label style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 4 }}>
              <strong>Nota / motivazione (Audit)</strong>
              <input
                type="text"
                value={operatorRef}
                onChange={e => setOperatorRef(e.target.value)}
                placeholder="operatore_non_autenticato"
                style={{ padding: "6px 8px", borderRadius: 6 }}
              />
              <input
                type="text"
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Es. Conferma da visura e bilanci"
                style={{ padding: "6px 8px", borderRadius: 6 }}
              />
              <button type="submit" disabled={saving} className="pd-btn" style={{ marginTop: 4, padding: "6px 10px", fontSize: 12 }}>
                {saving ? "Salvataggio..." : "Conferma inquadramento"}
              </button>
            </label>
          </form>

          <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 12 }}>
            Nota audit: {data.confirmed?.operator_audit_disclaimer || "Identità operatore non autenticata (nessun login/ruoli attivo): il log FieldEdit non costituisce prova certa dell'identità personale."}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12, fontSize: 12 }}>
            <div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Checklist documenti indispensabili (P0)</div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {p0Items.map(item => (
                  <li key={item.code} style={{ marginBottom: 6 }}>
                    <Pill
                      text={`${item.status}${item.verification_stage ? ` · ${item.verification_stage}` : ""}`}
                      kind={item.status === "presente" ? "ok" : (item.status === "in_elaborazione" || item.status === "parziale") ? "warn" : "err"}
                    />{" "}
                    <strong>{item.title}</strong>
                    {Array.isArray(item.missing_details) && item.missing_details.length > 0 && (
                      <div style={{ color: "#92400e", marginTop: 2 }}>{item.missing_details.join(" ")}</div>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Dati non disponibili / Decisioni sospese</div>
              {(gate0.decisioni_sospese || []).length > 0 && (
                <ul style={{ margin: "0 0 8px 0", paddingLeft: 16, color: "#92400e" }}>
                  {gate0.decisioni_sospese.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              )}
              {(gate0.anomalie_gate0 || []).length > 0 && (
                <>
                  <div style={{ fontWeight: 700, marginBottom: 4, color: "#991b1b" }}>Anomalie Gate 0 ({gate0.anomalie_gate0.length})</div>
                  <ul style={{ margin: 0, paddingLeft: 16, color: "#991b1b" }}>
                    {gate0.anomalie_gate0.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
