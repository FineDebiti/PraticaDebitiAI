import { headers } from "next/headers";
import "./design-system.css";
import AppShell from "./components/AppShell";

export const dynamic = "force-dynamic";

const SAFE_SESSION_TOKEN_RE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

export const metadata = {
  title: "DossierLex - Pre-Analisi Documentale, Legale ed Econometrica",
  icons: { icon: "/DossierLex-logo.svg" },
};

export default function RootLayout({ children }) {
  const rawInjected = (headers().get("x-dossierlex-injected-session") || "").trim();
  const injectedSession = SAFE_SESSION_TOKEN_RE.test(rawInjected) ? rawInjected : "";

  return (
    <html lang="it">
      <head>
        {injectedSession ? (
          <script
            dangerouslySetInnerHTML={{
              __html: `window.__DOSSIERLEX_SESSION__=${JSON.stringify(injectedSession)};`,
            }}
          />
        ) : null}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="pd-app">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
