import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1240px] px-4 md:px-8 ${className}`}>{children}</div>;
}

export function PrimaryLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      className="group inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-md bg-accent px-5 text-[15px] font-medium text-ink transition-colors duration-200 ease-out-expo hover:bg-accent-hover active:translate-y-px"
    >
      {children}
      <ArrowRight size={16} weight="bold" className="transition-transform duration-200 group-hover:translate-x-0.5" />
    </a>
  );
}

export function SecondaryLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      className="inline-flex h-11 items-center whitespace-nowrap rounded-md border border-ink/15 px-5 text-[15px] font-medium text-ink transition-colors duration-200 hover:border-ink/40 active:translate-y-px"
    >
      {children}
    </a>
  );
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 id={id} className="max-w-[18ch] text-3xl font-medium leading-[1.05] tracking-[-0.025em] md:text-[2.75rem]">
      {children}
    </h2>
  );
}

/** A simple geometric mark: a flange seen from above. */
export function Mark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <rect x="1" y="1" width="22" height="22" rx="2" fill="#262626" />
      <circle cx="12" cy="12" r="7.5" fill="none" stroke="#ff5e1f" strokeWidth="2" />
      <circle cx="12" cy="12" r="2.5" fill="#fdfdfc" />
    </svg>
  );
}
