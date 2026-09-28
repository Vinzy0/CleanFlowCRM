import Link from "next/link";
import { notFound } from "next/navigation";
import {
  api,
  authenticatedApi,
  LeadDetail,
  PublicConfig,
  Activity,
  latestDraft,
  latestEmail,
  latestClassification,
} from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { noticeFrom } from "@/lib/notices";
import { AiStatusChip, DemoBadge, EmailStatusChip, PriorityChip, StatusNotice } from "../../badges";
import StatusForm from "../../status-form";
import SubmitButton from "@/app/submit-button";
import EmailPanel from "./email-panel";
import { generateDraftReply, retryClassification, retryOwnerNotification } from "@/app/actions";

function activityDescription(activity: Activity) {
  const content = activity.content ?? {};
  switch (activity.type) {
    case "lead_created":
      return "Lead created";
    case "status_changed":
      return `Status changed from ${content.from} to ${content.to}`;
    case "ai_classified":
      return activity.status === "completed"
        ? `AI classified this lead as ${content.priority} priority${content.reused ? " (reused stored result)" : ""}`
        : "AI classification failed";
    case "reply_generated":
      return activity.status === "completed" ? "Draft reply generated" : "Draft reply generation failed";
    case "email_sent":
      if (content.sandboxed) return "Email captured in the sandbox outbox";
      return content.email_type === "owner_notification"
        ? "Owner notified by email"
        : `Email sent to ${content.to ?? "the customer"}${content.redirected ? " (demo inbox)" : ""}`;
    case "email_failed":
      return content.email_type === "owner_notification"
        ? `Owner notification failed: ${content.message ?? "unknown error"}`
        : `Email failed: ${content.message ?? "unknown error"}`;
    default:
      return activity.type.replaceAll("_", " ");
  }
}

export default async function LeadDetailPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string; ok?: string }>;
}) {
  const leadId = Number((await params).id);
  if (!Number.isSafeInteger(leadId) || leadId < 1) notFound();
  const [response, configResponse] = await Promise.all([
    authenticatedApi(`/api/leads/${leadId}`).catch(() => null),
    api("/api/config").catch(() => null),
  ]);
  if (response?.status === 404) notFound();
  if (!response?.ok || !configResponse?.ok) {
    return <main><h1>Lead unavailable</h1><p role="alert" className="error">Couldn’t load this lead. Refresh the page to try again.</p></main>;
  }
  const lead: LeadDetail = await response.json();
  const config: PublicConfig = await configResponse.json();
  const { error, ok } = await searchParams;
  const draft = latestDraft(lead.activities);
  const classification = latestClassification(lead.activities);
  const ownerNotification = latestEmail(lead.activities, "owner_notification");
  const customerReply = latestEmail(lead.activities, "customer_reply");
  const ownerEmailStatus = ownerNotification?.status === "sent" && ownerNotification.content.sandboxed ? "captured" : ownerNotification?.status ?? null;
  const customerEmailStatus = customerReply?.status === "sent" && customerReply.content.sandboxed ? "captured" : customerReply?.status ?? null;
  const analysisFailed = classification?.status === "failed";

  return <main className="lead-detail">
    <Link href="/crm/leads" className="back-link">← All leads</Link>
    <div className="detail-heading"><div><h1>{lead.name}</h1><p>{lead.service_type} · Inquiry #{lead.id}</p></div><div className="chip-row"><PriorityChip priority={lead.priority} /><span className="stage">{lead.pipeline_stage}</span><DemoBadge isDemo={lead.is_demo} /></div></div>
    <StatusNotice notice={noticeFrom({ error, ok })} />

    <section className="detail-panel" aria-label="Actions">
      <div className="panel-heading-row"><div><h2>Actions</h2><p className="muted-copy">Drafting never sends anything. You approve every email before it leaves.</p></div><AiStatusChip status={classification?.status ?? null} /></div>
      <div className="detail-actions">
        <a className="button button-secondary" href={`mailto:${lead.email}`}>Contact customer</a>
        <form action={generateDraftReply.bind(null, lead.id)}><SubmitButton label="Draft reply" pendingLabel="Drafting…" /></form>
        {analysisFailed && <form action={retryClassification.bind(null, lead.id)}><SubmitButton label="Retry AI analysis" pendingLabel="Analysing…" /></form>}
        {ownerNotification?.status === "failed" && <form action={retryOwnerNotification.bind(null, lead.id)}><SubmitButton label="Retry owner notification" pendingLabel="Retrying…" /></form>}
      </div>
      {analysisFailed && <p role="alert" className="error">AI analysis failed for this lead. The lead is saved — retry the analysis when you’re ready.</p>}
    </section>

    <div className="detail-grid"><div className="detail-primary">
      <section className="detail-panel"><h2>Customer</h2><dl className="detail-list"><div><dt>Name</dt><dd>{lead.name}</dd></div><div><dt>Email</dt><dd><a href={`mailto:${lead.email}`}>{lead.email}</a></dd></div><div><dt>Phone</dt><dd>{lead.phone}</dd></div></dl></section>

      <section className="detail-panel"><h2>Request</h2><dl className="detail-list"><div><dt>Service</dt><dd>{lead.service_type}</dd></div><div><dt>Property type</dt><dd>{lead.property_type}</dd></div><div><dt>Preferred date</dt><dd>{formatDate(lead.preferred_date)}</dd></div></dl><div className="inquiry-message"><h3>Original inquiry</h3><p>{lead.message}</p></div></section>

      <section className="detail-panel"><h2>AI analysis</h2>{lead.analysis ? <><div className="chip-row"><AiStatusChip status={classification?.status ?? "completed"} /><span className="chip neutral">{lead.analysis.service_category}</span><PriorityChip priority={lead.analysis.priority} /></div><dl className="detail-list"><div><dt>Summary</dt><dd className="summary-text">{lead.analysis.summary}</dd></div><div><dt>Category</dt><dd>{lead.analysis.service_category}</dd></div><div><dt>Priority</dt><dd>{lead.analysis.priority}</dd></div><div><dt>Why</dt><dd>{lead.analysis.classification_rationale}</dd></div>{lead.analysis.matched_priority_rules.length > 0 && <div><dt>Matched rules</dt><dd>{lead.analysis.matched_priority_rules.join("; ")}</dd></div>}<div><dt>Model</dt><dd className="muted-copy">{lead.analysis.model}</dd></div></dl></> : <div className="analysis-empty"><AiStatusChip status={classification?.status ?? null} /><p className="muted-copy">No AI analysis is stored for this lead yet. The inquiry remains saved and can be retried from Actions.</p><form action={retryClassification.bind(null, lead.id)}><SubmitButton label="Run AI analysis" pendingLabel="Analysing…" /></form></div>}</section>

      {draft !== null ? (
        <EmailPanel key={draft} leadId={lead.id} customerName={lead.name} customerEmail={lead.email} delivery={config.email_delivery} defaultSubject={`Re: your ${lead.service_type} request`} defaultBody={draft} lastStatus={customerEmailStatus} lastMessage={String(customerReply?.content.message ?? "")} />
      ) : (
        <section className="detail-panel"><div className="panel-heading-row"><div><h2>Reply to customer</h2><p className="muted-copy">Generate a draft reply, then edit it before sending. Emails are never sent automatically.</p></div><EmailStatusChip status={customerReply?.status ?? null} /></div>{customerReply?.status === "failed" && <p role="alert" className="error">Last send failed: {String(customerReply.content.message ?? "")}</p>}<form action={generateDraftReply.bind(null, lead.id)}><SubmitButton label="Draft reply" pendingLabel="Drafting…" /></form></section>
      )}
    </div><div className="detail-secondary">
      <section className="detail-panel"><h2>CRM</h2><dl className="detail-list"><div><dt>Current stage</dt><dd><span className="stage">{lead.pipeline_stage}</span></dd></div><div><dt>Created</dt><dd>{formatDateTime(lead.created_at)}</dd></div><div><dt>Last updated</dt><dd>{formatDateTime(lead.updated_at)}</dd></div></dl><div className="status-control"><h3>Change status</h3><StatusForm leadId={lead.id} customerName={lead.name} currentStage={lead.pipeline_stage} stages={config.pipeline_stages} returnTo="detail" /></div></section>

      <section className="detail-panel"><h2>Email</h2><dl className="detail-list"><div><dt>Owner notice</dt><dd><EmailStatusChip status={ownerEmailStatus} />{ownerNotification?.status === "failed" && <span className="muted-copy"> {String(ownerNotification.content.message ?? "")}</span>}</dd></div><div><dt>Customer reply</dt><dd><EmailStatusChip status={customerEmailStatus} />{customerReply?.content.delivered_to && <span className="muted-copy"> → {String(customerReply.content.delivered_to)}</span>}</dd></div></dl></section>

      <section className="detail-panel"><h2>Activity history</h2>{lead.activities.length === 0 ? <p className="muted-copy">No activity recorded yet.</p> : <ol className="timeline">{lead.activities.map((activity) => <li key={activity.id}><strong>{activityDescription(activity)}</strong><time dateTime={activity.created_at}>{formatDateTime(activity.created_at)}</time></li>)}</ol>}</section>
    </div></div>
  </main>;
}
