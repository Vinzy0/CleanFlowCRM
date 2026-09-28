import Link from "next/link";
import { getCrmSnapshot } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { noticeFrom } from "@/lib/notices";
import { DemoBadge, PriorityChip, StatusNotice } from "../badges";
import DemoControls from "../demo-controls";
import StatusForm from "../status-form";

export default async function PipelinePage({ searchParams }: {
  searchParams: Promise<{ error?: string; ok?: string }>;
}) {
  const { error, ok } = await searchParams;
  const snapshot = await getCrmSnapshot();
  if (!snapshot) {
    return <main><h1>Pipeline</h1><p role="alert" className="error">Couldn’t load the pipeline. Refresh the page to try again.</p></main>;
  }
  const { leads, config } = snapshot;
  return <main>
    <div className="crm-topline"><div><h1>Pipeline</h1><p>Move requests forward as your team follows up.</p></div><div className="topline-actions"><DemoControls demoMode={config.demo_mode} emailDelivery={config.email_delivery} compact /><Link className="button button-secondary" href="/inquiry">New inquiry</Link></div></div>
    <StatusNotice notice={noticeFrom({ error, ok })} />
    <div className="pipeline-board">{config.pipeline_stages.map((stage) => {
      const stageLeads = leads.filter((lead) => lead.pipeline_stage === stage);
      return <section className="pipeline-column" key={stage} aria-label={`${stage} leads`}>
        <div className="column-heading"><h2>{stage}</h2><span>{stageLeads.length}</span></div>
        <div className="column-content">{stageLeads.length === 0 ? <p className="column-empty">No leads in {stage}. Every request starts in New; move it here when it fits.</p> : stageLeads.map((lead) => <article className="lead-card" key={lead.id}>
          <Link href={`/crm/leads/${lead.id}`} className="lead-card-link"><strong>{lead.name}</strong><span>{lead.service_type}</span></Link>
          <div className="card-chips"><PriorityChip priority={lead.priority} /><DemoBadge isDemo={lead.is_demo} /></div>
          <div className="card-facts"><span>Preferred<b>{formatDate(lead.preferred_date)}</b></span><span>Property<b>{lead.property_type}</b></span></div>
          <StatusForm leadId={lead.id} customerName={lead.name} currentStage={lead.pipeline_stage} stages={config.pipeline_stages} returnTo="pipeline" />
        </article>)}</div>
      </section>;
    })}</div>
  </main>;
}
