"use server";
import { revalidatePath } from "next/cache";
import { authenticatedApi } from "@/lib/api";

export type IntegrationState = { error: string; notice: string; secret: string };
async function mutate(path: string, method: string, payload?: unknown): Promise<IntegrationState> {
  const response = await authenticatedApi(path, {
    method, headers: { "Content-Type": "application/json" },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  }).catch(() => null);
  const body = await response?.json().catch(() => null);
  if (!response?.ok) return {
    error: typeof body?.detail === "string" ? body.detail : response?.status === 422
      ? "Check the name, HTTPS destination, and selections, then try again."
      : "The integration service is unavailable. Refresh and try again.", notice: "", secret: "",
  };
  revalidatePath("/crm/integrations");
  return { error: "", notice: method === "DELETE" ? "Integration removed." : body?.status === "queued"
    ? "Retry queued. The worker or Process queued deliveries will send it."
    : typeof body?.processed === "number" ? `Processed ${body.processed} deliveries. Check the results below.` : "Saved.",
    secret: body?.key ?? body?.signing_secret ?? "" };
}
export async function createKey(_: IntegrationState, form: FormData) {
  return mutate("/api/integrations/keys", "POST", { name: form.get("name"), scopes: form.getAll("scopes") });
}
export async function createWebhook(_: IntegrationState, form: FormData) {
  return mutate("/api/integrations/webhooks", "POST", { name: form.get("name"), url: form.get("url"), events: form.getAll("events") });
}
export async function editSubscriptions(id: number, _: IntegrationState, form: FormData) {
  return mutate(`/api/integrations/webhooks/${id}`, "PATCH", { events: form.getAll("events") });
}
export async function revokeKey(id: number, _: IntegrationState, _form: FormData) {
  return mutate(`/api/integrations/keys/${id}`, "DELETE");
}
export async function removeWebhook(id: number, _: IntegrationState, _form: FormData) {
  return mutate(`/api/integrations/webhooks/${id}`, "DELETE");
}
export async function retryDelivery(id: number, _: IntegrationState, _form: FormData) {
  return mutate(`/api/integrations/deliveries/${id}/retry`, "POST");
}
export async function dispatchDeliveries(_: IntegrationState, _form: FormData) {
  return mutate("/api/integrations/dispatch", "POST");
}
