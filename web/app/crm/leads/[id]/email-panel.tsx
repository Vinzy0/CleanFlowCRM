"use client";

import { useActionState, useState } from "react";
import { sendLeadEmail, type EmailState } from "@/app/actions";
import { EmailStatusChip } from "@/app/crm/badges";
import type { EmailDelivery } from "@/lib/api";

const EMPTY: EmailState = { error: "", notice: "", duplicate: false };

const DELIVERY_NOTES: Record<EmailDelivery, string> = {
  redirected: "Demo mode: this message will be delivered to the controlled demo inbox, never to the customer address.",
  disabled: "Email delivery is switched off in this environment, so sending will report a configuration error.",
  sandbox: "Sandbox mode: this message will be captured by the local outbox instead of being delivered.",
  live: "",
};

export default function EmailPanel({
  leadId,
  customerName,
  customerEmail,
  delivery,
  defaultSubject,
  defaultBody,
  lastStatus,
  lastMessage,
}: {
  leadId: number;
  customerName: string;
  customerEmail: string;
  delivery: EmailDelivery;
  defaultSubject: string;
  defaultBody: string;
  lastStatus: string | null;
  lastMessage: string;
}) {
  const [state, action, pending] = useActionState(sendLeadEmail.bind(null, leadId), EMPTY);
  const [subject, setSubject] = useState(defaultSubject);
  const [body, setBody] = useState(defaultBody);
  const ready = subject.trim().length >= 3 && body.trim().length >= 10;

  return (
    <form action={action} className="email-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Reply to {customerName}</h2>
          <p className="muted-copy">
            Edit the draft, then send it yourself. Nothing is emailed until you press Send.
          </p>
        </div>
        <EmailStatusChip status={pending ? "pending" : lastStatus} />
      </div>

      {delivery !== "live" && <p className="muted-copy">{DELIVERY_NOTES[delivery]}</p>}

      {state.error && (
        <p role="alert" className="error">
          {state.error}
        </p>
      )}
      {state.notice && (
        <p role="status" className="notice">
          {state.notice}
        </p>
      )}
      {!state.error && !state.notice && lastStatus === "failed" && lastMessage && (
        <p role="alert" className="error">
          Last attempt failed: {lastMessage}
        </p>
      )}

      <label>
        Subject
        <input
          name="subject"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          maxLength={200}
          disabled={pending}
          required
        />
      </label>
      <label>
        Message
        <textarea
          name="body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          maxLength={5000}
          rows={10}
          disabled={pending}
          className="draft-textarea"
        />
      </label>
      <div className="email-footer">
        <span className="muted-copy">
          To: {customerEmail}
          {delivery === "redirected" ? " (redirected in demo mode)" : ""}
        </span>
        <button className="button" type="submit" disabled={pending || !ready}>
          {pending ? "Sending…" : "Send email"}
        </button>
      </div>
    </form>
  );
}
