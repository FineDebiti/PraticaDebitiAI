"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { PraticheDashboard } from "../components/PraticheHome";

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const u = new URL(window.location.href);
      if (u.searchParams.has("ticket")) {
        u.searchParams.delete("ticket");
        window.history.replaceState(null, "", `${u.pathname}${u.search}${u.hash}`);
      }
    } catch {
      // Ignora eventuali limiti su history.replaceState
    }
  }, []);

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

    function handleVisibilityChange() {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        emitLiveSignal();
      }
    }

    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", handleVisibilityChange);
    }
    return () => {
      clearInterval(timer);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
    };
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
