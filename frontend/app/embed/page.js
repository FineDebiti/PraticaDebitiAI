"use client";

import { Suspense, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { PraticheDashboard } from "../components/PraticheHome";

export const dynamic = "force-dynamic";

function EmbedContent() {
  const searchParams = useSearchParams();
  const embedToken = searchParams.get("token") || "";
  const liveEmittedRef = useRef(false);

  const handleLoaded = useCallback(() => {
    if (liveEmittedRef.current) return;
    liveEmittedRef.current = true;
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
  }, []);

  return <PraticheDashboard readOnly={true} embedToken={embedToken} onLoaded={handleLoaded} />;
}

export default function EmbedPage() {
  return (
    <Suspense fallback={<div style={{ padding: 20 }}>Caricamento vista DossierLex...</div>}>
      <EmbedContent />
    </Suspense>
  );
}
