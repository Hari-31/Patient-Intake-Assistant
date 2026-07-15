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

## API

- `GET /health` checks API availability.
- `POST /chat` accepts `{"message": "..."}` for the first turn and returns a
  server-generated UUID. Send that UUID as `session_id` on subsequent turns.
- `POST /summary` accepts `{"session_id": "<uuid>"}` and returns the fixed
  medical intake summary shape.

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
