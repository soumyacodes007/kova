"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { SHARED_NAV, TRACKS, trackOf, type TrackId } from "./nav";

function TrackSwitch({ current, sample }: { current: TrackId | null; sample: boolean }) {
  return (
    <div className="flex shrink-0 rounded-md border border-line p-0.5" role="group" aria-label="Track">
      {(Object.keys(TRACKS) as TrackId[]).map((id) => {
        const t = TRACKS[id];
        const on = current === id;
        return (
          <Link
            key={id}
            href={sample && t.home.startsWith("/hill") ? `${t.home}?sample=1` : t.home}
            aria-current={on ? "true" : undefined}
            className={`whitespace-nowrap rounded-sm px-2.5 py-1 text-[13px] transition-colors ${
              on ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            <span className="font-mono">{t.label}</span>
            <span className="hidden lg:inline"> · {t.name}</span>
          </Link>
        );
      })}
    </div>
  );
}

function NavLink({ href, label, path, sample }: { href: string; label: string; path: string; sample: boolean }) {
  const active = path === href || (href !== "/hill" && path.startsWith(`${href}/`));
  return (
    <Link
      href={sample && href.startsWith("/hill") ? `${href}?sample=1` : href}
      aria-current={active ? "page" : undefined}
      className={`whitespace-nowrap rounded-sm px-2.5 py-1.5 transition-colors ${
        active ? "bg-surface text-ink" : "text-ink-soft hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
}

export function NavLinks() {
  const path = usePathname();
  const track = trackOf(path);
  // sample mode stays on inside Track B
  const sampleParam = useSearchParams().get("sample") === "1";
  const sample = path.startsWith("/hill") && sampleParam;
  const items = track ? TRACKS[track].nav : [];

  return (
    <>
      <TrackSwitch current={track} sample={sample} />
      <span aria-hidden="true" className="mx-1 h-5 w-px shrink-0 bg-line" />
      {items.map((n) => (
        <NavLink key={n.href} {...n} path={path} sample={sample} />
      ))}
      {items.length > 0 && <span aria-hidden="true" className="mx-1 h-5 w-px shrink-0 bg-line" />}
      {SHARED_NAV.map((n) => (
        <NavLink key={n.href} {...n} path={path} sample={sample} />
      ))}
    </>
  );
}
