"use client";
import { useActionState, useEffect, useState } from "react";
import { Lead } from "@/lib/api";
import SubmitButton from "@/app/submit-button";
import { saveWorkflow, WorkflowState } from "./workflow-actions";

function localDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
export default function WorkflowPanel({ lead, canEdit }: { lead: Lead; canEdit: boolean }) {
  const [followUp, setFollowUp] = useState("");
  const [appointment, setAppointment] = useState("");
  useEffect(() => { setFollowUp(localDate(lead.next_follow_up)); setAppointment(localDate(lead.appointment_at)); }, [lead.next_follow_up, lead.appointment_at]);
  const [state, action] = useActionState(async (previous: WorkflowState, form: FormData) => {
    for (const field of ["next_follow_up", "appointment_at"]) {
      const value = String(form.get(field) ?? "");
      if (value) form.set(field, new Date(value).toISOString());
    }
    return saveWorkflow(lead.id, previous, form);
  }, { error: "", notice: "" });
  return <section className="detail-panel"><h2>Follow-up & appointment</h2><p className="muted-copy">Dates use your browser’s local timezone.</p><form action={action} className="workflow-form"><fieldset disabled={!canEdit}><label>Lead source<input name="source" maxLength={120} defaultValue={lead.source ?? ""} placeholder="Website, referral, Make…" /></label><label>Tags, separated by commas<input name="tags" defaultValue={lead.tags.join(", ")} placeholder="website, deep-cleaning" /></label><label>Next action<input name="next_action" maxLength={500} defaultValue={lead.next_action ?? ""} placeholder="Call to confirm the quote" /></label><label>Next follow-up<input name="next_follow_up" type="datetime-local" value={followUp} onChange={(event) => setFollowUp(event.target.value)} /></label><label>Appointment<input name="appointment_at" type="datetime-local" value={appointment} onChange={(event) => setAppointment(event.target.value)} /></label>{canEdit && <SubmitButton label="Save workflow details" pendingLabel="Saving…" />}</fieldset>{!canEdit && <p className="muted-copy">Workflow edits are disabled for demo users.</p>}{state.error && <p className="error" role="alert">{state.error}</p>}{state.notice && <p className="notice" role="status">{state.notice}</p>}</form></section>;
}
