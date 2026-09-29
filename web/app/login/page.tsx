import { signIn, signInAsDemo } from "@/app/actions";
import SubmitButton from "@/app/submit-button";
import { getPublicConfig } from "@/lib/api";

const MESSAGES: Record<string, string> = {
  credentials: "Email or password was incorrect. Try again.",
  unavailable: "Sign in is unavailable right now. Please try again.",
  rate: "Too many sign-in attempts from this address. Please wait a few minutes and try again.",
  demo: "The demo workspace couldn’t be opened. Please try again shortly.",
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  const config = await getPublicConfig();
  const demoEmail = (process.env.DEMO_LOGIN_EMAIL ?? "").trim();
  const demoReady = Boolean(config?.demo_mode && demoEmail && (process.env.DEMO_LOGIN_PASSWORD ?? "").trim());
  const emailNote = config?.email_delivery === "redirected"
    ? "Any email is redirected to a safe demo destination."
    : config?.email_delivery === "sandbox"
      ? "Email is captured in a sandbox outbox."
      : "Email delivery is disabled in this demo.";
  return <main className="message-page"><div className="login-card">
    <h1>Sign in to Tavo</h1>
    <p>Access your cleaning inquiries.</p>
    {error && <p role="alert" className="error">{MESSAGES[error] ?? "Sign in failed. Please try again."}</p>}
    {demoReady && <div className="demo-hint">
      <p role="note">Public demo workspace. It contains fake customer data only. {emailNote}</p>
      <form action={signInAsDemo}><SubmitButton label="Enter demo workspace" pendingLabel="Opening…" /></form>
    </div>}
    <form action={signIn} className="stacked-form">
      <label>Email<input name="email" type="email" autoComplete="username" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
      <SubmitButton label="Sign in" pendingLabel="Signing in…" />
    </form>
  </div></main>;
}
