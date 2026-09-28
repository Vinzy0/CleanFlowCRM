import Link from "next/link";

export default function InquirySuccess() {
  return <main className="message-page"><div className="message-card"><span className="success-mark">✓</span><h1>Inquiry received.</h1><p>Your request has been saved for the team to review.</p><Link className="button" href="/">Back to home</Link></div></main>;
}
