"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { clientPath, type EventOut } from "@/lib/api";

const POLL_MS = 2500;
const CHANGES = new Set(["hill.match_started", "hill.task_scored", "hill.crowned", "hill.defended", "hill.interrupted"]);

/**
 * Polls the hill events while `active`. The first pass only finds the newest event id, so history never
 * triggers `onChange`; after that, a scored task, a crowning or a defence calls it once per poll.
 */
export function useHillEvents(active: boolean, onChange: () => void) {
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!active) return;
    let closed = false;
    let after = 0;
    let primed = false;

    async function pollOnce() {
      try {
        let changed = false;
        for (;;) {
          const res = await fetch(clientPath(`/v1/events?kind=hill&after=${after}&limit=500`), { cache: "no-store" });
          if (!res.ok) return; // 404 until the backend ships the hill; stay quiet
          const events = ((await res.json()) as { events: EventOut[] }).events;
          if (events.length === 0) break;
          after = Math.max(after, ...events.map((e) => e.event_id));
          if (events.some((e) => CHANGES.has(e.kind))) changed = true;
          if (events.length < 500) break;
        }
        if (primed && changed && !closed) onChangeRef.current();
        primed = true;
      } catch {
        /* the status bar reports an offline API */
      }
    }

    pollOnce();
    const id = setInterval(pollOnce, POLL_MS);
    return () => {
      closed = true;
      clearInterval(id);
    };
  }, [active]);
}

/** Re-renders the server page when the hill changes. Renders nothing. */
export function HillLive({ active }: { active: boolean }) {
  const router = useRouter();
  useHillEvents(active, () => router.refresh());
  return null;
}
