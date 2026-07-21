import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  FileText,
  Loader2,
  MessageSquarePlus,
  RefreshCcw,
  Send,
  Upload,
} from "lucide-react";
import { ApiError } from "../../lib/api-client";
import type { ChatResponse, MedicalSummary, ReportUploadResponse } from "../../lib/types";
import { useApiClient } from "../../app/api-context";
import { Notice } from "../../components/feedback/Notice";
import { MedicalDisclaimer } from "../../components/feedback/MedicalDisclaimer";
import { useAuth } from "../auth/AuthProvider";

type IntakeMessage = {
  id: string;
  role: "patient" | "assistant";
  content: string;
  emergency?: boolean;
};

const maxReportBytes = 10 * 1024 * 1024;

export function PatientWorkspace() {
  const apiClient = useApiClient();
  const auth = useAuth();
  const queryClient = useQueryClient();
  const patientId = auth.user?.id ?? "anonymous";
  const activeSessionQueryKey = ["patient", "active-session", patientId] as const;
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<IntakeMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [summary, setSummary] = useState<MedicalSummary | null>(null);
  const [intakeComplete, setIntakeComplete] = useState(false);
  const [uploadResult, setUploadResult] = useState<ReportUploadResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const sendInFlightRef = useRef(false);

  const activeSessionQuery = useQuery({
    queryKey: activeSessionQueryKey,
    queryFn: () => apiClient.getActiveSession(),
    retry: false,
  });

  useEffect(() => {
    const activeSession = activeSessionQuery.data;
    if (!activeSession) {
      return;
    }
    setSessionId(activeSession.session_id);
    setMessages(
      activeSession.messages
        .filter((message) => message.role === "patient" || message.role === "assistant")
        .map((message, index) => ({
          id: `${message.created_at}-${index}`,
          role: message.role as "patient" | "assistant",
          content: message.content,
        })),
    );
  }, [activeSessionQuery.data]);

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      apiClient.chat({
        message,
        session_id: sessionId || undefined,
      }),
  });

  const summaryMutation = useMutation({
    mutationFn: (activeSessionId: string) => apiClient.summarize(activeSessionId),
    onSuccess: setSummary,
  });

  const uploadMutation = useMutation({
    mutationFn: ({ activeSessionId, file }: { activeSessionId: string; file: File }) =>
      apiClient.uploadReport(activeSessionId, file),
    onSuccess: (response) => {
      setUploadResult(response);
      setSelectedFile(null);
    },
  });

  const abandonMutation = useMutation({
    mutationFn: (activeSessionId: string) =>
      apiClient.abandonSession(activeSessionId),
  });

  const emergencyActive = useMemo(
    () => messages.some((message) => message.role === "assistant" && message.emergency),
    [messages],
  );
  const intakeStopped = emergencyActive || intakeComplete;
  const canSummarize = Boolean(sessionId) && intakeStopped;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, chatMutation.isPending]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (
      !message ||
      chatMutation.isPending ||
      sendInFlightRef.current ||
      intakeStopped
    ) {
      return;
    }

    sendInFlightRef.current = true;
    setDraft("");
    setChatError(null);
    setSummary(null);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "patient", content: message },
    ]);

    try {
      const hadSession = Boolean(sessionId);
      const response = await chatMutation.mutateAsync(message);
      if (
        response.resumed &&
        !hadSession &&
        !response.intake_complete &&
        !response.emergency_triggered
      ) {
        const restored = await apiClient.getActiveSession();
        if (restored) {
          queryClient.setQueryData(activeSessionQueryKey, restored);
          setSessionId(restored.session_id);
          setMessages(
            restored.messages
              .filter(
                (item) => item.role === "patient" || item.role === "assistant",
              )
              .map((item, index) => ({
                id: `${item.created_at}-${index}`,
                role: item.role as "patient" | "assistant",
                content: item.content,
              })),
          );
          return;
        }
      }
      receiveChatResponse(response);
    } catch (error) {
      setChatError(toUserError(error));
      if (error instanceof ApiError && error.status === 404) {
        setSessionId("");
      }
    } finally {
      sendInFlightRef.current = false;
    }
  }

  function receiveChatResponse(response: ChatResponse) {
    setSessionId(response.session_id);
    setIntakeComplete(response.intake_complete);
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.reply,
        emergency: response.emergency_triggered,
      },
    ]);
  }

  async function startNewIntake() {
    setChatError(null);
    if (sessionId && !intakeStopped) {
      try {
        await abandonMutation.mutateAsync(sessionId);
      } catch (error) {
        setChatError(toUserError(error));
        return;
      }
    }
    setSessionId("");
    queryClient.setQueryData(activeSessionQueryKey, null);
    setMessages([]);
    setDraft("");
    setChatError(null);
    setSummary(null);
    setIntakeComplete(false);
    setUploadResult(null);
    setSelectedFile(null);
    setFileError(null);
  }

  function handleFile(file: File | null) {
    setFileError(null);
    setUploadResult(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setSelectedFile(null);
      setFileError("Select a PDF report.");
      return;
    }

    if (file.size > maxReportBytes) {
      setSelectedFile(null);
      setFileError("Select a PDF under 10 MB.");
      return;
    }

    setSelectedFile(file);
  }

  async function submitUpload() {
    if (!sessionId || !selectedFile) {
      return;
    }
    setFileError(null);
    try {
      await uploadMutation.mutateAsync({ activeSessionId: sessionId, file: selectedFile });
    } catch (error) {
      setFileError(toUserError(error));
    }
  }

  async function requestSummary() {
    if (!sessionId) {
      return;
    }
    try {
      await summaryMutation.mutateAsync(sessionId);
    } catch {
      return;
    }
  }

  return (
    <section className="workspace patient-workspace" aria-labelledby="patient-workspace-title">
      <div className="workspace-heading">
        <div>
          <div className="eyebrow">Patient workspace</div>
          <h1 id="patient-workspace-title">Intake conversation</h1>
        </div>
        <button className="secondary-button" type="button" onClick={startNewIntake} disabled={chatMutation.isPending || abandonMutation.isPending || activeSessionQuery.isPending}>
          <RefreshCcw aria-hidden="true" size={16} />
          {abandonMutation.isPending ? "Starting" : "Start new intake"}
        </button>
      </div>

      <MedicalDisclaimer />

      {activeSessionQuery.error ? (
        <Notice tone="danger" title="Could not restore intake">
          {toUserError(activeSessionQuery.error)}
        </Notice>
      ) : null}

      {intakeComplete ? (
        <Notice tone="success" title="Intake assessment complete">
          The doctor will see you soon. Please wait for further instructions.
          You may log out using the sign-out button at the top of the page.
        </Notice>
      ) : null}

      {emergencyActive ? (
        <Notice tone="danger" title="Emergency response">
          The assistant flagged urgent symptoms in this intake. Follow the backend response and seek emergency care when directed.
        </Notice>
      ) : null}

      <div className="patient-grid">
        <section className="panel chat-panel" aria-label="Conversation">
          <div className="panel-header">
            <div>
              <h2>Conversation</h2>
              <p>{sessionId ? "Active intake" : "Start by describing your concern"}</p>
            </div>
          </div>
          <div className="message-list" aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-state">
                <MessageSquarePlus aria-hidden="true" size={24} />
                <span>No messages yet.</span>
              </div>
            ) : (
              messages.map((message) => (
                <article key={message.id} className={`message-bubble ${message.role} ${message.emergency ? "emergency" : ""}`}>
                  {message.emergency ? <AlertTriangle aria-hidden="true" size={16} /> : null}
                  <p>{message.content}</p>
                </article>
              ))
            )}
            {chatMutation.isPending ? (
              <div className="message-bubble assistant pending">
                <Loader2 className="spin" aria-hidden="true" size={16} />
                <p>Responding</p>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          {chatError ? (
            <Notice tone="danger" title="Message failed">
              {chatError}
            </Notice>
          ) : null}

          <form className="chat-composer" onSubmit={handleSend}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={
                emergencyActive
                  ? "This intake stopped after an emergency escalation"
                  : intakeComplete
                    ? "This intake is complete"
                  : "Describe symptoms, timeline, medications, or concerns"
              }
              rows={3}
              maxLength={10_000}
              disabled={intakeStopped || chatMutation.isPending || activeSessionQuery.isPending}
            />
            <button
              className="primary-button send-button"
              type="submit"
              disabled={!draft.trim() || chatMutation.isPending || intakeStopped || activeSessionQuery.isPending}
            >
              <Send aria-hidden="true" size={17} />
              {emergencyActive
                ? "Intake stopped"
                : intakeComplete
                  ? "Intake complete"
                  : "Send"}
            </button>
          </form>
        </section>

        <aside className="side-stack" aria-label="Intake tools">
          {canSummarize ? <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Medical summary</h2>
                <p>{summary ? "Generated from current transcript" : "Unavailable until a session exists"}</p>
              </div>
              <button className="secondary-button" type="button" disabled={summaryMutation.isPending} onClick={requestSummary}>
                <FileText aria-hidden="true" size={16} />
                {summaryMutation.isPending ? "Generating" : "Generate"}
              </button>
            </div>
            {summaryMutation.error instanceof Error ? (
              <Notice tone="danger" title="Summary failed">
                {summaryMutation.error.message}
              </Notice>
            ) : null}
            {summary ? <SummaryView summary={summary} /> : <CompactEmpty label="No summary generated." />}
          </section> : null}

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>PDF report</h2>
                <p>{uploadResult ? `${uploadResult.filename} is ready` : "Attach to the active intake"}</p>
              </div>
            </div>
            <div
              className={`drop-zone ${isDragging ? "dragging" : ""} ${!sessionId || intakeStopped ? "disabled" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (sessionId && !intakeStopped) {
                  setIsDragging(true);
                }
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                if (sessionId && !intakeStopped) {
                  handleFile(event.dataTransfer.files.item(0));
                }
              }}
            >
              <Upload aria-hidden="true" size={22} />
              <label>
                <span>{selectedFile ? selectedFile.name : "Select PDF"}</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={!sessionId || intakeStopped}
                  onChange={(event) => handleFile(event.target.files?.item(0) ?? null)}
                />
              </label>
            </div>
            {fileError ? (
              <Notice tone="danger" title="Upload blocked">
                {fileError}
              </Notice>
            ) : null}
            {uploadResult ? (
              <Notice tone="success" title="Report uploaded">
                {uploadResult.filename}
              </Notice>
            ) : null}
            <button className="primary-button full-width" type="button" disabled={!sessionId || !selectedFile || uploadMutation.isPending || intakeStopped} onClick={submitUpload}>
              <Upload aria-hidden="true" size={17} />
              {uploadMutation.isPending ? "Uploading" : "Upload report"}
            </button>
          </section>
        </aside>
      </div>
    </section>
  );
}

function SummaryView({ summary }: { summary: MedicalSummary }) {
  return (
    <div className="summary-view">
      <MedicalDisclaimer />
      <SummaryText title="Chief complaint" value={summary.chief_complaint} />
      <SummaryText title="Timeline" value={summary.symptom_timeline} />
      <SummaryText title="Relevant history" value={summary.relevant_history} />
      <SummaryList
        title="Reported red flags"
        values={summary.red_flags}
        empty="None reported."
        emphasis="danger"
      />
      <SummaryList title="Warning signs" values={summary.warning_signs_to_watch} empty="None returned." />
      <SummaryList title="Possible directions" values={summary.possible_directions} empty="None returned." />
      <SummaryList title="Questions for doctor" values={summary.suggested_questions_for_doctor} empty="None returned." />
    </div>
  );
}

function SummaryText({ title, value }: { title: string; value: string }) {
  return (
    <section>
      <h3>{title}</h3>
      <p>{value || "Not provided."}</p>
    </section>
  );
}

function SummaryList({
  title,
  values,
  empty,
  emphasis,
}: {
  title: string;
  values: string[];
  empty: string;
  emphasis?: "danger";
}) {
  return (
    <section className={emphasis === "danger" && values.length > 0 ? "reported-red-flags has-findings" : undefined}>
      <h3>{title}</h3>
      {values.length > 0 ? (
        <ul>
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </section>
  );
}

function CompactEmpty({ label }: { label: string }) {
  return <div className="compact-empty">{label}</div>;
}

function toUserError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The request failed.";
}
