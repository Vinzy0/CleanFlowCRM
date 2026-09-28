import Link from "next/link";
import { authenticatedApi, Lead } from "@/lib/api";

export default async function LeadsPage() {
  const response = await authenticatedApi("/api/leads").catch(() => null);
  const leads: Lead[] = response?.ok ? await response.json() : [];
  return <main><div className="crm-topline"><div><h1>Leads</h1><p>Customer requests saved from the inquiry form.</p></div><Link className="button" href="/inquiry">New inquiry</Link></div>{!response?.ok ? <p role="alert" className="error">Couldn’t load leads. Check the API connection and refresh.</p> : leads.length === 0 ? <div className="empty-state"><h2>No inquiries yet</h2><p>Submit the inquiry form to create the first lead.</p><Link href="/inquiry">Open inquiry form</Link></div> : <div className="table-wrap"><table><thead><tr><th>Customer</th><th>Service</th><th>Preferred date</th><th>Stage</th><th>Received</th></tr></thead><tbody>{leads.map((lead) => <tr key={lead.id}><td><strong>{lead.name}</strong><span>{lead.email}</span></td><td>{lead.service_type}</td><td>{lead.preferred_date}</td><td><span className="stage">{lead.pipeline_stage}</span></td><td>{new Date(lead.created_at).toLocaleDateString()}</td></tr>)}</tbody></table></div>}</main>;
}
