import Link from "next/link";
import { Suspense } from "react";

import { Mark } from "@/components/landing/ui";

import { SHARED_NAV, TRACKS } from "./nav";
import { NavLinks } from "./nav-links";
import { StatusBar } from "./status-bar";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 w-full max-w-[1400px] items-center gap-6 px-4 md:px-8">
        <Link href="/" className="flex shrink-0 items-center gap-2.5 text-[15px] font-semibold tracking-[-0.01em]">
          <Mark className="h-6 w-6" />
          <span className="hidden sm:inline">CADRecover</span>
        </Link>
        <nav aria-label="App" className="-mx-1 flex min-w-0 items-center gap-1 overflow-x-auto text-[14px]">
          {/* the active-page highlight reads the URL, so it streams in after the static shell */}
          <Suspense
            fallback={[...Object.values(TRACKS).map((t) => ({ href: t.home, label: t.label })), ...SHARED_NAV].map((n) => (
              <Link key={n.href} href={n.href} className="whitespace-nowrap rounded-sm px-2.5 py-1.5 text-ink-soft">
                {n.label}
              </Link>
            ))}
          >
            <NavLinks />
          </Suspense>
        </nav>
      </div>
      <StatusBar />
    </header>
  );
}
