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

For Gemini-backed chat, set `GEMINI_API_KEY`. The default model is the stable
`gemini-3.5-flash`; override it with `GEMINI_MODEL` if needed. Existing local
setups using `LLM_API_KEY` continue to work as a temporary migration fallback.

## API

- `GET /health` checks API availability.
- `POST /chat` accepts `{"session_id": "demo", "message": "..."}` and asks one
  adaptive follow-up question. Conversations are held in process memory.
- `POST /summary` accepts `{"session_id": "demo"}` and returns the fixed medical
  intake summary shape.

In-memory conversations are cleared whenever the server restarts and are not
shared between multiple server processes.
