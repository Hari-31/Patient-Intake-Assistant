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
