"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

function DatiEconomiciRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseId = searchParams.get("caseId");

  useEffect(() => {
    if (caseId) {
      router.replace(`/pratiche/${caseId}/scheda/raccolta`);
    } else {
      router.replace("/");
    }
  }, [caseId, router]);

  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--pd-text-muted)" }}>
      Reindirizzamento alla Scheda Cliente...
    </div>
  );
}

export default function DatiEconomiciPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center" }}>Caricamento...</div>}>
      <DatiEconomiciRedirect />
    </Suspense>
  );
}
