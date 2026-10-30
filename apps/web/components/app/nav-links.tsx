"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV } from "./nav";

export function NavLinks() {
  const path = usePathname();
  return NAV.map((n) => {
    const active = path === n.href || path.startsWith(`${n.href}/`);
    return (
      <Link
        key={n.href}
        href={n.href}
        aria-current={active ? "page" : undefined}
        className={`whitespace-nowrap rounded-sm px-2.5 py-1.5 transition-colors ${
          active ? "bg-surface text-ink" : "text-ink-soft hover:text-ink"
        }`}
      >
        {n.label}
      </Link>
    );
  });
}
