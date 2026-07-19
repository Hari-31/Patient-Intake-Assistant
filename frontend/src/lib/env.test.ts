import { describe, expect, it } from "vitest";
import { FrontendConfigurationError, readAppEnv } from "./env";

describe("readAppEnv", () => {
  it("maps public Vite environment variables", () => {
    expect(
      readAppEnv({
        VITE_API_BASE_URL: "http://127.0.0.1:8000/",
        VITE_SUPABASE_URL: "https://example.supabase.co",
        VITE_SUPABASE_ANON_KEY: "public-anon-key",
      } as unknown as ImportMetaEnv),
    ).toEqual({
      apiBaseUrl: "http://127.0.0.1:8000",
      supabaseUrl: "https://example.supabase.co",
      supabaseAnonKey: "public-anon-key",
    });
  });

  it("throws a clear error for missing required values", () => {
    expect(() => readAppEnv({} as ImportMetaEnv)).toThrow(FrontendConfigurationError);
  });

  it("rejects backend-only secrets exposed to Vite", () => {
    expect(() =>
      readAppEnv({
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
        VITE_SUPABASE_URL: "https://example.supabase.co",
        VITE_SUPABASE_ANON_KEY: "public-anon-key",
        VITE_OPENAI_API_KEY: "secret",
      } as unknown as ImportMetaEnv),
    ).toThrow(/backend-only secrets/);
  });
});
