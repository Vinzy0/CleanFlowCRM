import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <div className="landing-copy">
        <h1>Every cleaning inquiry, in one clear place.</h1>
        <p>CleanFlow CRM is a working example of a customer workflow built for a fictional cleaning business.</p>
        <div className="actions">
          <Link className="button" href="/inquiry">Submit an inquiry</Link>
          <Link className="button button-secondary" href="/login">Open business CRM</Link>
        </div>
        <p className="small-note">This first phase captures inquiries and gives the business a protected lead list. AI and email automation arrive in later phases.</p>
      </div>
      <div className="landing-panel" aria-label="Inquiry workflow preview">
        <div className="panel-heading">INQUIRY DESK</div>
        <div className="preview-row"><span className="preview-dot" /> New request received <span>01</span></div>
        <div className="preview-row"><span className="preview-dot" /> Customer details saved <span>02</span></div>
        <div className="preview-row"><span className="preview-dot muted" /> Ready for follow-up <span>03</span></div>
      </div>
    </main>
  );
}
