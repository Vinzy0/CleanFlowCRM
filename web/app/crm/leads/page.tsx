import Link from "next/link";
import { getCrmSnapshot } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { noticeFrom } from "@/lib/notices";
import { DemoBadge, PriorityChip, StatusNotice } from "../badges";

export default async function LeadsPage({ searchParams }: {
  searchParams: Promise<{ error?: string; ok?: string }>;
}) {
  const { error, ok } = await searchParams;
  const snapshot = await getCrmSnapshot();
  if (!snapshot) {
    return <main><h1>Leads</h1><p role="alert" className="error">Couldn’t load leads. Refresh the page to try again.</p></main>;
  }
  const { leads } = snapshot;
  return <main>
    <div className="crm-topline"><div><h1>Leads</h1><p>Every request in one place.</p></div><Link className="button" href="/inquiry">New inquiry</Link></div>
    <StatusNotice notice={noticeFrom({ error, ok })} />
    {leads.length === 0 ? <div className="empty-state"><h2>No inquiries yet</h2><p>Submit the inquiry form to create the first lead.</p><Link href="/inquiry">Open inquiry form</Link></div> : <div className="table-wrap"><table><thead><tr><th>Customer</th><th>Service</th><th>Preferred date</th><th>Priority</th><th>Stage</th></tr></thead><tbody>{leads.map((lead) => <tr key={lead.id}><td><Link className="table-person" href={`/crm/leads/${lead.id}`}><strong>{lead.name}</strong><span>{lead.email}</span>{lead.is_demo && <DemoBadge isDemo />}</Link></td><td>{lead.service_type}</td><td>{formatDate(lead.preferred_date)}</td><td><PriorityChip priority={lead.priority} /></td><td><span className="stage">{lead.pipeline_stage}</span></td></tr>)}</tbody></table></div>}
  </main>;
}
