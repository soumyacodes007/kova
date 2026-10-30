import type { Metadata } from "next";

import { Badge, Page, PageHead } from "@/components/app/page-parts";

export const metadata: Metadata = { title: "Submit a model | CADRecover" };

const STEPS = [
  {
    verb: "Train",
    text: "Fine-tune an open vision model to turn a drawing into build123d code. Practice tasks come from the generator: cadrecover task sample --family flange.",
    code: null,
  },
  {
    verb: "Publish",
    text: "Upload the complete weights (not a bare LoRA adapter) to a public Hugging Face repository. The commit hash you push is the revision you submit.",
    code: null,
  },
  {
    verb: "Check",
    text: "Free and local: the repository is public, the full weights are there, the size fits a single 24 GB GPU, and the fingerprint is computed from the weight files' hashes.",
    code: "cadrecover model check --repo you/your-model --revision <commit>",
  },
  {
    verb: "Submit",
    text: "Re-checks, records the evaluation fee, then commits {repo, revision, fingerprint} on chain with your hotkey. It refuses to commit anything that would not score.",
    code: "cadrecover model submit --repo you/your-model --revision <commit> --wallet miner1",
  },
  {
    verb: "Watch",
    text: "The validator deploys your exact revision on Chutes, runs it on fresh hidden drawings against the champion, and posts every step to the leaderboard.",
    code: null,
  },
];

const RULES = [
  "Every model gets the same prompt and harness, so only the weights differ.",
  "Seeds come from a block hash after your commit plus a drand round: nobody can know the drawings in advance.",
  "Each drawing is scored at its own values and three hidden edits; a missing or misplaced hole zeroes that set.",
  "To take the hill, beat the champion's mean by the margin on the same drawings.",
  "Identical weights: the earlier commit wins, the copy is rejected.",
  "Changing the repository after committing does not change what is scored: the revision is pinned.",
];

export default function SubmitPage() {
  return (
    <Page>
      <PageHead title="Submit a model">
        Track B pays for better models, not for answers. Publish weights, commit them on chain, and take the hill on
        drawings you have never seen.
      </PageHead>
      <p className="-mt-6 mb-10">
        <Badge tone="accent">stage 2, in development: commands below are the planned interface</Badge>
      </p>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <ol className="border-b border-line">
          {STEPS.map((s) => (
            <li key={s.verb} className="grid gap-3 border-t border-line py-6 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <p className="text-xl font-medium tracking-[-0.015em]">{s.verb}</p>
              <div className="min-w-0">
                <p className="max-w-[62ch] text-[15px] leading-relaxed text-ink-soft">{s.text}</p>
                {s.code && (
                  <pre className="mt-3 overflow-x-auto rounded-md bg-ink px-4 py-3 font-mono text-[12.5px] text-paper">
                    <code>{s.code}</code>
                  </pre>
                )}
              </div>
            </li>
          ))}
        </ol>

        <aside className="self-start rounded-md border border-line p-6">
          <p className="text-[15px] font-medium">The rules</p>
          <ul className="mt-4 grid gap-3">
            {RULES.map((r) => (
              <li key={r} className="grid grid-cols-[1rem_minmax(0,1fr)] gap-2 text-[14px] leading-relaxed text-ink-soft">
                <span aria-hidden="true" className="font-mono text-accent">+</span>
                {r}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </Page>
  );
}
