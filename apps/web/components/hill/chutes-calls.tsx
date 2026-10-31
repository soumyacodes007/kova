"use client";

import { useEffect, useState } from "react";

import { clientPath, type EventOut } from "@/lib/api";

type Call = {
  match_id: string;
  endpoint: string;
  status_code: number;
  requested_model: string;
  reported_model: string | null;
  response_id: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost_usd: number | null;
};

/** Every paid Chutes request the validator made for this match, as logged by the runner. */
export function ChutesCalls({ matchId, refreshKey }: { matchId: string; refreshKey: number }) {
  const [calls, setCalls] = useState<Call[] | null>(null);

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const res = await fetch(clientPath("/v1/events?kind=hill.provider_response&limit=500"), { cache: "no-store" });
        if (!res.ok) return;
        const events = ((await res.json()) as { events: EventOut[] }).events;
        const mine = events.map((e) => e.payload as unknown as Call).filter((c) => c.match_id === matchId);
        if (!stop) setCalls(mine);
      } catch {
        /* the status bar reports an offline API */
      }
    })();
    return () => {
      stop = true;
    };
  }, [matchId, refreshKey]);

  if (calls == null) return null;
  const total = calls.reduce((s, c) => s + (c.cost_usd ?? 0), 0);

  return (
    <section aria-label="Chutes inference calls" className="rounded-md border border-line p-5 md:p-6">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-[15px] font-medium">Chutes inference for this match</p>
        <p className="font-mono text-[12px] text-ink-soft">
          {calls.length} calls · ${total.toFixed(5)} · llm.chutes.ai (Bittensor subnet 64)
        </p>
      </div>
      {calls.length === 0 ? (
        <p className="text-[14px] text-ink-soft">No paid calls: both sides were served from this match&apos;s cache or by the mock miner.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] font-mono text-[12.5px]">
            <thead>
              <tr className="border-b border-line text-left text-ink-soft">
                <th className="py-1.5 pr-3 font-normal">model</th>
                <th className="py-1.5 pr-3 font-normal">Chutes response id</th>
                <th className="py-1.5 pr-3 text-right font-normal">tokens in/out</th>
                <th className="py-1.5 pr-3 text-right font-normal">cost USD</th>
                <th className="py-1.5 text-right font-normal">HTTP</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c, i) => (
                <tr key={c.response_id ?? i} className="border-b border-line last:border-0">
                  <td className="py-1.5 pr-3">{c.reported_model ?? c.requested_model}</td>
                  <td className="py-1.5 pr-3 text-ink-soft">{c.response_id ?? "n/a"}</td>
                  <td className="py-1.5 pr-3 text-right">
                    {c.prompt_tokens ?? "?"}/{c.completion_tokens ?? "?"}
                  </td>
                  <td className="py-1.5 pr-3 text-right">{c.cost_usd == null ? "n/a" : c.cost_usd.toFixed(6)}</td>
                  <td className="py-1.5 text-right">{c.status_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
