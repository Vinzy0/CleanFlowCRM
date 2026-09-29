import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "CleanFlow CRM",
  description: "Cleaning business inquiry and lead management demo",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="public-header">
          <Link className="brand" href="/">CleanFlow<span>CRM</span></Link>
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
