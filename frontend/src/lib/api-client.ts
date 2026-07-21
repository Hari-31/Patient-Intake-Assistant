import type {
  ChatRequest,
  ChatResponse,
  ActiveSession,
  DoctorPatient,
  DoctorSessionCompletion,
  DoctorSessionTranscript,
  DoctorSummary,
  MedicalSummary,
  PatientSignupRequest,
  PatientSignupResponse,
  ReportUploadResponse,
} from "./types";

type ApiClientOptions = {
  baseUrl: string;
  getAccessToken: () => Promise<string | null>;
  onUnauthorized?: () => void | Promise<void>;
};

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  authenticated?: boolean;
  query?: Record<string, string | null | undefined>;
};

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
  private readonly baseUrl: string;
  private readonly getAccessToken: () => Promise<string | null>;
  private readonly onUnauthorized: () => void | Promise<void>;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl;
    this.getAccessToken = options.getAccessToken;
    this.onUnauthorized = options.onUnauthorized ?? (() => undefined);
  }

  signupPatient(payload: PatientSignupRequest): Promise<PatientSignupResponse> {
    return this.request("/auth/signup", {
      method: "POST",
      body: payload,
      authenticated: false,
    });
  }

  chat(payload: ChatRequest): Promise<ChatResponse> {
    return this.request("/chat", {
      method: "POST",
      body: payload,
    });
  }

  summarize(sessionId: string): Promise<MedicalSummary> {
    return this.request("/summary", {
      method: "POST",
      body: { session_id: sessionId },
    });
  }

  async getActiveSession(): Promise<ActiveSession | null> {
    try {
      return await this.request("/sessions/active");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return null;
      }
      throw error;
    }
  }

  abandonSession(sessionId: string): Promise<void> {
    return this.request(`/sessions/${sessionId}/abandon`, { method: "POST" });
  }

  listDoctorPatients(): Promise<DoctorPatient[]> {
    return this.request("/doctor/patients");
  }

  listDoctorSummaries(patientId?: string): Promise<DoctorSummary[]> {
    return this.request("/doctor/summaries", {
      query: { patient_id: patientId },
    });
  }

  getDoctorSession(sessionId: string): Promise<DoctorSessionTranscript> {
    return this.request(`/doctor/sessions/${sessionId}`);
  }

  completeDoctorSession(sessionId: string): Promise<DoctorSessionCompletion> {
    return this.request(`/doctor/sessions/${sessionId}/complete`, {
      method: "POST",
    });
  }

  async uploadReport(sessionId: string, file: File): Promise<ReportUploadResponse> {
    const token = await this.requireAccessToken();
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("file", file);

    const response = await fetch(`${this.baseUrl}/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: form,
    });

    return this.parseResponse(response);
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    Object.entries(options.query ?? {}).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      }
    });

    const headers = new Headers();
    headers.set("Accept", "application/json");

    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    if (options.authenticated !== false) {
      headers.set("Authorization", `Bearer ${await this.requireAccessToken()}`);
    }

    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });

    return this.parseResponse<T>(response);
  }

  private async requireAccessToken(): Promise<string> {
    const token = await this.getAccessToken();
    if (!token) {
      await this.onUnauthorized();
      throw new ApiError(401, "Your session has expired. Sign in again.");
    }
    return token;
  }

  private async parseResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
      if (response.status === 401) {
        await this.onUnauthorized();
        throw new ApiError(401, "Your session has expired. Sign in again.");
      }
      if (response.status === 403 || response.status === 404) {
        throw new ApiError(
          response.status,
          "The requested resource was not found or is unavailable.",
        );
      }
      throw new ApiError(response.status, normalizeErrorDetail(body));
    }

    return body as T;
  }
}

function normalizeErrorDetail(body: unknown): string {
  if (typeof body === "string") {
    return body || "The request failed.";
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return String(item);
        })
        .join(" ");
    }
  }
  return "The request failed.";
}
