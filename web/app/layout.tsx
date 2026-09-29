import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tavo | Service business CRM demo",
  description: "Tavo turns customer inquiries into an actionable service business pipeline.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="public-header">
          <Link className="brand" href="/">Tavo</Link>
          <nav aria-label="Public navigation">
            <Link href="/inquiry">Inquiry flow</Link>
            <Link href="/login">Business sign in</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
