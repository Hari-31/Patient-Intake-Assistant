import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";
import type { UserRole } from "../../lib/types";

type AuthStatus = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  role: UserRole | null;
  status: AuthStatus;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  supabaseClient: SupabaseClient;
  children: ReactNode;
};

export function AuthProvider({ supabaseClient, children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let mounted = true;

    supabaseClient.auth.getSession().then(({ data }) => {
      if (!mounted) {
        return;
      }
      setSession(data.session);
      setStatus(data.session ? "authenticated" : "anonymous");
    });

    const { data } = supabaseClient.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setStatus(nextSession ? "authenticated" : "anonymous");
    });

    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, [supabaseClient]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const { error } = await supabaseClient.auth.signInWithPassword({
        email,
        password,
      });
      if (error) {
        throw new Error(error.message);
      }
    },
    [supabaseClient],
  );

  const signOut = useCallback(async () => {
    const { error } = await supabaseClient.auth.signOut();
    if (error) {
      throw new Error(error.message);
    }
  }, [supabaseClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      role: getRole(session),
      status,
      signIn,
      signOut,
    }),
    [session, signIn, signOut, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const auth = useContext(AuthContext);
  if (!auth) {
    throw new Error("AuthProvider is missing.");
  }
  return auth;
}

function getRole(session: Session | null): UserRole | null {
  const role = session?.user.app_metadata?.role;
  return role === "patient" || role === "doctor" ? role : null;
}
