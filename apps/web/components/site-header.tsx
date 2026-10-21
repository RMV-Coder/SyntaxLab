"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/** Only sections that exist are listed; planned ones are described on the About page. */
const SECTIONS = [
  { href: "/", label: "Analyzer" },
  { href: "/about", label: "About" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="flex h-14 items-center gap-8 border-b border-rule bg-sheet px-5">
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
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm",
                    active ? "bg-muted font-medium text-ink" : "text-ink-soft hover:text-ink",
                  )}
                >
                  {s.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
