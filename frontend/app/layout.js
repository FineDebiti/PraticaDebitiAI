import Link from "next/link";
import "./design-system.css";   // token + componenti Direzione B (fonte unica di colori/spazi)

export const metadata = {
  title: "DossierLex",
  icons: { icon: "/DossierLex-logo.svg" },
};

const NAV = [
  { icon: "📁", label: "Pratiche", href: "/", active: true },
];

export default function RootLayout({ children }) {
  return (
    <html lang="it">
      <body className="pd-app" style={{ margin: 0 }}>
        <style>{`
          .app-shell { display: flex; min-height: 100vh; align-items: stretch; }
          .app-sidebar {
            width: 220px; flex-shrink: 0; position: sticky; top: 0; height: 100vh;
            background: var(--pd-primary); color: #fff; display: flex; flex-direction: column;
            box-sizing: border-box; overflow: hidden;
          }
          .app-main { flex: 1; min-width: 0; padding: 24px; max-width: 1600px; box-sizing: border-box; }
          .nav-item {
            display: flex; align-items: center; gap: 12px; padding: 11px 18px;
            font-size: 15px; text-decoration: none; color: #fff; white-space: nowrap;
          }
          .nav-item .nav-icon { font-size: 17px; width: 20px; text-align: center; flex-shrink: 0; }
          .nav-active { background: var(--pd-accent); font-weight: bold; }
          .nav-link:hover { background: rgba(255,255,255,0.10); }
          .nav-disabled { color: rgba(255,255,255,0.55); cursor: default; }
          .nav-soon { margin-left: auto; font-size: 10px; background: rgba(255,255,255,0.12); padding: 2px 6px; border-radius: 8px; }
          @media (max-width: 800px) {
            .app-sidebar { width: 56px; }
            .nav-label, .nav-soon, .brand-sub { display: none; }
            .brand-logo { display: none; }
            .nav-item { justify-content: center; padding: 12px 0; gap: 0; }
          }
        `}</style>

        <div className="app-shell">
          <aside className="app-sidebar">
            <div style={{ padding: "18px 18px 14px", borderBottom: "1px solid rgba(255,255,255,0.12)", marginBottom: 8 }}>
              <img className="brand-logo" src="/DossierLex-logo-white.svg" alt="DossierLex"
                style={{ width: "100%", maxWidth: 150, height: "auto", display: "block" }} />
            </div>

            <nav style={{ display: "flex", flexDirection: "column", flex: 1 }}>
              {NAV.map(item => (
                <Link key={item.label} href={item.href} className="nav-item nav-link nav-active" title={item.label}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </Link>
              ))}

              <span className="nav-item nav-disabled" title="Altre funzioni in arrivo" style={{ marginTop: "auto", borderTop: "1px solid rgba(255,255,255,0.12)" }}>
                <span className="nav-icon">⏳</span>
                <span className="nav-label">Altro in arrivo</span>
              </span>
            </nav>
          </aside>

          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
