import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../../app/api-context";
import { ApiClient } from "../../lib/api-client";
import { DoctorDashboard } from "./DoctorDashboard";


afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});


const summary = {
  chief_complaint: "Severe headache",
  symptom_timeline: "Started this morning",
  relevant_history: "No relevant history",
  red_flags: ["Worst-ever sudden headache"],
  warning_signs_to_watch: ["New weakness"],
  possible_directions: ["Urgent clinical assessment"],
  suggested_questions_for_doctor: ["Do I need imaging?"],
};


function renderDashboard() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((input: URL | RequestInfo) => {
      const url = String(input);
      let body: unknown = [];
      if (url.includes("/doctor/patients")) {
        body = [{ patient_id: "patient-1", name: "Pat One", assigned_at: new Date().toISOString() }];
      } else if (url.includes("/doctor/summaries")) {
        body = [{
          session_id: "session-1",
          patient_id: "patient-1",
          patient_name: "Pat One",
          status: "submitted",
          summary,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }];
      } else if (url.includes("/doctor/sessions/session-1")) {
        body = {
          session_id: "session-1",
          patient_id: "patient-1",
          patient_name: "Pat One",
          status: "submitted",
          created_at: new Date().toISOString(),
          messages: [{ role: "patient", content: "It began suddenly.", created_at: new Date().toISOString() }],
          summary,
        };
      }
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
  const client = new ApiClient({
    baseUrl: "http://127.0.0.1:8000",
    getAccessToken: async () => "doctor-token",
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ApiProvider apiClient={client}>
        <DoctorDashboard />
      </ApiProvider>
    </QueryClientProvider>,
  );
}


describe("DoctorDashboard", () => {
  it("shows a transcript, completion action, and every summary field", async () => {
    renderDashboard();

    expect(await screen.findByText("It began suddenly.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Records" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Summaries" })).not.toBeInTheDocument();
    expect(screen.getByText("Urgent clinical assessment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark completed" })).toBeInTheDocument();
    expect(screen.getByText("Worst-ever sudden headache").closest("section")).toHaveClass(
      "reported-red-flags",
    );
    expect(screen.getByText("Educational intake tool")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit|delete/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Minimize transcript" }));
    expect(screen.queryByText("It began suddenly.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand transcript" }));
    expect(screen.getByText("It began suddenly.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Minimize transcript" })).toBeInTheDocument();
  });
});
