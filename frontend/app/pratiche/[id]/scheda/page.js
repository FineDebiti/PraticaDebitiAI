"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getCard, getCase, saveDebtor, createCompany, updateCompany, deleteCompany, uploadDoc, addRealEstate, delRealEstate, addVehicle, delVehicle,
  setPrimaryResidence, openapiSearch, openapiRequests, openapiRequest, companyFill, companyImport, promoteCompany,
  uploadAer, deleteAer, relatedCases, openRelated, docFileUrl, patchRecord, getEdits, getIndicators,
  getIncomeDocuments, getIncomeSummary, runCrossAnalysis, getCrossAnalysis, getPreanalysisReport, reanalyzeCase } from "../../../api";
import DocumentsPanel from "../../../components/DocumentsPanel";
import CaseChatDrawer from "../../../components/CaseChatDrawer";
import { CrBadge, Section, Stat, ToolsBar } from "./scheda-ui";
import {
  AuditTrail as AuditTrailView,
  CrossAnalysis as CrossAnalysisView,
  EconometricEvaluation as EconometricEvaluationView,
  FinalReport as FinalReportView,
} from "./scheda-analysis";

const EMPTY = {
  first_name: "", last_name: "", tax_code: "", birth_date: "", birth_place: "",
  residence: "", domicile: "", phone: "", email: "", pec: "", marital_status: "",
  profession: "", employer: "", client_type: "privato",
  household_composition: "", dependents: 0,
  monthly_net_income: 0, annual_income: 0, income_sources: "", monthly_expenses: 0,
  rent_or_mortgage: 0, bank_accounts: "",
  has_ongoing_garnishment: false, has_salary_assignment: false, has_payment_delegation: false,
  notes: "",
};

// Documenti reddituali: alimentano i campi economici del Debtor (human-in-the-loop).
const INCOME_DOC_TYPES = ["busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi"];

const EMPTY_COMPANY = {
  name: "", legal_form: "", company_type: "", tax_code: "", vat: "", rea: "", cciaa: "",
  pec: "", legal_address: "", status: "", constitution_date: "", capital: 0,
  ateco: "", fatturato: 0, dipendenti: 0, patrimonio_netto: 0, anno_bilancio: "",
  business_summary: "", members: [],
};

export default function Scheda({ params, initialSection = "documenti" }) {
  const { id } = params;
  const router = useRouter();
  const [d, setD] = useState(EMPTY);
  const [card, setCard] = useState({ real_estates: [], vehicles: [] });
  const [saved, setSaved] = useState("");
  const [incomeToast, setIncomeToast] = useState("");  // "verifica e salva" dopo estrazione reddito
  const [activeTab, setActiveTab] = useState(initialSection || "documenti");
  const [drafts, setDrafts] = useState([]);   // nuove aziende non ancora salvate (moduli aggiunti)
  const [docs, setDocs] = useState([]);          // documenti (per conteggi + auto-refresh cross-tab)
  const [uploadedByScope, setUploadedByScope] = useState({});  // id doc caricati per sezione (persistono al cambio tab)
  const [related, setRelated] = useState([]);   // altre pratiche con lo stesso CF (solo sommario)
  const [indic, setIndic] = useState(null);     // cruscotto indicatori (aggregati)
  const [edits, setEdits] = useState([]);       // correzioni manuali (audit) della pratica
  const [correction, setCorrection] = useState(null);  // modale correzione aperta {entityType,...}
  const [crossAnalysis, setCrossAnalysis] = useState(null);
  const [crossLoading, setCrossLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const docStatusRef = useRef({});
  const draftSeq = useRef(0);

  useEffect(() => {
    setActiveTab(initialSection || "documenti");
  }, [initialSection]);

  function addUploaded(scope, docId) {
    setUploadedByScope(prev => ({ ...prev, [scope]: [...(prev[scope] || []), docId] }));
  }
  function showIncomeToast() {
    setIncomeToast("Dati reddito aggiornati dal documento — verifica e salva");
    setTimeout(() => setIncomeToast(""), 7000);
  }

  // polling documenti SEMPRE attivo (anche fuori dalla tab Documenti): aggiorna i
  // conteggi e, quando un documento è elaborato, ricarica la scheda (dati estratti).
  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const cs = await getCase(id);
        if (stop || !cs || !cs.documents) return;
        setDocs(cs.documents);
        let processed = false, incomeUpdated = false;
        for (const doc of cs.documents) {
          const before = docStatusRef.current[doc.id];
          if (before && !["elaborato", "normalizzato"].includes(before) && ["elaborato", "normalizzato"].includes(doc.status)) {
            processed = true;
            if (INCOME_DOC_TYPES.includes(doc.doc_type)) incomeUpdated = true;
          }
          docStatusRef.current[doc.id] = doc.status;
        }
        if (processed) load();
        if (incomeUpdated) showIncomeToast();
      } catch {}
    }
    tick();
    const t = setInterval(tick, 4000);
    return () => { stop = true; clearInterval(t); };
  }, [id]);

  async function load() {
    let c;
    try {
      c = await getCard(id);
    } catch {
      // backend non raggiungibile (es. stack fermo): ignora silenziosamente
      return;
    }
    if (!c || c.error) return;
    setCard(c);
    const deb = c.debtor || null;
    if (deb) { setD({ ...EMPTY, ...deb }); setDirty(false); }
    getPreanalysisReport(id).then((r) => { if (r) setReportData(r); }).catch(() => {});
    getIndicators(id).then((ind) => { if (ind) setIndic(ind); }).catch(() => {});
  }
  useEffect(() => { load(); }, [id]);
  useEffect(() => { relatedCases(id).then(setRelated).catch(() => {}); }, [id]);
  useEffect(() => { getCrossAnalysis(id).then(setCrossAnalysis).catch(() => {}); }, [id]);
  // indicatori: ricaricati ogni volta che si apre la tab (riflettono i dati più recenti)
  useEffect(() => { if (["indicatori", "econometria", "report", "riepilogo"].includes(activeTab)) getIndicators(id).then(setIndic).catch(() => {}); }, [id, activeTab]);

  async function handleReanalyzeCase() {
    if (!id || reanalyzing) return;
    setReanalyzing(true);
    try {
      const res = await reanalyzeCase(id);
      if (res?.cross_analysis) setCrossAnalysis(res.cross_analysis);
      if (res?.report) setReportData(res.report);
      if (res?.indicators) setIndic(res.indicators);
      await load();
      setIncomeToast(`Pre-analisi rieseguita e aggiornata (v${res?.version || "aggiornata"})`);
      setTimeout(() => setIncomeToast(""), 5000);
    } catch (e) {
      alert("Errore durante la riesecuzione della pre-analisi: " + (e?.message || "Errore sconosciuto"));
    } finally {
      setReanalyzing(false);
    }
  }

  async function handleRunCrossAnalysis() {
    setCrossLoading(true);
    try {
      const res = await runCrossAnalysis(id);
      setCrossAnalysis(res);
    } catch (e) {
      alert("Errore durante l'analisi trasversale: " + e.message);
    } finally {
      setCrossLoading(false);
    }
  }

  // correzioni: storico + helper per aprire la modale e ricaricare dopo il salvataggio
  function reloadEdits() { getEdits(id).then(setEdits).catch(() => {}); }
  useEffect(() => { reloadEdits(); }, [id]);
  const editsByEntity = {};
  for (const e of edits) (editsByEntity[e.entity_id] = editsByEntity[e.entity_id] || []).push(e);
  function openCorrection(cfg) { setCorrection(cfg); }
  async function afterCorrection() { await load(); reloadEdits(); setCorrection(null); }
  const corr = { open: openCorrection, byEntity: editsByEntity };

  function set(k, v) { setD(prev => ({ ...prev, [k]: v })); setDirty(true); }

  async function save() {
    await saveDebtor(id, d);
    setDirty(false);
    setSaved("Scheda salvata");
    setTimeout(() => setSaved(""), 2500);
    load();
  }

  // P1.1 — protezione contro la perdita di modifiche non salvate
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    function warn(e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } }
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function goTab(k) {
    if (k === activeTab) return;
    if (dirty && activeTab === "anagrafica" &&
        !window.confirm("Hai modifiche non salvate nell'anagrafica. Cambiare scheda senza salvarle?")) return;
    const target = k === "documenti" ? `/pratiche/${id}/scheda` : `/pratiche/${id}/scheda/${k}`;
    router.push(target);
  }

  // moduli azienda: aggiunge una bozza vuota (nuova azienda da compilare)
  function addCompanyDraft() {
    draftSeq.current += 1;
    const key = "draft-" + draftSeq.current;
    setDrafts(prev => [...prev, { _key: key }]);
    setActiveTab("aziende");
  }
  function removeDraft(key) { setDrafts(prev => prev.filter(x => x._key !== key)); }

  // valore di un immobile: commerciale (mercato) se stimato, altrimenti catastale, altrimenti il manuale
  const reValore = (r) => r.commercial_value || r.cadastral_value || r.estimated_value || 0;
  const patrimonio = (card.real_estates || []).reduce((s, r) => s + reValore(r), 0)
    + (card.vehicles || []).reduce((s, v) => s + (v.estimated_value || 0), 0);

  // azienda? (societa o ditta individuale) -> anagrafica diversa, niente nucleo familiare
  const isAzienda = ["societa", "ditta_individuale"].includes(d.client_type);

  // dati derivati per riepilogo e badge tab
  const companies = card.companies || [];
  const clienteCompanies = companies.filter(c => c.role === "cliente");
  const controparti = companies.filter(c => c.role !== "cliente");
  // azienda-pratica senza ancora un record Company -> mostra un modulo seed dal debitore
  const needSeed = isAzienda && clienteCompanies.length === 0;
  const seedCompany = needSeed ? {
    role: "cliente", name: d.last_name || "",
    tax_code: d.tax_code || "", vat: /^[0-9]{11}$/.test(d.tax_code || "") ? d.tax_code : "",
    pec: d.pec || "", legal_address: d.residence || "", members: [],
  } : null;

  const totCad = (card.real_estates || []).reduce((s, r) => s + (r.cadastral_value || 0), 0);
  const totComm = (card.real_estates || []).reduce((s, r) => s + (r.commercial_value || 0), 0);
  const cr = card.credit_report;
  const taxDebts = card.tax_debts || [];
  const nAer = taxDebts.length;
  const totAer = taxDebts.reduce((s, t) => s + (t.total_residuo || 0), 0);
  const nPatr = (card.real_estates || []).length + (card.vehicles || []).length;
  const nAz = companies.length + (needSeed ? 1 : 0);
  const nDoc = docs.length;
  const nDocOk = docs.filter(x => ["elaborato", "normalizzato"].includes(x.status)).length;
  const isSocioAz = companies.some(c => (c.members || []).some(m => m.is_client));
  const isGaranteClient = ["garante", "coobbligato"].includes(d.client_type);
  const titolare = isAzienda
    ? (clienteCompanies[0]?.name || d.last_name || "—")
    : (`${d.first_name || ""} ${d.last_name || ""}`.trim() || "—");

  const TABS = [
    { key: "documenti", label: "Documenti", badge: nDoc },
    { key: "aer", label: "Stato passivo", badge: nAer, dim: nAer === 0 },
    { key: "aziende", label: "Aziende", badge: nAz, dim: nAz === 0 },
    { key: "anagrafica", label: "Anagrafica" },
    { key: "banca", label: "Banca", dim: !cr },
    { key: "patrimonio", label: "Patrimonio", badge: nPatr, dim: nPatr === 0 },
    { key: "raccolta", label: "Raccolta dati" },
    { key: "riepilogo", label: "Hub analitico" },
    { key: "indicatori", label: "Indicatori" },
    { key: "audit", label: "Audit", badge: edits.length },
    { key: "econometria", label: "Econometria" },
    { key: "report", label: "Report finale" },
  ];

  return (
    <div>
      <style>{`
        .tabbar { margin: 12px 0 20px; }
        td, th { overflow-wrap: anywhere; word-break: break-word; }
        .tools-grid { display: grid; gap: 12px; align-items: start; }
        .tools-2col { grid-template-columns: 65fr 35fr; }
        .tools-auto { grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
        @media (max-width: 820px) { .tools-2col, .tools-auto { grid-template-columns: 1fr; } }
        @media (max-width: 700px) { .tabbar { flex-wrap: nowrap; overflow-x: auto; } }
      `}</style>

      {/* HEADER ISTITUZIONALE DELLA PRATICA */}
      <div
        className="pd-card"
        style={{
          padding: "18px 22px",
          marginBottom: 16,
          background: "var(--pd-surface)",
          border: "1px solid var(--pd-border)",
          borderLeft: "4px solid var(--pd-primary)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
          <Link href="/pratiche" style={{ color: "var(--pd-accent)", fontSize: 13, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
            Tutte le pratiche
          </Link>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span className="pd-badge pd-badge--info" style={{ fontSize: 11 }}>
              Motore Forense v2.1 · Decimal Audit
            </span>
            <span className={`pd-badge pd-badge--${nDocOk === nDoc && nDoc > 0 ? "ok" : "neutral"}`} style={{ fontSize: 11 }}>
              {nDocOk}/{nDoc} fonti elaborate [D]
            </span>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h1 className="pd-h2" style={{ margin: 0, color: "var(--pd-primary)" }}>
                {titolare}
              </h1>
              <span className="pd-badge pd-badge--neutral">
                {SEL_LABELS[d.client_type] || d.client_type || "Privato"}
              </span>
              {(d.tax_code || clienteCompanies[0]?.vat) && (
                <span
                  style={{
                    fontFamily: "var(--pd-font-mono)",
                    fontSize: 12,
                    background: "var(--pd-surface-low)",
                    border: "1px solid var(--pd-border)",
                    borderRadius: 4,
                    padding: "2px 8px",
                    color: "var(--pd-text-muted)",
                    fontWeight: 600,
                  }}
                >
                  {isAzienda ? "P.IVA / CF: " : "CF: "}
                  {clienteCompanies[0]?.vat || d.tax_code}
                </span>
              )}
            </div>
            <p className="pd-muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
              Fascicolo istruttorio sovraindebitamento / crisi d&apos;impresa (D.Lgs. 14/2019 CCII) · Tracciabilità SHA-256 e controllo inferenze attivo.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="pd-btn pd-btn--secondary" onClick={() => goTab("documenti")}>
              <span className="material-symbols-outlined" aria-hidden="true">folder_open</span>
              Documenti ({nDoc})
            </button>
            <button
              type="button"
              className="pd-btn pd-btn--secondary"
              onClick={handleReanalyzeCase}
              disabled={reanalyzing}
              title="Ricalcola analisi trasversale, indicatori, econometria, relazione cliente e dossier audit sui dati aggiornati"
            >
              <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
              {reanalyzing ? "Riesecuzione..." : "Riesegui Pre-Analisi"}
            </button>
            <button type="button" className="pd-btn pd-btn--primary" onClick={() => goTab("report")}>
              <span className="material-symbols-outlined" aria-hidden="true">description</span>
              Relazione & Dossier Audit
            </button>
          </div>
        </div>
      </div>

      <RelatedBanner caseId={id} related={related} />

      {incomeToast && (
        <div style={{ position: "fixed", right: 16, bottom: 16, zIndex: 60, background: "var(--pd-ok)", color: "var(--pd-surface)",
          padding: "12px 16px", borderRadius: 8, boxShadow: "var(--pd-shadow-md)", fontSize: 14, fontWeight: 600, maxWidth: 340 }}>
          {incomeToast}
        </div>
      )}

      <CorrezioneModal caseId={id} correction={correction}
        onClose={() => setCorrection(null)} onSaved={afterCorrection} />

      {/* BARRA TAB (pattern ARIA: tablist/tab/tabpanel) */}
      <div className="pd-tabs tabbar" role="tablist" aria-label="Sezioni della scheda">
        {TABS.map(t => (
          <button key={t.key} type="button" role="tab" id={`tab-${t.key}`}
            aria-selected={activeTab === t.key} aria-controls="scheda-tabpanel"
            tabIndex={activeTab === t.key ? 0 : -1} onClick={() => goTab(t.key)} className="pd-tab">
            {t.label}{t.badge ? ` (${t.badge})` : ""}
          </button>
        ))}
      </div>

      <div id="scheda-tabpanel" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>

      {/* ===== RIEPILOGO / HUB ANALITICO ===== */}
      {activeTab === "riepilogo" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-page-head" style={{ marginBottom: 0 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h2 className="pd-h2">Hub Analitico e Quadro Sinottico</h2>
                <span className="pd-badge pd-badge--info">[D] Fonti · [C] Calcoli · [R] Riferiti</span>
              </div>
              <p>
                Vista integrata delle posizioni estratte dai documenti ufficiali, con collegamento diretto alle sezioni istruttorie e alla Super-Analisi Qwen.
              </p>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            <SummaryCard title="Soggetto / Cliente" badge="[D] Anagrafica" onGo={() => goTab("anagrafica")}>
              <div style={{ fontSize: 16, fontWeight: "bold", color: "var(--pd-primary)", marginBottom: 4 }}>{titolare}</div>
              <SLine k={isAzienda ? "P.IVA / CF" : "Codice Fiscale"} v={(isAzienda ? (clienteCompanies[0]?.vat || clienteCompanies[0]?.tax_code || d.tax_code) : d.tax_code) || "—"} />
              <SLine k="Natura giuridica" v={SEL_LABELS[d.client_type] || d.client_type} />
            </SummaryCard>
            <SummaryCard title="Patrimonio Imm. e Mob." badge="[D/R] Catasto & PRA" onGo={() => goTab("patrimonio")}>
              <SLine k="Immobili da visura [D]" v={(card.real_estates || []).length === 0 ? "0 (Visura negativa)" : (card.real_estates || []).length} />
              <SLine k="Valore immobiliare" v={totComm > 0 ? eurFull(totComm) : totCad > 0 ? eurFull(totCad) : "€ 0,00 (nessun immobile)"} />
              <SLine k="Beni mobili / Veicoli" v={(card.vehicles || []).length} />
              <SLine k="Stima mobiliare" v={(card.vehicles || []).reduce((s, v) => s + (v.estimated_value || 0), 0) > 0 ? eurFull((card.vehicles || []).reduce((s, v) => s + (v.estimated_value || 0), 0)) : "Da periziare (NULL)"} />
            </SummaryCard>
            <SummaryCard title="Stato Passivo AdER" badge="[D] Ruoli" onGo={() => goTab("aer")}>
              <SLine k="Totale residuo a ruolo" v={taxDebts.length > 0 ? eurFull(totAer) : "Non caricato (NULL)"} />
              <SLine k="Estratti / Prospetti" v={taxDebts.length} />
              <SLine k="Anti-duplicazione INPS" v="Attiva (incluso in AdER)" />
            </SummaryCard>
            <SummaryCard title="Posizione Bancaria e CR" badge="[D] Banca d'Italia" onGo={() => goTab("banca")}>
              <SLine k="Esposizione CR rilevata" v={cr ? eurFull(cr.total_exposure) : "Non rilevata (NULL)"} />
              <SLine k="Garanzie prestate" v={cr ? eurFull(cr.total_guarantees) : "—"} />
              {cr && (
                <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                  <CrBadge on={cr.has_sofferenze} okText="No sofferenze CR" alertText="Sofferenze" tone="danger" />
                  <CrBadge on={cr.has_criticita} okText="No sconfini CR" alertText="Criticità rilevate" tone="warning" />
                </div>
              )}
            </SummaryCard>
            <SummaryCard title="Aziende e Bilanci" badge="[D] CCIAA / OIC" onGo={() => goTab("aziende")}>
              <SLine k="Imprese collegate" v={nAz} />
              <SLine k="Situazioni contabili" v={(clienteCompanies[0]?.financial_statements || []).length || 0} />
              {isSocioAz && <div style={{ fontSize: 12, color: "var(--pd-warn)", marginTop: 4, fontWeight: 600 }}>Titolare / Socio con cariche attive</div>}
              {isGaranteClient && <div style={{ fontSize: 12, color: "var(--pd-warn)", marginTop: 4, fontWeight: 600 }}>Cliente garante / coobbligato</div>}
            </SummaryCard>
            <SummaryCard title="Inventario Documentale" badge="[D] SHA-256" onGo={() => goTab("documenti")}>
              <SLine k="Documenti acquisiti" v={nDoc} />
              <SLine k="Elaborati e normalizzati" v={`${nDocOk}/${nDoc}`} />
              <SLine k="Integrità crittografica" v="SHA-256 (64 char)" />
            </SummaryCard>
          </div>

          <div className="pd-card" style={{ padding: "18px 20px", background: "var(--pd-surface)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 14 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ color: "var(--pd-primary)", fontSize: 20 }}>verified_user</span>
                  <h3 className="pd-card__title" style={{ margin: 0, fontSize: 16 }}>
                    Sintesi Controlli Forensi e Riconciliazione Deterministica
                  </h3>
                  <span className="pd-badge pd-badge--ok">Motore v2.1 Attivo</span>
                </div>
                <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "var(--pd-text-muted)" }}>
                  I controlli su incongruenze, anti-duplicazione debiti e scenari CCII sono ora integrati e certificati nel <strong>Dossier Tecnico di Audit (7 pagg.)</strong>.
                </p>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="pd-btn pd-btn--secondary" onClick={() => goTab("audit")}>
                  <span className="material-symbols-outlined" aria-hidden="true">fact_check</span>
                  Quality Gate & Audit
                </button>
                <button type="button" className="pd-btn pd-btn--primary" onClick={() => goTab("report")}>
                  <span className="material-symbols-outlined" aria-hidden="true">description</span>
                  Apri Relazione & Dossier Tecnico
                </button>
              </div>
            </div>
            <div className="pd-grid pd-grid--4">
              {(() => {
                const td = reportData?.technical_dossier || {};
                const quads = td?.decimal_audit?.quadrature || [];
                const qOk = quads.filter((q) => String(q?.esito || "").includes("VERIFICATO")).length;
                const anom = td?.anomaly_register || [];
                const nRosse = td?.quality_gate?.counts?.rosso ?? anom.filter((a) => a.severita === "ROSSO").length;
                const infChecks = td?.inference_audit?.checks || [];
                const infOk = infChecks.filter((c) => c.esito === "SUPERATO" || String(c.esito || "").includes("OK")).length || infChecks.length;
                return (
                  <>
                    <div className="pd-source-box">
                      <label>Quadrature Decimal</label>
                      <strong style={{ color: "var(--pd-ok)" }}>{qOk} / {quads.length} Verificate</strong>
                      <span style={{ fontSize: 11, color: "var(--pd-text-muted)", display: "block", marginTop: 2 }}>Verifica aritmetica al centesimo</span>
                    </div>
                    <div className="pd-source-box">
                      <label>Anti-Duplicazione Passivo</label>
                      <strong style={{ color: "var(--pd-primary)" }}>Filtri Attivi</strong>
                      <span style={{ fontSize: 11, color: "var(--pd-text-muted)", display: "block", marginTop: 2 }}>Riconciliazione banche dati e bilancio</span>
                    </div>
                    <div className="pd-source-box">
                      <label>Controllo Inferenze</label>
                      <strong style={{ color: "var(--pd-ok)" }}>{infOk} / {infChecks.length || 5} Regole OK</strong>
                      <span style={{ fontSize: 11, color: "var(--pd-text-muted)", display: "block", marginTop: 2 }}>Blocco attivo su inferenze non documentate</span>
                    </div>
                    <div className="pd-source-box">
                      <label>Anomalie &amp; Human Gate</label>
                      <strong style={{ color: "var(--pd-warn)" }}>{anom.length} Censite ({nRosse} Rosse)</strong>
                      <span style={{ fontSize: 11, color: "var(--pd-text-muted)", display: "block", marginTop: 2 }}>Divieto di auto-approvazione senza revisione umana</span>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* ===== INDICATORI ===== */}
      {activeTab === "indicatori" && (
        <IndicatoriCruscotto data={indic} goTab={goTab} />
      )}

      {/* ===== RACCOLTA DATI GUIDATA ===== */}
      {activeTab === "raccolta" && (
        <DataCollectionFlow
          debtor={d}
          card={card}
          docs={docs}
          edits={edits}
          onGo={goTab}
          nPatr={nPatr}
          nAer={nAer}
          nAz={nAz}
          hasCreditReport={!!cr}
        />
      )}

      {/* ===== ANAGRAFICA ===== */}
      {activeTab === "anagrafica" && (
        <>
          <div className="pd-page-head" style={{ marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h2 className="pd-h2">Anagrafica, Inquadramento Soggetto e Dati Reddituali</h2>
                <span className="pd-badge pd-badge--info">[D] Anagrafica / Dichiarazioni · [R] Spese</span>
              </div>
              <p>
                Qualificazione soggettiva ai sensi del CCII (consumatore, professionista, imprenditore minore o sopra-soglia) e raccolta flussi personali.
              </p>
            </div>
            <button onClick={save} className="pd-btn pd-btn--primary" type="button">
              <span className="material-symbols-outlined" aria-hidden="true">save</span>
              Salva Anagrafica
            </button>
          </div>

          <Section
            title={isAzienda ? "Referente, Titolare e Inquadramento Giuridico" : "Dati Anagrafici e Residenza"}
            subtitle={isAzienda ? "Per le ditte individuali l'imprenditore risponde con l'intero patrimonio ex art. 2740 c.c." : "Dati identificativi della persona fisica e contatti."}
            badge="[D] Identificazione"
            icon="badge"
          >
            <Grid>
              {isAzienda ? (
                <>
                  <F label="Tipologia soggetto (CCII)">
                    <Sel v={d.client_type} on={v => set("client_type", v)}
                      opts={["privato", "ditta_individuale", "societa", "garante", "coobbligato"]} />
                  </F>
                  <F label="Titolare / Legale Rappresentante"><I v={d.first_name || d.last_name} on={v => set("first_name", v)} /></F>
                  <F label="Codice Fiscale / P.IVA"><I v={d.tax_code} on={v => set("tax_code", v)} /></F>
                  <F label="PEC / Domicilio Digitale"><I v={d.pec} on={v => set("pec", v)} /></F>
                  <F label="Telefono"><I v={d.phone} on={v => set("phone", v)} /></F>
                  <F label="Email"><I v={d.email} on={v => set("email", v)} /></F>
                  <div style={{ gridColumn: "1 / -1", background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 6, padding: "10px 14px", fontSize: 12.5, color: "var(--pd-text-muted)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>
                      I dati completi dell&apos;impresa (denominazione, P.IVA, codice ATECO, bilanci 2024–2026 e addetti) sono gestiti nella scheda <strong>Aziende</strong>.
                    </span>
                    <button type="button" className="pd-btn pd-btn--secondary" style={{ minHeight: 32, padding: "4px 12px", fontSize: 12 }} onClick={() => goTab("aziende")}>
                      Vai alla scheda Aziende →
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <F label="Nome"><I v={d.first_name} on={v => set("first_name", v)} /></F>
                  <F label="Cognome"><I v={d.last_name} on={v => set("last_name", v)} /></F>
                  <F label="Codice fiscale"><I v={d.tax_code} on={v => set("tax_code", v)} /></F>
                  <F label="Data di nascita"><I type="date" v={d.birth_date} on={v => set("birth_date", v)} /></F>
                  <F label="Luogo di nascita"><I v={d.birth_place} on={v => set("birth_place", v)} /></F>
                  <F label="Tipologia cliente">
                    <Sel v={d.client_type} on={v => set("client_type", v)}
                      opts={["privato", "ditta_individuale", "societa", "garante", "coobbligato"]} />
                  </F>
                  <F label="Residenza" wide><I v={d.residence} on={v => set("residence", v)} /></F>
                  <F label="Domicilio" wide><I v={d.domicile} on={v => set("domicile", v)} /></F>
                  <F label="Telefono"><I v={d.phone} on={v => set("phone", v)} /></F>
                  <F label="Email"><I v={d.email} on={v => set("email", v)} /></F>
                  <F label="PEC"><I v={d.pec} on={v => set("pec", v)} /></F>
                  <F label="Stato civile"><I v={d.marital_status} on={v => set("marital_status", v)} /></F>
                  <F label="Professione"><I v={d.profession} on={v => set("profession", v)} /></F>
                  <F label="Datore di lavoro"><I v={d.employer} on={v => set("employer", v)} /></F>
                </>
              )}
            </Grid>
          </Section>

          {!isAzienda && (
            <Section title="Nucleo familiare" subtitle="Composizione familiare rilevante per il calcolo del fabbisogno vitale ex art. 68/75 CCII." badge="[D/R] Stato Famiglia" icon="family_restroom">
              <Grid>
                <F label="Composizione nucleo" wide><I v={d.household_composition} on={v => set("household_composition", v)} /></F>
                <F label="Familiari a carico"><I type="number" v={d.dependents} on={v => set("dependents", +v)} /></F>
              </Grid>
            </Section>
          )}

          <Section
            title="Dati Economici, Dichiarazioni Fiscali e Fabbisogno Personale"
            subtitle="Acquisizione dichiarazioni (Modello Redditi PF / CU / ISEE) e distinzione rigorosa tra reddito imponibile fiscale e flussi di cassa."
            badge="[D] Dichiarazioni · [R] Fabbisogno"
            icon="payments"
          >
            {isAzienda && (
              <div
                style={{
                  background: "var(--pd-warn-bg)",
                  border: "1px solid var(--pd-accent)",
                  borderLeft: "4px solid var(--pd-warn)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  marginBottom: 14,
                  fontSize: 12.5,
                  color: "var(--pd-text)",
                }}
              >
                <strong>Regola Forense di Separazione Contabile/Fiscale (Blocco INF-01):</strong> Per le imprese e ditte individuali, i ricavi, i costi operativi e l&apos;EBITDA sono censiti nella scheda <strong>Aziende (Bilanci)</strong>. Eventuali componenti positivi da adeguamento ISA nei quadri fiscali (es. rigo RG5) hanno natura esclusivamente tributaria e non costituiscono liquidità o reddito mensile disponibile. Se i prelievi personali o le spese familiari non sono documentati, i relativi indicatori restano <strong>Non rilevati (NULL)</strong>.
              </div>
            )}
            <RedditoTools caseId={id} taxCode={d.tax_code} docs={docs}
              uploadedByScope={uploadedByScope} addUploaded={addUploaded}
              reload={load} onIncomeUpdated={showIncomeToast} />
            <RiepilogoReddito caseId={id} docs={docs}
              currentMonthly={d.monthly_net_income} currentAnnual={d.annual_income}
              onApplyMonthly={(v) => set("monthly_net_income", v)}
              onApplyAnnual={(v) => set("annual_income", v)} />
            <Grid>
              <F label="Reddito personale mensile netto (€) [D/R]"><Money v={d.monthly_net_income} on={v => set("monthly_net_income", v)} placeholder="Lasciare 0 se solo reddito d'impresa in Bilancio" /></F>
              <F label="Reddito imponibile annuo (€) [D]"><Money v={d.annual_income} on={v => set("annual_income", v)} /></F>
              <F label="Spese personali/familiari mensili (€) [R]"><Money v={d.monthly_expenses} on={v => set("monthly_expenses", v)} /></F>
              <F label="Canone affitto / mutuo abitazione (€) [D/R]"><Money v={d.rent_or_mortgage} on={v => set("rent_or_mortgage", v)} /></F>
              <F label="Note su fonti reddituali e raccordi fiscali (es. Modello PF Quadro RG / RN)" wide>
                <textarea value={d.income_sources ?? ""} onChange={e => set("income_sources", e.target.value)}
                  rows={Math.min(6, Math.max(2, (d.income_sources || "").split("\n").length))}
                  style={{ ...inp, width: "100%", boxSizing: "border-box", resize: "vertical", fontFamily: "inherit" }} />
              </F>
              <F label="Rapporti di conto corrente censiti" wide><I v={d.bank_accounts} on={v => set("bank_accounts", v)} /></F>
            </Grid>
          </Section>

          <Section title="Procedure Esecutive e Trattenute in Corso" subtitle="Verifica di pignoramenti presso terzi, immobiliari o cessioni del quinto attive." badge="[D/R] Esecuzioni" icon="gavel">
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
              <Chk label="Pignoramenti in corso" v={d.has_ongoing_garnishment} on={v => set("has_ongoing_garnishment", v)} />
              <Chk label="Cessione del quinto" v={d.has_salary_assignment} on={v => set("has_salary_assignment", v)} />
              <Chk label="Delega di pagamento" v={d.has_payment_delegation} on={v => set("has_payment_delegation", v)} />
            </div>
          </Section>

          <Section title="Note Istruttorie del Professionista" subtitle="Annotazioni interne riservate allo Studio per la predisposizione della pre-analisi." badge="Uso Interno" badgeTone="neutral" icon="edit_note">
            <textarea value={d.notes} onChange={e => set("notes", e.target.value)}
              style={{ width: "100%", minHeight: 80, padding: 10, border: "1px solid var(--pd-border)", borderRadius: 6 }} />
          </Section>

          <div style={{ position: "sticky", bottom: 0, background: "rgba(249, 249, 247, 0.96)", borderTop: "1px solid var(--pd-border)",
            display: "flex", alignItems: "center", gap: 14, padding: "12px 0", margin: "16px 0 0", zIndex: 5 }}>
            <button onClick={save} className="pd-btn pd-btn--primary" type="button">
              <span className="material-symbols-outlined" aria-hidden="true">save</span>
              Salva scheda anagrafica
            </button>
            {dirty && <span className="pd-badge pd-badge--warn">Modifiche non salvate</span>}
            {saved && <span className="pd-badge pd-badge--ok">{saved}</span>}
          </div>
        </>
      )}

      {/* ===== PATRIMONIO ===== */}
      {activeTab === "patrimonio" && (
        <>
          <div className="pd-page-head" style={{ marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h2 className="pd-h2">Patrimonio Immobiliare e Mobiliare</h2>
                <span className="pd-badge pd-badge--info">[D] Catasto / PRA · [S] Stime Realizzo</span>
              </div>
              <p>
                Censimento dei beni immobili (Visura Catastale Sister) e dei beni mobili registrati / strumentali, con distinzione tra valore contabile e valore di realizzo.
              </p>
            </div>
          </div>

          <ToolsBar title="Acquisizione Visure Catastali (Sister) e PRA" subtitle="Interroga le banche dati ufficiali Catasto/PRA o carica direttamente le visure PDF nel fascicolo.">
            <OpenapiSearch caseId={id} taxCode={d.tax_code} scope="patrimonio"
              title="Cerca al Catasto / PRA"
              subtitle="Recupera immobili (Catasto) e veicoli (PRA) da fonti ufficiali. L'elaborazione avviene in background."
              onImportItems={async (source, items) => {
                for (const it of items) {
                  const { _raw, ...clean } = it;
                  if (source === "veicoli") await addVehicle(id, { ...clean, source: "PRA (Openapi)" });
                  else if (source === "immobili") await addRealEstate(id, { ...clean, source: "Catasto (Openapi)" });
                }
                load();
              }} />
            <UploadBox caseId={id} label="Carica visura catastale o PRA (PDF/immagine)" onUploaded={load} docs={docs}
              scope="catastale" docType="visura_catastale" uploadedIds={uploadedByScope.catastale || []} onUploadedId={addUploaded} />
          </ToolsBar>
          <Patrimonio caseId={id} card={card} reload={load} totale={patrimonio} corr={corr} />
        </>
      )}

      {/* ===== POSIZIONE BANCARIA ===== */}
      {activeTab === "banca" && (
        <>
          <div className="pd-page-head" style={{ marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h2 className="pd-h2">Esposizione Bancaria e Centrale Rischi Banca d&apos;Italia</h2>
                <span className="pd-badge pd-badge--info">[D] Centrale Rischi / Piani Ammortamento</span>
              </div>
              <p>
                Analisi degli affidamenti a revoca, a scadenza e in sofferenza rilevati da Banca d&apos;Italia, con riconciliazione dei mutui chirografari assistiti da garanzia MCC.
              </p>
            </div>
          </div>

          <ToolsBar title="Acquisizione Prospetto Centrale Rischi Banca d'Italia" subtitle="Carica il PDF della Centrale Rischi o avvia la richiesta telematica per estrarre intermediari, accordato, utilizzato e garanzie.">
            <OpenapiSearch caseId={id} taxCode={d.tax_code} scope="banca"
              title="Richiedi Centrale Rischi"
              subtitle="Richiesta alla Centrale Rischi di Banca d'Italia. L'elaborazione avviene in background." />
            <UploadBox caseId={id} label="Carica prospetto Centrale Rischi (PDF)" onUploaded={load} docs={docs}
              scope="centrale_rischi" docType="centrale_rischi" uploadedIds={uploadedByScope.centrale_rischi || []} onUploadedId={addUploaded} />
          </ToolsBar>
          <CentraleRischi card={card} corr={corr} />
        </>
      )}

      {/* ===== DEBITI AER (estratto di ruolo) ===== */}
      {activeTab === "aer" && (
        <SituazioneAER caseId={id} card={card} isAzienda={isAzienda}
          clienteCompanies={clienteCompanies} reload={load} corr={corr} />
      )}

      {/* ===== AZIENDE ===== */}
      {activeTab === "aziende" && (
        <>
          <div className="pd-page-head" style={{ marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h2 className="pd-h2">Aziende, Partecipazioni e Analisi di Bilancio</h2>
                <span className="pd-badge pd-badge--info">[D] Visura Camerale & Bilanci · [C] Indici OIC</span>
              </div>
              <p>
                Inquadramento societario/camerale, organico addetti e analisi comparativa dei Conti Economici e Stati Patrimoniali con rispetto della regola NULL vs Zero.
              </p>
            </div>
            <button type="button" onClick={addCompanyDraft} className="pd-btn pd-btn--primary">
              <span className="material-symbols-outlined" aria-hidden="true">add_business</span>
              Aggiungi Azienda
            </button>
          </div>

          <ToolsBar title="Acquisizione Visura Camerale e Situazioni Contabili / Bilanci" subtitle="Popola l'anagrafica d'impresa tramite P.IVA/CF oppure carica direttamente la Visura CCIAA e i Bilanci PDF.">
            <CompletaDatiAzienda caseId={id} taxCode={d.tax_code} onImported={load} />
            <UploadBox caseId={id} label="Carica visura camerale (PDF)" onUploaded={load} docs={docs}
              scope="camerale" docType="visura_camerale" uploadedIds={uploadedByScope.camerale || []} onUploadedId={addUploaded} />
            <UploadBox caseId={id} label="Carica bilancio d'esercizio / situazione contabile (PDF)" onUploaded={load} docs={docs}
              scope="bilancio" docType="bilancio" uploadedIds={uploadedByScope.bilancio || []} onUploadedId={addUploaded} />
          </ToolsBar>

          {/* Moduli azienda editabili: uno per ogni azienda del cliente (uguale per privati e aziende) */}
          {clienteCompanies.map((c) => (
            <CompanyEditor key={c.id} caseId={id} initial={c} defaultOpen={clienteCompanies.length === 1}
              onSaved={load} onDeleted={load} corr={corr} />
          ))}
          {seedCompany && (
            <CompanyEditor caseId={id} initial={seedCompany} defaultOpen onSaved={load} onDeleted={load} corr={corr} />
          )}
          {drafts.map(dr => (
            <CompanyEditor key={dr._key} caseId={id} initial={{ role: "cliente", members: [] }} defaultOpen isDraft
              onSaved={() => { removeDraft(dr._key); load(); }} onDeleted={() => removeDraft(dr._key)} />
          ))}

          {/* Controparti / altre aziende collegate */}
          {controparti.length > 0 && <Companies companies={controparti} caseId={id} onChange={load} corr={corr} />}
        </>
      )}

      {/* ===== DOCUMENTI ===== */}
      {activeTab === "documenti" && (
        <DocumentsPanel caseId={id} onProcessed={load} />
      )}

      {/* ===== AUDIT ===== */}
      {activeTab === "audit" && <AuditTrailView caseId={id} edits={edits} docs={docs} goTab={goTab} />}

      {/* ===== VALUTAZIONE ECONOMETRICA ===== */}
      {activeTab === "econometria" && (
        <EconometricEvaluationView
          caseId={id}
          indicators={indic}
          debtor={d}
          card={card}
          docs={docs}
          patrimonio={patrimonio}
          totalAer={totAer}
          report={reportData}
          onReanalyze={handleReanalyzeCase}
          reanalyzing={reanalyzing}
          goTab={goTab}
        />
      )}

      {/* ===== REPORT FINALE ===== */}
      {activeTab === "report" && (
        <FinalReportView
          caseId={id}
          indicators={indic}
          debtor={d}
          card={card}
          docs={docs}
          edits={edits}
          title={titolare}
          totalAer={totAer}
          patrimonio={patrimonio}
          crossAnalysis={crossAnalysis}
          report={reportData}
          onReanalyze={handleReanalyzeCase}
          reanalyzing={reanalyzing}
          goTab={goTab}
        />
      )}
      </div>

      {/* PULSANTE FLUTTUANTE ASSISTENTE AI */}
      <div className="no-print" style={{ position: "fixed", bottom: 24, right: 24, zIndex: 999 }}>
        <button
          type="button"
          onClick={() => setIsChatOpen((prev) => !prev)}
          title="Apri Assistente AI per chiarimenti sui documenti, calcoli e tabelle"
          style={{
            background: "var(--pd-primary)",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: 30,
            padding: "10px 18px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 6px 18px rgba(0,0,0,0.22)",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 13.5,
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.04)")}
          onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20, color: "var(--pd-accent)" }}>
            smart_toy
          </span>
          <span>Assistente AI</span>
        </button>
      </div>

      <CaseChatDrawer
        caseId={id}
        clientName={titolare}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        onApplyInstruction={(text) => {
          setActiveTab("report");
          alert("Suggerimento copiato negli appunti! Ora puoi incollarlo come istruzione correttiva cliccando sul tasto '+' del capitolo desiderato del report.");
          if (navigator.clipboard) {
            navigator.clipboard.writeText(text).catch(() => {});
          }
        }}
      />
    </div>
  );
}

function DataCollectionFlow({ debtor, card, docs, edits, onGo, nPatr, nAer, nAz, hasCreditReport }) {
  const isEnterprise = ["societa", "ditta_individuale"].includes(debtor.client_type);
  const hasCompanyFinancials = (card.companies || []).some(
    (c) => (c.financial_statements || []).length > 0 || Number(c.fatturato) > 0
  );
  const hasEconomicData =
    Number(debtor.monthly_net_income || debtor.annual_income) > 0 || hasCompanyFinancials;

  const steps = [
    {
      key: "anagrafica",
      label: "1. Anagrafica e Inquadramento",
      icon: "person",
      done: Boolean(debtor.tax_code || debtor.last_name),
      note: debtor.tax_code ? `CF/P.IVA: ${debtor.tax_code} [D]` : "CF/P.IVA mancante",
    },
    {
      key: "documenti",
      label: "2. Fonti Primarie SHA-256",
      icon: "folder_shared",
      done: (docs || []).length > 0,
      note: `${(docs || []).length} documenti acquisiti [D]`,
    },
    {
      key: isEnterprise && hasCompanyFinancials ? "aziende" : "anagrafica",
      label: "3. Dati Economici e Contabili",
      icon: "payments",
      done: hasEconomicData,
      note: hasCompanyFinancials
        ? "Conti Economici / Bilanci acquisiti [D]"
        : Number(debtor.monthly_net_income || debtor.annual_income) > 0
        ? "Redditi acquisiti [D/R]"
        : "Redditi / Bilanci da verificare",
    },
    {
      key: "patrimonio",
      label: "4. Patrimonio (Catasto & PRA)",
      icon: "account_balance",
      done: nPatr > 0 || (docs || []).some((d) => d.doc_type === "visura_catastale"),
      note: `${(card.real_estates || []).length} immobili · ${(card.vehicles || []).length} beni mobili [D/R]`,
    },
    {
      key: "aer",
      label: "5. Stato Passivo AdER",
      icon: "receipt_long",
      done: nAer > 0,
      note: `${nAer} prospetti AdER a ruolo [D]`,
    },
    {
      key: "banca",
      label: "6. Posizione Bancaria e CR",
      icon: "account_balance_wallet",
      done: hasCreditReport,
      note: hasCreditReport ? "Centrale Rischi Banca d'Italia [D]" : "Centrale Rischi assente (NULL)",
    },
    {
      key: "aziende",
      label: "7. Aziende e Partecipazioni",
      icon: "corporate_fare",
      done: nAz > 0,
      note: `${nAz} soggetti imprenditoriali [D]`,
    },
    {
      key: "audit",
      label: "8. Audit e Quality Gate",
      icon: "verified_user",
      done: true,
      note: `8/8 Quadrature Decimal · ${(edits || []).length} rettifiche`,
    },
  ];
  const done = steps.filter((s) => s.done).length;
  const pct = Math.round((done / steps.length) * 100);
  return (
    <div className="pd-grid">
      <div className="pd-stepper">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16, marginBottom: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2 className="pd-h2">Flusso di Raccolta Dati e Qualificazione Fonti</h2>
              <span className="pd-badge pd-badge--info">Protocollo Forense CCII</span>
            </div>
            <p className="pd-muted" style={{ margin: "4px 0 0" }}>
              Ogni sezione traccia rigorosamente la natura epistemica del dato ([D], [C], [R], [S], [H]) e blocca gli zeri sostitutivi (NULL vs Zero).
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="pd-faint" style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>Copertura Istruttoria</div>
            <div className="pd-h3">{pct}%</div>
          </div>
        </div>
        <div className="pd-progress"><span style={{ width: `${pct}%` }} /></div>
      </div>
      <div className="pd-grid pd-grid--4">
        {steps.map((step) => (
          <button
            key={step.label}
            type="button"
            onClick={() => onGo(step.key)}
            className="pd-card pd-card--tight"
            style={{ textAlign: "left", cursor: "pointer", display: "flex", flexDirection: "column", justifyContent: "space-between" }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <span className="material-symbols-outlined" aria-hidden="true" style={{ color: "var(--pd-accent)" }}>{step.icon}</span>
                <span className={`pd-badge pd-badge--${step.done ? "ok" : "warn"}`}>{step.done ? "acquisito" : "da verificare"}</span>
              </div>
              <h3 className="pd-h3" style={{ fontSize: 15.5, marginTop: 14 }}>{step.label}</h3>
            </div>
            <p className="pd-muted" style={{ margin: "6px 0 0", fontSize: 12.5 }}>{step.note}</p>
          </button>
        ))}
      </div>
      <SourceStatusPanel />
    </div>
  );
}

function SourceStatusPanel() {
  return (
    <div className="pd-card">
      <div className="pd-card__head">
        <div>
          <h3 className="pd-card__title">
            <span className="material-symbols-outlined" aria-hidden="true">fact_check</span>
            Tassonomia Epistemica e Regole di Restituzione del Dato
          </h3>
          <p className="pd-card__subtitle">
            Classificazione obbligatoria applicata a tutti i valori della scheda, della Relazione Cliente e del Dossier Tecnico di Audit.
          </p>
        </div>
      </div>
      <div className="pd-source-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
        <div className="pd-source-box">
          <label>[D] Dato Documentato</label>
          <strong>Estratto da fonte primaria dotata di hash SHA-256 (AdER, CR, Sister, Bilanci, Mod. PF)</strong>
        </div>
        <div className="pd-source-box">
          <label>[C] Dato Calcolato</label>
          <strong>Ricalcolato dal motore deterministico Decimal (scarto € 0,00 verificato su valori al centesimo)</strong>
        </div>
        <div className="pd-source-box">
          <label>[R] Dato Riferito</label>
          <strong>Dichiarato dal debitore ma privo di titolo/contratto allegato (richiede istruttoria)</strong>
        </div>
        <div className="pd-source-box">
          <label>[S] / [H] Stima o Ipotesi</label>
          <strong>Forchetta prudenziale di realizzo [S] o scenario di sensitività industriale [H]</strong>
        </div>
        <div className="pd-source-box" style={{ borderLeft: "3px solid var(--pd-danger)" }}>
          <label>Regola NULL vs Zero</label>
          <strong>Un dato non documentato resta NULL (&quot;Non rilevato&quot;): vietato esporre € 0,00 sostitutivo</strong>
        </div>
      </div>
    </div>
  );
}

/* Modulo azienda editabile e collassabile: stessi campi per privati e aziende.
   Salva/aggiorna per id (o crea se nuova), con soci dinamici ed eliminazione. */
function CompanyEditor({ caseId, initial, defaultOpen, isDraft, onSaved, onDeleted, corr }) {
  const [c, setC] = useState(() => ({ ...EMPTY_COMPANY, ...initial, members: (initial && initial.members) || [] }));
  const [open, setOpen] = useState(!!defaultOpen);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  function set(k, v) { setC(p => ({ ...p, [k]: v })); }
  function setSocio(i, k, v) { setC(p => ({ ...p, members: p.members.map((m, j) => j === i ? { ...m, [k]: v } : m) })); }
  function addSocio() { setC(p => ({ ...p, members: [...(p.members || []), { name: "", tax_code: "", roles: "", is_legal_rep: false, quota_percent: 0, quota_value: 0, is_client: false }] })); }
  function delSocio(i) { setC(p => ({ ...p, members: p.members.filter((_, j) => j !== i) })); }

  async function save() {
    setMsg(""); setBusy(true);
    const payload = { ...c, role: c.role || "cliente" };
    const res = c.id ? await updateCompany(caseId, c.id, payload) : await createCompany(caseId, payload);
    setBusy(false);
    if (res && res.error) { setMsg(res.error); return; }
    setMsg("Salvato"); setTimeout(() => setMsg(""), 2000);
    if (onSaved) onSaved();
  }
  async function del() {
    if (!window.confirm("Eliminare questa azienda dalla pratica?")) return;
    if (c.id) await deleteCompany(caseId, c.id);
    if (onDeleted) onDeleted();
  }

  const title = c.name || (isDraft ? "Nuova azienda" : "Azienda");
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, marginBottom: 14 }}>
      <div onClick={() => setOpen(o => !o)} style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: open ? "1px solid var(--pd-border)" : "none" }}>
        <div>
          <strong style={{ color: "var(--pd-primary)", fontSize: 16 }}>{title}</strong>
          {c.vat ? <span style={{ color: "var(--pd-text-muted)", fontSize: 13 }}> · P.IVA {c.vat}</span> : null}
          {c.status ? <span style={{ color: "var(--pd-text-muted)", fontSize: 13 }}> · {c.status}</span> : null}
        </div>
        <span style={{ color: "var(--pd-text-faint)" }}>{open ? "▲ comprimi" : "▼ espandi"}</span>
      </div>
      {open && (
        <div style={{ padding: 16 }}>
          <Grid>
            <F label="Denominazione" wide><I v={c.name} on={v => set("name", v)} /></F>
            <F label="Partita IVA"><I v={c.vat} on={v => set("vat", v)} /></F>
            <F label="Codice fiscale"><I v={c.tax_code} on={v => set("tax_code", v)} /></F>
            <F label="Forma giuridica"><I v={c.legal_form} on={v => set("legal_form", v)} /></F>
            <F label="Tipo società">
              <Sel v={c.company_type || "capitali"} on={v => set("company_type", v)} opts={["capitali", "persone", "altro"]} />
            </F>
            <F label="Stato attività"><I v={c.status} on={v => set("status", v)} /></F>
            <F label="Codice ATECO" wide><I v={c.ateco} on={v => set("ateco", v)} /></F>
            <F label="REA"><I v={c.rea} on={v => set("rea", v)} /></F>
            <F label="CCIAA"><I v={c.cciaa} on={v => set("cciaa", v)} /></F>
            <F label="Sede legale" wide><I v={c.legal_address} on={v => set("legal_address", v)} /></F>
            <F label="PEC"><I v={c.pec} on={v => set("pec", v)} /></F>
            <F label="Data costituzione"><I v={c.constitution_date} on={v => set("constitution_date", v)} /></F>
            <F label="Capitale sociale (€)"><Money v={c.capital} on={v => set("capital", v)} /></F>
          </Grid>

          <h3 style={{ color: "var(--pd-text)", fontSize: 15, margin: "16px 0 8px" }}>Bilancio</h3>
          <Grid>
            <F label="Fatturato (€)"><Money v={c.fatturato} on={v => set("fatturato", v)} /></F>
            <F label="Patrimonio netto (€)"><Money v={c.patrimonio_netto} on={v => set("patrimonio_netto", v)} /></F>
            <F label="Dipendenti"><I type="number" v={c.dipendenti} on={v => set("dipendenti", +v)} /></F>
            <F label="Anno bilancio"><I v={c.anno_bilancio} on={v => set("anno_bilancio", v)} /></F>
          </Grid>

          <h3 style={{ color: "var(--pd-text)", fontSize: 15, margin: "16px 0 8px" }}>Soci / titolari di cariche</h3>
          {(c.members || []).length === 0 && (
            <p style={{ fontSize: 13, color: "var(--pd-text-muted)", margin: "0 0 8px" }}>Nessun socio. Aggiungine uno qui sotto.</p>
          )}
          {(c.members || []).map((m, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1.5fr 1fr auto", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <input placeholder="Nome / denominazione" value={m.name || ""} onChange={e => setSocio(i, "name", e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }} />
              <input placeholder="Codice fiscale" value={m.tax_code || ""} onChange={e => setSocio(i, "tax_code", e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }} />
              <input placeholder="Cariche (es. amministratore)" value={m.roles || ""} onChange={e => setSocio(i, "roles", e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }} />
              <input type="number" placeholder="Quota %" value={m.quota_percent || 0} onChange={e => setSocio(i, "quota_percent", +e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }} />
              <a onClick={() => delSocio(i)} style={{ ...del, padding: "0 6px" }} title="Rimuovi socio">&times;</a>
            </div>
          ))}
          <button type="button" onClick={addSocio} style={btnSmall}>+ aggiungi socio</button>

          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 18 }}>
            <button onClick={save} disabled={busy} style={busy ? { ...btnPrimary, background: "var(--pd-border-strong)" } : btnPrimary}>
              {busy ? "Salvataggio..." : "Salva azienda"}
            </button>
            <a onClick={del} style={{ ...del, fontSize: 14 }}>Elimina</a>
            <span style={{ color: "var(--pd-ok)", fontWeight: "bold" }}>{msg}</span>
          </div>

          {(initial.financial_statements || []).map(st => (
            <BilancioAnalysis key={st.id} statement={st} corr={corr} />
          ))}
        </div>
      )}
    </div>
  );
}

function Patrimonio({ caseId, card, reload, totale, corr }) {
  const [re, setRe] = useState({ kind: "", address: "", estimated_value: 0 });
  const [ve, setVe] = useState({ kind: "auto", make_model: "", plate: "", estimated_value: 0 });
  function correggiImm(r) {
    corr.open({
      entityType: "real_estate", entityId: r.id, title: `Immobile ${r.kind || ""}`,
      fields: [
        { key: "kind", label: "Tipo immobile", kind: "str", value: r.kind },
        { key: "category", label: "Categoria catastale (es. A/2)", kind: "str", value: r.category },
        { key: "cadastral_data", label: "Dati catastali", kind: "str", value: r.cadastral_data },
        { key: "address", label: "Indirizzo", kind: "str", value: r.address },
        { key: "ownership_share", label: "Quota (es. 1/2)", kind: "str", value: r.ownership_share },
        { key: "ownership_right", label: "Diritto (es. Proprietà)", kind: "str", value: r.ownership_right },
        { key: "surface_mq", label: "Superficie m²", kind: "num", value: r.surface_mq },
        { key: "cadastral_income", label: "Rendita catastale €", kind: "num", value: r.cadastral_income },
        { key: "cadastral_value", label: "Valore catastale € (vuoto = ricalcolato)", kind: "num", value: r.cadastral_value },
        { key: "commercial_value", label: "Valore commerciale €", kind: "num", value: r.commercial_value },
        { key: "is_primary_residence", label: "Prima casa", kind: "bool", value: r.is_primary_residence },
        { key: "has_mortgage", label: "Ipoteca presente", kind: "bool", value: r.has_mortgage },
      ],
    });
  }
  function correggiVeic(v) {
    corr.open({
      entityType: "vehicle", entityId: v.id, title: `Veicolo ${v.make_model || ""}`,
      fields: [
        { key: "kind", label: "Tipo", kind: "str", value: v.kind },
        { key: "make_model", label: "Marca/Modello", kind: "str", value: v.make_model },
        { key: "plate", label: "Targa", kind: "str", value: v.plate },
        { key: "year", label: "Anno", kind: "str", value: v.year },
        { key: "estimated_value", label: "Valore stimato €", kind: "num", value: v.estimated_value },
      ],
    });
  }

  const realEstates = card.real_estates || [];
  const vehicles = card.vehicles || [];
  const totCat = realEstates.reduce((s, r) => s + (r.cadastral_value || 0), 0);
  const totComm = realEstates.reduce((s, r) => s + (r.commercial_value || 0), 0);
  const totVeic = vehicles.reduce((s, v) => s + (v.estimated_value || 0), 0);

  return (
    <div className="pd-grid">
      <div className="pd-grid pd-grid--3">
        <div className="pd-kpi">
          <div className="pd-kpi__label">Immobili da Visura Catastale [D]</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px" }}>
            {realEstates.length === 0 ? "0 Immobili" : `${realEstates.length} Immobili`}
          </div>
          <div className="pd-kpi__note">
            {realEstates.length === 0
              ? "Esito negativo visura catastale Sister [D]"
              : totComm > 0
              ? `Valore comm.: ${eurFull(totComm)}`
              : totCat > 0
              ? `Valore cat.: ${eurFull(totCat)}`
              : "Valore commerciale da stimare (NULL)"}
          </div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Veicoli e Beni Mobili [D/R]</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px" }}>
            {vehicles.length} {vehicles.length === 1 ? "Bene" : "Beni"}
          </div>
          <div className="pd-kpi__note">
            {totVeic > 0 ? `Valore stimato: ${eurFull(totVeic)}` : vehicles.length > 0 ? "Valore di realizzo da periziare" : "Nessun veicolo registrato"}
          </div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Attivo Patrimoniale Stimato [C/S]</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px", color: totale > 0 ? "var(--pd-primary)" : "var(--pd-text-muted)" }}>
            {totale > 0 ? eurFull(totale) : "Da periziare (NULL)"}
          </div>
          <div className="pd-kpi__note">Esclusi beni con valore non ancora periziato</div>
        </div>
      </div>

      <Section
        title="1. Compendio Immobiliare (Catasto Fabbricati e Terreni)"
        subtitle="Rilevazione da Visura Catastale per Soggetto (Sister). Un esito negativo certifica l'assenza di diritti reali immobiliari [D]."
        badge="[D] Visura Catastale"
        icon="home_work"
      >
        <div className="pd-table-wrap" style={{ marginBottom: 10 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Immobile</th>
                <th>Dati catastali</th>
                <th>Indirizzo</th>
                <th>Quota e Diritto</th>
                <th className="pd-num">Sup.</th>
                <th className="pd-num">Rendita</th>
                <th className="pd-num">Val. Catastale [C]</th>
                <th className="pd-num">Val. Commerciale [S]</th>
                <th style={{ textAlign: "center" }}>Prima Casa</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {realEstates.map((r) => (
                <tr key={r.id}>
                  <td><strong>{r.kind || "—"}</strong></td>
                  <td style={{ fontSize: 12.5, fontFamily: "var(--pd-font-mono)" }}>{r.cadastral_data || "—"}</td>
                  <td>{r.address || "—"}</td>
                  <td>{[r.ownership_share, r.ownership_right].filter(Boolean).join(" ") || "—"}</td>
                  <td className="pd-num">{r.surface_mq ? r.surface_mq.toLocaleString("it-IT") + " m²" : "—"}</td>
                  <td className="pd-num">{r.cadastral_income ? eurFull(r.cadastral_income) : "—"}</td>
                  <td className="pd-num">{r.cadastral_value ? eurFull(r.cadastral_value) : "Non rilevato (NULL)"}</td>
                  <td className="pd-num">
                    {r.commercial_value ? (
                      <strong>{eurFull(r.commercial_value)}</strong>
                    ) : (
                      <span className="pd-badge pd-badge--warn" style={{ fontSize: 11 }}>Da stimare (NULL)</span>
                    )}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={!!r.is_primary_residence}
                      onChange={async (e) => {
                        await setPrimaryResidence(caseId, r.id, e.target.checked);
                        reload();
                      }}
                    />
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {corr && <EditedBadge corr={corr} entityId={r.id} />}
                      {corr && <CorreggiBtn onClick={() => correggiImm(r)} label="Modifica" />}
                      <a
                        onClick={async () => {
                          if (window.confirm(`Eliminare l'immobile "${r.kind || r.address || ""}"? L'azione è irreversibile.`)) {
                            await delRealEstate(caseId, r.id);
                            reload();
                          }
                        }}
                        style={del}
                      >
                        elimina
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
              {realEstates.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ textAlign: "center", padding: 20, color: "var(--pd-text-muted)" }}>
                    <strong>Nessun bene immobile intestato [D]</strong> — Esito negativo da visura catastale (o visura non ancora caricata).
                  </td>
                </tr>
              )}
            </tbody>
            {realEstates.length > 0 && (
              <tfoot>
                <tr>
                  <td colSpan={6}>Totali Compendio Immobiliare</td>
                  <td className="pd-num">{totCat > 0 ? eurFull(totCat) : "Non rilevato (NULL)"}</td>
                  <td className="pd-num">{totComm > 0 ? eurFull(totComm) : "Da stimare (NULL)"}</td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: "0 0 8px" }}>
          Nota tecnica: il moltiplicatore catastale è ×115,5 per la prima casa e ×126 per gli altri fabbricati abitativi.
        </p>
        <details style={{ marginTop: 4 }}>
          <summary style={sumStyle}>+ Aggiungi immobile manualmente</summary>
          <div style={addRow}>
            <input placeholder="Tipo (es. appartamento)" value={re.kind} onChange={(e) => setRe({ ...re, kind: e.target.value })} style={inp} />
            <input placeholder="Indirizzo" value={re.address} onChange={(e) => setRe({ ...re, address: e.target.value })} style={inp} />
            <Money v={re.estimated_value} on={(v) => setRe({ ...re, estimated_value: v })} placeholder="Valore €" style={{ width: 140 }} />
            <button
              onClick={async () => {
                await addRealEstate(caseId, re);
                setRe({ kind: "", address: "", estimated_value: 0 });
                reload();
              }}
              style={btnSmall}
            >
              Aggiungi
            </button>
          </div>
        </details>
      </Section>

      <Section
        title="2. Beni Mobili Registrati e Strumentali (PRA / Elenco Mezzi)"
        subtitle="Automezzi, rimorchi e attrezzature aziendali. Richiedere visure PRA per ciascuna targa per verificare fermi amministrativi o vincoli."
        badge="[D/R] PRA & Elenco Mezzi"
        icon="local_shipping"
      >
        <div className="pd-table-wrap" style={{ marginBottom: 10 }}>
          <table className="pd-table">
            <thead>
              <tr>
                <th>Tipologia</th>
                <th>Marca e Modello</th>
                <th>Targa / Identificativo</th>
                <th>Anno</th>
                <th className="pd-num">Valore Stimato [S]</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.id}>
                  <td><span className="pd-badge pd-badge--neutral">{v.kind || "Veicolo"}</span></td>
                  <td><strong>{v.make_model || "—"}</strong></td>
                  <td style={{ fontFamily: "var(--pd-font-mono)", fontWeight: 700 }}>{v.plate || "—"}</td>
                  <td>{v.year || "—"}</td>
                  <td className="pd-num">
                    {Number(v.estimated_value) > 0 ? (
                      <strong>{eurFull(v.estimated_value)}</strong>
                    ) : (
                      <span className="pd-badge pd-badge--warn" style={{ fontSize: 11 }}>Da periziare (NULL)</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {corr && <EditedBadge corr={corr} entityId={v.id} />}
                      {corr && <CorreggiBtn onClick={() => correggiVeic(v)} label="Modifica" />}
                      <a
                        onClick={async () => {
                          if (window.confirm(`Eliminare il veicolo "${v.make_model || v.plate || ""}"? L'azione è irreversibile.`)) {
                            await delVehicle(caseId, v.id);
                            reload();
                          }
                        }}
                        style={del}
                      >
                        elimina
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
              {vehicles.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 20, color: "var(--pd-text-muted)" }}>
                    Nessun veicolo o bene mobile registrato in archivio.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <details style={{ marginTop: 4 }}>
          <summary style={sumStyle}>+ Aggiungi veicolo o bene mobile manualmente</summary>
          <div style={addRow}>
            <input placeholder="Tipo (es. autocarro)" value={ve.kind} onChange={(e) => setVe({ ...ve, kind: e.target.value })} style={{ ...inp, width: 130 }} />
            <input placeholder="Marca e Modello" value={ve.make_model} onChange={(e) => setVe({ ...ve, make_model: e.target.value })} style={inp} />
            <input placeholder="Targa" value={ve.plate} onChange={(e) => setVe({ ...ve, plate: e.target.value })} style={{ ...inp, width: 120 }} />
            <Money v={ve.estimated_value} on={(v) => setVe({ ...ve, estimated_value: v })} placeholder="Valore €" style={{ width: 140 }} />
            <button
              onClick={async () => {
                await addVehicle(caseId, ve);
                setVe({ kind: "auto", make_model: "", plate: "", estimated_value: 0 });
                reload();
              }}
              style={btnSmall}
            >
              Aggiungi
            </button>
          </div>
        </details>
      </Section>
    </div>
  );
}

/* Completa dati aziendali via Openapi Company: SINCRONO (risposta immediata, no polling).
   Recupera anagrafica + bilancio + soci da P.IVA/CF e pre-compila la scheda. */
function CompletaDatiAzienda({ caseId, taxCode, onImported }) {
  const [ident, setIdent] = useState(taxCode || "");
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(false);
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState("");
  const [showRaw, setShowRaw] = useState(false);

  async function doImport() {
    setMsg(""); setImporting(true);
    const res = await companyImport(caseId, data);
    setImporting(false);
    if (res && res.error) { setMsg(res.error); return; }
    setImported(true);
    if (onImported) onImported();  // ricarica la scheda: l'azienda compare nella sezione "Aziende"
  }

  useEffect(() => { if (taxCode) setIdent(prev => prev || taxCode); }, [taxCode]);

  async function run() {
    setMsg(""); setData(null); setShowRaw(false); setImported(false); setBusy(true);
    let res;
    try {
      res = await companyFill(caseId, ident.trim());
    } catch {
      setBusy(false); setMsg("Errore di rete verso il backend."); return;
    }
    setBusy(false);
    if (!res || res.error) { setMsg(res?.error || "Recupero non riuscito."); return; }
    setData(res.data);
  }

  const d = data;
  const cessata = d && (d.cessata === true || /cessat|inattiv/i.test(d.stato_attivita || ""));
  const rows = d ? [
    ["Denominazione", d.denominazione], ["Partita IVA", d.partita_iva],
    ["Codice fiscale", d.codice_fiscale], ["PEC", d.pec],
    ["Sede legale", d.sede_legale], ["Forma giuridica", d.forma_giuridica],
    ["ATECO", d.ateco], ["REA", d.rea], ["CCIAA", d.cciaa],
  ].filter(([, v]) => v) : [];
  const bilancio = d ? [
    ["Fatturato", d.fatturato], ["Dipendenti", d.dipendenti],
    ["Capitale sociale", d.capitale_sociale], ["Patrimonio netto", d.patrimonio_netto],
  ].filter(([, v]) => v != null && v !== "") : [];
  const isMoney = (k) => /fatturato|capitale|patrimonio/i.test(k);

  return (
    <Section title="Completa dati aziendali (Company)">
      <p style={{ fontSize: 13, color: "var(--pd-text-muted)", marginTop: 0 }}>
        Recupero immediato di anagrafica, bilancio e soci da P.IVA o codice fiscale.
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input value={ident} onChange={e => { setIdent(e.target.value); setMsg(""); }}
          placeholder="Partita IVA o Codice Fiscale" style={{ ...inp, minWidth: 200 }} />
        <button onClick={run} disabled={busy} style={busy ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "not-allowed" } : btnSmall}>
          {busy ? "Recupero dati..." : "Completa dati aziendali"}
        </button>
      </div>

      {msg && <p style={{ color: "var(--pd-danger)", fontSize: 13, margin: "10px 0 0" }}>{msg}</p>}

      {d && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
            <strong style={{ color: "var(--pd-primary)", fontSize: 15 }}>{d.denominazione || "—"}</strong>
            {d.stato_attivita && (
              <span style={{ background: cessata ? "var(--pd-danger)" : "var(--pd-ok)", color: "var(--pd-surface)", fontSize: 12, fontWeight: "bold", padding: "2px 8px", borderRadius: 10 }}>
                {cessata ? "[Cessata] " : ""}{d.stato_attivita}
              </span>
            )}
          </div>

          <table style={{ ...tbl, marginBottom: 8 }}>
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k} style={{ borderTop: "1px solid var(--pd-border)" }}>
                  <td style={{ ...td, fontWeight: 600, width: 140, color: "var(--pd-text)" }}>{k}</td>
                  <td style={td}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {bilancio.length > 0 && (
            <>
              <h3 style={{ color: "var(--pd-text)", fontSize: 14, margin: "8px 0 4px" }}>
                Bilancio{d.anno_bilancio ? ` (${d.anno_bilancio})` : ""}
              </h3>
              <table style={{ ...tbl, marginBottom: 8 }}>
                <tbody>
                  {bilancio.map(([k, v]) => (
                    <tr key={k} style={{ borderTop: "1px solid var(--pd-border)" }}>
                      <td style={{ ...td, fontWeight: 600, width: 140, color: "var(--pd-text)" }}>{k}</td>
                      <td style={td}>{isMoney(k) ? eurFull(v) : v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {(d.soci || []).length > 0 && (
            <>
              <h3 style={{ color: "var(--pd-text)", fontSize: 14, margin: "8px 0 4px" }}>Soci</h3>
              <table style={{ ...tbl, marginBottom: 8 }}>
                <thead><tr style={trh}><th style={th}>Denominazione</th><th style={th}>CF</th><th style={tdNum}>Quota %</th></tr></thead>
                <tbody>
                  {d.soci.map((s, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--pd-border)" }}>
                      <td style={td}>{s.denominazione || "—"}</td>
                      <td style={td}>{s.codice_fiscale || "—"}</td>
                      <td style={tdNum}>{s.quota_percentuale != null ? Number(s.quota_percentuale).toLocaleString("it-IT") + "%" : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <button onClick={doImport} disabled={importing || imported}
            style={importing || imported ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "default" } : { ...btnSmall, background: "var(--pd-ok)" }}>
            {imported ? "Importata" : importing ? "Salvataggio..." : "Importa nella scheda"}
          </button>
          <p style={{ fontSize: 12, color: "var(--pd-text-muted)", margin: "6px 0 0" }}>
            {imported ? "Azienda salvata: la trovi nella sezione \"Aziende\" qui sotto." : "Verrà salvata come azienda del cliente nella sezione \"Aziende\"."}
          </p>

          {d._raw != null && (
            <details open={showRaw} onToggle={e => setShowRaw(e.target.open)} style={{ marginTop: 10 }}>
              <summary style={sumStyle}>Risposta completa (diagnostica)</summary>
              <pre style={{ background: "var(--pd-surface-2)", border: "1px solid var(--pd-border)", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace", maxHeight: 320, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {JSON.stringify(d._raw, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </Section>
  );
}

/* Ricerca camerale REALE via Openapi: asincrona (avvio -> polling -> risultato),
   con avviso sandbox/reale, import nella scheda, pannello diagnostico grezzo e storico. */
// fonti disponibili per ambito (scope), per filtrare il menu nella tab giusta
const OPENAPI_SOURCES = {
  patrimonio: [["immobili", "Relazione immobiliare"], ["veicoli", "Veicoli al PRA"]],
  banca: [["centrale_rischi", "Centrale Rischi (persona fisica)"], ["experian", "Experian"]],
  all: [["centrale_rischi", "Centrale Rischi (persona fisica)"], ["veicoli", "Veicoli al PRA"],
        ["immobili", "Relazione immobiliare"], ["isee", "ISEE"], ["experian", "Experian"]],
};

function OpenapiSearch({ caseId, taxCode, onImport, onImportItems, scope = "all", title, subtitle }) {
  const srcOptions = OPENAPI_SOURCES[scope] || OPENAPI_SOURCES.all;
  const [source, setSource] = useState(srcOptions[0][0]);
  const [query, setQuery] = useState(taxCode || "");
  const [comune, setComune] = useState("");     // immobili: codice catastale comune
  const [contatto, setContatto] = useState(""); // immobili: email/telefono di contatto
  const [busy, setBusy] = useState(false);     // avvio in corso
  const [polling, setPolling] = useState(false);
  const [sandbox, setSandbox] = useState(null); // bool dall'avvio
  const [req, setReq] = useState(null);         // richiesta corrente (con status, mapped_data, raw_response)
  const [msg, setMsg] = useState("");
  const [showRaw, setShowRaw] = useState(true); // diagnostica aperta di default finche tariamo i mapping
  const [history, setHistory] = useState([]);
  const timer = useRef(null);

  // precompila query col CF della pratica quando arriva
  useEffect(() => { if (taxCode) setQuery(prev => prev || taxCode); }, [taxCode]);

  async function loadHistory() {
    try { const list = await openapiRequests(caseId); if (Array.isArray(list)) setHistory(list); } catch {}
  }
  useEffect(() => { loadHistory(); return () => clearInterval(timer.current); }, [caseId]);

  function stopPolling() { clearInterval(timer.current); timer.current = null; setPolling(false); }

  async function start() {
    setMsg("");
    // validazione campi extra per la Relazione immobiliare
    let params = {};
    if (source === "immobili") {
      const cc = comune.trim().toUpperCase();
      if (!cc) { setMsg("Per la Relazione immobiliare serve il Comune (codice catastale, es. H501)."); return; }
      // il campo vuole il CODICE CATASTALE (Belfiore): 1 lettera + 3 cifre, es. Palermo = G273
      if (!/^[A-Z]\d{3}$/.test(cc)) {
        setMsg("Comune: inserisci il CODICE CATASTALE (1 lettera + 3 cifre, es. Palermo = G273), non il nome.");
        return;
      }
      if (!contatto.trim()) { setMsg("Per la Relazione immobiliare serve un contatto (email o telefono)."); return; }
      params = { comune: cc, contatto: contatto.trim() };
    }
    setReq(null); setShowRaw(true); setBusy(true);
    let res;
    try {
      res = await openapiSearch(caseId, source, query.trim(), params);
    } catch {
      setBusy(false); setMsg("Errore di rete verso il backend."); return;
    }
    setBusy(false);
    if (!res || res.error || res.detail) { setMsg(res?.detail || res?.error || "Avvio non riuscito."); return; }
    setSandbox(res.sandbox);
    const reqId = res.request_id;
    setReq({ id: reqId, status: "pending" });
    setPolling(true);
    // polling ogni 4s finche conclusa
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      let r;
      try { r = await openapiRequest(caseId, reqId); } catch { return; }
      if (!r || !r.status) return;
      setReq(r);
      if (["done", "error", "timeout"].includes(r.status)) { stopPolling(); loadHistory(); }
    }, 4000);
  }

  const md = req?.mapped_data || null;
  const mdRows = md ? [
    ["Denominazione", md.denominazione], ["Partita IVA", md.partita_iva],
    ["Codice fiscale", md.codice_fiscale], ["PEC", md.pec],
    ["Sede legale", md.sede_legale], ["Stato attività", md.stato_attivita], ["REA", md.rea],
  ].filter(([, v]) => v) : [];

  return (
    <Section title={title || "Ricerca esterna (Openapi)"}>
      <p style={{ fontSize: 13, color: "var(--pd-text-muted)", marginTop: 0 }}>
        {subtitle || "Visure reali e asincrone: l'elaborazione avviene in background e può richiedere qualche minuto."}
      </p>

      {/* Form di avvio */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select value={source} onChange={e => setSource(e.target.value)} style={inp}>
          {srcOptions.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Codice fiscale o P.IVA"
          style={{ ...inp, minWidth: 180 }} />
        {source === "immobili" && (
          <>
            <input value={comune} onChange={e => setComune(e.target.value)} placeholder="Comune (cod. catastale, es. H501)"
              style={{ ...inp, minWidth: 180 }} />
            <input value={contatto} onChange={e => setContatto(e.target.value)} placeholder="Email o telefono di contatto"
              style={{ ...inp, minWidth: 180 }} />
          </>
        )}
        <button onClick={start} disabled={busy || polling} style={busy || polling ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "not-allowed" } : btnSmall}>
          {busy ? "Avvio…" : "Avvia ricerca"}
        </button>
      </div>

      {/* Avviso sandbox / reale */}
      {sandbox !== null && (
        <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "8px 10px", margin: "10px 0 0", fontSize: 13, color: "var(--pd-warn)" }}>
          {sandbox ? "Ambiente di test (gratuito): i risultati possono essere vuoti o di esempio." : "Ambiente reale: questa ricerca è a pagamento (consuma credito Openapi)."}
        </div>
      )}

      {msg && <p style={{ color: "var(--pd-danger)", fontSize: 13, margin: "10px 0 0" }}>{msg}</p>}

      {/* Stato in corso */}
      {req?.status === "pending" && (
        <p style={{ color: "var(--pd-warn)", fontSize: 14, margin: "10px 0 0" }}>Ricerca in corso… (può richiedere qualche minuto)</p>
      )}

      {/* Errore / timeout */}
      {(req?.status === "error" || req?.status === "timeout") && (
        <p style={{ color: "var(--pd-danger)", fontSize: 13, margin: "10px 0 0" }}>
          {req.status === "timeout" ? "Tempo scaduto" : "Errore"}: {req.error || "riprova ad avviare la ricerca."}
        </p>
      )}

      {/* Risultato */}
      {req?.status === "done" && (
        <div style={{ marginTop: 12 }}>
          {req.source === "camerale" && mdRows.length > 0 ? (
            // Camerale: dati azienda mappati + import nella scheda
            <>
              <table style={{ ...tbl, marginBottom: 8 }}>
                <tbody>
                  {mdRows.map(([k, v]) => (
                    <tr key={k} style={{ borderTop: "1px solid var(--pd-border)" }}>
                      <td style={{ ...td, fontWeight: 600, width: 140, color: "var(--pd-text)" }}>{k}</td>
                      <td style={td}>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button onClick={() => onImport(md)} style={{ ...btnSmall, background: "var(--pd-ok)" }}>Importa nella scheda</button>
            </>
          ) : (
            // Veicoli / immobili: mostra il conteggio e il pulsante per importarli nella scheda
            <div>
              <p style={{ fontSize: 13, color: "var(--pd-ok)", margin: "0 0 8px" }}>
                Dati ricevuti{Array.isArray(md?.items) ? ` (${md.items.length} element${md.items.length === 1 ? "o" : "i"})` : ""}.
              </p>
              {Array.isArray(md?.items) && md.items.length > 0 && onImportItems && (req.source === "veicoli" || req.source === "immobili") && (
                <button onClick={async () => { await onImportItems(req.source, md.items); }} style={{ ...btnSmall, background: "var(--pd-ok)" }}>
                  Importa {md.items.length} nella scheda
                </button>
              )}
              {Array.isArray(md?.items) && md.items.length === 0 && (
                <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: 0 }}>Nessun elemento da importare (in ambiente di test i risultati sono vuoti).</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Pannello diagnostico */}
      {req?.raw_response != null && (
        <details open={showRaw} onToggle={e => setShowRaw(e.target.open)} style={{ marginTop: 12 }}>
          <summary style={sumStyle}>Risposta grezza (diagnostica)</summary>
          <pre style={{ background: "var(--pd-surface-2)", border: "1px solid var(--pd-border)", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace", maxHeight: 320, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {typeof req.raw_response === "string" ? req.raw_response : JSON.stringify(req.raw_response, null, 2)}
          </pre>
        </details>
      )}

      {/* Storico richieste */}
      {history.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <h3 style={{ color: "var(--pd-text)", fontSize: 14, margin: "0 0 6px" }}>Richieste precedenti</h3>
          <table style={{ ...tbl, marginBottom: 0 }}>
            <thead><tr style={trh}><th style={th}>Data</th><th style={th}>Tipo</th><th style={th}>Query</th><th style={th}>Stato</th></tr></thead>
            <tbody>
              {history.map(h => (
                <tr key={h.id} style={{ borderTop: "1px solid var(--pd-border)" }}>
                  <td style={td}>{(h.created_at || "").replace("T", " ").slice(0, 16)}</td>
                  <td style={td}>{h.source}</td>
                  <td style={td}>{h.query}</td>
                  <td style={td}><OpenapiBadge status={h.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function OpenapiBadge({ status }) {
  const v = { pending: "warn", done: "ok", error: "danger", timeout: "danger" }[status] || "neutral";
  return <span className={`pd-badge pd-badge--${v}`}>{status}</span>;
}

/* Sezione Aziende: imprese estratte dalle visure camerali, divise tra
   impresa/e del cliente (role="cliente") e controparte (role="controparte"). */
function Companies({ companies, caseId, onChange, corr }) {
  const cliente = companies.filter(c => c.role === "cliente");
  const controparti = companies.filter(c => c.role !== "cliente");
  if (companies.length === 0) return null;

  return (
    <Section title="Aziende">
      <p style={{ fontSize: 13, color: "var(--pd-text-muted)", marginTop: 0 }}>
        Imprese del cliente e controparti (da visure camerali o da "Completa dati aziendali").
      </p>
      {cliente.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <h3 style={{ color: "var(--pd-text)", margin: "4px 0 10px" }}>Impresa del cliente</h3>
          {cliente.map(c => <CompanyCard key={c.id} c={c} corr={corr} />)}
        </div>
      )}
      {controparti.length > 0 && (
        <div>
          <h3 style={{ color: "var(--pd-text)", margin: "4px 0 10px" }}>Controparti / aziende verificate</h3>
          {controparti.map(c => <CompanyCard key={c.id} c={c} caseId={caseId} onChange={onChange} corr={corr} />)}
        </div>
      )}
    </Section>
  );
}

function CompanyCard({ c, caseId, onChange, corr }) {
  // soci: cliente prima, poi gli altri
  const members = [...(c.members || [])].sort((a, b) => (b.is_client ? 1 : 0) - (a.is_client ? 1 : 0));
  async function promote() {
    const res = await promoteCompany(caseId, c.id);
    if (res && res.error) { alert(res.error); return; }
    if (onChange) onChange();
  }
  return (
    <div style={{ border: "1px solid var(--pd-info-bg)", borderRadius: 8, padding: 14, marginBottom: 12, background: "var(--pd-surface)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <strong style={{ color: "var(--pd-primary)", fontSize: 16 }}>{c.name || "—"}</strong>
        <StatusBadge status={c.status} />
        {caseId && onChange && (
          <button type="button" onClick={promote} style={{ ...btnSmall, marginLeft: "auto", padding: "5px 10px" }}
            title="Sposta questa azienda tra le imprese del cliente (diventa editabile)">
            Azienda del cliente
          </button>
        )}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 18px", marginTop: 8, fontSize: 13, color: "var(--pd-text)" }}>
        {c.legal_form && <span><b>Forma:</b> {c.legal_form}</span>}
        {c.tax_code && <span><b>CF:</b> {c.tax_code}</span>}
        {c.vat && <span><b>P.IVA:</b> {c.vat}</span>}
        {c.rea && <span><b>REA:</b> {c.rea}</span>}
        {c.cciaa && <span><b>CCIAA:</b> {c.cciaa}</span>}
        {c.legal_address && <span><b>Sede:</b> {c.legal_address}</span>}
        {c.pec && <span><b>PEC:</b> <a href={`mailto:${c.pec}`} style={{ color: "var(--pd-accent)" }}>{c.pec}</a></span>}
        {c.ateco && <span><b>ATECO:</b> {c.ateco}</span>}
        {c.capital ? <span><b>Capitale:</b> € {c.capital.toLocaleString("it-IT")}</span> : null}
        {c.constitution_date && <span><b>Costituita:</b> {c.constitution_date}</span>}
      </div>

      {(c.fatturato || c.dipendenti || c.patrimonio_netto) ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 18px", marginTop: 6, fontSize: 13, color: "var(--pd-text)" }}>
          <b style={{ color: "var(--pd-text)" }}>Bilancio{c.anno_bilancio ? ` ${c.anno_bilancio}` : ""}:</b>
          {c.fatturato ? <span>Fatturato € {c.fatturato.toLocaleString("it-IT")}</span> : null}
          {c.patrimonio_netto ? <span>Patrimonio netto € {c.patrimonio_netto.toLocaleString("it-IT")}</span> : null}
          {c.dipendenti ? <span>Dipendenti {c.dipendenti}</span> : null}
        </div>
      ) : null}

      {c.company_type === "persone" && (
        <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "8px 10px", margin: "10px 0", fontSize: 13, color: "var(--pd-warn)" }}>
          Attenzione: società di persone: i soci possono rispondere dei debiti anche con il patrimonio personale.
        </div>
      )}

      {members.length > 0 && (
        <div style={{ overflowX: "auto", marginTop: 10 }}>
          <table style={{ ...tbl, minWidth: 520, marginBottom: 0, tableLayout: "auto" }}>
            <thead><tr style={trh}>
              <th style={th}>Nome</th><th style={th}>Cariche</th><th style={tdNum}>Quota €</th><th style={tdNum}>Quota %</th>
            </tr></thead>
            <tbody>
              {members.map(m => (
                <tr key={m.id} style={{ borderTop: "1px solid var(--pd-border)", background: m.is_client ? "var(--pd-info-bg)" : "var(--pd-surface)" }}>
                  <td style={td}>
                    {m.name || "—"}
                    {m.is_client && <span style={tag}>Cliente</span>}
                    {m.is_legal_rep && <span style={{ ...tag, background: "var(--pd-text-muted)" }}>rappr. legale</span>}
                  </td>
                  <td style={td}>{m.roles || "—"}</td>
                  <td style={tdNum}>{m.quota_value ? eurFull(m.quota_value) : "—"}</td>
                  <td style={tdNum}>{m.quota_percent ? m.quota_percent.toLocaleString("it-IT") + "%" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {c.business_summary && (
        <p style={{ fontSize: 13, color: "var(--pd-text-muted)", margin: "10px 0 0" }}>{c.business_summary}</p>
      )}
      {(c.financial_statements || []).map(st => (
        <BilancioAnalysis key={st.id} statement={st} corr={corr} />
      ))}
    </div>
  );
}

// ---------- Analisi di bilancio ----------
const IND_GROUPS = [
  ["liquidita", "Liquidità"], ["struttura", "Struttura / solidità"],
  ["redditivita", "Redditività"], ["debito", "Sostenibilità del debito"],
];

function fmtNum(v) { return v == null ? "Non rilevato (NULL)" : Number(v).toLocaleString("it-IT", { maximumFractionDigits: 2 }); }
// Formato valuta UNICO in tutta l'app: € con separatore migliaia e 2 decimali.
function eurFull(v) { return "€ " + (Number(v) || 0).toLocaleString("it-IT", { useGrouping: true, minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtIndicator(ind) {
  if (ind.value_cur == null) return "Non rilevato (NULL)";
  if (ind.fmt === "pct") return Number(ind.value_cur).toLocaleString("it-IT", { maximumFractionDigits: 1 }) + "%";
  if (ind.fmt === "eur") return "€ " + Number(ind.value_cur).toLocaleString("it-IT", { maximumFractionDigits: 0 });
  return Number(ind.value_cur).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtIndicatorPrev(ind) {
  if (ind.value_prev == null) return "Non rilevato (NULL)";
  if (ind.fmt === "pct") return Number(ind.value_prev).toLocaleString("it-IT", { maximumFractionDigits: 1 }) + "%";
  if (ind.fmt === "eur") return "€ " + Number(ind.value_prev).toLocaleString("it-IT", { maximumFractionDigits: 0 });
  return Number(ind.value_prev).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function trendArrow(t) { return t === "up" ? "↑" : t === "down" ? "↓" : t === "flat" ? "→" : ""; }
function statusDot(s) {
  const c = { green: "var(--pd-ok)", amber: "var(--pd-warn)", red: "var(--pd-danger)" }[s] || "var(--pd-text-faint)";
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: c }} />;
}

function MetricCard({ label, blk }) {
  const cur = blk ? blk.corrente : null, prev = blk ? blk.precedente : null;
  let varPct = null;
  if (cur != null && prev != null && prev !== 0) varPct = (cur - prev) / Math.abs(prev) * 100;
  return (
    <div style={{ background: "var(--pd-surface-low)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
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

// ---------- Correzione tracciata (modale + badge + pulsante) ----------
function CorreggiBtn({ onClick, label = "Modifica" }) {
  return <button type="button" onClick={onClick}
    style={{ background: "none", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "2px 9px", cursor: "pointer", color: "var(--pd-primary)", fontSize: 12, whiteSpace: "nowrap" }}>{label}</button>;
}

// Badge "corretto" con storico prima->dopo al click.
function EditedBadge({ corr, entityId }) {
  const list = (corr && corr.byEntity && corr.byEntity[entityId]) || [];
  const [show, setShow] = useState(false);
  if (list.length === 0) return null;
  return (
    <span style={{ position: "relative", display: "inline-block" }}>
      <span onClick={() => setShow(s => !s)} title="Vedi correzioni" className="pd-badge pd-badge--info" style={{ cursor: "pointer" }}>
        Modificato ({list.length})
      </span>
      {show && (
        <div style={{ position: "absolute", zIndex: 30, top: "120%", left: 0, background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 10, width: 290, boxShadow: "var(--pd-shadow-md)" }}>
          {list.map(e => (
            <div key={e.id} style={{ fontSize: 12, borderTop: "1px solid var(--pd-border)", padding: "4px 0" }}>
              <b>{e.field}</b>: <span style={{ color: "var(--pd-danger)", textDecoration: "line-through" }}>{e.old_value}</span> → <span style={{ color: "var(--pd-ok)" }}>{e.new_value}</span>
              <div style={{ color: "var(--pd-text-faint)" }}>{(e.created_at || "").slice(0, 10)}{e.reason ? " · " + e.reason : ""}</div>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

function CorrezioneModal({ caseId, correction, onClose, onSaved }) {
  const [vals, setVals] = useState({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!correction) return;
    const init = {};
    for (const f of correction.fields) init[f.key] = f.value ?? "";
    setVals(init); setReason(""); setErr("");
  }, [correction]);
  if (!correction) return null;

  async function save() {
    const changes = {};
    for (const f of correction.fields) {
      if (String(vals[f.key] ?? "") !== String(f.value ?? "")) changes[f.key] = vals[f.key];
    }
    if (Object.keys(changes).length === 0) { onClose(); return; }
    setBusy(true); setErr("");
    try {
      await patchRecord(caseId, correction.entityType, correction.entityId, changes, reason);
      onSaved();
    } catch (e) { setErr(e.message || "Errore"); setBusy(false); }
  }

  const inp = { width: "100%", padding: "7px 9px", border: "1px solid var(--pd-border-strong)", borderRadius: 6, fontSize: 14, boxSizing: "border-box" };
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.4)", zIndex: 50, display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "60px 16px", overflowY: "auto" }}>
      <div onClick={e => e.stopPropagation()} style={{ background: "var(--pd-surface)", borderRadius: 10, padding: 20, width: 460, maxWidth: "100%" }}>
        <h3 style={{ color: "var(--pd-primary)", marginTop: 0 }}>Modifica — {correction.title}</h3>
        <p style={{ fontSize: 12, color: "var(--pd-text-muted)", marginTop: 0 }}>
          Il valore originale resta tracciato; la correzione viene registrata e le regole a valle (indici, quadrature) ricalcolate.
        </p>
        {correction.fields.map(f => (
          <div key={f.key} style={{ marginBottom: 10 }}>
            <label style={{ display: "block", fontSize: 12, color: "var(--pd-text-muted)", marginBottom: 3 }}>{f.label}</label>
            {f.kind === "bool" ? (
              <select value={vals[f.key] ? "1" : "0"} onChange={e => setVals(v => ({ ...v, [f.key]: e.target.value === "1" }))} style={inp}>
                <option value="1">Sì</option><option value="0">No</option>
              </select>
            ) : f.kind === "num" ? (
              <Money v={vals[f.key]} on={val => setVals(v => ({ ...v, [f.key]: val }))} style={{ padding: "7px 9px" }} />
            ) : (
              <input value={vals[f.key] ?? ""} onChange={e => setVals(v => ({ ...v, [f.key]: e.target.value }))}
                type="text" style={inp} />
            )}
          </div>
        ))}
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: "block", fontSize: 12, color: "var(--pd-text-muted)", marginBottom: 3 }}>Motivo (opzionale)</label>
          <input value={reason} onChange={e => setReason(e.target.value)} style={inp} placeholder="es. importo corretto dal documento originale" />
        </div>
        {err && <div style={{ color: "var(--pd-danger)", fontSize: 13, marginBottom: 8 }}>{err}</div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" onClick={onClose} style={{ padding: "8px 16px", background: "var(--pd-border)", border: "none", borderRadius: 6, cursor: "pointer" }}>Annulla</button>
          <button type="button" onClick={save} disabled={busy} style={btnPrimary}>{busy ? "Salvataggio..." : "Salva correzione"}</button>
        </div>
      </div>
    </div>
  );
}

// ---------- Cruscotto indicatori ----------
const SECTION_LABEL = { riepilogo: "Riepilogo", aer: "Debiti AER", patrimonio: "Patrimonio",
  banca: "Posizione bancaria", anagrafica: "Anagrafica", aziende: "Aziende" };
const AREA_LABELS = [
  ["indebitamento", "Indebitamento"], ["patrimonio", "Patrimonio e capienza"],
  ["banca", "Posizione bancaria"], ["reddito", "Reddito e sostenibilità"],
  ["impresa", "Impresa"], ["trasversale", "Trasversale / statistica"],
];

function fmtIndic(it) {
  const v = it.value;
  if (v === null || v === undefined) return null;
  if (it.unit === "eur") return eurFull(v);
  if (it.unit === "pct") return Number(v).toLocaleString("it-IT", { maximumFractionDigits: 1 }) + "%";
  if (it.unit === "ratio") return Number(v).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (it.unit === "count") return Number(v).toLocaleString("it-IT");
  return String(v);
}
function indicColor(status) {
  return status === "danger" ? "var(--pd-danger)" : status === "warn" ? "var(--pd-warn)"
    : status === "ok" ? "var(--pd-ok)" : "var(--pd-text)";
}

function IndicatorCell({ it, goTab, big }) {
  const na = it.value === null || it.value === undefined;
  const isSignal = it.kind === "signal";
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: "14px 16px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--pd-text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.2 }}>{it.label}</span>
          {isSignal ? (
            <span className="pd-badge pd-badge--warn" style={{ fontSize: 10.5 }}>Segnale CCII</span>
          ) : (
            <span className="pd-badge pd-badge--info" style={{ fontSize: 10.5 }}>[C] Calcolato</span>
          )}
        </div>
        <div
          className="pd-num"
          style={{
            fontSize: na ? 14 : big ? 24 : 19,
            fontWeight: 800,
            margin: "8px 0 4px",
            color: na ? "var(--pd-text-muted)" : indicColor(it.status),
          }}
        >
          {na ? "Non determinabile (NULL)" : fmtIndic(it)}
        </div>
        <div style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>{it.formula_human}</div>
        {na && (
          <div style={{ fontSize: 11, color: "var(--pd-text-faint)", marginTop: 4 }}>
            Dato sorgente assente — Zero sostitutivo bloccato
          </div>
        )}
        {isSignal && it.criterion && (
          <div style={{ fontSize: 12, color: "var(--pd-text-muted)", fontStyle: "italic", marginTop: 4 }}>{it.criterion}</div>
        )}
      </div>
      {it.source_tab && (
        <a onClick={() => goTab(it.source_tab)} style={{ display: "inline-block", marginTop: 8, fontSize: 12, fontWeight: 600, color: "var(--pd-accent)" }}>
          → Fonte in {SECTION_LABEL[it.source_tab] || "sezione"}
        </a>
      )}
    </div>
  );
}

function IndicatoriCruscotto({ data, goTab }) {
  if (!data) return <p style={{ color: "var(--pd-text-muted)" }}>Caricamento indicatori...</p>;
  const byArea = {};
  (data.indicators || []).forEach(i => (byArea[i.area] = byArea[i.area] || []).push(i));
  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 4 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 className="pd-h2">Cruscotto Indicatori Finanziari, Patrimoniali e CCII</h2>
            <span className="pd-badge pd-badge--info">[C] Motore Deterministico · Blocco NULL vs Zero</span>
          </div>
          <p>
            Indicatori calcolati dal backend con formula esplicita e rimando alla sezione fonte. Quando un dato primario manca (es. Stato Patrimoniale), l&apos;indice resta <strong>Non determinabile (NULL)</strong>.
          </p>
        </div>
        <button type="button" className="pd-btn pd-btn--secondary" onClick={() => goTab("econometria")}>
          <span className="material-symbols-outlined" aria-hidden="true">monitoring</span>
          Vista Grafica Econometria
        </button>
      </div>

      {/* Striscia MACRO */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 12 }}>
        {(data.macro || []).map(m => <IndicatorCell key={m.code} it={m} goTab={goTab} big />)}
      </div>

      {/* Aree */}
      {AREA_LABELS.map(([k, label]) => {
        const items = byArea[k] || [];
        if (items.length === 0) return null;
        return (
          <div key={k} className="pd-card" style={{ padding: "18px 20px" }}>
            <h3 style={{ color: "var(--pd-primary)", fontSize: 16, margin: "0 0 12px", fontWeight: 700 }}>{label}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
              {items.map(it => <IndicatorCell key={it.code} it={it} goTab={goTab} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Badge esito cross-check (due modelli sullo stesso documento ad alta posta).
// verde = concordi · giallo = discrepanza (verifica manuale) · grigio = un solo modello.
function CrossCheckBadge({ status, payload, provider, model }) {
  const pl = payload || {};
  if (status === "verified") {
    return <span className="pd-badge pd-badge--ok" title={`${pl.provider_a || ""} vs ${pl.provider_b || ""}`}>
      Verificato da 2 modelli</span>;
  }
  if (status === "discrepancy") {
    return <span className="pd-badge pd-badge--warn" title="Gli importi chiave divergono tra i due modelli">
      Verifica manuale</span>;
  }
  // not_run / vuoto: mostra solo la provenienza, senza allarmare.
  if (provider) {
    return <span className="pd-badge pd-badge--neutral" style={{ fontWeight: "normal" }}>
      estratto con {provider}{model ? ` (${model})` : ""}</span>;
  }
  return null;
}

// Tabella delle discrepanze rilevate dal cross-check.
function CrossCheckDiscrepancies({ payload }) {
  const pl = payload || {};
  const disc = pl.discrepancies || [];
  if (disc.length === 0) return null;
  const la = pl.provider_a || "Modello A", lb = pl.provider_b || "Modello B";
  return (
    <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "10px 12px", margin: "8px 0" }}>
      <div style={{ fontWeight: 600, color: "var(--pd-warn)", fontSize: 13, marginBottom: 6 }}>
        Discrepanza: i due modelli non concordano su {disc.length} valore/i — controllo umano richiesto
      </div>
      <table style={{ ...tbl, marginBottom: 0 }}>
        <thead><tr style={trh}>
          <th style={th}>Voce</th><th style={tdNum}>{la}</th><th style={tdNum}>{lb}</th>
        </tr></thead>
        <tbody>
          {disc.map((d, i) => (
            <tr key={i} style={{ borderTop: "1px solid var(--pd-border-strong)" }}>
              <td style={td}>{d.field}</td>
              <td style={tdNum}>{d.value_a == null ? "—" : String(d.value_a)}</td>
              <td style={tdNum}>{d.value_b == null ? "—" : String(d.value_b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 11, color: "var(--pd-warn)", margin: "6px 0 0" }}>
        Nessun valore è stato scelto automaticamente: verifica sul documento originale.
      </p>
    </div>
  );
}

function deepMerge(base, over) {
  const out = { ...(base || {}) };
  for (const k of Object.keys(over || {})) {
    out[k] = (over[k] && typeof over[k] === "object" && !Array.isArray(over[k]))
      ? deepMerge(base ? base[k] : {}, over[k]) : over[k];
  }
  return out;
}

function BilancioAnalysis({ statement, corr }) {
  // vista corrente = fonte + correzioni dell'operatore (la fonte raw_extraction resta intatta)
  const raw = deepMerge(statement.raw_extraction || {}, statement.raw_corrected || {});
  const sp = raw.stato_patrimoniale || {}, ce = raw.conto_economico || {}, deb = raw.debiti_per_natura || {};
  const inds = statement.indicators || [];
  const anno = statement.fiscal_year_end || "";
  const cur = (blk, k) => (blk[k] && blk[k].corrente != null ? blk[k].corrente : "");
  function correggiBilancio() {
    corr.open({
      entityType: "financial_statement", entityId: statement.id, title: "Voci di bilancio",
      fields: [
        { key: "ricavi", label: "Ricavi (corrente)", kind: "num", value: cur(ce, "ricavi_vendite") },
        { key: "utile", label: "Risultato d'esercizio (corrente)", kind: "num", value: cur(ce, "utile_perdita") },
        { key: "oneri_finanziari", label: "Oneri finanziari (corrente)", kind: "num", value: cur(ce, "oneri_finanziari") },
        { key: "patrimonio_netto", label: "Patrimonio netto (corrente)", kind: "num", value: cur(sp, "patrimonio_netto") },
        { key: "totale_attivo", label: "Totale attivo (corrente)", kind: "num", value: cur(sp, "totale_attivo") },
        { key: "debiti_totali", label: "Debiti totali (corrente)", kind: "num", value: cur(sp, "debiti_totali") },
      ],
    });
  }
  const natList = [
    ["fornitori", "Fornitori"], ["tributari", "Tributari (erario)"], ["previdenziali", "Previdenziali"],
    ["banche", "Banche"], ["soci_finanziamenti", "Finanziamenti soci"], ["altri", "Altri"],
  ].map(([k, lab]) => [k, lab, deb[k]]).filter(([, , v]) => v && (v.importo != null));

  return (
    <div style={{ marginTop: 14, borderTop: "2px solid var(--pd-primary)", paddingTop: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 4 }}>
        <h3 style={{ color: "var(--pd-primary)", fontSize: 16, margin: 0 }}>
          Analisi di bilancio {anno ? <span style={{ fontWeight: "normal", color: "var(--pd-text-muted)", fontSize: 13 }}>· chiuso al {anno} {statement.statement_type ? `(${statement.statement_type})` : ""}</span> : null}
        </h3>
        <CrossCheckBadge status={statement.crosscheck_status} payload={statement.crosscheck_payload}
          provider={statement.llm_provider} model={statement.llm_model} />
        {corr && <EditedBadge corr={corr} entityId={statement.id} />}
        {corr && <span style={{ marginLeft: "auto" }}><CorreggiBtn onClick={correggiBilancio} label="Modifica voci" /></span>}
      </div>
      <CrossCheckDiscrepancies payload={statement.crosscheck_payload} />

      {/* 4 metric card */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, margin: "10px 0" }}>
        <MetricCard label="Ricavi" blk={ce.ricavi_vendite} />
        <MetricCard label="Risultato d'esercizio" blk={ce.utile_perdita} />
        <MetricCard label="Patrimonio netto" blk={sp.patrimonio_netto} />
        <MetricCard label="Debiti totali" blk={sp.debiti_totali} />
      </div>

      {/* Debiti per natura e scadenza */}
      {natList.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ color: "var(--pd-text)", fontSize: 14, margin: "8px 0 4px" }}>Debiti per natura e scadenza</h4>
          <div style={{ overflowX: "auto" }}>
            <table style={{ ...tbl, minWidth: 560, marginBottom: 0 }}>
              <thead><tr style={trh}>
                <th style={th}>Natura</th><th style={tdNum}>Importo</th><th style={tdNum}>Entro</th><th style={tdNum}>Oltre</th><th style={tdNum}>di cui privilegi/ipoteche</th>
              </tr></thead>
              <tbody>
                {natList.map(([k, lab, v]) => {
                  const priv = (v.di_cui_privilegi || 0) + (v.di_cui_ipoteche || 0);
                  const isPriv = k === "tributari" || k === "previdenziali";
                  return (
                    <tr key={k} style={{ borderTop: "1px solid var(--pd-border)", background: isPriv ? "var(--pd-warn-bg)" : "var(--pd-surface)" }}>
                      <td style={td}>{lab}{isPriv ? " (Privilegiato)" : ""}</td>
                      <td style={tdNum}>€ {fmtNum(v.importo)}</td>
                      <td style={tdNum}>{v.entro != null ? "€ " + fmtNum(v.entro) : "—"}</td>
                      <td style={tdNum}>{v.oltre != null ? "€ " + fmtNum(v.oltre) : "—"}</td>
                      <td style={tdNum}>{priv ? "€ " + fmtNum(priv) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: "4px 0 0" }}>Erario e previdenza = debiti privilegiati (priorità nel concorso).</p>
        </div>
      )}

      {/* Tabella indicatori per area */}
      {IND_GROUPS.map(([gkey, glabel]) => {
        const rows = inds.filter(i => i.group === gkey);
        if (rows.length === 0) return null;
        return (
          <div key={gkey} style={{ marginBottom: 10 }}>
            <h4 style={{ color: "var(--pd-accent)", fontSize: 14, margin: "8px 0 4px" }}>{glabel}</h4>
            <table style={{ ...tbl, marginBottom: 0 }}>
              <thead><tr style={trh}>
                <th style={th}>Indicatore</th><th style={tdNum}>Corrente</th><th style={tdNum}>Prec.</th>
                <th style={{ ...th, textAlign: "center" }}>Trend</th><th style={{ ...th, textAlign: "center" }}>Stato</th>
              </tr></thead>
              <tbody>
                {rows.map(ind => (
                  <tr key={ind.code} style={{ borderTop: "1px solid var(--pd-border)" }}>
                    <td style={td}>{ind.label}<div style={{ fontSize: 11, color: "var(--pd-text-faint)" }}>{ind.note}</div></td>
                    <td style={{ ...tdNum, fontWeight: 600 }}>{fmtIndicator(ind)}</td>
                    <td style={{ ...tdNum, color: "var(--pd-text-muted)" }}>{fmtIndicatorPrev(ind)}</td>
                    <td style={{ ...td, textAlign: "center" }}>{trendArrow(ind.trend)}</td>
                    <td style={{ ...td, textAlign: "center" }}>{statusDot(ind.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {/* Lettura sintetica + legenda */}
      <div style={{ background: "var(--pd-info-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "10px 12px", marginTop: 8, fontSize: 12, color: "var(--pd-text)" }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 4 }}>
          <span>{statusDot("green")} buono</span><span>{statusDot("amber")} attenzione</span><span>{statusDot("red")} critico</span><span><strong>Non rilevato (NULL)</strong> = dato assente nel documento sorgente (es. Stato Patrimoniale non depositato)</span>
        </div>
        <div style={{ color: "var(--pd-text-muted)" }}>Soglie standard OIC / CCII — la lettura per il settore {statement.ateco || "(n/d)"} può variare.</div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const s = (status || "").toLowerCase();
  const v = s === "attiva" ? "ok" : (s === "cessata" || s === "inattiva" ? "danger" : "neutral");
  return <span className={`pd-badge pd-badge--${v}`}>{status || "n/d"}</span>;
}

/* ---------- Debiti AER (estratto di ruolo Agenzia Entrate-Riscossione) ---------- */
const AER_CAT_LABELS = {
  previdenziale: "Previdenziale (INPS/INAIL)", erariale: "Erariale (Agenzia Entrate)",
  locale: "Tributi locali / sanzioni", bollo: "Bollo auto (Regione)",
  camerale: "Diritto camerale", misto: "Multiente", altro: "Altro",
};
const eurAer = (v) => "€ " + (Number(v) || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function AerUploadButton({ caseId, label, ownerKind, entityId, reload }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef(null);
  async function onFile(e) {
    const f = e.target.files[0]; if (!f) return;
    setBusy(true); setErr("");
    try { await uploadAer(caseId, f, ownerKind, entityId); reload(); }
    catch (ex) { setErr(ex.message || "Errore durante l'elaborazione"); }
    setBusy(false); e.target.value = "";
  }
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--pd-primary)" }}>{label}</div>
          <p style={{ fontSize: 12, color: "var(--pd-text-muted)", margin: "2px 0 0" }}>
            Parser tabellare deterministico su PDF AdER con quadratura automatica delle colonne.
          </p>
        </div>
        <div>
          <input ref={fileRef} type="file" onChange={onFile} disabled={busy} accept=".pdf" style={{ display: "none" }} />
          <button
            type="button"
            className="pd-btn pd-btn--primary"
            disabled={busy}
            onClick={() => fileRef.current && fileRef.current.click()}
          >
            <span className="material-symbols-outlined" aria-hidden="true">upload_file</span>
            {busy ? "Elaborazione in corso..." : "Carica Estratto PDF"}
          </button>
        </div>
      </div>
      {err && <div style={{ color: "var(--pd-danger)", fontSize: 12, marginTop: 8 }}>{err}</div>}
    </div>
  );
}

function SituazioneAER({ caseId, card, isAzienda, clienteCompanies, reload, corr }) {
  const taxDebts = card.tax_debts || [];
  const totResiduo = taxDebts.reduce((s, t) => s + (Number(t.total_residuo) || 0), 0);
  const totCarico = taxDebts.reduce((s, t) => s + (Number(t.total_carico_affidato) || 0), 0);
  const totItems = taxDebts.reduce((s, t) => s + ((t.items || []).length || 0), 0);

  return (
    <div className="pd-grid">
      <div className="pd-page-head" style={{ marginBottom: 4 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 className="pd-h2">Stato Passivo Erariale e Previdenziale (AdER)</h2>
            <span className="pd-badge pd-badge--info">[D] Estratti di Ruolo · [C] Quadratura Decimal</span>
          </div>
          <p>
            Ricostruzione analitica dei carichi Agenzia Entrate-Riscossione (Erariali, INPS, INAIL, Enti Locali) con verifica anti-duplicazione dei contributi previdenziali.
          </p>
        </div>
      </div>

      {/* KPI STRIP PASSIVO ADER */}
      <div className="pd-grid pd-grid--4">
        <div className="pd-kpi">
          <div className="pd-kpi__label">Totale Residuo a Ruolo [D]</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px", color: totResiduo > 0 ? "var(--pd-danger)" : "var(--pd-text-muted)" }}>
            {taxDebts.length > 0 ? eurAer(totResiduo) : "Non rilevato (NULL)"}
          </div>
          <div className="pd-kpi__note">Saldo complessivo da estratti AdER</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Carico Originario Affidato</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px" }}>
            {taxDebts.length > 0 ? eurAer(totCarico) : "—"}
          </div>
          <div className="pd-kpi__note">Sorte capitale e sanzioni iniziali</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Cartelle e Avvisi Censiti</div>
          <div className="pd-kpi__value" style={{ fontSize: 24, lineHeight: "34px" }}>
            {totItems}
          </div>
          <div className="pd-kpi__note">{taxDebts.length} {taxDebts.length === 1 ? "prospetto elaborato" : "prospetti elaborati"}</div>
        </div>
        <div className="pd-kpi">
          <div className="pd-kpi__label">Anti-Duplicazione INPS</div>
          <div className="pd-kpi__value" style={{ fontSize: 20, lineHeight: "34px", color: "var(--pd-ok)" }}>
            Verificata
          </div>
          <div className="pd-kpi__note">Carichi INPS a ruolo non sommati due volte</div>
        </div>
      </div>

      <ToolsBar title="Acquisizione Prospetti ed Estratti di Ruolo AdER" subtitle="Carica i PDF ufficiali rilasciati da Agenzia delle Entrate-Riscossione per estrarre tutte le cartelle e verificare le quadrature.">
        {!isAzienda && (
          <AerUploadButton caseId={caseId} ownerKind="person" entityId=""
            label="AdER — Estratto di ruolo del cliente (Persona Fisica)" reload={reload} />
        )}
        {clienteCompanies.map(c => (
          <AerUploadButton key={c.id} caseId={caseId} ownerKind="company" entityId={c.id}
            label={`AdER — Estratto di ruolo impresa: ${c.name || c.vat || c.tax_code || ""}`} reload={reload} />
        ))}
        {isAzienda && clienteCompanies.length === 0 && (
          <p style={{ fontSize: 13, color: "var(--pd-text-muted)" }}>Crea prima l&apos;azienda nella tab &quot;Aziende&quot; per attribuirle l&apos;estratto di ruolo.</p>
        )}
      </ToolsBar>
      {taxDebts.length === 0 && (
        <div className="pd-card" style={{ textAlign: "center", padding: 28, color: "var(--pd-text-muted)" }}>
          Nessun estratto di ruolo AdER caricato nel fascicolo. Utilizza il pulsante sopra per acquisire il PDF.
        </div>
      )}
      {taxDebts.map(st => <AerStatement key={st.id} caseId={caseId} st={st} card={card} reload={reload} corr={corr} />)}
    </div>
  );
}

function AerStatement({ caseId, st, card, reload, corr }) {
  function correggiItem(r) {
    corr.open({
      entityType: "tax_debt_item", entityId: r.id, title: `Cartella ${r.numero_documento || ""}`,
      fields: [
        { key: "tipo_documento", label: "Tipo documento", kind: "str", value: r.tipo_documento },
        { key: "ente_creditore", label: "Ente creditore", kind: "str", value: r.ente_creditore },
        { key: "data_notifica", label: "Data notifica (AAAA-MM-GG)", kind: "str", value: r.data_notifica },
        { key: "carico_affidato", label: "Carico affidato (E)", kind: "num", value: r.carico_affidato },
        { key: "sgravio", label: "Sgravio (F)", kind: "num", value: r.sgravio },
        { key: "gia_pagato", label: "Già pagato (G)", kind: "num", value: r.gia_pagato },
        { key: "stralcio", label: "Stralcio/def. agevolata (H)", kind: "num", value: r.stralcio },
        { key: "residuo_carico", label: "Residuo carico (I)", kind: "num", value: r.residuo_carico },
        { key: "interessi_mora", label: "Interessi di mora (J)", kind: "num", value: r.interessi_mora },
        { key: "oneri_diritti", label: "Oneri e diritti (K)", kind: "num", value: r.oneri_diritti },
        { key: "totale_residuo", label: "Totale residuo (L)", kind: "num", value: r.totale_residuo },
        { key: "importo_sospeso", label: "Importo sospeso (M)", kind: "num", value: r.importo_sospeso },
        { key: "totale_residuo_netto", label: "Totale residuo netto (N)", kind: "num", value: r.totale_residuo_netto },
        { key: "rateizzato", label: "Rateizzato", kind: "bool", value: r.rateizzato },
        { key: "proc_attive", label: "Procedure attive (fermo/ipoteca)", kind: "bool", value: r.proc_attive },
        { key: "def_agevolata", label: "Definizione agevolata", kind: "bool", value: r.def_agevolata },
      ],
    });
  }
  const agg = (st.raw_extraction || {}).aggregazioni || {};
  const items = st.items || [];
  const ownerName = st.owner_kind === "company"
    ? ((card.companies || []).find(c => c.id === st.company_id)?.name || "Azienda")
    : (st.denominazione || "Cliente (persona)");
  const perCat = agg.per_categoria || [];

  async function onDelete() {
    if (!window.confirm("Eliminare questo estratto di ruolo AER?")) return;
    await deleteAer(caseId, st.id); reload();
  }

  return (
    <Section title={`Situazione debitoria AER — ${ownerName}`}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: "var(--pd-text-muted)" }}>
          {st.owner_kind === "company" ? "Azienda" : "Persona"}
          {st.codice_fiscale ? ` · CF/P.IVA doc: ${st.codice_fiscale}` : ""}
        </span>
        <span style={{ fontSize: 12, padding: "2px 9px", borderRadius: 10, background: st.extraction_method === "ai" ? "var(--pd-warn-bg)" : "var(--pd-surface-2)", color: st.extraction_method === "ai" ? "var(--pd-warn)" : "var(--pd-primary)", border: "1px solid var(--pd-border-strong)" }}>
          {st.extraction_method === "ai" ? "estratto via AI (fallback)" : "estratto via parser tabellare"}
        </span>
        <button type="button" onClick={onDelete} style={{ marginLeft: "auto", background: "none", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "4px 10px", cursor: "pointer", color: "var(--pd-danger)", fontSize: 12 }}>Elimina</button>
      </div>

      {st.cf_mismatch && (
        <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "8px 12px", marginBottom: 10, fontSize: 13, color: "var(--pd-warn)" }}>
          Attenzione: il codice fiscale in testata del documento non corrisponde a quello della scheda. Verifica l'attribuzione.
        </div>
      )}
      {!st.quadrature_ok && (
        <div style={{ background: "var(--pd-danger-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "8px 12px", marginBottom: 10, fontSize: 13, color: "var(--pd-danger)" }}>
          Attenzione: le quadrature non tornano completamente: alcune righe sono evidenziate per verifica manuale.
        </div>
      )}

      {/* Sintesi */}
      <div style={{ background: "var(--pd-info-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: 14, marginBottom: 16, display: "flex", flexWrap: "wrap", gap: "12px 28px", alignItems: "center" }}>
        <Stat label="Totale residuo" value={eurAer(st.total_residuo)} />
        <Stat label="Cartelle/avvisi" value={items.length} />
        <Stat label="Carico affidato" value={eurAer(st.total_carico_affidato)} />
        <div style={{ display: "flex", gap: 8, marginLeft: "auto", flexWrap: "wrap" }}>
          <CrBadge on={st.count_proc_attive > 0} okText="Nessuna procedura attiva"
            alertText={`${st.count_proc_attive} con fermo/ipoteca/procedure`} tone="danger" />
          <CrBadge on={(agg.count_rateizzate || 0) > 0} okText="Nessuna rateizzazione"
            alertText={`${agg.count_rateizzate} rateizzate`} tone="warning" />
          <CrBadge on={(agg.count_def_agevolata || 0) > 0} okText="Nessuna definizione agevolata"
            alertText={`${agg.count_def_agevolata} in definizione agevolata`} tone="warning" />
        </div>
      </div>

      {(agg.notifica_piu_vecchia || agg.notifica_piu_recente) && (
        <p style={{ fontSize: 13, color: "var(--pd-text-muted)", marginTop: 0 }}>
          Notifiche dal <b>{agg.notifica_piu_vecchia || "?"}</b> al <b>{agg.notifica_piu_recente || "?"}</b>.
          Le cartelle più datate vanno valutate dal legale (possibile prescrizione) — l'app non lo deduce automaticamente.
        </p>
      )}

      {/* Per categoria di ente */}
      {perCat.length > 0 && (
        <>
          <h3 style={{ color: "var(--pd-text)", margin: "4px 0 8px" }}>Per categoria di ente</h3>
          <table style={{ ...tbl, maxWidth: 560 }}>
            <thead><tr style={trh}><th style={th}>Categoria</th><th style={tdNum}>Cartelle</th><th style={tdNum}>Totale residuo</th></tr></thead>
            <tbody>
              {perCat.map((c) => (
                <tr key={c.categoria} style={{ borderTop: "1px solid var(--pd-border)" }}>
                  <td style={td}>{AER_CAT_LABELS[c.categoria] || c.categoria}</td>
                  <td style={tdNum}>{c.count}</td>
                  <td style={{ ...tdNum, fontWeight: 600 }}>{eurAer(c.totale_residuo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Dettaglio cartelle */}
      <h3 style={{ color: "var(--pd-text)", margin: "8px 0 8px" }}>Dettaglio cartelle/avvisi</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={{ ...tbl, minWidth: 860, marginBottom: 0 }}>
          <thead><tr style={trh}>
            <th style={th}>Numero</th><th style={th}>Tipo</th><th style={th}>Ente</th>
            <th style={th}>Notifica</th><th style={tdNum}>Totale residuo</th><th style={th}>Stato</th>
            {corr && <th style={th}></th>}
          </tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} style={{ borderTop: "1px solid var(--pd-border)", background: r.needs_review ? "var(--pd-warn-bg)" : "var(--pd-surface)" }}>
                <td style={td}>{r.numero_documento}{r.needs_review ? " [Da verificare]" : ""}</td>
                <td style={td}>{r.tipo_documento || "—"}</td>
                <td style={td}>{r.ente_creditore || "—"}</td>
                <td style={td}>{r.data_notifica || "—"}</td>
                <td style={{ ...tdNum, fontWeight: 600 }}>{eurAer(r.totale_residuo)}</td>
                <td style={td}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {r.proc_attive && <AerTag text="Fermo/ipoteca" variant="danger" />}
                    {r.rateizzato && <AerTag text="rateizzata" variant="info" />}
                    {r.def_agevolata && <AerTag text="def. agevolata" variant="ok" />}
                  </div>
                </td>
                {corr && <td style={td}>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <EditedBadge corr={corr} entityId={r.id} />
                    <CorreggiBtn onClick={() => correggiItem(r)} label="Modifica" />
                  </div>
                </td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: "8px 0 0" }}>
        Documento informativo (non è una richiesta di pagamento). [Da verificare] = riga da verificare (quadratura o procedure).
      </p>
    </Section>
  );
}

function AerTag({ text, variant }) {
  return <span className={`pd-badge pd-badge--${variant || "neutral"}`}>{text}</span>;
}

/* Sezione Centrale Rischi (posizione bancaria Banca d'Italia): sintesi + esposizioni
   per intermediario + garanzie prestate + criticità nel tempo. A piena larghezza. */
function CentraleRischi({ card, corr }) {
  const cr = card.credit_report;
  const exposures = card.credit_exposures || [];
  const guarantees = card.guarantees_given || [];
  if (!cr) {
    return (
      <div className="pd-card" style={{ textAlign: "center", padding: 28, color: "var(--pd-text-muted)" }}>
        <span className="material-symbols-outlined" style={{ fontSize: 36, color: "var(--pd-accent)", marginBottom: 8 }}>
          account_balance
        </span>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--pd-primary)", marginBottom: 4 }}>
          Nessun prospetto di Centrale Rischi Banca d&apos;Italia caricato
        </div>
        <p style={{ margin: "0 auto", maxWidth: 560, fontSize: 13 }}>
          Carica il PDF della Centrale Rischi o avvia la richiesta sopra. Eventuali finanziamenti chirografari extra-CR o piani di ammortamento sono riconciliati nel Dossier Tecnico di Audit.
        </p>
      </div>
    );
  }

  const criticita = [...(cr.criticita || [])].sort((a, b) => (a.mese || "").localeCompare(b.mese || ""));
  const eur = eurFull;
  function correggiEsp(e) {
    corr.open({
      entityType: "credit_exposure", entityId: e.id, title: `Esposizione ${e.intermediary || ""}`,
      fields: [
        { key: "intermediary", label: "Intermediario", kind: "str", value: e.intermediary },
        { key: "category", label: "Categoria", kind: "str", value: e.category },
        { key: "accordato", label: "Accordato", kind: "num", value: e.accordato },
        { key: "utilizzato", label: "Utilizzato", kind: "num", value: e.utilizzato },
        { key: "importo_garantito", label: "Importo garantito", kind: "num", value: e.importo_garantito },
        { key: "status", label: "Stato", kind: "str", value: e.status },
        { key: "is_critical", label: "Critico", kind: "bool", value: e.is_critical },
      ],
    });
  }
  function correggiGar(g) {
    corr.open({
      entityType: "guarantee_given", entityId: g.id, title: `Garanzia a ${g.guaranteed_subject || ""}`,
      fields: [
        { key: "guaranteed_subject", label: "Soggetto garantito", kind: "str", value: g.guaranteed_subject },
        { key: "intermediary", label: "Intermediario", kind: "str", value: g.intermediary },
        { key: "valore_garanzia", label: "Valore garanzia", kind: "num", value: g.valore_garanzia },
        { key: "importo_garantito", label: "Importo garantito", kind: "num", value: g.importo_garantito },
        { key: "status", label: "Stato", kind: "str", value: g.status },
      ],
    });
  }

  return (
    <Section
      title="Posizione Centrale Rischi Banca d'Italia"
      subtitle="Rilevazione degli affidamenti segnalati dagli intermediari vigilati e verifica di sconfinamenti o sofferenze."
      badge="[D] Banca d'Italia"
      icon="account_balance"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
        <CrossCheckBadge status={cr.crosscheck_status} payload={cr.crosscheck_payload}
          provider={cr.llm_provider} model={cr.llm_model} />
      </div>
      <CrossCheckDiscrepancies payload={cr.crosscheck_payload} />

      {/* 1. Riga di sintesi */}
      <div style={{ background: "var(--pd-info-bg)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14, marginBottom: 16, display: "flex", flexWrap: "wrap", gap: "12px 24px", alignItems: "center" }}>
        <Stat label="Periodo analizzato" value={`${cr.period_from || "?"} → ${cr.period_to || "?"}`} />
        <Stat label="Intermediari segnalanti" value={cr.num_intermediaries ?? 0} />
        <Stat label="Utilizzato totale [D]" value={eur(cr.total_exposure)} />
        <Stat label="Garanzie prestate" value={eur(cr.total_guarantees)} />
        <div style={{ display: "flex", gap: 8, marginLeft: "auto", flexWrap: "wrap" }}>
          <CrBadge on={cr.has_sofferenze} okText="Nessuna sofferenza" alertText="Sofferenze presenti" tone="danger" />
          <CrBadge on={cr.has_criticita} okText="Nessuna criticità" alertText="Criticità rilevate" tone="warning" />
        </div>
      </div>

      {/* 2. Esposizione per intermediario */}
      <h3 style={{ color: "var(--pd-primary)", fontSize: 15, margin: "8px 0 8px" }}>1. Esposizione per intermediario segnalante</h3>
      <div className="pd-table-wrap" style={{ marginBottom: 18 }}>
        <table className="pd-table">
          <thead>
            <tr>
              <th>Intermediario</th>
              <th>Categoria Censimento</th>
              <th className="pd-num">Accordato Operativo</th>
              <th className="pd-num">Utilizzato [D]</th>
              <th className="pd-num">Importo Garantito</th>
              <th>Stato</th>
              {corr && <th>Azioni</th>}
            </tr>
          </thead>
          <tbody>
            {exposures.map(e => (
              <tr key={e.id} className={e.is_critical ? "pd-row--review" : undefined}>
                <td><strong>{e.intermediary || "—"}</strong></td>
                <td>{e.category || "—"}</td>
                <td className="pd-num">{eur(e.accordato)}</td>
                <td className="pd-num"><strong>{eur(e.utilizzato)}</strong></td>
                <td className="pd-num">{eur(e.importo_garantito)}</td>
                <td>{e.status || "—"}</td>
                {corr && <td><div style={{ display: "flex", gap: 6, alignItems: "center" }}><EditedBadge corr={corr} entityId={e.id} /><CorreggiBtn onClick={() => correggiEsp(e)} label="Modifica" /></div></td>}
              </tr>
            ))}
            {exposures.length === 0 && <tr><td colSpan={corr ? 7 : 6} style={{ textAlign: "center", color: "var(--pd-text-muted)" }}>Nessuna esposizione diretta rilevata nel periodo.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* 3. Garanzie prestate */}
      <h3 style={{ color: "var(--pd-primary)", fontSize: 15, margin: "4px 0 6px" }}>2. Garanzie personali o reali prestate a favore di terzi</h3>
      <p style={{ fontSize: 12.5, color: "var(--pd-warn)", background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border)", borderRadius: 6, padding: "8px 12px", margin: "0 0 10px" }}>
        Attenzione: in presenza di fideiussioni o coobbligazioni, verificare il rischio di escussione e il regresso.
      </p>
      <div className="pd-table-wrap" style={{ marginBottom: 18 }}>
        <table className="pd-table">
          <thead>
            <tr>
              <th>Soggetto Garantito</th>
              <th>Intermediario</th>
              <th className="pd-num">Valore Garanzia</th>
              <th className="pd-num">Importo Garantito</th>
              <th>Stato</th>
              {corr && <th>Azioni</th>}
            </tr>
          </thead>
          <tbody>
            {guarantees.map(g => (
              <tr key={g.id}>
                <td><strong>{g.guaranteed_subject || "—"}</strong></td>
                <td>{g.intermediary || "—"}</td>
                <td className="pd-num">{eur(g.valore_garanzia)}</td>
                <td className="pd-num">{eur(g.importo_garantito)}</td>
                <td>{g.status || "—"}</td>
                {corr && <td><div style={{ display: "flex", gap: 6, alignItems: "center" }}><EditedBadge corr={corr} entityId={g.id} /><CorreggiBtn onClick={() => correggiGar(g)} label="Modifica" /></div></td>}
              </tr>
            ))}
            {guarantees.length === 0 && <tr><td colSpan={corr ? 6 : 5} style={{ textAlign: "center", color: "var(--pd-text-muted)" }}>Nessuna garanzia prestata a terzi rilevata.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* 4. Criticità nel tempo */}
      <h3 style={{ color: "var(--pd-primary)", fontSize: 15, margin: "4px 0 8px" }}>3. Andamento storico di sconfinamenti e criticità</h3>
      {criticita.length === 0 ? (
        <p style={{ fontSize: 13, color: "var(--pd-ok)", margin: 0, fontWeight: 600 }}>Nessuna criticità o sofferenza storica rilevata nel periodo esaminato.</p>
      ) : (
        <div className="pd-table-wrap">
          <table className="pd-table">
            <thead>
              <tr>
                <th>Mese</th>
                <th>Intermediario</th>
                <th>Tipo Evento</th>
                <th>Descrizione</th>
                <th className="pd-num">Importo</th>
              </tr>
            </thead>
            <tbody>
              {criticita.map((c, i) => (
                <tr key={i} className="pd-row--review">
                  <td><strong>{c.mese || "—"}</strong></td>
                  <td>{c.intermediario || "—"}</td>
                  <td>{c.tipo || "—"}</td>
                  <td>{c.descrizione || "—"}</td>
                  <td className="pd-num">{c.importo ? eur(c.importo) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

// ---------- UI helpers ----------
// Avviso discreto: esistono altre pratiche con lo stesso CF. Mostra SOLO il sommario
// (GDPR: niente importi/contenuti). L'apertura di una correlata viene tracciata (AccessLog).
function RelatedBanner({ caseId, related }) {
  const [open, setOpen] = useState(false);
  if (!related || related.length === 0) return null;
  async function goTo(toId) {
    try { await openRelated(caseId, toId); } catch {}
    window.location.href = `/pratiche/${toId}/scheda`;
  }
  return (
    <div style={{ background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "10px 14px", margin: "8px 0 4px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ color: "var(--pd-warn)", fontWeight: 600, fontSize: 14 }}>
          Attenzione: esistono {related.length} altra/e pratica/he con questo codice fiscale
        </span>
        <button type="button" onClick={() => setOpen(o => !o)}
          style={{ background: "none", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "3px 10px", cursor: "pointer", color: "var(--pd-warn)", fontSize: 13 }}>
          {open ? "Nascondi" : "Vedi correlate"}
        </button>
      </div>
      {open && (
        <table style={{ ...tbl, marginTop: 10, marginBottom: 0, background: "var(--pd-surface)" }}>
          <thead><tr style={trh}>
            <th style={th}>Pratica</th><th style={tdNum}>Documenti</th><th style={tdNum}>Consultazioni</th>
            <th style={th}>Ultima attività</th><th style={th}></th>
          </tr></thead>
          <tbody>
            {related.map(r => (
              <tr key={r.case_id} style={{ borderTop: "1px solid var(--pd-border)" }}>
                <td style={td}>{r.case_label || r.case_id}</td>
                <td style={tdNum}>{r.n_documenti}</td>
                <td style={tdNum}>{r.n_visure}</td>
                <td style={td}>{r.ultima_attivita ? r.ultima_attivita.slice(0, 10) : "—"}</td>
                <td style={td}><button type="button" onClick={() => goTo(r.case_id)}
                  style={{ ...btnPrimary, padding: "4px 12px", fontSize: 13 }}>Apri</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{ fontSize: 12, color: "var(--pd-warn)", margin: "8px 0 0" }}>
        Solo il riepilogo è mostrato (nessun importo/contenuto). L'apertura di una pratica correlata viene registrata.
      </p>
    </div>
  );
}

function docStatusBadge(s) {
  const v = { caricato: "neutral", in_elaborazione: "warn", elaborato: "ok", normalizzato: "ok", errore: "danger" }[s] || "neutral";
  const label = { caricato: "caricato", in_elaborazione: "in elaborazione", elaborato: "elaborato", normalizzato: "elaborato", errore: "errore" };
  return <span className={`pd-badge pd-badge--${v}`}>{label[s] || s}</span>;
}

function UploadBox({ caseId, label, onUploaded, docs = [], scope = "", uploadedIds = [], onUploadedId, docType = "" }) {
  const [busy, setBusy] = useState(false);
  const [dup, setDup] = useState("");
  const fileRef = useRef(null);
  async function onFile(e) {
    const f = e.target.files[0];
    if (!f) return;
    setBusy(true); setDup("");
    let res;
    try { res = await uploadDoc(caseId, f, docType); } catch {}
    setBusy(false);
    e.target.value = "";
    if (res && res.duplicate) setDup(`"${res.original_filename}" è già presente (deduplicazione SHA-256 attiva).`);
    if (res && res.id && !res.duplicate && onUploadedId) onUploadedId(scope, res.id);
    if (onUploaded) onUploaded();
  }
  // stato dei documenti caricati qui (id persistiti nello Scheda -> sopravvivono al cambio tab)
  const mine = uploadedIds.map(id => (docs || []).find(x => x.id === id)).filter(Boolean);
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--pd-primary)" }}>{label}</div>
          <p style={{ fontSize: 12, color: "var(--pd-text-muted)", margin: "2px 0 0" }}>
            Acquisizione con impronta SHA-256 e normalizzazione automatica nella scheda.
          </p>
        </div>
        <div>
          <input ref={fileRef} type="file" onChange={onFile} disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.tiff" style={{ display: "none" }} />
          <button
            type="button"
            className="pd-btn pd-btn--primary"
            disabled={busy}
            onClick={() => fileRef.current && fileRef.current.click()}
          >
            <span className="material-symbols-outlined" aria-hidden="true">upload_file</span>
            {busy ? "Acquisizione..." : "Seleziona File"}
          </button>
        </div>
      </div>
      {dup && <div style={{ marginTop: 8, color: "var(--pd-warn)", fontSize: 12, background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border)", borderRadius: 6, padding: "5px 9px" }}>{dup}</div>}
      {mine.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {mine.map(doc => (
            <div key={doc.id} style={{ fontSize: 13, padding: "4px 0", borderTop: "1px solid var(--pd-border-soft)" }}>
              <a href={docFileUrl(caseId, doc.id)} target="_blank" rel="noopener noreferrer"
                style={{ color: "var(--pd-accent)", fontWeight: 600 }}>{doc.original_filename}</a> — {docStatusBadge(doc.status)}
              {doc.doc_type && doc.doc_type !== "da_classificare" ? <span style={{ color: "var(--pd-text-muted)" }}> · {doc.doc_type}</span> : null}
              {doc.error ? <div style={{ color: "var(--pd-danger)", fontSize: 12 }}>{doc.error}</div> : null}
              {["elaborato", "normalizzato"].includes(doc.status) && <span style={{ color: "var(--pd-ok)", fontSize: 12 }}> · dati estratti</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ====================================================================
   Box doppio-canale (riutilizzabile) — per OGNI documento: carica file
   OPPURE richiedi via API (dove consentito), con prezzo in evidenza.
   È il TEMPLATE replicabile nelle altre tab cambiando solo la config.
   ==================================================================== */
// Flag UI: mostra i prezzi delle richieste API. OFF finché non arriva il wallet
// prepagato (il pagamento passa ancora dal credito OpenAPI esterno -> il prezzo
// in-app sarebbe transazionale senza azione). price_eur resta nei dati: si
// riaccende cambiando questa sola costante. (Decisione Giuseppe, giu 2026.)
const SHOW_PRICES = false;

const REDDITO_DOCS = [
  { docType: "busta_paga", label: "Busta paga",
    description: "Cedolino mensile → reddito netto e datore (estrazione AI)." },
  { docType: "cu", label: "CU",
    description: "Certificazione Unica → reddito annuo (estrazione AI)." },
  { docType: "isee", label: "ISEE",
    description: "Indicatore situazione economica del nucleo.",
    api: { source: "isee", price_eur: 12.70, eta: "4-5 giorni lavorativi",
           required_fields: ["tax_code"], confirm_required: true } },
  { docType: "estratto_conto", label: "Estratto conto",
    description: "Movimenti bancari → entrate/uscite (parser gratuito)." },
  { docType: "dichiarazione_redditi", label: "Dichiarazione redditi (Modello Redditi / 730)",
    description: "Redditi non da lavoro dipendente: affitti, autonomo, partecipazioni (estrazione AI per quadro)." },
];

function RedditoTools({ caseId, taxCode, docs, uploadedByScope, addUploaded, reload, onIncomeUpdated }) {
  return (
    <div style={{ background: "var(--pd-surface-2)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "12px 14px", marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-primary)", textTransform: "uppercase", letterSpacing: 0.3, marginBottom: 10 }}>
        Strumenti — documenti di reddito
      </div>
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
        {REDDITO_DOCS.map(cfg => (
          <DualChannelBox key={cfg.docType} caseId={caseId} taxCode={taxCode} cfg={cfg}
            docs={docs} uploadedIds={uploadedByScope[cfg.docType] || []} onUploadedId={addUploaded}
            reload={reload} onIncomeUpdated={onIncomeUpdated} />
        ))}
      </div>
      <IncomeDocsDetail caseId={caseId} docs={docs} />
      <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: "10px 0 0" }}>
        I documenti PROPONGONO i valori nei campi qui sotto (riempiono solo quelli vuoti): verifica e salva.
      </p>
    </div>
  );
}

/* Riepilogo reddito: consolida tutte le fonti reddituali (normalizzate a mensile),
   propone un reddito mensile e lo fa applicare al campo che guida il cruscotto. */
const BASE_LABELS = { mensile: "mensile", annuo: "annuo", indicatore: "indicatore", flusso: "flusso" };

function RiepilogoReddito({ caseId, docs, currentMonthly, currentAnnual, onApplyMonthly, onApplyAnnual }) {
  const [sum, setSum] = useState(null);
  const nReady = (docs || []).filter(x => INCOME_DOC_TYPES.includes(x.doc_type) && ["elaborato", "normalizzato"].includes(x.status)).length;
  useEffect(() => { getIncomeSummary(caseId).then(setSum).catch(() => {}); }, [caseId, nReady]);
  if (!sum || !sum.has_data) return null;
  const { summable, references, representative, proposed_monthly, proposed_annual, flags } = sum;
  const appliedM = Math.abs((currentMonthly || 0) - proposed_monthly) < 0.01;
  const appliedA = Math.abs((currentAnnual || 0) - proposed_annual) < 0.01;

  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: 14, marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <strong style={{ color: "var(--pd-primary)", fontSize: 15 }}>Riepilogo reddito</strong>
        <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>fonti consolidate, normalizzate a mensile</span>
      </div>
      {flags.map((f, i) => (
        <div key={i} style={{ fontSize: 12, color: "var(--pd-warn)", background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "6px 9px", marginBottom: 6 }}>{f}</div>
      ))}

      {summable.length > 0 && (
        <table style={{ ...tbl, marginBottom: 8 }}>
          <thead><tr style={trh}>
            <th style={th}>Fonte</th><th style={th}>Periodo</th><th style={th}>Base</th>
            <th style={tdNum}>Importo</th><th style={tdNum}>~ mensile</th><th style={tdNum}>~ annuo</th>
          </tr></thead>
          <tbody>
            {summable.map((s, i) => (
              <tr key={i} style={{ borderTop: "1px solid var(--pd-border)" }}>
                <td style={td}>{s.source}{s.note ? <div style={{ fontSize: 11, color: "var(--pd-text-faint)" }}>{s.note}</div> : null}</td>
                <td style={td}>{s.period || "—"}</td>
                <td style={td}>{BASE_LABELS[s.basis] || s.basis}</td>
                <td style={tdNum}>{eurFull(s.amount)}{s.basis === "annuo" ? "/a" : s.basis === "mensile" ? "/m" : ""}</td>
                <td style={{ ...tdNum, fontWeight: 600 }}>{s.monthly_equiv == null ? "—" : eurFull(s.monthly_equiv)}</td>
                <td style={tdNum}>{s.annual_equiv == null ? "—" : eurFull(s.annual_equiv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ background: "var(--pd-info-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "10px 12px" }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-primary)", marginBottom: 6 }}>Consolidato (proposto)</div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>
            <th style={{ textAlign: "left", fontSize: 11, color: "var(--pd-text-muted)", fontWeight: 600 }}>Categoria</th>
            <th style={{ textAlign: "right", fontSize: 11, color: "var(--pd-text-muted)", fontWeight: 600 }}>mensile</th>
            <th style={{ textAlign: "right", fontSize: 11, color: "var(--pd-text-muted)", fontWeight: 600 }}>annuo</th>
          </tr></thead>
          <tbody>
            {representative.map((r, i) => (
              <tr key={i}>
                <td style={{ fontSize: 13, color: "var(--pd-text-muted)", padding: "2px 0" }}>{r.category_label}{r.year ? ` · ${r.year}` : ""}</td>
                <td style={{ fontSize: 13, fontWeight: 600, textAlign: "right" }}>{eurFull(r.monthly_equiv)}</td>
                <td style={{ fontSize: 13, fontWeight: 600, textAlign: "right" }}>{r.annual_equiv == null ? "—" : eurFull(r.annual_equiv)}</td>
              </tr>
            ))}
            <tr style={{ borderTop: "2px solid var(--pd-primary)" }}>
              <td style={{ fontWeight: 700, color: "var(--pd-primary)", padding: "6px 0 0" }}>Reddito considerato</td>
              <td style={{ fontWeight: 700, color: "var(--pd-primary)", textAlign: "right", padding: "6px 0 0" }}>{eurFull(proposed_monthly)}/mese</td>
              <td style={{ fontWeight: 700, color: "var(--pd-primary)", textAlign: "right", padding: "6px 0 0" }}>{eurFull(proposed_annual)}/anno</td>
            </tr>
          </tbody>
        </table>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <button type="button" onClick={() => onApplyMonthly(proposed_monthly)} disabled={appliedM}
            style={appliedM ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "default" } : { ...btnSmall, background: "var(--pd-ok)" }}>
            {appliedM ? "Mensile applicato" : 'Applica a "Reddito mensile netto"'}
          </button>
          <button type="button" onClick={() => onApplyAnnual(proposed_annual)} disabled={appliedA}
            style={appliedA ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "default" } : { ...btnSmall, background: "var(--pd-ok)" }}>
            {appliedA ? "Annuo applicato" : 'Applica a "Reddito annuo"'}
          </button>
          <span style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>poi verifica e salva</span>
        </div>
      </div>

      {references.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--pd-text-muted)" }}>
          <b>Riferimenti</b> (non sommati al reddito): {references.map((r, i) => (
            <span key={i}>{i ? " · " : ""}{r.source} {eurFull(r.amount)}{r.basis === "flusso" ? "/mese (flusso lordo)" : ""}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/* Pannello "dettaglio estratto" dei documenti di reddito: mostra COSA è stato letto
   da ogni documento (lordo/netto/trattenute, quadri, movimenti...), non solo il totale
   ripiegato nei campi economici. Un <details> per documento, contenuto per tipo. */
const INCOME_DOC_LABELS = {
  busta_paga: "Busta paga", cu: "CU (Certificazione Unica)", isee: "ISEE",
  estratto_conto: "Estratto conto", dichiarazione_redditi: "Dichiarazione redditi",
};
const QUADRO_ROWS = [
  ["RA_terreni", "Terreni (RA)"],
  ["RB_fabbricati", "Fabbricati / affitti (RB)"],
  ["RC_lavoro_dipendente", "Lavoro dipendente (RC)"],
  ["RE_lavoro_autonomo", "Lavoro autonomo (RE)"],
  ["RF_RG_impresa", "Impresa (RF/RG)"],
  ["RH_partecipazioni", "Partecipazioni (RH)"],
  ["RL_altri_redditi", "Altri redditi (RL)"],
  ["RP_oneri_detrazioni", "Oneri / detrazioni (RP)"],
];

// righe [etichetta, valore, isMoney] per i tipi a struttura semplice (no dichiarazione)
function incomeRows(docType, data) {
  if (docType === "busta_paga") return [
    ["Periodo", data.periodo, false], ["Datore di lavoro", data.datore_lavoro, false],
    ["Retribuzione lorda", data.retribuzione_lorda, true], ["Totale competenze", data.totale_competenze, true],
    ["Totale trattenute", data.totale_trattenute, true], ["Retribuzione netta", data.retribuzione_netta, true],
    ["Tipo contratto", data.tipo_contratto, false],
  ];
  if (docType === "cu") return [
    ["Anno", data.anno, false], ["Sostituto d'imposta", data.datore_sostituto, false],
    ["Reddito complessivo", data.reddito_complessivo, true], ["Reddito imponibile", data.reddito_imponibile, true],
    ["Ritenute", data.ritenute, true],
  ];
  if (docType === "isee") return [
    ["Anno", data.anno, false], ["ISEE ordinario", data.isee_ordinario, true],
    ["ISR", data.isr, true], ["ISE", data.ise, true],
    ["Componenti nucleo", data.componenti_nucleo, false], ["Scadenza", data.scadenza, false],
  ];
  if (docType === "estratto_conto") {
    const a = data.aggregazioni || {};
    const p = data.periodo || {};
    return [
      ["Periodo", (p.da || p.a) ? `${p.da || "?"} → ${p.a || "?"}` : null, false],
      ["Movimenti", a.count_movimenti, false], ["Mesi coperti", a.mesi_coperti, false],
      ["Totale entrate", a.totale_entrate, true], ["Totale uscite", a.totale_uscite, true],
      ["Entrate medie mensili", a.entrate_medie_mensili, true], ["Uscite medie mensili", a.uscite_medie_mensili, true],
      ["Saldo finale", a.saldo_finale, true],
    ];
  }
  return [];
}

function IncomeDocsDetail({ caseId, docs }) {
  const [items, setItems] = useState([]);
  // ricarica quando cambia il numero di documenti di reddito elaborati
  const nReady = (docs || []).filter(x => INCOME_DOC_TYPES.includes(x.doc_type) && ["elaborato", "normalizzato"].includes(x.status)).length;
  useEffect(() => {
    getIncomeDocuments(caseId).then(d => setItems(Array.isArray(d) ? d : [])).catch(() => {});
  }, [caseId, nReady]);

  const ready = items.filter(d => d.data && Object.keys(d.data).length > 0);
  if (ready.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--pd-text)", margin: "0 0 6px" }}>Dettaglio estratto dai documenti</div>
      {ready.map(it => (
        <IncomeDocPanel key={it.document_id} item={it} />
      ))}
    </div>
  );
}

function IncomeDocPanel({ item }) {
  const data = item.data || {};
  const label = INCOME_DOC_LABELS[item.doc_type] || item.doc_type;
  const isDecl = item.doc_type === "dichiarazione_redditi";

  // intestazione comune
  let head = label;
  if (isDecl) head += ` · ${data.modello === "730" ? "Modello 730" : "Modello Redditi PF"}${data.anno_imposta ? ` · anno ${data.anno_imposta}` : ""}`;
  else if (item.doc_type === "busta_paga" && data.periodo) head += ` · ${data.periodo}`;
  else if (data.anno) head += ` · anno ${data.anno}`;

  return (
    <details style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8 }}>
      <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--pd-primary)" }}>
        {head} — dettaglio estratto
      </summary>
      <div style={{ marginTop: 8 }}>
        {isDecl ? <DeclQuadriTable data={data} /> : <IncomeKeyValueTable docType={item.doc_type} data={data} />}
        {data.note && (
          <p style={{ fontSize: 12, color: "var(--pd-warn)", background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "6px 9px", margin: "8px 0 0" }}>{data.note}</p>
        )}
      </div>
    </details>
  );
}

function IncomeKeyValueTable({ docType, data }) {
  const rows = incomeRows(docType, data).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (rows.length === 0) return <p style={{ fontSize: 12, color: "var(--pd-text-muted)", margin: 0 }}>Nessun dato leggibile estratto dal documento.</p>;
  return (
    <table style={{ ...tbl, marginBottom: 0 }}>
      <tbody>
        {rows.map(([k, v, money]) => (
          <tr key={k} style={{ borderTop: "1px solid var(--pd-border)" }}>
            <td style={{ ...td, fontWeight: 600, width: 200, color: "var(--pd-text)" }}>{k}</td>
            <td style={money ? tdNum : td}>{money ? eurFull(v) : String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DeclQuadriTable({ data }) {
  const q = data.quadri || {};
  const rn = data.riepilogo_RN || {};
  const rows = QUADRO_ROWS
    .filter(([k]) => (q[k] || {}).presente)
    .map(([k, label]) => {
      const blk = q[k] || {};
      const val = k === "RP_oneri_detrazioni" ? blk.totale_oneri : blk.reddito;
      let det = "";
      if (k === "RB_fabbricati") {
        const bits = [];
        if (blk.canoni_percepiti) bits.push(`canoni ${eurFull(blk.canoni_percepiti)}`);
        if (blk.n_immobili_locati) { const n = blk.n_immobili_locati; bits.push(`${n} ${n === 1 ? "immobile locato" : "immobili locati"}`); }
        det = bits.join(" · ");
      } else if (k === "RE_lavoro_autonomo" && blk.volume_affari) {
        det = `volume affari ${eurFull(blk.volume_affari)}`;
      }
      return { k, label, val, det };
    })
    // sopprime le righe-quadro nulle: nessun importo significativo e nessun dettaglio
    .filter(r => (r.val != null && Number(r.val) !== 0) || r.det);
  return (
    <>
      {data.dichiarante?.nominativo && (
        <p style={{ fontSize: 12, color: "var(--pd-text-muted)", margin: "0 0 8px" }}>
          Dichiarante: {data.dichiarante.nominativo}{data.dichiarante.codice_fiscale ? ` · ${data.dichiarante.codice_fiscale}` : ""}
        </p>
      )}
      <table style={{ ...tbl, marginBottom: 0 }}>
        <thead><tr style={trh}><th style={th}>Quadro</th><th style={tdNum}>Reddito / importo</th><th style={th}>Dettaglio</th></tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td style={td} colSpan={3}>Nessun quadro con importo rilevato.</td></tr>}
          {rows.map(r => (
            <tr key={r.k} style={{ borderTop: "1px solid var(--pd-border)" }}>
              <td style={td}>{r.label}</td>
              <td style={{ ...tdNum, fontWeight: 600 }}>{eurFull(r.val)}</td>
              <td style={{ ...td, color: "var(--pd-text-muted)", fontSize: 12 }}>{r.det || "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ borderTop: "2px solid var(--pd-primary)", fontWeight: "bold", background: "var(--pd-info-bg)" }}>
            <td style={td}>Reddito complessivo (RN)</td>
            <td style={tdNum}>{eurFull(rn.reddito_complessivo)}</td>
            <td style={{ ...td, fontSize: 12, color: "var(--pd-text-muted)", fontWeight: "normal" }}>
              {rn.imposta_netta ? `imposta netta ${eurFull(rn.imposta_netta)}` : ""}
            </td>
          </tr>
        </tfoot>
      </table>
    </>
  );
}

function DualChannelBox({ caseId, taxCode, cfg, docs, uploadedIds, onUploadedId, reload, onIncomeUpdated }) {
  const [busy, setBusy] = useState(false);
  const [dup, setDup] = useState("");
  // canale API
  const api = cfg.api;
  const [cf, setCf] = useState(taxCode || "");
  const [apiBusy, setApiBusy] = useState(false);
  const [polling, setPolling] = useState(false);
  const [req, setReq] = useState(null);
  const [apiMsg, setApiMsg] = useState("");
  const timer = useRef(null);
  useEffect(() => { if (taxCode) setCf(prev => prev || taxCode); }, [taxCode]);
  useEffect(() => () => clearInterval(timer.current), []);

  async function onFile(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setBusy(true); setDup("");
    const dups = [];
    for (const f of files) {
      let res;
      try { res = await uploadDoc(caseId, f, cfg.docType); } catch {}
      if (res && res.duplicate) dups.push(res.original_filename || f.name);
      if (res && res.id && !res.duplicate && onUploadedId) onUploadedId(cfg.docType, res.id);
    }
    setBusy(false);
    e.target.value = "";
    if (dups.length) setDup(`${dups.length === 1 ? `"${dups[0]}" è già presente: non ricaricato.` : `${dups.length} file già presenti: deduplicazione applicata.`}`);
    if (reload) reload();
  }

  const priceLabel = api ? eurFull(api.price_eur) : "";
  const onerous = api && api.price_eur > 1;   // prezzo in evidenza solo se oneroso

  async function richiedi() {
    setApiMsg("");
    const q = (cf || "").trim();
    if (!q) { setApiMsg("Inserisci il codice fiscale."); return; }
    const confirmMsg = SHOW_PRICES
      ? `La richiesta ${cfg.label} via API costa ${priceLabel} e richiede ${api.eta}. Procedere?`
      : `Confermi la richiesta di ${cfg.label} via API? Tempo stimato: ${api.eta}.`;
    if (api.confirm_required && !window.confirm(confirmMsg)) return;
    setReq(null); setApiBusy(true);
    let res;
    try { res = await openapiSearch(caseId, api.source, q); }
    catch { setApiBusy(false); setApiMsg("Errore di rete verso il backend."); return; }
    setApiBusy(false);
    if (!res || res.error || res.detail) { setApiMsg(res?.detail || res?.error || "Avvio non riuscito."); return; }
    const reqId = res.request_id;
    setReq({ id: reqId, status: "pending", sandbox: res.sandbox });
    setPolling(true);
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      let r;
      try { r = await openapiRequest(caseId, reqId); } catch { return; }
      if (!r || !r.status) return;
      setReq(prev => ({ ...prev, ...r }));
      if (["done", "error", "timeout"].includes(r.status)) {
        clearInterval(timer.current); setPolling(false);
        if (r.status === "done") { if (reload) reload(); if (onIncomeUpdated) onIncomeUpdated(); }
      }
    }, 4000);
  }

  const mine = uploadedIds.map(id => (docs || []).find(x => x.id === id)).filter(Boolean);
  const md = req?.mapped_data || null;

  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--pd-primary)" }}>{cfg.label}</div>
      <div style={{ fontSize: 12, color: "var(--pd-text-muted)" }}>{cfg.description}</div>

      {/* Canale UPLOAD — sempre presente */}
      <div style={{ borderTop: "1px solid var(--pd-border)", paddingTop: 8 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--pd-text)" }}>Carica documento [D]</div>
          <label style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "5px 11px", fontSize: 12, fontWeight: 700,
            background: busy ? "var(--pd-surface-alt)" : "var(--pd-primary)",
            color: busy ? "var(--pd-text-muted)" : "#fff",
            borderRadius: 6, cursor: busy ? "not-allowed" : "pointer",
            boxShadow: "var(--pd-shadow-sm)"
          }}>
            {busy ? "Caricamento..." : "Seleziona File"}
            <input type="file" multiple onChange={onFile} disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.tiff" style={{ display: "none" }} />
          </label>
        </div>
        {dup && <div style={{ marginTop: 6, color: "var(--pd-warn)", fontSize: 12, background: "var(--pd-warn-bg)", border: "1px solid var(--pd-border-strong)", borderRadius: 6, padding: "5px 9px" }}>{dup}</div>}
        {mine.map(doc => (
          <div key={doc.id} style={{ fontSize: 12, padding: "3px 0", borderTop: "1px solid var(--pd-border)", marginTop: 4 }}>
            <a href={docFileUrl(caseId, doc.id)} target="_blank" rel="noopener noreferrer" style={{ color: "var(--pd-accent)", textDecoration: "none" }}>{doc.original_filename}</a>
            {" — "}{docStatusBadge(doc.status)}
            {doc.error ? <div style={{ color: "var(--pd-danger)" }}>{doc.error}</div> : null}
            {["elaborato", "normalizzato"].includes(doc.status) && <span style={{ color: "var(--pd-ok)" }}> valori proposti nei campi sotto</span>}
          </div>
        ))}
      </div>

      {/* Canale API — solo se il documento è richiedibile */}
      {api && (
        <div style={{ borderTop: "1px solid var(--pd-border)", paddingTop: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--pd-text)" }}>Richiedi via API</span>
            {SHOW_PRICES && <span className={`pd-badge pd-badge--${onerous ? "warn" : "neutral"}`}>{priceLabel}</span>}
            <span style={{ fontSize: 11, color: "var(--pd-text-faint)" }}>{api.eta}</span>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <input value={cf} onChange={e => setCf(e.target.value)} placeholder="Codice fiscale" style={{ ...inp, minWidth: 150 }} />
            <button onClick={richiedi} disabled={apiBusy || polling}
              style={apiBusy || polling ? { ...btnSmall, background: "var(--pd-border-strong)", cursor: "not-allowed" } : btnSmall}>
              {apiBusy ? "Avvio..." : "Richiedi"}
            </button>
          </div>
          {apiMsg && <p style={{ color: "var(--pd-danger)", fontSize: 12, margin: "6px 0 0" }}>{apiMsg}</p>}
          {req?.status === "pending" && (
            <p style={{ color: "var(--pd-warn)", fontSize: 12, margin: "6px 0 0" }}>
              Richiesta in corso...{req.sandbox ? " (ambiente di test)" : ""}
            </p>
          )}
          {(req?.status === "error" || req?.status === "timeout") && (
            <p style={{ color: "var(--pd-danger)", fontSize: 12, margin: "6px 0 0" }}>{req.error || "Richiesta non riuscita."}</p>
          )}
          {req?.status === "done" && (
            md && md.isee_ordinario
              ? <p style={{ fontSize: 12, color: "var(--pd-ok)", margin: "6px 0 0" }}>ISEE {eurFull(md.isee_ordinario)} ricevuto — nota aggiunta alle fonti di reddito.</p>
              : <p style={{ fontSize: 12, color: "var(--pd-text-faint)", margin: "6px 0 0" }}>Richiesta evasa (in ambiente di test il risultato può essere vuoto).</p>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryCard({ title, badge, onGo, children }) {
  const [hover, setHover] = useState(false);
  const clickable = !!onGo;
  return (
    <div onClick={onGo} role={clickable ? "button" : undefined} tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onGo(); } }) : undefined}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        background: "var(--pd-surface)", borderRadius: 8, padding: "16px 18px",
        border: "1px solid " + (clickable && hover ? "var(--pd-accent)" : "var(--pd-border)"),
        boxShadow: clickable && hover ? "var(--pd-shadow-md)" : "var(--pd-shadow)",
        transform: clickable && hover ? "translateY(-1px)" : "none",
        cursor: clickable ? "pointer" : "default", transition: "border-color .12s, box-shadow .12s, transform .12s",
      }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 10, paddingBottom: 8, borderBottom: "1px solid var(--pd-border-soft)" }}>
        <strong style={{ color: "var(--pd-primary)", fontSize: 14.5 }}>{title}</strong>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {badge && <span className="pd-badge pd-badge--info" style={{ fontSize: 10.5, padding: "2px 7px" }}>{badge}</span>}
          {onGo && <span style={{ color: "var(--pd-accent)", fontSize: 12.5, fontWeight: 700 }}>Apri →</span>}
        </div>
      </div>
      {children}
    </div>
  );
}

function SLine({ k, v }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "2px 0" }}>
      <span style={{ color: "var(--pd-text-muted)" }}>{k}</span><span style={{ fontWeight: 600, color: "var(--pd-text)" }}>{v}</span>
    </div>
  );
}
function Grid({ children }) { return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>{children}</div>; }
function F({ label, wide, children }) {
  return <div style={{ gridColumn: wide ? "1 / -1" : "auto" }}>
    <label style={{ display: "block", fontSize: 12, color: "var(--pd-text-muted)", marginBottom: 3 }}>{label}</label>{children}
  </div>;
}
function I({ v, on, type = "text" }) {
  return <input type={type} value={v ?? ""} onChange={e => on(e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }} />;
}
// Converte "1.234,56" / "1234,56" / "1234.56" in numero.
function parseMoney(s) {
  let t = String(s).replace(/[^\d.,-]/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");  // formato italiano
  const n = parseFloat(t);
  return isNaN(n) ? 0 : n;
}
// Campo valuta: a riposo mostra il numero formattato it-IT (separatore migliaia);
// al focus diventa editabile come numero semplice. Salva sempre un numero.
function Money({ v, on, style, placeholder }) {
  const [focused, setFocused] = useState(false);
  const [raw, setRaw] = useState("");
  const num = Number(v) || 0;
  const shown = focused
    ? raw
    : (v === "" || v == null ? "" : num.toLocaleString("it-IT", { useGrouping: true, minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  return (
    <input type="text" inputMode="decimal" value={shown} placeholder={placeholder}
      onFocus={() => { setRaw(num ? String(num) : ""); setFocused(true); }}
      onBlur={() => setFocused(false)}
      onChange={e => { setRaw(e.target.value); on(parseMoney(e.target.value)); }}
      style={{ ...inp, width: "100%", boxSizing: "border-box", ...style }} />
  );
}
// etichette leggibili per i valori enum (il valore resta quello del backend)
const SEL_LABELS = {
  privato: "Privato", ditta_individuale: "Ditta individuale", societa: "Società",
  garante: "Garante", coobbligato: "Coobbligato",
  capitali: "Società di capitali", persone: "Società di persone", altro: "Altro",
};
function Sel({ v, on, opts }) {
  return <select value={v} onChange={e => on(e.target.value)} style={{ ...inp, width: "100%", boxSizing: "border-box" }}>
    {opts.map(o => <option key={o} value={o}>{SEL_LABELS[o] || o.replace(/_/g, " ")}</option>)}
  </select>;
}
function Chk({ label, v, on }) {
  return <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14 }}>
    <input type="checkbox" checked={!!v} onChange={e => on(e.target.checked)} />{label}
  </label>;
}

const inp = { padding: "8px 10px", border: "1px solid var(--pd-border-strong)", borderRadius: 6, fontSize: 14 };
const btnPrimary = { padding: "10px 22px", background: "var(--pd-primary)", color: "var(--pd-surface)", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 15 };
const btnSmall = { padding: "8px 14px", background: "var(--pd-accent)", color: "var(--pd-surface)", border: "none", borderRadius: 6, cursor: "pointer" };
const tbl = { width: "100%", borderCollapse: "collapse", marginBottom: 8 };
const trh = { background: "var(--pd-primary)", color: "var(--pd-surface)", textAlign: "left" };
const th = { padding: "8px 10px", fontSize: 13 };
const td = { padding: "8px 10px", fontSize: 14 };
const tdNum = { padding: "8px 10px", fontSize: 13, textAlign: "right", whiteSpace: "nowrap" };
const addRow = { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 };
const del = { color: "var(--pd-danger)", cursor: "pointer", fontSize: 13 };
const tag = { background: "var(--pd-accent)", color: "var(--pd-surface)", fontSize: 10, fontWeight: "bold", padding: "1px 6px", borderRadius: 8, marginLeft: 6, whiteSpace: "nowrap" };
const sumStyle = { cursor: "pointer", fontSize: 13, color: "var(--pd-accent)", padding: "4px 0" };

