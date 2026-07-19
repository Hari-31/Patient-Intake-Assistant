import { describe, expect, it } from "vitest";
import { FrontendConfigurationError, readAppEnv } from "./env";

describe("readAppEnv", () => {
  it("maps public Vite environment variables", () => {
    expect(
      readAppEnv({
        VITE_SUPABASE_URL: "https://example.supabase.co",
        VITE_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_example",
      } as unknown as ImportMetaEnv),
    ).toEqual({
      supabaseUrl: "https://example.supabase.co",
      supabasePublishableKey: "sb_publishable_example",
    });
  });

  it("throws a clear error for missing required values", () => {
    expect(() => readAppEnv({} as ImportMetaEnv)).toThrow(FrontendConfigurationError);
  });

  it("rejects backend-only secrets exposed to Vite", () => {
    expect(() =>
      readAppEnv({
        VITE_SUPABASE_URL: "https://example.supabase.co",
        VITE_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_example",
        VITE_OPENAI_API_KEY: "secret",
      } as unknown as ImportMetaEnv),
    ).toThrow(/backend-only secrets/);
  });
});
