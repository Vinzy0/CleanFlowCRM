# Integrations and lead workflow UI handoff

## Scope

This narrow extension covers `web/app/crm/integrations` and `web/app/crm/leads/[id]/workflow-panel.tsx`.
It preserves the existing CRM: green sidebar (#173e35), pale ground (#f5f8f5), white panels, Arial, green actions, and rounded inputs.
Desktop integrations use two panels above delivery logs; below 1000px they stack. The CRM navigation moves above the content on smaller screens.
Lead workflow stays within the existing detail layout and stacks with the other panels on mobile.

## Owner controls and states

- API keys: name, read/write permissions, generate, one-time credential reveal/hide, active/revoked status, last use, and confirmed revoke.
- Webhooks: name, HTTPS URL, event checkboxes, one-time signing-secret reveal/hide, active/removed status, subscription editing, and confirmed removal.
- Deliveries: latest 50, status, event ID, attempt count, expandable attempt history, and next attempt for pending deliveries.
- Failed last attempts expose Retry; Process queued deliveries handles up to five due deliveries. Success means HTTP 2xx; downstream results require checking the automation platform.
- Forms provide pending labels, error alerts, and success notices. Empty keys, destinations, deliveries, and attempt histories have explanatory copy; load failure offers refresh guidance.
- Public-demo integrations show an unavailable panel without credential or delivery controls. Demo workflow fields are disabled and the save action is omitted.
- Workflow fields cover source, comma-separated tags, next action, next follow-up, and appointment. Dates display in browser-local time and submit as ISO timestamps; save errors and confirmation appear in the panel.

## Evidence and review

These are synthetic localhost fake-provider evidence, not live Make proof. They demonstrate local owner UI states and responsive composition; they do not establish production delivery or downstream automation success.

- [Integrations desktop](evidence/integrations-desktop.jpg): empty keys, active mock destination, collapsed subscription/history controls, and three succeeded mock deliveries.
- [Integrations mobile](evidence/integrations-mobile.jpg): the same state in stacked panels with wrapped delivery metadata.
- [Lead workflow desktop](evidence/lead-workflow-desktop.jpg): populated synthetic source/tags/action/dates, save control, and automation history with a pending appointment event.
- [Lead workflow mobile](evidence/lead-workflow-mobile.jpg): the populated workflow and automation history in the existing stacked lead detail layout.

Reviewer disposition: ship after the resolved contrast fix. Secondary text on the new integration and workflow surfaces uses #4b6358, scoped in `integrations.css` and `crm.css`.
Mechanical detector findings: `[]`.
This handoff records the extension only; the existing product identity and unrelated screens remain the visual authority.
