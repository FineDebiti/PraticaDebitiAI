import { redirect } from "next/navigation";

export default function PracticeValutazioneRedirect({ params }) {
  redirect(`/pratiche/${params.id}/scheda/econometria`);
}
