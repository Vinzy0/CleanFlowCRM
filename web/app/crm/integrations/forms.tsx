"use client";
import { useActionState, useState } from "react";
import SubmitButton from "@/app/submit-button";
import { createKey, createWebhook, editSubscriptions, IntegrationState } from "./actions";

const initial: IntegrationState = { error: "", notice: "", secret: "" };
type Mutation = (state: IntegrationState, form: FormData) => Promise<IntegrationState>;
function Feedback({ state }: { state: IntegrationState }) {
  return <>{state.error && <p className="error" role="alert">{state.error}</p>}{state.notice && <p className="notice" role="status">{state.notice}</p>}</>;
}
function OneTimeSecret({ secret, label }: { secret: string; label: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return <p className="muted-copy">Credential hidden. It cannot be retrieved again.</p>;
  return <div className="secret-reveal"><label>{label}<input readOnly value={secret} autoComplete="off" onFocus={(event) => event.target.select()} /></label><p className="muted-copy">Copy this now and store it securely. It is shown once.</p><button className="button button-secondary" type="button" onClick={() => setHidden(true)}>I saved it — hide</button></div>;
}
export function KeyForm() {
  const [state, action] = useActionState(createKey, initial);
  return <form action={action} className="integration-form"><label>Key name<input name="name" required maxLength={120} placeholder="Make lead intake" /></label><fieldset><legend>Permissions</legend><label className="check-option"><input type="checkbox" name="scopes" value="leads:read" defaultChecked />Read leads</label><label className="check-option"><input type="checkbox" name="scopes" value="leads:write" defaultChecked />Create and update leads</label></fieldset><SubmitButton label="Generate API key" pendingLabel="Generating…" /><Feedback state={state} />{state.secret && <OneTimeSecret key={state.secret} secret={state.secret} label="New API key" />}</form>;
}
export function EventChoices({ events, selected = [] }: { events: string[]; selected?: string[] }) {
  return <fieldset className="event-options"><legend>Subscribed events</legend>{events.map((event) => <label className="check-option" key={event}><input type="checkbox" name="events" value={event} defaultChecked={selected.includes(event)} />{event}</label>)}</fieldset>;
}
export function WebhookForm({ events }: { events: string[] }) {
  const [state, action] = useActionState(createWebhook, initial);
  return <form action={action} className="integration-form"><label>Destination name<input name="name" required maxLength={120} placeholder="Make → Google Sheets" /></label><label>Webhook URL<input name="url" type="url" required maxLength={2048} placeholder="https://…" autoComplete="off" /></label><EventChoices events={events} selected={["lead.created"]} /><SubmitButton label="Register webhook" pendingLabel="Registering…" /><Feedback state={state} />{state.secret && <OneTimeSecret key={state.secret} secret={state.secret} label="New signing secret" />}</form>;
}
export function SubscriptionForm({ id, events, selected }: { id: number; events: string[]; selected: string[] }) {
  const [state, action] = useActionState(editSubscriptions.bind(null, id), initial);
  return <form action={action} className="integration-form"><EventChoices events={events} selected={selected} /><SubmitButton label="Save subscriptions" pendingLabel="Saving…" /><Feedback state={state} /></form>;
}
export function MutationForm({ action: mutation, label, pendingLabel = "Working…", confirm }: { action: Mutation; label: string; pendingLabel?: string; confirm?: string }) {
  const [state, action] = useActionState(mutation, initial);
  return <form action={action} onSubmit={(event) => { if (confirm && !window.confirm(confirm)) event.preventDefault(); }}><SubmitButton label={label} pendingLabel={pendingLabel} /><Feedback state={state} /></form>;
}
