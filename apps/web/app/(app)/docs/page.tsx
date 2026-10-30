import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Page, PageHead } from "@/components/app/page-parts";

export const metadata: Metadata = { title: "Docs | CADRecover" };

const TOC = [
  ["task", "What a task looks like"],
  ["answer", "What a miner returns"],
  ["score", "How it is scored"],
  ["sandbox", "The sandbox"],
  ["audit", "Engines and audits"],
  ["local", "Run it locally"],
  ["api", "Read API"],
] as const;

// Excerpt of a real public record (challenge ch_fd3bc4d69d414df5, 29 Oct 2026); "..." marks fields left out.
const TASK = `{
  "challenge_id": "ch_fd3bc4d69d414df5",
  "family": "plate",
  "units": "mm",
  "frame": "Origin at the centre of the plate's bottom face. X runs along
            the width, Y along the length, Z up through the thickness.",
  "entry_point": "build_part(overrides: dict[str, float]) -> build123d.Part",
  "engine": { "build123d": "0.13.0" },
  "parameters": [
    { "name": "width",     "unit": "mm", "min": 80.0, "max": 200.0 },
    { "name": "length",    "unit": "mm", "min": 50.0, "max": 150.0 },
    { "name": "thickness", "unit": "mm", "min": 4.0,  "max": 16.0 },
    ...
  ],
  "edit_rules": [
    "Each of the 4 holes stays 10 mm from the two nearest outer edges
     when width or length changes.", ...
  ],
  "critical_features": [
    { "name": "hole_1", "kind": "hole",
      "size_tolerance_mm": 0.1, "position_tolerance_mm": 0.1 }, ...
  ],
  "drawing": { "path": "ch_fd3bc4d69d414df5/drawing.png", "sha256": "5422..." }
}`;

const ANSWER = `DRAWN = {"width": 110.0, "length": 75.0, "thickness": 10.5, "hole_diameter": 6.0}

def build_part(overrides):
    p = {**DRAWN, **overrides}       # hidden edits arrive as overrides
    ...
    return part                      # one valid build123d solid`;

const API_ROUTES = [
  ["GET", "/v1/status", "chain, counts, latest round"],
  ["GET", "/v1/runs", "rounds, newest first"],
  ["GET", "/v1/runs/{run_id}", "per-miner, per-set scores and failed checks"],
  ["GET", "/v1/challenges/{id}", "public record (values withheld while active)"],
  ["GET", "/v1/challenges/{id}/drawing.png", "the published drawing"],
  ["GET", "/v1/runs/{run_id}/miners/{uid}/models/{name}", "rebuilt GLB, candidate or reference"],
  ["GET", "/v1/leaderboard", "rolling standings and weights"],
  ["GET", "/v1/weights", "weight batches with every receipt"],
  ["GET", "/v1/commitments", "engine digests signed on chain"],
  ["GET", "/v1/audits", "audit runs and their tasks"],
  ["GET", "/v1/events/stream", "server-sent events, resumable with Last-Event-ID"],
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-32 border-t border-line pt-10 pb-14">
      <h2 className="text-2xl font-medium tracking-[-0.02em]">{title}</h2>
      <div className="mt-5 grid max-w-[72ch] gap-4 text-[15px] leading-relaxed text-ink-soft">{children}</div>
    </section>
  );
}

function Code({ children }: { children: string }) {
  return (
    <pre className="max-w-full overflow-x-auto rounded-md bg-ink p-5 font-mono text-[12.5px] leading-[1.7] text-[#e8e8e3]">
      <code>{children}</code>
    </pre>
  );
}

const C = ({ children }: { children: ReactNode }) => <code className="font-mono text-[13.5px] text-ink">{children}</code>;

export default function DocsPage() {
  return (
    <Page>
      <PageHead title="Docs">
        How a CADRecover miner is tested, end to end. Everything here matches the code in this repository; the
        protocol is version 0.2.0 and scoring is version 2.1.
      </PageHead>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-16">
        <nav aria-label="On this page" className="lg:sticky lg:top-32 lg:self-start">
          <ul className="flex gap-x-5 gap-y-2 overflow-x-auto text-[14px] lg:flex-col">
            {TOC.map(([id, label]) => (
              <li key={id} className="whitespace-nowrap">
                <a href={`#${id}`} className="text-ink-soft transition-colors hover:text-ink">
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0">
          <Section id="task" title="What a task looks like">
            <p>
              Each round the validator generates a new part, keeps its exact dimensions private, and publishes two
              things: a drawing PNG and a public record. The record names every parameter and its allowed range, the
              coordinate frame, the rules hidden edits follow, and the features that must be exactly right. It never
              contains the values; those are only on the drawing.
            </p>
            <Code>{TASK}</Code>
            <p>
              Practise on your own: <C>cadrecover task sample --family plate</C> writes a retired task (record plus
              drawing) to a folder.
            </p>
          </Section>

          <Section id="answer" title="What a miner returns">
            <p>
              The validator sends a signed job to <C>POST /v1/jobs</C> on the miner&apos;s axon and polls{" "}
              <C>GET /v1/jobs/{"{job_id}"}</C>. The answer is Python source, at most 64 KB, defining{" "}
              <C>build_part(overrides)</C>. It must read the drawing&apos;s values into parameters and apply any
              overrides, because the same code is rebuilt with edited values the miner never sees.
            </p>
            <Code>{ANSWER}</Code>
            <p>
              Requests and results are signed with the sender&apos;s hotkey. A valid signature proves who sent a
              result, never that it is correct.
            </p>
          </Section>

          <Section id="score" title="How it is scored">
            <p>
              The source is rebuilt four times: at the drawing&apos;s values and at three hidden edits. Each set gets
            </p>
            <Code>{`Q_s = V × C × (0.7 G + 0.3 D)\nQ   = mean of Q_s over the 4 sets, 0 to 100`}</Code>
            <ul className="grid gap-2">
              <li>
                <C>V</C> the build produced one valid, finite solid.
              </li>
              <li>
                <C>C</C> every critical feature is present and within 0.1 mm, and there are no extra ones. Any miss
                zeroes that set.
              </li>
              <li>
                <C>G</C> solid overlap (IoU) with the reference built at the same values.
              </li>
              <li>
                <C>D</C> the share of dimensions within tolerance.
              </li>
            </ul>
            <p>
              Hidden edits move a critical feature by more than 5× its tolerance and change the shape enough that
              copying the drawn part cannot pass. Weights come from a rolling mean over each miner&apos;s last 20
              tasks; a mean under 50 earns nothing. A validator outage is excluded for everyone, never charged to a
              miner.
            </p>
          </Section>

          <Section id="sandbox" title="The sandbox">
            <p>Miner code never runs inside the validator or API process. Each rebuild gets a fresh container with:</p>
            <ul className="grid gap-2">
              <li>no network, a non-root user, a read-only root filesystem and dropped capabilities;</li>
              <li>CPU, memory, process and output limits and a hard wall-clock timeout;</li>
              <li>no wallets, tokens, ground truth, host mounts or Docker socket inside.</li>
            </ul>
            <p>
              The geometry comes back as a STEP file and is imported by a second, constrained process. This is a
              constrained hackathon environment, not hostile-grade isolation.
            </p>
          </Section>

          <Section id="audit" title="Engines and audits">
            <p>
              Each miner packages its strategy as a Docker image and signs the image digest on chain (
              <C>cadrecover chain commit-engine</C>). The auditor takes the top miners, runs their committed image
              offline (<C>--network none --read-only --cap-drop ALL</C>) on three fresh hidden tasks, and compares.
            </p>
            <p>
              An engine passes if its audit mean is no more than 10 points under its live mean. A failure sets that
              miner&apos;s weight to zero until a clean audit, so serving one engine and committing another does not
              pay.
            </p>
          </Section>

          <Section id="local" title="Run it locally">
            <p>Linux or WSL with Docker. Everything stays on 127.0.0.1 and a local chain.</p>
            <Code>{`make envs        # three locked Python environments
make doctor      # checks envs, Docker, images, chain, miners, ports
make demo        # local chain, 5 miners, 2 rounds, audit, weights (tmux)
make api         # this site's read API on 127.0.0.1:8000
cadrecover score solution.py --task <challenge_id>   # score like a validator
ALL=1 make demo-down`}</Code>
          </Section>

          <Section id="api" title="Read API">
            <p>
              Read-only, served on 127.0.0.1:8000 by <C>make api</C>. While a challenge is active its values, failed
              checks and reference models are withheld; all of it appears once the challenge retires.
            </p>
            <ul className="mt-2 border-b border-line">
              {API_ROUTES.map(([method, path, what]) => (
                <li key={path} className="grid gap-1 border-t border-line py-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:gap-6">
                  <span className="break-all font-mono text-[12.5px] text-ink">
                    <span className="text-ink-soft">{method} </span>
                    {path}
                  </span>
                  <span className="text-[14px]">{what}</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </Page>
  );
}
