import type { Metadata } from "next";
import Link from "next/link";

import { Page, PageHead } from "@/components/app/page-parts";
import { SHARED_NAV, TRACKS } from "@/components/app/nav";

export const metadata: Metadata = { title: "Tracks | CADRecover" };

const ABOUT = {
  a: {
    pitch: "Miners answer every new drawing live. The validator rebuilds each answer, scores it at the drawing's values and three hidden edits, and sets weights on chain.",
    facts: ["one new part per round", "scored in a sandbox", "engines audited offline"],
    state: "Live on localnet",
  },
  b: {
    pitch: "Miners publish models instead of answers. Each challenger meets the champion on the same hidden drawings, and only a clear win takes the top spot.",
    facts: ["models pinned to a Hugging Face revision", "run on Chutes, in a TEE", "champion served as an API"],
    state: "Stage 2, in development",
  },
} as const;

export default function TracksPage() {
  return (
    <Page>
      <PageHead title="Two ways to compete">
        Both tracks are scored by the same checker: every hole, bore and dimension measured against an exact answer.
      </PageHead>

      <div className="grid gap-4 lg:grid-cols-2">
        {(["a", "b"] as const).map((id) => {
          const t = TRACKS[id];
          const a = ABOUT[id];
          const dark = id === "b";
          return (
            <section
              key={id}
              aria-labelledby={`track-${id}`}
              className={`flex flex-col rounded-md p-7 md:p-9 ${dark ? "bg-ink text-paper" : "border border-line bg-paper shadow-card"}`}
            >
              <p className="flex items-center justify-between gap-3 font-mono text-[12.5px]">
                <span className={dark ? "text-accent" : "text-ink-soft"}>{t.label}</span>
                <span className={dark ? "text-[#a8a8a3]" : "text-ink-soft"}>{a.state}</span>
              </p>
              <h2 id={`track-${id}`} className="mt-3 text-3xl font-medium tracking-[-0.025em] md:text-[2.4rem]">
                {t.name}
              </h2>
              <p className={`mt-4 max-w-[52ch] text-[15.5px] leading-relaxed ${dark ? "text-[#c9c9c4]" : "text-ink-soft"}`}>{a.pitch}</p>
              <ul className={`mt-6 grid gap-1.5 font-mono text-[12.5px] ${dark ? "text-[#e8e8e3]" : "text-ink"}`}>
                {a.facts.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span aria-hidden="true" className="text-accent">+</span>
                    {f}
                  </li>
                ))}
              </ul>
              <nav aria-label={`${t.label} pages`} className={`mt-auto grid gap-px pt-9 ${dark ? "bg-white/10" : "bg-line"}`}>
                {t.nav.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className={`group flex items-center justify-between px-1 py-3.5 text-[15px] transition-colors ${
                      dark ? "bg-ink hover:text-accent" : "bg-paper hover:text-accent"
                    }`}
                  >
                    {n.label}
                    <span aria-hidden="true" className="font-mono text-[13px] transition-transform group-hover:translate-x-0.5">
                      {n.href}
                    </span>
                  </Link>
                ))}
              </nav>
            </section>
          );
        })}
      </div>

      <p className="mt-8 text-[14px] text-ink-soft">
        Shared by both tracks:{" "}
        {SHARED_NAV.map((n, i) => (
          <span key={n.href}>
            {i > 0 && ", "}
            <Link href={n.href} className="text-ink underline-offset-2 hover:underline">
              {n.label}
            </Link>
          </span>
        ))}
        .
      </p>
    </Page>
  );
}
