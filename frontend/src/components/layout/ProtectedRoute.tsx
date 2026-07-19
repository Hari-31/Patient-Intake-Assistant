import { Navigate, Outlet } from "react-router-dom";
import { Loader2, ShieldAlert } from "lucide-react";
import { useAuth } from "../../features/auth/AuthProvider";
import type { UserRole } from "../../lib/types";

type ProtectedRouteProps = {
  role: UserRole;
};

export function ProtectedRoute({ role }: ProtectedRouteProps) {
  const auth = useAuth();

  if (auth.status === "loading") {
    return (
      <div className="center-state" role="status">
        <Loader2 className="spin" aria-hidden="true" size={22} />
        <span>Checking session</span>
      </div>
    );
  }

  if (!auth.session) {
    return <Navigate to="/auth" replace />;
  }

  if (auth.role !== role) {
    return <Unauthorized />;
  }

  return <Outlet />;
}

export function Unauthorized() {
  return (
    <div className="center-state center-state-large" role="alert">
      <ShieldAlert aria-hidden="true" size={32} />
      <div>
        <h1>Access unavailable</h1>
        <p>This account is not authorized for that workspace.</p>
      </div>
    </div>
  );
}
