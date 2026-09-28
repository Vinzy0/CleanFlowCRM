"use server";

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";

export type InquiryState = { error: string; values: Record<string, string>; attempt: number };

export async function submitInquiry(previous: InquiryState, form: FormData): Promise<InquiryState> {
  const fields = ["name", "email", "phone", "service_type", "property_type", "preferred_date", "message"];
  const payload = Object.fromEntries(fields.map((field) => [field, String(form.get(field) ?? "").trim()]));
  const inquiryKey = String(form.get("inquiry_key") ?? "");
  const response = await api("/api/leads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, inquiry_key: inquiryKey || randomUUID() }),
  }).catch(() => null);
  if (!response?.ok) {
    return {
      error: response?.status === 422 ? "Check the form details and try again." : "We couldn’t save your request. Please try again.",
      values: payload,
      attempt: previous.attempt + 1,
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
  if (!response?.ok) redirect(response?.status === 401 ? "/login?error=credentials" : "/login?error=unavailable");
  const { access_token } = await response.json();
  (await cookies()).set("cleanflow_session", access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  redirect("/crm");
}

export async function signOut() {
  (await cookies()).delete("cleanflow_session");
  redirect("/login");
}
