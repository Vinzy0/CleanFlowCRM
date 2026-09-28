"use client";

import { useFormStatus } from "react-dom";

export default function SubmitButton({ label, ariaLabel }: { label: string; ariaLabel?: string }) {
  const { pending } = useFormStatus();
  return <button className="button" type="submit" disabled={pending} aria-label={ariaLabel}>{pending ? "Working…" : label}</button>;
}
