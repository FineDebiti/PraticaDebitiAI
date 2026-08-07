import { redirect } from "next/navigation";

export default function PracticeValutazioneRedirect({ params }) {
  redirect(`/valutazione?caseId=${params.id}`);
}
