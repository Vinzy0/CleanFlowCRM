"use client";

import { useActionState } from "react";
import { submitInquiry } from "@/app/actions";
import SubmitButton from "@/app/submit-button";
import type { PublicConfig } from "@/lib/api";

export default function InquiryForm({ config, inquiryKey }: { config: PublicConfig; inquiryKey: string }) {
  const [state, action, pending] = useActionState(submitInquiry, { error: "", fields: {}, values: {}, attempt: 0 });
  const values = state.values ?? {};
  const errors = state.fields ?? {};
  const field = (name: string) =>
    errors[name] ? <span className="field-error" role="alert">{errors[name]}</span> : null;
  return (
    <form key={state.attempt ?? 0} action={action} className="form-card" aria-busy={pending}>
      <input type="hidden" name="inquiry_key" value={inquiryKey} />
      {state.error && <p role="alert" className="error">{state.error}</p>}
      <div className="form-grid">
        <label>Customer name<input name="name" autoComplete="name" minLength={2} maxLength={120} defaultValue={values.name} aria-invalid={Boolean(errors.name)} required />{field("name")}</label>
        <label>Email<input name="email" type="email" autoComplete="email" defaultValue={values.email} aria-invalid={Boolean(errors.email)} required />{field("email")}</label>
        <label>Phone number<input name="phone" type="tel" autoComplete="tel" minLength={7} maxLength={32} defaultValue={values.phone} aria-invalid={Boolean(errors.phone)} required />{field("phone")}</label>
        <label>Service type<select name="service_type" defaultValue={values.service_type ?? ""} aria-invalid={Boolean(errors.service_type)} required><option value="" disabled>Choose a service</option>{config.services.map((service) => <option key={service}>{service}</option>)}</select>{field("service_type")}</label>
        <label>Property type<select name="property_type" defaultValue={values.property_type ?? ""} aria-invalid={Boolean(errors.property_type)} required><option value="" disabled>Choose a property</option>{config.property_types.map((property) => <option key={property}>{property}</option>)}</select>{field("property_type")}</label>
        <label>Preferred date<input name="preferred_date" type="date" defaultValue={values.preferred_date} aria-invalid={Boolean(errors.preferred_date)} required />{field("preferred_date")}</label>
      </div>
      <label>What should we know?<textarea name="message" rows={5} minLength={10} maxLength={5000} required defaultValue={values.message} aria-invalid={Boolean(errors.message)} placeholder="Tell us about the space, timing, and anything to focus on." />{field("message")}</label>
      <div className="form-footer">
        <span>{pending ? "Sending your request…" : "Your details are used for this cleaning request. Required fields are marked by your browser."}</span>
        <SubmitButton label="Send inquiry" pendingLabel="Sending…" />
      </div>
    </form>
  );
}
