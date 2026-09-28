import Link from "next/link";
import { getCrmSnapshot } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default async function DashboardPage() {
  const snapshot = await getCrmSnapshot();
  if (!snapshot) return <main><h1>Dashboard</h1><p role="alert" className="error">Couldn’t load the dashboard. Refresh the page to try again.</p></main>;
  const { leads, config } = snapshot;
  return <main>
    <div className="crm-topline"><div><h1>Dashboard</h1><p>See what needs attention across your cleaning inquiries.</p></div><Link className="button" href="/crm/pipeline">View pipeline</Link></div>
    <section aria-label="Lead counts" className="metric-grid">{config.pipeline_stages.map((stage) => <Link href="/crm/pipeline" key={stage} className="metric-card"><span>{stage} leads</span><strong>{leads.filter((lead) => lead.pipeline_stage === stage).length}</strong></Link>)}</section>
    <section className="recent-section"><div className="section-heading"><div><h2>Recent leads</h2><p>The latest requests from your inquiry form.</p></div><Link href="/crm/leads">View all leads</Link></div>
      {leads.length === 0 ? <div className="empty-state"><h3>No inquiries yet</h3><p>New customer requests will appear here.</p><Link href="/inquiry">Open inquiry form</Link></div> : <div className="recent-list">{leads.slice(0, 5).map((lead) => <Link href={`/crm/leads/${lead.id}`} className="recent-row" key={lead.id}><span className="avatar">{lead.name.slice(0, 1).toUpperCase()}</span><span className="recent-person"><strong>{lead.name}</strong><small>{lead.service_type}</small></span><span className="recent-date">{formatDate(lead.created_at.slice(0, 10))}</span><span className="stage">{lead.pipeline_stage}</span></Link>)}</div>}
    </section>
  </main>;
}
