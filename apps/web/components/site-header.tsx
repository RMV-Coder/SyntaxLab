import Link from "next/link";
import { Suspense } from "react";

import { MainNav, NavLinks } from "./main-nav";

/**
 * The header is server-rendered. Only the navigation, which needs the current path to mark the
 * active section, reads the URL; it sits in a Suspense boundary so routes with request-time
 * params (e.g. /learn/[id]) can still prerender (a Next.js 16 requirement).
 */
export function SiteHeader() {
  return (
    <header className="flex h-14 items-center gap-4 border-b border-rule bg-sheet px-4 sm:gap-8 sm:px-5">
      <Link href="/" className="font-data text-xl font-bold tracking-tight text-ink">
        SyntaxLab
      </Link>
      <Suspense fallback={<NavLinks current={null} />}>
        <MainNav />
      </Suspense>
    </header>
  );
}
