import { redirect } from "next/navigation";

export default function PracticeReportRedirect({ params }) {
  redirect(`/pratiche/${params.id}/scheda/report`);
}
