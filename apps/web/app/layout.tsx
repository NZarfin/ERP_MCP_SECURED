import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "600"],
  style: ["normal", "italic"],
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex-sans",
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Green Fields Wholesale — Ledger",
  description: "Sales and purchasing ledger for a produce/herbs wholesaler.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${plexSans.variable} ${plexMono.variable}`}>
      <body className="font-sans antialiased min-h-screen">
        <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
          <header className="flex items-center justify-between border-b border-ink-border py-6">
            <Link href="/sales" className="flex items-baseline gap-3 group">
              <span className="text-2xl font-display font-semibold italic text-paper-primary tracking-tight">
                Green Fields
              </span>
              <span className="text-[11px] uppercase tracking-[0.2em] text-crop-text font-mono">
                Ledger
              </span>
            </Link>
            <nav className="flex items-center gap-1 font-mono text-[13px] uppercase tracking-wide">
              <Link
                href="/sales"
                className="px-4 py-2 rounded-sm text-paper-secondary hover:text-paper-primary hover:bg-ink-surface transition-colors"
              >
                Sales
              </Link>
              <Link
                href="/purchases"
                className="px-4 py-2 rounded-sm text-paper-secondary hover:text-paper-primary hover:bg-ink-surface transition-colors"
              >
                Purchases
              </Link>
            </nav>
          </header>
          <main className="py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
