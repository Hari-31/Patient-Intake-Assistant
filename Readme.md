# Patient Intake Assistant

A chatbot that interviews patients before they see a doctor.

Patients describe their symptoms in a chat. The bot asks follow-up questions one at a time — onset, location, severity, history, medications, allergies — until the intake request is sent for doctor review and closed. A patient can have only one active request at a time. Once a request is closed for review, further chat messages and uploads are rejected, and changed symptoms or a new concern start a new intake. Doctors review assigned requests and expand the transcript.

This is an educational project. It is decision support, not a diagnostic tool, and it says so to every user.

## How it works

```
Patient chat (React)
        │  Supabase JWT
        ▼
FastAPI ── auth gate (verify token, read role from app_metadata)
        │
        ▼
Orchestrator ── every intake turn:
        1. save message
        2. deterministic red-flag check ── emergency? stop and escalate
        3. RAG: pull relevant chunks from uploaded reports (pgvector)
        4. LLM decides: ask next question, or close request for review
        │
        ▼
Structured summary + transcript ──► Doctor dashboard ──► mark completed
```

A few design decisions worth knowing:

- **The server decides when intake is complete, not the model.** The LLM returns per-topic coverage booleans; the request is marked `completed` only when all nine topics are answered, declined, or unknown.
- **One active request is enforced in the database.** A partial unique index prevents more than one `active` request for the same patient.
- **Red flags are rule-based, not LLM-based.** A deterministic checker (with negation handling, so "no chest pain" doesn't trigger) runs before the model on every message. The `red_flags` field in the summary is overwritten with these detected flags — the safety-critical output never depends on model judgement.
- **Report text is treated as data, never as instructions**, which closes off prompt injection through uploaded PDFs.
- **Isolation is enforced twice**: application queries scope by patient/doctor id, and Row Level Security policies back them up at the database.

## Stack

| | |
|---|---|
| Backend | FastAPI (Python) |
| Frontend | React + Vite + TypeScript |
| Auth | Supabase Auth (JWT, roles in `app_metadata`) |
| Database | Supabase Postgres + pgvector |
| Files | Supabase Storage (private bucket) |
| LLM | OpenAI (`OPENAI_MODEL`, default `gpt-5.6-terra`) |
| Embeddings | `text-embedding-3-small`, 1536 dims |

## Running it locally

Backend (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then fill in the values
python scripts/apply_migrations.py
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
copy .env.example .env.local  # then fill in the values
npm run dev
```

API docs live at `http://127.0.0.1:8000/docs`.

### Environment variables

Backend `.env`:

```env
OPENAI_API_KEY=            # chat + embeddings
DATABASE_URL=              # Supabase Postgres URI, not https://<project>.supabase.co
SUPABASE_URL=              # https://<project>.supabase.co
SUPABASE_JWT_SECRET=       # for HS256 token verification
SUPABASE_SERVICE_ROLE_KEY= # backend only. Never ship this to a client.
```

Frontend `frontend/.env.local` uses only the **anon** key — the service-role key must never appear anywhere in frontend code:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=    # or VITE_SUPABASE_PUBLISHABLE_KEY
```

## API

| Endpoint | Auth | What it does |
|---|---|---|
| `GET /health` | — | liveness check |
| `POST /auth/signup` | — | creates a patient account server-side; role is set by the server, never the caller |
| `POST /chat` | patient | send a message; without `session_id`, resumes the patient's active request or creates one. Response includes `resumed` and `intake_complete`; closed sessions return `409` |
| `POST /summary` | patient | structured summary for a completed intake (`409` if still incomplete, unless a red-flag escalation ended it) |
| `POST /upload` | patient | attach a text-based PDF report (≤10 MB) to an owned active request; extracted text is normalized to compact markdown before chunking and embedding |
| `GET /sessions/active` | patient | return the patient's active request and ordered messages, or `404` when none exists |
| `POST /sessions/{id}/abandon` | patient | close an active request as abandoned so a new intake can be started |
| `GET /doctor/patients` | doctor | patients assigned to this doctor |
| `GET /doctor/summaries` | doctor | assigned completed/escalated requests, optionally filtered by `patient_id`; summary may be null until generated |
| `GET /doctor/sessions/{id}` | doctor | full ordered transcript + summary, for verification |
| `POST /doctor/sessions/{id}/complete` | doctor | mark an assigned request completed |

Doctor access is scoped to assigned patients; the only doctor write operation is marking a reviewed request completed. Assignments are created manually (there is deliberately no API for it):

```sql
insert into public.patient_doctor (patient_id, doctor_id)
values ('<patient-uuid>', '<doctor-uuid>');
```

For local/admin testing, PowerShell helpers can create a doctor, copy their
bearer token, and assign existing patients by email:

```powershell
# This changes policy only for the current PowerShell process.
Set-ExecutionPolicy -Scope Process Bypass

# Edit the marked values at the top of each script, then run them.
# The doctor-token script prompts securely for the password.
.\scripts\get_doctor_token.ps1

# Assign the patient emails listed inside the assignment script.
.\scripts\assign_patients_to_doctor.ps1
```

Set `$ShowToken = $true` inside the first script only when the token must also
be printed.
These trusted admin scripts read `SUPABASE_SERVICE_ROLE_KEY` from `.env`; never
ship the scripts or that key to a browser/client environment.

## The summary shape

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

`red_flags` = alarming findings the patient actually reported (rule-detected, often empty — that's good news).
`warning_signs_to_watch` = symptoms that would warrant urgent care if they appear later. The two are never mixed.

## Project layout

```
app/
  routers/        thin endpoints (chats, reports, doctors, auth, health)
  services/       the actual logic: chat orchestration, LLM client,
                  RAG, safety rules, doctor reader, conversation store
  dependencies/   auth gate (JWT verification, role checks)
  models/         pydantic shapes
frontend/         React app (patient chat + doctor dashboard)
supabase/
  migrations/     schema, RLS policies, pgvector setup
tests/            backend tests
```

## Testing

```powershell
pytest
```

Frontend tests run with `npm test` from `frontend/`.

## Limitations

- Educational use only — no real patient data, and not a medical device.
- Scanned/image PDFs are rejected (no OCR yet).
- Doctor-patient assignment is manual by design.
- English only for the red-flag rules.
