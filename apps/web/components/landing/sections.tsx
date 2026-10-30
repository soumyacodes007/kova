import Image from "next/image";

import { PartViewer } from "@/components/part-viewer";
import {
  attackChart,
  attackChartBlock,
  receipt,
  redrawCost,
  swappedEngine,
  zeroScore,
} from "@/lib/landing-data";

import { Container, Mark, PrimaryLink, SecondaryLink, SectionTitle } from "./ui";

const REFERENCE = "/assets/flange-reference.glb";
const CANDIDATE = "/assets/flange-candidate.glb";
const MARKERS = "/assets/flange-markers.glb";

export function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur-sm">
      <Container className="flex h-16 items-center justify-between gap-6">
        <a href="#top" className="flex items-center gap-2.5 text-[15px] font-semibold tracking-[-0.01em]">
          <Mark className="h-6 w-6" />
          CADRecover
        </a>
        <nav aria-label="Sections" className="hidden items-center gap-8 text-[14px] text-ink-soft md:flex">
          <a href="#check" className="transition-colors hover:text-ink">The check</a>
          <a href="#how" className="transition-colors hover:text-ink">How it works</a>
          <a href="#proof" className="transition-colors hover:text-ink">Proof</a>
        </nav>
        <PrimaryLink href="#run">Run the demo</PrimaryLink>
      </Container>
    </header>
  );
}

export function Hero() {
  return (
    <section id="top" className="overflow-hidden">
      <Container className="grid items-center gap-12 pb-24 pt-10 md:pt-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-14 lg:pb-28 lg:pt-16">
        <div>
          <h1 className="text-4xl font-medium leading-[1.04] tracking-[-0.035em] md:text-5xl lg:text-[3.15rem] xl:text-[3.5rem]">
            Engineering drawings in.
            <br className="hidden sm:block" /> Machinable CAD out.
          </h1>
          <p className="mt-6 max-w-[44ch] text-[17px] leading-relaxed text-ink-soft">
            An open Bittensor network where miners compete to turn drawings into parametric CAD, checked to a tenth
            of a millimetre.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <PrimaryLink href="#run">Run the demo</PrimaryLink>
            <SecondaryLink href="#proof">See the proof</SecondaryLink>
          </div>
        </div>

        <figure className="relative">
          <div className="overflow-hidden rounded-md border border-line bg-[#f3efe6] shadow-card">
            <Image
              src="/assets/flange-drawing.webp"
              alt={`Engineering drawing ${zeroScore.drawingNumber} of a vacuum flange: top view, side view and iso view with dimensions`}
              width={1800}
              height={1134}
              priority
              sizes="(min-width: 1024px) 58vw, 100vw"
              className="h-auto w-full"
            />
          </div>
          <div className="absolute -bottom-12 left-3 aspect-square w-[42%] overflow-hidden rounded-md border border-line bg-paper shadow-card md:-bottom-16 md:left-6 md:w-[33%]">
            <PartViewer layers={[{ url: REFERENCE, tone: "part" }]} label="The flange from the drawing, rebuilt in 3D" />
          </div>
          <figcaption className="mt-4 pl-[calc(42%+1.25rem)] text-[13px] leading-snug text-ink-soft md:pl-[calc(33%+2.5rem)]">
            Drawing {zeroScore.drawingNumber} and the part it describes, rebuilt from code. Drag to turn it.
          </figcaption>
        </figure>
      </Container>
    </section>
  );
}

export function Statement() {
  return (
    <section className="border-t border-line">
      <Container className="grid gap-12 py-20 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:items-end md:py-28">
        <p className="max-w-[26ch] text-2xl font-medium leading-[1.15] tracking-[-0.02em] md:text-[2.4rem]">
          Factories keep drawers of drawings for parts nobody can make anymore.{" "}
          <span className="text-ink-soft">The 3D files are gone.</span>
        </p>
        <div className="md:justify-self-end">
          <p className="font-mono text-5xl tracking-[-0.04em] md:text-6xl">{redrawCost}</p>
          <p className="mt-3 max-w-[30ch] text-[15px] leading-relaxed text-ink-soft">
            to redraw one part by hand, at the price one 2D-to-3D conversion provider quotes.
          </p>
        </div>
      </Container>
    </section>
  );
}

export function ZeroScore() {
  return (
    <section id="check" className="bg-surface">
      <Container className="py-20 md:py-28">
        <SectionTitle>Looks right. Scores zero.</SectionTitle>
        <p className="mt-5 max-w-[60ch] text-[17px] leading-relaxed text-ink-soft">
          This miner built the flange with its bolt circle {zeroScore.boltCircleError} too wide. To the eye it is
          the same part. The checker measures every hole and rejects it.
        </p>

        <div className="mt-12 grid gap-4 md:grid-cols-2">
          <div className="overflow-hidden rounded-md border border-line bg-paper">
            <p className="border-b border-line px-4 py-3 text-[13px] text-ink-soft">What the drawing says</p>
            <div className="aspect-[4/3]">
              <PartViewer layers={[{ url: REFERENCE, tone: "part" }]} label="Reference flange built from the drawing" />
            </div>
          </div>
          <div className="overflow-hidden rounded-md border border-line bg-paper">
            <p className="border-b border-line px-4 py-3 text-[13px] text-ink-soft">What the miner built</p>
            <div className="aspect-[4/3]">
              <PartViewer
                layers={[
                  { url: CANDIDATE, tone: "part" },
                  { url: MARKERS, tone: "fail" },
                ]}
                label="Miner's flange with its six misplaced bolt holes outlined in red"
              />
            </div>
            <p className="border-t border-line px-4 py-3 font-mono text-[12.5px] text-fail">
              bolt_1 to bolt_{zeroScore.holes}: centre off by {zeroScore.holeOffset} (tolerance {zeroScore.tolerance})
            </p>
          </div>
        </div>

        <dl className="mt-12 grid gap-8 border-t border-ink/10 pt-8 sm:grid-cols-3">
          <div>
            <dt className="text-[14px] text-ink-soft">Shape overlap with the right part</dt>
            <dd className="mt-2 font-mono text-4xl tracking-[-0.03em]">{zeroScore.shapeOverlap}</dd>
          </div>
          <div>
            <dt className="text-[14px] text-ink-soft">Dimensions within tolerance</dt>
            <dd className="mt-2 font-mono text-4xl tracking-[-0.03em]">{zeroScore.dimensionsInTolerance}</dd>
          </div>
          <div>
            <dt className="text-[14px] text-ink-soft">Score for this set</dt>
            <dd className="mt-2 font-mono text-4xl tracking-[-0.03em] text-fail">{zeroScore.score}</dd>
          </div>
        </dl>
      </Container>
    </section>
  );
}

// Excerpt of the flange solution template (src/cadrecover/miner/templates.py), hub omitted.
const SNIPPET = `def build_part(overrides):
    p = {**DRAWN, **overrides}
    t = p["thickness"]
    part = Cylinder(p["outer_diameter"] / 2, t,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
    part -= Pos(0, 0, t / 2) * Cylinder(p["bore_diameter"] / 2, 3 * t)
    r = p["bolt_circle_diameter"] / 2
    n = int(DRAWN["bolt_count"])
    for k in range(n):
        a = 2 * math.pi * k / n
        hole = Cylinder(p["bolt_hole_diameter"] / 2, 3 * t)
        part -= Pos(r * math.cos(a), r * math.sin(a), t / 2) * hole
    return part`;

export function HowItWorks() {
  return (
    <section id="how" className="border-t border-line">
      <Container className="py-20 md:py-28">
        <SectionTitle>How a round works</SectionTitle>

        <div className="mt-12 grid gap-4 md:grid-cols-5">
          <article className="flex flex-col overflow-hidden rounded-md border border-line bg-[#f3efe6] md:col-span-2 md:row-span-2">
            <div className="p-6">
              <h3 className="text-xl font-medium tracking-[-0.015em]">Draw</h3>
              <p className="mt-2 max-w-[38ch] text-[15px] leading-relaxed text-ink-soft">
                The validator generates a new part, draws it like an old scanned blueprint, and keeps the exact
                answer private.
              </p>
            </div>
            <div className="relative mt-auto aspect-square w-full">
              <Image
                src="/assets/flange-drawing-top.webp"
                alt="Top view of the flange drawing: six bolt holes on a 116.5 mm bolt circle"
                fill
                sizes="(min-width: 768px) 40vw, 100vw"
                className="object-cover object-top"
              />
            </div>
          </article>

          <article className="overflow-hidden rounded-md bg-ink text-paper md:col-span-3">
            <div className="p-6">
              <h3 className="text-xl font-medium tracking-[-0.015em]">Build</h3>
              <p className="mt-2 max-w-[48ch] text-[15px] leading-relaxed text-[#c9c9c4]">
                Miners reply with build123d code that takes the drawing&apos;s dimensions as parameters.
              </p>
            </div>
            <pre className="overflow-x-auto border-t border-white/10 px-6 py-5 font-mono text-[12.5px] leading-[1.6] text-[#e8e8e3]">
              <code>{SNIPPET}</code>
            </pre>
          </article>

          <article className="rounded-md border border-line bg-paper p-6 shadow-card md:col-span-3">
            <h3 className="text-xl font-medium tracking-[-0.015em]">Check</h3>
            <p className="mt-2 max-w-[52ch] text-[15px] leading-relaxed text-ink-soft">
              The code is rebuilt at the drawing&apos;s values and at three hidden edits. A missing or misplaced
              hole zeroes that set, so copying the picture is not enough.
            </p>
            <p className="mt-5 font-mono text-[13px] text-ink">Q = V &times; C &times; (0.7 G + 0.3 D), averaged over 4 sets</p>
          </article>

          <article className="grid gap-6 rounded-md border border-accent/40 bg-accent/[0.07] p-6 md:col-span-5 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:items-center">
            <div>
              <h3 className="text-xl font-medium tracking-[-0.015em]">Settle</h3>
              <p className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-ink-soft">
                Scores become weights on chain. Each miner commits the hash of its engine image, and audits re-run
                that engine offline on fresh tasks.
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-4 font-mono text-[13px]">
              <div>
                <dt className="text-ink-soft">weights committed</dt>
                <dd className="mt-1 text-2xl text-ink">block {receipt.committedAt}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">weights revealed</dt>
                <dd className="mt-1 text-2xl text-ink">block {receipt.revealedAt}</dd>
              </div>
            </dl>
          </article>
        </div>
      </Container>
    </section>
  );
}

export function Proof() {
  return (
    <section id="proof" className="border-t border-line">
      <Container className="grid gap-14 py-20 md:py-28 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)]">
        <div>
          <SectionTitle>What cheating earns</SectionTitle>
          <p className="mt-5 max-w-[56ch] text-[17px] leading-relaxed text-ink-soft">
            Five miners on a fresh local Bittensor network: two honest, three built to cheat or fail. Weights read
            back from the chain at block {attackChartBlock}.
          </p>

          <div className="mt-10 grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 text-[13px] text-ink-soft sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto]">
            <span>Miner</span>
            <span className="hidden sm:block">Mean score</span>
            <span className="text-right">Weight</span>
          </div>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {attackChart.map((row) => (
              <li
                key={row.miner}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-2 py-4 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto]"
              >
                <div>
                  <p className="font-mono text-[14px]">{row.miner}</p>
                  <p className="text-[13px] text-ink-soft">{row.behaviour}</p>
                </div>
                <div className="col-span-2 flex items-center gap-3 sm:col-span-1">
                  <span className="w-10 font-mono text-[14px]">{row.meanQ}</span>
                  <span
                    aria-hidden="true"
                    className={`h-1.5 rounded-sm ${row.honest ? "bg-accent" : "bg-ink/35"}`}
                    style={{ width: `${Math.max(row.meanQ, 1.5) * 0.9}%` }}
                  />
                </div>
                <p className="row-start-1 text-right font-mono text-[15px] sm:row-start-auto">{row.weight.toFixed(2)}</p>
              </li>
            ))}
          </ul>
        </div>

        <aside className="self-end rounded-md bg-ink p-7 text-paper">
          <h3 className="text-xl font-medium tracking-[-0.015em]">The swapped engine</h3>
          <p className="mt-3 text-[15px] leading-relaxed text-[#c9c9c4]">
            A miner served a good engine live but committed a bad one on chain. The audit re-ran the committed
            engine on hidden tasks.
          </p>
          <dl className="mt-7 grid grid-cols-2 gap-4 font-mono">
            <div>
              <dt className="text-[12.5px] text-[#a8a8a3]">live score</dt>
              <dd className="mt-1 text-3xl">{swappedEngine.live}</dd>
            </div>
            <div>
              <dt className="text-[12.5px] text-[#a8a8a3]">audit score</dt>
              <dd className="mt-1 text-3xl text-accent">{swappedEngine.audit}</dd>
            </div>
          </dl>
          <p className="mt-7 border-t border-white/10 pt-5 text-[14px] text-[#e8e8e3]">
            Weight revoked on chain at block {swappedEngine.revokedAtBlock}.
          </p>
        </aside>
      </Container>
    </section>
  );
}

export function RunIt() {
  return (
    <section id="run" className="border-t border-line bg-surface">
      <Container className="grid gap-10 py-20 md:grid-cols-2 md:items-center md:py-28">
        <div>
          <SectionTitle>Run the whole network on your laptop</SectionTitle>
          <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-ink-soft">
            One command starts a local chain, five miners, a validator and an audit, then shows the weights landing
            on chain. Needs Linux or WSL and Docker.
          </p>
        </div>
        <pre className="overflow-x-auto rounded-md bg-ink p-6 font-mono text-[14px] leading-[1.8] text-[#e8e8e3]">
          <code>
            <span className="text-[#8f8f8a]"># three panes in tmux: validator, events, status</span>
            {"\n"}make demo
            {"\n\n"}
            <span className="text-[#8f8f8a]"># the same run, plain output, exit 1 on any failure</span>
            {"\n"}DEMO_HEADLESS=1 make demo
            {"\n\n"}
            <span className="text-[#8f8f8a]"># stop everything, chain included</span>
            {"\n"}ALL=1 make demo-down
          </code>
        </pre>
      </Container>
    </section>
  );
}

const NEXT = [
  { verb: "Publish", text: "Miners publish fine-tuned open models instead of answering each drawing live." },
  { verb: "Challenge", text: "The validator tests each challenger offline on fresh hidden drawings. A clearly better score takes the top spot." },
  { verb: "Serve", text: "The champion model reads customers' drawings through Chutes, inside secure enclaves." },
];

export function Next() {
  return (
    <section className="border-t border-line">
      <Container className="py-20 md:py-28">
        <div className="flex flex-wrap items-center gap-4">
          <SectionTitle>Next: king of the hill</SectionTitle>
          <span className="rounded-sm border border-ink/20 px-2 py-1 font-mono text-[12px] text-ink-soft">Planned</span>
        </div>
        <ol className="mt-12 grid gap-10 md:grid-cols-[repeat(3,minmax(0,1fr))] md:gap-12">
          {NEXT.map((n) => (
            <li key={n.verb} className="border-t-2 border-ink pt-5">
              <p className="text-2xl font-medium tracking-[-0.02em]">{n.verb}</p>
              <p className="mt-3 max-w-[34ch] text-[15px] leading-relaxed text-ink-soft">{n.text}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line">
      <Container className="flex flex-col gap-4 py-10 text-[13px] text-ink-soft md:flex-row md:items-center md:justify-between">
        <p className="flex items-center gap-2.5 font-medium text-ink">
          <Mark className="h-5 w-5" />
          CADRecover
        </p>
        <p>Runs on local and test networks only. Ground truth never leaves the validator.</p>
      </Container>
    </footer>
  );
}
