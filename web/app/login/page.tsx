import { signIn } from "@/app/actions";
import SubmitButton from "@/app/submit-button";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return <main className="message-page"><div className="login-card"><h1>Business sign in</h1><p>Access your cleaning inquiries.</p><form action={signIn} className="stacked-form">{error && <p role="alert" className="error">{error === "credentials" ? "Email or password was incorrect. Try again." : "Sign in is unavailable right now. Please try again."}</p>}<label>Email<input name="email" type="email" autoComplete="username" required /></label><label>Password<input name="password" type="password" autoComplete="current-password" required /></label><SubmitButton label="Sign in" /></form></div></main>;
}
