"use server";
import { revalidatePath } from "next/cache";
import { authenticatedApi } from "@/lib/api";

export type WorkflowState = { error: string; notice: string };
export async function saveWorkflow(id: number, _: WorkflowState, form: FormData): Promise<WorkflowState> {
  const nullable = (name: string) => String(form.get(name) ?? "").trim() || null;
  const response = await authenticatedApi(`/api/leads/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      source: nullable("source"), tags: String(form.get("tags") ?? "").split(",").map((tag) => tag.trim()).filter(Boolean),
      next_action: nullable("next_action"), next_follow_up: nullable("next_follow_up"), appointment_at: nullable("appointment_at"),
    }),
  }).catch(() => null);
  if (!response?.ok) return { error: response?.status === 403 ? "Demo leads cannot be edited."
    : response?.status === 422 ? "Check the fields. Use at most 20 tags, each up to 40 characters."
    : "Couldn’t save these details. Try again.", notice: "" };
  revalidatePath(`/crm/leads/${id}`);
  revalidatePath("/crm");
  revalidatePath("/crm/integrations");
  return { error: "", notice: "Workflow details saved." };
}
