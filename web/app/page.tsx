import Link from "next/link";
import { getPublicConfig } from "@/lib/api";

export default async function Home() {
  const config = await getPublicConfig();
  if (!config) {
    return <main className="message-page"><div className="message-card"><h1>Tavo is waking up</h1><p>The demo service is starting. Refresh this page in a moment.</p></div></main>;
  }
  return (
    <main className="landing">
      <div className="landing-copy">
        {config?.demo_mode && <span className="demo-indicator">Demo workspace</span>}
        <h1>Every cleaning inquiry, in one clear place.</h1>
        <p>Tavo is a working customer workflow for a fictional cleaning business. See how an inquiry becomes a lead your team can act on.</p>
        <div className="actions">
          {config?.demo_mode ? (
            <Link className="button" href="/login">Try the live demo</Link>
          ) : (
            <>
              <Link className="button" href="/inquiry">Submit an inquiry</Link>
              <Link className="button button-secondary" href="/login">Open business CRM</Link>
            </>
          )}
        </div>
        <p className="small-note">
          Each inquiry becomes a lead with an AI-generated service category, priority, and summary. The owner reviews it in
          the pipeline and can have AI draft a reply — which is only sent after a human approves it.
          {config?.demo_mode ? " The hosted demo creates only fake inquiries and redirects email to a safe test destination." : ""}
        </p>
      </div>
      <div className="landing-panel" aria-label="Inquiry workflow preview">
        <div className="panel-heading">INQUIRY DESK</div>
        <div className="preview-row"><span className="preview-dot" /> New request received <span>01</span></div>
        <div className="preview-row"><span className="preview-dot" /> Customer details saved <span>02</span></div>
        <div className="preview-row"><span className="preview-dot" /> AI classified and summarised <span>03</span></div>
        <div className="preview-row"><span className="preview-dot muted" /> Reply drafted, owner approves <span>04</span></div>
      </div>
    </main>
  );
}
