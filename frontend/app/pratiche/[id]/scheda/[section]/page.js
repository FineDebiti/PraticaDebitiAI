"use client";
import Scheda from "../page";

export default function SchedaSectionPage({ params }) {
  return <Scheda params={params} initialSection={params?.section || "documenti"} />;
}
