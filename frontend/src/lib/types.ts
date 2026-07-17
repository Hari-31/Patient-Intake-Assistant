export type UserRole = "patient" | "doctor";

export type PatientSignupRequest = {
  email: string;
  password: string;
  name: string;
};

export type PatientSignupResponse = {
  user_id: string;
  email: string;
  role: UserRole;
};

export type ChatRequest = {
  session_id?: string;
  message: string;
};

export type ChatResponse = {
  session_id: string;
  reply: string;
  emergency_triggered: boolean;
};

export type MedicalSummary = {
  chief_complaint: string;
  symptom_timeline: string;
  relevant_history: string;
  red_flags: string[];
  warning_signs_to_watch: string[];
  possible_directions: string[];
  suggested_questions_for_doctor: string[];
};

export type ReportUploadResponse = {
  report_id: string;
  session_id: string;
  filename: string;
  chunk_count: number;
};

export type DoctorPatient = {
  patient_id: string;
  name: string | null;
  assigned_at: string;
};

export type DoctorSummary = {
  session_id: string;
  patient_id: string;
  patient_name: string | null;
  summary: MedicalSummary;
  created_at: string;
  updated_at: string;
};

export type TranscriptMessage = {
  role: string;
  content: string;
  created_at: string;
};

export type DoctorSessionTranscript = {
  session_id: string;
  patient_id: string;
  patient_name: string | null;
  created_at: string;
  messages: TranscriptMessage[];
  summary: MedicalSummary | null;
};
