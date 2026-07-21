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


function renderWorkspace(
  fetchMock: ReturnType<typeof vi.fn>,
  activeSession: object | null = null,
) {
  const routedFetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).endsWith("/sessions/active")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(
            activeSession ?? { detail: "No active intake was found." },
          ),
          {
            status: activeSession ? 200 : 404,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    }
    return fetchMock(input, init);
  });
  vi.stubGlobal("fetch", routedFetch);
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
    await waitFor(() => expect(textarea).toBeEnabled());
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
    await waitFor(() => expect(textarea).toBeEnabled());
    fireEvent.change(textarea, { target: { value: "I have chest pain" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Call emergency services now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Intake stopped" })).toBeDisabled();
    expect(textarea).toBeDisabled();
  });

  it("locks the composer after the backend marks intake complete", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: "session-1",
          reply: "Thank you. Your intake request has been sent for doctor review. If something changes or you have a new concern, start a new intake.",
          emergency_triggered: false,
          intake_complete: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWorkspace(fetchMock);
    await waitFor(() => expect(screen.getByRole("textbox")).toBeEnabled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "I cannot answer the remaining question." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Medical summary")).toBeInTheDocument();
    expect(screen.getByText("Intake sent for doctor review")).toBeInTheDocument();
    expect(screen.getByText(/this intake is closed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Intake closed" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start new intake" })).toBeEnabled();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Start new intake" }));
    expect(screen.getByText("No messages yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByRole("textbox")).toBeEnabled();
  });

  it("locks a restored submitted transcript and offers a new intake action", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    renderWorkspace(fetchMock, {
      session_id: "session-active",
      status: "submitted",
      messages: [
        {
          role: "patient",
          content: "I have a headache.",
          created_at: "2026-07-21T10:00:00Z",
        },
        {
          role: "assistant",
          content: "When did it begin?",
          created_at: "2026-07-21T10:00:01Z",
        },
      ],
    });

    expect(await screen.findByText("I have a headache.")).toBeInTheDocument();
    expect(screen.getByText("When did it begin?")).toBeInTheDocument();
    expect(screen.getByText("Sent for review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start new intake" })).toBeEnabled();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats a 409 chat response as a closed intake end state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: "This intake is closed. Start a new intake for a new concern.",
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWorkspace(fetchMock, {
      session_id: "session-complete",
      status: "active",
      messages: [
        {
          role: "patient",
          content: "I have a headache.",
          created_at: "2026-07-21T10:00:00Z",
        },
      ],
    });

    const textarea = await screen.findByRole("textbox");
    await waitFor(() => expect(textarea).toBeEnabled());
    fireEvent.change(textarea, { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Intake sent for doctor review")).toBeInTheDocument();
    expect(screen.queryByText("Message failed")).not.toBeInTheDocument();
    expect(screen.queryByText("ok")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start new intake" })).toBeEnabled();
  });
});
