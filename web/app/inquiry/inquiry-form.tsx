"use client";

import { useActionState } from "react";
import { submitInquiry } from "@/app/actions";
import SubmitButton from "@/app/submit-button";
import type { PublicConfig } from "@/lib/api";

export default function InquiryForm({ config, inquiryKey }: { config: PublicConfig; inquiryKey: string }) {
  const [state, action] = useActionState(submitInquiry, { error: "", values: {}, attempt: 0 });
  return (
    <form key={state.attempt} action={action} className="form-card">
      <input type="hidden" name="inquiry_key" value={inquiryKey} />
      {state.error && <p role="alert" className="error">{state.error}</p>}
      <div className="form-grid">
        <label>Customer name<input name="name" autoComplete="name" minLength={2} maxLength={120} defaultValue={state.values.name} required /></label>
        <label>Email<input name="email" type="email" autoComplete="email" defaultValue={state.values.email} required /></label>
        <label>Phone number<input name="phone" type="tel" autoComplete="tel" minLength={7} maxLength={32} defaultValue={state.values.phone} required /></label>
        <label>Service type<select name="service_type" defaultValue={state.values.service_type ?? ""} required><option value="" disabled>Choose a service</option>{config.services.map((service) => <option key={service}>{service}</option>)}</select></label>
        <label>Property type<select name="property_type" defaultValue={state.values.property_type ?? ""} required><option value="" disabled>Choose a property</option>{config.property_types.map((property) => <option key={property}>{property}</option>)}</select></label>
        <label>Preferred date<input name="preferred_date" type="date" defaultValue={state.values.preferred_date} required /></label>
      </div>
      <label>What should we know?<textarea name="message" rows={5} minLength={10} maxLength={5000} required defaultValue={state.values.message} placeholder="Tell us about the space, timing, and anything to focus on." /></label>
      <div className="form-footer"><span>Your details are used for this cleaning request.</span><SubmitButton label="Send inquiry" /></div>
    </form>
  );
}
