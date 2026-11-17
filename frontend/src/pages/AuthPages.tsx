import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage, forgotPassword, googleSignIn, loginAccount, registerAccount } from "../api/client";
import { MarketingFrame } from "../components/Marketing";
import { Button, TextField } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function LoginPage() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const { push } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      setSession(await loginAccount({ email, password }));
      navigate("/app");
    } catch (error) {
      setMessage(errorMessage(error, "Sign in failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <MarketingFrame>
      <form onSubmit={onSubmit} className="card mx-auto grid max-w-md gap-4 p-6">
        <div>
          <h1 className="text-2xl font-medium">Welcome Back</h1>
          <p className="mt-1 text-sm muted">Sign in to continue your digital investigations.</p>
        </div>
        <TextField label="Email Address" name="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        <TextField label="Password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        {message ? <p className="text-sm text-[var(--danger)]">{message}</p> : null}
        <Button type="submit" disabled={busy}>
          Sign In
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            void googleSignIn().catch((error) => push(errorMessage(error, "Google sign-in is not configured."), "danger"));
          }}
        >
          Continue with Google
        </Button>
        <button
          type="button"
          className="text-left text-sm text-[var(--blue)]"
          onClick={() => {
            if (!email) {
              setMessage("Enter your email address first.");
              return;
            }
            void forgotPassword(email).catch((error) => push(errorMessage(error, "Password reset email is not configured."), "danger"));
          }}
        >
          Forgot Password?
        </button>
        <p className="text-sm muted">
          Don't have an account? <Link to="/register">Create Account</Link>
        </p>
      </form>
    </MarketingFrame>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setMessage("Passwords do not match.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      setSession(await registerAccount({ full_name: fullName, email, password, accepted_terms: accepted }));
      navigate("/app");
    } catch (error) {
      setMessage(errorMessage(error, "Account creation failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <MarketingFrame>
      <form onSubmit={onSubmit} className="card mx-auto grid max-w-md gap-4 p-6">
        <h1 className="text-2xl font-medium">Create Your TRUSTIFY AI Account</h1>
        <TextField label="Full Name" name="full_name" required value={fullName} onChange={(event) => setFullName(event.target.value)} />
        <TextField label="Email Address" name="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        <TextField label="Password" name="password" type="password" autoComplete="new-password" required minLength={12} hint="At least 12 characters." value={password} onChange={(event) => setPassword(event.target.value)} />
        <TextField label="Confirm Password" name="confirm" type="password" autoComplete="new-password" required value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} required />
          <span>
            I agree to the <Link to="/terms">Terms of Service</Link> and <Link to="/privacy">Privacy Policy</Link>.
          </span>
        </label>
        {message ? <p className="text-sm text-[var(--danger)]">{message}</p> : null}
        <Button type="submit" disabled={busy}>
          Create Account
        </Button>
      </form>
    </MarketingFrame>
  );
}
