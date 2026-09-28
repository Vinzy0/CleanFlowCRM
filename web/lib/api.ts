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
  is_demo: boolean;
  created_at: string;
  updated_at: string;
};

export type ActivityContent = {
  from?: string;
  to?: string;
  email_type?: "owner_notification" | "customer_reply" | string;
  subject?: string;
  delivered_to?: string;
  redirected?: boolean;
  reason?: string;
  message?: string;
  draft?: string;
  attempts?: number;
  priority?: string;
  category?: string;
  reused?: boolean;
  [key: string]: unknown;
};

export type Activity = {
  id: number;
  type: string;
  status: string;
  content: ActivityContent;
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

export type EmailDelivery = "live" | "sandbox" | "redirected" | "disabled";

export type PublicConfig = {
  business_name: string;
  services: string[];
  property_types: string[];
  pipeline_stages: string[];
  demo_mode: boolean;
  email_delivery: EmailDelivery;
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

export async function getPublicConfig(): Promise<PublicConfig | null> {
  const response = await api("/api/config").catch(() => null);
  return response?.ok ? response.json() : null;
}

/** Latest tracked email of one kind (owner notification or customer reply). */
export function latestEmail(activities: Activity[], emailType: string): Activity | null {
  const matches = activities.filter(
    (activity) =>
      (activity.type === "email_sent" || activity.type === "email_failed") &&
      activity.content.email_type === emailType,
  );
  return matches.length > 0 ? matches[matches.length - 1] : null;
}

export function latestDraft(activities: Activity[]): string | null {
  const matches = activities.filter(
    (activity) => activity.type === "reply_generated" && activity.status === "completed",
  );
  const draft = matches.length > 0 ? matches[matches.length - 1].content.draft : null;
  return typeof draft === "string" ? draft : null;
}

export function latestClassification(activities: Activity[]): Activity | null {
  const matches = activities.filter((activity) => activity.type === "ai_classified");
  return matches.length > 0 ? matches[matches.length - 1] : null;
}
