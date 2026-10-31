import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/app/page-parts";
import type { Family, Model, ModelStatus } from "@/lib/hill-types";

export const FAMILY_LABEL: Record<Family, string> = {
  plate: "Plate",
  flange: "Flange",
  wafer_chuck: "Wafer chuck",
  vacuum_chamber: "Chamber",
};

export function SampleBanner({ live }: { live: string }) {
  return (
    <div className="mb-8 flex flex-wrap items-center justify-between gap-3 rounded-md border border-accent bg-accent/10 px-4 py-3 text-[14px]">
      <p>
        <span className="font-mono font-medium">Sample data.</span> Made up for designing this page, not from the network.
      </p>
      <Link href={live} className="font-medium underline-offset-2 hover:underline">
        Show live data
      </Link>
    </div>
  );
}

export function BackendPending({ error, samplePath }: { error: string; samplePath: string }) {
  const offline = error === "unreachable";
  return (
    <div className="rounded-md border border-line bg-surface p-8">
      <p className="text-lg font-medium">{offline ? "The read API is not running" : "Track B's backend isn't live yet"}</p>
      <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-ink-soft">
        {offline
          ? "Start it from the repo in WSL with make api. This page shows real validator data only."
          : "This page reads the king-of-the-hill endpoints described in docs/api/hill-contract.md. They appear here as soon as the validator serves them."}
      </p>
      <Link
        href={samplePath}
        className="mt-5 inline-flex h-10 items-center rounded-md border border-ink/20 px-4 text-[14px] font-medium transition-colors hover:border-ink/50"
      >
        Preview with sample data
      </Link>
    </div>
  );
}

const STATUS_TONE: Record<ModelStatus, "accent" | "ink" | "plain" | "fail"> = {
  champion: "accent",
  evaluating: "ink",
  scored: "plain",
  queued: "plain",
  prechecked: "plain",
  submitted: "plain",
  defeated: "plain",
  rejected: "fail",
};

export function StatusBadge({ m }: { m: Pick<Model, "status" | "progress"> }) {
  const label = m.status === "evaluating" && m.progress ? `evaluating ${m.progress.done}/${m.progress.total}` : m.status;
  return <Badge tone={STATUS_TONE[m.status]}>{label}</Badge>;
}

export function SourceBadge({ m }: { m: Pick<Model, "source" | "tee"> }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Badge>{m.source === "catalog" ? "Chutes catalog" : m.source === "mock" ? "mock miner (scripted)" : "miner"}</Badge>
      {m.tee && <Badge>TEE</Badge>}
    </span>
  );
}

/** One square per task of the model's latest match. */
export function TaskStrip({ tasks, size = "sm" }: { tasks: (number | null)[]; size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-3 w-3" : "h-5 w-5";
  return (
    <span className="flex gap-[3px]" aria-label={`Latest match tasks: ${tasks.map((t) => t ?? "pending").join(", ")}`}>
      {tasks.map((q, i) => (
        <span
          key={i}
          className={`${box} rounded-[2px] ${
            q == null ? "border border-dashed border-ink/25" : q === 100 ? "bg-accent" : q > 0 ? "bg-accent/35" : "hatch border border-ink/15"
          }`}
        />
      ))}
    </span>
  );
}

export function FamilyBars({ per }: { per: Model["per_family"] }) {
  const entries = Object.entries(per) as [Family, number][];
  if (!entries.length) return <span className="text-[12px] text-ink-soft">no scores yet</span>;
  return (
    <span className="grid gap-1">
      {entries.map(([f, v]) => (
        <span key={f} className="grid grid-cols-[5.5rem_minmax(0,1fr)_2.2rem] items-center gap-2 font-mono text-[11.5px]">
          <span className="truncate text-ink-soft">{FAMILY_LABEL[f]}</span>
          <span aria-hidden="true" className="h-1 rounded-sm bg-ink/60" style={{ width: `${v}%` }} />
          <span className="text-right">{Math.round(v)}</span>
        </span>
      ))}
    </span>
  );
}

/** Champion score with the line a challenger has to cross (score + margin). No background track. */
export function DethroneMeter({ score, margin, challenger }: { score: number; margin: number; challenger?: number | null }) {
  const line = Math.min(100, score + margin);
  return (
    <div className="relative h-7" role="img" aria-label={`Champion ${score.toFixed(1)}; a challenger needs more than ${line.toFixed(1)}`}>
      <span className="absolute left-0 top-[13px] h-[2px] bg-ink" style={{ width: `${score}%` }} />
      {challenger != null && (
        <span className="absolute left-0 top-[19px] h-[2px] bg-accent" style={{ width: `${challenger}%` }} />
      )}
      <span className="absolute top-0 h-7 w-[2px] bg-accent" style={{ left: `${line}%` }} />
      <span className="absolute -top-0.5 font-mono text-[11px] text-ink-soft" style={{ left: `calc(${line}% + 6px)` }}>
        {line.toFixed(1)} to take the hill
      </span>
    </div>
  );
}

/** Engineering-drawing frame: border, zone letters along the top, sheet line at the bottom. */
export function Sheet({ children, footer }: { children: ReactNode; footer: ReactNode }) {
  return (
    <div className="border-[1.5px] border-ink p-1.5">
      <div className="border border-ink/70 px-4 pb-3 pt-2 md:px-6">
        <div aria-hidden="true" className="mb-4 flex justify-between font-mono text-[10.5px] text-ink-soft/70">
          {["A", "B", "C", "D", "E", "F", "G", "H"].map((z) => (
            <span key={z}>{z}</span>
          ))}
        </div>
        {children}
        <div className="mt-5 flex flex-wrap justify-between gap-x-6 gap-y-1 border-t border-ink/70 pt-2 font-mono text-[11px] text-ink-soft">
          {footer}
        </div>
      </div>
    </div>
  );
}

export const q1 = (v: number | null | undefined) => (v == null ? "n/a" : v.toFixed(1));
export const shortRev = (r: string | null) => (r ? r.slice(0, 7) : "n/a");
