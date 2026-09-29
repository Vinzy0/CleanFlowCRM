import { redirect } from "next/navigation";
import { api, authenticatedApi, PublicConfig } from "@/lib/api";
import { signOut } from "@/app/actions";
import CrmNavigation from "./navigation";
import "./crm.css";

export default async function CrmLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const response = await authenticatedApi("/api/auth/me").catch(() => null);
  if (response?.status === 401) redirect("/login");
  if (!response?.ok) return <main className="service-error"><h1>CRM temporarily unavailable</h1><p>We couldn’t connect to the lead service. Please refresh to try again.</p></main>;
  const user: { name: string; email: string } = await response.json();
  const configResponse = await api("/api/config").catch(() => null);
  const config: PublicConfig | null = configResponse?.ok ? await configResponse.json() : null;
  return <div className="crm-shell"><aside className="crm-sidebar"><div className="workspace-title"><span>{config?.business_name ?? "Service business"}</span><strong>Tavo {config?.demo_mode && <small className="demo-indicator">Demo</small>}</strong></div><CrmNavigation /><div className="sidebar-footer"><span>{user.name}</span><form action={signOut}><button type="submit">Sign out</button></form></div></aside><div className="crm-main">{children}</div></div>;
}
