import Link from "next/link";
import { redirect } from "next/navigation";
import { api, authenticatedApi, PublicConfig } from "@/lib/api";
import { signOut } from "@/app/actions";

export default async function CrmLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const response = await authenticatedApi("/api/auth/me").catch(() => null);
  if (!response?.ok) redirect("/login");
  const user: { name: string; email: string } = await response.json();
  const configResponse = await api("/api/config");
  const config: PublicConfig = await configResponse.json();
  return <div className="crm-shell"><aside className="crm-sidebar"><div className="workspace-title">{config.business_name}<br /><strong>Workspace</strong></div><nav aria-label="CRM navigation"><Link className="nav-active" href="/crm">Leads</Link><Link href="/inquiry">Inquiry form</Link></nav><div className="sidebar-footer"><span>{user.name}</span><form action={signOut}><button type="submit">Sign out</button></form></div></aside><div className="crm-main">{children}</div></div>;
}
