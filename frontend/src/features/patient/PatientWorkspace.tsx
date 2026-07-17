import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
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

type IntakeMessage = {
  id: string;
  role: "patient" | "assistant";
  content: string;
  emergency?: boolean;
};

const sessionStorageKey = "patient-intake-active-session";
const maxReportBytes = 10 * 1024 * 1024;

export function PatientWorkspace() {
  const apiClient = useApiClient();
  const [sessionId, setSessionId] = useLocalSessionId();
  const [messages, setMessages] = useState<IntakeMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [summary, setSummary] = useState<MedicalSummary | null>(null);
  const [uploadResult, setUploadResult] = useState<ReportUploadResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

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

  const emergencyActive = useMemo(
    () => messages.some((message) => message.role === "assistant" && message.emergency),
    [messages],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, chatMutation.isPending]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || chatMutation.isPending) {
      return;
    }

    setDraft("");
    setChatError(null);
    setSummary(null);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "patient", content: message },
    ]);

    try {
      const response = await chatMutation.mutateAsync(message);
      receiveChatResponse(response);
    } catch (error) {
      setChatError(toUserError(error));
      if (error instanceof ApiError && error.status === 404) {
        setSessionId("");
      }
    }
  }

  function receiveChatResponse(response: ChatResponse) {
    setSessionId(response.session_id);
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

  function startNewIntake() {
    setSessionId("");
    setMessages([]);
    setDraft("");
    setChatError(null);
    setSummary(null);
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
        <button className="secondary-button" type="button" onClick={startNewIntake}>
          <RefreshCcw aria-hidden="true" size={16} />
          New intake
        </button>
      </div>

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
              <p>{sessionId ? `Session ${sessionId}` : "No active session"}</p>
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
              placeholder="Describe symptoms, timeline, medications, or concerns"
              rows={3}
              maxLength={10_000}
            />
            <button className="primary-button send-button" type="submit" disabled={!draft.trim() || chatMutation.isPending}>
              <Send aria-hidden="true" size={17} />
              Send
            </button>
          </form>
        </section>

        <aside className="side-stack" aria-label="Intake tools">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Medical summary</h2>
                <p>{summary ? "Generated from current transcript" : "Unavailable until a session exists"}</p>
              </div>
              <button className="secondary-button" type="button" disabled={!sessionId || summaryMutation.isPending} onClick={requestSummary}>
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
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>PDF report</h2>
                <p>{uploadResult ? `${uploadResult.filename} embedded in ${uploadResult.chunk_count} chunks` : "Attach to the active intake"}</p>
              </div>
            </div>
            <div
              className={`drop-zone ${isDragging ? "dragging" : ""} ${!sessionId ? "disabled" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (sessionId) {
                  setIsDragging(true);
                }
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                if (sessionId) {
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
                  disabled={!sessionId}
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
            <button className="primary-button full-width" type="button" disabled={!sessionId || !selectedFile || uploadMutation.isPending} onClick={submitUpload}>
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
      <SummaryText title="Chief complaint" value={summary.chief_complaint} />
      <SummaryText title="Timeline" value={summary.symptom_timeline} />
      <SummaryText title="Relevant history" value={summary.relevant_history} />
      <SummaryList title="Reported red flags" values={summary.red_flags} empty="None reported." />
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

function SummaryList({ title, values, empty }: { title: string; values: string[]; empty: string }) {
  return (
    <section>
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

function useLocalSessionId() {
  const [sessionId, setSessionIdState] = useState(() => localStorage.getItem(sessionStorageKey) ?? "");

  function setSessionId(nextSessionId: string) {
    setSessionIdState(nextSessionId);
    if (nextSessionId) {
      localStorage.setItem(sessionStorageKey, nextSessionId);
    } else {
      localStorage.removeItem(sessionStorageKey);
    }
  }

  return [sessionId, setSessionId] as const;
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
