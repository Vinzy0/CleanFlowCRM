"use server";

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { api, authenticatedApi } from "@/lib/api";

export type FieldErrors = Record<string, string>;
export type InquiryState = {
  error: string;
  fields: FieldErrors;
  values: Record<string, string>;
  attempt: number;
};
export type EmailState = { error: string; notice: string; duplicate: boolean };

const INQUIRY_FIELDS = ["name", "email", "phone", "service_type", "property_type", "preferred_date", "message"];

const FRIENDLY_MESSAGES: Record<string, string> = {
  name: "Enter the customer’s name (at least 2 characters).",
  email: "Enter a valid email address.",
  phone: "Enter a phone number with at least 7 digits.",
  service_type: "Choose one of the listed services.",
  property_type: "Choose one of the listed property types.",
  preferred_date: "Choose a valid preferred date.",
  message: "Describe the request in at least 10 characters.",
  subject: "Add a short subject line (at least 3 characters).",
  body: "Write at least 10 characters before sending.",
};

async function bodyOf(response: Response | null) {
  if (!response) return null;
  return response.json().catch(() => null);
}

/** Turn a FastAPI 422 payload into per-field messages. */
function fieldErrors(detail: unknown): FieldErrors {
  if (!Array.isArray(detail)) return {};
  const errors: FieldErrors = {};
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const { loc, msg } = item as { loc?: unknown; msg?: unknown };
    if (!Array.isArray(loc)) continue;
    const field = loc[loc.length - 1];
    if (typeof field !== "string" || !INQUIRY_FIELDS.includes(field)) continue;
    errors[field] = FRIENDLY_MESSAGES[field] ?? (typeof msg === "string" ? msg : "Check this field.");
  }
  return errors;
}

function rateLimitMessage(response: Response, payload: { detail?: unknown } | null): string {
  if (typeof payload?.detail === "string") return payload.detail;
  return `Too many requests from this address. Please try again in about ${
    response.headers.get("retry-after") ?? "a few"
  } seconds.`;
}

export async function submitInquiry(previous: InquiryState, form: FormData): Promise<InquiryState> {
  const payload = Object.fromEntries(INQUIRY_FIELDS.map((field) => [field, String(form.get(field) ?? "").trim()]));
  const inquiryKey = String(form.get("inquiry_key") ?? "");
  const response = await api("/api/leads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, inquiry_key: inquiryKey || randomUUID() }),
  }).catch(() => null);
  const body = await bodyOf(response);
  if (!response?.ok) {
    return {
      error:
        response?.status === 422
          ? "Check the highlighted details and try again."
          : response?.status === 429
            ? rateLimitMessage(response, body)
            : "We couldn’t save your request. Your details are still here — please try again.",
      fields: response?.status === 422 ? fieldErrors(body?.detail) : {},
      values: payload,
      attempt: (previous.attempt ?? 0) + 1,
    };
  }
  redirect("/inquiry/success");
}

export async function signIn(form: FormData) {
  const response = await api("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
  }).catch(() => null);
  if (!response?.ok) {
    redirect(
      response?.status === 401 ? "/login?error=credentials" : response?.status === 429 ? "/login?error=rate" : "/login?error=unavailable",
    );
  }
  const { access_token } = await response.json();
  await setSession(access_token);
  redirect("/crm");
}

/** One-click entry for the public demo workspace (demo credentials only). */
export async function signInAsDemo() {
  const email = (process.env.DEMO_LOGIN_EMAIL ?? "").trim();
  const password = (process.env.DEMO_LOGIN_PASSWORD ?? "").trim();
  if (!email || !password) redirect("/login?error=demo");
  const response = await api("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }).catch(() => null);
  if (!response?.ok) {
    redirect(response?.status === 429 ? "/login?error=rate" : "/login?error=demo");
  }
  const { access_token } = await response.json();
  const [userResponse, configResponse] = await Promise.all([
    api("/api/auth/me", { headers: { Authorization: `Bearer ${access_token}` } }).catch(() => null),
    api("/api/config").catch(() => null),
  ]);
  if (!userResponse?.ok || !(await userResponse.json()).is_demo || !configResponse?.ok || !(await configResponse.json()).demo_mode) {
    redirect("/login?error=demo");
  }
  await setSession(access_token);
  redirect("/crm");
}

async function setSession(token: string) {
  (await cookies()).set("cleanflow_session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
}

export async function signOut() {
  (await cookies()).delete("cleanflow_session");
  redirect("/login");
}

export async function changeStatus(leadId: number, returnTo: "pipeline" | "detail", form: FormData) {
  const destination = returnTo === "pipeline" ? "/crm/pipeline" : `/crm/leads/${leadId}`;
  const response = await authenticatedApi(`/api/leads/${leadId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage: String(form.get("stage") ?? "") }),
  }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  if (response?.status === 429) redirect(`${destination}?error=rate`);
  if (!response?.ok) redirect(`${destination}?error=status`);
  refreshCrm(leadId);
  redirect(`${destination}?ok=status`);
}

export async function retryClassification(leadId: number) {
  const destination = `/crm/leads/${leadId}`;
  const response = await authenticatedApi(`/api/leads/${leadId}/classify`, { method: "POST" }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  refreshCrm(leadId);
  if (response?.status === 429) redirect(`${destination}?error=rate`);
  redirect(response?.ok ? `${destination}?ok=analysis` : `${destination}?error=analysis`);
}

export async function generateDraftReply(leadId: number) {
  const destination = `/crm/leads/${leadId}`;
  const response = await authenticatedApi(`/api/leads/${leadId}/draft-reply`, { method: "POST" }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  refreshCrm(leadId);
  if (response?.status === 429) redirect(`${destination}?error=rate`);
  redirect(response?.ok ? `${destination}?ok=draft` : `${destination}?error=draft`);
}

/** Send the owner-approved reply. Never called by draft generation. */
export async function sendLeadEmail(leadId: number, previous: EmailState, form: FormData): Promise<EmailState> {
  const values = {
    subject: String(form.get("subject") ?? "").trim(),
    body: String(form.get("body") ?? "").trim(),
  };
  const response = await authenticatedApi(`/api/leads/${leadId}/send-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }).catch(() => null);
  const body = await bodyOf(response);
  if (!response) {
    return { error: "We couldn’t reach the email service. Your text is still here — try again.", notice: "", duplicate: false };
  }
  if (response.status === 401) redirect("/login");
  if (response.ok) {
    refreshCrm(leadId);
    const duplicate = Boolean(body?.duplicate);
    const redirected = Boolean(body?.redirected);
    const sandboxed = Boolean(body?.sandboxed);
    const notice = duplicate
      ? "This exact reply was already sent, so nothing was sent again."
      : redirected
        ? sandboxed
          ? `Captured in the sandbox outbox for the controlled demo inbox (${body?.delivered_to}).`
          : `Sent to the controlled demo inbox (${body?.delivered_to}) instead of the customer address ${body?.to}.`
        : sandboxed
          ? `Captured in the sandbox outbox for ${body?.to}; no email was delivered.`
          : `Email sent to ${body?.to}.`;
    return { error: "", notice, duplicate };
  }
  if (response.status === 422) {
    return { error: Object.values(fieldErrors(body?.detail))[0] ?? "Check the subject and message.", notice: "", duplicate: false };
  }
  if (response.status === 429) {
    return { error: rateLimitMessage(response, body), notice: "", duplicate: false };
  }
  const detail = typeof body?.detail === "string" ? body.detail : "The email could not be sent.";
  return { error: detail, notice: "", duplicate: false };
}

export async function retryOwnerNotification(leadId: number) {
  const destination = `/crm/leads/${leadId}`;
  const response = await authenticatedApi(`/api/leads/${leadId}/notify-owner`, { method: "POST" }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  refreshCrm(leadId);
  if (response?.status === 429) redirect(`${destination}?error=rate`);
  redirect(response?.ok ? `${destination}?ok=notification` : `${destination}?error=notification`);
}

export async function simulateInquiry() {
  const response = await authenticatedApi("/api/demo/simulate-inquiry", { method: "POST" }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  if (!response) redirect("/crm?error=service");
  if (response.status === 429) redirect("/crm?error=rate");
  if (response.status === 404) redirect("/crm?error=demo_disabled");
  if (!response.ok) redirect("/crm?error=demo");
  const { lead_id } = await response.json();
  refreshCrm(Number(lead_id));
  redirect(`/crm/leads/${lead_id}?ok=simulated`);
}

export async function resetDemoData() {
  const response = await authenticatedApi("/api/demo/reset", { method: "POST" }).catch(() => null);
  if (response?.status === 401) redirect("/login");
  if (!response) redirect("/crm?error=service");
  if (response.status === 429) redirect("/crm?error=rate");
  if (response.status === 404) redirect("/crm?error=demo_disabled");
  if (!response.ok) redirect("/crm?error=demo");
  const { seeded } = await response.json();
  refreshCrm();
  redirect(`/crm?ok=reset&seeded=${seeded}`);
}

function refreshCrm(leadId?: number) {
  revalidatePath("/crm");
  revalidatePath("/crm/pipeline");
  revalidatePath("/crm/leads");
  if (leadId) revalidatePath(`/crm/leads/${leadId}`);
}
