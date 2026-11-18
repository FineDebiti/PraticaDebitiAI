"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { PraticheDashboard } from "../components/PraticheHome";

export const dynamic = "force-dynamic";

const HEARTBEAT_MS = 30000;

function emitLiveSignal() {
  try {
    if (typeof window !== "undefined" && window.parent) {
      window.parent.postMessage(
        { source: "dossierlex", status: "LIVE", version: "1.0" },
        "*"
      );
    }
  } catch {
    // Ignora eventuali restrizioni cross-origin del frame ospite
  }
}

function EmbedContent() {
  const [isLiveActive, setIsLiveActive] = useState(false);

  const handleLoaded = useCallback(() => {
    setIsLiveActive(true);
    emitLiveSignal();
  }, []);

  const handleError = useCallback(() => {
    setIsLiveActive(false);
  }, []);

  useEffect(() => {
    if (!isLiveActive) return undefined;
    const timer = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }
      emitLiveSignal();
    }, HEARTBEAT_MS);
    return () => clearInterval(timer);
  }, [isLiveActive]);

  return <PraticheDashboard readOnly={true} onLoaded={handleLoaded} onError={handleError} />;
}

export default function EmbedPage() {
  return (
    <Suspense fallback={<div style={{ padding: 20 }}>Caricamento vista DossierLex...</div>}>
      <EmbedContent />
    </Suspense>
  );
}
