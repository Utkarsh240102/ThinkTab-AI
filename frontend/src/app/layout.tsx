import type { Metadata } from "next";
import "./globals.css";

/* ─────────────────────────────────────────────────────────────
   Root Layout — ThinkTab AI
   
   This is the outermost wrapper rendered on every single page.
   It provides:
     1. HTML document structure (lang, font class)
     2. App-wide SEO metadata (title, description)
     3. The globals.css styles (including our design system)
   
   The font is loaded via CSS @import in globals.css (Inter from
   Google Fonts) to keep this file clean.
─────────────────────────────────────────────────────────────── */

export const metadata: Metadata = {
  title: "ThinkTab AI — Your Intelligent Browsing Assistant",
  description:
    "Ask questions about any webpage you're reading and get instant, AI-powered answers with sources — powered by a Hybrid RAG pipeline.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      {/*
        `antialiased` smooths font rendering on all platforms.
        `h-full`      ensures the body fills the entire viewport
                      height (critical for the sidebar layout).
      */}
      <body className="h-full antialiased">
        {children}
      </body>
    </html>
  );
}
