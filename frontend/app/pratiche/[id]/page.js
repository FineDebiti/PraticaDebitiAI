import { redirect } from "next/navigation";

// La pagina pratica non esiste più come pagina a sé: la scheda cliente è ora
// la pagina centrale (con i documenti nel pannello laterale). Reindirizziamo.
export default function CaseRedirect({ params }) {
  redirect(`/pratiche/${params.id}/scheda`);
}
