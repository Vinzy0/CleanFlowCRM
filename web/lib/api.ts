import { cookies } from "next/headers";

export type Lead = {
  id: number;
  name: string;
  email: string;
  phone: string;
  service_type: string;
  property_type: string;
  preferred_date: string;
  message: string;
  pipeline_stage: string;
  priority: string | null;
  created_at: string;
  updated_at: string;
};

export type Activity = {
  id: number;
  type: string;
  status: string;
  content: { from?: string; to?: string; [key: string]: unknown };
  created_at: string;
};

export type AIAnalysis = {
  service_category: string;
  priority: string;
  summary: string;
  matched_priority_rules: string[];
  classification_rationale: string;
  model: string;
  created_at: string;
};

export type LeadDetail = Lead & { activities: Activity[]; analysis: AIAnalysis | null };

export type PublicConfig = {
  business_name: string;
  services: string[];
  property_types: string[];
  pipeline_stages: string[];
};

const baseUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function api(path: string, init?: RequestInit) {
  return fetch(`${baseUrl}${path}`, { ...init, cache: "no-store" });
}

export async function authenticatedApi(path: string, init?: RequestInit) {
  const token = (await cookies()).get("cleanflow_session")?.value;
  return api(path, {
    ...init,
    headers: { ...init?.headers, Authorization: `Bearer ${token ?? ""}` },
  });
}

export async function getCrmSnapshot(): Promise<{ leads: Lead[]; config: PublicConfig } | null> {
  const [leadsResponse, configResponse] = await Promise.all([
    authenticatedApi("/api/leads").catch(() => null),
    api("/api/config").catch(() => null),
  ]);
  if (!leadsResponse?.ok || !configResponse?.ok) return null;
  return { leads: await leadsResponse.json(), config: await configResponse.json() };
}
