import { LogIn, LogOut, MessageSquareText, Stethoscope, UserRound } from "lucide-react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthProvider";

export function AppShell() {
  const auth = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await auth.signOut();
    navigate("/", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Patient Intake Assistant home">
          <Stethoscope aria-hidden="true" size={22} />
          <span>Patient Intake</span>
        </a>
        <nav className="topbar-nav" aria-label="Primary navigation">
          {auth.status === "authenticated" ? (
            <>
              {auth.role === "patient" ? (
                <NavLink to="/patient" className={({ isActive }) => (isActive ? "active" : undefined)}>
                  <MessageSquareText aria-hidden="true" size={17} />
                  <span>Intake</span>
                </NavLink>
              ) : null}
              {auth.role === "doctor" ? (
                <NavLink to="/doctor" className={({ isActive }) => (isActive ? "active" : undefined)}>
                  <UserRound aria-hidden="true" size={17} />
                  <span>Review</span>
                </NavLink>
              ) : null}
            </>
          ) : (
            <>
              <Link to="/auth?mode=signup&role=patient">
                <MessageSquareText aria-hidden="true" size={17} />
                <span>Patient</span>
              </Link>
              <Link to="/auth?mode=signin&role=doctor">
                <UserRound aria-hidden="true" size={17} />
                <span>Doctor</span>
              </Link>
            </>
          )}
        </nav>
        <div className="topbar-actions">
          {auth.status === "authenticated" ? (
            <>
              <span className="user-chip">{auth.user?.email}</span>
              <button className="icon-button" type="button" onClick={handleSignOut} aria-label="Sign out" title="Sign out">
                <LogOut aria-hidden="true" size={18} />
              </button>
            </>
          ) : (
            <Link className="topbar-login" to="/auth?mode=signin">
              <LogIn aria-hidden="true" size={17} />
              Sign in
            </Link>
          )}
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
