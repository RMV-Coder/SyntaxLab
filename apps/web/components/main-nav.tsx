"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/** Only sections that exist are listed; planned ones are described on the About page. */
const SECTIONS = [
  { href: "/", label: "Analyzer", short: "Analyzer" },
  { href: "/learn", label: "Practice", short: "Practice" },
  { href: "/lab", label: "Algorithm Lab", short: "Lab" },
  { href: "/about", label: "About", short: "About" },
] as const;

/** The links themselves; `current` is null when the path is not known yet (Suspense fallback). */
export function NavLinks({ current }: { current: string | null }) {
  return (
    <nav aria-label="Main">
      <ul className="flex gap-1">
        {SECTIONS.map((s) => {
          const active = current != null && (s.href === "/" ? current === "/" : current.startsWith(s.href));
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
  );
}

/** Navigation with the current section marked. */
export function MainNav() {
  return <NavLinks current={usePathname()} />;
}
