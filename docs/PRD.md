# Product Requirements Document

## 1. Product Overview

### Product Name
**CleanFlow CRM** — working name.

### Product Type
A fully working CRM demo designed around a fictional cleaning business.

### Primary Purpose
The product has two goals:

1. Demonstrate Vince's ability to build a complete custom CRM and business automation system.
2. Act as a sales demo for freelance clients who want a CRM customized around their own business.

The demo must feel like a real product rather than a mockup.

### Core Pitch

> This example is for a cleaning business. I can make the same kind of system around your own customers, workflow, fields, automation, and branding.

---

# 2. Target User

Primary user:

**Owner or employee of a small cleaning business.**

Their current workflow may look like:

Customer sends inquiry  
→ employee manually records customer  
→ employee reads the message  
→ decides priority  
→ contacts customer  
→ remembers to follow up  
→ manually tracks whether customer booked

The CRM centralizes and automates this process.

---

# 3. Main Product Flow

```text
Customer submits inquiry
        ↓
Lead is created
        ↓
AI processes inquiry
        ↓
AI generates:
- service classification
- priority classification
- short summary
- classification rationale
        ↓
Business owner receives email notification
        ↓
Lead appears in CRM pipeline
        ↓
Owner reviews lead
        ↓
Owner changes status
New → Contacted → Booked → Completed
        ↓
AI can generate suggested follow-up email
        ↓
Human reviews / edits reply
        ↓
Email is sent
```

---

# 4. Demo Flow

The publicly hosted demo must include:

## Simulate New Inquiry

A prominent button:

**Simulate New Inquiry**

When clicked:

1. Select or generate one predefined fake customer inquiry.
2. Create the lead through the same backend process used by the real inquiry form.
3. Run AI classification.
4. Generate AI summary.
5. Store AI results.
6. Add lead to pipeline.
7. Trigger demo-safe notification behavior.
8. Redirect/show user the newly created lead.

This allows a recruiter or potential client to experience the complete workflow immediately.

---

# 5. MVP Features

## 5.1 Authentication

Business users can:

- log in
- log out
- access protected CRM pages

MVP does not need complex organizations or enterprise role management.

At minimum:

- authenticated user
- unauthenticated visitor

---

# 5.2 Public Inquiry Form

Fields:

- Customer name
- Email
- Phone number
- Service type
- Property type
- Preferred date
- Customer message

Submission must:

- validate required fields
- create a lead
- prevent accidental duplicate submission where practical
- trigger AI processing
- trigger owner notification

---

# 5.3 Dashboard

Display:

- New leads
- Contacted leads
- Booked leads
- Completed leads
- Recent leads

Example:

```text
New Leads       12
Contacted        8
Booked           4
Completed       21
```

Do not build complex analytics for MVP.

---

# 5.4 Pipeline

Pipeline stages:

```text
New
↓
Contacted
↓
Booked
↓
Completed
```

Optional terminal state:

```text
Lost
```

Each lead should display:

- customer name
- requested service
- priority
- preferred date

Preferred interaction:

**Kanban drag-and-drop.**

Fallback:

If drag-and-drop threatens the delivery timeline, replace it with:

**Change Status → dropdown/button**

The pipeline itself must remain.

---

# 5.5 Lead Detail View

Display:

### Customer
- name
- email
- phone

### Request
- service
- property type
- preferred date
- original inquiry

### CRM
- current pipeline stage
- created timestamp
- latest update

### AI Analysis
- summary
- category
- priority
- classification rationale

### Actions
- Change status
- Contact customer
- Draft Reply

---

# 6. AI Features

Limit MVP AI functionality to exactly three major features.

## 6.1 AI Classification

The AI classifies the inquiry using a predefined list of allowed categories.

Example:

### Service Category
- Standard House Cleaning
- Deep Cleaning
- Move-In / Move-Out
- Commercial Cleaning
- Other

### Priority
- High
- Normal

The model must not invent arbitrary labels.

---

# 6.2 Priority Rules

Priority must use constrained classification.

Example high-priority criteria:

- customer requests service within 48 hours
- commercial/high-value job
- urgent move-out deadline
- explicitly asks for immediate response

The AI receives these criteria and evaluates whether the inquiry matches them.

Expected structured response:

```json
{
  "priority": "high",
  "matched_rules": [
    "Customer requested service within 48 hours"
  ],
  "rationale": "The requested cleaning date is tomorrow."
}
```

Persist:

- classification
- matched rule(s)
- short rationale

Do not depend on hidden chain-of-thought or unrestricted model reasoning.

---

# 6.3 AI Summary

Convert the inquiry into concise bullets.

Example:

```text
• Residential deep cleaning
• 3-bedroom property
• Requested Saturday
• Customer wants kitchen and bathrooms prioritized
```

The summary must be stored in the database.

---

# 6.4 Draft Reply

Button:

**Draft Reply**

AI generates a suggested customer email based on:

- inquiry
- customer name
- service
- requested date
- CRM context

Example:

```text
Hi John,

Thanks for contacting Acme Cleaning Services.

We can help with your three-bedroom deep cleaning request for Saturday...
```

Important:

**Never automatically send an AI-generated response.**

Flow:

```text
Generate
↓
Human reviews
↓
Human edits if needed
↓
Human clicks Send
```

---

# 7. Email

Use:

**Resend**

Email use cases:

### Owner Notification

Example:

```text
New lead: John Smith
Service: Deep Cleaning
Priority: High
```

### Customer Follow-Up

Only send after explicit human confirmation.

No SMS in MVP.

No Twilio in MVP.

---

# 8. Config-First Architecture

The system must not be deeply hardcoded around cleaning terminology.

Create a business configuration layer.

Example structure:

```text
businessConfig
├── businessName
├── branding
├── pipelineStages
├── serviceCategories
├── leadFields
├── priorityRules
└── AI classification categories
```

Cleaning is the first implementation.

Example:

```json
{
  "business_name": "Acme Cleaning Services",

  "pipeline_stages": [
    "New",
    "Contacted",
    "Booked",
    "Completed"
  ],

  "services": [
    "Standard Cleaning",
    "Deep Cleaning",
    "Move-In / Move-Out",
    "Commercial Cleaning"
  ]
}
```

Important:

Do **not** turn this into a generic CRM-building framework.

Only extract configuration that clearly makes future client customization easier.

The cleaning demo remains the first-class product.

---

# 9. Data Model

## User

```text
id
email
password_hash / auth_provider_id
name
created_at
```

## Lead

```text
id
name
email
phone
service_type
property_type
preferred_date
message
pipeline_stage
priority
created_at
updated_at
```

## AI Analysis

```text
id
lead_id
service_category
priority
summary
matched_priority_rules
classification_rationale
model
created_at
```

## Email / Activity

```text
id
lead_id
type
status
content / metadata
created_at
```

Examples:

```text
lead_created
status_changed
email_sent
ai_classified
reply_generated
```

---

# 10. Activity Timeline

Each lead should show a basic history.

Example:

```text
10:31 AM — Lead created
10:31 AM — AI classified lead as High Priority
10:32 AM — Owner notified
11:06 AM — Status changed to Contacted
11:08 AM — Draft reply generated
11:10 AM — Email sent
```

This improves both usability and the quality of the demo.

---

# 11. Recommended Technical Architecture

## Frontend

Preferred:

**Next.js + TypeScript**

Responsibilities:

- dashboard
- pipeline
- lead pages
- inquiry form
- authentication UI
- demo interaction

A simpler React frontend is acceptable if the existing CRM already uses it.

Do not rewrite an existing working frontend merely to match this recommendation.

---

## Backend

Preferred:

**Python + FastAPI**

Responsibilities:

- lead API
- AI processing
- business rules
- email sending
- demo simulation
- authentication integration
- activity logging
- config handling

---

## Database

**PostgreSQL**

Use migrations.

---

## AI

**DeepSeek 4.1**

AI calls must return structured output where possible.

Never rely on free-form parsing if the provider supports a reliable structured-response approach.

---

## Email

**Resend**

---

## Deployment

Use a simple cloud deployment suitable for a portfolio project.

Requirements:

- HTTPS
- environment variables
- production PostgreSQL
- logs
- separate secrets from source code

Docker should be supported for reproducible local/backend deployment.

---

# 12. API Requirements

Illustrative endpoints:

```text
POST /api/leads
GET  /api/leads
GET  /api/leads/{id}
PATCH /api/leads/{id}

PATCH /api/leads/{id}/status

POST /api/leads/{id}/draft-reply
POST /api/leads/{id}/send-email

POST /api/demo/simulate-inquiry
POST /api/demo/reset
```

Exact routes may change based on implementation architecture.

---

# 13. Public Demo Safety

The public demo must not become an uncontrolled production system.

Implement:

## Rate limiting

Especially for:

- Simulate Inquiry
- AI requests
- login attempts
- Draft Reply

---

## AI Limits

Prevent visitors from generating unlimited paid AI requests.

Possible methods:

- per-IP limits
- session limits
- fixed demo scenarios
- cached/pre-generated fallback

---

## Email Safety

Public demo users must NOT be able to send email to arbitrary addresses.

Demo mode should either:

- redirect email to a controlled test inbox
- disable actual sending
- use a sandbox/testing configuration

---

## Demo Data

Use fake customer information only.

Never include actual client/customer data.

---

## Reset

Provide a way to periodically restore demo data to a known state.

---

# 14. Non-Functional Requirements

## Performance

Normal CRM pages should feel responsive.

Long AI requests should display loading state rather than freeze the interface.

---

## Reliability

Failures must not silently disappear.

Example:

If AI classification fails:

```text
Lead is still created
AI status = Failed / Pending
Owner can retry
```

If email fails:

```text
Email status = Failed
Failure is logged
Owner can retry
```

---

## Security

At minimum:

- authentication
- password security through trusted auth solution
- authorization on CRM routes
- input validation
- secrets stored in environment variables
- no API keys exposed to browser
- rate limiting
- safe logging
- database parameterization/ORM protection

---

## Maintainability

Code should be:

- modular
- typed where practical
- documented
- testable
- organized by clear responsibilities

Avoid unnecessary abstraction.

---

# 15. Testing

Minimum automated testing:

## Backend

Test:

- lead creation
- invalid lead rejection
- status updates
- AI structured-response parsing
- priority rule handling
- email workflow
- demo simulation
- authentication/authorization

## Integration

Test one complete path:

```text
Create inquiry
↓
Lead saved
↓
AI result stored
↓
Activity created
↓
Lead returned correctly
```

---

# 16. Demo Presentation

## Live Demo

Public URL with:

**Try Live Demo**

Main demo CTA:

**Simulate New Inquiry**

The visitor should understand the product within approximately one minute.

---

## Video Demo

Create a **60–90 second video**.

Suggested sequence:

```text
0–10 sec
"This is a CRM I built for a fictional cleaning business."

10–25 sec
Submit/simulate customer inquiry.

25–40 sec
Show lead automatically appear.

40–55 sec
Show AI classification + summary.

55–70 sec
Move lead through pipeline.

70–80 sec
Generate draft reply.

80–90 sec
"This can be customized around another business's workflow."
```

Portfolio buttons:

```text
[ Watch Demo ]
[ Try Live Demo ]
```

---

# 17. Explicitly Out of Scope

Do NOT add these to MVP:

- SMS
- WhatsApp
- Twilio
- invoicing
- payments
- calendar booking system
- complex analytics
- marketing automation suite
- chatbot
- RAG
- autonomous agents
- multiple organizations
- enterprise RBAC
- mobile app
- hundreds of CRM settings
- full HubSpot replacement
- unlimited business-config builder
- advanced reporting
- automatic AI email sending

These can be added only after V1 is shipped.

---

# 18. Build Priority

## Phase 1 — Foundation

- authentication
- database schema
- lead CRUD
- inquiry form
- CRM layout

## Phase 2 — Core CRM

- dashboard
- pipeline
- lead detail
- status changes
- activity history

## Phase 3 — AI

- constrained classification
- summary
- classification rationale
- draft reply

## Phase 4 — Automation

- Resend notifications
- customer email sending
- failure/retry behavior

## Phase 5 — Demo Mode

- simulated inquiries
- fake data
- AI/email safety
- rate limits
- reset behavior

## Phase 6 — Polish

- clean UI
- responsive states
- loading/error states
- README
- deployment
- demo video

---

# 19. MVP Acceptance Criteria

The product is considered functional when:

- [ ] User can log in.
- [ ] Customer inquiry can create a lead.
- [ ] Lead is persisted in PostgreSQL.
- [ ] AI classifies the lead using fixed categories.
- [ ] AI provides a short stored summary.
- [ ] AI priority is based on predefined criteria.
- [ ] Classification rationale is persisted.
- [ ] Owner receives a notification.
- [ ] Lead appears in pipeline.
- [ ] Owner can change lead status.
- [ ] Lead has a detail page.
- [ ] Activity history is recorded.
- [ ] AI can draft a follow-up response.
- [ ] Human must approve email before sending.
- [ ] Demo visitors can trigger a simulated inquiry.
- [ ] Demo AI usage is rate-limited.
- [ ] Demo cannot send arbitrary emails.
- [ ] App is deployed.
- [ ] README/setup instructions exist.
- [ ] 60–90 second demo video exists.

---

# 20. Definition of Done

The project is **DONE** when this exact sequence can be demonstrated reliably:

```text
Simulate customer inquiry
        ↓
Lead created
        ↓
AI classifies and summarizes
        ↓
Owner notified
        ↓
Lead appears in pipeline
        ↓
Owner opens lead
        ↓
Owner changes status
        ↓
AI generates reply
        ↓
Owner approves email
        ↓
Email workflow completes
```

The app must be:

- deployed
- stable enough for public demonstration
- populated with realistic fake data
- documented
- safe for public visitors
- presented through both live demo and video

Once those conditions are satisfied:

**Stop adding features and publish it.**