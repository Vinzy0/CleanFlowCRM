"use client";

import { useFormStatus } from "react-dom";

export default function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return <button className="button" type="submit" disabled={pending}>{pending ? "Working…" : label}</button>;
}
