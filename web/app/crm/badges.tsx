import type { Notice } from "@/lib/notices";

export function StatusNotice({ notice }: { notice: Notice }) {
  if (!notice) return null;
  return (
    <p role={notice.tone === "error" ? "alert" : "status"} className={notice.tone === "error" ? "error" : "notice"}>
      {notice.text}
    </p>
  );
}

export function PriorityChip({ priority }: { priority: string | null }) {
  const label = priority ?? "not assessed";
  const tone = priority === "high" ? "priority high" : priority === "normal" ? "priority normal" : "priority none";
  return <span className={tone}>Priority: {label}</span>;
}

const AI_LABELS: Record<string, string> = {
  completed: "AI analysis complete",
  failed: "AI analysis failed",
  pending: "AI analysis pending",
};

export function AiStatusChip({ status }: { status: string | null }) {
  if (!status) return <span className="chip neutral">AI not run</span>;
  return <span className={`chip ai-${status}`}>{AI_LABELS[status] ?? status}</span>;
}

const EMAIL_LABELS: Record<string, string> = {
  sent: "Sent",
  failed: "Failed",
  pending: "Sending",
};

export function EmailStatusChip({ status }: { status: string | null }) {
  const tone = status === "sent" ? "email-sent" : status === "failed" ? "email-failed" : status === "pending" ? "email-pending" : "neutral";
  return <span className={`chip ${tone}`}>{status ? (EMAIL_LABELS[status] ?? status) : "Not sent"}</span>;
}

export function DemoBadge({ isDemo }: { isDemo: boolean }) {
  return isDemo ? <span className="chip demo">Fake demo data</span> : null;
}
