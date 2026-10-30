"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { clientPath, type Status } from "@/lib/api";
import type { Hill } from "@/lib/hill-types";

type State = { kind: "loading" } | { kind: "offline" } | { kind: "ok"; status: Status; at: number };

const POLL_MS = 5000;

function useStatus(): State {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let stop = false;
    let misses = 0;
    async function tick() {
      try {
        const res = await fetch(clientPath("/v1/status"), { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const status = (await res.json()) as Status;
        misses = 0;
        if (!stop) setState({ kind: "ok", status, at: Date.now() });
      } catch {
        // one slow poll while the validator is busy is not an outage: show offline after two misses in a row
        misses += 1;
        if (!stop && misses >= 2) setState({ kind: "offline" });
      }
    }
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, []);

  return state;
}

/** Wall clock for the round countdown; null until mounted, so prerendering never reads the time. */
function useNow(active: boolean) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

function Item({ label, children, tone }: { label: string; children: React.ReactNode; tone?: "warn" }) {
  return (
    <span className="flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-ink-soft">{label}</span>
      <span className={tone === "warn" ? "text-fail" : "text-ink"}>{children}</span>
    </span>
  );
}

/** The champion and the running match on /hill routes. Stays empty while /v1/hill is missing or fails. */
function useHill(active: boolean): Hill | null {
  const [hill, setHill] = useState<Hill | null>(null);
  useEffect(() => {
    if (!active) return;
    let stop = false;
    async function tick() {
      try {
        const res = await fetch(clientPath("/v1/hill"), { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const next = (await res.json()) as Hill;
        if (!stop) setHill(next);
      } catch {
        if (!stop) setHill(null);
      }
    }
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [active]);
  return active ? hill : null;
}

function HillItems() {
  const hill = useHill(usePathname().startsWith("/hill"));
  if (!hill) return null;
  const { champion, live_match: m } = hill;
  return (
    <>
      {champion && (
        <Link href={`/hill/models/${champion.fingerprint}`} className="flex items-baseline gap-1.5 whitespace-nowrap hover:underline">
          <span className="text-ink-soft">champion</span>
          <span className="text-ink">{champion.name}</span>
          {champion.mean_quality != null && <span className="text-accent">{champion.mean_quality.toFixed(1)}</span>}
        </Link>
      )}
      {m && m.status === "running" && (
        <Link href={`/hill/match/${m.match_id}`} className="flex items-baseline gap-1.5 whitespace-nowrap hover:underline">
          <span className="text-ink-soft">match</span>
          <span className="text-ink">
            {m.tasks_done}/{m.tasks_total}
          </span>
        </Link>
      )}
    </>
  );
}

const LIVE = new Set(["dispatching", "collecting", "evaluating"]);

export function StatusBar() {
  const state = useStatus();
  const run = state.kind === "ok" ? state.status.latest_run : null;
  const live = !!run && LIVE.has(run.status);
  const now = useNow(live);

  return (
    <div className="border-t border-line bg-surface">
      <div
        className="mx-auto flex h-9 w-full max-w-[1400px] items-center gap-5 overflow-x-auto px-4 font-mono text-[12px] md:px-8"
        aria-live="polite"
      >
        {state.kind === "loading" && <span className="text-ink-soft">Connecting to the read API</span>}
        {state.kind === "offline" && (
          <span className="whitespace-nowrap text-fail">
            Read API offline. Start it with <span className="text-ink">make api</span>
          </span>
        )}
        {state.kind === "ok" && (
          <>
            <Item label="network">{state.status.chain.network ?? "unknown"}</Item>
            <Item label="netuid">{state.status.chain.netuid ?? "n/a"}</Item>
            {state.status.chain.reachable ? (
              <Item label="block">{state.status.chain.block?.toLocaleString("en-US") ?? "n/a"}</Item>
            ) : (
              <Item label="chain" tone="warn">
                unreachable
              </Item>
            )}
            <Item label="commit-reveal">{state.status.chain.commit_reveal_enabled ? "on" : "off"}</Item>
            <Item label="miners">{state.status.counts.miners}</Item>
            <Suspense fallback={null}>
              <HillItems />
            </Suspense>
            {run && (
              <Link href={`/arena/${run.run_id}`} className="flex items-baseline gap-1.5 whitespace-nowrap hover:underline">
                <span className="text-ink-soft">latest round</span>
                <span className="text-ink">{run.run_id}</span>
                <span className={live ? "text-accent" : "text-ink-soft"}>{run.status}</span>
                {live && now != null && (
                  <span className="text-ink">
                    {Math.max(0, Math.round((new Date(run.deadline_at).getTime() - now) / 1000))}s left
                  </span>
                )}
              </Link>
            )}
          </>
        )}
      </div>
    </div>
  );
}
