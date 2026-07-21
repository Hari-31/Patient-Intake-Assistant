import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./api-client";


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("ApiClient authorization handling", () => {
  it("attaches the Supabase access token to protected requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: "session-id",
          reply: "When did it start?",
          emergency_triggered: false,
          intake_complete: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient({
      baseUrl: "http://127.0.0.1:8000",
      getAccessToken: async () => "supabase-access-token",
    });

    await client.chat({ message: "Headache" });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer supabase-access-token",
    );
  });

  it("invokes the login redirect handler on a backend 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "invalid token" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const onUnauthorized = vi.fn();
    const client = new ApiClient({
      baseUrl: "http://127.0.0.1:8000",
      getAccessToken: async () => "expired-token",
      onUnauthorized,
    });

    await expect(client.listDoctorPatients()).rejects.toMatchObject({
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it.each([403, 404])(
    "normalizes %s without revealing resource existence",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ detail: "sensitive backend detail" }), {
            status,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      );
      const client = new ApiClient({
        baseUrl: "http://127.0.0.1:8000",
        getAccessToken: async () => "token",
      });

      await expect(client.listDoctorPatients()).rejects.toEqual(
        new ApiError(
          status,
          "The requested resource was not found or is unavailable.",
        ),
      );
    },
  );
});
