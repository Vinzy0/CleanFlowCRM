"use client";

export default function CrmError({ reset }: { error: Error; reset: () => void }) {
  return <main className="service-error"><h1>Something went wrong</h1><p>We couldn’t load this CRM page.</p><button className="button" type="button" onClick={reset}>Try again</button></main>;
}
