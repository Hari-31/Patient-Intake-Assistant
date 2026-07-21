import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ClipboardList,
  Loader2,
  Maximize2,
  MessageSquareText,
  Minimize2,
  UserRoundSearch,
} from "lucide-react";
import { useApiClient } from "../../app/api-context";
import { Notice } from "../../components/feedback/Notice";
import { MedicalDisclaimer } from "../../components/feedback/MedicalDisclaimer";
import { formatDateTime, formatTime } from "../../lib/format";
import type { MedicalSummary } from "../../lib/types";

export function DoctorDashboard() {
  const apiClient = useApiClient();
  const queryClient = useQueryClient();
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [isTranscriptMinimized, setIsTranscriptMinimized] = useState(false);

  const patientsQuery = useQuery({
    queryKey: ["doctor", "patients"],
    queryFn: () => apiClient.listDoctorPatients(),
  });

  const summariesQuery = useQuery({
    queryKey: ["doctor", "summaries", selectedPatientId],
    queryFn: () => apiClient.listDoctorSummaries(selectedPatientId || undefined),
  });

  const sessionQuery = useQuery({
    queryKey: ["doctor", "session", selectedSessionId],
    queryFn: () => apiClient.getDoctorSession(selectedSessionId),
    enabled: Boolean(selectedSessionId),
  });

  const summaries = useMemo(() => summariesQuery.data ?? [], [summariesQuery.data]);
  const selectedSummary = useMemo(
    () => summaries.find((summary) => summary.session_id === selectedSessionId) ?? null,
    [selectedSessionId, summaries],
  );
  const selectedStatus = sessionQuery.data?.status ?? selectedSummary?.status ?? null;
  const canComplete = selectedStatus === "active" || selectedStatus === "submitted";

  const completeMutation = useMutation({
    mutationFn: (sessionId: string) => apiClient.completeDoctorSession(sessionId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["doctor", "summaries"] }),
        queryClient.invalidateQueries({ queryKey: ["doctor", "session", selectedSessionId] }),
      ]);
    },
  });

  useEffect(() => {
    if (summaries.length > 0 && !summaries.some((summary) => summary.session_id === selectedSessionId)) {
      setSelectedSessionId(summaries[0].session_id);
    }
    if (summaries.length === 0) {
      setSelectedSessionId("");
    }
  }, [selectedSessionId, summaries]);

  return (
    <section className="workspace doctor-workspace" aria-labelledby="doctor-workspace-title">
      <div className="workspace-heading">
        <div>
          <div className="eyebrow">Doctor workspace</div>
          <h1 id="doctor-workspace-title">Assigned patient review</h1>
        </div>
        <label className="filter-control">
          <span>Patient</span>
          <select value={selectedPatientId} onChange={(event) => setSelectedPatientId(event.target.value)} disabled={patientsQuery.isLoading}>
            <option value="">All assigned patients</option>
            {(patientsQuery.data ?? []).map((patient) => (
              <option key={patient.patient_id} value={patient.patient_id}>
                {patient.name ?? patient.patient_id}
              </option>
            ))}
          </select>
        </label>
      </div>

      {patientsQuery.error instanceof Error ? (
        <Notice tone="danger" title="Patients unavailable">
          {patientsQuery.error.message}
        </Notice>
      ) : null}
      {summariesQuery.error instanceof Error ? (
        <Notice tone="danger" title="Records unavailable">
          {summariesQuery.error.message}
        </Notice>
      ) : null}
      {completeMutation.error instanceof Error ? (
        <Notice tone="danger" title="Completion failed">
          {completeMutation.error.message}
        </Notice>
      ) : null}

      <div className="doctor-grid">
        <section className="panel review-list-panel" aria-label="Records">
          <div className="panel-header">
            <div>
              <h2>Records</h2>
              <p>{summaries.length} returned</p>
            </div>
          </div>
          {summariesQuery.isLoading ? (
            <LoadingInline label="Loading records" />
          ) : summaries.length === 0 ? (
            <div className="empty-state">
              <ClipboardList aria-hidden="true" size={24} />
              <span>No records found.</span>
            </div>
          ) : (
            <div className="summary-list">
              {summaries.map((summary) => (
                <button
                  key={summary.session_id}
                  type="button"
                  className={summary.session_id === selectedSessionId ? "summary-row active" : "summary-row"}
                  onClick={() => setSelectedSessionId(summary.session_id)}
                >
                  <span>{summary.patient_name ?? summary.patient_id}</span>
                  <strong>{summary.summary?.chief_complaint || "Request awaiting summary"}</strong>
                  <em>{statusLabel(summary.status)}</em>
                  <small>{formatDateTime(summary.updated_at)}</small>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel summary-detail-panel" aria-label="Session summary">
          <div className="panel-header summary-main-header">
            <div>
              <h2>Summary</h2>
              <p>{sessionQuery.data?.patient_name ?? selectedSummary?.patient_name ?? "No patient selected"}</p>
            </div>
            {selectedSessionId ? (
              <button
                className="secondary-button"
                type="button"
                disabled={!canComplete || completeMutation.isPending}
                onClick={() => completeMutation.mutate(selectedSessionId)}
              >
                <CheckCircle2 aria-hidden="true" size={16} />
                {selectedStatus === "completed"
                  ? "Completed"
                  : completeMutation.isPending
                    ? "Completing"
                    : "Mark completed"}
              </button>
            ) : null}
          </div>
          <div className="summary-detail-scroll">
            {sessionQuery.data?.summary ? (
              <DoctorSummaryView summary={sessionQuery.data.summary} />
            ) : selectedSummary?.summary ? (
              <DoctorSummaryView summary={selectedSummary.summary} />
            ) : (
              <div className="compact-empty">No summary generated yet. Review the transcript for details.</div>
            )}
          </div>
        </section>
      </div>

      <section
        className={`transcript-dock ${isTranscriptMinimized ? "minimized" : ""}`}
        aria-label="Transcript chat window"
      >
        {isTranscriptMinimized ? (
          <button
            className="transcript-minimized-trigger"
            type="button"
            aria-controls="doctor-transcript-window"
            aria-expanded={false}
            aria-label="Expand transcript"
            onClick={() => setIsTranscriptMinimized(false)}
          >
            <span className="transcript-dock-title compact">
              <MessageSquareText aria-hidden="true" size={18} />
              <span>
                <strong>Transcript</strong>
                <small>
                  {selectedSummary
                    ? `${selectedSummary.session_id} · ${statusLabel(selectedStatus)}`
                    : "No session selected"}
                </small>
              </span>
            </span>
            <span className="transcript-expand-label">
              Expand
              <Maximize2 aria-hidden="true" size={17} />
            </span>
          </button>
        ) : (
          <>
            <div className="transcript-dock-header">
              <div className="transcript-dock-title">
                <MessageSquareText aria-hidden="true" size={18} />
                <div>
                  <h2>Transcript</h2>
                  <p>
                    {selectedSummary
                      ? `${selectedSummary.session_id} · ${statusLabel(selectedStatus)}`
                      : "No session selected"}
                  </p>
                </div>
              </div>
              <button
                className="transcript-toggle-button"
                type="button"
                aria-controls="doctor-transcript-window"
                aria-expanded
                aria-label="Minimize transcript"
                onClick={() => setIsTranscriptMinimized(true)}
              >
                <Minimize2 aria-hidden="true" size={17} />
              </button>
            </div>
          <div className="transcript-dock-body" id="doctor-transcript-window">
            {sessionQuery.isFetching ? (
              <LoadingInline label="Loading transcript" />
            ) : sessionQuery.error instanceof Error ? (
              <Notice tone="danger" title="Transcript unavailable">
                {sessionQuery.error.message}
              </Notice>
            ) : sessionQuery.data ? (
              <div className="transcript-list">
                {sessionQuery.data.messages.map((message) => (
                  <article key={`${message.role}-${message.created_at}-${message.content.slice(0, 16)}`} className={`transcript-message ${message.role}`}>
                    <header>
                      <strong>{message.role}</strong>
                      <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
                    </header>
                    <p>{message.content}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <UserRoundSearch aria-hidden="true" size={24} />
                <span>Select a session.</span>
              </div>
            )}
          </div>
          </>
        )}
      </section>
    </section>
  );
}

function DoctorSummaryView({ summary }: { summary: MedicalSummary }) {
  return (
    <div className="summary-view doctor-summary-view">
      <MedicalDisclaimer />
      <SummaryBlock title="Chief complaint" values={[summary.chief_complaint]} />
      <SummaryBlock title="Timeline" values={[summary.symptom_timeline]} />
      <SummaryBlock title="Relevant history" values={[summary.relevant_history]} />
      <SummaryBlock title="Reported red flags" values={summary.red_flags} emphasis="danger" />
      <SummaryBlock title="Warning signs" values={summary.warning_signs_to_watch} />
      <SummaryBlock title="Possible directions" values={summary.possible_directions} />
      <SummaryBlock title="Questions" values={summary.suggested_questions_for_doctor} />
    </div>
  );
}

function SummaryBlock({
  title,
  values,
  emphasis,
}: {
  title: string;
  values: string[];
  emphasis?: "danger";
}) {
  const filteredValues = values.filter(Boolean);
  return (
    <section className={emphasis === "danger" && filteredValues.length > 0 ? "reported-red-flags has-findings" : undefined}>
      <h3>{title}</h3>
      {filteredValues.length > 0 ? (
        filteredValues.map((value) => <p key={value}>{value}</p>)
      ) : (
        <p>None returned.</p>
      )}
    </section>
  );
}

function LoadingInline({ label }: { label: string }) {
  return (
    <div className="loading-inline" role="status">
      <Loader2 className="spin" aria-hidden="true" size={18} />
      <span>{label}</span>
    </div>
  );
}

function statusLabel(status?: string | null) {
  if (status === "submitted") {
    return "Awaiting review";
  }
  if (status === "completed") {
    return "Completed";
  }
  if (status === "escalated") {
    return "Emergency flagged";
  }
  if (status === "active") {
    return "In progress";
  }
  return "Unknown status";
}
