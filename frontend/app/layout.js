import "./design-system.css";
import AppShell from "./components/AppShell";

export const metadata = {
  title: "DossierLex - Pre-Analisi Documentale, Legale ed Econometrica",
  icons: { icon: "/DossierLex-logo.svg" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="it">
      <head>
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
