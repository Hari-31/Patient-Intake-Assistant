import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, Loader2, UserRoundSearch } from "lucide-react";
import { useApiClient } from "../../app/api-context";
import { Notice } from "../../components/feedback/Notice";
import { formatDateTime } from "../../lib/format";
import type { DoctorSummary, MedicalSummary } from "../../lib/types";

export function DoctorDashboard() {
  const apiClient = useApiClient();
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");

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
        <Notice tone="danger" title="Summaries unavailable">
          {summariesQuery.error.message}
        </Notice>
      ) : null}

      <div className="doctor-grid">
        <section className="panel review-list-panel" aria-label="Summaries">
          <div className="panel-header">
            <div>
              <h2>Summaries</h2>
              <p>{summaries.length} returned</p>
            </div>
          </div>
          {summariesQuery.isLoading ? (
            <LoadingInline label="Loading summaries" />
          ) : summaries.length === 0 ? (
            <div className="empty-state">
              <ClipboardList aria-hidden="true" size={24} />
              <span>No summaries found.</span>
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
                  <strong>{summary.summary.chief_complaint || "No chief complaint"}</strong>
                  <small>{formatDateTime(summary.updated_at)}</small>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel transcript-panel" aria-label="Selected session">
          <div className="panel-header">
            <div>
              <h2>Transcript</h2>
              <p>{selectedSummary ? selectedSummary.session_id : "No session selected"}</p>
            </div>
          </div>
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
                    <span>{formatDateTime(message.created_at)}</span>
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
        </section>

        <section className="panel summary-detail-panel" aria-label="Session summary">
          <div className="panel-header">
            <div>
              <h2>Summary</h2>
              <p>{sessionQuery.data?.patient_name ?? selectedSummary?.patient_name ?? "No patient selected"}</p>
            </div>
          </div>
          {sessionQuery.data?.summary ? (
            <DoctorSummaryView summary={sessionQuery.data.summary} />
          ) : selectedSummary ? (
            <DoctorSummaryView summary={selectedSummary.summary} />
          ) : (
            <div className="compact-empty">No summary selected.</div>
          )}
        </section>
      </div>
    </section>
  );
}

function DoctorSummaryView({ summary }: { summary: MedicalSummary }) {
  return (
    <div className="summary-view compact">
      <SummaryBlock title="Chief complaint" values={[summary.chief_complaint]} />
      <SummaryBlock title="Timeline" values={[summary.symptom_timeline]} />
      <SummaryBlock title="Relevant history" values={[summary.relevant_history]} />
      <SummaryBlock title="Reported red flags" values={summary.red_flags} />
      <SummaryBlock title="Warning signs" values={summary.warning_signs_to_watch} />
      <SummaryBlock title="Questions" values={summary.suggested_questions_for_doctor} />
    </div>
  );
}

function SummaryBlock({ title, values }: { title: string; values: string[] }) {
  const filteredValues = values.filter(Boolean);
  return (
    <section>
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
