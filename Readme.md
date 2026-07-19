# Patient Intake Assistant

Minimal FastAPI backend for an educational AI patient-intake assistant.

## Local setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Check it with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Copy `.env.example` to `.env` for local secrets. `.env` is ignored by Git;
deployment environments should inject the same values as environment variables.

For OpenAI-backed chat, set `OPENAI_API_KEY`. The default model is
`gpt-5.6-terra`; override it with `OPENAI_MODEL` if needed.

## Supabase Auth

Enable the desired login provider in **Supabase Dashboard → Authentication →
Providers**. Configure the backend with:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=
SUPABASE_SERVICE_ROLE_KEY=
```

The JWT secret and service-role key are backend-only secrets and must never be
included in frontend code. `POST /auth/signup` creates patient accounts through
the Supabase admin API and writes `patient` to `app_metadata.role`; callers
cannot choose a role. The patient's name is copied into `profiles` by a database
trigger. After signup, log in through Supabase Auth and send its access token to
the protected endpoints:

```http
Authorization: Bearer <supabase-access-token>
```

The API verifies the signature, issuer, audience, and expiration using either
the configured HS256 secret or Supabase's JWKS endpoint for current asymmetric
tokens. It then reads the application role only from `app_metadata.role` and
never authorizes from user-editable `user_metadata`.

## API

- `GET /health` checks API availability.
- `POST /auth/signup` accepts `{"email": "...", "password": "...", "name":
  "..."}` and creates a patient account server-side.
- `POST /chat` requires a patient bearer token, accepts `{"message": "..."}`
  for the first turn, and returns an owned server-generated UUID. Send that UUID
  as `session_id` on subsequent turns. The response includes
  `intake_complete`; it remains false until onset/duration, location, quality,
  0-10 severity, modifying factors, associated symptoms, relevant history and
  prior episodes, medications and supplements, and allergies are all answered,
  declined, or marked unknown.
- `POST /summary` accepts `{"session_id": "<uuid>"}` and returns the fixed
  medical intake summary shape. `red_flags` contains only alarming findings the
  patient actually reported; `warning_signs_to_watch` contains future symptoms
  that should prompt urgent care if they develop. It requires the owning
  patient's bearer token.
  Incomplete non-emergency intakes return `409`; deterministic red-flag
  escalations may be summarized immediately.
- `POST /upload` requires a patient bearer token and multipart form fields
  `session_id` plus a PDF `file`. The session must belong to that patient. The
  response includes the report UUID and number of embedded chunks.
- `GET /doctor/patients` requires a doctor bearer token and lists only patients
  assigned to that doctor.
- `GET /doctor/summaries` returns summaries for assigned patients. Pass an
  optional `patient_id` query parameter to filter the result.
- `GET /doctor/sessions/{session_id}` returns an assigned patient's ordered
  transcript and its current summary for side-by-side verification.

Doctor access is read-only. Create assignments manually with a trusted SQL or
admin workflow; never expose this operation to a patient client:

```sql
insert into public.patient_doctor (patient_id, doctor_id)
values ('<patient-auth-user-uuid>', '<doctor-auth-user-uuid>');
```

## Supabase Postgres persistence

Create a Supabase project, open its **Connect** panel, and copy the direct or
session-pooler Postgres connection string into `.env`:

```env
DATABASE_URL=postgresql://...
```

For a persistent FastAPI server, use the direct connection when IPv6 is
available; otherwise use the session pooler on port 5432. Apply the schema:

```powershell
python scripts/apply_migrations.py
```

The `sessions`, `messages`, `summaries`, and `audit_log` tables can then be
inspected from Supabase's Table Editor. Messages and summaries persist across
API restarts. A new message invalidates the previously generated summary so the
next `/summary` call reflects the latest transcript.

The Phase 3 migration creates `profiles`, reserves `doctor_id` for Phase 5,
rejects new sessions without an owner, and adds patient-only RLS policies using
`auth.jwt() -> 'app_metadata' ->> 'role'`. Legacy NULL-owner sessions remain
inaccessible. Once they have been deliberately assigned or removed, make the
column fully non-nullable:

```sql
alter table public.sessions validate constraint sessions_patient_id_required;
alter table public.sessions alter column patient_id set not null;
alter table public.sessions drop constraint sessions_patient_id_required;
```

The Phase 5 migration creates `patient_doctor` as the authoritative assignment
table and adds doctor-only SELECT policies for assigned profiles, sessions,
messages, and summaries. It grants no doctor write operations. The FastAPI
reader also joins every query through `patient_doctor` because the backend
database connection is privileged and bypasses RLS.

## Patient report RAG

Phase 4 creates a private `medical-reports` Storage bucket plus patient-owned
`reports` and `report_chunks` tables. PDF text is split into overlapping chunks,
embedded with `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`), and
stored in pgvector. Chat and summary retrieval always filters by both patient
and session before ranking chunks with cosine distance. Sessions without a
report skip the embedding call and retain the original chat behavior.

Upload from Swagger by authorizing with a patient token, opening `POST /upload`,
entering an owned session UUID, and selecting a text-based PDF. Scanned PDFs are
rejected until OCR support is added. The initial file limit is 10 MB.
