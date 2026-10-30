"use client";

import { Check, Copy } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import type { TranscriptLine } from "@/lib/landing-data";

const TONE: Record<NonNullable<TranscriptLine["tone"]> | "plain", string> = {
  cmd: "text-paper",
  head: "text-accent",
  dim: "text-[#77776f]",
  ok: "text-paper font-medium",
  plain: "text-[#cfcfc9]",
};

/** Plays the real run back line by line once it scrolls into view (instant under reduced motion). */
export function Transcript({ lines }: { lines: TranscriptLine[] }) {
  const ref = useRef<HTMLPreElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <pre ref={ref} className="overflow-x-auto px-5 py-5 font-mono text-[12.5px] leading-[1.75] md:px-6">
      <code>
        {lines.map((l, i) => (
          <span
            key={i}
            className={`block whitespace-pre transition-[opacity,transform] duration-500 ease-out-expo ${TONE[l.tone ?? "plain"]} ${
              shown ? "translate-y-0 opacity-100" : "translate-y-1 opacity-0"
            }`}
            style={{ transitionDelay: shown ? `${i * 70}ms` : "0ms" }}
          >
            {l.text}
          </span>
        ))}
      </code>
    </pre>
  );
}

export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="flex h-12 items-center justify-between gap-4 rounded-md border border-ink/15 bg-paper pl-4 pr-1.5 font-mono text-[14px]">
      <span>
        <span className="text-ink-soft">$ </span>
        {command}
      </span>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : `Copy ${command}`}
        className="inline-flex h-9 items-center gap-1.5 rounded-sm px-3 text-[13px] text-ink-soft transition-colors hover:bg-surface hover:text-ink active:translate-y-px"
      >
        {copied ? <Check size={15} weight="bold" /> : <Copy size={15} />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
