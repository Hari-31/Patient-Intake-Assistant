# Supabase Deployment

This directory is the deployed backend for the application. The browser talks to
Supabase Auth and the `patient-intake-api` Edge Function; it no longer needs
the FastAPI server running.

The Edge Function owns patient account creation, role assignment, intake chat,
summary generation, report storage and embeddings, and doctor-scoped reads. It
uses the hosted function's secret key server-side and never exposes it to the
browser.

## Deploy To The Connected Project

From `backend/`, link the project once and apply every migration:

```sh
npx supabase login
npx supabase link --project-ref dhvocjpqdfljsjuxeapv
npx supabase db push
```

Set the OpenAI secrets used by chat, summaries, and PDF embeddings. Do not put
these values in any `VITE_*` variable:

```sh
npx supabase secrets set OPENAI_API_KEY=your-openai-key
npx supabase secrets set OPENAI_MODEL=gpt-4.1-mini
npx supabase secrets set OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Deploy the function:

```sh
npx supabase functions deploy patient-intake-api --no-verify-jwt
```

`verify_jwt` is disabled at the platform layer only because patient signup
must be public. The function validates the project's publishable key itself,
then verifies every non-signup user token and checks the immutable
`app_metadata.role` claim.

## Frontend Configuration

The frontend uses only these browser-safe values:

```env
VITE_SUPABASE_URL=https://dhvocjpqdfljsjuxeapv.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

The browser calls the function through
`supabase.functions.invoke("patient-intake-api")`; do not configure
`VITE_API_BASE_URL` to the Supabase URL.

## Operational Notes

- Apply all files in `migrations/` before deploying the function. The final
  migration adds the private report-vector lookup used for retrieval.
- The function automatically receives Supabase project credentials in the
  hosted runtime. Never set `SUPABASE_SECRET_KEY` or
  `SUPABASE_SERVICE_ROLE_KEY` in the frontend.
- Report text is extracted in the browser with PDF.js, then the Edge Function
  validates it, stores the original PDF privately, creates embeddings, and
  saves the chunks under the authenticated patient's session.
