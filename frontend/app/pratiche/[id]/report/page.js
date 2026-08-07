import { redirect } from "next/navigation";

export default function PracticeReportRedirect({ params }) {
  redirect(`/report?caseId=${params.id}`);
}
