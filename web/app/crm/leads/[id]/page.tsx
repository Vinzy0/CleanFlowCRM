import Link from "next/link";
import { notFound } from "next/navigation";
import { api, authenticatedApi, LeadDetail, PublicConfig, Activity } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import StatusForm from "../../status-form";
import SubmitButton from "@/app/submit-button";
import { generateDraftReply, retryClassification } from "@/app/actions";

function activityDescription(activity: Activity) {
  if (activity.type === "lead_created") return "Lead created";
  if (activity.type === "status_changed") return `Status changed from ${activity.content.from} to ${activity.content.to}`;
  if (activity.type === "ai_classified") return activity.status === "completed" ? `AI classified this lead as ${activity.content.priority} priority` : "AI classification failed";
  if (activity.type === "reply_generated") return activity.status === "completed" ? "Draft reply generated" : "Draft reply generation failed";
  return activity.type.replaceAll("_", " ");
}

export default async function LeadDetailPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const leadId = Number((await params).id);
  if (!Number.isSafeInteger(leadId) || leadId < 1) notFound();
  const [response, configResponse] = await Promise.all([
    authenticatedApi(`/api/leads/${leadId}`).catch(() => null),
    api("/api/config").catch(() => null),
  ]);
  if (response?.status === 404) notFound();
  if (!response?.ok || !configResponse?.ok) return <main><h1>Lead unavailable</h1><p role="alert" className="error">Couldn’t load this lead. Refresh the page to try again.</p></main>;
  const lead: LeadDetail = await response.json();
  const config: PublicConfig = await configResponse.json();
  const { error } = await searchParams;
  const latestDraft = [...lead.activities].reverse().find((activity) => activity.type === "reply_generated" && activity.status === "completed")?.content.draft;
  return <main className="lead-detail">
    <Link href="/crm/leads" className="back-link">← All leads</Link>
    <div className="detail-heading"><div><h1>{lead.name}</h1><p>{lead.service_type} · Inquiry #{lead.id}</p></div><span className="stage">{lead.pipeline_stage}</span></div>
    {error && <p role="alert" className="error">{error === "status" ? "Status wasn’t updated." : error === "analysis" ? "AI analysis is unavailable. The lead is saved; you can retry." : "Draft reply is unavailable. Please try again."}</p>}
    <div className="detail-actions"><a className="button" href={`mailto:${lead.email}`}>Contact customer</a><form action={generateDraftReply.bind(null, lead.id)}><SubmitButton label="Draft reply" /></form></div>
    <div className="detail-grid"><div className="detail-primary">
      <section className="detail-panel"><h2>Customer</h2><dl className="detail-list"><div><dt>Name</dt><dd>{lead.name}</dd></div><div><dt>Email</dt><dd><a href={`mailto:${lead.email}`}>{lead.email}</a></dd></div><div><dt>Phone</dt><dd>{lead.phone}</dd></div></dl></section>
      <section className="detail-panel"><h2>Request</h2><dl className="detail-list"><div><dt>Service</dt><dd>{lead.service_type}</dd></div><div><dt>Property type</dt><dd>{lead.property_type}</dd></div><div><dt>Preferred date</dt><dd>{formatDate(lead.preferred_date)}</dd></div></dl><div className="inquiry-message"><h3>Original inquiry</h3><p>{lead.message}</p></div></section>
      <section className="detail-panel"><h2>AI analysis</h2>{lead.analysis ? <dl className="detail-list"><div><dt>Summary</dt><dd className="summary-text">{lead.analysis.summary}</dd></div><div><dt>Category</dt><dd>{lead.analysis.service_category}</dd></div><div><dt>Priority</dt><dd>{lead.analysis.priority}</dd></div><div><dt>Rationale</dt><dd>{lead.analysis.classification_rationale}</dd></div></dl> : <div className="analysis-empty"><p className="muted-copy">No AI analysis is available for this lead yet. The inquiry remains saved.</p><form action={retryClassification.bind(null, lead.id)}><SubmitButton label="Retry analysis" /></form></div>}</section>
      {typeof latestDraft === "string" && <section className="detail-panel"><h2>Suggested reply</h2><p className="muted-copy">Review and edit this draft. Email sending will be available in a later phase.</p><textarea className="draft-textarea" aria-label="Suggested reply draft" defaultValue={latestDraft} rows={10} /></section>}
    </div><div className="detail-secondary">
      <section className="detail-panel"><h2>CRM</h2><dl className="detail-list"><div><dt>Current stage</dt><dd><span className="stage">{lead.pipeline_stage}</span></dd></div><div><dt>Created</dt><dd>{formatDateTime(lead.created_at)}</dd></div><div><dt>Last updated</dt><dd>{formatDateTime(lead.updated_at)}</dd></div></dl><div className="status-control"><h3>Change status</h3><StatusForm leadId={lead.id} customerName={lead.name} currentStage={lead.pipeline_stage} stages={config.pipeline_stages} returnTo="detail" /></div></section>
      <section className="detail-panel"><h2>Activity</h2>{lead.activities.length === 0 ? <p className="muted-copy">No activity recorded yet.</p> : <ol className="timeline">{lead.activities.map((activity) => <li key={activity.id}><strong>{activityDescription(activity)}</strong><time dateTime={activity.created_at}>{formatDateTime(activity.created_at)}</time></li>)}</ol>}</section>
    </div></div>
  </main>;
}
