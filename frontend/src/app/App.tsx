import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import type { SupabaseClient } from "@supabase/supabase-js";
import { ApiProvider } from "./api-context";
import { queryClient } from "./query-client";
import type { ApiClient } from "../lib/api-client";
import { AuthPage } from "../features/auth/AuthPage";
import { AuthProvider } from "../features/auth/AuthProvider";
import { AppShell } from "../components/layout/AppShell";
import { ProtectedRoute, Unauthorized } from "../components/layout/ProtectedRoute";
import { PatientWorkspace } from "../features/patient/PatientWorkspace";
import { DoctorDashboard } from "../features/doctor/DoctorDashboard";
import { LandingPage } from "../features/landing/LandingPage";

type AppProps = {
  apiClient: ApiClient;
  supabaseClient: SupabaseClient;
};

export function App({ apiClient, supabaseClient }: AppProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ApiProvider apiClient={apiClient}>
        <AuthProvider supabaseClient={supabaseClient}>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route path="/" element={<LandingPage />} />
                <Route path="/auth" element={<AuthPage />} />
                <Route path="/unauthorized" element={<Unauthorized />} />
                <Route element={<ProtectedRoute role="patient" />}>
                  <Route path="/patient" element={<PatientWorkspace />} />
                </Route>
                <Route element={<ProtectedRoute role="doctor" />}>
                  <Route path="/doctor" element={<DoctorDashboard />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ApiProvider>
    </QueryClientProvider>
  );
}
