import type { SupabaseClient } from "@supabase/supabase-js";
import type {
  ChatRequest,
  ChatResponse,
  DoctorPatient,
  DoctorSessionTranscript,
  DoctorSummary,
  MedicalSummary,
  PatientSignupRequest,
  PatientSignupResponse,
  ReportUploadResponse,
} from "./types";

type ApiClientOptions = {
  supabaseClient: SupabaseClient;
};

type EdgeFunctionAction =
  | "signup_patient"
  | "chat"
  | "summary"
  | "doctor_patients"
  | "doctor_summaries"
  | "doctor_session"
  | "upload_report";

const functionName = "patient-intake-api";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class ApiClient {
  private readonly supabaseClient: SupabaseClient;

  constructor(options: ApiClientOptions) {
    this.supabaseClient = options.supabaseClient;
  }

  signupPatient(payload: PatientSignupRequest): Promise<PatientSignupResponse> {
    return this.invoke("signup_patient", payload);
  }

  chat(payload: ChatRequest): Promise<ChatResponse> {
    return this.invoke("chat", payload);
  }

  summarize(sessionId: string): Promise<MedicalSummary> {
    return this.invoke("summary", { session_id: sessionId });
  }

  listDoctorPatients(): Promise<DoctorPatient[]> {
    return this.invoke("doctor_patients", {});
  }

  listDoctorSummaries(patientId?: string): Promise<DoctorSummary[]> {
    return this.invoke("doctor_summaries", { patient_id: patientId ?? null });
  }

  getDoctorSession(sessionId: string): Promise<DoctorSessionTranscript> {
    return this.invoke("doctor_session", { session_id: sessionId });
  }

  async uploadReport(sessionId: string, file: File, extractedText: string): Promise<ReportUploadResponse> {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("file", file);
    form.append("extracted_text", extractedText);
    return this.invoke("upload_report", form);
  }

  private async invoke<T>(action: EdgeFunctionAction, payload: Record<string, unknown> | FormData): Promise<T> {
    const body = payload instanceof FormData ? withAction(payload, action) : { action, ...payload };
    const { data, error } = await this.supabaseClient.functions.invoke<unknown>(functionName, { body });

    if (error) {
      throw await toApiError(error);
    }

    return data as T;
  }
}

function withAction(form: FormData, action: EdgeFunctionAction): FormData {
  form.set("action", action);
  return form;
}

async function toApiError(error: Error & { context?: unknown }): Promise<ApiError> {
  const response = error.context;
  if (response instanceof Response) {
    const body = await response.clone().json().catch(() => null);
    return new ApiError(response.status, normalizeErrorDetail(body) || error.message);
  }
  return new ApiError(502, error.message || "The Supabase function could not be reached.");
}

function normalizeErrorDetail(body: unknown): string {
  if (typeof body === "string") {
    return body;
  }
  if (body && typeof body === "object") {
    for (const key of ["detail", "message", "error"]) {
      const value = (body as Record<string, unknown>)[key];
      if (typeof value === "string") {
        return value;
      }
    }
  }
  return "";
}
