import { changeStatus } from "@/app/actions";
import SubmitButton from "@/app/submit-button";

export default function StatusForm({
  leadId,
  customerName,
  currentStage,
  stages,
  returnTo,
}: {
  leadId: number;
  customerName: string;
  currentStage: string;
  stages: string[];
  returnTo: "pipeline" | "detail";
}) {
  return <form className="status-form" action={changeStatus.bind(null, leadId, returnTo)}><label><span className="sr-only">Change status for {customerName}</span><select name="stage" defaultValue={currentStage} aria-label={`Change status for ${customerName}`}>{stages.map((stage) => <option key={stage} value={stage}>{stage}</option>)}</select></label><SubmitButton label="Update" ariaLabel={`Update status for ${customerName}`} /></form>;
}
