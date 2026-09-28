import Link from "next/link";

export default function LeadNotFound() {
  return <main className="empty-state"><h1>Lead not found</h1><p>This lead may have been removed.</p><Link href="/crm/leads">Back to leads</Link></main>;
}
