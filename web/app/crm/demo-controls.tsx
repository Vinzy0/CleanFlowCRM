"use client";

import { useFormStatus } from "react-dom";
import { resetDemoData, simulateInquiry } from "@/app/actions";
import type { EmailDelivery } from "@/lib/api";

function DemoButton({ label, pendingLabel, secondary }: { label: string; pendingLabel: string; secondary?: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button className={`button${secondary ? " button-secondary" : ""}`} type="submit" disabled={pending}>
      {pending ? pendingLabel : label}
    </button>
  );
}

function emailSafetyCopy(delivery: EmailDelivery) {
  if (delivery === "redirected") return "Email is redirected to the controlled demo inbox — no customer or owner address can be reached from here.";
  if (delivery === "disabled") return "Email delivery is switched off in this demo, so nothing can be sent to a real address.";
  if (delivery === "sandbox") return "Email is captured by the local sandbox outbox instead of being delivered.";
  return "Email delivery is live on this environment.";
}

export default function DemoControls({
  demoMode,
  emailDelivery,
  compact,
}: {
  demoMode: boolean;
  emailDelivery: EmailDelivery;
  compact?: boolean;
}) {
  if (!demoMode) return null;
  if (compact) {
    return (
      <form action={simulateInquiry}>
        <DemoButton label="Simulate new inquiry" pendingLabel="Creating lead…" />
      </form>
    );
  }
  return (
    <section className="demo-panel" aria-label="Public demo controls">
      <div className="demo-copy">
        <h2>Public demo</h2>
        <p>
          Simulate a customer inquiry to watch the full workflow: lead created, AI classification and summary, owner
          notification, then a reply you approve yourself.
        </p>
        <p className="muted-copy">All demo customers are fake. Resetting restores a known, populated demo state.</p>
        <p className="muted-copy">{emailSafetyCopy(emailDelivery)}</p>
      </div>
      <div className="demo-actions">
        <form action={simulateInquiry}>
          <DemoButton label="Simulate new inquiry" pendingLabel="Creating lead…" />
        </form>
        <form action={resetDemoData}>
          <DemoButton label="Reset demo data" pendingLabel="Resetting…" secondary />
        </form>
      </div>
    </section>
  );
}
