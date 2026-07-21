export type AppEnv = {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
};

const requiredEnv = {
  VITE_API_BASE_URL: "apiBaseUrl",
  VITE_SUPABASE_URL: "supabaseUrl",
} as const;

const supabaseKeyEnvNames = [
  "VITE_SUPABASE_ANON_KEY",
  "VITE_SUPABASE_PUBLISHABLE_KEY",
] as const;

const forbiddenSecretNames = [
  "SUPABASE_SERVICE_ROLE_KEY",
  "SUPABASE_JWT_SECRET",
  "DATABASE_URL",
  "OPENAI_API_KEY",
];

export class FrontendConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FrontendConfigurationError";
  }
}

export function readAppEnv(metaEnv: ImportMetaEnv = import.meta.env): AppEnv {
  const missing = Object.keys(requiredEnv).filter((key) => !metaEnv[key]);
  const supabaseKey = supabaseKeyEnvNames
    .map((key) => metaEnv[key])
    .find((value): value is string => Boolean(value));
  const exposedSecrets = Object.keys(metaEnv).filter((key) =>
    forbiddenSecretNames.some((secretName) => key.includes(secretName)),
  );
  if (!supabaseKey) {
    missing.push("VITE_SUPABASE_ANON_KEY or VITE_SUPABASE_PUBLISHABLE_KEY");
  }

  if (missing.length > 0 || exposedSecrets.length > 0) {
    const messages = [];
    if (missing.length > 0) {
      messages.push(`Missing frontend environment variables: ${missing.join(", ")}`);
    }
    if (exposedSecrets.length > 0) {
      messages.push(`Remove backend-only secrets from frontend env: ${exposedSecrets.join(", ")}`);
    }
    throw new FrontendConfigurationError(messages.join(". "));
  }
  if (!supabaseKey) {
    throw new FrontendConfigurationError(
      "Missing frontend environment variables: VITE_SUPABASE_ANON_KEY or VITE_SUPABASE_PUBLISHABLE_KEY",
    );
  }

  return {
    apiBaseUrl: metaEnv.VITE_API_BASE_URL.replace(/\/+$/, ""),
    supabaseUrl: metaEnv.VITE_SUPABASE_URL,
    supabaseAnonKey: supabaseKey,
  };
}
