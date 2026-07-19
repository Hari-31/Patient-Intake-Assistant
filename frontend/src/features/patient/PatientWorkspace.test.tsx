import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../../app/api-context";
import { ApiClient } from "../../lib/api-client";
import { AuthProvider } from "../auth/AuthProvider";
import { PatientWorkspace } from "./PatientWorkspace";


afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});


function patientSession(): Session {
  return {
    access_token: "patient-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "refresh-token",
    user: {
      id: "patient-1",
      app_metadata: { role: "patient" },
    } as unknown as Session["user"],
  };
}


function renderWorkspace(fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  const session = patientSession();
  const supabaseClient = {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session }, error: null }),
      onAuthStateChange: vi.fn().mockReturnValue({
        data: { subscription: { unsubscribe: vi.fn() } },
      }),
    },
  } as unknown as SupabaseClient;
  const apiClient = new ApiClient({
    baseUrl: "http://127.0.0.1:8000",
    getAccessToken: async () => session.access_token,
  });
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiProvider apiClient={apiClient}>
        <AuthProvider supabaseClient={supabaseClient}>
          <PatientWorkspace />
        </AuthProvider>
      </ApiProvider>
    </QueryClientProvider>,
  );
}


describe("PatientWorkspace safety", () => {
  it("shows the educational disclaimer before chat begins", () => {
    renderWorkspace(vi.fn());

    expect(screen.getByText("Educational intake tool")).toBeInTheDocument();
    expect(screen.getByText(/not medical advice or a diagnosis/i)).toBeInTheDocument();
    expect(screen.queryByText("Medical summary")).not.toBeInTheDocument();
  });

  it("uses a synchronous lock to prevent duplicate submissions", async () => {
    const fetchMock = vi.fn().mockImplementation(
      () => new Promise<Response>(() => undefined),
    );
    renderWorkspace(fetchMock);
    const textarea = screen.getByRole("textbox");
    const form = screen.getByRole("button", { name: "Send" }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(textarea, { target: { value: "My head hurts" } });

    fireEvent.submit(form!);
    fireEvent.submit(form!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it("stops the intake after an emergency escalation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: "session-1",
          reply: "Call emergency services now.",
          emergency_triggered: true,
          intake_complete: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWorkspace(fetchMock);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "I have chest pain" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Call emergency services now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Intake stopped" })).toBeDisabled();
    expect(textarea).toBeDisabled();
  });

  it("offers a summary only after the backend marks intake complete", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: "session-1",
          reply: "Thank you. Your intake is complete, and the doctor will see you soon.",
          emergency_triggered: false,
          intake_complete: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWorkspace(fetchMock);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "I cannot answer the remaining question." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Medical summary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Intake complete" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate" })).toBeEnabled();
  });
});
