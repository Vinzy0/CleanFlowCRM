export type Notice = { tone: "ok" | "error"; text: string } | null;

const OK: Record<string, string> = {
  status: "Status updated.",
  analysis: "AI analysis completed.",
  draft: "Draft reply generated. Review and edit it before sending.",
  notification: "Owner notification sent.",
  reset: "Demo data reset to its known state.",
  simulated: "Simulated inquiry created from fake demo data.",
};

const ERRORS: Record<string, string> = {
  status: "Status wasn’t updated. Please try again.",
  analysis: "AI analysis is unavailable. The lead is saved; you can retry.",
  draft: "Draft reply is unavailable. Please try again.",
  notification: "The owner notification didn’t send. Check the email setup and retry.",
  rate: "You’ve reached the demo limit for that action. Please wait a moment and try again.",
  demo: "That demo action didn’t complete. Please try again.",
  demo_disabled: "Demo mode isn’t enabled on this server.",
  service: "We couldn’t reach the service. Please refresh and try again.",
};

export function noticeFrom(params: {
  ok?: string;
  error?: string;
  seeded?: string;
  simulated?: string;
}): Notice {
  if (params.error) {
    return { tone: "error", text: ERRORS[params.error] ?? "Something went wrong. Please try again." };
  }
  if (!params.ok) return null;
  if (params.ok === "reset") {
    return {
      tone: "ok",
      text: params.seeded ? `Demo data reset. Seeded ${params.seeded} fake leads.` : OK.reset,
    };
  }
  return { tone: "ok", text: OK[params.ok] ?? "Done." };
}
