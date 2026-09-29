import { randomUUID } from "node:crypto";
import Link from "next/link";
import { api, PublicConfig } from "@/lib/api";
import InquiryForm from "./inquiry-form";

export default async function InquiryPage() {
  const response = await api("/api/config").catch(() => null);
  if (!response?.ok) {
    return <main className="form-page"><div className="form-intro"><h1>Inquiry form unavailable</h1><p role="alert">We can’t load the service choices right now. Please try again shortly.</p></div></main>;
  }
  const config: PublicConfig = await response.json();
  if (config.demo_mode) {
    return <main className="form-page"><div className="form-intro"><h1>Try a sample inquiry</h1><p>This public demo uses fictional customers. Enter the demo workspace to simulate an inquiry and follow it through the CRM.</p><Link className="button" href="/login">Enter demo workspace</Link></div></main>;
  }
  return (
    <main className="form-page">
      <div className="form-intro">
        <h1>Tell us what needs cleaning.</h1>
        <p>Share a few details and {config.business_name} will have everything needed to review your request.</p>
      </div>
      <InquiryForm config={config} inquiryKey={randomUUID()} />
    </main>
  );
}
