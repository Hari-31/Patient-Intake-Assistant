import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { describe, expect, it, vi } from "vitest";
import { getFreshAccessToken } from "./auth-session";


function session(accessToken: string, expiresAt: number): Session {
  return {
    access_token: accessToken,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: expiresAt,
    refresh_token: "refresh-token",
    user: {} as Session["user"],
  };
}


describe("getFreshAccessToken", () => {
  it("refreshes a token that is about to expire", async () => {
    const expiring = session("old-token", Math.floor(Date.now() / 1000) + 10);
    const refreshed = session("new-token", Math.floor(Date.now() / 1000) + 3600);
    const refreshSession = vi.fn().mockResolvedValue({
      data: { session: refreshed, user: refreshed.user },
      error: null,
    });
    const client = {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: expiring },
          error: null,
        }),
        refreshSession,
      },
    } as unknown as SupabaseClient;

    await expect(getFreshAccessToken(client)).resolves.toBe("new-token");
    expect(refreshSession).toHaveBeenCalledOnce();
  });

  it("returns a valid current token without refreshing", async () => {
    const current = session("current-token", Math.floor(Date.now() / 1000) + 3600);
    const refreshSession = vi.fn();
    const client = {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: current },
          error: null,
        }),
        refreshSession,
      },
    } as unknown as SupabaseClient;

    await expect(getFreshAccessToken(client)).resolves.toBe("current-token");
    expect(refreshSession).not.toHaveBeenCalled();
  });
});
