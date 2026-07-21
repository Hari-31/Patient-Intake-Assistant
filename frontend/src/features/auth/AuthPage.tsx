import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Eye, KeyRound, LogIn, UserPlus } from "lucide-react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import {
  useForm,
  type FieldValues,
  type Path,
  type UseFormRegisterReturn,
  type UseFormReturn,
} from "react-hook-form";
import { z, type ZodError } from "zod";
import { useApiClient } from "../../app/api-context";
import { Notice } from "../../components/feedback/Notice";
import { useAuth } from "./AuthProvider";

const signInSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

const signupSchema = z.object({
  name: z.string().min(1, "Patient name is required.").max(200, "Use 200 characters or fewer."),
  email: z.string().email("Enter a valid email address.").max(320, "Use 320 characters or fewer."),
  password: z.string().min(8, "Use at least 8 characters.").max(128, "Use 128 characters or fewer."),
});

type SignInValues = z.infer<typeof signInSchema>;
type SignupValues = z.infer<typeof signupSchema>;
type AuthMode = "signin" | "signup";

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const requestedRole = searchParams.get("role");
  const doctorOnly = requestedRole === "doctor";
  const requestedMode = searchParams.get("mode");
  const [mode, setMode] = useState<AuthMode>(() =>
    requestedMode === "signup" && !doctorOnly ? "signup" : "signin",
  );
  const [showPassword, setShowPassword] = useState(false);
  const apiClient = useApiClient();
  const auth = useAuth();
  const navigate = useNavigate();

  const signInForm = useForm<SignInValues>({
    defaultValues: { email: "", password: "" },
  });
  const signupForm = useForm<SignupValues>({
    defaultValues: { name: "", email: "", password: "" },
  });

  useEffect(() => {
    setMode(requestedMode === "signup" && !doctorOnly ? "signup" : "signin");
  }, [doctorOnly, requestedMode]);

  const signInMutation = useMutation({
    mutationFn: async (values: SignInValues) => auth.signIn(values.email, values.password),
    onSuccess: () => navigate("/", { replace: true }),
  });

  const signupMutation = useMutation({
    mutationFn: async (values: SignupValues) => {
      await apiClient.signupPatient(values);
      await auth.signIn(values.email, values.password);
    },
    onSuccess: () => navigate("/", { replace: true }),
  });

  if (auth.status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  function submitSignIn(values: SignInValues) {
    const parsed = signInSchema.safeParse(values);
    if (!parsed.success) {
      applyZodErrors(signInForm, parsed.error);
      return;
    }
    signInMutation.mutate(parsed.data);
  }

  function submitSignup(values: SignupValues) {
    const parsed = signupSchema.safeParse(values);
    if (!parsed.success) {
      applyZodErrors(signupForm, parsed.error);
      return;
    }
    signupMutation.mutate(parsed.data);
  }

  const error = signInMutation.error ?? signupMutation.error;

  return (
    <section className="auth-layout" aria-labelledby="auth-title">
      <div className="auth-summary">
        <div className="eyebrow">{doctorOnly ? "Doctor sign in" : "Secure intake workspace"}</div>
        <h1 id="auth-title">Patient Intake Assistant</h1>
        <p>
          {doctorOnly
            ? "Doctor accounts are created by an admin. Sign in to review assigned patient requests."
            : "Create a patient account, open one active request, and start a new intake if something changes after review submission."}
        </p>
      </div>

      <div className="auth-panel">
        {doctorOnly ? (
          <div className="auth-mode-heading">
            <LogIn aria-hidden="true" size={18} />
            <span>Doctor sign in</span>
          </div>
        ) : (
          <div className="segmented-control" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              className={mode === "signin" ? "active" : undefined}
              aria-selected={mode === "signin"}
              role="tab"
              onClick={() => setMode("signin")}
            >
              <LogIn aria-hidden="true" size={16} />
              Sign in
            </button>
            <button
              type="button"
              className={mode === "signup" ? "active" : undefined}
              aria-selected={mode === "signup"}
              role="tab"
              onClick={() => setMode("signup")}
            >
              <UserPlus aria-hidden="true" size={16} />
              Patient signup
            </button>
          </div>
        )}

        {error instanceof Error ? (
          <Notice tone="danger" title="Authentication failed">
            {error.message}
          </Notice>
        ) : null}

        {mode === "signin" ? (
          <form className="stack-form" onSubmit={signInForm.handleSubmit(submitSignIn)} noValidate>
            <label>
              <span>Email</span>
              <input type="email" autoComplete="email" {...signInForm.register("email")} />
              <FormError message={signInForm.formState.errors.email?.message} />
            </label>
            <PasswordField
              label="Password"
              visible={showPassword}
              onToggle={() => setShowPassword((value) => !value)}
              registration={signInForm.register("password")}
              error={signInForm.formState.errors.password?.message}
            />
            <button className="primary-button" type="submit" disabled={signInMutation.isPending}>
              <LogIn aria-hidden="true" size={17} />
              {signInMutation.isPending ? "Signing in" : "Sign in"}
            </button>
          </form>
        ) : (
          <form className="stack-form" onSubmit={signupForm.handleSubmit(submitSignup)} noValidate>
            <label>
              <span>Patient name</span>
              <input type="text" autoComplete="name" {...signupForm.register("name")} />
              <FormError message={signupForm.formState.errors.name?.message} />
            </label>
            <label>
              <span>Email</span>
              <input type="email" autoComplete="email" {...signupForm.register("email")} />
              <FormError message={signupForm.formState.errors.email?.message} />
            </label>
            <PasswordField
              label="Password"
              visible={showPassword}
              onToggle={() => setShowPassword((value) => !value)}
              registration={signupForm.register("password")}
              error={signupForm.formState.errors.password?.message}
            />
            <button className="primary-button" type="submit" disabled={signupMutation.isPending}>
              <UserPlus aria-hidden="true" size={17} />
              {signupMutation.isPending ? "Creating account" : "Create patient account"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

function PasswordField({
  label,
  visible,
  onToggle,
  registration,
  error,
}: {
  label: string;
  visible: boolean;
  onToggle: () => void;
  registration: UseFormRegisterReturn;
  error?: string;
}) {
  return (
    <label>
      <span>{label}</span>
      <div className="input-with-button">
        <input type={visible ? "text" : "password"} autoComplete="current-password" {...registration} />
        <button type="button" onClick={onToggle} aria-label={visible ? "Hide password" : "Show password"} title={visible ? "Hide password" : "Show password"}>
          {visible ? <KeyRound aria-hidden="true" size={16} /> : <Eye aria-hidden="true" size={16} />}
        </button>
      </div>
      <FormError message={error} />
    </label>
  );
}

function FormError({ message }: { message?: string }) {
  return message ? <span className="field-error">{message}</span> : null;
}

function applyZodErrors<T extends FieldValues>(form: UseFormReturn<T>, error: ZodError) {
  error.issues.forEach((issue) => {
    const field = issue.path[0];
    if (typeof field === "string") {
      form.setError(field as Path<T>, { message: issue.message });
    }
  });
}
