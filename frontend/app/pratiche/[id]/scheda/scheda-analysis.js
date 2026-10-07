"use client";

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

export function FinalReport({ indicators, debtor, card, docs, edits, title, totalAer, patrimonio, goTab }) {
  const macro = indicators?.macro || [];
  const risk = riskFromIndicators([...(macro || []), ...((indicators && indicators.indicators) || [])]);
  return (
    <div className="pd-grid">
      <div className="pd-page-head no-print" style={{ marginBottom: 0 }}>
        <div>
          <h2 className="pd-h2">Scheda analisi finale</h2>
          <p>Output sintetico pronto per revisione o export, con rimando alle fonti.</p>
        </div>
        <button type="button" className="pd-btn pd-btn--primary" onClick={() => window.print()}><span className="material-symbols-outlined" aria-hidden="true">picture_as_pdf</span>Esporta PDF</button>
      </div>
      <article className="pd-report-paper">
        <header style={{ display: "flex", justifyContent: "space-between", gap: 24, marginBottom: 42 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <span className="material-symbols-outlined" aria-hidden="true" style={{ background: "var(--pd-primary)", color: "#fff", padding: 8, borderRadius: 4 }}>account_balance</span>
              <strong className="pd-h3">DossierLex</strong>
            </div>
            <p className="pd-muted" style={{ margin: 0 }}>Pre-analisi documentale, legale ed econometrica</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <span className="pd-badge pd-badge--neutral">Private & Confidential</span>
            <p className="pd-muted" style={{ margin: "8px 0 0" }}>Generato da interfaccia frontend</p>
          </div>
        </header>
        <h1 className="pd-h1" style={{ borderBottom: "1px solid var(--pd-border)", paddingBottom: 20, marginBottom: 28 }}>Dossier analitico: {title}</h1>
        <section className="pd-grid pd-grid--2" style={{ marginBottom: 32 }}>
          <ReportField label="Cliente" value={title} />
          <ReportField label="Rating operativo" value={risk.label} badgeTone={risk.tone} />
          <ReportField label="Debito AER consolidato" value={eurFull(totalAer)} />
          <ReportField label="Patrimonio rilevato" value={eurFull(patrimonio)} />
          <ReportField label="Documenti fonti" value={`${(docs || []).length} caricati`} />
          <ReportField label="Correzioni audit" value={`${(edits || []).length} registrate`} />
        </section>
        <section style={{ marginBottom: 32 }}>
          <h2 className="pd-h3" style={{ marginBottom: 12 }}>Indicatori principali</h2>
          <div className="pd-table-wrap">
            <table className="pd-table">
              <thead><tr><th>Indicatore</th><th>Valore</th><th>Tracciabilita</th></tr></thead>
              <tbody>
                {macro.map((item) => <tr key={item.code}><td><strong>{item.label}</strong></td><td className="pd-num">{fmtIndic(item) || "n.d."}</td><td>{item.formula_human || "Output backend"}</td></tr>)}
                {macro.length === 0 && <tr><td colSpan={3}>Indicatori non ancora disponibili.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
        <section className="pd-grid pd-grid--3" style={{ marginBottom: 32 }}>
          <SourceBox title="Dato grezzo" value="Documenti originali e fonti API" />
          <SourceBox title="Dato corretto" value="Storico correzioni con motivazione" />
          <SourceBox title="Dato derivato" value="Indicatori e consolidamenti backend" />
        </section>
        <footer style={{ borderTop: "1px solid var(--pd-border)", paddingTop: 24, display: "flex", justifyContent: "space-between", gap: 24 }}>
          <button type="button" className="pd-btn pd-btn--secondary no-print" onClick={() => goTab("audit")}>Apri audit</button>
          <p className="pd-muted" style={{ margin: 0, textAlign: "right" }}>Scheda pronta per revisione professionale prima dell'export.</p>
        </footer>
      </article>
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
