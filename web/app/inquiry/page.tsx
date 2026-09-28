import { randomUUID } from "node:crypto";
import { api, PublicConfig } from "@/lib/api";
import InquiryForm from "./inquiry-form";

export default async function InquiryPage() {
  const response = await api("/api/config").catch(() => null);
  if (!response?.ok) {
    return <main className="form-page"><div className="form-intro"><h1>Inquiry form unavailable</h1><p role="alert">We can’t load the service choices right now. Please try again shortly.</p></div></main>;
  }
  const config: PublicConfig = await response.json();
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
