# Patient Intake Assistant

A chatbot that interviews patients before they see a doctor.

The patient describes what's wrong in a chat. The assistant asks follow-up questions one at a time — when it started, where it hurts, how bad, what makes it worse, past history, medications, allergies — and once it has the full picture it closes the request and sends it for review. The doctor opens a dashboard, reads a structured summary in about thirty seconds, and can expand the full transcript to check every claim against what the patient actually typed.

Patients can also attach a PDF report. The assistant reads it, and if what the patient says contradicts what's in the report — no medications, but the report lists two — the summary flags the discrepancy for the doctor.

This is an educational project. It is decision support, not a diagnostic tool, and it says so on every screen.

## Screens

**Landing** — start a new request or check status; separate sign-in for doctors.
**Patient workspace** — the intake conversation on the left, PDF upload on the right, disclaimer at the top.
**Doctor workspace** — assigned requests down the side, summary in the middle, transcript expandable, and one button to mark a request reviewed.

## How a turn works

```
Patient chat (React)
        │  Supabase JWT
        ▼
FastAPI ── auth gate: verify signature, read role from app_metadata
        │
        ▼
Orchestrator, on every message:
        1. reject the turn if the request is already closed
        2. save the message
        3. deterministic red-flag check → emergency? close and escalate
        4. RAG: pull matching chunks from the patient's uploaded report
        5. LLM returns coverage booleans + one follow-up question
        6. all nine topics covered? close the request and write the summary
        │
        ▼
Structured summary + transcript ──► doctor dashboard ──► mark completed
```

## Decisions worth explaining

**The server decides when the interview ends, not the model.** The LLM returns a boolean per topic. The request closes only when all nine are true — answered, declined, or "I don't know". The model can't talk its way out early, and it isn't allowed to offer a summary itself.

**Red flags are rules, not model judgement.** A deterministic checker runs *before* the LLM on every message, with negation handling so "no chest pain" doesn't fire. When it matches, the request is escalated immediately and the LLM never sees the turn. The `red_flags` field in the final summary is overwritten with what the rules found, so the safety-critical output never depends on what the model felt like writing.

**One active request per patient, enforced in the database.** A partial unique index makes a second `active` row impossible. Closed requests are immutable — further messages and uploads return `409`. A new concern starts a new request, so each summary stays verifiable against its own frozen transcript.

**Uploaded report text is data, never instructions.** Retrieved chunks are injected with explicit framing that closes off prompt injection through a PDF.

**Isolation is enforced twice.** Every query scopes by patient or doctor id, and Row Level Security policies enforce the same rules at the database. A bug in the application layer still can't leak another patient's data.

## Stack

| | |
|---|---|
| Backend | FastAPI, Python |
| Frontend | React, Vite, TypeScript, TanStack Query |
| Auth | Supabase Auth — JWT, roles in `app_metadata` |
| Database | Supabase Postgres + pgvector |
| Files | Supabase Storage, private bucket |
| LLM | OpenAI, structured JSON outputs |
| Embeddings | `text-embedding-3-small`, 1536 dims |

## Request lifecycle

| Status | Meaning |
|---|---|
| `active` | interview in progress; the only status that accepts messages |
| `submitted` | sent for review, summary being written |
| `completed` | reviewed, or intake finished — terminal |
| `escalated` | a red-flag rule matched and stopped the interview — terminal |
| `abandoned` | patient walked away from it to start something else — terminal |

## Running it locally

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # fill in the values
python scripts/apply_migrations.py
python -m uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:

```powershell
cd frontend
npm.cmd install
copy .env.example .env.local  # fill in the values
npm.cmd run dev
```

API docs at `http://127.0.0.1:8000/docs`.

### Environment

Backend `.env`:

```env
OPENAI_API_KEY=            # chat + embeddings
DATABASE_URL=              # Supabase Postgres URI, not the https:// project URL
SUPABASE_URL=              # https://<project>.supabase.co
SUPABASE_JWT_SECRET=       # HS256 verification
SUPABASE_SERVICE_ROLE_KEY= # backend only, never ship to a client
CORS_ORIGINS=              # comma-separated, no trailing slashes
```

Frontend `frontend/.env.local` — anon key only. The service-role key must never appear in frontend code:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

## API

| Endpoint | Auth | What it does |
|---|---|---|
| `GET /health` | — | liveness check |
| `POST /auth/signup` | — | creates a patient account; the server sets the role, never the caller |
| `POST /chat` | patient | send a message. Without `session_id` it resumes the active request or opens one. Returns `resumed`, `intake_complete`; closed requests return `409` |
| `POST /summary` | patient | the stored summary — written automatically when a request completes or escalates |
| `POST /upload` | patient | attach a text-based PDF (≤10 MB) to an owned active request; text is normalized to markdown, chunked, embedded |
| `GET /sessions/active` | patient | the active request and its messages, or `404` |
| `POST /sessions/{id}/abandon` | patient | drop an active request so a new one can start |
| `GET /doctor/patients` | doctor | patients assigned to this doctor |
| `GET /doctor/summaries` | doctor | their submitted requests, optionally filtered by `patient_id` |
| `GET /doctor/sessions/{id}` | doctor | full ordered transcript + summary |
| `POST /doctor/sessions/{id}/complete` | doctor | mark a reviewed request completed |

Doctors are scoped to assigned patients, and marking a request completed is their only write. Assignments are created deliberately by hand — there is no API for it:

```sql
insert into public.patient_doctor (patient_id, doctor_id)
values ('<patient-uuid>', '<doctor-uuid>');
```

For local testing, `backend/scripts/` has PowerShell helpers to create a doctor, fetch a bearer token, and assign patients by email. They read `SUPABASE_SERVICE_ROLE_KEY` from `.env` and are strictly admin-side.

## The summary

```json
{
  "chief_complaint": "...",
  "symptom_timeline": "...",
  "relevant_history": "...",
  "red_flags": [],
  "warning_signs_to_watch": [],
  "possible_directions": [],
  "suggested_questions_for_doctor": []
}
```

`red_flags` holds only what the patient actually reported, detected by rules — usually empty, which is the good outcome. `warning_signs_to_watch` holds things that would justify urgent care *if* they show up later. The two are deliberately never mixed, because a doctor scanning `red_flags` is asking one question: is anything alarming happening right now?

## Layout

```
backend/
  app/
    routers/        thin endpoints — chats, sessions, reports, doctors, auth, health
    services/       the real work: chat orchestration, LLM client, RAG,
                    safety rules, doctor reader, conversation store
    dependencies/   auth gate — JWT verification and role checks
    models/         Pydantic request/response shapes
  scripts/          migrations and trusted admin helpers
  supabase/
    migrations/     schema, RLS policies, pgvector, lifecycle
  tests/
frontend/
  src/
    features/       auth, patient workspace, doctor dashboard, landing
    lib/            API client, Supabase client, env validation, types
    components/     layout and feedback
```

Endpoints stay thin on purpose — all the logic lives in `services/`, which is why swapping the LLM provider mid-project touched exactly one file.

## Tests

```powershell
cd backend
python -m unittest discover -s tests -v
```

Frontend: `npm test` from `frontend/`.

Coverage worth knowing about: cross-patient isolation, JWT verification, red-flag negation, RAG chunk integrity and patient scoping, session lifecycle migrations, and the follow-up question builder.

## Limitations

- Educational use only. No real patient data, and not a medical device.
- Scanned PDFs are rejected — no OCR yet.
- Doctor–patient assignment is manual by design.
- Red-flag rules are English-only.
