"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { clientPath, type Status } from "@/lib/api";

type State = { kind: "loading" } | { kind: "offline" } | { kind: "ok"; status: Status; at: number };

const POLL_MS = 5000;

function useStatus(): State {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const res = await fetch(clientPath("/v1/status"), { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const status = (await res.json()) as Status;
        if (!stop) setState({ kind: "ok", status, at: Date.now() });
      } catch {
        if (!stop) setState({ kind: "offline" });
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
