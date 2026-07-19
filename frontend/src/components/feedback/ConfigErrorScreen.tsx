import { AlertTriangle } from "lucide-react";
import { FrontendConfigurationError } from "../../lib/env";
import "./ConfigErrorScreen.css";

type ConfigErrorScreenProps = {
  error: unknown;
};

export function ConfigErrorScreen({ error }: ConfigErrorScreenProps) {
  const message =
    error instanceof FrontendConfigurationError
      ? error.message
      : "The frontend could not start because configuration validation failed.";

  return (
    <main className="config-error-screen">
      <section className="config-error-panel" aria-labelledby="config-error-title">
        <AlertTriangle aria-hidden="true" size={28} />
        <div>
          <h1 id="config-error-title">Configuration required</h1>
          <p>{message}</p>
          <p>Create `frontend/.env.local` from `frontend/.env.example` and restart the dev server.</p>
        </div>
      </section>
    </main>
  );
}
