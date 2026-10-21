import type { Metadata, Viewport } from "next";
import { Gentium_Book_Plus, IBM_Plex_Sans } from "next/font/google";

import { SiteHeader } from "@/components/site-header";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

// Gentium (SIL) is designed for linguistic data: full Latin diacritics and true small caps.
const dataFace = Gentium_Book_Plus({
  weight: ["400", "700"],
  style: ["normal", "italic"],
  subsets: ["latin", "latin-ext"],
  variable: "--font-data-face",
});

const uiFace = IBM_Plex_Sans({
  weight: ["400", "500", "600"],
  subsets: ["latin", "latin-ext"],
  variable: "--font-ui",
});

export const metadata: Metadata = {
  title: { default: "SyntaxLab", template: "%s · SyntaxLab" },
  description:
    "Analyze sentences and explore their syntax: phrase-structure trees, dependency graphs and explained grammatical labels.",
};

export const viewport: Viewport = {
  themeColor: "#f6f7f9",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${dataFace.variable} ${uiFace.variable} antialiased`}>
      <body className="min-h-dvh">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-sheet focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <TooltipProvider delayDuration={300}>
          <SiteHeader />
          <main id="main">{children}</main>
        </TooltipProvider>
      </body>
    </html>
  );
}
