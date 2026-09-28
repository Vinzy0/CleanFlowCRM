import Link from "next/link";
import { getCrmSnapshot } from "@/lib/api";
import { formatDate } from "@/lib/format";
import StatusForm from "../status-form";

export default async function PipelinePage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const snapshot = await getCrmSnapshot();
  const { error } = await searchParams;
  if (!snapshot) return <main><h1>Pipeline</h1><p role="alert" className="error">Couldn’t load the pipeline. Refresh the page to try again.</p></main>;
  const { leads, config } = snapshot;
  return <main><div className="crm-topline"><div><h1>Pipeline</h1><p>Move requests forward as your team follows up.</p></div><Link className="button" href="/inquiry">New inquiry</Link></div>
    {error && <p role="alert" className="error">Status wasn’t updated. Please try again.</p>}
    <div className="pipeline-board">{config.pipeline_stages.map((stage) => {
      const stageLeads = leads.filter((lead) => lead.pipeline_stage === stage);
      return <section className="pipeline-column" key={stage} aria-label={`${stage} leads`}><div className="column-heading"><h2>{stage}</h2><span>{stageLeads.length}</span></div><div className="column-content">{stageLeads.length === 0 ? <p className="column-empty">No leads in this stage.</p> : stageLeads.map((lead) => <article className="lead-card" key={lead.id}><Link href={`/crm/leads/${lead.id}`} className="lead-card-link"><strong>{lead.name}</strong><span>{lead.service_type}</span></Link><div className="card-facts"><span>Priority <b>{lead.priority ?? "Not assessed"}</b></span><span>Preferred <b>{formatDate(lead.preferred_date)}</b></span></div><StatusForm leadId={lead.id} customerName={lead.name} currentStage={lead.pipeline_stage} stages={config.pipeline_stages} returnTo="pipeline" /></article>)}</div></section>;
    })}</div>
  </main>;
}
