import Link from "next/link";
import { getPublicConfig } from "@/lib/api";

export default async function Home() {
  const config = await getPublicConfig();
  return (
    <main className="landing">
      <div className="landing-copy">
        <h1>Every cleaning inquiry, in one clear place.</h1>
        <p>CleanFlow CRM is a working example of a customer workflow built for a fictional cleaning business.</p>
        <div className="actions">
          <Link className="button" href="/inquiry">Submit an inquiry</Link>
          <Link className="button button-secondary" href="/login">{config?.demo_mode ? "Try the live demo" : "Open business CRM"}</Link>
        </div>
        <p className="small-note">
          Each inquiry becomes a lead with an AI-generated service category, priority, and summary. The owner reviews it in
          the pipeline and can have AI draft a reply — which is only sent after a human approves it.
          {config?.demo_mode ? " The hosted demo uses fake customers and a controlled inbox." : ""}
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
