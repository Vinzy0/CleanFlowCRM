"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/crm", label: "Dashboard" },
  { href: "/crm/pipeline", label: "Pipeline" },
  { href: "/crm/leads", label: "Leads" },
];

export default function CrmNavigation() {
  const path = usePathname();
  return <nav aria-label="CRM navigation">{items.map((item) => <Link key={item.href} href={item.href} aria-current={path === item.href || (item.href === "/crm/leads" && path.startsWith("/crm/leads/")) ? "page" : undefined}>{item.label}</Link>)}</nav>;
}
