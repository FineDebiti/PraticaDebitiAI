import Link from "next/link";
import "./design-system.css";

export const metadata = {
  title: "DossierLex",
  icons: { icon: "/DossierLex-logo.svg" },
};

const NAV = [
  { icon: "gavel", label: "Pratiche", href: "/", active: true },
  { icon: "database", label: "Dati economici", href: "/", muted: true },
  { icon: "analytics", label: "Valutazione", href: "/", muted: true },
  { icon: "description", label: "Report", href: "/", muted: true },
];

export default function RootLayout({ children }) {
  return (
    <html lang="it">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body className="pd-app">
        <div className="app-shell">
          <aside className="app-sidebar">
            <div className="app-brand">
              <p className="app-brand__title">DossierLex</p>
              <p className="app-brand__sub">Institutional Portal</p>
            </div>
            <nav className="app-nav" aria-label="Navigazione principale">
              {NAV.map((item) => (
                item.href && !item.muted ? (
                  <Link
                    key={item.label}
                    href={item.href}
                    className={`app-nav__item ${item.active ? "app-nav__item--active" : ""}`}
                    aria-current={item.active ? "page" : undefined}
                    title={item.label}
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">{item.icon}</span>
                    <span className="app-nav__label">{item.label}</span>
                  </Link>
                ) : (
                  <span
                    key={item.label}
                    className="app-nav__item app-nav__item--muted"
                    title={item.label}
                    aria-disabled="true"
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">{item.icon}</span>
                    <span className="app-nav__label">{item.label}</span>
                  </span>
                )
              ))}
              <div className="app-nav__bottom">
                <span className="app-nav__item" title="Impostazioni">
                  <span className="material-symbols-outlined" aria-hidden="true">settings</span>
                  <span className="app-nav__label">Impostazioni</span>
                </span>
                <span className="app-nav__item" title="Supporto">
                  <span className="material-symbols-outlined" aria-hidden="true">help</span>
                  <span className="app-nav__label">Supporto</span>
                </span>
              </div>
            </nav>
          </aside>
          <main className="app-main">
            <header className="app-topbar">
              <div className="app-topbar__title">
                <strong>Debt Analysis</strong>
                <span className="app-topbar__crumb">Pre-analisi documentale, legale ed econometrica</span>
              </div>
              <div className="app-topbar__actions">
                <span className="pd-badge pd-badge--info">Ambiente operativo</span>
                <button className="pd-icon-btn" type="button" aria-label="Notifiche">
                  <span className="material-symbols-outlined" aria-hidden="true">notifications</span>
                </button>
                <button className="pd-icon-btn" type="button" aria-label="Profilo utente">
                  <span className="material-symbols-outlined" aria-hidden="true">account_circle</span>
                </button>
              </div>
            </header>
            <div className="app-content">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
