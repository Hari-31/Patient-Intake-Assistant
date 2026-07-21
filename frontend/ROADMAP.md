# React Frontend Roadmap

Roadmap for building the React frontend against the existing FastAPI backend in
`backend/`.

## Guiding Assumptions

- The first frontend will live in `frontend/`.
- React will be implemented with TypeScript.
- Supabase Auth is the source of login state and bearer tokens.
- The backend remains the source of authorization, role enforcement, safety
  handling, persistence, and AI calls.
- Patient and doctor workflows are separate route groups.
- The UI must treat AI output as educational intake support, not diagnosis.

## Phase 0: Requirements Alignment

Goal: confirm scope before building user-facing flows that are expensive to
change later.

Deliverables:

- Answer the clarifying questions in `README.md`.
- Decide whether the first release includes patient, doctor, or both role
  surfaces.
- Choose frontend framework details: Vite versus Next.js, styling system, test
  stack, deployment target.
- Decide whether patient session history is in scope for the first release.
- Define required medical, privacy, and emergency copy.

Acceptance criteria:

- Product scope is documented.
- Technical stack is documented.
- Hard constraints are documented.
- Any backend gaps required for the first release are converted into issues.

## Phase 1: Project Scaffold And Tooling

Goal: create a maintainable React foundation.

Deliverables:

- Vite React TypeScript app under `frontend/`.
- Environment validation for `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and
  `VITE_SUPABASE_ANON_KEY`.
- Supabase browser client.
- API client that attaches Supabase access tokens to protected requests.
- React Router route shell.
- TanStack Query provider.
- ESLint, formatting, typecheck, unit test, and build scripts.

Acceptance criteria:

- `npm run dev` starts the frontend.
- `npm run build` succeeds.
- `npm run typecheck` succeeds.
- Missing environment variables fail with a clear local error.
- No backend-only secret names appear in built frontend code.

## Phase 2: Auth And Route Protection

Goal: support safe role-aware navigation.

Deliverables:

- Patient signup form using backend `POST /auth/signup`.
- Login and logout using Supabase Auth.
- Auth session persistence and refresh handling.
- Protected route wrapper.
- Role-aware routing for patient and doctor areas.
- Unauthorized and expired-session states.

Acceptance criteria:

- A patient can sign up, log in, and reach the patient intake screen.
- A logged-out user cannot access protected pages.
- Patient UI does not show doctor routes.
- Doctor UI does not show patient-only actions.
- Invalid or expired tokens produce a clear recovery path.

Backend dependencies:

- Backend CORS must allow the frontend origin.
- Supabase providers must be configured.
- Doctor accounts must exist through an admin workflow.

## Phase 3: Patient Intake Chat

Goal: make the core intake conversation usable.

Deliverables:

- Chat interface for starting a new session.
- Follow-up message flow using the returned `session_id`.
- Loading, retry, empty, and error states.
- Emergency response presentation when `emergency_triggered` is true.
- Local active-session persistence if cross-refresh resume is required.

Acceptance criteria:

- First patient message creates a session.
- Follow-up messages reuse the current session ID.
- Unknown session errors offer a new-intake path.
- Emergency-triggered responses are visually distinct and cannot be confused
  with ordinary assistant output.
- The UI never claims to diagnose or clear emergencies.

Backend dependencies:

- Existing `POST /chat` route.
- Optional future endpoint to list patient sessions if historical resume is
  required.

## Phase 4: Report Upload

Goal: attach patient PDFs to an owned intake session.

Deliverables:

- PDF file picker and drag-and-drop area.
- Client-side file type and size checks.
- Multipart upload to `POST /upload`.
- Upload progress, success, validation error, and retry states.
- Post-upload chat guidance that report context may influence future responses.

Acceptance criteria:

- Upload is disabled until a patient session exists.
- Non-PDF and over-10-MB files are rejected before request submission.
- Backend validation errors are visible and actionable.
- Successful upload shows filename and embedded chunk count.

Backend dependencies:

- Existing `POST /upload` route.
- OCR support is out of scope until backend support exists.

## Phase 5: Patient Summary Review

Goal: present generated summaries clearly and safely.

Deliverables:

- Summary request using `POST /summary`.
- Structured display for chief complaint, timeline, relevant history, red
  flags, warning signs, possible directions, and doctor questions.
- Refetch or invalidation when new chat messages are sent.
- Print or export decision, if required.

Acceptance criteria:

- Summary cannot be requested before a session exists.
- Reported red flags are separated from future warning signs.
- Empty arrays display useful empty states.
- Summary content is not editable unless product scope explicitly requires it.

Backend dependencies:

- Existing `POST /summary` route.
- Optional future endpoint for patient summary history.

## Phase 6: Doctor Dashboard

Goal: give doctors read-only review tools for assigned patients.

Deliverables:

- Assigned patient list from `GET /doctor/patients`.
- Summary list from `GET /doctor/summaries`.
- Patient filter support.
- Transcript and summary view from `GET /doctor/sessions/{session_id}`.
- Empty, loading, and unauthorized states.

Acceptance criteria:

- Doctors only see assigned patients returned by the backend.
- Doctors can inspect a transcript alongside its summary.
- No UI exposes patient-doctor assignment writes.
- No UI exposes doctor notes unless backend write APIs are added.

Backend dependencies:

- Existing doctor read routes.
- Admin process for patient-doctor assignments.

## Phase 7: Quality, Safety, And Accessibility

Goal: raise the app from working prototype to reliable clinical-adjacent tool.

Deliverables:

- Keyboard-accessible chat, forms, upload controls, tabs, and dialogs.
- Screen-reader labels and status announcements for async events.
- Consistent error handling for 400, 401, 403, 404, 502, and 503 responses.
- Privacy review for browser storage and logs.
- Unit tests for API client, auth guards, and critical rendering states.
- E2E tests for signup/login, patient chat, summary, upload, and doctor review.

Acceptance criteria:

- Critical flows are covered by automated tests.
- The app remains usable on mobile and desktop viewports.
- Sensitive data is not logged to the console.
- Error messages do not expose backend secrets or internal stack traces.

## Phase 8: Production Readiness

Goal: prepare deployment with explicit operational controls.

Deliverables:

- Production environment configuration.
- Build and deploy pipeline.
- Backend CORS production allowlist.
- Error monitoring decision with privacy review.
- Release checklist.
- Runbook for auth failures, backend downtime, and report upload failures.

Acceptance criteria:

- Production build is reproducible.
- Required environment variables are documented.
- Health-check behavior is defined.
- Rollback path is documented.
- No frontend bundle contains backend secrets.

## Frontend Backlog

- Add patient session history after backend support exists.
- Add transcript retrieval for patients after backend support exists.
- Add password reset flow through Supabase Auth.
- Add doctor account invitation flow after backend/admin support exists.
- Add reviewed/unreviewed summary state if doctors need workflow tracking.
- Add OCR upload flow after backend support exists.
- Add internationalization if target users require it.
- Add audit-friendly UI event logging only after privacy constraints are clear.

## Current Risks

- Patient session history is persisted but not exposed through a patient API.
- Doctor accounts and assignments require an admin workflow outside the current
  frontend.
- Medical and emergency copy requires clinical/legal review before production.
- Compliance constraints have not been stated.
- Scanned PDFs are rejected until OCR support is implemented.

## Decisions Needed

1. Build scope: patient MVP only, doctor MVP only, or both?
2. Framework: Vite React TypeScript or another React framework?
3. Styling: Tailwind CSS, CSS Modules, shadcn/ui, MUI, or custom components?
4. Session history: required for MVP or deferred?
5. Doctor workflow: read-only only, reviewed state, or notes?
6. Deployment: Vercel, Netlify, Supabase hosting, custom server, or other?
7. Compliance: what privacy, storage, audit, and monitoring limits apply?
8. Release quality bar: required tests, accessibility level, and browser support?
