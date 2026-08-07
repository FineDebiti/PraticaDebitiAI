"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { listCases, checkHealth } from "../api";

const NAV = [
  { icon: "gavel", label: "Pratiche", href: "/", baseHref: "/" },
  { icon: "database", label: "Dati economici", href: "/dati-economici", baseHref: "/dati-economici" },
  { icon: "analytics", label: "Valutazione econometrica", href: "/valutazione", baseHref: "/valutazione" },
  { icon: "description", label: "Report", href: "/report", baseHref: "/report" },
];

function AppShellInner({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [cases, setCases] = useState([]);
  const [isBackendOnline, setIsBackendOnline] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showSupportModal, setShowSupportModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Extract caseId from URL: either ?caseId= or /pratiche/[id]/...
  const caseIdFromQuery = searchParams.get("caseId");
  const caseIdFromPath = pathname.match(/^\/pratiche\/([^/]+)/)?.[1] || null;
  const activeCaseId = caseIdFromQuery || caseIdFromPath || "";

  useEffect(() => {
    async function loadCases() {
      try {
        const list = await listCases();
        if (Array.isArray(list)) setCases(list);
      } catch {
        // silent fallback if backend is offline
      }
    }
    async function pingBackend() {
      const ok = await checkHealth();
      setIsBackendOnline(ok);
    }

    loadCases();
    pingBackend();
    const interval = setInterval(pingBackend, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeCase = cases.find(c => c.id === activeCaseId);

  // Build nav href: if a case is selected, append caseId to section links
  function getNavHref(item) {
    if (item.baseHref === "/") return "/";
    if (activeCaseId) {
      return `${item.baseHref}?caseId=${activeCaseId}`;
    }
    return item.baseHref;
  }

  // Determine active route
  function isNavActive(itemHref) {
    if (itemHref === "/") {
      return pathname === "/" || (pathname.startsWith("/pratiche") && !pathname.includes("/valutazione") && !pathname.includes("/report") && !pathname.includes("/scheda"));
    }
    if (itemHref === "/dati-economici") {
      return pathname.startsWith("/dati-economici") || pathname.includes("/scheda");
    }
    if (itemHref === "/valutazione") {
      return pathname.startsWith("/valutazione") || (pathname.includes("/valutazione") && pathname.startsWith("/pratiche"));
    }
    if (itemHref === "/report") {
      return pathname.startsWith("/report") || (pathname.includes("/report") && pathname.startsWith("/pratiche"));
    }
    return pathname === itemHref;
  }

  function handleSearchKeyDown(e) {
    if (e.key === "Enter" && searchQuery.trim()) {
      router.push(`/?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  }

  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className="app-sidebar">
        <div className="app-brand">
          <p className="app-brand__title">DossierLex</p>
          <p className="app-brand__sub">Institutional Portal</p>
        </div>

        <nav className="app-nav" aria-label="Navigazione principale">
          {NAV.map((item) => {
            const active = isNavActive(item.baseHref);
            const href = getNavHref(item);
            return (
              <Link
                key={item.label}
                href={href}
                className={`app-nav__item ${active ? "app-nav__item--active" : ""}`}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="app-nav__label">{item.label}</span>
              </Link>
            );
          })}

          {/* Practice context indicator */}
          {activeCase && (
            <div className="app-nav__context">
              <span className="app-nav__context-label">Pratica attiva</span>
              <span className="app-nav__context-value">
                #{activeCase.code || activeCase.id?.slice(0, 8)}
              </span>
              <span className="app-nav__context-name">
                {activeCase.client_name || "Cliente"}
              </span>
            </div>
          )}

          <div className="app-nav__bottom">
            <button
              type="button"
              className="app-nav__item"
              onClick={() => setShowSettingsModal(true)}
              style={{ background: "none", border: 0, width: "100%", cursor: "pointer", textAlign: "left" }}
              title="Impostazioni"
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                settings
              </span>
              <span className="app-nav__label">Impostazioni</span>
            </button>
            <button
              type="button"
              className="app-nav__item"
              onClick={() => setShowSupportModal(true)}
              style={{ background: "none", border: 0, width: "100%", cursor: "pointer", textAlign: "left" }}
              title="Supporto"
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                help
              </span>
              <span className="app-nav__label">Supporto</span>
            </button>
          </div>
        </nav>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="app-main">
        <header className="app-topbar">
          <div className="app-topbar__title">
            <strong style={{ fontSize: 15, color: "var(--pd-primary)" }}>
              Pre-analisi documentale, legale ed econometrica
            </strong>
          </div>

          <div style={{ flex: 1, maxWidth: 360, margin: "0 16px" }}>
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <input
                type="text"
                className="pd-input"
                placeholder="Cerca codice, cliente o CF..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                style={{ paddingLeft: 36, height: 38, fontSize: 13 }}
              />
              <span
                className="material-symbols-outlined"
                style={{ position: "absolute", left: 10, color: "var(--pd-outline)", fontSize: 18, pointerEvents: "none" }}
              >
                search
              </span>
            </div>
          </div>

          <div className="app-topbar__actions">
            <span className={`pd-badge pd-badge--${isBackendOnline ? "ok" : "danger"}`}>
              {isBackendOnline ? "Sistema Operativo" : "Backend Disconnesso"}
            </span>
            <button
              className="pd-icon-btn"
              type="button"
              title="Notifiche"
              onClick={() => alert("Nessuna nuova notifica di sistema.")}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                notifications
              </span>
            </button>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 8px",
                borderRadius: "var(--pd-radius)",
                background: "var(--pd-surface-low)",
                border: "1px solid var(--pd-border)",
              }}
            >
              <span className="material-symbols-outlined" style={{ color: "var(--pd-primary)" }}>
                account_circle
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--pd-primary)" }}>
                Dr. Alessandro Rossi
              </span>
            </div>
          </div>
        </header>

        <div className="app-content">{children}</div>
      </main>

      {/* SETTINGS MODAL */}
      {showSettingsModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={() => setShowSettingsModal(false)}
        >
          <div
            className="pd-card"
            style={{ width: 480, maxWidth: "90vw" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined">settings</span>
                Impostazioni di Sistema
              </h3>
              <button
                className="pd-btn pd-btn--ghost"
                onClick={() => setShowSettingsModal(false)}
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 12 }}>
              <div className="pd-field">
                <label className="pd-field__label">Provider OCR / LLM Backend</label>
                <input className="pd-input" value="FastAPI + Tesseract / OpenAI / Gemini" readOnly />
              </div>
              <div className="pd-field">
                <label className="pd-field__label">Modalità Calcolo Econometrico</label>
                <select className="pd-select">
                  <option>D. Lgs. 14/2019 (Codice Crisi d'Impresa)</option>
                  <option>Verifica Anatocismo e Usura (TEGM)</option>
                </select>
              </div>
              <div className="pd-field">
                <label className="pd-field__label">Versione Frontend</label>
                <p style={{ margin: 0, fontSize: 13, color: "var(--pd-text-muted)" }}>
                  Institutional Heritage v2.4 — Stitch Approved Reference
                </p>
              </div>
            </div>
            <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
              <button className="pd-btn pd-btn--primary" onClick={() => setShowSettingsModal(false)}>
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SUPPORT MODAL */}
      {showSupportModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={() => setShowSupportModal(false)}
        >
          <div
            className="pd-card"
            style={{ width: 500, maxWidth: "90vw" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pd-card__head">
              <h3 className="pd-card__title">
                <span className="material-symbols-outlined">help</span>
                Supporto Istituzionale & Guida
              </h3>
              <button
                className="pd-btn pd-btn--ghost"
                onClick={() => setShowSupportModal(false)}
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
              <p style={{ fontSize: 14, color: "var(--pd-text-muted)", margin: 0 }}>
                La piattaforma <strong>DossierLex</strong> consente la gestione completa del ciclo di pre-analisi debitoria ed econometrica:
              </p>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--pd-text-muted)", display: "flex", flexDirection: "column", gap: 6 }}>
                <li><strong>Pratiche:</strong> Registrazione anagrafica persona/azienda e caricamento documenti con deduplicazione.</li>
                <li><strong>Dati Economici:</strong> Raccolta analitica guidata (Redditi, Spese, Stato Passivo, Patrimonio).</li>
                <li><strong>Valutazione Econometrica:</strong> Cruscotto indicatori di rischio, DTI Ratio, proiezioni e usura.</li>
                <li><strong>Report Finale:</strong> Dossier professionale auditabile ed esportabile in PDF.</li>
              </ul>
            </div>
            <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
              <button className="pd-btn pd-btn--primary" onClick={() => setShowSupportModal(false)}>
                Capito
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }) {
  return (
    <Suspense fallback={<div className="pd-app" style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>Caricamento...</div>}>
      <AppShellInner>{children}</AppShellInner>
    </Suspense>
  );
}
