import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { AppEnv } from "./env";

export function createSupabaseBrowserClient(env: AppEnv): SupabaseClient {
  return createClient(env.supabaseUrl, env.supabaseAnonKey, {
    auth: {
      autoRefreshToken: true,
      detectSessionInUrl: true,
      persistSession: true,
    },
  });
}
