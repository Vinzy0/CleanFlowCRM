import Link from "next/link";
import { getCrmSnapshot } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { noticeFrom } from "@/lib/notices";
import { DemoBadge, PriorityChip, StatusNotice } from "./badges";
import DemoControls from "./demo-controls";

export default async function DashboardPage({ searchParams }: {
  searchParams: Promise<{ error?: string; ok?: string; seeded?: string }>;
}) {
  const { error, ok, seeded } = await searchParams;
  const snapshot = await getCrmSnapshot();
  if (!snapshot) {
    return <main><h1>Dashboard</h1><p role="alert" className="error">Couldn’t load the dashboard. Refresh the page to try again.</p></main>;
  }
  const { leads, config } = snapshot;
  const counts = config.pipeline_stages.map((stage) => ({ stage, count: leads.filter((lead) => lead.pipeline_stage === stage).length }));
  return <main>
    <div className="crm-topline"><div><h1>Dashboard</h1><p>See what needs attention across your cleaning inquiries.</p></div><Link className="button" href="/crm/pipeline">View pipeline</Link></div>
    <StatusNotice notice={noticeFrom({ error, ok, seeded })} />

    <section aria-label="Lead counts" className="metric-grid">{counts.map(({ stage, count }) => <Link href="/crm/pipeline" key={stage} className="metric-card"><span>{stage} leads</span><strong>{count}</strong><small>{count === 0 ? "Nothing here yet" : count === 1 ? "1 request to review" : `${count} requests to review`}</small></Link>)}</section>

    <DemoControls demoMode={config.demo_mode} emailDelivery={config.email_delivery} />

    <section className="recent-section"><div className="section-heading"><div><h2>Recent leads</h2><p>The latest requests from your inquiry form.</p></div><Link href="/crm/leads">View all leads</Link></div>
      {leads.length === 0 ? <div className="empty-state"><h3>No inquiries yet</h3><p>New customer requests will appear here. Submit the public inquiry form{config.demo_mode ? " or simulate one from the demo panel above" : ""} to see the workflow.</p><Link href="/inquiry">Open inquiry form</Link></div> : <div className="recent-list">{leads.slice(0, 5).map((lead) => <Link href={`/crm/leads/${lead.id}`} className="recent-row" key={lead.id}><span className="avatar">{lead.name.slice(0, 1).toUpperCase()}</span><span className="recent-person"><strong>{lead.name}</strong><small>{lead.service_type} · preferred {formatDate(lead.preferred_date)}</small></span><span className="recent-facts"><PriorityChip priority={lead.priority} /><DemoBadge isDemo={lead.is_demo} /></span><span className="recent-date">{formatDate(lead.created_at.slice(0, 10))}</span><span className="stage">{lead.pipeline_stage}</span></Link>)}</div>}
    </section>
  </main>;
}
