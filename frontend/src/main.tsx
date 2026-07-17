import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { ApiClient } from "./lib/api-client";
import { readAppEnv } from "./lib/env";
import { createSupabaseBrowserClient } from "./lib/supabase";
import { ConfigErrorScreen } from "./components/feedback/ConfigErrorScreen";
import "./styles.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element is missing.");
}

const root = createRoot(rootElement);

try {
  const env = readAppEnv();
  const supabaseClient = createSupabaseBrowserClient(env);
  const apiClient = new ApiClient({
    baseUrl: env.apiBaseUrl,
    getAccessToken: async () => {
      const { data } = await supabaseClient.auth.getSession();
      return data.session?.access_token ?? null;
    },
  });

  root.render(
    <StrictMode>
      <App apiClient={apiClient} supabaseClient={supabaseClient} />
    </StrictMode>,
  );
} catch (error) {
  root.render(
    <StrictMode>
      <ConfigErrorScreen error={error} />
    </StrictMode>,
  );
}
