import type { SupabaseClient } from "@supabase/supabase-js";


const refreshWindowMilliseconds = 60_000;


export async function getFreshAccessToken(
  supabaseClient: SupabaseClient,
): Promise<string | null> {
  const { data, error } = await supabaseClient.auth.getSession();
  if (error || !data.session) {
    return null;
  }

  const expiresAt = data.session.expires_at ?? 0;
  if (expiresAt * 1000 <= Date.now() + refreshWindowMilliseconds) {
    const refreshed = await supabaseClient.auth.refreshSession();
    return refreshed.data.session?.access_token ?? null;
  }

  return data.session.access_token;
}
