import { ArrowRight, ClipboardCheck, LogIn, Stethoscope, UserPlus } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function LandingPage() {
  const auth = useAuth();

  if (auth.status === "authenticated") {
    if (auth.role === "patient") {
      return <Navigate to="/patient" replace />;
    }
    if (auth.role === "doctor") {
      return <Navigate to="/doctor" replace />;
    }
    return <Navigate to="/unauthorized" replace />;
  }

  return (
    <section className="landing-page simple-landing" aria-labelledby="landing-title">
      <img
        className="simple-landing-image"
        src="https://images.unsplash.com/photo-1584982751601-97dcc096659c?auto=format&fit=crop&w=1800&q=80"
        alt="Clinician reviewing patient intake details"
      />
      <div className="simple-landing-overlay" />
      <div className="simple-landing-content">
        <div className="simple-landing-copy">
          <div className="landing-kicker">
            <Stethoscope aria-hidden="true" size={18} />
            Patient Intake Assistant
          </div>
          <h1 id="landing-title">Start your request or check its status.</h1>
          <p>
            Patients can keep one active request at a time. Once it is sent for
            doctor review, start a new intake for changed symptoms or a new
            concern.
          </p>
        </div>

        <div className="landing-action-panel" aria-label="Start or access intake">
          <Link className="primary-button landing-action-main" to="/auth?mode=signup&role=patient">
            <UserPlus aria-hidden="true" size={18} />
            Start new request
            <ArrowRight aria-hidden="true" size={17} />
          </Link>
          <Link className="secondary-button landing-action-main" to="/auth?mode=signin&role=patient">
            <ClipboardCheck aria-hidden="true" size={18} />
            Check request status
          </Link>
          <div className="doctor-signin-row">
            <span>Doctor access</span>
            <Link className="text-link" to="/auth?mode=signin&role=doctor">
              <LogIn aria-hidden="true" size={16} />
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
