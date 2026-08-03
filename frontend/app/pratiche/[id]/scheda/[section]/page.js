import { notFound } from "next/navigation";
import Scheda from "../page";

const VALID_SECTIONS = new Set([
  "riepilogo",
  "raccolta",
  "anagrafica",
  "documenti",
  "patrimonio",
  "banca",
  "aer",
  "aziende",
  "indicatori",
  "econometria",
  "report",
  "audit",
]);

export default function SchedaSectionPage({ params }) {
  if (!VALID_SECTIONS.has(params.section)) notFound();
  return <Scheda params={params} initialSection={params.section} />;
}
