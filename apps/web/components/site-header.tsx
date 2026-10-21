"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/** Only sections that exist are listed; planned ones are described on the About page. */
const SECTIONS = [
  { href: "/", label: "Analyzer", short: "Analyzer" },
  { href: "/lab", label: "Algorithm Lab", short: "Lab" },
  { href: "/about", label: "About", short: "About" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="flex h-14 items-center gap-4 border-b border-rule bg-sheet px-4 sm:gap-8 sm:px-5">
      <Link href="/" className="font-data text-xl font-bold tracking-tight text-ink">
        SyntaxLab
      </Link>
      <nav aria-label="Main">
        <ul className="flex gap-1">
          {SECTIONS.map((s) => {
            const active = s.href === "/" ? pathname === "/" : pathname.startsWith(s.href);
            return (
              <li key={s.href}>
                <Link
                  href={s.href}
                  aria-current={active ? "page" : undefined}
                  aria-label={s.label}
                  className={cn(
                    "whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm sm:px-3",
                    active ? "bg-muted font-medium text-ink" : "text-ink-soft hover:text-ink",
                  )}
                >
                  <span className="sm:hidden">{s.short}</span>
                  <span className="hidden sm:inline">{s.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
