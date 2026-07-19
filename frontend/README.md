# Patient Intake Assistant Frontend

React frontend backed by Supabase Auth, Postgres, Storage, and a Supabase Edge
Function. The browser does not require the FastAPI server in `backend/` to
run.

This document describes the current frontend architecture, API contract, setup
path, security boundaries, and open questions that must be answered before the
React implementation is treated as product-complete.

## Implementation Status

The first implementation is a Vite React TypeScript app with:

- Supabase Auth session management and role-aware routing.
- Patient signup through the `patient-intake-api` Edge Function, then
  Supabase login.
- Patient intake chat, summaries, PDF report storage/embeddings, and doctor
  review through that same Supabase-hosted function.
- Environment validation, typed API client, TanStack Query, React Hook Form,
  Zod validation, Vitest, and React Testing Library setup.

## Supabase Backend Context

The Supabase Edge Function is the server-side API for the educational
patient-intake assistant. It supports:

- Patient account creation with the Supabase admin API from the Edge Function.
- Supabase Auth login, with frontend clients using the Supabase publishable key.
- Patient-only chat and medical summary generation through OpenAI calls made
  from the Edge Function.
- Patient-only PDF report upload and embeddings through private Storage.
- Doctor-only read access through role and assignment checks in the function.
- Supabase Postgres persistence for sessions, messages, summaries, reports, and
  patient-doctor assignments.

The backend enforces authorization by reading `app_metadata.role` from the
Supabase access token. Frontend code must never trust or set the role from
editable user metadata.

## Frontend Stack

- React with TypeScript.
- Vite for local development and builds.
- React Router for route-level patient and doctor flows.
- `@supabase/supabase-js` for login, logout, session refresh, and access tokens.
- TanStack Query for API request state, caching, retries, and invalidation.
- React Hook Form plus Zod for forms and validation.
- MSW for API mocking in component and integration tests.
- Vitest and React Testing Library for unit and component tests.
- Playwright for critical end-to-end flows.
- Lucide React for icons.

## App Structure

```text
frontend/
  README.md
  ROADMAP.md
  .env.example
  package.json
  vite.config.ts
  src/
    app/
      App.tsx
      api-context.tsx
      query-client.ts
    components/
      layout/
      feedback/
    features/
      auth/
      patient/
      doctor/
    lib/
      api-client.ts
      supabase.ts
      env.ts
      types.ts
    test/
      setup.ts
```

## Environment Variables

The frontend should use only public client-safe values:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-public-publishable-key
```

Never include these backend-only values in frontend code or browser-exposed
environment variables:

- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `DATABASE_URL`
- `OPENAI_API_KEY`

## Local Development

1. Apply the database migrations and deploy `patient-intake-api` as described
   in [the Supabase deployment guide](../backend/supabase/README.md).
2. Copy `.env.example` to `.env.local` and fill in the `VITE_*` values.
3. Install dependencies and run the frontend dev server.

Commands:

```sh
cd frontend
npm install
npm run dev
```

Validation:

```sh
npm run typecheck
npm run test
npm run build
```

## API Contract

All protected requests must send:

```http
Authorization: Bearer <supabase-access-token>
```

### Supabase Edge Function

The browser invokes `patient-intake-api` through the Supabase client. The
function routes its typed actions internally and verifies the signed-in user's
role before every patient, report, or doctor operation.

Patient signup request:

```json
{
  "email": "patient@example.com",
  "password": "secure-password",
  "name": "Test Patient"
}
```

Response:

```json
{
  "user_id": "uuid",
  "email": "patient@example.com",
  "role": "patient"
}
```

Login uses Supabase Auth directly from the frontend. The Edge Function creates
patient accounts only; doctor accounts remain an administrator workflow.

### Patient Chat

`patient-intake-api` action: `chat`

First request:

```json
{
  "message": "I have had a headache since yesterday."
}
```

Follow-up request:

```json
{
  "session_id": "uuid-returned-from-first-chat-response",
  "message": "It is getting worse."
}
```

Response:

```json
{
  "session_id": "uuid",
  "reply": "Assistant response text",
  "emergency_triggered": false
}
```

Frontend behavior:

- Store the active `session_id` for the current intake.
- Send `session_id` on follow-up messages.
- Treat a missing or unknown session as a recoverable state and offer to start a
  new intake.
- When `emergency_triggered` is true, display the backend reply prominently and
  avoid presenting the response as a diagnosis.

### Patient Summary

`patient-intake-api` action: `summary`

Request:

```json
{
  "session_id": "uuid"
}
```

Response:

```json
{
  "chief_complaint": "Headache",
  "symptom_timeline": "Started yesterday.",
  "relevant_history": "No relevant history reported.",
  "red_flags": [],
  "warning_signs_to_watch": ["Sudden severe worsening"],
  "possible_directions": ["Discuss with a clinician"],
  "suggested_questions_for_doctor": ["Could this be a migraine?"]
}
```

Frontend behavior:

- Present the summary as educational intake support, not medical advice.
- Clearly separate reported `red_flags` from future `warning_signs_to_watch`.
- Regenerate or refetch the summary after new chat messages.

### Patient Report Upload

`patient-intake-api` action: `upload_report`

Multipart form fields:

- `session_id`: UUID for an owned patient session.
- `file`: PDF file.

Response:

```json
{
  "report_id": "uuid",
  "session_id": "uuid",
  "filename": "labs.pdf",
  "chunk_count": 3
}
```

Frontend behavior:

- Accept PDFs only.
- Enforce a client-side 10 MB limit before upload.
- Show upload progress, success state, and backend validation errors.
- Explain scanned PDFs may fail until OCR support exists.

### Doctor Dashboard

`patient-intake-api` action: `doctor_patients`

Returns assigned patients:

```json
[
  {
    "patient_id": "uuid",
    "name": "Test Patient",
    "assigned_at": "2026-07-17T00:00:00Z"
  }
]
```

`patient-intake-api` action: `doctor_summaries` with an optional
`patient_id`.

Returns summaries for assigned patients.

`patient-intake-api` action: `doctor_session` with `session_id`.

Returns ordered transcript messages and the current summary for an assigned
patient session.

Frontend behavior:

- Use role-based routing to separate doctor and patient screens.
- Treat doctor access as read-only.
- Show empty states for no assignments, no summaries, and no transcript.
- Never expose patient-doctor assignment controls unless a backend admin route is
  explicitly added later.

## Required Screens

- Auth: patient signup, login, logout, password reset if Supabase is configured
  for it.
- Patient intake: conversational chat, active session state, emergency response
  state, report upload, summary review.
- Doctor dashboard: assigned patient list, summary list, transcript and summary
  verification view.
- Shared: loading states, error states, authenticated layout, unauthorized page,
  not-found page.

## Security And Privacy Rules

- Do not store backend secrets in frontend code.
- Do not log access tokens, patient messages, uploaded file names, or summaries.
- Keep browser storage minimal; prefer Supabase session storage and short-lived
  UI state.
- Do not authorize UI actions from user-editable metadata.
- Do not let patient routes call doctor APIs, even if the backend rejects them.
- Do not present AI responses as diagnosis, treatment, or emergency clearance.
- Make emergency and urgent-care language visible without being dismissible as
  ordinary chat decoration.

## Backend Gaps To Resolve For Frontend

- CORS middleware is not currently configured in `backend/app/main.py`.
- There is no patient endpoint to list previous sessions.
- There is no patient endpoint to fetch a prior transcript.
- There is no public doctor signup or invite workflow.
- There is no backend route for password reset; this should use Supabase Auth if
  enabled.
- There is no OCR path for scanned PDFs.

## Clarifying Questions

### Product Requirements

1. Who is the first release for: patients only, doctors only, or both roles?
2. Should the first screen after login be a new patient intake, a previous intake
   list, or a role-based dashboard?
3. Should patients be able to resume old sessions across browsers and devices?
4. Should patients be able to edit a generated summary before sharing it?
5. Should doctors be able to add notes, mark summaries reviewed, or only read?
6. What exact disclaimer and emergency language must appear in the UI?
7. Are uploaded reports limited to labs, imaging reports, discharge notes, or any
   medical PDF?
8. Is this intended for education, clinic workflow support, or production care
   coordination?

### Technical Requirements

1. Should the frontend be created inside this repo as `frontend/`, or should it
   be a separate repository?
2. Do you want Vite React TypeScript, Next.js, or another React framework?
3. Which UI approach should be used: Tailwind CSS, CSS Modules, shadcn/ui, MUI,
   or a custom component system?
4. Which deployment target should the frontend support first?
5. Should API types be hand-written, generated from OpenAPI, or shared from a
   contract package?
6. Should the app use Supabase email/password only, or also OAuth providers?
7. Should protected routes depend only on Supabase session state, or should the
   frontend call a backend `/me` endpoint if one is added?
8. Should file uploads show progress, support retry, or support background
   processing states?

### Engineering Principles

1. What is the minimum acceptable test coverage for the first frontend release?
2. Should the project enforce lint, format, typecheck, unit tests, and E2E tests
   in CI before merge?
3. Should frontend code optimize for speed of iteration or stricter domain
   modeling from day one?
4. Should accessibility follow WCAG 2.1 AA as a hard release requirement?
5. Should the UI be designed as a quiet clinical tool, a consumer-friendly
   assistant, or both through different role surfaces?
6. Should analytics be excluded entirely until privacy and compliance rules are
   explicit?

### Hard Constraints

1. Are there HIPAA, GDPR, SOC 2, clinic procurement, or institutional review
   constraints that apply now?
2. Can any patient data be stored in browser local storage, session storage, or
   IndexedDB?
3. Are screenshots, analytics, error monitoring breadcrumbs, or session replay
   tools prohibited?
4. What browsers and mobile screen sizes must be supported?
5. What is the maximum acceptable response time for chat, summary generation,
   and report upload?
6. Should the frontend block use when the backend health check fails?
7. Should the product require explicit patient consent before uploading reports
   or generating summaries?
8. Are there brand, copy, accessibility, or clinical review approvals required
   before launch?
