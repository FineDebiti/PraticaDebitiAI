"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  listCases,
  getCard,
  saveDebtor,
  uploadAer,
  getIncomeSummary,
  getIndicators
} from "../api";
import DocumentsPanel from "../components/DocumentsPanel";

function DatiEconomiciContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseIdParam = searchParams.get("caseId");

  const [cases, setCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdParam || "");
  const [card, setCard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("redditi");
  const [notice, setNotice] = useState("");

  // Debtor form fields
  const [incomeList, setIncomeList] = useState([]);

  const [household, setHousehold] = useState([]);

  const [expenses, setExpenses] = useState({
    affitto: 0,
    utenze: 0,
    cibo: 0,
    altre: 0,
    note: "",
  });

  const [aerUploadBusy, setAerUploadBusy] = useState(false);

  // Load cases list
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

  // Load selected case data
  useEffect(() => {
    if (!selectedCaseId) return;
    async function loadData() {
      setLoading(true);
      try {
        const cData = await getCard(selectedCaseId);
        setCard(cData);
        if (cData?.debtor) {
          const d = cData.debtor;
          const monthlyInc = d.monthly_net_income || 0;
          setIncomeList([
            { anno: "Corrente", annuo: monthlyInc * 12, mensile: monthlyInc, note: "Dichiarato" }
          ]);
          setExpenses({
            affitto: 0,
            utenze: 0,
            cibo: 0,
            altre: d.monthly_expenses || 0,
            note: d.notes || ""
          });
          if (d.first_name || d.last_name) {
            setHousehold([
              { parentela: "Dichiarante", nome: `${d.first_name || ''} ${d.last_name || ''}`.trim() || "Debitore", luogo: d.birth_place || "-", data: d.birth_date || "-" }
            ]);
          } else {
            setHousehold([]);
          }
        } else {
          setIncomeList([]);
          setHousehold([]);
          setExpenses({ affitto: 0, utenze: 0, cibo: 0, altre: 0, note: "" });
        }
      } catch (err) {
        console.error("Error loading case card:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [selectedCaseId]);

  function handleCaseChange(e) {
    const id = e.target.value;
    setSelectedCaseId(id);
    router.push(`/dati-economici?caseId=${id}`);
  }

  async function handleSaveDraft() {
    if (!selectedCaseId) return;
    setSaving(true);
    setNotice("");
    try {
      const totExpenses = Number(expenses.affitto) + Number(expenses.utenze) + Number(expenses.cibo) + Number(expenses.altre);
      await saveDebtor(selectedCaseId, {
        monthly_net_income: incomeList[0]?.mensile || 0,
        monthly_expenses: totExpenses,
        notes: expenses.note
      });
      setNotice("Bozza salvata con successo!");
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setNotice("Errore nel salvataggio della bozza.");
    } finally {
      setSaving(false);
    }
  }

  async function handleAerUpload(e) {
    const file = e.target.files?.[0];
    if (!file || !selectedCaseId) return;
    setAerUploadBusy(true);
    try {
      await uploadAer(selectedCaseId, file);
      setNotice("Estratto ADeR caricato ed elaborato!");
      const updated = await getCard(selectedCaseId);
      setCard(updated);
    } catch (err) {
      alert(err.message || "Errore upload ADeR");
    } finally {
      setAerUploadBusy(false);
      e.target.value = "";
    }
  }

  const currentCase = cases.find(c => c.id === selectedCaseId);
  const totalMonthlyExpenses = Number(expenses.affitto) + Number(expenses.utenze) + Number(expenses.cibo) + Number(expenses.altre);

  return (
    <div style={{ paddingBottom: 80 }}>
      {/* Top Header & Selector */}
      <div className="pd-page-head">
        <div>
          <h1 className="pd-h1">Dati Economici e Raccolta Analitica</h1>
          <p>Compilazione e verifica guidata dei dati di reddito, spese, debito e patrimonio.</p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: "var(--pd-text-muted)" }}>
            Seleziona Pratica:
          </label>
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
        </div>
      </div>

      {notice && (
        <div style={{ marginBottom: 16 }} className="pd-badge pd-badge--ok">
          {notice}
        </div>
      )}

      {/* Progress Stepper Header (Screen 2 Stitch) */}
      <div className="pd-stepper">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 12 }}>
          <div>
            <h2 className="pd-h2" style={{ fontSize: 20 }}>
              Fase 2: Raccolta Dati Economici
            </h2>
            <p className="pd-muted" style={{ margin: "2px 0 0", fontSize: 13 }}>
              Pratica: <strong>#{currentCase?.code || "SELEZIONA"}</strong> | {currentCase?.client_name || "Cliente"}
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-accent)", textTransform: "uppercase" }}>
              Step 2 di 4
            </span>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--pd-primary)" }}>
              65% Completato
            </div>
          </div>
        </div>
        <div className="pd-progress">
          <span style={{ width: "65%" }}></span>
        </div>
      </div>

      {/* Section Navigation Tabs */}
      <div className="pd-tabs" style={{ marginBottom: 24 }}>
        <button
          className="pd-tab"
          aria-selected={activeTab === "redditi"}
          onClick={() => setActiveTab("redditi")}
        >
          Redditi e Nucleo Familiare
        </button>
        <button
          className="pd-tab"
          aria-selected={activeTab === "spese"}
          onClick={() => setActiveTab("spese")}
        >
          Spese e Sostentamento
        </button>
        <button
          className="pd-tab"
          aria-selected={activeTab === "passivo"}
          onClick={() => setActiveTab("passivo")}
        >
          Stato Passivo
        </button>
        <button
          className="pd-tab"
          aria-selected={activeTab === "patrimonio"}
          onClick={() => setActiveTab("patrimonio")}
        >
          Patrimonio
        </button>
        <button
          className="pd-tab"
          aria-selected={activeTab === "crisi"}
          onClick={() => setActiveTab("crisi")}
        >
          Analisi Reddittuale e Crisi
        </button>
      </div>

      {/* TAB CONTENT 1: REDDITI E NUCLEO */}
      {activeTab === "redditi" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-card">
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
                  family_restroom
                </span>
                Redditi e Composizione Nucleo
              </h3>
            </div>

            <div style={{ marginBottom: 24 }}>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-accent)", textTransform: "uppercase", marginBottom: 12 }}>
                Reddito Netto Medio Mensile (Ultimi 3 Anni)
              </h4>
              <div className="pd-table-wrap">
                <table className="pd-table">
                  <thead>
                    <tr>
                      <th>Anno</th>
                      <th>Reddito Annuo Netto</th>
                      <th>Reddito Mensile Netto</th>
                      <th>Note / Fonte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incomeList.map((item) => (
                      <tr key={item.anno}>
                        <td style={{ fontWeight: 600 }}>{item.anno}</td>
                        <td className="pd-num" style={{ fontWeight: 600 }}>
                          € {item.annuo.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="pd-num">
                          € {item.mensile.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ fontStyle: "italic", color: "var(--pd-text-muted)" }}>
                          {item.note}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-accent)", textTransform: "uppercase", marginBottom: 12 }}>
                Membri del Nucleo Familiare
              </h4>
              <div className="pd-table-wrap">
                <table className="pd-table">
                  <thead>
                    <tr>
                      <th>Parentela</th>
                      <th>Cognome e Nome</th>
                      <th>Luogo di Nascita</th>
                      <th>Data di Nascita</th>
                    </tr>
                  </thead>
                  <tbody>
                    {household.map((m, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{m.parentela}</td>
                        <td style={{ fontWeight: 700, color: i === 0 ? "var(--pd-primary)" : "inherit" }}>
                          {m.nome}
                        </td>
                        <td>{m.luogo}</td>
                        <td>{m.data}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT 2: SPESE E SOSTENTAMENTO */}
      {activeTab === "spese" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-card">
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
                  payments
                </span>
                Spese Correnti di Sostentamento
              </h3>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <div>
                <div className="pd-table-wrap">
                  <table className="pd-table">
                    <thead>
                      <tr>
                        <th>Voci di Spesa</th>
                        <th className="pd-num">Media Mensile (€)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Canone di locazione / Mutuo prima casa</td>
                        <td className="pd-num">
                          <input
                            type="number"
                            className="pd-input"
                            style={{ width: 120, textAlign: "right" }}
                            value={expenses.affitto}
                            onChange={(e) => setExpenses({ ...expenses, affitto: e.target.value })}
                          />
                        </td>
                      </tr>
                      <tr>
                        <td>Utenze (Acqua, Luce, Gas, Telefono)</td>
                        <td className="pd-num">
                          <input
                            type="number"
                            className="pd-input"
                            style={{ width: 120, textAlign: "right" }}
                            value={expenses.utenze}
                            onChange={(e) => setExpenses({ ...expenses, utenze: e.target.value })}
                          />
                        </td>
                      </tr>
                      <tr>
                        <td>Fabbisogno Nutrizionale e Spesa Alimentare</td>
                        <td className="pd-num">
                          <input
                            type="number"
                            className="pd-input"
                            style={{ width: 120, textAlign: "right" }}
                            value={expenses.cibo}
                            onChange={(e) => setExpenses({ ...expenses, cibo: e.target.value })}
                          />
                        </td>
                      </tr>
                      <tr>
                        <td>Altre Spese Essenziali (Carburante, Condominio)</td>
                        <td className="pd-num">
                          <input
                            type="number"
                            className="pd-input"
                            style={{ width: 120, textAlign: "right" }}
                            value={expenses.altre}
                            onChange={(e) => setExpenses({ ...expenses, altre: e.target.value })}
                          />
                        </td>
                      </tr>
                    </tbody>
                    <tfoot>
                      <tr>
                        <td>TOTALE SPESE MENSILI</td>
                        <td className="pd-num" style={{ fontSize: 16 }}>
                          € {totalMonthlyExpenses.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <div className="pd-card pd-card--tonal">
                <h4 className="pd-h3" style={{ fontSize: 16, marginBottom: 8 }}>
                  Note di Supporto
                </h4>
                <textarea
                  className="pd-textarea"
                  rows={5}
                  value={expenses.note}
                  onChange={(e) => setExpenses({ ...expenses, note: e.target.value })}
                />
                <p className="pd-faint" style={{ fontSize: 12, marginTop: 8 }}>
                  Le spese mensili vengono utilizzate nel calcolo del saldo disponibile per l'accordo di ristrutturazione.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT 3: STATO PASSIVO */}
      {activeTab === "passivo" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-card">
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined" style={{ color: "var(--pd-danger)" }}>
                  receipt_long
                </span>
                Stato Passivo - Posizioni Debitorie
              </h3>
              <label className="pd-btn pd-btn--olive" style={{ cursor: "pointer" }}>
                <span className="material-symbols-outlined">upload_file</span>
                {aerUploadBusy ? "Elaborazione..." : "Importa Estratto ADeR"}
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  style={{ display: "none" }}
                  onChange={handleAerUpload}
                  disabled={aerUploadBusy}
                />
              </label>
            </div>

            <div className="pd-table-wrap">
              <table className="pd-table">
                <thead>
                  <tr>
                    <th>Creditore / Ente</th>
                    <th>Natura Obbligazione</th>
                    <th>Debitore / Garante</th>
                    <th className="pd-num">Rata Mensile</th>
                    <th className="pd-num">Debito Residuo</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {card?.aer_records && card.aer_records.length > 0 ? (
                    card.aer_records.map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 700 }}>{r.ente || "ADeR"}</td>
                        <td>{r.natura || "Debito iscritto a ruolo"}</td>
                        <td>{currentCase?.client_name || "Debitore"}</td>
                        <td className="pd-num">-</td>
                        <td className="pd-num" style={{ fontWeight: 700, color: "var(--pd-danger)" }}>
                          € {(Number(r.importo) || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ fontStyle: "italic", fontSize: 12 }}>{r.note || "-"}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "var(--pd-text-muted)", padding: 24 }}>
                        Nessun estratto di ruolo ADeR caricato. Usa il pulsante "Importa Estratto ADeR" in alto per associare una cartella esattoriale.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Integrated Document Upload Panel */}
          {selectedCaseId && <DocumentsPanel caseId={selectedCaseId} />}
        </div>
      )}

      {/* TAB CONTENT 4: PATRIMONIO */}
      {activeTab === "patrimonio" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-card">
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
                  account_balance
                </span>
                Analisi Patrimoniale
              </h3>
            </div>

            {/* Beni Mobili */}
            <div style={{ marginBottom: 24 }}>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-accent)", textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>local_shipping</span>
                Beni Mobili Registrati
              </h4>
              {card?.vehicles && card.vehicles.length > 0 ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  {card.vehicles.map((v, i) => (
                    <div key={i} style={{ padding: 16, border: "1px solid var(--pd-border)", borderRadius: "var(--pd-radius-lg)", background: "var(--pd-surface-low)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <strong style={{ display: "block" }}>{v.brand || v.model || "Veicolo"} ({v.year || "-"})</strong>
                        <span style={{ fontSize: 13, color: "var(--pd-text-muted)" }}>Targa: {v.plate || "-"}</span>
                      </div>
                      <span className="material-symbols-outlined" style={{ color: "var(--pd-ok)" }}>directions_car</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="pd-faint" style={{ margin: 0, fontStyle: "italic" }}>
                  Nessun bene mobile registrato presente in banca dati.
                </p>
              )}
            </div>

            {/* Patrimonio Immobiliare */}
            <div>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-accent)", textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>domain</span>
                Patrimonio Immobiliare (Visure Catastali)
              </h4>
              <div className="pd-table-wrap">
                <table className="pd-table">
                  <thead>
                    <tr>
                      <th>Estremi Catastali</th>
                      <th>Ubicazione</th>
                      <th style={{ textAlign: "center" }}>Mq</th>
                      <th>Quota</th>
                      <th className="pd-num">Valore Stimato</th>
                    </tr>
                  </thead>
                  <tbody>
                    {card?.real_estates && card.real_estates.length > 0 ? (
                      card.real_estates.map((re, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{re.catasto_data || re.type || "Immobile"}</td>
                          <td>{re.address || "-"}</td>
                          <td style={{ textAlign: "center" }}>{re.sqm || "-"}</td>
                          <td>{re.share || "100%"}</td>
                          <td className="pd-num" style={{ fontWeight: 700 }}>
                            € {(Number(re.estimated_value) || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", color: "var(--pd-text-muted)", padding: 18 }}>
                          Nessun immobile rilevato a visura. Carica visure catastali nel pannello documenti.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT 5: CRISI E SOSTENIBILITA */}
      {activeTab === "crisi" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="pd-card">
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined" style={{ color: "var(--pd-accent)" }}>
                  monitoring
                </span>
                Analisi di Sostenibilità e Rischio
              </h3>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 24 }}>
              {/* Risk Light */}
              <div
                style={{
                  background: "var(--pd-surface-mid)",
                  borderRadius: "var(--pd-radius-lg)",
                  padding: 24,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  borderLeft: "6px solid var(--pd-outline)",
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", marginBottom: 8 }}>
                  Semaforo di Rischio
                </span>
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: "50%",
                    background: "var(--pd-surface-highest)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 12,
                  }}
                >
                  <span className="material-symbols-outlined" style={{ color: "var(--pd-text-muted)", fontSize: 36 }}>
                    help_outline
                  </span>
                </div>
                <span style={{ fontSize: 18, fontWeight: 700, color: "var(--pd-text-muted)", textTransform: "uppercase" }}>
                  IN ATTESA DATI
                </span>
                <p style={{ fontSize: 12, color: "var(--pd-text-muted)", marginTop: 8, textAlign: "center" }}>
                  Completare il caricamento documentale per calcolare il rischio
                </p>
              </div>

              {/* Metrics */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div style={{ padding: 16, background: "#fff", border: "1px solid var(--pd-border)", borderRadius: "var(--pd-radius)" }}>
                    <span className="pd-kpi__label">Reddito Netto Dichiarato</span>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--pd-primary)", marginTop: 4 }}>
                      € {(card?.debtor?.monthly_net_income || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })} / mese
                    </div>
                  </div>
                  <div style={{ padding: 16, background: "#fff", border: "1px solid var(--pd-border)", borderRadius: "var(--pd-radius)" }}>
                    <span className="pd-kpi__label">Spese Dichiarate</span>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--pd-accent)", marginTop: 4 }}>
                      € {totalMonthlyExpenses.toLocaleString("it-IT", { minimumFractionDigits: 2 })} / mese
                    </div>
                  </div>
                </div>

                <div style={{ padding: 16, background: "#fff", border: "1px solid var(--pd-border)", borderRadius: "var(--pd-radius)" }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 12 }}>
                    Capacità Residua di Sostentamento
                  </h4>
                  <div style={{ fontSize: 22, fontWeight: 700, color: (card?.debtor?.monthly_net_income || 0) - totalMonthlyExpenses >= 0 ? "var(--pd-ok)" : "var(--pd-danger)" }}>
                    € {((card?.debtor?.monthly_net_income || 0) - totalMonthlyExpenses).toLocaleString("it-IT", { minimumFractionDigits: 2 })} / mese
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STICKY ACTIONS BAR */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: "var(--pd-sidebar-width)",
          right: 0,
          height: 64,
          background: "#fff",
          borderTop: "1px solid var(--pd-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 var(--pd-gutter)",
          boxShadow: "0 -4px 12px rgba(0,0,0,0.06)",
          zIndex: 30,
        }}
      >
        <button
          className="pd-btn pd-btn--secondary"
          onClick={handleSaveDraft}
          disabled={saving || !selectedCaseId}
        >
          <span className="material-symbols-outlined">save</span>
          {saving ? "Salvataggio..." : "Salva Bozza"}
        </button>

        <div style={{ display: "flex", gap: 12 }}>
          <button
            className="pd-btn pd-btn--primary"
            onClick={() => {
              handleSaveDraft();
              router.push(`/valutazione?caseId=${selectedCaseId}`);
            }}
          >
            Revisiona e Continua
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DatiEconomiciPage() {
  return (
    <Suspense fallback={<div className="pd-card">Caricamento Dati Economici...</div>}>
      <DatiEconomiciContent />
    </Suspense>
  );
}
