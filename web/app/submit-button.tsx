"use client";

import { useFormStatus } from "react-dom";

export default function SubmitButton({
  label,
  pendingLabel,
  ariaLabel,
  secondary,
}: {
  label: string;
  pendingLabel?: string;
  ariaLabel?: string;
  secondary?: boolean;
}) {
  const { pending } = useFormStatus();
  return (
    <button
      className={`button${secondary ? " button-secondary" : ""}`}
      type="submit"
      disabled={pending}
      aria-label={ariaLabel}
    >
      {pending ? (pendingLabel ?? "Working…") : label}
    </button>
  );
}
