import type { ReactNode } from "react";

export function Page({ children }: { children: ReactNode }) {
  return <main className="mx-auto w-full max-w-[1400px] px-4 pb-24 pt-10 md:px-8 md:pt-14">{children}</main>;
}

export function PageHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-10">
      <h1 className="text-3xl font-medium tracking-[-0.03em] md:text-[2.6rem] md:leading-[1.05]">{title}</h1>
      {children && <div className="mt-3 max-w-[70ch] text-[15px] leading-relaxed text-ink-soft">{children}</div>}
    </div>
  );
}

export function Offline({ error }: { error: string }) {
  return (
    <div className="rounded-md border border-line bg-surface p-8">
      <p className="text-lg font-medium">No live data</p>
      <p className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-ink-soft">
        The read API is {error === "unreachable" ? "not running" : `not answering (${error})`}. This page shows real
        validator data only, never samples. Start it from the repo in WSL:
      </p>
      <pre className="mt-5 inline-block rounded-sm bg-ink px-4 py-3 font-mono text-[13px] text-paper">make api</pre>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-ink/20 p-8">
      <p className="text-lg font-medium">{title}</p>
      {children && <p className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-ink-soft">{children}</p>}
    </div>
  );
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-md bg-surface" />
      ))}
    </div>
  );
}

export function Badge({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "accent" | "fail" | "ink" }) {
  const cls = {
    plain: "border border-ink/20 text-ink-soft",
    accent: "bg-accent text-ink",
    fail: "border border-fail/40 text-fail",
    ink: "bg-ink text-paper",
  }[tone];
  return <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 font-mono text-[11.5px] ${cls}`}>{children}</span>;
}

/** A score bar with no background track; width is the value out of 100. */
export function Bar({ value, tone = "accent" }: { value: number; tone?: "accent" | "muted" }) {
  return (
    <span
      aria-hidden="true"
      className={`block h-1.5 rounded-sm ${tone === "accent" ? "bg-accent" : "bg-ink/30"}`}
      style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
    />
  );
}
