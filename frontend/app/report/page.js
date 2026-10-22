"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

function ReportRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseId = searchParams.get("caseId");

  useEffect(() => {
    if (caseId) {
      router.replace(`/pratiche/${caseId}/scheda/report`);
    } else {
      router.replace("/");
    }
  }, [caseId, router]);

  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--pd-text-muted)" }}>
      Reindirizzamento al Report di Pre-Analisi...
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center" }}>Caricamento...</div>}>
      <ReportRedirect />
    </Suspense>
  );
}
