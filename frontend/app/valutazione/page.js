"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

function ValutazioneRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseId = searchParams.get("caseId");

  useEffect(() => {
    if (caseId) {
      router.replace(`/pratiche/${caseId}/scheda/econometria`);
    } else {
      router.replace("/");
    }
  }, [caseId, router]);

  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--pd-text-muted)" }}>
      Reindirizzamento alla Valutazione Econometrica...
    </div>
  );
}

export default function ValutazionePage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center" }}>Caricamento...</div>}>
      <ValutazioneRedirect />
    </Suspense>
  );
}
