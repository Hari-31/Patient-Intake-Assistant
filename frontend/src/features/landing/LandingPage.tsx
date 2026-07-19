import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileText,
  HeartPulse,
  LockKeyhole,
  MessageSquareText,
  ShieldCheck,
  Stethoscope,
  UploadCloud,
  UserRoundCheck,
} from "lucide-react";
import { useAuth } from "../auth/AuthProvider";

type WorkflowKey = "patient" | "doctor" | "operations";

const workflowPanels = {
  patient: {
    title: "Guided patient intake",
    body: "Patients start with a calm symptom conversation, upload report PDFs, and generate a structured summary before the visit.",
    image:
      "https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=1200&q=80",
    alt: "Clinician reviewing information with a patient in a bright exam room",
  },
  doctor: {
    title: "Read-only clinical review",
    body: "Assigned doctors review summaries and transcripts side-by-side without changing patient-doctor assignments from the frontend.",
    image:
      "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&q=80",
    alt: "Healthcare worker using a tablet during clinical review",
  },
  operations: {
    title: "Protected backend boundaries",
    body: "Supabase roles, FastAPI authorization, and scoped patient ownership keep the browser experience aligned with backend policy.",
    image:
      "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1200&q=80",
    alt: "Medical monitoring equipment in a healthcare environment",
  },
} satisfies Record<WorkflowKey, { title: string; body: string; image: string; alt: string }>;

const intakeSteps = [
  {
    icon: MessageSquareText,
    title: "Symptom conversation",
    body: "Collect onset, severity, timeline, relevant history, and medication context.",
  },
  {
    icon: UploadCloud,
    title: "Report context",
    body: "Attach text-based PDF reports to the active intake session with client-side checks.",
  },
  {
    icon: ClipboardList,
    title: "Structured summary",
    body: "Separate chief complaint, timeline, red flags, warning signs, and doctor questions.",
  },
  {
    icon: UserRoundCheck,
    title: "Assigned review",
    body: "Doctors inspect assigned sessions through read-only patient and transcript views.",
  },
];

const trustItems = [
  "Role-aware route protection",
  "Bearer-token API requests",
  "Patient-owned sessions",
  "Backend-only secrets excluded",
];

const faqItems = [
  {
    question: "Is this a diagnosis tool?",
    answer:
      "No. The interface presents AI output as intake support and keeps urgent symptoms visually distinct from ordinary assistant replies.",
  },
  {
    question: "Can patients upload reports?",
    answer:
      "Yes. The current frontend accepts PDFs under 10 MB and sends them to the backend for session-scoped processing.",
  },
  {
    question: "Can doctors edit records here?",
    answer:
      "No. Doctor workflows are read-only until the backend exposes a reviewed state, notes, or assignment APIs.",
  },
];

export function LandingPage() {
  const auth = useAuth();
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowKey>("patient");
  const [priority, setPriority] = useState(62);
  const [openFaq, setOpenFaq] = useState(0);

  const activePanel = workflowPanels[activeWorkflow];
  const workspacePath = auth.role === "doctor" ? "/doctor" : auth.role === "patient" ? "/patient" : "/unauthorized";
  const priorityLabel = useMemo(() => {
    if (priority >= 76) {
      return "Escalate for urgent review";
    }
    if (priority >= 45) {
      return "Prioritize in the intake queue";
    }
    return "Continue routine intake";
  }, [priority]);

  return (
    <div className="landing-page">
      <section className="landing-hero" aria-labelledby="landing-title">
        <img
          className="landing-hero-image"
          src="https://images.unsplash.com/photo-1584982751601-97dcc096659c?auto=format&fit=crop&w=2200&q=80"
          alt="Clinician reviewing patient intake information in a healthcare setting"
        />
        <div className="landing-hero-overlay" />
        <div className="landing-hero-content">
          <div className="landing-kicker">
            <HeartPulse aria-hidden="true" size={18} />
            AI-assisted clinical intake
          </div>
          <h1 id="landing-title">Patient Intake Assistant</h1>
          <p>
            A healthcare-focused workspace for patient symptom collection, report context,
            structured summaries, and assigned doctor review.
          </p>
          <div className="landing-actions">
            <Link className="primary-button landing-cta" to={auth.session ? workspacePath : "/auth"}>
              {auth.session ? "Open workspace" : "Start intake"}
              <ArrowRight aria-hidden="true" size={17} />
            </Link>
            <a className="secondary-button landing-secondary" href="#workflow">
              See workflow
            </a>
          </div>
          <div className="hero-proof-row" aria-label="Platform highlights">
            <span>
              <ShieldCheck aria-hidden="true" size={16} />
              Role-scoped access
            </span>
            <span>
              <FileText aria-hidden="true" size={16} />
              PDF report context
            </span>
            <span>
              <Activity aria-hidden="true" size={16} />
              Emergency-aware responses
            </span>
          </div>
        </div>
      </section>

      <section className="landing-section stats-band" aria-label="Operational highlights">
        <div>
          <strong>4</strong>
          <span>Core intake surfaces</span>
        </div>
        <div>
          <strong>10 MB</strong>
          <span>Client PDF limit</span>
        </div>
        <div>
          <strong>2</strong>
          <span>Role workspaces</span>
        </div>
        <div>
          <strong>0</strong>
          <span>Browser backend secrets</span>
        </div>
      </section>

      <section className="landing-section split-section" id="platform" aria-labelledby="platform-title">
        <div className="section-copy">
          <div className="eyebrow">Platform</div>
          <h2 id="platform-title">Designed around clinical intake moments</h2>
          <p>
            The experience emphasizes patient clarity, clinician review, and backend-enforced
            authorization instead of turning healthcare workflows into a generic chat page.
          </p>
        </div>
        <div className="feature-grid">
          {intakeSteps.map((step) => {
            const Icon = step.icon;
            return (
              <article className="feature-tile" key={step.title}>
                <Icon aria-hidden="true" size={22} />
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="landing-section workflow-section" id="workflow" aria-labelledby="workflow-title">
        <div className="section-copy centered">
          <div className="eyebrow">Interactive workflow</div>
          <h2 id="workflow-title">Choose the view that matches the care team</h2>
          <p>Switch between the primary product surfaces and see what each role needs from the intake flow.</p>
        </div>
        <div className="workflow-layout">
          <div className="workflow-tabs" role="tablist" aria-label="Workflow role views">
            {(Object.keys(workflowPanels) as WorkflowKey[]).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={activeWorkflow === key}
                className={activeWorkflow === key ? "active" : undefined}
                onClick={() => setActiveWorkflow(key)}
              >
                {workflowPanels[key].title}
              </button>
            ))}
          </div>
          <article className="workflow-preview">
            <img src={activePanel.image} alt={activePanel.alt} />
            <div>
              <h3>{activePanel.title}</h3>
              <p>{activePanel.body}</p>
              <Link to={auth.session ? workspacePath : "/auth"} className="text-link">
                {auth.session ? "Open workspace" : "Continue to sign in"}
                <ArrowRight aria-hidden="true" size={16} />
              </Link>
            </div>
          </article>
        </div>
      </section>

      <section className="landing-section decision-section" aria-labelledby="decision-title">
        <div className="decision-panel">
          <div>
            <div className="eyebrow">Intake priority control</div>
            <h2 id="decision-title">Model the triage emphasis before the conversation</h2>
            <p>
              This interactive preview shows how the interface can make priority states visible
              without presenting the AI as a diagnosis engine.
            </p>
          </div>
          <div className="priority-control">
            <label htmlFor="priority-range">Symptom priority</label>
            <input
              id="priority-range"
              type="range"
              min="0"
              max="100"
              value={priority}
              onChange={(event) => setPriority(Number(event.target.value))}
            />
            <div className="priority-meter" aria-hidden="true">
              <span style={{ width: `${priority}%` }} />
            </div>
            <output htmlFor="priority-range">{priorityLabel}</output>
          </div>
        </div>
      </section>

      <section className="landing-section trust-section" id="trust" aria-labelledby="trust-title">
        <div className="trust-image-wrap">
          <img
            src="https://images.unsplash.com/photo-1551076805-e1869033e561?auto=format&fit=crop&w=1200&q=80"
            alt="Stethoscope and clinical tools on a medical desk"
            loading="lazy"
          />
        </div>
        <div className="trust-copy">
          <div className="eyebrow">Trust boundaries</div>
          <h2 id="trust-title">Healthcare UI with explicit safety edges</h2>
          <p>
            The frontend keeps sensitive authority in the backend, separates patient and doctor
            workspaces, and makes urgent-care states visually distinct.
          </p>
          <ul className="trust-list">
            {trustItems.map((item) => (
              <li key={item}>
                <CheckCircle2 aria-hidden="true" size={18} />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="landing-section faq-section" id="faq" aria-labelledby="faq-title">
        <div className="section-copy">
          <div className="eyebrow">Questions</div>
          <h2 id="faq-title">Common product boundaries</h2>
        </div>
        <div className="faq-list">
          {faqItems.map((item, index) => (
            <button
              key={item.question}
              type="button"
              className={openFaq === index ? "faq-item open" : "faq-item"}
              aria-expanded={openFaq === index}
              onClick={() => setOpenFaq(openFaq === index ? -1 : index)}
            >
              <span>
                <strong>{item.question}</strong>
                {openFaq === index ? <p>{item.answer}</p> : null}
              </span>
              <ChevronDown aria-hidden="true" size={18} />
            </button>
          ))}
        </div>
      </section>

      <section className="landing-section final-cta" aria-labelledby="final-cta-title">
        <div>
          <BrainCircuit aria-hidden="true" size={28} />
          <h2 id="final-cta-title">Start with intake, review with context</h2>
          <p>Open the product workspace when you are ready to connect real Supabase and backend values.</p>
        </div>
        <Link className="primary-button landing-cta" to={auth.session ? workspacePath : "/auth"}>
          {auth.session ? "Open workspace" : "Go to sign in"}
          <Stethoscope aria-hidden="true" size={17} />
        </Link>
      </section>
    </div>
  );
}
