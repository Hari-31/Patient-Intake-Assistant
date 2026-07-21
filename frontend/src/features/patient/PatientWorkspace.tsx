import { type FormEvent, type KeyboardEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  FileText,
  Loader2,
  MessageSquarePlus,
  Send,
  Upload,
} from "lucide-react";
import { ApiError } from "../../lib/api-client";
import { formatTime } from "../../lib/format";
import type { ChatResponse, MedicalSummary, ReportUploadResponse, SessionStatus } from "../../lib/types";
import { useApiClient } from "../../app/api-context";
import { Notice } from "../../components/feedback/Notice";
import { MedicalDisclaimer } from "../../components/feedback/MedicalDisclaimer";
import { useAuth } from "../auth/AuthProvider";

type IntakeMessage = {
  id: string;
  role: "patient" | "assistant";
  content: string;
  createdAt?: string;
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
  const [activeSessionStatus, setActiveSessionStatus] = useState<SessionStatus | null>(null);
  const [messages, setMessages] = useState<IntakeMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [summary, setSummary] = useState<MedicalSummary | null>(null);
  const [intakeComplete, setIntakeComplete] = useState(false);
  const [uploadResult, setUploadResult] = useState<ReportUploadResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const draftTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const sendInFlightRef = useRef(false);
  const shouldRefocusComposerRef = useRef(false);
  const [composerFocusRequest, setComposerFocusRequest] = useState(0);

  const activeSessionQuery = useQuery({
    queryKey: activeSessionQueryKey,
    queryFn: () => apiClient.getActiveSession(),
    retry: false,
  });

  useEffect(() => {
    if (activeSessionQuery.isPending) {
      return;
    }
    const activeSession = activeSessionQuery.data;
    if (!activeSession) {
      setSessionId("");
      setActiveSessionStatus(null);
      setMessages([]);
      setIntakeComplete(false);
      return;
    }
    setSessionId(activeSession.session_id);
    setActiveSessionStatus(activeSession.status);
    setIntakeComplete(isReviewStatus(activeSession.status));
    setMessages(
      activeSession.messages
        .filter((message) => message.role === "patient" || message.role === "assistant")
        .map((message, index) => ({
          id: `${message.created_at}-${index}`,
          role: message.role as "patient" | "assistant",
          content: message.content,
          createdAt: message.created_at,
        })),
    );
  }, [activeSessionQuery.data, activeSessionQuery.isPending]);

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
      setSummary(null);
      setSelectedFile(null);
    },
  });

  const emergencyActive = useMemo(
    () => messages.some((message) => message.role === "assistant" && message.emergency),
    [messages],
  );
  const requestSubmitted = intakeComplete || isReviewStatus(activeSessionStatus);
  const intakeStopped =
    emergencyActive ||
    requestSubmitted ||
    activeSessionStatus === "escalated" ||
    activeSessionStatus === "abandoned";
  const canSummarize = Boolean(sessionId) && (requestSubmitted || emergencyActive);
  const uploadDisabled = !sessionId || intakeStopped;

  useEffect(() => {
    const messageList = messageListRef.current;
    if (!messageList) {
      return;
    }
    messageList.scrollTop = messageList.scrollHeight;
  }, [messages, chatMutation.isPending]);

  useLayoutEffect(() => {
    const textarea = draftTextareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = "0px";
    const height = Math.max(44, Math.min(textarea.scrollHeight || 44, 144));
    textarea.style.height = `${height}px`;
    textarea.style.overflowY = textarea.scrollHeight > height ? "auto" : "hidden";
  }, [draft]);

  useEffect(() => {
    if (!shouldRefocusComposerRef.current) {
      return;
    }
    if (chatMutation.isPending || activeSessionQuery.isPending) {
      return;
    }
    if (intakeStopped) {
      shouldRefocusComposerRef.current = false;
      return;
    }

    const textarea = draftTextareaRef.current;
    if (!textarea || textarea.disabled) {
      return;
    }

    textarea.focus({ preventScroll: true });
    const cursorPosition = textarea.value.length;
    textarea.setSelectionRange(cursorPosition, cursorPosition);
    shouldRefocusComposerRef.current = false;
  }, [activeSessionQuery.isPending, chatMutation.isPending, composerFocusRequest, draft, intakeStopped]);

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

    const optimisticMessage: IntakeMessage = {
      id: crypto.randomUUID(),
      role: "patient",
      content: message,
      createdAt: new Date().toISOString(),
    };
    sendInFlightRef.current = true;
    setDraft("");
    setChatError(null);
    setSummary(null);
    setMessages((current) => [...current, optimisticMessage]);

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
                  createdAt: item.created_at,
                })),
          );
          return;
        }
      }
      receiveChatResponse(response);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setMessages((current) =>
          current.filter((item) => item.id !== optimisticMessage.id),
        );
        markIntakeClosed();
        return;
      }
      setChatError(toUserError(error));
      if (error instanceof ApiError && error.status === 404) {
        setSessionId("");
      }
    } finally {
      sendInFlightRef.current = false;
      requestComposerFocus();
    }
  }

  function requestComposerFocus() {
    shouldRefocusComposerRef.current = true;
    setComposerFocusRequest((request) => request + 1);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.nativeEvent.isComposing
    ) {
      return;
    }

    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  function receiveChatResponse(response: ChatResponse) {
    setSessionId(response.session_id);
    setIntakeComplete(response.intake_complete);
    setActiveSessionStatus(
      response.emergency_triggered
        ? "escalated"
        : response.intake_complete
          ? "completed"
          : "active",
    );
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.reply,
        createdAt: new Date().toISOString(),
        emergency: response.emergency_triggered,
      },
    ]);
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
      if (error instanceof ApiError && error.status === 409) {
        markIntakeClosed();
        setFileError(null);
        return;
      }
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

  async function startNewIntake() {
    const shouldAbandonCurrent =
      Boolean(sessionId) &&
      activeSessionStatus === "active" &&
      !intakeComplete &&
      !emergencyActive;

    if (shouldAbandonCurrent) {
      try {
        await apiClient.abandonSession(sessionId);
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 409)) {
          setChatError(toUserError(error));
          return;
        }
      }
    }

    resetIntake();
  }

  function markIntakeClosed() {
    setChatError(null);
    setFileError(null);
    setSelectedFile(null);
    setIntakeComplete(true);
    setActiveSessionStatus("completed");
  }

  function resetIntake() {
    setSessionId("");
    setActiveSessionStatus(null);
    setMessages([]);
    setDraft("");
    setChatError(null);
    setSummary(null);
    setIntakeComplete(false);
    setUploadResult(null);
    setSelectedFile(null);
    setFileError(null);
    chatMutation.reset();
    summaryMutation.reset();
    uploadMutation.reset();
    queryClient.setQueryData(activeSessionQueryKey, null);
  }

  return (
    <section
      className="workspace patient-workspace"
      aria-labelledby="patient-workspace-title"
    >
      <div className="workspace-heading">
        <div>
          <div className="eyebrow">Patient workspace</div>
          <h1 id="patient-workspace-title">Current request</h1>
        </div>
        <div
          className="request-status-pill"
          data-status={activeSessionStatus ?? "new"}
        >
          {statusLabel(
            activeSessionStatus,
            Boolean(sessionId),
            requestSubmitted,
          )}
        </div>
      </div>

      <MedicalDisclaimer />

      {activeSessionQuery.error ? (
        <Notice tone="danger" title="Could not restore intake">
          {toUserError(activeSessionQuery.error)}
        </Notice>
      ) : null}

      {intakeComplete ? (
        <Notice tone="success" title="Intake sent for doctor review">
          <div className="notice-action-row">
            <span>
              This intake is closed. Start a new intake if something changes or
              you have a new concern.
            </span>
            <button
              className="secondary-button"
              type="button"
              onClick={startNewIntake}
            >
              <MessageSquarePlus aria-hidden="true" size={16} />
              Start new intake
            </button>
          </div>
        </Notice>
      ) : null}

      {emergencyActive ? (
        <Notice tone="danger" title="Emergency response">
          The assistant flagged urgent symptoms in this intake. Follow the
          backend response and seek emergency care when directed.
        </Notice>
      ) : null}

      <div className="patient-grid">
        <section className="panel chat-panel" aria-label="Conversation">
          <div className="panel-header">
            <div>
              <h2>Conversation</h2>
              <p>
                {requestSubmitted
                  ? "Sent for doctor review"
                  : sessionId
                    ? "Request in progress"
                    : "Start by describing your concern"}
              </p>
            </div>
          </div>
          <div className="message-list" ref={messageListRef} aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-state">
                <MessageSquarePlus aria-hidden="true" size={24} />
                <span>No messages yet.</span>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={`message-bubble ${message.role} ${message.emergency ? "emergency" : ""}`}
                >
                  <header className="message-meta">
                    <span>
                      {message.role === "patient" ? "You" : "Assistant"}
                    </span>
                    {message.createdAt ? (
                      <time dateTime={message.createdAt}>
                        {formatTime(message.createdAt)}
                      </time>
                    ) : null}
                  </header>
                  <div
                    className={
                      message.emergency
                        ? "message-content with-alert"
                        : "message-content"
                    }
                  >
                    {message.emergency ? (
                      <AlertTriangle aria-hidden="true" size={16} />
                    ) : null}
                    <p>{message.content}</p>
                  </div>
                </article>
              ))
            )}
            {chatMutation.isPending ? (
              <div className="message-bubble assistant pending">
                <Loader2 className="spin" aria-hidden="true" size={16} />
                <p>Responding</p>
              </div>
            ) : null}
          </div>

          {chatError ? (
            <Notice tone="danger" title="Message failed">
              {chatError}
            </Notice>
          ) : null}

          <form className="chat-composer" onSubmit={handleSend}>
            <textarea
              ref={draftTextareaRef}
              aria-label="Message details"
              className="chat-textarea"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder={
                emergencyActive
                  ? "This intake stopped after an emergency escalation"
                  : intakeStopped
                    ? "This intake is closed"
                    : "Describe symptoms, timeline, medications, or concerns"
              }
              rows={1}
              maxLength={10_000}
              disabled={
                intakeStopped ||
                chatMutation.isPending ||
                activeSessionQuery.isPending
              }
            />
            <button
              className="primary-button send-button"
              type="submit"
              disabled={
                !draft.trim() ||
                chatMutation.isPending ||
                intakeStopped ||
                activeSessionQuery.isPending
              }
            >
              <Send aria-hidden="true" size={17} />
              {emergencyActive
                ? "Intake stopped"
                : intakeStopped
                  ? "Intake closed"
                  : "Send"}
            </button>
          </form>
        </section>

        <aside className="side-stack" aria-label="Intake tools">
          {canSummarize ? (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Medical summary</h2>
                  <p>
                    {summary
                      ? "Generated from current transcript"
                      : "Ready after the request is sent"}
                  </p>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={summaryMutation.isPending}
                  onClick={requestSummary}
                >
                  <FileText aria-hidden="true" size={16} />
                  {summaryMutation.isPending ? "Generating" : "Generate"}
                </button>
              </div>
              {summaryMutation.error instanceof Error ? (
                <Notice tone="danger" title="Summary failed">
                  {summaryMutation.error.message}
                </Notice>
              ) : null}
              {summary ? (
                <SummaryView summary={summary} />
              ) : (
                <CompactEmpty label="No summary generated." />
              )}
            </section>
          ) : null}

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>PDF report</h2>
                <p>
                  {uploadResult
                    ? `${uploadResult.filename} is ready`
                    : "Attach to the current request"}
                </p>
              </div>
            </div>
            <div
              className={`drop-zone ${isDragging ? "dragging" : ""} ${uploadDisabled ? "disabled" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (!uploadDisabled) {
                  setIsDragging(true);
                }
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                if (!uploadDisabled) {
                  handleFile(event.dataTransfer.files.item(0));
                }
              }}
            >
              <Upload aria-hidden="true" size={22} />
              <label className="file-picker" aria-disabled={uploadDisabled}>
                <span className="file-picker-text">
                  {selectedFile ? selectedFile.name : "Choose PDF report"}
                </span>
                <span className="file-picker-button">Browse</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={uploadDisabled}
                  onChange={(event) =>
                    handleFile(event.target.files?.item(0) ?? null)
                  }
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
                Converted to compact markdown for AI retrieval.{" "}
                {uploadResult.chunk_count} chunks,{" "}
                {uploadResult.markdown_char_count.toLocaleString()} characters.
              </Notice>
            ) : null}
            <button
              className="primary-button full-width h-[4px]"
              type="button"
              disabled={
                !sessionId ||
                !selectedFile ||
                uploadMutation.isPending ||
                uploadDisabled
              }
              onClick={submitUpload}
            >
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

function isReviewStatus(status: SessionStatus | null): boolean {
  return status === "submitted" || status === "completed";
}

function statusLabel(
  status: SessionStatus | null,
  hasSession: boolean,
  requestSubmitted: boolean,
) {
  if (!hasSession) {
    return "New request";
  }
  if (status === "completed") {
    return "Sent for review";
  }
  if (status === "escalated") {
    return "Emergency flagged";
  }
  if (status === "abandoned") {
    return "Closed";
  }
  if (requestSubmitted) {
    return "Sent for review";
  }
  return "In progress";
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
